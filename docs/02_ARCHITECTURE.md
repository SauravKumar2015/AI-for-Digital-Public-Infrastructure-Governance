# AI for Digital Infrastructure & Governance — Technology Stack and Architecture

## 1. Technology Stack

### Frontend
- React
- TypeScript
- Vite
- React Router
- Tailwind CSS or another accessible component library
- Fetch API or Axios
- Reviewed localization JSON resources

### Backend
- Python 3.11+
- FastAPI
- Pydantic
- SQLAlchemy 2
- psycopg
- Alembic
- OIDC/OAuth-based identity integration
- Background worker for asynchronous processing

### Database
- PostgreSQL
- PostGIS only if geospatial queries require it

### AI / NLP
- Custom NLP inference service owned by the model teammate
- Private service-to-service HTTP API
- Optional external provider adapter
- Separate ASR adapter for audio unless the custom model supports audio directly

### Storage
- Private object storage for audio
- PostgreSQL for structured data and metadata

### Deployment
- React frontend
- FastAPI backend
- PostgreSQL
- Worker
- Optional ASR service
- Private NLP service
- Secret/environment configuration

## 2. Architecture

```text
React + TypeScript
        |
        | HTTPS / REST
        v
Python FastAPI Backend
        |
        +--------------------+
        |                    |
        v                    v
   PostgreSQL          Background Worker
                             |
                    +--------+---------+
                    |                  |
                    v                  v
                  ASR              NLP Service
                (audio)             (text)
                    |                  |
                    +--------+---------+
                             |
                             v
                    Validate / Persist
                             |
                             v
                       PostgreSQL
```

The browser must never call the private NLP service directly.

## 3. Core Processing Flow

### Text

```text
Citizen
  -> React
  -> POST /api/v1/feedback
  -> FastAPI validates and persists source
  -> status = received
  -> processing job created
  -> worker
  -> NLP service
  -> validate structured result
  -> save proposed result
  -> complete OR needs_review
```

### Audio

```text
Citizen
  -> React
  -> request upload slot
  -> private object storage
  -> create feedback referencing upload
  -> processing job
  -> ASR
  -> transcript
  -> NLP service
  -> validate result
  -> complete OR needs_review
```

The original audio is never replaced by the transcript.

## 4. Application Responsibilities

FastAPI owns:
- Authentication/session validation.
- Authorization.
- Input validation.
- Business rules.
- Database transactions.
- Feedback lifecycle.
- Review workflow.
- Audit logging.
- NLP/ASR adapter calls.
- Model-response validation.
- Analytics queries.

The NLP service owns:
- Model loading.
- Inference runtime.
- Model-specific preprocessing.
- Model versioning.
- Model-specific dependencies.

The model service must not write directly to the application database.

## 5. Internal Provider Interfaces

Example conceptual contracts:

```python
class NlpClient:
    async def classify(
        self,
        text: str,
        language: str,
        taxonomy_version: str,
    ) -> ClassificationResult:
        ...


class AsrClient:
    async def transcribe(
        self,
        audio_ref: str,
        language_hint: str | None = None,
    ) -> TranscriptResult:
        ...
```

Implementations can include:
- `MockNlpClient`
- `CustomNlpClient`
- Optional external-provider client
- `MockAsrClient`
- Optional external ASR client

## 6. Model Result Rules

The model response must:
- Use server-approved taxonomy values.
- Permit `unknown`.
- Include model name/version.
- Include taxonomy version.
- Include evidence where applicable.
- Respect maximum field lengths.
- Include confidence only as a review signal unless calibrated.
- Indicate `needs_human_review`.

Invalid or failed output must never be converted into a fabricated successful result.

## 7. Processing States

AI processing state is separate from government-handling status.

### AI processing state

```text
queued
transcribing
classifying
needs_review
complete
failed
```

### Government-handling status

```text
received
processing
under_review
forwarded
in_progress
resolved
needs_more_information
rejected_with_reason
closed
failed
```

Do not treat “AI processed” as “government resolved.”

## 8. Security Baseline

- Keep NLP and ASR endpoints private.
- Keep provider/API secrets on the backend.
- Use TLS in deployment.
- Use role-based authorization.
- Enforce object ownership server-side.
- Apply payload limits and rate limits.
- Use bounded retries and timeouts.
- Do not log raw sensitive submissions by default.
- Restrict raw submissions and audio to authorized staff.
- Use synthetic data for the hackathon unless real-data handling is approved.

## 9. Development Principle

Build one vertical slice first:

```text
React form
    ->
FastAPI submission endpoint
    ->
PostgreSQL
    ->
receipt
    ->
mock processing
    ->
classification result
    ->
dashboard
```

Then replace the mock NLP client with the teammate's real service.
