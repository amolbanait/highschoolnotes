"""The Postgres job queue and the job handlers the worker runs.

Jobs are claimed with SELECT ... FOR UPDATE SKIP LOCKED, so several workers can run safely.
A job whose worker died is reclaimed once its lock expires, and resumes from its saved state.
"""

import copy
import logging
import socket
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import Settings
from app.db.models import (
    GenerationJob,
    GuideEvent,
    GuideSource,
    QualityReport,
    Source,
    SourceSegment,
    StudyGuide,
)
from app.ingestion.base import ExtractionError
from app.ingestion.registry import get_extractor
from app.ingestion.segment import segment, word_count
from app.llm.client import LLM, LLMError, TokenMeter
from app.pipeline import orchestrator
from app.pipeline.orchestrator import PipelineContext, PipelineError
from app.storage.files import Storage

log = logging.getLogger(__name__)

WORKER_ID = f"{socket.gethostname()}-{uuid.uuid4().hex[:6]}"
RETRYABLE = {"ai_busy", "ai_unavailable", "ai_unreachable"}


def now() -> datetime:
    return datetime.now(UTC)


def enqueue(
    db: Session, kind: str, *, guide_id=None, source_id=None, params: dict | None = None
) -> GenerationJob:
    job = GenerationJob(
        kind=kind, guide_id=guide_id, source_id=source_id, params=params or {}, status="queued"
    )
    db.add(job)
    db.flush()
    return job


def add_event(db: Session, guide_id: uuid.UUID, type_: str, data: dict[str, Any]) -> None:
    db.add(GuideEvent(guide_id=guide_id, type=type_, data={"guide_id": str(guide_id), **data}))


