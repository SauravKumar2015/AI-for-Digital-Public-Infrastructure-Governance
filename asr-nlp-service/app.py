import os
import json
import csv
import mimetypes
from datetime import datetime

import torch
import torchaudio
import requests
import shutil
from huggingface_hub import login, snapshot_download
from transformers import AutoModel
from google import genai
import gradio as gr
from fastapi import FastAPI, HTTPException

# ---------- Auth / clients (reads from HF Space "Repository secrets") ----------
HF_TOKEN = os.environ.get("HF_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
SARVAM_KEY = os.environ.get("SARVAM_API_KEY")

if HF_TOKEN:
    login(token=HF_TOKEN)

_ASR_REPO_ID = "ai4bharat/indic-conformer-600m-multilingual"

# The model's own loading code re-downloads itself into HF's default cache
# (blobs + symlinks). A newer onnxruntime rejects that symlinked layout with
# an "external data path escapes model directory" error. Fix: pre-populate
# the same cache ourselves, then replace every symlink with a real copy of
# its target file. When the model's internal loader runs afterwards, the
# files it needs already exist as real files, so nothing gets re-symlinked.
_snapshot_dir = snapshot_download(repo_id=_ASR_REPO_ID, token=HF_TOKEN)
for _root, _dirs, _files in os.walk(_snapshot_dir):
    for _fname in _files:
        _fpath = os.path.join(_root, _fname)
        if os.path.islink(_fpath):
            _real_target = os.path.realpath(_fpath)
            os.unlink(_fpath)
            shutil.copyfile(_real_target, _fpath)

model = AutoModel.from_pretrained(_ASR_REPO_ID, trust_remote_code=True)
print("ASR model loaded")

client = genai.Client(api_key=GEMINI_KEY)
print("Gemini + Sarvam keys loaded")

# ---------- Categories (citizen-facing UI) ----------
CATEGORIES = [
    "Aadhaar/Identity Update", "Ration Card", "Pension", "Scholarship",
    "MGNREGA/Job Card", "Housing Scheme", "Health Insurance",
    "Income/Residence Certificate", "Traffic Fine Query",
    "House Construction Permission", "Water Supply Complaint",
    "Road/Bridge Complaint", "Electricity Complaint", "Ration Shop Complaint",
    "Health Center Complaint", "School Complaint", "Garbage/Streetlight Complaint",
    "Corruption/Bribery Complaint", "Farmer Support", "Other"
]

def understand_and_reply(transcript, lang_name):
    prompt = f"""You are a multilingual citizen-service assistant for an Indian government platform.
A citizen submitted this request (transcribed from voice), in {lang_name}:

"{transcript}"

Do the following:
1. Classify it into exactly one of these categories: {', '.join(CATEGORIES)}
2. Write a short, helpful, respectful reply that:
   - Is in {lang_name}, using EXACTLY the same script/writing system as the input text above — copy the script style from the quoted transcript, do not switch to a different script even if that script is also used for {lang_name} elsewhere in the world
   - Acknowledges their request
   - Gives general guidance on the process or where to go (CSC center, gram panchayat, municipal office, etc. — keep it generic/informational, not a specific fake office)
   - Is 2-4 sentences, plain and clear for a citizen with no technical background

Respond ONLY in this exact JSON format, no markdown, no extra text:
{{"category": "...", "priority": "high|medium|low", "reply": "..."}}

Priority guide: complaints about basic services with no response yet (health, water, electricity, corruption) = high; scheme applications/queries = medium; general info requests = low.
"""
    response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
    text = response.text.strip()
    if text.startswith("```"):
        text = text.strip("`").replace("json", "", 1).strip()
    return json.loads(text)

# ---------- Partner-backend classification contract ----------
# Matches ClassificationProposal in the partner repo
# (backend/app/features/feedback/schemas.py) so this service can be plugged in
# as their HttpNlpClient target via APP_NLP_MODE=http + APP_NLP_BASE_URL,
# called at POST {APP_NLP_BASE_URL}/v1/classify.
PARTNER_CATEGORIES = [
    "water", "roads", "sanitation", "electricity", "health",
    "education", "transport", "housing", "public_safety", "other", "unknown",
]
PARTNER_FEEDBACK_TYPES = ["complaint", "request", "suggestion", "appreciation", "other", "unknown"]
PARTNER_LEVELS = ["low", "medium", "high", "unknown"]
PARTNER_SENTIMENTS = ["positive", "neutral", "negative", "mixed", "unknown"]

def _coerce_enum(value, allowed, default="unknown"):
    return value if value in allowed else default

def classify_for_partner(text, language_code):
    lang_name = LANG_NAMES.get(language_code, language_code)
    prompt = f"""You are a classification service for a citizen-feedback governance platform.
A citizen submitted this text, in {lang_name}:

"{text}"

Classify it using EXACTLY these controlled vocabularies (pick one value per field from
the list given, never invent a new value):
- feedback_type: one of {PARTNER_FEEDBACK_TYPES}
- category: one of {PARTNER_CATEGORIES}
- severity: one of {PARTNER_LEVELS}
- urgency: one of {PARTNER_LEVELS}
- sentiment: one of {PARTNER_SENTIMENTS}

Also provide:
- summary: a neutral, factual, English summary of the issue, under 500 characters
- evidence: up to 8 short quoted or paraphrased snippets from the text supporting your
  classification
- confidence: a number from 0 to 1 for how confident you are in this classification
- needs_human_review: true if the text is ambiguous, sensitive, low-confidence, or the
  category/severity is unclear; false otherwise

If unsure of any field, use "unknown" rather than guessing.

Respond ONLY in this exact JSON format, no markdown, no extra text:
{{"feedback_type": "...", "category": "...", "severity": "...", "urgency": "...", "sentiment": "...", "summary": "...", "evidence": ["..."], "confidence": 0.0, "needs_human_review": true}}
"""
    response = client.models.generate_content(model="gemini-3.8-flash", contents=prompt)
    raw = response.text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").replace("json", "", 1).strip()
    parsed = json.loads(raw)

    try:
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0

    evidence = parsed.get("evidence") or []
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(item)[:500] for item in evidence[:8]]

    return {
        "model_name": "citizen-feedback-gemini-classifier",
        "model_version": "1.0.0",
        "taxonomy_version": "1.0",
        "detected_language": language_code,
        "feedback_type": _coerce_enum(parsed.get("feedback_type"), PARTNER_FEEDBACK_TYPES),
        "category": _coerce_enum(parsed.get("category"), PARTNER_CATEGORIES),
        "severity": _coerce_enum(parsed.get("severity"), PARTNER_LEVELS),
        "urgency": _coerce_enum(parsed.get("urgency"), PARTNER_LEVELS),
        "sentiment": _coerce_enum(parsed.get("sentiment"), PARTNER_SENTIMENTS),
        "summary": str(parsed.get("summary", ""))[:500],
        "evidence": evidence,
        "confidence": confidence,
        "needs_human_review": bool(parsed.get("needs_human_review", True)),
    }

