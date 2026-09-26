from __future__ import annotations

import io
import json
import os
import re
import sys
import threading
import time
import unicodedata
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .vieneu_adapter import VieNeuAdapter

APP_NAME = "AIRI Vietnamese Speech"
APP_VERSION = "0.2.0"
TTS_MODEL_ID = "vieneu-tts-v3-turbo"
STT_MODEL_ID = os.getenv("AIRI_STT_MODEL", "base")
STT_PUBLIC_MODEL_ID = f"faster-whisper-{STT_MODEL_ID}"
API_KEY = os.getenv("AIRI_SPEECH_API_KEY", "airi-local")
if os.getenv("AIRI_SPEECH_DATA_DIR"):
    DATA_DIR = Path(os.environ["AIRI_SPEECH_DATA_DIR"])
elif getattr(sys, "frozen", False):
    # Portable build keeps its state beside the executable. This avoids profile
    # permission problems and makes the whole folder movable between computers.
    DATA_DIR = Path(sys.executable).resolve().parent / "data"
else:
    DATA_DIR = Path.home() / ".airi-vietnamese-speech"
VOICE_DIR = DATA_DIR / "voices"
VOICE_DB = DATA_DIR / "voices.json"
VOICE_DIR.mkdir(parents=True, exist_ok=True)
MODEL_STATE_DIR = DATA_DIR / "model-state"
MODEL_STATE_DIR.mkdir(parents=True, exist_ok=True)
TTS_READY_MARKER = MODEL_STATE_DIR / "vieneu-v3-turbo.ready"
STT_READY_MARKER = MODEL_STATE_DIR / f"faster-whisper-{STT_MODEL_ID}.ready"
FORCE_OFFLINE = os.getenv("AIRI_FORCE_OFFLINE", "0") == "1"

# After both engines have completed once, prevent Hugging Face from making even
# metadata/HEAD requests. If the selected STT model changes, its marker changes too.
OFFLINE_MODE = FORCE_OFFLINE or (TTS_READY_MARKER.exists() and STT_READY_MARKER.exists())
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
if OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
MAX_TTS_CHARS = int(os.getenv("AIRI_MAX_TTS_CHARS", "5000"))
MAX_AUDIO_BYTES = int(os.getenv("AIRI_MAX_AUDIO_MB", "50")) * 1024 * 1024

# Local metadata makes voice discovery instant: no model load just to fill a menu.
PRESET_VOICES = (
    ("Minh Đức", "Nam · Bắc · Tin tức"), ("Phạm Tuyên", "Nam · Bắc · Tự nhiên"),
    ("Thái Sơn", "Nam · Nam · Kể chuyện"), ("Xuân Vĩnh", "Nam · Nam · Tự nhiên"),
    ("Thanh Bình", "Nam · Bắc · Kể chuyện"), ("Trúc Ly", "Nữ · Bắc · Tự nhiên"),
    ("Ngọc Linh", "Nữ · Bắc · Kể chuyện"), ("Đoan Trang", "Nữ · Bắc · Tự nhiên"),
    ("Mai Anh", "Nữ · Bắc · Tin tức"), ("Thục Đoan", "Nữ · Nam · Kể chuyện"),
    ("Minh Triết", "Nam · Nam · Tin tức"), ("Thùy Dung", "Nữ · Nam · Tin tức"),
    ("Quang Sơn", "Nam · Trung · Tự nhiên"), ("Ngọc Trân", "Nữ · Trung · Tự nhiên"),
)


def voice_id(name: str) -> str:
    value = unicodedata.normalize("NFKD", name.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch)).replace("đ", "d")
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9_-]+", "-", value)).strip("-")


PRESET_BY_ID = {voice_id(name): name for name, _ in PRESET_VOICES}


class SpeechRequest(BaseModel):
    model: str = TTS_MODEL_ID
    input: str = Field(min_length=1, max_length=MAX_TTS_CHARS)
    voice: str = "truc-ly"
    response_format: str = "wav"
    speed: float = Field(default=1.0, ge=0.25, le=4.0)
    style: str = "tu_nhien"


