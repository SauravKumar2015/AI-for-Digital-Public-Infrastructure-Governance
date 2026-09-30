# AI for Digital Infrastructure & Governance — External API Catalog for Language Support

**Research checked:** 27 September 2026  
**Purpose:** identify external services the application may call for multilingual UI, citizen text/audio intake, translation, and feedback categorization.

## Recommendation

You do **not** need an external API just to display a translated website or accept/store text in Indian scripts. Use maintained UI translation files and Unicode text storage. External APIs are useful for speech-to-text, optional translation, language identification, and AI classification.

For the hackathon, integrate **one ASR provider only if voice intake is enabled** and **one classification provider behind the internal NLP adapter**. Add a separate text-translation API only if staff need an English (or other language) reading aid. Keep provider calls behind backend adapters so you can switch providers. BHASHINI and Sarvam are candidate India-focused providers to evaluate. The final provider must be selected only after testing the exact language/capability matrix. Test your chosen 40+ language set before claiming coverage: one provider's “multilingual” or “22 language” statement does not establish support for all 40 languages, every script, or every capability.

## Which APIs are needed?

| Capability | Needed? | What it does | Recommendation |
|---|---|---|---|
| Website interface localization | Yes, feature required; external API no | Shows menus, help, form labels, validation, and status labels in the selected language | Use versioned translation resource files (e.g. JSON) reviewed by people. Do not translate UI on every request with an LLM. |
| Multilingual text intake/storage | Yes; external API no | Accepts text in the selected language and saves it | HTML/Unicode + PostgreSQL `TEXT`/`JSONB` can store native scripts. Preserve source text unchanged. |
| Speech-to-text (ASR) | Only for voice submissions | Turns uploaded speech into a transcript for search/classification and staff review | Choose BHASHINI or Sarvam after language/audio tests; never block saving the original audio on transcript success. |
| LLM feedback classification | Recommended for MVP | Suggests category, feedback type, severity/urgency, summary, and evidence from text/transcript | Use one LLM API with structured output; validate schema and enums in backend and route low-confidence cases to review. |
| Text translation | Optional | Shows staff a translated rendering of citizen text | Use BHASHINI or Sarvam translation. Keep original alongside translation; label it machine translated. Not needed to accept a submission. |
| Language detection | Optional | Guesses the language when user did not choose one or input is mixed | Prefer user's selected language as hint; add a provider only for `unknown`/code-mixed cases. Keep detected and selected language separate. |
| Text-to-speech | Optional accessibility enhancement | Reads status/instructions aloud | Add only if needed for the product demo; not needed to record citizen voice. |
| Geocoding/maps | Optional and separate from language | Converts a typed location into coordinates or renders a map | Add only if the map feature needs it. Never infer a precise location from text without review. |

## Provider options researched

### 1. BHASHINI / ULCA — India-first provider to evaluate

Potential services: Automatic Speech Recognition (ASR), machine translation, text-to-speech, transliteration, normalization, language-related tasks, and other Indic language models. The developer documentation describes selecting a task pipeline/model, configuring it, then calling inference. The model catalog is language/task-specific, so confirm each source/target pair and ASR language against the current portal before integrating. Access may require organization onboarding/credentials.

