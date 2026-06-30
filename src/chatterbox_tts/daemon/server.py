"""
FastAPI server for tts-sidecar daemon.
Provides HTTP endpoints for TTS synthesis with persistent model.
"""

import platform
import tempfile
import os

from fastapi import FastAPI, HTTPException, Response

from .protocol import (
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
)


def get_socket_path() -> str:
    """Get platform-appropriate socket path for IPC."""
    system = platform.system()

    if system == "Windows":
        return r"\\.\pipe\tts-sidecar-daemon"
    else:
        sock_dir = os.getenv('XDG_RUNTIME_DIR') or tempfile.gettempdir()
        return os.path.join(sock_dir, "tts-sidecar-daemon.sock")


# Global state (set by run.py)
_engine = None
_start_time = None


def set_engine(engine):
    """Set the global engine instance."""
    global _engine
    _engine = engine


def set_start_time(timestamp: float):
    """Set the server start time."""
    global _start_time
    _start_time = timestamp


# FastAPI application
app = FastAPI(
    title="tts-sidecar-daemon",
    description="Persistent TTS daemon with cached model",
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    import time
    return HealthResponse(
        status="healthy" if _engine else "initializing",
        model_loaded=_engine is not None,
        uptime_seconds=time.time() - _start_time if _start_time else 0,
    )


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest) -> Response:
    """
    Synthesize text to audio via the cached model.

    Returns audio as WAV binary.
    """
    if not _engine:
        raise HTTPException(status_code=503, detail="Model not loaded")

    try:
        audio_bytes = _engine.speak(
            text=req.text,
            voice_audio=req.voice_audio,
            speech_audio=req.speech_audio,
            verbose=True,
        )

        timing = getattr(_engine, '_synthesis_timing', {})
        headers = {
            "Content-Disposition": "attachment; filename=synth.wav",
            "X-T3-Time": f"{timing.get('t3', 0):.1f}",
            "X-S3Gen-Time": f"{timing.get('s3gen', 0):.1f}",
        }

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers=headers,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices", response_model=VoicesResponse)
async def list_voices():
    """List registered voices."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Model not loaded")

    return VoicesResponse(voices=_engine.list_voices())


@app.post("/shutdown")
async def shutdown():
    """Graceful shutdown endpoint."""
    raise HTTPException(status_code=200, detail="Shutting down")
