# API Testing Guide

This guide covers the API currently implemented in the backend. It uses the local PostgreSQL database configured in the project `.env` and assumes the API is running at `http://127.0.0.1:8000`.

## Start the API and worker

In PowerShell, from the `backend` directory:

```powershell
.\.venv\Scripts\Activate.ps1
alembic upgrade head
uvicorn app.main:app --reload
```

In a second PowerShell window, start background processing:

```powershell
cd "E:\AI for Digital Public Infrastructure & Governance\backend"
.\.venv\Scripts\Activate.ps1
python -m app.workers.runner
```

OpenAPI documentation is available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Base URL and authentication

```text
Base URL: http://127.0.0.1:8000/api/v1
```

The API supports three authentication modes:

- **Local development:** with `APP_AUTH_MODE=development`, every private route requires `X-Dev-User`. The request must also come from localhost. Use `demo-citizen` (or another name) for citizen routes and `local-staff` for staff routes. This is a development identity header, not a password or secure login, and must not be used for a deployed/public API.
- **App-managed accounts:** set `APP_AUTH_MODE=local-jwt` and configure `APP_JWT_SECRET`. The API issues signed access JWTs and rotating refresh tokens after sign-up or login. This mode can be self-hosted; use HTTPS and protect the signing secret.
- **Deployed API:** set `APP_AUTH_MODE=oidc`, `APP_ENVIRONMENT=production`, and configure `APP_OIDC_ISSUER`, `APP_OIDC_AUDIENCE`, and `APP_OIDC_JWKS_URL`. Send an access JWT issued by that OIDC provider as a Bearer token. The API validates the signature, issuer, and audience. Staff routes additionally require the token's `role` claim to be `analyst`, `official`, or `admin`.

Production request header:

```http
Authorization: Bearer <OIDC_ACCESS_TOKEN>
```

In `local-jwt` mode, sign-up/login accept an email and password in JSON and return tokens. For private routes, send the access token as `Authorization: Bearer <ACCESS_TOKEN>`. In OIDC mode, login and password handling are provided by the identity provider. For JSON requests, send `Content-Type: application/json`.

### Which endpoints are public?

These endpoints do not require an access JWT:

| Endpoint | Access | What it exposes |
|---|---|---|
| `GET /api/v1/health/live` | Public | Liveness status only |
| `GET /api/v1/health/ready` | Public | Readiness and configured NLP mode; also checks database availability |
| `GET /api/v1/languages` | Public | Language registry and capability labels |
| `POST /api/v1/auth/signup` | Public | Creates a new citizen account and returns tokens in `local-jwt` mode |
| `POST /api/v1/auth/login` | Public | Exchanges valid credentials for tokens in `local-jwt` mode |

`POST /api/v1/auth/refresh` and `POST /api/v1/auth/logout` also do not require an access JWT, but the caller must possess and submit a valid refresh token. Every other endpoint requires an authenticated user or staff access JWT, except in the explicitly selected localhost-only development shim. Feedback and comment endpoints also enforce ownership; staff endpoints require an authorized staff role.

### Route security matrix

| Route(s) | Required access | Authorization rules |
|---|---|---|
| `GET /me`; `PATCH /me`; `DELETE /me` | Authenticated user | Own profile/account only |
| `POST /uploads`; `PUT /uploads/{upload_id}/content` | Authenticated user | Upload belongs to current user; short-lived slot and size/MIME checks |
| `POST /feedback`; `GET /me/feedback` | Authenticated user | Feedback is created/listed for current user |
| `GET /feedback/{feedback_id}`; `DELETE /feedback/{feedback_id}` | Authenticated user | Owner or authorized staff; non-owners receive not found |
| `GET /feedback/{feedback_id}/status`; `GET /feedback/{feedback_id}/status-events` | Authenticated user | Feedback owner or authorized staff |
| `GET /feedback/{feedback_id}/comments`; `POST /feedback/{feedback_id}/comments` | Authenticated user | Feedback owner or authorized staff |
| `DELETE /feedback/{feedback_id}/comments/{comment_id}` | Authenticated user | Comment author, analyst, or admin; feedback access is checked |
| `GET /staff/feedback` | Staff role | `analyst`, `official`, or `admin` |
| `PATCH /staff/feedback/{feedback_id}/status`; `PATCH /staff/feedback/{feedback_id}/classification` | Staff role | `analyst`, `official`, or `admin`; changes are audited |
| `POST /staff/feedback/{feedback_id}/groups/{group_id}` | Staff role | `analyst`, `official`, or `admin`; confirmation is audited |
| `GET /analytics/summary`; `GET /analytics/priorities` | Staff role | `analyst`, `official`, or `admin` |
| `POST /auth/signup`; `POST /auth/login` | Public in `local-jwt` mode | Public citizen registration/login; no role may be supplied |
| `POST /auth/refresh`; `POST /auth/logout` | Refresh token required | Refresh token is stored hashed, rotated on refresh, and revocable on logout |

