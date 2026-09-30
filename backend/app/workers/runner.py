import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.clients.nlp import get_nlp_client
from app.core.config import get_settings
from app.core.db import SessionLocal
from app.features.feedback.models import (Feedback, FeedbackAsset, ProcessingJob, ProcessingRun,
                                          StatusEvent, Upload, Comment, FeedbackGroup)


def process_one() -> bool:
    with SessionLocal() as db:
        job = db.scalar(select(ProcessingJob).where(ProcessingJob.state.in_(["queued", "retry"]))
                        .order_by(ProcessingJob.created_at).with_for_update(skip_locked=True).limit(1))
        if job is None:
            return False
        job.state = "processing"
        job.locked_at = datetime.now(timezone.utc)
        job.attempts += 1
        run = db.scalar(select(ProcessingRun).where(ProcessingRun.feedback_id == job.feedback_id))
        item = db.get(Feedback, job.feedback_id)
        if item is None or item.deleted_at:
            job.state = "cancelled"
            db.commit()
            return True
        if item.kind == "audio":
            settings = get_settings()
            asset = db.scalar(select(FeedbackAsset).where(FeedbackAsset.feedback_id == item.id))
            audio_path = (Path(settings.audio_storage_dir).resolve() / Path(asset.object_key).name) if asset else None
            if settings.audio_mode != "gemini" or not settings.gemini_api_key or not audio_path or not audio_path.is_file():
                run.state = "needs_review"
                run.needs_human_review = True
                run.error_code = "audio_processing_unavailable"
                run.completed_at = datetime.now(timezone.utc)
                job.state = "complete"
                db.add(StatusEvent(feedback_id=item.id, status=item.government_status,
                                   public_message="Your recording was received and is waiting for staff review.", actor_id="system"))
                db.commit()
                return True
            run.state = "transcribing"
            db.commit()
            try:
                from app.clients.gemini_audio import transcribe_and_classify

                transcript, proposal = transcribe_and_classify(
                    audio_path=audio_path, mime_type=asset.mime_type,
                    language=item.declared_language, api_key=settings.gemini_api_key,
                    model=settings.gemini_audio_model,
                )
            except Exception:
                with SessionLocal() as failed_db:
                    failed_job = failed_db.get(ProcessingJob, job.id)
                    failed_run = failed_db.get(ProcessingRun, run.id)
                    if failed_job.attempts < 3:
                        failed_job.state = "retry"
                        failed_run.state = "queued"
                    else:
                        failed_job.state = "complete"
                        failed_run.state = "needs_review"
                        failed_run.needs_human_review = True
                        failed_run.error_code = "audio_inference_unavailable"
                        failed_run.completed_at = datetime.now(timezone.utc)
                    failed_db.commit()
                return True
            with SessionLocal() as done_db:
                done_job = done_db.get(ProcessingJob, job.id)
                done_run = done_db.get(ProcessingRun, run.id)
                current_item = done_db.get(Feedback, item.id)
                if current_item is None or current_item.deleted_at is not None:
                    done_run.transcript = None
                    done_run.proposal = None
                    done_run.state = "cancelled"
                    done_job.state = "cancelled"
                else:
                    done_run.transcript = transcript
                    done_run.proposal = proposal.model_dump()
                    done_run.detected_language = proposal.detected_language
                    done_run.model_name = proposal.model_name
                    done_run.model_version = proposal.model_version
                    done_run.taxonomy_version = proposal.taxonomy_version
                    done_run.confidence = proposal.confidence
                    done_run.needs_human_review = True
                    done_run.state = "needs_review"
                    done_run.completed_at = datetime.now(timezone.utc)
                    done_job.state = "complete"
                done_db.commit()
            return True
        run.state = "classifying"
        db.commit()
        try:
            proposal = asyncio.run(get_nlp_client().classify(text=item.original_text or "",
                                                              language=item.declared_language,
                                                              feedback_id=item.id))
        except Exception as exc:
            # Errors are represented by a stable code; provider details and input text are not logged.
            with SessionLocal() as failed_db:
                failed_job = failed_db.get(ProcessingJob, job.id)
                failed_run = failed_db.get(ProcessingRun, run.id)
                if failed_job.attempts < 3:
                    failed_job.state = "retry"
                    failed_run.state = "queued"
                else:
                    failed_job.state = "complete"
                    failed_run.state = "needs_review"
                    failed_run.needs_human_review = True
                    failed_run.error_code = "inference_unavailable"
                    failed_run.completed_at = datetime.now(timezone.utc)
                failed_db.commit()
            return True
        with SessionLocal() as done_db:
            done_job = done_db.get(ProcessingJob, job.id)
            done_run = done_db.get(ProcessingRun, run.id)
            current_item = done_db.get(Feedback, item.id)
            if current_item is None or current_item.deleted_at is not None:
                done_run.proposal = None
                done_run.transcript = None
                done_run.state = "cancelled"
                done_job.state = "cancelled"
                done_db.commit()
                return True
            done_run.state = "needs_review" if proposal.needs_human_review else "complete"
            done_run.proposal = proposal.model_dump()
            done_run.detected_language = proposal.detected_language
            done_run.model_name = proposal.model_name
            done_run.model_version = proposal.model_version
            done_run.taxonomy_version = proposal.taxonomy_version
            done_run.confidence = proposal.confidence
            done_run.needs_human_review = proposal.needs_human_review
            done_run.completed_at = datetime.now(timezone.utc)
            done_job.state = "complete"
            done_db.commit()
        return True


def purge_expired_data() -> None:
    settings = get_settings()
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.retention_days)
    root = settings.audio_storage_dir
    with SessionLocal() as db:
        items = list(db.scalars(select(Feedback).where(Feedback.deleted_at.is_not(None), Feedback.deleted_at < cutoff)))
        for item in items:
            asset = db.scalar(select(FeedbackAsset).where(FeedbackAsset.feedback_id == item.id))
            if asset:
                path = os.path.join(root, os.path.basename(asset.object_key))
                try:
                    os.remove(path)
                except FileNotFoundError:
                    pass
                db.delete(asset)
            for model in (StatusEvent, ProcessingJob, ProcessingRun, Comment, FeedbackGroup):
                for child in db.scalars(select(model).where(model.feedback_id == item.id)):
                    db.delete(child)
            db.delete(item)
        expired = list(db.scalars(select(Upload).where(Upload.expires_at < datetime.now(timezone.utc), Upload.state != "attached")))
        for upload in expired:
            path = os.path.join(root, os.path.basename(upload.object_key))
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            db.delete(upload)
        db.commit()


def main() -> None:
    delay = get_settings().worker_poll_seconds
    last_purge = 0.0
    while True:
        if time.monotonic() - last_purge > 60:
            purge_expired_data()
            last_purge = time.monotonic()
        if not process_one():
            time.sleep(delay)


if __name__ == "__main__":
    main()
