# API Design

For runnable local examples and representative responses, see [API Testing Guide](08_API_TESTING_GUIDE.md).

Version prefix: `/api/v1`. All application routes below are relative to this prefix. JSON over HTTPS. API keys for AI providers stay on the server. Timestamps use ISO 8601 UTC. This design assumes an identity provider (OIDC/OAuth) issues the user's identity; do not build password storage/authentication from scratch for a hackathon.

## Controller/router inventory

Implement these as FastAPI routers. Keep route handlers thin: authenticate/authorize, validate the request, call a service, and return a response. Business rules and database writes belong in feature services/repositories.

| Router/controller | Main routes | Responsibility |
|---|---|---|
| `AuthRouter` | `GET /auth/login`; `GET /auth/callback`; `POST /auth/logout` | Start hosted OIDC login, validate callback/state, establish or revoke the application session. Passwords remain with the identity provider. |
| `LanguageRouter` | `GET /languages` | Return configured 40+ language/script entries and capabilities. |
| `ProfileRouter` | `GET/PATCH/DELETE /me` | Current user's profile; only safe preference fields can be edited. |
| `UploadRouter` | `POST /uploads` | Issue private, short-lived audio upload slots and validate completed upload. |
| `FeedbackRouter` | `POST /feedback`; `GET /me/feedback`; `GET /feedback/{id}`; `DELETE /feedback/{id}` | Create text/audio feedback; list/read/delete only owner's submissions. No edit route. |
| `FeedbackStatusRouter` | `GET /feedback/{id}/status`; `GET /feedback/{id}/status-events` | Expose safe processing and government progress to owner. |
| `CommentRouter` | `GET/POST /feedback/{id}/comments`; `DELETE /feedback/{id}/comments/{comment_id}` | Create/list/delete comments; no edit route. |
| `StaffFeedbackRouter` | `GET /staff/feedback`; `PATCH /staff/feedback/{id}/status`; `PATCH /staff/feedback/{id}/classification`; optional assignment route | Staff queue, status progression, human review, and assignment. Require staff role and audit changes. |
| `AnalyticsRouter` | `GET /analytics/summary`; `GET /analytics/priorities` | Authorized, aggregate dashboard data and transparent priority components. |
| `HealthRouter` | `GET /health/live`; `GET /health/ready` | Liveness/readiness checks; readiness should check dependencies required for serving API traffic; NLP availability may be reported separately so a temporary NLP outage does not make the entire citizen API unavailable. Do not reveal secrets or stack traces. |

All application routes are authenticated except login/callback, health endpoints, and the language registry when it contains no private data. Apply object ownership checks to every user-facing feedback/comment route. The custom NLP inference endpoint is internal service-to-service traffic, not part of the public application API and must not be exposed through the `/api/v1` browser-facing routers.

## 1. Core data and storage model

Store text and structured metadata in PostgreSQL. Store audio bytes in **private object storage** (or a local private file store for a local demo), then save only an object key and metadata in PostgreSQL. Do not put audio blobs directly in ordinary database rows. Never expose the storage key or permanent public URL to browsers.

Suggested tables/SQLAlchemy models:

- `users`: identity-provider subject ID, role, safe profile fields, preferred UI language, created/updated timestamps. Authentication credentials remain with the identity provider.
- `feedback`: UUID, owner user ID, immutable original text or media reference, declared language, script if known, location supplied by user, source channel, created time, lifecycle/deletion state.
- `feedback_assets`: feedback ID, private object key, MIME type, byte size, duration, checksum, upload/retention state.
- `processing_runs`: feedback ID, detected language, transcript (if audio), optional translation, proposed classification, provider/model and taxonomy/prompt versions, confidence/review state, error code, timestamps.
- `feedback_status_events`: feedback ID, status, stage, safe user-facing message, actor (system/analyst), timestamp. Append events instead of overwriting history.
- `comments`: feedback ID, author ID, immutable comment body, created time, deleted time. Users may create and delete their own comments; no edit endpoint.
- `audit_events`: actor, operation, target, timestamp, and safe change metadata. Do not copy raw sensitive content into logs.

Keep submitted language and original text/audio distinct from detected language, transcript, translation, and model output. Translations and transcripts are derived data and must never overwrite source content.

## 2. General rules

- All endpoints require an authenticated session except public language/configuration reads and the identity provider's own login flow.
- Use UUIDs, pagination (`limit`, `cursor`), server-side authorization, request IDs, payload limits, and rate limits.
- Return errors as `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`; never return provider stack traces.
- Return `202 Accepted` after a submission is safely persisted while background processing is pending.
- Enforce ownership on every citizen operation. A user can never change `owner_id`, moderation data, status, classification, or role.
- Feedback and comments are immutable after creation. There is deliberately no `PATCH` or `PUT` for feedback/comment content. A user can delete their own item.
- Deletion removes the item from normal views and future aggregates immediately, cancels queued work, and schedules attached audio/derived data for deletion under the configured retention policy. Keep only the minimum deletion tombstone/audit metadata required by policy; document the actual purge window to users.
- Model output is provisional and must be validated against server-owned schemas/enums. Client-supplied categories, status, confidence, and scores are ignored/rejected.

