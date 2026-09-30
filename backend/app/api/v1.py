import hashlib
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.security import Principal, current_user, require_staff
from app.features.feedback.models import (AuditEvent, Comment, Feedback, FeedbackGroup, ProcessingRun,
                                          StatusEvent, Upload, UserProfile)
from app.features.feedback.schemas import (ClassificationChange, CommentCreate, FeedbackCreate,
                                           ProfilePatch, StatusChange, UploadCreate)
from app.features.feedback.service import create_feedback, delete_feedback, owned_feedback, public_state
from app.features.languages.registry import LANGUAGES, LANGUAGE_BY_CODE

router = APIRouter()
Db = Annotated[Session, Depends(get_db)]
User = Annotated[Principal, Depends(current_user)]
Staff = Annotated[Principal, Depends(require_staff)]
ALLOWED_STATUS_TRANSITIONS = {
    "received": {"under_review", "needs_more_information", "closed"},
    "under_review": {"forwarded", "needs_more_information", "rejected_with_reason", "closed"},
    "forwarded": {"in_progress", "needs_more_information", "closed"},
    "in_progress": {"resolved", "needs_more_information", "closed"},
    "needs_more_information": {"under_review", "closed"},
    "rejected_with_reason": {"closed"}, "resolved": {"closed"}, "closed": set(),
}


@router.get("/languages")
def languages():
    return LANGUAGES


@router.get("/me")
def get_profile(db: Db, user: User):
    profile = db.get(UserProfile, user.subject)
    return {"subject": user.subject, "role": user.role, "display_name": profile.display_name if profile else None,
            "preferred_language": profile.preferred_language if profile else "en",
            "preferred_script": profile.preferred_script if profile else None}


@router.patch("/me")
def patch_profile(payload: ProfilePatch, db: Db, user: User):
    values = payload.model_dump(exclude_unset=True)
    if values.get("preferred_language") and values["preferred_language"] not in LANGUAGE_BY_CODE:
        raise HTTPException(400, "Unsupported language code")
    profile = db.get(UserProfile, user.subject)
    if profile is None:
        profile = UserProfile(subject_id=user.subject)
        db.add(profile)
    for key, value in values.items():
        setattr(profile, key, value)
    db.commit()
    return get_profile(db, user)


@router.delete("/me", status_code=202)
def delete_account(db: Db, user: User):
    profile = db.get(UserProfile, user.subject)
    for item in db.scalars(select(Feedback).where(Feedback.owner_id == user.subject, Feedback.deleted_at.is_(None))):
        delete_feedback(db, item)
    if profile:
        db.delete(profile)
    db.add(AuditEvent(actor_id=user.subject, operation="account.deletion_requested",
                      target_id=str(uuid.uuid4()), metadata_json={"provider_session_revocation": "not_configured"}))
    db.commit()
    return {"status": "deletion_requested"}


@router.post("/uploads", status_code=201)
def create_upload(payload: UploadCreate, db: Db, user: User):
    settings = get_settings()
    upload_id = str(uuid.uuid4())
    upload = Upload(id=upload_id, owner_id=user.subject, object_key=f"{upload_id}.bin",
                    mime_type=payload.mime_type, expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.upload_expiry_minutes))
    db.add(upload)
    db.commit()
    # Local development uses an authenticated API upload. Production should replace this with a
    # private object-storage signed URL adapter before enabling external uploads.
    return {"upload_id": upload.id, "upload_url": f"/api/v1/uploads/{upload.id}/content",
            "expires_at": upload.expires_at, "max_bytes": settings.max_audio_bytes,
            "accepted_types": [payload.mime_type]}