def load_db() -> dict:
    try:
        value = json.loads(VOICE_DB.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


voices = load_db()
engine: Optional[VieNeuAdapter] = None
stt_engine = None
_tts_init_lock = threading.RLock()
_stt_init_lock = threading.RLock()
_tts_inference_lock = threading.Lock()
_stt_inference_lock = threading.Lock()
_state_lock = threading.Lock()
_state = {"tts": "idle", "stt": "idle", "tts_error": None, "stt_error": None}
last_airi_request = None


def set_state(component: str, value: str, error: Optional[str] = None) -> None:
    with _state_lock:
        _state[component] = value
        _state[f"{component}_error"] = error


def save_db() -> None:
    temp = VOICE_DB.with_suffix(".tmp")
    temp.write_text(json.dumps(voices, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(VOICE_DB)


def auth(authorization: Optional[str]) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Invalid API key")


def note_airi_request(endpoint: str, user_agent: Optional[str], ui_request: Optional[str]) -> None:
    global last_airi_request
    if ui_request != "1":
        last_airi_request = {"endpoint": endpoint, "user_agent": user_agent or "Unknown client", "at": time.time()}


def get_engine() -> VieNeuAdapter:
    global engine
    if engine is not None:
        return engine
    with _tts_init_lock:
        if engine is None:
            set_state("tts", "loading")
            try:
                instance = VieNeuAdapter()
                for item in voices.values():
                    source, name = Path(item.get("file", "")), item.get("vieneu_name")
                    if name and source.is_file():
                        instance.add_voice(name, str(source))
                engine = instance
                TTS_READY_MARKER.write_text(APP_VERSION, encoding="ascii")
                set_state("tts", "ready")
            except Exception as exc:
                if OFFLINE_MODE:
                    TTS_READY_MARKER.unlink(missing_ok=True)
                set_state("tts", "error", str(exc))
                raise
    return engine


def get_stt_engine():
    global stt_engine
    if stt_engine is not None:
        return stt_engine
    with _stt_init_lock:
        if stt_engine is None:
            set_state("stt", "loading")
            try:
                from faster_whisper import WhisperModel
                stt_engine = WhisperModel(
                    STT_MODEL_ID,
                    device="cpu",
                    compute_type="int8",
                    local_files_only=OFFLINE_MODE or STT_READY_MARKER.exists(),
                )
                STT_READY_MARKER.write_text(APP_VERSION, encoding="ascii")
                set_state("stt", "ready")
            except Exception as exc:
                if OFFLINE_MODE:
                    STT_READY_MARKER.unlink(missing_ok=True)
                set_state("stt", "error", str(exc))
                raise
    return stt_engine


def prepare_models() -> None:
    """First launch downloads both engines; later launches are cache-only."""
    for loader in (get_engine, get_stt_engine):
        try:
            loader()
        except Exception:
            pass  # The UI reports errors; a failed download must not close the app.


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("AIRI_PRELOAD_MODELS", "1") != "0":
        threading.Thread(target=prepare_models, name="airi-model-setup", daemon=True).start()
    yield


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


def vieneu_voice(vid: str) -> str:
    if vid in voices:
        return voices[vid]["vieneu_name"]
    if vid in PRESET_BY_ID:
        return PRESET_BY_ID[vid]
    if vid in PRESET_BY_ID.values():
        return vid
    raise HTTPException(400, f"Unknown voice '{vid}'")


def wav_bytes(audio) -> bytes:
    import numpy as np
    import soundfile as sf
    sample_rate = 48000
    if isinstance(audio, tuple):
        if len(audio) > 1 and isinstance(audio[1], (int, float)):
            sample_rate = int(audio[1])
        audio = audio[0]
    out = io.BytesIO()
    sf.write(out, np.asarray(audio).squeeze().astype(np.float32), sample_rate, format="WAV", subtype="PCM_16")
    return out.getvalue()


def synthesize(request: SpeechRequest) -> bytes:
    with _tts_inference_lock:  # Protect the shared native ONNX session.
        result = get_engine().synthesize(request.input, vieneu_voice(request.voice), request.style, request.speed)
        return wav_bytes(result)


def transcribe_audio(data: bytes, filename: str, language: str, task: str):
    audio = io.BytesIO(data)
    audio.name = f"audio{Path(filename).suffix or '.wav'}"
    with _stt_inference_lock:
        segments, info = get_stt_engine().transcribe(
            audio, language=language or None, task=task, vad_filter=True, beam_size=1,
            condition_on_previous_text=False,
        )
        return "".join(segment.text for segment in segments).strip(), info


async def read_audio(file: UploadFile) -> bytes:
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if not data:
        raise HTTPException(400, "Empty audio file")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, f"Audio file is larger than {MAX_AUDIO_BYTES // 1024 // 1024} MB")
    return data


@app.get("/health")
def health():
    with _state_lock:
        state = dict(_state)
    return {"status": "ok", "service": APP_NAME, "version": APP_VERSION,
            "models": {"tts": TTS_MODEL_ID, "stt": STT_PUBLIC_MODEL_ID},
            "offline": OFFLINE_MODE,
            "cache_ready": TTS_READY_MARKER.exists() and STT_READY_MARKER.exists(),
            "engines": state}


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(Path(__file__).resolve().parents[1] / "ui" / "index.html")


@app.get("/api/connection-status")
def connection_status(authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    with _state_lock:
        state = dict(_state)
    return {"server": "ready", "base_url": "http://127.0.0.1:23333/v1", "tts_model": TTS_MODEL_ID,
            "stt_model": "whisper", "offline": OFFLINE_MODE,
            "cache_ready": TTS_READY_MARKER.exists() and STT_READY_MARKER.exists(),
            "engines": state, "last_airi_request": last_airi_request}


@app.get("/api/debug/voices")
def debug_voices(authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    return {"voices": [{"id": vid, "name": name} for vid, name in PRESET_BY_ID.items()]}


@app.post("/api/models/preload/{component}")
async def preload_model(component: str, authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    if component == "tts":
        await run_in_threadpool(get_engine)
    elif component == "stt":
        await run_in_threadpool(get_stt_engine)
    else:
        raise HTTPException(404, "component must be tts or stt")
    return {"ok": True, "component": component, "state": "ready"}


@app.get("/v1/models")
def models(authorization: Optional[str] = Header(default=None), user_agent: Optional[str] = Header(default=None),
           x_airi_speech_ui: Optional[str] = Header(default=None)):
    auth(authorization); note_airi_request("GET /v1/models", user_agent, x_airi_speech_ui)
    return {"object": "list", "data": [
        {"id": TTS_MODEL_ID, "object": "model", "owned_by": "pnnbao97/VieNeu-TTS"},
        {"id": STT_PUBLIC_MODEL_ID, "object": "model", "owned_by": "SYSTRAN/faster-whisper"},
        {"id": "whisper-1", "object": "model", "owned_by": "local-alias"},
        {"id": "whisper", "object": "model", "owned_by": "local-alias"},
    ]}


@app.get("/v1/voices")
def list_voices(authorization: Optional[str] = Header(default=None), user_agent: Optional[str] = Header(default=None),
                x_airi_speech_ui: Optional[str] = Header(default=None)):
    auth(authorization); note_airi_request("GET /v1/voices", user_agent, x_airi_speech_ui)
    descriptions = dict(PRESET_VOICES)
    data = [{"id": vid, "name": name, "description": descriptions[name], "language": "vi-VN", "type": "preset"}
            for vid, name in PRESET_BY_ID.items()]
    preset_ids = {item["id"] for item in data}
    data.extend({"id": vid, "name": item["name"], "language": "vi-VN", "type": "cloned"}
                for vid, item in voices.items() if vid not in preset_ids)
    return {"object": "list", "data": data}


@app.post("/v1/audio/speech")
async def speech(request: SpeechRequest, authorization: Optional[str] = Header(default=None),
                 user_agent: Optional[str] = Header(default=None), x_airi_speech_ui: Optional[str] = Header(default=None)):
    auth(authorization); note_airi_request("POST /v1/audio/speech", user_agent, x_airi_speech_ui)
    if request.model != TTS_MODEL_ID:
        raise HTTPException(400, f"Unsupported TTS model: {request.model}")
    if request.response_format.lower() not in {"wav", "wave"}:
        raise HTTPException(400, "Only WAV is supported")
    try:
        audio = await run_in_threadpool(synthesize, request)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Speech synthesis failed: {exc}") from exc
    return Response(audio, media_type="audio/wav", headers={"Content-Disposition": 'inline; filename="airi-speech.wav"',
                    "X-AIRI-Voice": request.voice, "X-AIRI-Model": TTS_MODEL_ID})


async def perform_transcription(file: UploadFile, model: str, language: str, task: str, response_format: str):
    if model not in {STT_PUBLIC_MODEL_ID, STT_MODEL_ID, "whisper-1", "whisper"}:
        raise HTTPException(400, f"Unsupported STT model: {model}")
    if task not in {"transcribe", "translate"}:
        raise HTTPException(400, "task must be transcribe or translate")
    data = await read_audio(file)
    try:
        text, info = await run_in_threadpool(transcribe_audio, data, file.filename or "audio.wav", language, task)
    except Exception as exc:
        raise HTTPException(500, f"Transcription failed: {exc}") from exc
    if response_format in {"text", "txt"}:
        return PlainTextResponse(text)
    if response_format not in {"json", "verbose_json"}:
        raise HTTPException(400, "response_format must be json, verbose_json, or text")
    payload = {"text": text}
    if response_format == "verbose_json":
        payload.update({"language": info.language, "duration": info.duration})
    return JSONResponse(payload)


@app.post("/v1/audio/transcriptions")
async def openai_transcription(file: UploadFile = File(...), model: str = Form("whisper-1"),
                               language: str = Form("vi"), response_format: str = Form("json"),
                               authorization: Optional[str] = Header(default=None),
                               user_agent: Optional[str] = Header(default=None),
                               x_airi_speech_ui: Optional[str] = Header(default=None)):
    """OpenAI-compatible endpoint used by AIRI Settings -> Hearing."""
    auth(authorization); note_airi_request("POST /v1/audio/transcriptions", user_agent, x_airi_speech_ui)
    return await perform_transcription(file, model, language, "transcribe", response_format)


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("vi"), task: str = Form("transcribe"),
                     authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    return await perform_transcription(file, STT_PUBLIC_MODEL_ID, language, task, "verbose_json")


@app.post("/api/voices/clone")
async def clone_voice(name: str = Form(...), file: UploadFile = File(...),
                      authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "A WAV reference file is required")
    vid = voice_id(name)
    if not vid:
        raise HTTPException(400, "Invalid voice name")
    data, target = await read_audio(file), VOICE_DIR / f"{vid}.wav"
    target.write_bytes(data)
    try:
        # Keep the lock inside a worker thread; never block the async event loop.
        def add() -> None:
            with _tts_inference_lock:
                instance = get_engine()
                instance.add_voice(name, str(target))
                instance.save_voices(str(DATA_DIR / "vieneu_voices.json"))
        await run_in_threadpool(add)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(500, f"VieNeu voice cloning failed: {exc}") from exc
    voices[vid] = {"id": vid, "name": name, "vieneu_name": name, "file": str(target)}
    save_db()
    return {"ok": True, "voice": {"id": vid, "name": name, "language": "vi-VN", "type": "cloned"}}


@app.delete("/api/voices/{vid}")
async def delete_voice(vid: str, authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    item = voices.get(vid)
    if not item:
        raise HTTPException(404, "Voice not found")
    def remove() -> None:
        with _tts_inference_lock:
            get_engine().remove_voice(item["vieneu_name"])
    await run_in_threadpool(remove)
    voices.pop(vid, None)
    Path(item["file"]).unlink(missing_ok=True)
    save_db()
    return {"ok": True, "deleted": vid}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=23333)