def claim(db: Session, settings: Settings) -> GenerationJob | None:
    current = now()
    job = db.execute(
        select(GenerationJob)
        .where(
            or_(
                (GenerationJob.status == "queued") & (GenerationJob.run_after <= current),
                (GenerationJob.status == "running") & (GenerationJob.locked_until < current),
            )
        )
        .order_by(GenerationJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).scalar_one_or_none()
    if job is None:
        return None
    job.status = "running"
    job.attempts += 1
    job.locked_by = WORKER_ID
    job.locked_until = current + timedelta(seconds=settings.job_lock_seconds)
    db.commit()
    return job


def heartbeat(db: Session, job: GenerationJob, settings: Settings) -> None:
    job.locked_until = now() + timedelta(seconds=settings.job_lock_seconds)


def run_job(
    Session_: sessionmaker[Session],
    job_id: uuid.UUID,
    llm: LLM,
    storage: Storage,
    settings: Settings,
    reviewer: LLM | None = None,
) -> None:
    with Session_() as db:
        job = db.get(GenerationJob, job_id)
        if job is None:
            return
        if job.attempts > settings.job_max_attempts:
            _fail(db, job, "too_many_attempts", "This job failed repeatedly and was stopped.")
            return
        try:
            if job.kind == "extract":
                run_extract(db, job, storage, settings)
            elif job.kind == "generate":
                run_generate(db, job, llm, settings, reviewer)
            elif job.kind == "regenerate_section":
                run_regenerate(db, job, llm, settings, reviewer)
            else:
                _fail(db, job, "unknown_job", f"Unknown job kind {job.kind}")
        except LLMError as exc:
            db.rollback()
            if exc.code in RETRYABLE and job.attempts < settings.job_max_attempts:
                _retry_later(db, job, exc.code, exc.message)
            else:
                _fail(db, job, exc.code, exc.message)
        except PipelineError as exc:
            db.rollback()
            _fail(db, job, exc.code, exc.message)
        except Exception:
            log.exception("job %s (%s) crashed", job.id, job.kind)
            db.rollback()
            if job.attempts < settings.job_max_attempts:
                _retry_later(db, job, "internal_error", "Something went wrong; retrying.")
            else:
                _fail(db, job, "internal_error", "Something went wrong while making this guide.")


def _retry_later(db: Session, job: GenerationJob, code: str, message: str) -> None:
    job = db.merge(job)
    job.status = "queued"
    job.locked_by = None
    job.locked_until = None
    job.run_after = now() + timedelta(seconds=15 * job.attempts)
    job.error = {"code": code, "message": message}
    db.commit()


def _fail(db: Session, job: GenerationJob, code: str, message: str) -> None:
    job = db.merge(job)
    job.status = "failed"
    job.error = {"code": code, "message": message}
    job.finished_at = now()
    job.locked_by = None
    if job.kind == "extract" and job.source_id:
        source = db.get(Source, job.source_id)
        if source:
            source.status = "failed"
            source.error = {"code": code, "message": message}
    if job.guide_id:
        guide = db.get(StudyGuide, job.guide_id)
        if guide and job.kind == "generate":
            guide.status = "failed"
        add_event(db, job.guide_id, "failed", {"code": code, "message": message, "job_id": str(job.id)})
    db.commit()


def _finish(db: Session, job: GenerationJob) -> None:
    job.status = "done"
    job.finished_at = now()
    job.locked_by = None
    job.error = None
    db.commit()


# ---------- extract ----------


def run_extract(db: Session, job: GenerationJob, storage: Storage, settings: Settings) -> None:
    source = db.get(Source, job.source_id)
    if source is None:
        _finish(db, job)
        return
    try:
        data = storage.get(source.storage_key)
        result = get_extractor(source.kind).extract(data)
        if result.page_count and result.page_count > settings.max_pages:
            raise ExtractionError(
                "source_too_long",
                f"This file has {result.page_count} pages. The limit is {settings.max_pages} pages per guide; "
                "split it into parts and upload each one.",
            )
        segments = segment(result)
        words = sum(word_count(s.text) for s in segments)
        if words == 0:
            raise ExtractionError("no_text", "No readable text was found in this material.")
        if words > settings.max_words:
            raise ExtractionError(
                "source_too_long",
                f"This material has about {words:,} words. The limit is {settings.max_words:,} words per guide; "
                "split it into parts and upload each one.",
            )
    except ExtractionError as exc:
        _fail(db, job, exc.code, exc.message)
        return

    db.execute(delete(SourceSegment).where(SourceSegment.source_id == source.id))
    for s in segments:
        db.add(
            SourceSegment(
                source_id=source.id,
                ordinal=s.ordinal,
                ref=s.ref,
                locator=s.locator,
                heading_path=s.heading_path,
                text=s.text,
                token_count=s.token_count,
            )
        )
    source.page_count = result.page_count
    source.word_count = words
    source.warnings = result.warnings
    source.status = "ready"
    source.error = None
    _finish(db, job)


# ---------- generate ----------


def guide_segments(db: Session, guide_id: uuid.UUID) -> tuple[list[dict], list[Source]]:
    """Segments of every source in the guide. With several sources, refs get a d2-, d3- prefix."""
    rows = db.execute(
        select(Source, GuideSource.position)
        .join(GuideSource, GuideSource.source_id == Source.id)
        .where(GuideSource.guide_id == guide_id)
        .order_by(GuideSource.position)
    ).all()
    sources = [r[0] for r in rows]
    segments: list[dict] = []
    for position, source in enumerate(sources):
        for seg in db.scalars(
            select(SourceSegment).where(SourceSegment.source_id == source.id).order_by(SourceSegment.ordinal)
        ):
            segments.append(
                {
                    "ref": guide_ref(position, seg.ref),
                    "text": seg.text,
                    "heading_path": seg.heading_path,
                    "source_id": str(source.id),
                }
            )
    return segments, sources


def guide_ref(position: int, ref: str) -> str:
    return ref if position == 0 else f"d{position + 1}-{ref}"


def split_guide_ref(ref: str) -> tuple[int, str]:
    if ref.startswith("d") and "-" in ref:
        head, rest = ref.split("-", 1)
        if head[1:].isdigit():
            return int(head[1:]) - 1, rest
    return 0, ref


def _context(
    db: Session,
    job: GenerationJob,
    guide: StudyGuide,
    segments: list[dict],
    llm: LLM,
    settings: Settings,
    event_job: GenerationJob | None = None,
    reviewer: LLM | None = None,
):
    """`job` holds the pipeline state; events name `event_job` (the job actually running) if given."""
    meter = TokenMeter.from_dict(settings.guide_token_budget, guide.token_usage)
    state = copy.deepcopy(job.state or {})

    def save(stage: str) -> None:
        job.state = copy.deepcopy(state)
        flag_modified(job, "state")  # nested JSONB changes are not tracked automatically
        job.stage = stage
        job.progress = {"done": list(state.get("done", [])), "sections": len(state.get("sections", {}))}
        guide.content = orchestrator.build_content(state, guide.level)
        if state.get("sequence"):
            guide.title = state["sequence"]["title"][:300]
        guide.token_usage = meter.as_dict()
        guide.quality_score = orchestrator.quality_score(state)
        guide.models = {
            "writer": llm.model,
            "reviewer": (reviewer or llm).model,
            "prompt_version": _prompt_version(),
        }
        heartbeat(db, job, settings)
        db.commit()

    def emit(type_: str, data: dict) -> None:
        add_event(db, guide.id, type_, {**data, "job_id": str((event_job or job).id)})
        db.commit()

    return PipelineContext(
        segments=segments,
        level=guide.level,
        llm=llm,
        meter=meter,
        settings=settings,
        state=state,
        save=save,
        emit=emit,
        reviewer=reviewer,
    )


def _prompt_version() -> str:
    from app.llm.prompts.common import PROMPT_VERSION

    return PROMPT_VERSION


def write_quality_reports(db: Session, guide_id: uuid.UUID, reports: list[dict]) -> None:
    """One quality_reports row per reviewed section: the checks, every review attempt, the outcome."""
    for report in reports:
        db.add(
            QualityReport(
                guide_id=guide_id,
                section_id=report["section_id"],
                score=report.get("score"),
                action=report["action"],
                checks={k: v for k, v in report.items() if k not in ("section_id", "score", "action")},
            )
        )


def run_generate(
    db: Session, job: GenerationJob, llm: LLM, settings: Settings, reviewer: LLM | None = None
) -> None:
    guide = db.get(StudyGuide, job.guide_id)
    if guide is None:
        _finish(db, job)
        return
    segments, sources = guide_segments(db, guide.id)
    statuses = {s.status for s in sources}
    if not sources:
        raise PipelineError("no_sources", "This guide has no source material.")
    if "failed" in statuses:
        raise PipelineError("source_failed", "The source material could not be read, so no guide was made.")
    if "extracting" in statuses:
        # Wait for extraction without holding the lock; this does not count as an attempt.
        job.status = "queued"
        job.attempts -= 1
        job.locked_by = None
        job.run_after = now() + timedelta(seconds=2)
        db.commit()
        return

    guide.status = "running"
    db.commit()
    ctx = _context(db, job, guide, segments, llm, settings, reviewer=reviewer)
    content = orchestrator.run(ctx)
    guide.content = content
    guide.status = "ready"
    guide.quality_score = orchestrator.quality_score(ctx.state)
    write_quality_reports(db, guide.id, list(ctx.state.get("reviews", {}).values()))
    guide.token_usage = ctx.meter.as_dict()
    add_event(
        db,
        guide.id,
        "completed",
        {
            "job_id": str(job.id),
            "concepts": len(content["concepts"]),
            "quality_score": guide.quality_score,
            "token_usage": ctx.meter.usage.as_dict(),
        },
    )
    _finish(db, job)


def run_regenerate(
    db: Session, job: GenerationJob, llm: LLM, settings: Settings, reviewer: LLM | None = None
) -> None:
    guide = db.get(StudyGuide, job.guide_id)
    source_job = db.scalars(
        select(GenerationJob)
        .where(
            GenerationJob.guide_id == job.guide_id,
            GenerationJob.kind == "generate",
            GenerationJob.status == "done",
        )
        .order_by(GenerationJob.created_at.desc())
    ).first()
    if guide is None or source_job is None:
        raise PipelineError("guide_not_ready", "This guide is not finished yet.")
    segments, _ = guide_segments(db, guide.id)
    ctx = _context(db, source_job, guide, segments, llm, settings, event_job=job, reviewer=reviewer)
    section_id = job.params["section_id"]
    content = orchestrator.regenerate_section(ctx, section_id, job.params.get("instruction"))
    guide.content = content
    guide.quality_score = orchestrator.quality_score(ctx.state)
    report = ctx.state.get("reviews", {}).get(section_id)
    if report and settings.review_enabled:
        write_quality_reports(db, guide.id, [{**report, "trigger": "student_rewrite"}])
    guide.token_usage = ctx.meter.as_dict()
    _finish(db, job)


def running_guides(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(StudyGuide)
        .where(StudyGuide.user_id == user_id, StudyGuide.status.in_(["queued", "running"]))
    )
