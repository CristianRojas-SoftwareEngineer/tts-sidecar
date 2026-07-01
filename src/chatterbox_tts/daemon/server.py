"""
Servidor FastAPI del daemon de tts-sidecar.
Expone endpoints HTTP para síntesis TTS con el modelo persistente en memoria.
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


# TODO: get_socket_path es un residuo del diseño original basado en Unix sockets.
# El servidor usa HTTP/TCP (puerto 8765) en todas las plataformas; esta función
# ya no se invoca desde ningún lugar del código.
def get_socket_path() -> str:
    """Devuelve la ruta de socket apropiada para la plataforma (sin uso activo)."""
    system = platform.system()

    if system == "Windows":
        return r"\\.\pipe\tts-sidecar-daemon"
    else:
        sock_dir = os.getenv('XDG_RUNTIME_DIR') or tempfile.gettempdir()
        return os.path.join(sock_dir, "tts-sidecar-daemon.sock")


# Estado global (asignado por run.py antes de arrancar uvicorn)
_engine = None
_start_time = None
_server = None


def set_engine(engine):
    """Asigna la instancia global del engine."""
    global _engine
    _engine = engine


def set_server(server):
    """Registra la instancia de uvicorn.Server para permitir el apagado graceful."""
    global _server
    _server = server


def set_start_time(timestamp: float):
    """Registra el timestamp de inicio del servidor."""
    global _start_time
    _start_time = timestamp


# Aplicación FastAPI
app = FastAPI(
    title="tts-sidecar-daemon",
    description="Daemon TTS persistente con modelo cacheado en memoria",
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Endpoint de health check."""
    import time
    return HealthResponse(
        status="healthy" if _engine else "initializing",
        model_loaded=_engine is not None,
        uptime_seconds=time.time() - _start_time if _start_time else 0,
    )


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest) -> Response:
    """
    Sintetiza texto a audio usando el modelo cacheado en memoria.

    Devuelve el audio como binario WAV.
    """
    if not _engine:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

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
    """Lista las voces registradas."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    return VoicesResponse(voices=_engine.list_voices())


@app.post("/shutdown")
async def shutdown():
    """Endpoint de cierre graceful del daemon.

    Señaliza `should_exit` sobre la instancia de uvicorn.Server para que el
    servidor termine su ciclo de vida de forma ordenada. Se responde antes de
    que uvicorn cierre: el flag se procesa en la siguiente iteración del loop.
    """
    if _server is not None:
        _server.should_exit = True
        return {"status": "shutting_down"}
    # Sin instancia registrada (no debería ocurrir): el kill por PID es la red de seguridad.
    raise HTTPException(status_code=503, detail="Servidor no disponible para apagado graceful")
