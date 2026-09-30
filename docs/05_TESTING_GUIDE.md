# AI for Digital Infrastructure & Governance — Testing Guide

## 1. Test Layers

### Unit
Test:
- Taxonomy validation.
- Language registry.
- Priority calculation.
- Redaction.
- Review routing.
- Duplicate rules.
- API serialization.

### Contract
Verify that NLP/ASR adapters:
- Accept expected inputs.
- Normalize responses.
- Validate output schemas.
- Handle provider errors.
- Respect timeouts.

### Integration
Verify:
- Submission persistence before processing.
- Worker status transitions.
- Dashboard reads stored results.
- Analyst corrections create audit events.
- Deletion cancels pending work.

### End-to-End
Test:
```text
Citizen submission
    -> receipt
    -> processing
    -> review if necessary
    -> analyst correction
    -> dashboard aggregate
```

### Language Evaluation
Maintain a separate labelled test set for every enabled language and modality.

Never allow high-volume languages to hide failures in lower-volume languages through one pooled score.

### Security / Privacy
Test:
- Authorization.
- Ownership checks.
- Payload limits.
- Secret exposure.
- PII logging.
- Deletion.
- Aggregate privacy.

## 2. Language Test Matrix

For each configured language record:

- Unicode round-trip.
- Script handling.
- Punctuation.
- Spelling variation.
- Mixed-language input.
- Very short input.
- Language detection.
- Related-language confusion.
- Transliteration.
- Classification by major category.
- Classification by feedback type.
- Ambiguous/multi-issue examples.
- Voice recording and upload for the citizen flow.
- ASR/transcript checks for each language marked speech-supported; unsupported/failed ASR preserves original audio and routes the item for review.
- Provider/model/version.
- Sample size.
- Precision/recall/accuracy as applicable.
- Unsupported rate.
- Human correction rate.

Mark each capability:

```text
supported
limited
unavailable
```

## 3. Essential Scenarios

| Scenario | Expected Result |
|---|---|
| Valid text submission | Persist immediately; receipt returned; processing state starts `queued`. |
| Valid model result | Validate and save as proposed result. |
| Invalid model JSON/category | Quarantine result; source remains intact; processing becomes `needs_review` or `failed`. |
| Provider timeout/rate limit | Bounded retry; no fabricated classification. |
| Unsupported language | Preserve original; return `unknown`/review-needed processing result. |
| Mixed language/transliteration | Preserve source and mark uncertainty where needed. |
| Negative sentiment but low urgency | Sentiment does not automatically increase urgency. |
| Duplicate submissions | Suggest group; require human confirmation before merge. |
| Missing location | Keep record unlocated; never guess coordinates. |
| Analyst correction | Authorized update succeeds and audit event is created. |
| Unauthorized access | Deny request without leaking raw content. |
| PII in input | Apply configured redaction before external processing; logs do not expose raw PII. |
| HTML/script-like model output | Render as text; never execute. |
| Browser bundle inspection | No provider secret is present. |
| Priority view | Shows components, weights/version, time period, counts, denominators/source, and caveats. |

## 4. AI Quality Evaluation

Maintain a human-labelled test set and a held-out evaluation set.

Report by language and category:
- Language detection accuracy.
- Unsupported rate.
- Category precision/recall.
- Feedback-type precision/recall.
- Confusion matrix.
- Severity/urgency reviewer agreement.
- False-high severity/urgency rate.
- Evidence validity.
- Hallucinated-field rate.
- Human override rate.
- Processing latency.

Do not publish one overall accuracy figure without language-level sample counts.

## 5. Operational Checks

Verify:
- Rate limits.
- Request size/duration limits.
- Timeouts.
- Bounded retries.
- Queue idempotency.
- Database backup.
- Retention/deletion.
- Request IDs.
- No raw content in operational logs by default.
- Mock AI adapter works for demos even when the provider is unavailable.

## 6. Release Checklist

- All configured language capabilities are accurately labelled.
- Demo uses synthetic or approved de-identified data.
- Every AI result is traceable to source content and processing version.
- Low-confidence/unsupported results can be reviewed.
- Dashboard priority is explainable.
- Priority cannot directly execute public spending decisions.
- Provider secrets remain server-side.
- Authorization and deletion tests pass.
