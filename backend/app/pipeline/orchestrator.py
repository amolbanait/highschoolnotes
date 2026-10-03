"""Runs the pipeline stage by stage, saving after each so a crashed job resumes where it stopped.

This module knows nothing about the database: the worker passes `save` and `emit` callbacks,
and the CLI passes in-memory ones. Stages 1 and 2 (extract, segment) run when a source is
uploaded; a guide starts from stored segments.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.llm.client import LLM, TokenMeter
from app.pipeline.grounding import SourceIndex
from app.pipeline.stages import assemble, plan, practice, review, sequence, write
from app.quality.checks import coverage
from app.schemas.study_guide import StudyGuideContent

log = logging.getLogger(__name__)

STAGES = ("plan", "sequence", "write_sections", "review", "assemble", "practice", "check")


@dataclass
class PipelineContext:
    segments: list[dict]
    level: str
    llm: LLM
    meter: TokenMeter
    settings: Settings
    state: dict[str, Any]
    save: Callable[[str], None]
    emit: Callable[[str, dict], None]
    reviewer: LLM | None = None  # the quality reviewer; the writer model if not given

    def __post_init__(self) -> None:
        self.index = SourceIndex(self.segments)
        if self.reviewer is None:
            self.reviewer = self.llm


def run(ctx: PipelineContext) -> dict:
    state = ctx.state
    for number, stage in enumerate(STAGES, start=1):
        if stage in state.get("done", []):
            continue
        ctx.emit("stage", {"stage": stage, "step": number, "total_steps": len(STAGES)})
        if stage == "plan":
            state["plan"] = plan.run(ctx.segments, ctx.level, ctx.llm, ctx.meter, ctx.settings)
        elif stage == "sequence":
            state["sequence"] = sequence.run(state["plan"], ctx.index)
            if not state["sequence"]["concepts"]:
                raise PipelineError("no_concepts", "No teachable concepts were found in this material.")
            ctx.emit(
                "topics_detected",
                {
                    "title": state["sequence"]["title"],
                    "topics": state["sequence"]["topics"],
                    "concepts": [{"id": c["id"], "title": c["title"]} for c in state["sequence"]["concepts"]],
                },
            )
        elif stage == "write_sections":
            _write_sections(ctx)
        elif stage == "review":
            if ctx.settings.review_enabled:
                _review_sections(ctx)
        elif stage == "assemble":
            state["assemble"] = assemble.run(
                state["sequence"]["title"], _sections(state), ctx.level, ctx.llm, ctx.meter, ctx.settings
            )
        elif stage == "practice":
            seq = state["sequence"]
            state["practice"] = practice.run(
                _sections(state),
                seq["vocabulary"],
                seq["facts"],
                ctx.index,
                ctx.level,
                ctx.llm,
                ctx.meter,
                ctx.settings,
            )
        elif stage == "check":
            state["check"] = check(state, ctx.index)
        state.setdefault("done", []).append(stage)
        ctx.save(stage)
    return build_content(state, ctx.level)


def regenerate_section(ctx: PipelineContext, concept_id: str, instruction: str | None) -> dict:
    concepts = ctx.state["sequence"]["concepts"]
    concept = next((c for c in concepts if c["id"] == concept_id), None)
    if concept is None:
        raise PipelineError("not_found", "That section does not exist.")
    ctx.emit("stage", {"stage": "regenerate_section", "section_id": concept_id})
    section = write.run_one(
        concept, concepts, ctx.index, ctx.level, ctx.llm, ctx.meter, ctx.settings, instruction
    )
    if ctx.settings.review_enabled:
        section, report = review.run_one(
            section,
            concept,
            concepts,
            ctx.index,
            ctx.level,
            ctx.llm,
            ctx.reviewer,
            ctx.meter,
            ctx.settings,
            instruction=instruction,
        )
        ctx.state.setdefault("reviews", {})[concept_id] = report
    ctx.state.setdefault("sections", {})[concept_id] = section
    ctx.state["check"] = check(ctx.state, ctx.index)
    ctx.save("regenerate_section")
    ctx.emit("section_ready", {"section_id": concept_id, "regenerated": True})
    if section["quality"].get("needs_checking"):
        ctx.emit("quality_flag", _flag_event(section))
    return build_content(ctx.state, ctx.level)


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _write_sections(ctx: PipelineContext) -> None:
    concepts = ctx.state["sequence"]["concepts"]
    sections = ctx.state.setdefault("sections", {})
    todo = [c for c in concepts if c["id"] not in sections]
    done = len(concepts) - len(todo)
    with ThreadPoolExecutor(max_workers=max(1, ctx.settings.write_concurrency)) as pool:
        futures = {
            pool.submit(write.run_one, c, concepts, ctx.index, ctx.level, ctx.llm, ctx.meter, ctx.settings): c
            for c in todo
        }
        error: BaseException | None = None
        for future in as_completed(futures):
            concept = futures[future]
            try:
                sections[concept["id"]] = future.result()
            except BaseException as exc:  # keep the first failure; let calls already running finish
                if error is None:
                    error = exc
                    for f in futures:
                        f.cancel()
                continue
            done += 1
            # Saved one by one in this thread, so a failure keeps every finished (and paid-for) section.
            ctx.save("write_sections")
            ctx.emit(
                "section_ready",
                {
                    "stage": "write_sections",
                    "section_id": concept["id"],
                    "done": done,
                    "total": len(concepts),
                },
            )
        if error is not None:
            raise error


def _review_sections(ctx: PipelineContext) -> None:
    concepts = ctx.state["sequence"]["concepts"]
    sections = ctx.state["sections"]
    reviews = ctx.state.setdefault("reviews", {})
    todo = [c for c in concepts if c["id"] in sections and c["id"] not in reviews]
    done = len(concepts) - len(todo)
    with ThreadPoolExecutor(max_workers=max(1, ctx.settings.write_concurrency)) as pool:
        futures = {
            pool.submit(
                review.run_one,
                sections[c["id"]],
                c,
                concepts,
                ctx.index,
                ctx.level,
                ctx.llm,
                ctx.reviewer,
                ctx.meter,
                ctx.settings,
            ): c
            for c in todo
        }
        error: BaseException | None = None
        for future in as_completed(futures):
            concept = futures[future]
            try:
                section, report = future.result()
            except BaseException as exc:  # keep the first failure; finished reviews stay saved
                if error is None:
                    error = exc
                    for f in futures:
                        f.cancel()
                continue
            done += 1
            sections[concept["id"]] = section
            reviews[concept["id"]] = report
            ctx.save("review")
            ctx.emit(
                "section_reviewed",
                {
                    "stage": "review",
                    "section_id": concept["id"],
                    "action": report["action"],
                    "done": done,
                    "total": len(concepts),
                },
            )
            if report["action"] == "regenerated":
                ctx.emit(
                    "section_ready", {"stage": "review", "section_id": concept["id"], "regenerated": True}
                )
            if section["quality"].get("needs_checking"):
                ctx.emit("quality_flag", _flag_event(section))
        if error is not None:
            raise error


def _flag_event(section: dict) -> dict:
    quality = section["quality"]
    return {
        "section_id": section["id"],
        "title": section["title"],
        "score": quality.get("score"),
        "problems": quality.get("problems", []),
    }


def quality_score(state: dict) -> int | None:
    """The guide's score: the mean of its reviewed sections' scores."""
    scores = [r["score"] for r in state.get("reviews", {}).values() if r.get("score") is not None]
    return round(sum(scores) / len(scores)) if scores else None


def _sections(state: dict) -> list[dict]:
    sections = state.get("sections", {})
    return [sections[c["id"]] for c in state["sequence"]["concepts"] if c["id"] in sections]


def check(state: dict, index: SourceIndex | None = None) -> dict:
    """Guide-level checks done by code, after the per-section review."""
    seq = state["sequence"]
    sections = state.get("sections", {})
    missing = [c["id"] for c in seq["concepts"] if c["id"] not in sections]
    unverified = [f["id"] for f in seq["facts"] if not f["verified"]]
    unverified += [v["id"] for v in seq["vocabulary"] if not v["verified"]]
    unverified += [m["id"] for m in seq["formulas"] if not m["verified"]]
    flagged = {cid: s["quality"]["flags"] for cid, s in sections.items() if s["quality"]["flags"]}
    unreferenced_questions = [
        q["id"] for q in state.get("practice", {}).get("questions", []) if not q["source_refs"]
    ]
    result = {
        "missing_sections": missing,
        "unverified_quotes": unverified,
        "section_flags": flagged,
        "needs_checking": [cid for cid, s in sections.items() if s["quality"].get("needs_checking")],
        "unreferenced_questions": unreferenced_questions,
        "quality_score": quality_score(state),
    }
    if index is not None:
        result["coverage"] = coverage(state, index)
    return result


def build_content(state: dict, level: str) -> dict:
    """The guide document from whatever stages have finished (partial while running)."""
    seq = state.get("sequence")
    if not seq:
        return StudyGuideContent(title="Study guide", level=level).model_dump(by_alias=True)
    framing = state.get("assemble", {})
    practice_out = state.get("practice", {})
    warnings = list(seq.get("warnings", []))
    checks = state.get("check")
    if checks and checks["unverified_quotes"]:
        warnings.append(
            f"{len(checks['unverified_quotes'])} quoted item(s) could not be matched word for word to the source; "
            "they are marked for checking."
        )
    if checks and checks.get("needs_checking"):
        count = len(checks["needs_checking"])
        warnings.append(
            f"{count} section(s) could not be fully confirmed against your material; "
            'they are marked "Check this against your source".'
        )
    gaps = (checks or {}).get("coverage") or {}
    if gaps.get("uncited_share", 0) > 0.25:
        where = f" ({'; '.join(gaps['uncited_headings'][:4])})" if gaps.get("uncited_headings") else ""
        warnings.append(
            f"About {round(gaps['uncited_share'] * 100)}% of your material is not used in this guide{where}. "
            "Check whether anything important is missing."
        )
    content = StudyGuideContent(
        title=seq["title"],
        level=level,
        topics=seq["topics"],
        overview=framing.get("overview"),
        objectives=framing.get("objectives", []),
        vocabulary=seq["vocabulary"],
        concepts=_sections(state),
        facts=seq["facts"],
        formulas=seq["formulas"],
        relationships=seq["relationships"],
        summary=framing.get("summary"),
        questions=practice_out.get("questions", []),
        flashcards=practice_out.get("flashcards", []),
        review_checklist=framing.get("review_checklist", []),
        not_covered=seq.get("not_covered", []),
        warnings=warnings,
    )
    return content.model_dump(by_alias=True)
