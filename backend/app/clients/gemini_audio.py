from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.features.feedback.schemas import ClassificationProposal


class AudioResult(BaseModel):
    transcript: str = Field(max_length=10000)
    proposal: ClassificationProposal


def transcribe_and_classify(*, audio_path: Path, mime_type: str, language: str,
                            api_key: str, model: str) -> tuple[str, ClassificationProposal]:
    """Use Gemini to transcribe and propose a structured classification for one recording."""
    client = genai.Client(api_key=api_key)
    remote_file = client.files.upload(
        file=str(audio_path),
        config=types.UploadFileConfig(mime_type=mime_type),
    )
    try:
        response = client.models.generate_content(
            model=model,
            contents=[
                remote_file,
                (
                    "Transcribe this civic feedback recording faithfully in its spoken language. "
                    f"The submitter selected language code {language}. Do not add facts. "
                    "Then propose a classification using only the allowed schema values. "
                    "Set needs_human_review to true. Use unknown when uncertain."
                ),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=AudioResult,
                temperature=0,
            ),
        )
        result = response.parsed
        if not isinstance(result, AudioResult) or not result.transcript.strip():
            raise ValueError("Gemini returned no audio transcript")
        proposal = result.proposal.model_copy(update={
            "model_name": model,
            "model_version": "api-managed",
            "taxonomy_version": "1.0",
            "needs_human_review": True,
        })
        return result.transcript, proposal
    finally:
        try:
            client.files.delete(name=remote_file.name)
        except Exception:
            # Gemini Files expire automatically; a cleanup failure must not mask inference results.
            pass
