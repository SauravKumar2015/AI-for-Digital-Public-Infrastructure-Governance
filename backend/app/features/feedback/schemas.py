from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


FeedbackKind = Literal["text", "audio"]
FeedbackType = Literal["complaint", "request", "suggestion", "appreciation", "other", "unknown"]
Category = Literal["water", "roads", "sanitation", "electricity", "health", "education", "transport", "housing", "public_safety", "other", "unknown"]
Level = Literal["low", "medium", "high", "unknown"]
Sentiment = Literal["positive", "neutral", "negative", "mixed", "unknown"]


class Location(BaseModel):
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    locality: str | None = Field(default=None, max_length=160)


class FeedbackCreate(BaseModel):
    kind: FeedbackKind
    text: str | None = Field(default=None, max_length=10000)
    upload_id: str | None = None
    language: str = Field(min_length=2, max_length=16)
    location: Location | None = None
    consent: bool

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Text cannot be blank")
        return value


class Receipt(BaseModel):
    id: str
    status: str
    processing_state: str
    created_at: datetime
    receipt: str


class ClassificationProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_name: str = Field(max_length=120)
    model_version: str = Field(max_length=60)
    taxonomy_version: str = Field(default="1.0", max_length=30)
    detected_language: str | None = Field(default=None, max_length=16)
    feedback_type: FeedbackType
    category: Category
    severity: Level
    urgency: Level
    sentiment: Sentiment = "unknown"
    summary: str = Field(max_length=500)
    evidence: list[str] = Field(default_factory=list, max_length=8)
    confidence: float = Field(ge=0, le=1)
    needs_human_review: bool


class CommentCreate(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    language: str = Field(min_length=2, max_length=16)


class StatusChange(BaseModel):
    status: Literal["under_review", "forwarded", "in_progress", "resolved", "needs_more_information", "rejected_with_reason", "closed"]
    public_message: str = Field(min_length=1, max_length=500)


class ClassificationChange(BaseModel):
    feedback_type: FeedbackType | None = None
    category: Category | None = None
    severity: Level | None = None
    urgency: Level | None = None
    summary: str | None = Field(default=None, max_length=500)


class ProfilePatch(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    preferred_language: str | None = Field(default=None, max_length=16)
    preferred_script: str | None = Field(default=None, max_length=16)


class UploadCreate(BaseModel):
    mime_type: Literal["audio/webm", "audio/wav", "audio/mpeg", "audio/mp4", "audio/ogg"]
