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
from app.pipeline.stages import assemble, plan, practice, sequence, write
from app.schemas.study_guide import StudyGuideContent

log = logging.getLogger(__name__)

STAGES = ("plan", "sequence", "write_sections", "assemble", "practice", "check")


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

    def __post_init__(self) -> None:
        self.index = SourceIndex(self.segments)


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
            state["check"] = check(state)
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
    ctx.state.setdefault("sections", {})[concept_id] = section
    ctx.state["check"] = check(ctx.state)
    ctx.save("regenerate_section")
    ctx.emit("section_ready", {"section_id": concept_id, "regenerated": True})
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


def _sections(state: dict) -> list[dict]:
    sections = state.get("sections", {})
    return [sections[c["id"]] for c in state["sequence"]["concepts"] if c["id"] in sections]


def check(state: dict) -> dict:
    """Deterministic checks over the assembled guide. The model review is added in the quality stage."""
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
    return {
        "missing_sections": missing,
        "unverified_quotes": unverified,
        "section_flags": flagged,
        "unreferenced_questions": unreferenced_questions,
    }


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
