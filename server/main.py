from __future__ import annotations

import io, json, os, re, tempfile, threading, unicodedata
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from .vieneu_adapter import VieNeuAdapter

APP_NAME = "AIRI Vietnamese Speech"
MODEL_ID = "vieneu-tts-v3-turbo"
API_KEY = os.getenv("AIRI_SPEECH_API_KEY", "airi-local")
DATA_DIR = Path.home() / ".airi-vietnamese-speech"
VOICE_DIR = DATA_DIR / "voices"
VOICE_DB = DATA_DIR / "voices.json"
VOICE_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title=APP_NAME, version="0.1.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_credentials=False,
    allow_methods=["*"], allow_headers=["*"]
)

engine = None
stt_engine = None
lock = threading.RLock()
last_airi_request = None

class SpeechRequest(BaseModel):
    model: str = MODEL_ID
    input: str = Field(min_length=1)
    voice: str = "ngoc-linh"
    response_format: str = "wav"
    speed: float = 1.0
    style: str = "tu_nhien"

def load_db():
    if not VOICE_DB.exists():
        return {}
    try:
        return json.loads(VOICE_DB.read_text(encoding="utf-8"))
    except Exception:
        return {}

voices = load_db()

def save_db():
    VOICE_DB.write_text(
        json.dumps(voices, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

def auth(authorization: Optional[str]):
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "Invalid API key")


def note_airi_request(endpoint: str, user_agent: Optional[str], ui_request: Optional[str]):
    """Remember external OpenAI-compatible calls so the desktop UI can show AIRI status."""
    global last_airi_request
    if ui_request != "1":
        last_airi_request = {"endpoint": endpoint, "user_agent": user_agent or "Unknown client"}

def get_engine():
    global engine
    with lock:
        if engine is None:
            engine = VieNeuAdapter()
            # VieNeu keeps embeddings in memory. Re-register references saved by
            # this app so cloned voices remain available after a server restart.
            for item in voices.values():
                source = Path(item.get("file", ""))
                name = item.get("vieneu_name")
                if name and source.is_file():
                    engine.add_voice(name, str(source))
    return engine

def voice_id(name):
    # VieNeu voice names contain Vietnamese diacritics. Normalize them
    # before creating the stable ASCII slug used by AIRI.
    value = unicodedata.normalize("NFKD", name.lower().strip())
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.replace("đ", "d")
    value = re.sub(r"[^a-z0-9_-]+", "-", value)
    return re.sub(r"-+", "-", value).strip("-")

def _preset_voice_names():
    """Get preset voice names from the actual VieNeu engine."""
    try:
        e = get_engine()
        raw = getattr(getattr(e, "engine", None), "_preset_voices", None)
        if raw is None:
            raw = getattr(e, "_preset_voices", None)

        if isinstance(raw, dict):
            return [str(name) for name in raw.keys()]
        if raw is not None:
            return [str(name) for name in raw]
    except Exception:
        pass
    return []


def vieneu_voice(vid):
    # Cloned voice: resolve to the actual name stored in our DB.
    cloned = voices.get(vid)
    if cloned:
        return cloned["vieneu_name"]

    # Preset voice: AIRI sends a slug such as "truc-ly".
    # Resolve that slug against VieNeu's real installed preset list.
    preset_names = _preset_voice_names()
    for name in preset_names:
        if voice_id(name) == vid:
            return name

    # Also accept an exact VieNeu display name if a caller sends one.
    if vid in preset_names:
        return vid

    available = ", ".join(preset_names) if preset_names else "none"
    raise HTTPException(
        400,
        f"Unknown VieNeu voice '{vid}'. Available preset voices: {available}"
    )

def wav_bytes(audio):
    sample_rate = 48000
    if isinstance(audio, tuple):
        if len(audio) > 1 and isinstance(audio[1], (int, float)):
            sample_rate = int(audio[1])
        audio = audio[0]
    audio = np.asarray(audio).squeeze().astype(np.float32)
    out = io.BytesIO()
    sf.write(out, audio, sample_rate, format="WAV", subtype="PCM_16")
    return out.getvalue()

@app.get("/health")
def health():
    return {"status":"ok","service":APP_NAME,"tts":"ready","model":MODEL_ID}


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(Path(__file__).resolve().parents[1] / "ui" / "index.html")


@app.get("/api/debug/voices")
def debug_voices(authorization: Optional[str] = Header(default=None)):
    """Show the exact VieNeu preset names and their AIRI slugs."""
    auth(authorization)
    names = _preset_voice_names()
    return {
        "voices": [{"id": voice_id(name), "name": name} for name in names],
        "count": len(names),
    }


@app.get("/api/connection-status")
def connection_status(authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    return {
        "server": "ready",
        "base_url": "http://127.0.0.1:23333/v1/",
        "model": MODEL_ID,
        "last_airi_request": last_airi_request,
    }

@app.get("/v1/models")
def models(
    authorization: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_airi_speech_ui: Optional[str] = Header(default=None),
):
    auth(authorization)
    note_airi_request("GET /v1/models", user_agent, x_airi_speech_ui)
    return {"object":"list","data":[
        {"id":MODEL_ID,"object":"model","owned_by":"pnnbao97/VieNeu-TTS"}
    ]}

@app.get("/v1/voices")
def list_voices(
    authorization: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_airi_speech_ui: Optional[str] = Header(default=None),
):
    auth(authorization)
    note_airi_request("GET /v1/voices", user_agent, x_airi_speech_ui)

    # Never use a fake/static preset list. Read the actual VieNeu engine.
    data = [
        {
            "id": voice_id(name),
            "name": name,
            "language": "vi-VN",
            "type": "preset",
        }
        for name in _preset_voice_names()
    ]

    # Cloned voices coexist with VieNeu presets.
    preset_ids = {item["id"] for item in data}
    for vid, item in voices.items():
        if vid not in preset_ids:
            data.append({
                "id": vid,
                "name": item["name"],
                "language": "vi-VN",
                "type": "cloned",
            })

    return {"object": "list", "data": data}

@app.post("/v1/audio/speech")
def speech(
    request: SpeechRequest,
    authorization: Optional[str] = Header(default=None),
    user_agent: Optional[str] = Header(default=None),
    x_airi_speech_ui: Optional[str] = Header(default=None),
):
    auth(authorization)
    note_airi_request("POST /v1/audio/speech", user_agent, x_airi_speech_ui)
    if request.model != MODEL_ID:
        raise HTTPException(400, f"Unsupported model: {request.model}")
    if request.response_format.lower() not in {"wav","wave"}:
        raise HTTPException(400, "Only WAV is supported")
    if not 0.25 <= request.speed <= 4:
        raise HTTPException(400, "speed must be between 0.25 and 4")

    with lock:
        audio = get_engine().synthesize(
            request.input, vieneu_voice(request.voice),
            request.style, request.speed
        )
    return Response(
        wav_bytes(audio), media_type="audio/wav",
        headers={
            "Content-Disposition": 'inline; filename="airi-speech.wav"',
            "X-AIRI-Voice": request.voice,
            "X-AIRI-Model": MODEL_ID,
        }
    )

@app.post("/api/voices/clone")
async def clone_voice(
    name: str = Form(...),
    file: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None)
):
    auth(authorization)
    if not file.filename or not file.filename.lower().endswith(".wav"):
        raise HTTPException(400, "A WAV reference file is required")

    vid = voice_id(name)
    if not vid:
        raise HTTPException(400, "Invalid voice name")

    target = VOICE_DIR / f"{vid}.wav"
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty WAV file")
    target.write_bytes(data)

    try:
        with lock:
            e = get_engine()
            e.add_voice(name, str(target))
            e.save_voices(str(DATA_DIR / "vieneu_voices.json"))
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise HTTPException(500, f"VieNeu voice cloning failed: {exc}")

    voices[vid] = {
        "id":vid, "name":name, "vieneu_name":name, "file":str(target)
    }
    save_db()
    return {"ok":True,"voice":{
        "id":vid,"name":name,"language":"vi-VN","type":"cloned"
    }}

@app.delete("/api/voices/{vid}")
def delete_voice(vid: str, authorization: Optional[str] = Header(default=None)):
    auth(authorization)
    item = voices.pop(vid, None)
    if not item:
        raise HTTPException(404, "Voice not found")
    with lock:
        get_engine().remove_voice(item["vieneu_name"])
    Path(item["file"]).unlink(missing_ok=True)
    save_db()
    return {"ok":True,"deleted":vid}


@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("vi"),
    task: str = Form("transcribe"),
    authorization: Optional[str] = Header(default=None),
):
    """Optional local STT endpoint, backed by faster-whisper on first use."""
    auth(authorization)
    if task not in {"transcribe", "translate"}:
        raise HTTPException(400, "task must be transcribe or translate")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty audio file")
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            temp.write(data)
            temp_path = temp.name
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise HTTPException(503, "STT is unavailable. Install faster-whisper first.") from exc
        global stt_engine
        with lock:
            if stt_engine is None:
                # "auto" can select CUDA merely because a GPU is visible, then
                # fail on machines without the matching CUDA DLLs. CPU INT8 is
                # portable and needs no NVIDIA/CUDA installation.
                stt_engine = WhisperModel(
                    os.getenv("AIRI_STT_MODEL", "base"),
                    device="cpu",
                    compute_type="int8",
                )
        segments, info = stt_engine.transcribe(temp_path, language=language or None, task=task)
        text = "".join(segment.text for segment in segments).strip()
        return {"text": text, "language": info.language, "duration": info.duration}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Transcription failed: {exc}") from exc
    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=23333)