- [BHASHINI developer docs: Text-to-Text](https://bhashini-developer-portal-dev.bhashini.co.in/docs/capabilities/text-to-text)
- [BHASHINI API integration guide](https://dibd-bhashini.gitbook.io/bhashini-apis)
- [BHASHINI portal](https://bhashini.gov.in/)
- [BHASHINI.ai REST API Swagger](https://tts.bhashini.ai/openapi/ui/)

**Use when:** the hackathon wants an India-specific language platform and the team can obtain access and verify the required endpoints quickly. **Check first:** onboarding time, rate limits, available task/model IDs for the required languages, service availability, audio limits, and current data processing terms. The live documentation and model catalog may differ between BHASHINI portal products.

### 2. Sarvam AI — straightforward Indic API alternative

Official API docs currently describe:

- `POST /speech-to-text` for transcription; its language options include the 22 Scheduled Indian languages plus English, with model/mode options such as native transcription, transliteration, verbatim, code-mixed output, and speech-to-English translation. Check current model/version notes and per-language behavior.
- `POST /translate` for text translation; `sarvam-translate:v1` documents translation among the 22 Scheduled Indian languages, with a 2,000-character request limit. Longer content needs sentence-aware chunking.
- Other API families include language identification, transliteration, text-to-speech, and chat/reasoning; these are optional for this application's first version.

- [Sarvam speech-to-text API reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe)
- [Sarvam text translation API reference](https://docs.sarvam.ai/api-reference/text/translate-text)
- [Sarvam language coverage guide](https://docs.sarvam.ai/api-reference-docs/building-for-india)
- [Sarvam API overview](https://docs.sarvam.ai/api-reference/introduction)

**Use when:** the team wants a compact India-focused API integration and the target languages fit its verified coverage. **Limitation:** support for 22 scheduled languages alone does not meet a 40+ language requirement. Confirm whether the selected speech model covers every language you plan to enable.

### 3. Google Cloud Translation / Speech-to-Text — general-purpose comparison option

Google provides separate Cloud Translation and Speech-to-Text APIs. Their supported-language tables are capability/model-specific. The Translation page distinguishes models, and some language support is marked experimental; Speech-to-Text requires checking the exact locale/model. Do not infer full 40-language coverage from the general product description.

- [Cloud Translation language support](https://docs.cloud.google.com/translate/docs/languages)
- [Cloud Translation text endpoint](https://docs.cloud.google.com/translate/docs/translate-text)
- [Cloud Speech-to-Text supported languages](https://docs.cloud.google.com/speech-to-text/docs/speech-to-text-supported-languages)

**Use when:** the project already has Google Cloud access or evaluation shows better performance for the languages/audio in scope. **Check first:** locale coverage, region/data residency, billing, project setup, and model-specific limitations.

### 4. LLM API for categorization — select one, provider-neutral

Use one API from an LLM provider that supports your chosen languages and schema-constrained/structured JSON output. Example: [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) supports output schemas, while its documentation cautions that schema compliance alone does not guarantee semantically correct values. Other LLM providers can be substituted behind the same internal interface.

Ask for only fields such as:

```json
{
  "feedback_type": "complaint",
  "category": "water",
  "severity": "medium",
  "urgency": "high",
  "summary": "Water supply is unavailable in the locality.",
  "evidence": ["original phrase supporting the label"],
  "needs_human_review": true
}
```

The server owns the allowed categories and validates every field. Keep confidence as a review hint until calibrated. Don't let the LLM update government status, decide eligibility, or trigger funding actions. Test classification in the original language; translation to English before classification can lose nuance and should be measured rather than assumed better.

## Minimal Integration Set for This Application

### Required for the described product

1. **No external localization API:** app loads reviewed interface translation bundles; user preference selects a locale.
2. **No external text API for storage:** submit the original Unicode text to the application's own backend and database.
3. **One ASR provider** for audio submissions. Start with BHASHINI or Sarvam; verify voice coverage for every enabled language and record provider/model on each processing run.
4. **One classification provider** for category/issue extraction. This may be the teammate's custom NLP service or an external provider behind the same backend adapter. Invoke asynchronously from the backend after persistence.

### Optional, based on chosen UI/workflow

5. **Text translation** to help staff read submissions outside their language. Prefer a button/secondary view; retain original and label translation as machine-generated.
6. **Language identification** when a citizen selects “not sure” or code-mixing makes the selected language unclear.
7. **Text-to-speech** to read interface guidance or status messages aloud.
8. **Geocoding/maps** if the dashboard includes mapped locations.

Login/identity, email/SMS OTP, database, object storage, and map tiles are infrastructure or separate app integrations; they are not language AI APIs. The [API_DESIGN.md](API_DESIGN.md) file specifies the application's own browser-facing endpoints; provider endpoints remain private.

## Integration pattern

```text
Browser (localized UI bundle)
  -> App API: submit original Unicode text OR request private audio upload
  -> PostgreSQL: persist immutable submission and pending processing job
  -> Private object storage: original audio bytes
  -> Backend worker: ASR API (audio only) -> optional translation API -> LLM classification API
  -> Validate/record proposed result -> staff review/dashboard API
```

Never call paid AI providers directly from the browser. Store provider secrets in backend environment/secret management. Add timeouts, bounded retries, cost/rate limits, request IDs, and a mock provider for demos. Provider failure must not lose a submission or prevent a user from seeing its receipt/status.

## 40+ language acceptance checklist

The product's 40+ list must be an explicit project-owned registry: language name/endonym, code, script(s), interface translation status, typed text status, ASR status, translation status, and last evaluation date. For each provider and capability:

1. Verify the exact language code and script against current provider documentation/portal.
2. Check credentials, quota, request/audio duration limits, and whether the API is production-ready or preview.
3. Test real examples for dialects, code-mixing, Roman-script typing, regional names, and noisy voice samples.
4. Measure error and human correction rates by language. Do not pool all languages into one score.
5. Mark each feature as `supported`, `limited`, or `unavailable`; provide a safe manual path when unavailable.

No provider researched here should be assumed to cover all 40+ languages for **all** of interface localization, text translation, speech recognition, and classification. If the exact 40-language/capability matrix is mandatory, combine providers or add human-reviewed fallback, and budget time to verify each pair before promising it.

## Privacy and procurement checks before real submissions

Before sending real citizen text/audio to a vendor, review its terms, retention/training settings, data location, subprocessors, deletion support, security controls, and whether the project has authority/consent for external processing. Minimize direct identifiers. Use synthetic data for the hackathon demo until the data owner approves real data handling.
