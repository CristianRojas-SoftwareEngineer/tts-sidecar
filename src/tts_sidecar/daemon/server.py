"""
Servidor FastAPI del daemon de tts-sidecar.
Expone endpoints HTTP para síntesis TTS con el modelo persistente en memoria.
"""

import base64
import gc
import logging
import os
import queue
import threading

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from .. import voices
from .protocol import (
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
    ProgressEvent,
    ResultEvent,
    ErrorEvent,
)


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


def _clear_model_memory():
    """Libera la caché CUDA fragmentada y fuerza GC tras cada síntesis.

    Esta rutina es segura y multiplataforma:
    - `torch.cuda.empty_cache()` es un no-op si no hay dispositivo CUDA disponible
    - `gc.collect()` funciona universalmente (CPU/CUDA/MPS y todos los SO)
    - El import de `torch` es diferido y está protegido por ImportError para
      que la rutina sea inocua incluso si `torch` no está disponible

    La limpieza se ejecuta en el hilo worker tras cada síntesis (éxito o error),
    previniendo la fragmentación de memoria del daemon bajo uso prolongado en GPU.
    """
    try:
        import torch
        torch.cuda.empty_cache()
    except ImportError:
        pass  # torch no disponible: nada que limpiar
    finally:
        gc.collect()


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


# Serializa la síntesis completa (preparación de conds + generate): engine.speak
# muta estado global del modelo (tts.conds) y dos peticiones concurrentes
# cruzarían voces.
_synthesis_lock = threading.Lock()

# Control de admisión: sin tope, una ráfaga de invocaciones concurrentes
# lanza un thread worker por petición que se apila esperando _synthesis_lock,
# saturando el proceso bajo el GIL. El semáforo acota la admisión a 1 síntesis
# activa + hasta 3 en espera; la N+1 se rechaza con 503 antes de crear thread.
MAX_INFLIGHT_SYNTHESIS = 4
_admission_semaphore = threading.BoundedSemaphore(MAX_INFLIGHT_SYNTHESIS)


def _validate_audio_path(path: str, field: str, allowed_dirs: list[str]) -> str:
    """Valida y canoniza una ruta de audio de entrada del daemon.

    Devuelve ``os.path.realpath(path)`` (ruta canónica, resuelta una sola vez)
    si la ruta:
      - tiene extensión ``.wav`` (case-insensitive) y es un archivo existente,
      - queda contenida en alguno de ``allowed_dirs`` (contención vía realpath
        para evitar escapes por symlink, WARNING-02), y
      - es un WAV válido (header RIFF/WAVE de 12 bytes).

    En cualquier otro caso lanza ``HTTPException(400)`` con un ``detail`` que
    no expone rutas del sistema. El caller (``synthesize``) reusa el realpath
    devuelto para pasarlo al engine, cerrando la ventana de symlink swap.
    """
    if not path.lower().endswith(".wav") or not os.path.isfile(path):
        raise HTTPException(
            status_code=400,
            detail=f"{field}: se requiere una ruta a un archivo .wav existente",
        )
    real_path = os.path.realpath(path)
    if not any(real_path == d or real_path.startswith(d + os.sep) for d in allowed_dirs):
        raise HTTPException(
            status_code=400,
            detail=f"{field}: la ruta no está en un directorio permitido",
        )
    try:
        with open(real_path, "rb") as f:
            header = f.read(12)
    except OSError:
        header = b""
    if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise HTTPException(
            status_code=400,
            detail=f"{field}: el archivo no es un WAV válido",
        )
    return real_path