@router.put("/uploads/{upload_id}/content", status_code=204)
async def put_upload(upload_id: str, db: Db, user: User, file: UploadFile = File(...)):
    settings = get_settings()
    upload = db.scalar(select(Upload).where(Upload.id == upload_id, Upload.owner_id == user.subject, Upload.state == "pending"))
    if upload is None:
        raise HTTPException(404, "Upload not found")
    if file.content_type != upload.mime_type:
        raise HTTPException(415, "Unexpected media type")
    content = await file.read(settings.max_audio_bytes + 1)
    if not content or len(content) > settings.max_audio_bytes:
        raise HTTPException(413, "Audio is empty or exceeds configured limit")
    if upload.expires_at.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
        raise HTTPException(409, "Upload slot expired")
    root = Path(settings.audio_storage_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    target = (root / upload.object_key).resolve()
    if root not in target.parents:
        raise HTTPException(400, "Invalid storage key")
    target.write_bytes(content)
    upload.size_bytes = len(content)
    upload.checksum = hashlib.sha256(content).hexdigest()
    upload.state = "complete"
    db.commit()


@router.post("/feedback", status_code=202)
def submit_feedback(payload: FeedbackCreate, db: Db, user: User):
    item = create_feedback(db, user, payload)
    return {"id": item.id, "status": item.government_status, "processing_state": "queued",
            "created_at": item.created_at, "receipt": item.id}


@router.get("/me/feedback")
def my_feedback(db: Db, user: User, limit: int = Query(20, ge=1, le=100), cursor: str | None = None):
    query = select(Feedback).where(Feedback.owner_id == user.subject, Feedback.deleted_at.is_(None)).order_by(Feedback.created_at.desc())
    if cursor:
        query = query.where(Feedback.id < cursor)
    items = list(db.scalars(query.limit(limit + 1)))
    has_more = len(items) > limit
    items = items[:limit]
    return {"items": [{"id": item.id, "kind": item.kind, "language": item.declared_language,
                       "status": item.government_status, "created_at": item.created_at} for item in items],
            "next_cursor": items[-1].id if has_more and items else None}


@router.get("/feedback/{feedback_id}")
def feedback_detail(feedback_id: str, db: Db, user: User):
    item = owned_feedback(db, feedback_id, user)
    run = db.scalar(select(ProcessingRun).where(ProcessingRun.feedback_id == item.id).order_by(ProcessingRun.created_at.desc()))
    return {"id": item.id, "kind": item.kind, "text": item.original_text, "language": item.declared_language,
            "script": item.script, "location": item.location, "status": item.government_status,
            "processing_state": run.state if run else "queued", "transcript": run.transcript if run else None,
            "proposal": run.proposal if run else None,
            "created_at": item.created_at}


@router.delete("/feedback/{feedback_id}", status_code=204)
def remove_feedback(feedback_id: str, db: Db, user: User):
    delete_feedback(db, owned_feedback(db, feedback_id, user))


@router.get("/feedback/{feedback_id}/status")
def feedback_status(feedback_id: str, db: Db, user: User):
    return public_state(db, owned_feedback(db, feedback_id, user))


@router.get("/feedback/{feedback_id}/status-events")
def status_events(feedback_id: str, db: Db, user: User):
    item = owned_feedback(db, feedback_id, user)
    events = db.scalars(select(StatusEvent).where(StatusEvent.feedback_id == item.id).order_by(StatusEvent.created_at))
    return [{"status": e.status, "public_message": e.public_message, "created_at": e.created_at} for e in events]


@router.get("/feedback/{feedback_id}/comments")
def list_comments(feedback_id: str, db: Db, user: User):
    item = owned_feedback(db, feedback_id, user)
    rows = db.scalars(select(Comment).where(Comment.feedback_id == item.id, Comment.deleted_at.is_(None)).order_by(Comment.created_at))
    return [{"id": c.id, "author_id": c.author_id, "text": c.text, "language": c.language, "created_at": c.created_at} for c in rows]


@router.post("/feedback/{feedback_id}/comments", status_code=201)
def create_comment(feedback_id: str, payload: CommentCreate, db: Db, user: User):
    item = owned_feedback(db, feedback_id, user)
    if payload.language not in LANGUAGE_BY_CODE:
        raise HTTPException(400, "Unsupported language code")
    comment = Comment(feedback_id=item.id, author_id=user.subject, text=payload.text, language=payload.language)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return {"id": comment.id, "text": comment.text, "language": comment.language, "created_at": comment.created_at}


@router.delete("/feedback/{feedback_id}/comments/{comment_id}", status_code=204)
def delete_comment(feedback_id: str, comment_id: str, db: Db, user: User):
    item = owned_feedback(db, feedback_id, user)
    comment = db.scalar(select(Comment).where(Comment.id == comment_id, Comment.feedback_id == item.id, Comment.deleted_at.is_(None)))
    if comment is None or (comment.author_id != user.subject and user.role not in {"analyst", "admin"}):
        raise HTTPException(404, "Comment not found")
    comment.deleted_at = datetime.now(timezone.utc)
    db.commit()


@router.get("/staff/feedback")
def staff_feedback(db: Db, user: Staff, status: str | None = None, category: str | None = None,
                   language: str | None = None, district: str | None = None, limit: int = Query(50, ge=1, le=200)):
    query = select(Feedback).where(Feedback.deleted_at.is_(None)).order_by(Feedback.created_at.desc())
    if status:
        query = query.where(Feedback.government_status == status)
    if language:
        query = query.where(Feedback.declared_language == language)
    items = list(db.scalars(query.limit(limit)))
    result = []
    for item in items:
        if district and (not item.location or item.location.get("district", "").casefold() != district.casefold()):
            continue
        run = db.scalar(select(ProcessingRun).where(ProcessingRun.feedback_id == item.id).order_by(ProcessingRun.created_at.desc()))
        if category and (not run or not run.proposal or run.proposal.get("category") != category):
            continue
        result.append({"id": item.id, "kind": item.kind, "text": item.original_text,
                       "language": item.declared_language, "location": item.location,
                       "status": item.government_status, "processing_state": run.state if run else "queued",
                       "transcript": run.transcript if run else None,
                       "proposal": run.proposal if run else None, "created_at": item.created_at})
    return result


@router.patch("/staff/feedback/{feedback_id}/status")
def staff_status(feedback_id: str, payload: StatusChange, db: Db, user: Staff):
    item = owned_feedback(db, feedback_id, user)
    if payload.status not in ALLOWED_STATUS_TRANSITIONS.get(item.government_status, set()):
        raise HTTPException(409, "Invalid status transition")
    previous_status = item.government_status
    item.government_status = payload.status
    db.add(StatusEvent(feedback_id=item.id, status=payload.status, public_message=payload.public_message, actor_id=user.subject))
    db.add(AuditEvent(actor_id=user.subject, operation="feedback.status_changed", target_id=item.id,
                      metadata_json={"from": previous_status, "to": payload.status}))
    db.commit()
    return {"id": item.id, "status": item.government_status}


@router.patch("/staff/feedback/{feedback_id}/classification")
def staff_classification(feedback_id: str, payload: ClassificationChange, db: Db, user: Staff):
    item = owned_feedback(db, feedback_id, user)
    run = db.scalar(select(ProcessingRun).where(ProcessingRun.feedback_id == item.id).order_by(ProcessingRun.created_at.desc()))
    if run is None or not run.proposal:
        raise HTTPException(409, "No classification proposal is available")
    changes = payload.model_dump(exclude_unset=True)
    old = {key: run.proposal.get(key) for key in changes}
    run.proposal = {**run.proposal, **changes}
    run.needs_human_review = False
    db.add(AuditEvent(actor_id=user.subject, operation="feedback.classification_corrected", target_id=item.id,
                      metadata_json={"before": old, "after": changes}))
    db.commit()
    return {"id": item.id, "proposal": run.proposal, "needs_human_review": False}


@router.post("/staff/feedback/{feedback_id}/groups/{group_id}", status_code=201)
def confirm_group(feedback_id: str, group_id: str, db: Db, user: Staff):
    item = owned_feedback(db, feedback_id, user)
    db.add(FeedbackGroup(feedback_id=item.id, group_id=group_id, confirmed_by=user.subject))
    db.add(AuditEvent(actor_id=user.subject, operation="feedback.group_confirmed", target_id=item.id,
                      metadata_json={"group_id": group_id}))
    db.commit()
    return {"feedback_id": item.id, "group_id": group_id, "confirmed": True}


@router.get("/analytics/summary")
def analytics_summary(db: Db, user: Staff, language: str | None = None):
    query = select(Feedback).where(Feedback.deleted_at.is_(None))
    if language:
        query = query.where(Feedback.declared_language == language)
    items = list(db.scalars(query))
    counts: dict[str, int] = {}
    for item in items:
        counts[item.government_status] = counts.get(item.government_status, 0) + 1
    return {"source": "AI for Digital Infrastructure & Governance submissions", "window": "all_time", "total_reports": len(items),
            "denominator": None, "status_counts": counts, "caveats": ["Submission counts are not population-adjusted needs estimates."]}


@router.get("/analytics/priorities")
def analytics_priorities(db: Db, user: Staff):
    rows: dict[str, int] = {}
    for item in db.scalars(select(Feedback).where(Feedback.deleted_at.is_(None))):
        district = (item.location or {}).get("district")
        if district:
            rows[district] = rows.get(district, 0) + 1
    return {"method": "raw_report_count_v1", "advisory_only": True, "weights": {"reports": 1.0},
            "denominator": None, "caveats": ["Counts are not population-adjusted and must not determine funding."],
            "areas": [{"area": area, "unique_reports": count, "score": count} for area, count in sorted(rows.items(), key=lambda kv: kv[1], reverse=True)]}


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Db):
    db.execute(select(func.count()).select_from(Feedback))
    return {"status": "ready", "nlp_mode": get_settings().nlp_mode}