# ---------- ASR ----------
def get_audio_content_type(fname):
    ext = fname.lower().rsplit(".", 1)[-1]
    mapping = {
        "ogg": "audio/ogg", "mp3": "audio/mpeg", "wav": "audio/wav",
        "m4a": "audio/x-m4a", "mp4": "audio/mp4", "aac": "audio/aac",
        "opus": "audio/opus", "flac": "audio/flac", "amr": "audio/amr",
        "webm": "audio/webm",
    }
    return mapping.get(ext, "application/octet-stream")

def transcribe_sarvam(wav_path, lang_code):
    url = "https://api.sarvam.ai/speech-to-text"
    headers = {"api-subscription-key": SARVAM_KEY}
    lang_map = {
        "pa": "pa-IN", "kn": "kn-IN", "or": "or-IN", "as": "as-IN",
        "kok": "kok-IN", "mai": "mai-IN", "sd": "sd-IN", "ks": "ks-IN",
        "mni": "mni-IN", "sat": "sat-IN", "brx": "brx-IN", "ne": "ne-IN",
        "doi": "doi-IN",
    }
    content_type = get_audio_content_type(wav_path)
    with open(wav_path, "rb") as f:
        files = {"file": (wav_path, f, content_type)}
        data = {"language_code": lang_map.get(lang_code, "hi-IN"), "model": "saaras:v4"}
        resp = requests.post(url, headers=headers, files=files, data=data)
    resp.raise_for_status()
    return resp.json().get("transcript", "")

INDICCONFORMER_LANGS = {"hi", "mr", "bn", "gu", "sa", "ta", "te", "ml", "ur"}

