"""Quality review: code checks, then a separate model scores each section against its source.

A section scoring below the threshold is written again once with the reviewer's problems
attached, and reviewed again. The better of the two versions is kept; if even that is below
the threshold, the section is flagged so the student checks it against the source.
"""

import logging

from app.core.config import Settings
from app.llm.client import LLM, LLMError, TokenMeter
from app.llm.prompts import review as prompt
from app.pipeline.grounding import SourceIndex
from app.pipeline.stages import write
from app.quality.checks import section_checks
from app.schemas.study_guide import ReviewOutput

log = logging.getLogger(__name__)

# Weights of each criterion in the section score. Visuals count only when there is a diagram.
WEIGHTS = {"accuracy": 0.35, "grounding": 0.25, "examples": 0.15, "clarity": 0.15, "visuals": 0.10}
# A major problem of these kinds means a student could learn something false: the section
# cannot pass, whatever its other scores.
FAILING_KINDS = {"inaccurate", "unsupported", "changed_formula_or_number", "mislabelled_origin"}
FAILING_CAP = 60
# Errors that should not stop a guide: the section is shown unreviewed instead.
SKIPPABLE = {"model_refused", "invalid_output", "output_too_long", "ai_bad_request"}


def score(review: dict, checks: dict) -> int:
    scores = {k: v for k, v in review["scores"].items() if v is not None}
    weight = sum(WEIGHTS[k] for k in scores)
    total = sum(WEIGHTS[k] * max(0, min(100, v)) for k, v in scores.items()) / weight if weight else 0
    result = round(total)
    if any(p["severity"] == "major" and p["kind"] in FAILING_KINDS for p in review["problems"]):
        result = min(result, FAILING_CAP)
    if checks.get("no_source_reference"):
        result = min(result, FAILING_CAP)
    return result


def review_once(
    section: dict, index: SourceIndex, level: str, llm: LLM, meter: TokenMeter, settings: Settings
) -> dict:
    checks = section_checks(section, index, level)
    segments = index.context_for(section["source_refs"]) or index.segments[:24]
    system, user = prompt.build(section, segments, level, checks)
    output, usage = llm.generate(
        stage="review", system=system, prompt=user, output=ReviewOutput, effort=settings.review_effort
    )
    meter.add("review", usage)
    review = output.model_dump()
    return {**review, "checks": checks, "score": score(review, checks)}


def run_one(
    section: dict,
    concept: dict,
    concepts: list[dict],
    index: SourceIndex,
    level: str,
    writer: LLM,
    reviewer: LLM,
    meter: TokenMeter,
    settings: Settings,
    instruction: str | None = None,
) -> tuple[dict, dict]:
    """Review a written section, rewriting it once if needed. Returns (section, report)."""
    threshold = settings.quality_threshold
    try:
        first = review_once(section, index, level, reviewer, meter, settings)
    except LLMError as exc:
        if exc.code not in SKIPPABLE:
            raise
        log.warning("review of %s skipped: %s", section["id"], exc.code)
        return _apply(section, None, "not_reviewed", rewritten=False), {
            "section_id": section["id"],
            "action": "not_reviewed",
            "score": None,
            "attempts": [],
            "error": exc.code,
        }
    attempts = [first]
    best, best_review, rewritten = section, first, False
    if first["score"] < threshold:
        retry = write.run_one(
            concept,
            concepts,
            index,
            level,
            writer,
            meter,
            settings,
            instruction=instruction,
            feedback=prompt.feedback(first["problems"]),
        )
        try:
            second = review_once(retry, index, level, reviewer, meter, settings)
        except LLMError as exc:
            if exc.code not in SKIPPABLE:
                raise
            second = None
        if second is not None:
            attempts.append(second)
            if second["score"] >= first["score"]:
                best, best_review, rewritten = retry, second, True
    if best_review["score"] >= threshold:
        action = "regenerated" if rewritten else "passed"
    else:
        action = "flagged"
    report = {
        "section_id": section["id"],
        "action": action,
        "score": best_review["score"],
        "attempts": attempts,
        "kept_attempt": attempts.index(best_review) + 1,
    }
    return _apply(best, best_review, action, rewritten), report


def _apply(section: dict, review: dict | None, action: str, rewritten: bool) -> dict:
    quality = dict(section.get("quality") or {"score": None, "flags": []})
    flags = [f for f in quality.get("flags", []) if f not in ("needs_checking", "not_reviewed")]
    if review is None:
        flags.append("not_reviewed")
        quality.update(score=None, reviewed=False, rewritten=False, needs_checking=False, problems=[])
    else:
        needs_checking = action == "flagged"
        if needs_checking:
            flags.append("needs_checking")
        if review["checks"].get("reading_level_high"):
            flags.append("reading_level_high")
        majors = [p["problem"] for p in review["problems"] if p["severity"] == "major"]
        quality.update(
            score=review["score"],
            reviewed=True,
            rewritten=rewritten,
            needs_checking=needs_checking,
            problems=majors[:5] if needs_checking else [],
        )
    quality["flags"] = list(dict.fromkeys(flags))
    return {**section, "quality": quality}
