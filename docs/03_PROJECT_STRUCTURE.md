# AI for Digital Infrastructure & Governance — Project Structure and Implementation Plan

## 1. Repository Layout

```text
project-root/
├── frontend/                    # React + TypeScript + Vite
│   ├── public/
│   │   └── locales/             # Reviewed UI translation JSON files
│   └── src/
│       ├── app/                 # Routes and application shell
│       ├── components/          # Shared UI components
│       ├── features/
│       │   ├── auth/
│       │   ├── profile/
│       │   ├── feedback/
│       │   ├── comments/
│       │   ├── status/
│       │   └── dashboard/
│       ├── lib/
│       │   ├── api/             # Typed API client
│       │   └── i18n/            # Locale handling
│       └── main.tsx
│
├── backend/                     # Python + FastAPI
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/                # Settings, DB, security, errors
│   │   ├── api/                 # Versioned FastAPI routers
│   │   ├── features/
│   │   │   ├── auth/
│   │   │   ├── languages/
│   │   │   ├── profile/
│   │   │   ├── feedback/
│   │   │   ├── comments/
│   │   │   ├── processing/
│   │   │   ├── review/
│   │   │   └── analytics/
│   │   ├── clients/             # NLP/ASR adapters
│   │   ├── workers/             # Background processing
│   │   └── utils/
│   ├── migrations/              # Alembic migrations
│   └── tests/
│
├── nlp-service/                 # Optional sibling service
│   └── README.md
│
├── infra/
│   ├── compose.yaml
│
├── .env.example                 # Safe variable names/sample values; commit this
├── .env                         # Local secrets/values; never commit (in .gitignore)
│
├── docs/
├── .gitignore
└── README.md
```

`backend/pyproject.toml` is the Python dependency manifest in this layout. It replaces a separate `requirements.txt`; use one dependency source of truth rather than maintaining both by hand. If the team prefers the simpler `pip install -r requirements.txt` workflow, it can use `requirements.txt` instead, but update the setup instructions and do not let the two files drift.

The `.env.example` is safe to commit and documents required configuration variables. Developers copy it to `.env` and set local values there. The real `.env` must be ignored by Git; never put API keys, database passwords, or production secrets in `.env.example`.

This tree is the proposed application layout. The backend foundation, API, database migration, worker, and local compose setup have now been created under `backend/` and `infra/`. The `frontend/` directory remains intentionally untouched.

The backend currently uses configurable OIDC bearer-token validation, local development identity, a mock NLP adapter by default, and private local audio storage for development. Before using real citizen data or production deployment, select and configure the identity provider, private object storage, ASR provider, and approved NLP endpoint. The language registry is an intake list; its limited capability labels are not an evaluation claim.

## 2. FastAPI Feature Structure

Each feature should grow around its domain rather than creating one giant controller/service package.

Example:

```text
backend/app/features/feedback/
├── router.py
├── schemas.py
├── service.py
├── repository.py
├── models.py
└── permissions.py
```

### Responsibilities

- `router.py`: HTTP routes only.
- `schemas.py`: Pydantic request/response models.
- `service.py`: use cases and business rules.
- `repository.py`: database access.
- `models.py`: SQLAlchemy models.
- `permissions.py`: domain authorization helpers.

Routes should remain thin.

## 3. API Router Mapping

| Router | Main routes | Responsibility |
|---|---|---|
| Auth | `/auth/*` | OIDC login/callback/logout |
| Languages | `/languages` | Language registry |
| Profile | `/me` | Safe profile preferences and account deletion |
| Uploads | `/uploads` | Private audio upload authorization |
| Feedback | `/feedback` | Create/read/delete feedback |
| Status | `/feedback/{id}/status*` | Citizen-visible progress |
| Comments | `/feedback/{id}/comments*` | Immutable comments |
| Staff Feedback | `/staff/feedback*` | Staff review/status/classification |
| Analytics | `/analytics/*` | Aggregate dashboard data |
| Health | `/health/*` | Liveness/readiness |

## 4. Controller/Router Rules

Use FastAPI routers rather than Spring controllers.

A router should:

1. Authenticate the request.
2. Validate the request using Pydantic.
3. Check basic authorization.
4. Call the application service.
5. Return a typed response.

Business logic must not be placed directly in route handlers.

SQLAlchemy models must not be returned directly as API responses. Use Pydantic response schemas.

## 5. Implementation Order

### Phase 1 — Contract
Agree on:
- Taxonomy.
- Language registry.
- Feedback lifecycle.
- API schemas.
- NLP request/response schema.
- Audio limits.
- Roles.

### Phase 2 — Backend Foundation
Build:
- FastAPI application.
- PostgreSQL connection.
- SQLAlchemy models.
- Alembic.
- Health endpoints.
- Common error format.
- Authentication integration.

### Phase 3 — First Vertical Slice
Implement:
- `POST /api/v1/feedback`
- PostgreSQL persistence.
- `GET /api/v1/me/feedback`
- `GET /api/v1/feedback/{id}`
- Receipt response.
- Mock NLP processing.

### Phase 4 — Frontend
Build:
- Login.
- Language picker.
- Text submission.
- Receipt.
- Submission list/detail.
- Status display.
- Dashboard shell.

### Phase 5 — Review and Processing
Build:
- Background jobs.
- Mock NLP client.
- Real NLP client.
- Model-response validation.
- Review queue.
- Audit events.

### Phase 6 — Audio
Build:
- Private upload flow.
- Audio metadata.
- ASR adapter.
- Transcript provenance.

### Phase 7 — Analytics
Build:
- Aggregate dashboard.
- Filters.
- Priority components.
- Explainable score.
- Per-language evaluation.

## 6. Team Split

### Backend developer
- FastAPI API.
- PostgreSQL.
- SQLAlchemy/Alembic.
- Authentication/authorization.
- Processing workflow.
- NLP/ASR adapters.
- Tests.

### Frontend developer
- React + TypeScript.
- UI components.
- Localization.
- Citizen flows.
- Staff dashboard.
- API integration.

### Model developer
- NLP inference service.
- Model versioning.
- Supported-language declaration.
- Evaluation dataset/results.
- Private HTTP contract.

The model service must not directly modify the application database.