## 3. Language and UI configuration

### List supported languages

`GET /api/v1/languages`

Returns the language registry and per-capability status. Example:

```json
[{ "code": "hi", "name": "Hindi", "native_name": "हिन्दी", "script": "Deva", "text_status": "supported", "speech_status": "limited", "translation_status": "limited" }]
```

The frontend uses this list for language selection. Localized interface labels should come from versioned frontend translation files or a localization service—not be generated on every page load by an LLM. Save the user's preferred display language in their profile. A language may be available for text while speech processing is marked limited/unavailable.

## 4. Authentication and user profile

### Authentication

Use the selected identity provider's hosted login / OIDC flow. On success, the backend establishes a secure, HTTP-only, same-site session cookie (or validates short-lived bearer tokens if the client architecture requires them). The application API does not store passwords.

- `GET /api/v1/me`: return current user's safe profile and role.
- `PATCH /api/v1/me`: update only allow-listed fields such as `display_name`, `preferred_language`, `preferred_script`, and optional accessibility preferences.
- `DELETE /api/v1/me`: begin account deletion according to retention policy; revoke sessions and remove or anonymize owned content according to published policy.
- `POST /api/v1/me/sessions/revoke` (optional): revoke current/all sessions through the identity provider.

Example safe profile update:

```json
{ "display_name": "Asha", "preferred_language": "mr", "preferred_script": "Deva" }
```

Never allow self-service changes to `user_id`/identity-provider subject, role, permissions, verification status, account flags, audit fields, or ownership. Email/phone changes and verification belong to the identity provider's verified flow, not a normal profile PATCH.

## 5. Audio upload and feedback submission

### Create an upload slot

`POST /api/v1/uploads`

Authenticated; response provides a short-lived signed upload URL for private storage:

```json
{ "upload_id": "uuid", "upload_url": "https://signed-storage-url", "expires_at": "2026-09-26T10:05:00Z", "max_bytes": 15000000, "accepted_types": ["audio/webm", "audio/wav", "audio/mpeg"] }
```

The backend validates ownership, expiry, MIME type, byte size, and duration. The upload slot is temporary and not yet public feedback. Expire unattached uploads.

### Create text feedback

`POST /api/v1/feedback`

```json
{
  "kind": "text",
  "text": "आमच्या भागात तीन दिवसांपासून पाणी नाही.",
  "language": "mr",
  "location": { "state": "Maharashtra", "district": "Pune", "locality": "Ward 4" }
}
```

### Create audio feedback

`POST /api/v1/feedback`

```json
{
  "kind": "audio",
  "upload_id": "uuid",
  "language": "mr",
  "location": { "state": "Maharashtra", "district": "Pune", "locality": "Ward 4" }
}
```

The signed upload flow is: create upload slot → upload bytes → create feedback referencing `upload_id`. The server verifies that the upload belongs to this user and is complete before attaching it. Audio submissions preserve the original recording; transcription happens asynchronously when configured for that language. A text submission stores its exact Unicode text as submitted.

Response `202`:

```json
{
  "id": "b91fa812-60e2-4d2c-9e12-9eb673ce10e1",
  "status": "received",
  "created_at": "2026-09-26T10:00:00Z",
  "receipt": "b91fa812-60e2-4d2c-9e12-9eb673ce10e1"
}
```

The authenticated user's ID is taken from the session, never from the request body. Require consent for the stated processing purpose. Keep submissions immutable after creation; to correct an error, the user deletes the old submission and creates a new one.

## 6. Citizen feedback operations

- `GET /api/v1/me/feedback?limit=20&cursor=...`: list only the current user's submissions.
- `GET /api/v1/feedback/{id}`: owner can view their content and safe status; staff can view according to role. Do not expose internal prompts/provider errors to citizens.
- `DELETE /api/v1/feedback/{id}`: owner or authorized staff can delete according to policy. No content-edit endpoint exists.
- `GET /api/v1/feedback/{id}/status`: owner can see current progress and safe status text.
- `GET /api/v1/feedback/{id}/status-events?limit=...`: owner can see user-facing progress history, not internal-only audit details.

Suggested lifecycle: `received → processing → under_review → forwarded → in_progress → resolved`, with terminal/exception states `needs_more_information`, `rejected_with_reason`, `closed`, or `failed`. Define which transitions are available to staff and show a translated, plain-language label for each. AI processing state (transcription/classification) is separate from government handling state; do not conflate “AI processed” with “government resolved.”

Example status:

```json
{
  "feedback_id": "b91fa812-60e2-4d2c-9e12-9eb673ce10e1",
  "status": "in_progress",
  "stage": "assigned_to_department",
  "public_message": "The issue has been forwarded to the district water department.",
  "updated_at": "2026-09-27T08:15:00Z"
}
```

## 7. Comments

Comments are separate immutable records attached to feedback. Users may create and delete their own comments; there is no edit endpoint.

