from typing import Protocol

import httpx

from app.core.config import get_settings
from app.features.feedback.schemas import ClassificationProposal
from app.utils import redact_common_identifiers


class NlpClient(Protocol):
    async def classify(self, *, text: str, language: str, feedback_id: str) -> ClassificationProposal: ...


class MockNlpClient:
    async def classify(self, *, text: str, language: str, feedback_id: str) -> ClassificationProposal:
        lowered = text.casefold()
        category = "water" if any(word in lowered for word in ("water", "पाणी", "जल", "தண்ணீர்")) else "unknown"
        return ClassificationProposal(
            model_name="civic-platform-demo-mock", model_version="0.1.0", detected_language=language,
            feedback_type="complaint", category=category, severity="unknown", urgency="unknown",
            sentiment="unknown", summary="Demo result; staff review required.", evidence=[],
            confidence=0.0, needs_human_review=True,
        )


class HttpNlpClient:
    async def classify(self, *, text: str, language: str, feedback_id: str) -> ClassificationProposal:
        settings = get_settings()
        if not settings.nlp_base_url:
            raise RuntimeError("NLP endpoint is not configured")
        headers = {"Authorization": f"Bearer {settings.nlp_api_token}"} if settings.nlp_api_token else {}
        async with httpx.AsyncClient(timeout=settings.nlp_timeout_seconds) as client:
            response = await client.post(f"{settings.nlp_base_url.rstrip('/')}/v1/classify", json={
                "feedback_id": feedback_id, "text": redact_common_identifiers(text),
                "language": language, "taxonomy_version": "1.0",
            }, headers=headers)
            response.raise_for_status()
            return ClassificationProposal.model_validate(response.json())


def get_nlp_client() -> NlpClient:
    return HttpNlpClient() if get_settings().nlp_mode == "http" else MockNlpClient()