In OIDC mode, missing or invalid JWT credentials return `401`; a valid citizen token used on a staff route returns `403`. In local development mode, missing `X-Dev-User` or a non-local request returns `401`.

### Sign up and get tokens

Generate a signing secret in PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the output in the repository root `.env` as `APP_JWT_SECRET=...`, set `APP_AUTH_MODE=local-jwt`, then restart the API and run `alembic upgrade head`. Keep this secret private and stable across API restarts and instances; never commit it.

`POST /api/v1/auth/signup` is public and creates a citizen account. Passwords must contain 12–128 characters. Successful sign-up returns an access and refresh token pair:

```powershell
$body = @{ email = 'citizen@example.org'; password = 'a-long-unique-passphrase'; display_name = 'Local Citizen' } | ConvertTo-Json
$tokens = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/signup' -ContentType 'application/json' -Body $body
```

Use the access JWT on private endpoints:

```powershell
Invoke-RestMethod -Uri 'http://127.0.0.1:8000/api/v1/me' -Headers @{ Authorization = "Bearer $($tokens.access_token)" }
```

### Log in

`POST /api/v1/auth/login` is public. It accepts the registered email and password and returns a new token pair. Invalid credentials return `401`.

```powershell
$body = @{ email = 'citizen@example.org'; password = 'a-long-unique-passphrase' } | ConvertTo-Json
$tokens = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/login' -ContentType 'application/json' -Body $body
```

### Refresh and log out

`POST /api/v1/auth/refresh` accepts the current refresh token and returns a replacement token pair. Each refresh token can be used once; reuse is detected and revokes that token family. Clients must store the replacement refresh token after every successful refresh.

```powershell
$body = @{ refresh_token = $tokens.refresh_token } | ConvertTo-Json
$tokens = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/refresh' -ContentType 'application/json' -Body $body
```

`POST /api/v1/auth/logout` revokes the refresh-token family. The current access token remains usable until its expiry (15 minutes by default).

```powershell
$body = @{ refresh_token = $tokens.refresh_token } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/auth/logout' -ContentType 'application/json' -Body $body
```

Sign-up never accepts a role; new accounts are always citizens. Staff roles must be assigned through a controlled administrative process. This initial flow does not yet include email verification, password reset, or MFA. For public production use, configure HTTPS, verification and account recovery, monitoring, and an account-abuse policy; an established OIDC provider is preferable when available.

## 1. Health checks

### Liveness

```http
GET /api/v1/health/live
```

No authentication required. Expected `200` response:

```json
{"status":"ok"}
```

### Readiness

```http
GET /api/v1/health/ready
```

No authentication required. Checks the database. Expected `200` response:

```json
{"status":"ready","nlp_mode":"mock"}
```

## 2. Language registry

```http
GET /api/v1/languages
```

No authentication required. Returns the configured language records. Example item:

```json
{
  "code":"mr",
  "name":"Marathi",
  "native_name":"मराठी",
  "script":"Deva",
  "text_status":"supported",
  "speech_status":"unavailable",
  "translation_status":"unavailable"
}
```

## 3. Profile

### Read profile

```http
GET /api/v1/me
```

Local request:

```powershell
curl.exe -i http://127.0.0.1:8000/api/v1/me -H "X-Dev-User: demo-citizen"
```

For a deployed OIDC configuration, use `-H "Authorization: Bearer <OIDC_ACCESS_TOKEN>"` instead of the development header.

Example response:

```json
{
  "subject":"demo-citizen",
  "role":"citizen",
  "display_name":null,
  "preferred_language":"en",
  "preferred_script":null
}
```

### Update safe preferences

