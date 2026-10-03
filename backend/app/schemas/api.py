"""Request and response models for the HTTP API."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.study_guide import Level


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=80)
    confirms_age_13_plus: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=200)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    default_level: str
    created_at: datetime


class UpdateMeIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    default_level: Level | None = None


class PasteIn(BaseModel):
    kind: Literal["paste"] = "paste"
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: str
    title: str
    filename: str | None
    byte_size: int
    status: str
    page_count: int | None
    word_count: int | None
    warnings: list[Any]
    error: dict[str, Any] | None
    created_at: datetime


class SegmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ref: str
    ordinal: int
    locator: dict[str, Any]
    heading_path: list[Any]
    text: str


class GuideRefOut(SegmentOut):
    source_id: uuid.UUID


class CreateGuideIn(BaseModel):
    source_ids: list[uuid.UUID] = Field(min_length=1, max_length=5)
    level: Level | None = None


class CreateGuideOut(BaseModel):
    guide_id: uuid.UUID
    job_id: uuid.UUID


class JobOut(BaseModel):
    job_id: uuid.UUID


class GuideSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    level: str
    status: str
    quality_score: int | None
    created_at: datetime
    updated_at: datetime


class GuideOut(GuideSummaryOut):
    source_ids: list[uuid.UUID]
    content: dict[str, Any] | None
    progress: dict[str, Any] | None
    error: dict[str, Any] | None
    token_usage: dict[str, Any]


class GuideListOut(BaseModel):
    items: list[GuideSummaryOut]
    next_cursor: str | None


class RegenerateIn(BaseModel):
    instruction: str | None = Field(default=None, max_length=300)


class QuizAttemptIn(BaseModel):
    question_id: str = Field(max_length=32)
    answer: str = Field(max_length=4000)


class QuizAttemptOut(BaseModel):
    is_correct: bool | None
    correct_answer: str
    explanation: str
    source_refs: list[str]


class FlashcardReviewIn(BaseModel):
    card_id: str = Field(max_length=32)
    rating: Literal["again", "good", "easy"]
