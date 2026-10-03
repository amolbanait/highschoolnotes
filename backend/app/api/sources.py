import hashlib
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response as RawResponse
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.api.deps import current_user, own_source
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.models import GuideSource, Source, SourceSegment, StudyGuide, User
from app.db.session import get_db
from app.ingestion.base import ExtractionError
from app.ingestion.registry import MIME_TYPES, detect_kind
from app.pipeline import jobs
from app.schemas.api import PasteIn, SegmentOut, SourceOut
from app.storage.files import get_storage

router = APIRouter(tags=["sources"])

_EXTENSIONS = {"pdf": ".pdf", "docx": ".docx", "txt": ".txt", "markdown": ".md", "paste": ".txt"}


@router.post("/sources", status_code=201, response_model=SourceOut)
async def create_source(
    request: Request, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Source:
    """Upload a file (multipart field `file`, optional `title`) or paste text (JSON {kind, title, text})."""
    settings = get_settings()
    content_type = request.headers.get("content-type", "")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > settings.max_upload_bytes + 64 * 1024:
        raise AppError(
            413, "source_too_large", f"Files can be up to {settings.max_upload_bytes // (1024 * 1024)} MB."
        )
    if content_type.startswith("multipart/form-data"):
        form = await request.form(max_files=1, max_fields=5)
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise AppError(400, "file_missing", "Choose a file to upload.")
        data = await upload.read(settings.max_upload_bytes + 1)
        filename = (upload.filename or "upload").rsplit("/", 1)[-1][:300]
        title = str(form.get("title") or filename.rsplit(".", 1)[0])[:300]
    elif content_type.startswith("application/json"):
        try:
            body = PasteIn.model_validate_json(await request.body())
        except ValidationError as exc:
            problems = [{"loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
            raise AppError(
                422, "invalid_request", "Give the pasted text a title and some text.", {"problems": problems}
            ) from exc
        data = body.text.encode("utf-8")
        filename = None
        title = body.title
    else:
        raise AppError(
            415, "unsupported_media_type", "Send a file as multipart/form-data or pasted text as JSON."
        )

    return await run_in_threadpool(_store_source, db, user, data, filename, title)


def _store_source(db: Session, user: User, data: bytes, filename: str | None, title: str) -> Source:
    settings = get_settings()
    if len(data) > settings.max_upload_bytes:
        raise AppError(
            413, "source_too_large", f"Files can be up to {settings.max_upload_bytes // (1024 * 1024)} MB."
        )
    if not data.strip():
        raise AppError(400, "empty_source", "This material is empty.")
    try:
        kind = detect_kind(filename, data) if filename else "paste"
    except ExtractionError as exc:
        raise AppError(415, exc.code, exc.message, exc.details) from exc

    sha = hashlib.sha256(data).hexdigest()
    source = Source(
        user_id=user.id,
        kind=kind,
        title=title.strip() or "Untitled",
        filename=filename,
        mime=MIME_TYPES[kind],
        byte_size=len(data),
        sha256=sha,
        status="extracting",
    )
    db.add(source)
    db.flush()
    source.storage_key = f"{user.id}/{source.id}{_EXTENSIONS[kind]}"
    get_storage().put(source.storage_key, data)

    previous = db.scalar(
        select(Source)
        .where(Source.user_id == user.id, Source.sha256 == sha, Source.kind == kind, Source.status == "ready")
        .where(Source.id != source.id)
        .order_by(Source.created_at.desc())
    )
    if previous is not None:
        _copy_extraction(db, previous, source)
    else:
        jobs.enqueue(db, "extract", source_id=source.id)
    db.commit()
    return source


def _copy_extraction(db: Session, previous: Source, source: Source) -> None:
    """Same file uploaded again: reuse the earlier extraction instead of re-reading it."""
    for seg in previous.segments:
        db.add(
            SourceSegment(
                source_id=source.id,
                ordinal=seg.ordinal,
                ref=seg.ref,
                locator=seg.locator,
                heading_path=seg.heading_path,
                text=seg.text,
                token_count=seg.token_count,
            )
        )
    source.page_count = previous.page_count
    source.word_count = previous.word_count
    source.warnings = previous.warnings
    source.status = "ready"


@router.get("/sources", response_model=list[SourceOut])
def list_sources(user: User = Depends(current_user), db: Session = Depends(get_db)) -> list[Source]:
    return list(
        db.scalars(select(Source).where(Source.user_id == user.id).order_by(Source.created_at.desc()))
    )


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(
    source_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Source:
    return own_source(db, user, source_id)


@router.get("/sources/{source_id}/segments", response_model=list[SegmentOut])
def get_segments(
    source_id: uuid.UUID,
    page: int | None = Query(default=None, ge=1),
    ref: str | None = Query(default=None, max_length=32),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> list[SourceSegment]:
    """Extracted text with locations, for the "view in source" panel. Filter by page or by ref."""
    own_source(db, user, source_id)
    query = select(SourceSegment).where(SourceSegment.source_id == source_id)
    if page is not None:
        query = query.where(SourceSegment.locator["page"].as_integer() == page)
    if ref is not None:
        query = query.where(SourceSegment.ref == ref)
    return list(db.scalars(query.order_by(SourceSegment.ordinal)))


@router.get("/sources/{source_id}/file")
def get_file(
    source_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> RawResponse:
    source = own_source(db, user, source_id)
    data = get_storage().get(source.storage_key)
    name = source.filename or f"{source.title}.txt"
    safe = "".join(ch if ch.isalnum() or ch in "._- " else "_" for ch in name)
    return RawResponse(
        content=data,
        media_type=source.mime or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{safe}"'},
    )


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(
    source_id: uuid.UUID, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> Response:
    """Deletes the source and every guide built only from it."""
    source = own_source(db, user, source_id)
    guide_ids = list(db.scalars(select(GuideSource.guide_id).where(GuideSource.source_id == source_id)))
    for guide_id in guide_ids:
        others = db.scalar(
            select(func.count())
            .select_from(GuideSource)
            .where(GuideSource.guide_id == guide_id, GuideSource.source_id != source_id)
        )
        if not others:
            db.execute(delete(StudyGuide).where(StudyGuide.id == guide_id))
    if source.storage_key:
        get_storage().delete(source.storage_key)
    db.delete(source)
    db.commit()
    return Response(status_code=204)
