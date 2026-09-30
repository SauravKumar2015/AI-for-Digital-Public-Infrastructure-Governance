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

The root `.env.example` is configured for the PostgreSQL database `AI for digital instarcture & covernance`; copy it to `.env` and replace `YOUR_PASSWORD` and `APP_JWT_SECRET`. Generate the latter with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Set `APP_AUTH_MODE=local-jwt` for app-managed signup/login and JWT bearer authentication. If no `.env` is present, local development falls back to `application.db` (SQLite). The API uses an in-process mock classifier and private local audio directory. The development identity shim (`APP_AUTH_MODE=development`) remains restricted to localhost and is disabled in production. OIDC bearer authentication is also supported.

## Configuration

Set `APP_DATABASE_URL` in the root `.env` to the URL-encoded database name. App-managed local JWT mode requires a random `APP_JWT_SECRET`; access tokens last 15 minutes and refresh tokens rotate on use. OIDC mode requires issuer, audience, and JWKS URL. A production deployment also needs PostgreSQL, HTTPS, managed secrets, and private object storage. Do not enable development auth in production. `APP_NLP_MODE=http` enables the private NLP adapter; audio processing can use Gemini when separately configured.

The authentication API is `POST /api/v1/auth/signup`, `/login`, `/refresh`, and `/logout`. Sign-up creates citizen accounts only. Email verification, password reset, and MFA are not implemented yet; see the root API testing guide for request examples and deployment limitations.

The local upload implementation stores audio under `APP_AUDIO_STORAGE_DIR` and accepts files up to 15,000,000 bytes. Audio defaults to staff review; set `APP_AUDIO_MODE=gemini` and `APP_GEMINI_API_KEY` to enable Gemini transcription/classification in the worker. Every resulting classification remains subject to staff review. The audio is sent to Google's Gemini API when that mode is enabled. Replace local file storage with a private object-storage adapter before deployment. Database migration 0001 defines the initial schema.

## API

OpenAPI docs are served at `/docs` outside production. Routes follow `docs/06_API_DESIGN.md` under `/api/v1`. OIDC token validation is implemented for bearer JWTs; hosted login/callback and session-cookie issuance are delegated to the selected identity provider/client deployment and are not implemented in this API yet. Account deletion immediately redacts source text and removes it from normal queries, with private media purged after the configured retention window.

For endpoint URLs, authentication rules, request payloads, and example responses, see [`docs/08_API_TESTING_GUIDE.md`](../docs/08_API_TESTING_GUIDE.md).
