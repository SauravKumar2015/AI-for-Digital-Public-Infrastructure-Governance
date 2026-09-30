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

During local development, `APP_AUTH_MODE=development` is enabled. Do **not** send a bearer token for local requests. Citizen routes default to the `local-citizen` identity. To use a separate citizen identity, send `X-Dev-User: demo-citizen`. For staff-only routes, send `X-Dev-User: local-staff`.

In production, development identity headers are ignored. Send the identity provider's access token:

```http
Authorization: Bearer <OIDC_ACCESS_TOKEN>
```

For JSON requests, send `Content-Type: application/json`. Health and language endpoints are public. All other routes require an authenticated identity. Staff routes additionally require an `analyst`, `official`, or `admin` role.

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
curl.exe -i http://127.0.0.1:8000/api/v1/me
```

Example response:

```json
{
  "subject":"local-citizen",
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
Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:8000/api/v1/feedback' -ContentType 'application/json' -Body $body
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
curl.exe -i -X PUT "http://127.0.0.1:8000/api/v1/uploads/<upload-uuid>/content" `
  -H "X-Dev-User: local-citizen" `
  -F "file=@recording.webm;type=audio/webm"
```

Expected response: `204 No Content`.

<!-- ### Create audio feedback

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
} -->
```

Expected response: `202 Accepted` with the same receipt shape as text submission. ASR is not configured yet, so the worker marks audio feedback for staff review rather than returning a transcript.

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

