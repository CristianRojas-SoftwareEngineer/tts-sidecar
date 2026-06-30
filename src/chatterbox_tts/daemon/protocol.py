"""
Protocol definitions for tts-sidecar daemon IPC.
"""

from pydantic import BaseModel
from typing import Optional


class SynthesizeRequest(BaseModel):
    """Request to synthesize speech."""
    text: str
    voice_audio: Optional[str] = None
    speech_audio: Optional[str] = None
    model: str = "es-latam"
    device: str = "cpu"


class HealthResponse(BaseModel):
    """Health check response."""
    status: str  # "healthy", "initializing", "error"
    model_loaded: bool
    uptime_seconds: float


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    code: str


class VoicesResponse(BaseModel):
    """List of registered voices."""
    voices: list[str]