@app.post("/synthesize")
def synthesize(req: SynthesizeRequest) -> StreamingResponse:
    """
    Sintetiza texto a audio usando el modelo cacheado en memoria.

    Endpoint síncrono (def): FastAPI lo despacha a su threadpool, de modo que
    una síntesis larga no bloquea el event loop y /health sigue respondiendo.

    Devuelve un flujo NDJSON (application/x-ndjson): N líneas `progress` con el
    avance de la síntesis (etapa y conteo de tokens del T3 en vivo) seguidas de
    una línea `result` con el WAV en base64 y los tiempos por sub-etapa; si la
    síntesis falla en el hilo worker, se emite una línea `error`. El esquema de
    cada línea lo define protocol.py (ProgressEvent/ResultEvent/ErrorEvent).

    La validación de rutas de audio ocurre ANTES de arrancar la síntesis: un
    400/503 de validación sigue siendo una respuesta de error inmediata (no un
    frame del stream).
    """
    if not _engine:
        raise HTTPException(status_code=503, detail="Modelo no cargado")

    # Valida las rutas de audio antes de que lleguen a librosa.load: deben
    # existir, ser .wav y quedar contenidas en un directorio permitido
    # (WARNING-02: sin esto, cualquier proceso local podía hacer que el daemon
    # leyera un .wav arbitrario del sistema de archivos). Los mensajes de error
    # no exponen rutas del sistema.
    allowed_dirs = [os.path.realpath(d) for d in voices.allowed_audio_dirs()]
    # Cada ruta se resuelve a su forma canónica UNA sola vez dentro de
    # _validate_audio_path y esa misma ruta (no la cruda de la petición) es la
    # que se pasa a _engine.speak: sin esto, quedaba una ventana entre validar
    # y usar en la que el archivo podía cambiar (symlink swap) sin volver a
    # pasar por la validación (WARNING-02).
    real_paths: dict[str, str] = {}
    for field, path in (("voice_audio", req.voice_audio), ("speech_audio", req.speech_audio)):
        if path is None:
            continue
        real_paths[field] = _validate_audio_path(path, field, allowed_dirs)

    # Admisión no bloqueante: si ya hay MAX_INFLIGHT_SYNTHESIS peticiones en
    # vuelo, se rechaza de inmediato en vez de apilar otro thread worker.
    if not _admission_semaphore.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Daemon ocupado (demasiadas síntesis concurrentes), reintente en unos segundos",
        )

    # Patrón productor/consumidor: la síntesis (CPU-bound y bloqueante) corre en
    # un hilo worker que empuja eventos a una cola; el generador de la respuesta
    # los drena como líneas NDJSON hasta un centinela. Así el progreso viaja al
    # cliente mientras el T3/S3Gen siguen trabajando, sin bloquear el event loop.
    def event_stream():
        q: queue.Queue = queue.Queue()
        SENTINEL = object()

        def worker():
            try:
                # La síntesis sigue serializada (una a la vez): engine.speak muta
                # estado global del modelo (tts.conds) y dos síntesis concurrentes
                # cruzarían voces. /health responde igual (endpoint aparte).
                with _synthesis_lock:
                    def push(ev: dict):
                        q.put(("progress", ev))

                    audio_bytes = _engine.speak(
                        text=req.text,
                        voice_audio=real_paths.get("voice_audio"),
                        speech_audio=real_paths.get("speech_audio"),
                        verbose=True,
                        progress_callback=push,
                    )
                    timing = getattr(_engine, "_synthesis_timing", {})
                    q.put((
                        "result",
                        {
                            "audio_b64": base64.b64encode(audio_bytes).decode("ascii"),
                            "t3_time": float(timing.get("t3", 0.0) or 0.0),
                            "s3gen_time": float(timing.get("s3gen", 0.0) or 0.0),
                        },
                    ))
            except FileNotFoundError as e:
                # El detalle real (con rutas) queda solo en el log del servidor.
                logging.getLogger(__name__).warning("synthesize: recurso no encontrado: %s", e)
                q.put(("error", {"detail": "Recurso de voz no encontrado"}))
            except Exception as e:
                logging.getLogger(__name__).error("synthesize: error interno: %s", e)
                q.put(("error", {"detail": "Error interno de síntesis"}))
            finally:
                _clear_model_memory()
                _admission_semaphore.release()
                q.put((SENTINEL, None))

        t = threading.Thread(target=worker, daemon=True)
        t.start()

        while True:
            kind, payload = q.get()
            if kind is SENTINEL:
                break
            if kind == "progress":
                yield ProgressEvent(
                    stage=payload.get("stage"),
                    tokens=payload.get("tokens"),
                    elapsed=payload.get("elapsed"),
                ).model_dump_json() + "\n"
            elif kind == "result":
                yield ResultEvent(**payload).model_dump_json() + "\n"
            elif kind == "error":
                yield ErrorEvent(**payload).model_dump_json() + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


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

    Libera la referencia global al engine y fuerza la misma limpieza de
    memoria (`_clear_model_memory`) que corre tras cada síntesis (S3-04,
    a50fc6d): sin esto, un auto-restart frecuente del daemon podía dejar
    memoria GPU retenida entre reinicios porque nada liberaba `_engine` en el
    apagado. Simétrico por diseño: mismo helper, mismas garantías (no-op sin
    CUDA, gc.collect() incondicional).

    Riesgo aceptado (SUGGESTION-02): no lleva token ni confirmación explícita.
    El daemon bindea exclusivamente a 127.0.0.1 (ver run.py), por lo que solo
    un proceso con acceso local a la máquina puede invocarlo; se acepta ese
    riesgo residual en vez de añadir un secreto que el propio cliente IPC
    tendría que gestionar y persistir.
    """
    global _engine

    if _server is not None:
        _server.should_exit = True
        # Libera la referencia al engine (permite al GC recolectar los
        # tensores/modelos que retiene) y limpia la caché CUDA fragmentada,
        # igual que al final de cada síntesis.
        _engine = None
        _clear_model_memory()
        return {"status": "shutting_down"}
    # Sin instancia registrada (no debería ocurrir): el kill por PID es la red de seguridad.
    raise HTTPException(status_code=503, detail="Servidor no disponible para apagado graceful")