LANG_NAMES = {
    "hi": "Hindi", "mr": "Marathi", "bn": "Bengali", "gu": "Gujarati",
    "sa": "Sanskrit", "ta": "Tamil", "te": "Telugu", "ml": "Malayalam", "ur": "Urdu",
    "pa": "Punjabi", "kn": "Kannada", "or": "Odia", "as": "Assamese",
    "kok": "Konkani", "mai": "Maithili", "sd": "Sindhi", "ks": "Kashmiri",
    "mni": "Manipuri", "sat": "Santali", "brx": "Bodo", "ne": "Nepali", "doi": "Dogri",
}

# ---------- Logging for the policymaker dashboard ----------
LOG_FILE = "requests_log.csv"

def log_request(language, asr_engine, transcript, category, priority, reply):
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                ["timestamp", "language", "asr_engine", "transcript", "category", "priority", "reply"]
            )
        writer.writerow(
            [datetime.utcnow().isoformat(), language, asr_engine, transcript, category, priority, reply]
        )

# ---------- Full pipeline ----------
def process_request(wav_path, lang_code):
    lang_name = LANG_NAMES.get(lang_code, lang_code)

    if lang_code in INDICCONFORMER_LANGS:
        wav, sr = torchaudio.load(wav_path)
        wav = torch.mean(wav, dim=0, keepdim=True)
        if sr != 16000:
            wav = torchaudio.transforms.Resample(orig_freq=sr, new_freq=16000)(wav)
        transcript = model(wav, lang_code, "ctc")
        asr_engine = "IndicConformer"
    else:
        transcript = transcribe_sarvam(wav_path, lang_code)
        asr_engine = "Sarvam AI"

    result = understand_and_reply(transcript, lang_name)
    result["transcript"] = transcript
    result["language"] = lang_name
    result["asr_engine"] = asr_engine

    log_request(
        language=lang_name,
        asr_engine=asr_engine,
        transcript=transcript,
        category=result["category"],
        priority=result["priority"],
        reply=result["reply"],
    )
    return result

print("Pipeline ready.")

# ---------- Gradio UI ----------
LANG_OPTIONS = list(LANG_NAMES.items())

def gradio_handler(audio_path, lang_code):
    if audio_path is None:
        return "Please record or upload audio.", "", "", ""
    try:
        result = process_request(audio_path, lang_code)
        return (
            result["transcript"],
            result["category"],
            result["priority"],
            result["reply"]
        )
    except Exception as e:
        return f"Error: {e}", "", "", ""

with gr.Blocks(title="Citizen Voice Assistant") as demo:
    gr.Markdown("# 🗣️ Multilingual Citizen Feedback Assistant")
    gr.Markdown("Speak or upload your request in your language. Get a response, and it's logged for policymakers.")

    with gr.Row():
        with gr.Column():
            lang_dropdown = gr.Dropdown(
                choices=[(name, code) for code, name in LANG_OPTIONS],
                label="Select your language",
                value="hi"
            )
            audio_input = gr.Audio(sources=["microphone", "upload"], type="filepath", label="Speak or upload")
            submit_btn = gr.Button("Submit", variant="primary")
        with gr.Column():
            transcript_out = gr.Textbox(label="What we heard (transcript)")
            category_out = gr.Textbox(label="Category")
            priority_out = gr.Textbox(label="Priority")
            reply_out = gr.Textbox(label="Response", lines=4)

    submit_btn.click(
        gradio_handler,
        inputs=[audio_input, lang_dropdown],
        outputs=[transcript_out, category_out, priority_out, reply_out]
    )

# ---------- FastAPI wrapper: partner-backend API + mounted Gradio UI ----------
api = FastAPI(title="Citizen Feedback ASR + NLP service")

@api.post("/v1/classify")
def v1_classify(payload: dict):
    """Contract expected by the partner backend's HttpNlpClient
    (backend/app/clients/nlp.py): POST {feedback_id, text, language, taxonomy_version}
    -> ClassificationProposal JSON. Configure their service with
    APP_NLP_MODE=http and APP_NLP_BASE_URL=<this service's URL>.
    """
    text = (payload.get("text") or "").strip()
    language = payload.get("language", "hi")
    if not text:
        raise HTTPException(status_code=422, detail="text is required")
    try:
        return classify_for_partner(text, language)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"classification failed: {e}")

app = gr.mount_gradio_app(api, demo, path="/")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