```http
PATCH /api/v1/me
```

Request:

```json
{"display_name":"Asha","preferred_language":"mr","preferred_script":"Deva"}
```

Example response is the updated profile, with `preferred_language` set to `mr`. The API does notol accept re, permissions, or account identity changes here.

### Request account deletion

```http
DELETE /api/v1/me
```

Expected `202` response:

```json
{"status":"deletion_requested"}
```

## 4. Submit text feedback

```http
POST /api/v1/feedback
```

Request:

```json
{
  "kind":"text",
  "text":"आमच्या भागात तीन दिवसांपासून पाणी नाही.",
  "language":"mr",
  "location":{"state":"Maharashtra","district":"Pune","locality":"Ward 4"},
  "consent":true
}
```

Expected `202 Accepted` response:

```json
{
  "id":"<feedback-uuid>",
  "status":"received",
  "processing_state":"queued",
  "created_at":"<UTC timestamp>",
  "receipt":"<feedback-uuid>"
}
```

The receipt is returned after the source is stored and the processing job is queued. `consent` is required. The optional `location` object accepts `state`, `district`, and `locality`.

PowerShell example:

```powershell
$body = @{
  kind = 'text'
  text = 'आमच्या भागात तीन दिवसांपासून पाणी नाही.'
  language = 'mr'
  location = @{ state = 'Maharashtra'; district = 'Pune'; locality = 'Ward 4' }
  consent = $true
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/feedback' -Headers @{ 'X-Dev-User' = 'demo-citizen' } -ContentType 'application/json' -Body $body
```

## 5. Audio upload and submission

Audio is stored in the configured private local directory in development. The upload request and feedback creation both use the same local identity.

### Create upload slot

```http
POST /api/v1/uploads
```

Request:

```json
{"mime_type":"audio/webm"}
```

Local PowerShell example:

```powershell
$slot = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/uploads' -Headers @{ 'X-Dev-User' = 'demo-citizen' } -ContentType 'application/json' -Body '{"mime_type":"audio/webm"}'
```

Example `201 Created` response:

```json
{
  "upload_id":"<upload-uuid>",
  "upload_url":"/api/v1/uploads/<upload-uuid>/content",
  "expires_at":"<UTC timestamp>",
  "max_bytes":15000000,
  "accepted_types":["audio/webm"]
}
```

### Upload bytes

Use multipart form data with the field name `file` and the same content type declared in the upload slot:

```powershell
curl.exe -i -X PUT "http://127.0.0.1:8000/api/v1/uploads/$($slot.upload_id)/content" `
  -H "X-Dev-User: demo-citizen" `
  -F "file=@recording.webm;type=audio/webm"
```

Use the slot's `upload_id` in the URL. The upload must be no larger than the returned `max_bytes` (15,000,000 by default).

Expected response: `204 No Content`.

### Create audio feedback

```http
POST /api/v1/feedback
```

Request:

```json
{
  "kind":"audio",
  "upload_id":"<upload-uuid>",
  "language":"mr",
  "location":{"state":"Maharashtra","district":"Pune"},
  "consent":true
}
```

Expected response: `202 Accepted` with the same receipt shape as text submission. The worker processes the recording asynchronously. By default (`APP_AUDIO_MODE=review`) it queues the recording for staff review. To enable Gemini transcription and classification, set `APP_AUDIO_MODE=gemini` and configure `APP_GEMINI_API_KEY`; the worker stores a transcript and a proposed classification, always marked for human review. Gemini processing sends the submitted recording to Google's Gemini API. Keep consent and the applicable data-processing terms in mind before enabling it for real citizen recordings. The 15,000,000-byte upload cap is enforced per audio file.

Send the create-feedback request with the same identity used for the upload:

```powershell
$feedback = @{
  kind = 'audio'
  upload_id = $slot.upload_id
  language = 'mr'
  location = @{ state = 'Maharashtra'; district = 'Pune' }
  consent = $true
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/feedback' -Headers @{ 'X-Dev-User' = 'demo-citizen' } -ContentType 'application/json' -Body $feedback
```

## 6. List, read, track, and delete feedback

### List my submissions

```http
GET /api/v1/me/feedback?limit=20
```

Example response:

```json
{
  "items":[
    {"id":"<feedback-uuid>","kind":"text","language":"mr","status":"received","created_at":"<UTC timestamp>"}
  ],
  "next_cursor":null
}
```

