# AI for Digital Infrastructure & Governance backend

FastAPI API and database-backed processing worker. The implementation uses synchronous SQLAlchemy sessions and a DB job table so intake commits before model processing. Run the API and worker as separate processes.

## Local setup

From this directory, create a virtual environment, install the project, and start the API:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
alembic upgrade head
uvicorn app.main:app --reload
```

In a second terminal, start the worker:

```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m app.workers.runner
```

The root `.env.example` is configured for the PostgreSQL database `AI for digital instarcture & covernance`; copy it to `.env` and replace `YOUR_PASSWORD` with the PostgreSQL password. If no `.env` is present, local development falls back to `application.db` (SQLite). The API uses an in-process mock classifier and private local audio directory. In development, every private route requires `X-Dev-User`; use `local-citizen` or another citizen label for citizen routes and `local-staff` for configured staff access. The development identity shim is limited to localhost and disabled when `APP_ENVIRONMENT=production`. Production requests require an OIDC bearer token.

## Configuration

Set `APP_DATABASE_URL` in the root `.env` to the URL-encoded database name. Production must use `APP_AUTH_MODE=oidc` with issuer, audience, and JWKS URL, PostgreSQL, private object storage integration, TLS at the edge, and a managed secret store. Do not enable development auth in production. `APP_NLP_MODE=http` enables the private NLP adapter; without that service audio remains review-only because no ASR adapter is configured.

The local upload implementation stores audio under `APP_AUDIO_STORAGE_DIR` and accepts files up to 15,000,000 bytes. Audio defaults to staff review; set `APP_AUDIO_MODE=gemini` and `APP_GEMINI_API_KEY` to enable Gemini transcription/classification in the worker. Every resulting classification remains subject to staff review. The audio is sent to Google's Gemini API when that mode is enabled. Replace local file storage with a private object-storage adapter before deployment. Database migration 0001 defines the initial schema.

## API

OpenAPI docs are served at `/docs` outside production. Routes follow `docs/06_API_DESIGN.md` under `/api/v1`. OIDC token validation is implemented for bearer JWTs; hosted login/callback and session-cookie issuance are delegated to the selected identity provider/client deployment and are not implemented in this API yet. Account deletion immediately redacts source text and removes it from normal queries, with private media purged after the configured retention window.

For endpoint URLs, authentication rules, request payloads, and example responses, see [`docs/08_API_TESTING_GUIDE.md`](../docs/08_API_TESTING_GUIDE.md).
