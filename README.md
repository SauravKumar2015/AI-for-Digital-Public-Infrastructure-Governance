# AI for Digital Public Infrastructure & Governance

A multilingual civic-feedback platform concept for collecting community concerns and helping public-service teams review submissions, track their status, and understand aggregate patterns. The system is intended to support human review and planning; it does not make government decisions or allocate public funds.

> **Project status:** This repository currently contains the FastAPI backend and project documentation. A frontend is not included yet. Text classification uses a mock provider by default. Audio submissions are accepted, but automatic speech recognition (ASR) is not connected and audio jobs are routed to staff review. See [Known limitations](#known-limitations).

## Problem and approach

Community concerns may arrive through disconnected channels and in different languages. This project provides an API foundation for collecting text or audio feedback, preserving the original submission, returning a receipt, tracking status, and supporting staff review and aggregate analytics.

The planned AI flow is modular: audio is transcribed by an ASR service; text is classified by an NLP service; the backend validates and stores model proposals for people to review. Provider credentials belong on the server, never in browser code.

## Current capabilities

- FastAPI REST API with interactive OpenAPI documentation.
- PostgreSQL persistence using SQLAlchemy and Alembic migrations.
- Text and audio feedback intake with receipt IDs.
- Local audio upload storage for development.
- Database-backed processing queue with a separate worker process.
- Mock text classifier for local development and an HTTP adapter for a compatible private NLP service.
- Citizen profile, feedback, status, and comment endpoints.
- Staff feedback queue, status updates, classification corrections, and aggregate analytics.
- Language registry and request validation.

## Architecture

    Client / future frontend
           | HTTPS REST
           v
    FastAPI backend ------ PostgreSQL
           |                    ^
           +-- processing jobs  |
                    |           |
              Background worker
                 /         \
       NLP classifier     ASR service
        (optional)      (not connected)
                 \         /
                 validated proposals / transcripts

ASR, a production classifier such as Gemini, hosted object storage, and a frontend are not configured by this repository. Do not describe planned integrations as live until they have been deployed and demonstrated.

## Technology

- Python 3.11 or newer
- FastAPI and Uvicorn
- Pydantic settings
- SQLAlchemy 2, psycopg, and PostgreSQL
- Alembic migrations
- HTTPX for the external NLP adapter

## Run locally on Windows

### Prerequisites

- Python 3.11+
- PostgreSQL running locally
- A PostgreSQL database created in pgAdmin or with createdb

From the repository root, copy the sample environment file and edit the database URL:

    Copy-Item .env.example .env
    notepad .env

The sample database name contains spaces and an ampersand, so they are URL-encoded:

    APP_DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/AI%20for%20digital%20instarcture%20%26%20covernance

Replace YOUR_PASSWORD with your local PostgreSQL password. Percent-encode reserved characters in a password if needed. Never commit .env, credentials, citizen recordings, or model weights.

Create the virtual environment and install the backend:

    cd backend
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -e .
    alembic upgrade head

Start the API in this terminal:

    uvicorn app.main:app --reload

Open a second PowerShell terminal for the worker:

    cd "E:\AI for Digital Public Infrastructure & Governance\backend"
    .\.venv\Scripts\Activate.ps1
    python -m app.workers.runner

The worker is a long-running process; leave its terminal open while using the API. Interactive API documentation is at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs). Database readiness is at [http://127.0.0.1:8000/api/v1/health/ready](http://127.0.0.1:8000/api/v1/health/ready).

### Local authentication

Local development defaults to APP_AUTH_MODE=development. Every private API route requires an explicit development identity header; anonymous requests receive `401`. This header is a local-only shim, not production authentication. Citizen request example:

    Header: X-Dev-User: local-citizen

Staff-only routes require this development identity:

    X-Dev-User: local-staff

Example:

    Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/analytics/summary' -Headers @{ 'X-Dev-User' = 'local-staff' }

Development identity headers are for local development only. Production requires configured OIDC issuer, audience, JWKS URL, and a bearer token with an allowed staff role. Audio uploads accept up to 15,000,000 bytes; Gemini processing is optional and disabled by default. See the [audio guide](docs/08_API_TESTING_GUIDE.md#audio-upload-and-submission) for configuration.

## API overview

All routes are under /api/v1.

| Area | Example routes | Access |
|---|---|---|
| Health | GET /health/live, GET /health/ready | Public |
| Languages | GET /languages | Public |
| Profile | GET/PATCH/DELETE /me | Authenticated user |
| Feedback | POST /feedback, GET /me/feedback, GET /feedback/{id} | Authenticated; ownership checked |
| Uploads | POST /uploads, PUT /uploads/{id}/content | Authenticated user |
| Status and comments | /feedback/{id}/status*, /feedback/{id}/comments | Authenticated; ownership checked |
| Staff review | /staff/feedback* | Staff role |
| Analytics | /analytics/summary, /analytics/priorities | Staff role |

See the [API testing guide](docs/08_API_TESTING_GUIDE.md) for payloads, responses, upload steps, authentication, and common errors. See [API design](docs/06_API_DESIGN.md) and the [provider catalog](docs/07_API_CATALOG.md) for more context.

## NLP classifier configuration

By default, APP_NLP_MODE=mock; text submissions receive a demo proposal requiring human review. To use the HTTP adapter, configure:

    APP_NLP_MODE=http
    APP_NLP_BASE_URL=https://your-private-nlp-service
    APP_NLP_API_TOKEN=your-secret-token

The backend sends POST to APP_NLP_BASE_URL/v1/classify with feedback_id, redacted text, language, and taxonomy_version. The response must match ClassificationProposal in backend/app/features/feedback/schemas.py. Keep API tokens in a secret manager or environment settings, not in Git.

### Audio transcription and classification

Audio uploads support up to 15,000,000 bytes (15 MB). Audio processing defaults to staff review. To enable Gemini processing, set `APP_AUDIO_MODE=gemini` and `APP_GEMINI_API_KEY` in the backend environment; optionally set `APP_GEMINI_AUDIO_MODEL` (default `gemini-2.5-flash`). The worker sends the recording to Gemini, stores its transcript and proposed classification, and always requires staff review. Audio processing is asynchronous. See [Audio upload and submission](docs/08_API_TESTING_GUIDE.md#audio-upload-and-submission) for the API flow.

## Known limitations

- **Frontend:** not included yet.
- **Text classification:** mock by default; the HTTP adapter requires a compatible deployed classifier.
- **Audio/ASR:** audio intake exists, but the worker does not call an ASR model. Audio jobs are marked for staff review.
- **Groups:** the staff route can confirm a supplied group ID, but there is no group creation/listing API to obtain one.
- **Uploads:** local filesystem storage is for development only. Production needs private object storage and a retention/deletion policy.
- **Authentication:** development identity is local-only. Production OIDC settings and the identity-provider login flow are not supplied here.
- **Analytics:** priority values are raw report counts, not population-adjusted estimates or funding recommendations.
- **Language quality:** configured languages do not imply that every AI capability is implemented or evaluated for each language.

The database schema includes transcript and model provenance fields, but those fields do not mean that ASR or a production classifier is connected.

## Repository layout

    backend/
      app/                 FastAPI routes, settings, models, clients, worker
      migrations/          Alembic database migrations
      Dockerfile           Backend container image
      pyproject.toml        Python dependencies and package settings
    docs/
      01_PRD.md             Product requirements
      02_ARCHITECTURE.md    Architecture and processing flows
      03_PROJECT_STRUCTURE.md
      04_REQUIREMENTS.md
      05_TESTING_GUIDE.md
      06_API_DESIGN.md
      07_API_CATALOG.md
      08_API_TESTING_GUIDE.md
    infra/
      compose.yaml          Container deployment reference

## Before production deployment

The local setup is not production-ready deployment configuration. Use managed PostgreSQL, private object storage for recordings, a production identity provider, managed secrets, HTTPS, restricted CORS origins, and deployed NLP/ASR services. Run database migrations during deployment and validate the end-to-end workflow with non-sensitive sample data.

## Project documents

- [Product requirements](docs/01_PRD.md)
- [Architecture](docs/02_ARCHITECTURE.md)
- [Project structure](docs/03_PROJECT_STRUCTURE.md)
- [Requirements](docs/04_REQUIREMENTS.md)
- [Testing guide](docs/05_TESTING_GUIDE.md)
- [API design](docs/06_API_DESIGN.md)
- [Provider catalog](docs/07_API_CATALOG.md)
- [API testing guide](docs/08_API_TESTING_GUIDE.md)
- [Hackathon submission materials](docs/HACKATHON_SUBMISSION.md)

## Submission materials

The `submission/` directory contains the project pitch deck in both editable PowerPoint and PDF formats:

- [Pitch deck (PDF)](submission/Code_for_Communities_Pitch_Deck.pdf)
- [Pitch deck (PowerPoint)](submission/Code_for_Communities_Pitch_Deck.pptx)

## Deployment reference

`infra/compose.yaml` describes a containerized deployment with PostgreSQL, a one-shot migration service, the API, and the background worker. It expects production configuration (including `POSTGRES_PASSWORD` and OIDC settings); it is not a zero-configuration local demo. Review the compose file and configure secrets and infrastructure before deploying. The local Windows workflow above is the intended development setup.
