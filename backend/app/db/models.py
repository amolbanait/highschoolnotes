import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB, uuid.UUID: UUID(as_uuid=True)}


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _id()
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    default_level: Mapped[str] = mapped_column(String(32), nullable=False, default="high_school")
    birth_year_confirmed_13plus: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = _created()


class UserSession(Base):
    """Server-side sessions so logout and account deletion revoke cookies immediately."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = _created()


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # pdf, docx, txt, markdown, paste
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    filename: Mapped[str | None] = mapped_column(String(300))
    mime: Mapped[str | None] = mapped_column(String(120))
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="extracting"
    )  # extracting, ready, failed
    page_count: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()

    segments: Mapped[list["SourceSegment"]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="SourceSegment.ordinal",
    )


class SourceSegment(Base):
    """The unit of traceability: every citation in a guide points at a segment ref."""

    __tablename__ = "source_segments"
    __table_args__ = (
        UniqueConstraint("source_id", "ref"),
        Index("ix_segments_source_ordinal", "source_id", "ordinal"),
    )

    id: Mapped[uuid.UUID] = _id()
    source_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    ref: Mapped[str] = mapped_column(String(32), nullable=False)  # p12-s3 (paged) or s7 (flowing text)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    heading_path: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)

    source: Mapped[Source] = relationship(back_populates="segments")


class StudyGuide(Base):
    __tablename__ = "study_guides"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued"
    )  # queued, running, ready, failed
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    models: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class GuideSource(Base):
    __tablename__ = "guide_sources"

    guide_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("study_guides.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class GenerationJob(Base):
    """The job queue. Workers claim rows with FOR UPDATE SKIP LOCKED.

    kind: extract (one source), generate (one guide), regenerate_section (one concept of a guide).
    state holds each finished stage's output so a crashed job resumes where it stopped.
    """

    __tablename__ = "generation_jobs"
    __table_args__ = (Index("ix_jobs_claim", "status", "run_after"),)

    id: Mapped[uuid.UUID] = _id()
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    guide_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("study_guides.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    stage: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="queued"
    )  # queued, running, done, failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_after: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = _created()
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GuideEvent(Base):
    """Progress events, replayed to the browser over SSE (the row id is the SSE event id)."""

    __tablename__ = "guide_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    guide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_guides.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _created()


class QualityReport(Base):
    __tablename__ = "quality_reports"

    id: Mapped[uuid.UUID] = _id()
    guide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_guides.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[str] = mapped_column(String(32), nullable=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    score: Mapped[int | None] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(16), nullable=False)  # passed, regenerated, flagged
    created_at: Mapped[datetime] = _created()


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    guide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_guides.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[str] = mapped_column(String(32), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _created()


class FlashcardReview(Base):
    __tablename__ = "flashcard_reviews"

    id: Mapped[uuid.UUID] = _id()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    guide_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("study_guides.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rating: Mapped[str] = mapped_column(String(8), nullable=False)  # again, good, easy
    reviewed_at: Mapped[datetime] = _created()