- `GET /api/v1/feedback/{id}/comments`: list comments visible to the current user.
- `POST /api/v1/feedback/{id}/comments`: create a comment (text + selected language; apply size limits and moderation).
- `DELETE /api/v1/feedback/{id}/comments/{comment_id}`: author or authorized moderator deletes it.

Example body: `{ "text": "The water supply is still unavailable.", "language": "en" }`. A comment does not change the original feedback, status, or priority. Staff replies, if needed, should use a distinct role and be clearly labelled.

## 8. Staff and analyst operations

Role-protected endpoints:

- `GET /api/v1/staff/feedback?...`: search/filter records for assigned geography and role.
- `PATCH /api/v1/staff/feedback/{id}/status`: transition government-handling status; require a public message/reason and append a status event. Citizens cannot call this.
- `PATCH /api/v1/staff/feedback/{id}/classification`: approve/correct proposed category, severity, urgency, or summary; append an audit event. Do not alter original submission.
- `POST /api/v1/staff/feedback/{id}/assignments`: assign to a department/queue if assignment is in MVP scope.
- `GET /api/v1/analytics/summary?...`: aggregate counts and distributions with time window, source, denominator, and privacy safeguards.
- `GET /api/v1/analytics/priorities?...`: advisory area ranking with visible weights/components/data caveats; never triggers funding decisions.

## 9. Custom NLP integration (internal worker, not citizen-facing API)

The application backend calls the teammate's custom NLP model through a private service interface. The browser must never call the model directly. After a submission is persisted, a worker loads the text (or an ASR transcript for audio) and sends a bounded request to the model service. The model returns **proposed** classifications; the application validates and persists them to `processing_runs`. Human review is separate from the model result.

Suggested model-service contract:

`POST http://nlp-service:8001/v1/classify`

```json
{
  "feedback_id": "b91fa812-60e2-4d2c-9e12-9eb673ce10e1",
  "text": "आमच्या भागात तीन दिवसांपासून पाणी नाही.",
  "language": "mr",
  "taxonomy_version": "1.0"
}
```

```json
{
  "model_name": "civic-feedback-classifier",
  "model_version": "0.1.0",
  "detected_language": "mr",
  "feedback_type": "complaint",
  "category": "water",
  "severity": "medium",
  "urgency": "high",
  "summary": "Water is unavailable in the locality.",
  "evidence": ["तीन दिवसांपासून पाणी नाही"],
  "confidence": 0.72,
  "needs_human_review": true
}
```

The model response must use only the agreed taxonomy enum values, allow `unknown`, have maximum lengths, identify model/taxonomy version, and return a clear error for unsupported language or failed inference. The backend must validate typed schemas, bound timeout/retries, and mark failed/uncertain jobs `needs_review`; it must not invent a successful result. `GET /health/ready` may check service availability. Keep the model service on a private network and authenticate service-to-service calls if supported by the deployment.

For audio submissions, this contract is text-in/text-out. Unless the teammate explicitly delivers an audio-capable model, run a separate ASR component first, preserve original audio, and store transcript plus ASR model/version. If no ASR component is ready, accept the recording and put it in a review queue rather than pretending the NLP text classifier processed it.

Suggested processing status fields: `processing_state = queued | transcribing | classifying | needs_review | complete | failed`. This is separate from the citizen-visible government-handling status. Model classification never updates that government status.

```json
{
  "detected_language": "mr",
  "script": "Deva",
  "transcript": null,
  "feedback_type": "complaint",
  "category": "water",
  "severity": "medium",
  "urgency": "high",
  "sentiment": "negative",
  "summary": "Water is unavailable in the locality.",
  "evidence": ["तीन दिवसांपासून पाणी नाही"],
  "confidence": 0.72,
  "needs_human_review": true
}
```

Confidence is only a review hint until calibrated. Invalid/failed model output leaves the original submission intact and marks NLP processing as needing review.

## 10. Database write sequence

For a text submission: authenticate → validate language/text/location → insert immutable `feedback` row with `received` status → insert status event and processing job in the same database transaction → return receipt → worker calls the private custom NLP service asynchronously, validates its result, and appends processing events.

For audio: authenticate → create upload slot → upload to private object storage → verify upload → insert feedback metadata + asset key + job transactionally → run ASR (if configured), then custom NLP classification asynchronously. If database creation fails, clean up the unattached uploaded object. When deleted, hide immediately, cancel jobs, remove from aggregates, then purge audio/transcript/derived content according to retention policy.

## 11. Error examples

- `400 invalid_language`: language code is not in registry.
- `401 unauthenticated` / `403 forbidden`: no valid session or wrong owner/role.
- `404 not_found`: resource absent or not visible to this user.
- `409 upload_not_ready`: audio upload not complete or already attached.
- `413 payload_too_large`: text/audio exceeds configured limits.
- `422 immutable_resource`: attempted edit of feedback/comment; create a new submission after deleting if correction is needed.
- `429 rate_limited`: request quota reached.
