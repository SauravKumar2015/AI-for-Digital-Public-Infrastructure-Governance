# AI for Digital Infrastructure & Governance — Requirements

## 1. Product Requirements

| ID | Requirement | Priority |
|---|---|---|
| PR-01 | Accept citizen text in at least 40 configured Indian languages, including the 22 Eighth Schedule languages. | Must |
| PR-02 | Preserve original text, declared language, detected language, and script; never replace source with translation. | Must |
| PR-03 | Classify submissions into a versioned allow-listed taxonomy and permit `unknown`/manual review. | Must |
| PR-04 | Keep feedback type, issue category, sentiment, severity, and urgency as distinct fields. | Must |
| PR-05 | Show aggregate patterns and individual records with filters and review state. | Must |
| PR-06 | Explain area-priority calculations and allow authorized analyst annotation/correction. | Must |
| PR-07 | Let users record and submit voice feedback in their selected language; preserve the original audio and run ASR where that language is marked speech-supported, retaining transcript provenance and routing unsupported/failed recognition for review. | Must |
| PR-08 | Suggest duplicates/groups but require authorized human confirmation before merging. | Should |
| PR-09 | Provide submission receipt and processing status. | Should |
| PR-10 | Export authorized aggregate results for demonstration. | Could |
| PR-11 | Localize website interface independently from submission language. | Must |
| PR-12 | Allow only allow-listed, non-security profile preferences to be changed. | Must |
| PR-13 | Allow users to submit text/audio, view their own submission/status, and delete their own submission. | Must |
| PR-14 | Make submitted feedback/comments immutable; provide no edit endpoint. | Must |
| PR-15 | Keep source text/audio separate from transcripts, translations, detected language, and AI output. | Must |

## 2. AI Processing Requirements

- Call the custom NLP service only from the FastAPI backend/worker.
- Never expose model credentials or private model endpoints to the browser.
- Validate structured output against a server-owned Pydantic schema.
- Restrict labels to server-owned enums.
- Allow `unknown` where the model cannot determine a value.
- Request concise evidence spans from the original text where feasible.
- Treat submission content as untrusted input.
- Record model name/version, taxonomy version, processing time, confidence/review state, and human corrections.
- Treat confidence as a review signal until calibration is measured.
- Do not send unnecessary identifiers to the model.
- Use bounded retries, timeouts, request limits, quotas, and manual fallback.

## 3. Data and Classification

### Feedback Type

```text
complaint
request
suggestion
appreciation
other
```

### Category

Initial categories:

```text
water
roads
sanitation
electricity
health
education
transport
housing
public_safety
other
unknown
```

### Severity

```text
low
medium
high
unknown
```

### Urgency

```text
low
medium
high
unknown
```

### Sentiment

```text
positive
neutral
negative
mixed
unknown
```

Sentiment must never be used alone to determine urgency or priority.

### Language

Use the project-owned language registry. Store:
- Language code.
- Display/native name.
- Script where known.
- Declared language.
- Detected language.
- Capability status.

## 4. Data Storage Requirements

Store structured data and metadata in PostgreSQL.

Store audio in private object storage and store only:
- Object key.
- MIME type.
- Size.
- Duration.
- Checksum.
- Upload state.
- Retention state.

Store processing runs separately from source feedback.

Ownership must always come from the authenticated session, never from client input.

## 5. Non-Functional Requirements

### Security
- TLS in deployment.
- Secret/environment management.
- Role-based access.
- Server-side authorization.
- Rate limiting.
- Input validation.
- Audit logging.

### Privacy
- Data minimization.
- Configurable retention.
- Deletion workflow.
- PII-aware logging.
- No raw sensitive data in public dashboards.

### Reliability
- Persist submission before AI processing.
- Use asynchronous processing.
- Keep failed jobs visible.
- Never lose the original submission because AI failed.

### Performance
- Intake must not wait for model inference.
- Dashboard should query stored results/aggregates.

### Accessibility
- Keyboard-usable forms.
- Readable labels.
- Responsive layout.
- Localized user-facing strings.

### Observability
Record:
- Request/processing latency.
- Failure rate.
- Model/version.
- Language.
- Review rate.
- Evaluation metrics.

Do not log raw content by default.

### Explainability
Show:
- Data window.
- Counts.
- Denominators where relevant.
- Score inputs.
- Weights.
- Data sources.
- Missing-data caveats.
- Review state.
