"""
Definiciones del protocolo IPC del daemon de tts-sidecar.

`SynthesizeRequest` (el cuerpo del POST /synthesize) NO cambia respecto a la
variante binaria previa. Lo que cambia es la RESPUESTA de `/synthesize`: ahora es
un flujo NDJSON (una línea JSON por evento) en vez de un único cuerpo binario WAV.
El orden garantizado del stream es N×`progress` → 1×`result` (con el WAV en base64),
o bien 1×`error` si la síntesis falla en el hilo worker. El esquema de cada línea
lo definen `ProgressEvent` / `ResultEvent` / `ErrorEvent` (abajo), fuente única de
verdad validada por ambos extremos: `server.py` (productor) emite vía
`model_dump_json()` e `ipc.py` (consumidor) valida cada línea con `model_validate` y
aborta con `DaemonIPCError` ante cualquier frame no conforme (sin tolerancia).
Ver `server.py::synthesize` para el productor y `docs/DAEMON-MODE.md` para el
protocolo completo.
"""

from pydantic import BaseModel, Field
from typing import Literal, Optional

# Tope de texto por petición: acota el trabajo del T3 y evita el DoS local
# trivial de un payload ilimitado.
MAX_TEXT_LENGTH = 5000

# Tope de longitud para las rutas de audio: por encima del límite práctico de
# ruta en los tres SO soportados (Windows MAX_PATH extendido, Linux/macOS
# PATH_MAX), evita payloads desproporcionados antes de que lleguen a la
# validación de directorio permitido de /synthesize.
MAX_AUDIO_PATH_LENGTH = 4096


class SynthesizeRequest(BaseModel):
    """Request de síntesis de habla.

    El daemon sirve un único modelo y compute backend fijados al arrancar; la
    petición no lleva `model` ni `compute_backend` (el servidor los ignoraría).
    """
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_audio: Optional[str] = Field(default=None, max_length=MAX_AUDIO_PATH_LENGTH)
    speech_audio: Optional[str] = Field(default=None, max_length=MAX_AUDIO_PATH_LENGTH)


# ---------------------------------------------------------------------------
# Esquema del stream NDJSON de /synthesize (contrato daemon→cliente).
#
# Cada línea del stream es exactamente uno de estos tres modelos, discriminados
# por el campo `event`. El cliente parsea cada línea, lee `event` y actúa:
#   - "progress": avance de la síntesis (etapa actual y, durante el T3, tokens).
#   - "result":  frame final con el WAV en base64 y los tiempos por sub-etapa.
#   - "error":   la síntesis falló en el hilo worker; el cliente lo convierte en
#                DaemonIPCError (exit 5 en el CLI). No expone rutas del sistema.
# ---------------------------------------------------------------------------


class ProgressEvent(BaseModel):
    """Evento de avance de la síntesis (una línea `progress` del stream)."""
    event: Literal["progress"] = "progress"
    stage: Optional[str] = None
    """Etapa actual: conditionals, tts, t3, s3gen, encoding, saving."""
    tokens: Optional[int] = None
    """Conteo de tokens del T3 en vivo (solo durante la etapa 't3')."""
    elapsed: Optional[float] = None
    """Segundos transcurridos desde el inicio de la síntesis (opcional)."""


class ResultEvent(BaseModel):
    """Frame final del stream: el WAV completo y los tiempos por sub-etapa."""
    event: Literal["result"] = "result"
    audio_b64: str
    """WAV PCM 24kHz mono codificado en base64 (ASCII)."""
    t3_time: float = 0.0
    s3gen_time: float = 0.0


class ErrorEvent(BaseModel):
    """Frame de error del stream: la síntesis falló en el hilo worker."""
    event: Literal["error"] = "error"
    detail: str
    """Mensaje seguro para el cliente (sin rutas del sistema)."""


class HealthResponse(BaseModel):
    """Respuesta del health check."""
    status: str
    """Estado del daemon: 'healthy', 'initializing' o 'error'."""
    model_loaded: bool
    """True cuando el modelo está completamente cargado en memoria."""
    uptime_seconds: float
    """Segundos transcurridos desde el inicio del daemon."""


class VoicesResponse(BaseModel):
    """Lista de voces registradas."""
    voices: list[str]
