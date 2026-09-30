# ASR + NLP Classification Service

Multilingual citizen voice-feedback service deployed on Google Cloud Run.

- **ASR**: IndicConformer (Hindi, Marathi, Bengali, Gujarati, Sanskrit, Tamil,
  Telugu, Malayalam, Urdu) + Sarvam AI (Punjabi, Kannada, Odia, Assamese,
  Konkani, Maithili, Sindhi, Kashmiri, Manipuri, Santali, Bodo, Nepali, Dogri)
- **Classification/Reply**: Google Gemini 2.5 Flash
- **UI**: Gradio (record or upload audio, get transcript + category + reply)
- **Partner-backend integration**: `POST /v1/classify` implements the
  `ClassificationProposal` contract expected by `backend/app/clients/nlp.py`
  in this repo. Configure the FastAPI backend with `APP_NLP_MODE=http` and
  `APP_NLP_BASE_URL=<this service's Cloud Run URL>`.

## Live demo
https://citizen-feedback-chatbot-508734134597.us-central1.run.app

## Run locally
\`\`\`bash
pip install -r requirements.txt
export GEMINI_API_KEY=...
export SARVAM_API_KEY=...
export HF_TOKEN=...
python app.py
\`\`\`

## Deploy (Google Cloud Run)
\`\`\`bash
gcloud run deploy citizen-feedback-chatbot \\
  --source . \\
  --region us-central1 \\
  --allow-unauthenticated \\
  --memory 8Gi \\
  --cpu 2 \\
  --timeout 600 \\
  --set-build-env-vars GOOGLE_ENTRYPOINT="python app.py" \\
  --set-env-vars GEMINI_API_KEY=...,SARVAM_API_KEY=...,HF_TOKEN=...
\`\`\`
