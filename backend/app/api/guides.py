import base64
import json
import time
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user, own_guide, own_source
from app.core.config import get_settings
from app.core.errors import AppError, not_found
from app.db.models import GenerationJob, GuideEvent, GuideSource, Source, SourceSegment, StudyGuide, User
from app.db.session import get_db, get_sessionmaker
from app.export import FORMATS, ExportInfo, filename, render
from app.pipeline import jobs
from app.schemas.api import (
    CreateGuideIn,
    CreateGuideOut,
    GuideListOut,
    GuideOut,
    GuideRefOut,
    JobOut,
    RegenerateIn,
)

router = APIRouter(tags=["guides"])

TERMINAL_EVENTS = {"completed", "failed"}


@router.post("/guides", status_code=202, response_model=CreateGuideOut)
def create_guide(
    body: CreateGuideIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    settings = get_settings()
    sources = [own_source(db, user, sid) for sid in dict.fromkeys(body.source_ids)]
    failed = [s for s in sources if s.status == "failed"]
    if failed:
        raise AppError(
            400, "source_failed", f"'{failed[0].title}' could not be read, so it cannot be used for a guide."
        )
    total_words = sum(s.word_count or 0 for s in sources)
    if total_words > settings.max_words:
        raise AppError(
            413,
            "source_too_long",
            f"Together these sources have about {total_words:,} words; the limit is {settings.max_words:,} per guide.",
        )
    if jobs.running_guides(db, user.id) > 0:
        raise AppError(
            429, "guide_in_progress", "A guide is already being made. Wait for it to finish first."
        )
    recent = db.scalar(
        select(func.count())
        .select_from(StudyGuide)
        .where(StudyGuide.user_id == user.id, StudyGuide.created_at > datetime.now(UTC) - timedelta(hours=1))
    )
    if recent >= settings.guides_per_hour:
        raise AppError(
            429,
            "too_many_guides",
            f"You can make {settings.guides_per_hour} guides an hour. Try again a bit later.",
        )

    guide = StudyGuide(
        user_id=user.id,
        title=sources[0].title,
        level=body.level or user.default_level,
        status="queued",
        token_usage={},
        models={},
    )
    db.add(guide)
    db.flush()
    for position, source in enumerate(sources):
        db.add(GuideSource(guide_id=guide.id, source_id=source.id, position=position))
    job = jobs.enqueue(db, "generate", guide_id=guide.id)
    jobs.add_event(db, guide.id, "stage", {"stage": "queued", "job_id": str(job.id)})
    db.commit()
    return {"guide_id": guide.id, "job_id": job.id}


@router.get("/guides", response_model=GuideListOut)
def list_guides(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    query = select(StudyGuide).where(StudyGuide.user_id == user.id)
    if cursor:
        try:
            created, gid = json.loads(base64.urlsafe_b64decode(cursor.encode()))
            created_at = datetime.fromisoformat(created)
        except (ValueError, TypeError) as exc:
            raise AppError(400, "invalid_cursor", "That page link is invalid.") from exc
        query = query.where(
            (StudyGuide.created_at < created_at)
            | ((StudyGuide.created_at == created_at) & (StudyGuide.id < uuid.UUID(gid)))
        )
    rows = list(
        db.scalars(query.order_by(StudyGuide.created_at.desc(), StudyGuide.id.desc()).limit(limit + 1))
    )
    next_cursor = None
    if len(rows) > limit:
        last = rows[limit - 1]
        next_cursor = base64.urlsafe_b64encode(
            json.dumps([last.created_at.isoformat(), str(last.id)]).encode()
        ).decode()
    return {"items": rows[:limit], "next_cursor": next_cursor}


@router.get("/guides/{guide_id}", response_model=GuideOut)
def get_guide(guide_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict:
    guide = own_guide(db, user, guide_id)
    job = db.scalars(
        select(GenerationJob)
        .where(GenerationJob.guide_id == guide.id, GenerationJob.kind == "generate")
        .order_by(GenerationJob.created_at.desc())
    ).first()
    source_ids = list(
        db.scalars(
            select(GuideSource.source_id)
            .where(GuideSource.guide_id == guide.id)
            .order_by(GuideSource.position)
        )
    )
    return {
        "id": guide.id,
        "title": guide.title,
        "level": guide.level,
        "status": guide.status,
        "quality_score": guide.quality_score,
        "created_at": guide.created_at,
        "updated_at": guide.updated_at,
        "source_ids": source_ids,
        "content": guide.content,
        "progress": {"stage": job.stage, **job.progress} if job else None,
        "error": job.error if job and job.status == "failed" else None,
        "token_usage": guide.token_usage,
    }


@router.get("/guides/{guide_id}/refs/{ref}", response_model=GuideRefOut)
def resolve_ref(
    guide_id: uuid.UUID, ref: str, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    """Resolve a citation in the guide (e.g. p4-s1) to its segment text and location."""
    guide = own_guide(db, user, guide_id)
    position, source_ref = jobs.split_guide_ref(ref)
    row = db.execute(
        select(SourceSegment)
        .join(GuideSource, GuideSource.source_id == SourceSegment.source_id)
        .where(
            GuideSource.guide_id == guide.id,
            GuideSource.position == position,
            SourceSegment.ref == source_ref,
        )
    ).scalar_one_or_none()
    if row is None:
        raise not_found("reference")
    return {
        "ref": ref,
        "ordinal": row.ordinal,
        "locator": row.locator,
        "heading_path": row.heading_path,
        "text": row.text,
        "source_id": row.source_id,
    }


@router.get("/guides/{guide_id}/events")
def guide_events(
    guide_id: uuid.UUID,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    last_event_id: str | None = Header(default=None),
    after: int | None = Query(
        default=None, description="Replay events after this id (alternative to Last-Event-ID)"
    ),
) -> StreamingResponse:
    """Server-sent events: stage, topics_detected, section_ready, quality_flag, completed, failed."""
    own_guide(db, user, guide_id)
    db.close()  # the stream opens its own short sessions; do not hold a connection for its lifetime
    start = after if after is not None else int(last_event_id) if (last_event_id or "").isdigit() else 0
    return StreamingResponse(
        _event_stream(guide_id, start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _event_stream(
    guide_id: uuid.UUID, last_id: int, poll: float = 1.0, max_seconds: float = 900
) -> Iterator[str]:
    Session_ = get_sessionmaker()
    deadline = time.monotonic() + max_seconds
    idle = 0.0
    yield "retry: 3000\n\n"
    while time.monotonic() < deadline:
        with Session_() as db:
            events = list(
                db.scalars(
                    select(GuideEvent)
                    .where(GuideEvent.guide_id == guide_id, GuideEvent.id > last_id)
                    .order_by(GuideEvent.id)
                    .limit(200)
                )
            )
            status = db.scalar(select(StudyGuide.status).where(StudyGuide.id == guide_id))
        for event in events:
            last_id = event.id
            yield f"id: {event.id}\nevent: {event.type}\ndata: {json.dumps(event.data)}\n\n"
            if event.type in TERMINAL_EVENTS and status in ("ready", "failed"):
                return
        if status is None:
            return
        if not events:
            idle += poll
            if idle >= 15:
                yield ": keep-alive\n\n"
                idle = 0.0
            time.sleep(poll)


@router.post("/guides/{guide_id}/sections/{section_id}/regenerate", status_code=202, response_model=JobOut)
def regenerate_section(
    guide_id: uuid.UUID,
    section_id: str,
    body: RegenerateIn | None = None,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict:
    guide = own_guide(db, user, guide_id)
    if guide.status != "ready":
        raise AppError(409, "guide_not_ready", "Wait for the guide to finish before rewriting a section.")
    if not any(c["id"] == section_id for c in (guide.content or {}).get("concepts", [])):
        raise not_found("section")
    busy = db.scalar(
        select(func.count())
        .select_from(GenerationJob)
        .where(
            GenerationJob.guide_id == guide.id,
            GenerationJob.kind == "regenerate_section",
            GenerationJob.status.in_(["queued", "running"]),
        )
    )
    if busy:
        raise AppError(429, "regenerate_in_progress", "A section of this guide is already being rewritten.")
    job = jobs.enqueue(
        db,
        "regenerate_section",
        guide_id=guide.id,
        params={"section_id": section_id, "instruction": body.instruction if body else None},
    )
    db.commit()
    return {"job_id": job.id}


@router.get(
    "/guides/{guide_id}/export",
    response_class=Response,
    responses={200: {"content": {media: {} for media, _ in FORMATS.values()}, "description": "The file"}},
)
def export_guide(
    guide_id: uuid.UUID,
    format: Literal["pdf", "docx", "md", "html"] = Query(default="pdf"),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Download the finished guide as PDF, Word, Markdown or a standalone HTML page."""
    guide = own_guide(db, user, guide_id)
    if guide.status != "ready" or not guide.content:
        raise AppError(409, "guide_not_ready", "Wait for the guide to finish before exporting it.")
    titles = list(
        db.scalars(
            select(Source.title)
            .join(GuideSource, GuideSource.source_id == Source.id)
            .where(GuideSource.guide_id == guide.id)
            .order_by(GuideSource.position)
        )
    )
    info = ExportInfo(
        title=guide.content.get("title") or guide.title,
        level=guide.level,
        source_titles=titles,
    )
    media_type, ext = FORMATS[format]
    data = render(guide.content, format, info)
    name = filename(info.title, ext)
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{name}"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/guides/{guide_id}", status_code=204)
def delete_guide(
    guide_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    guide = own_guide(db, user, guide_id)
    db.delete(guide)
    db.commit()
    return Response(status_code=204)