For the next page, send the returned `next_cursor` as the `cursor` query parameter.

### Read a submission

```http
GET /api/v1/feedback/<feedback-uuid>
```

Example response:

```json
{
  "id":"<feedback-uuid>",
  "kind":"text",
  "text":"आमच्या भागात तीन दिवसांपासून पाणी नाही.",
  "language":"mr",
  "script":"Deva",
  "location":{"state":"Maharashtra","district":"Pune","locality":"Ward 4"},
  "status":"received",
  "processing_state":"queued",
  "proposal":null,
  "created_at":"<UTC timestamp>"
}
```

After the worker completes, `processing_state` and `proposal` will contain the processing result. The local mock model returns a demo proposal and marks it for human review.

### Read current status and status history

```http
GET /api/v1/feedback/<feedback-uuid>/status
GET /api/v1/feedback/<feedback-uuid>/status-events
```

Example current status:

```json
{
  "feedback_id":"<feedback-uuid>",
  "status":"received",
  "processing_state":"queued",
  "updated_at":"<UTC timestamp>"
}
```

Status events return an array of `{ "status", "public_message", "created_at" }` records.

### Delete a submission

```http
DELETE /api/v1/feedback/<feedback-uuid>
```

Expected response: `204 No Content`. Source text is redacted immediately; attached audio is purged according to the configured retention period.

## 7. Comments

### Add comment

```http
POST /api/v1/feedback/<feedback-uuid>/comments
```

Request:

```json
{"text":"The water supply is still unavailable.","language":"en"}
```

Expected `201 Created` response:

```json
{"id":"<comment-uuid>","text":"The water supply is still unavailable.","language":"en","created_at":"<UTC timestamp>"}
```

### List or delete comments

```http
GET /api/v1/feedback/<feedback-uuid>/comments
DELETE /api/v1/feedback/<feedback-uuid>/comments/<comment-uuid>
```

Delete returns `204 No Content`. Comments cannot be edited.

## 8. Staff endpoints

For local testing, add this header to each request:

```http
X-Dev-User: local-staff
```

### Staff feedback queue

```http
GET /api/v1/staff/feedback?status=received&language=mr&district=Pune&limit=50
```

Filters are optional: `status`, `category`, `language`, `district`, and `limit`. The response is an array of staff-visible feedback records.

### Change government status

```http
PATCH /api/v1/staff/feedback/<feedback-uuid>/status
```

Request:

```json
{"status":"under_review","public_message":"An analyst is reviewing this report."}
```

Example response:

```json
{"id":"<feedback-uuid>","status":"under_review"}
```

Only valid status transitions are accepted. Starting from `received`, `under_review` is a valid next status.

### Correct a classification

```http
PATCH /api/v1/staff/feedback/<feedback-uuid>/classification
```

Request example:

```json
{"category":"water","severity":"medium","urgency":"high","summary":"Water is unavailable in the locality."}
```

The feedback must already have a model proposal. The response contains the updated `proposal` and `needs_human_review:false`. Each correction creates an audit event.

<!-- ### Confirm a group

```http
POST /api/v1/staff/feedback/<feedback-uuid>/groups/<group-uuid>
```

Example response:

```json
{"feedback_id":"<feedback-uuid>","group_id":"<group-uuid>","confirmed":true}
``` -->

## 9. Analytics endpoints

Both endpoints require staff identity.
add -  X-Dev-User : local-staff
```http
GET /api/v1/analytics/summary
GET /api/v1/analytics/summary?language=mr
GET /api/v1/analytics/priorities
```

The summary response includes all-time totals and government-status counts. Priority results are advisory raw report counts by district, with caveats and no population denominator. They must not be treated as funding decisions.


Common status codes:

| HTTP | Example cause |
|---|---|
| `400` | Unknown language code or `consent:false` |
| `401` | Missing or invalid production bearer token |
| `403` | Citizen tries a staff-only route |
| `404` | Record is absent or not visible to this identity |
| `409` | Upload is incomplete/expired or status transition is invalid |
| `413` | Text or audio exceeds the configured limit |
| `415` | Uploaded file MIME type differs from the upload slot |
| `422` | Request fields fail validation |
| `429` | Local API rate limit reached |

