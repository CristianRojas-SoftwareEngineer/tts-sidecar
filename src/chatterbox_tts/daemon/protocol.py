"""
Definiciones del protocolo IPC del daemon de tts-sidecar.
"""

from pydantic import BaseModel, Field
from typing import Optional

# Tope de texto por petición: acota el trabajo del T3 y evita el DoS local
# trivial de un payload ilimitado.
MAX_TEXT_LENGTH = 5000


class SynthesizeRequest(BaseModel):
    """Request de síntesis de habla.

    El daemon sirve un único modelo/dispositivo fijado al arrancar; la petición
    no lleva `model` ni `device` (el servidor los ignoraría).
    """
    text: str = Field(min_length=1, max_length=MAX_TEXT_LENGTH)
    voice_audio: Optional[str] = None
    speech_audio: Optional[str] = None


class HealthResponse(BaseModel):
    """Respuesta del health check."""
    status: str
    """Estado del daemon: 'healthy', 'initializing' o 'error'."""
    model_loaded: bool
    """True cuando el modelo está completamente cargado en memoria."""
    uptime_seconds: float
    """Segundos transcurridos desde el inicio del daemon."""


class ErrorResponse(BaseModel):
    """Respuesta de error."""
    error: str
    code: str


class VoicesResponse(BaseModel):
    """Lista de voces registradas."""
    voices: list[str]
