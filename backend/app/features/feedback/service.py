from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal
from app.features.feedback.models import (AuditEvent, Comment, Feedback, FeedbackAsset,
                                          ProcessingJob, ProcessingRun, StatusEvent, Upload,
                                          UserProfile)
from app.features.feedback.schemas import FeedbackCreate
from app.features.languages.registry import LANGUAGE_BY_CODE


def owned_feedback(db: Session, feedback_id: str, user: Principal) -> Feedback:
    item = db.scalar(select(Feedback).where(Feedback.id == feedback_id, Feedback.deleted_at.is_(None)))
    if item is None or (item.owner_id != user.subject and user.role not in {"analyst", "official", "admin"}):
        raise HTTPException(404, "Feedback not found")
    return item


def create_feedback(db: Session, user: Principal, payload: FeedbackCreate) -> Feedback:
    settings = get_settings()
    if not payload.consent:
        raise HTTPException(400, "Consent is required")
    language = LANGUAGE_BY_CODE.get(payload.language)
    if language is None:
        raise HTTPException(400, "Unsupported language code")
    if payload.kind == "text" and (not payload.text or len(payload.text) > settings.max_text_chars):
        raise HTTPException(413 if payload.text else 422, "Text is missing or exceeds configured limit")
    if payload.kind == "audio" and (not payload.upload_id or payload.text is not None):
        raise HTTPException(422, "Audio feedback requires a completed upload")
    item = Feedback(owner_id=user.subject, kind=payload.kind, original_text=payload.text,
                    declared_language=payload.language, script=language["script"],
                    location=payload.location.model_dump(exclude_none=True) if payload.location else None)
    db.add(item)
    db.flush()
    if payload.kind == "audio":
        upload = db.scalar(select(Upload).where(Upload.id == payload.upload_id,
                                               Upload.owner_id == user.subject, Upload.state == "complete"))
        expiry = upload.expires_at.replace(tzinfo=timezone.utc) if upload and upload.expires_at.tzinfo is None else (upload.expires_at if upload else None)
        if upload is None or expiry <= datetime.now(timezone.utc):
            db.rollback()
            raise HTTPException(409, "Audio upload is not ready")
        db.add(FeedbackAsset(feedback_id=item.id, object_key=upload.object_key,
                             mime_type=upload.mime_type, size_bytes=upload.size_bytes,
                             checksum=upload.checksum or ""))
        upload.state = "attached"
    db.add(StatusEvent(feedback_id=item.id, status="received", public_message="Your feedback was received.", actor_id="system"))
    db.add(ProcessingJob(feedback_id=item.id))
    db.add(ProcessingRun(feedback_id=item.id))
    db.commit()
    db.refresh(item)
    return item


def delete_feedback(db: Session, item: Feedback) -> None:
    item.deleted_at = datetime.now(timezone.utc)
    # Hide and redact source content immediately; the scheduled purge handles private media.
    item.original_text = None
    for comment in db.scalars(select(Comment).where(Comment.feedback_id == item.id, Comment.deleted_at.is_(None))):
        comment.text = ""
        comment.deleted_at = item.deleted_at
    for run in db.scalars(select(ProcessingRun).where(ProcessingRun.feedback_id == item.id)):
        run.transcript = None
        run.proposal = None
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.feedback_id == item.id))
    if job and job.state in {"queued", "retry"}:
        job.state = "cancelled"
    db.add(AuditEvent(actor_id=item.owner_id, operation="feedback.deleted", target_id=item.id, metadata_json={"mode": "soft_delete"}))
    db.commit()


def public_state(db: Session, item: Feedback) -> dict:
    run = db.scalar(select(ProcessingRun).where(ProcessingRun.feedback_id == item.id).order_by(ProcessingRun.created_at.desc()))
    return {"feedback_id": item.id, "status": item.government_status,
            "processing_state": run.state if run else "queued", "updated_at": item.created_at}

