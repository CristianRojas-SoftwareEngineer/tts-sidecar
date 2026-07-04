"""
Cliente IPC para comunicarse con el daemon de tts-sidecar.
Usa HTTP sobre TCP (funciona en todas las plataformas).
"""

import base64
import json
from typing import Callable, Optional

import requests

from ..timing import log

# Puerto fijo del daemon (loopback 127.0.0.1). Fuente única importada por
# daemon.py y run.py: no existe flag --port. Correr dos daemons o convivir con
# otro servicio en este puerto no está soportado por diseño (ver DAEMON-MODE.md).
DEFAULT_PORT = 8765


class DaemonIPCError(Exception):
    """Error de comunicación IPC con el daemon."""
    pass


class DaemonIPCClient:
    """
    Cliente IPC para comunicarse con el daemon de tts-sidecar.

    Usa HTTP sobre TCP (127.0.0.1:8765), lo que garantiza compatibilidad
    con Windows, Linux y macOS sin depender de Unix sockets ni named pipes.
    """

    TIMEOUT = 5.0          # Timeout de conexión
    REQUEST_TIMEOUT = 300.0  # Timeout de síntesis (5 min para audio largo)

    def __init__(self):
        self.port = DEFAULT_PORT
        self.base_url = f"http://127.0.0.1:{self.port}"

    def is_running(self) -> bool:
        """Comprueba si el daemon está corriendo y responde al health check."""
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=self.TIMEOUT
            )
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def synthesize(
        self,
        text: str,
        voice_audio: Optional[str] = None,
        speech_audio: Optional[str] = None,
        on_progress: Optional[Callable[[dict], None]] = None,
    ) -> bytes:
        """
        Sintetiza texto vía daemon, consumiendo el stream NDJSON.

        El daemon responde con N líneas `progress` (avance de la síntesis)
        seguidas de una línea `result` con el WAV en base64; una línea `error`
        indica un fallo del hilo de síntesis. Cada línea `progress` se reenvía a
        `on_progress` (si se da) para alimentar el indicador de progreso del CLI.

        Args:
            on_progress: Callback opcional invocado con el dict de cada evento
                `progress` del stream (mismo contrato que engine.speak).

        Devuelve los bytes del audio WAV (decodificados del frame `result`).

        Raises:
            DaemonIPCError: Si la comunicación falla o el daemon emite `error`.
        """
        try:
            response = requests.post(
                f"{self.base_url}/synthesize",
                json={
                    "text": text,
                    "voice_audio": voice_audio,
                    "speech_audio": speech_audio,
                },
                timeout=self.REQUEST_TIMEOUT,
                stream=True,
            )

            # Los errores de validación (400/503) llegan como respuesta inmediata
            # con cuerpo JSON {"detail": ...}, no como frame del stream.
            if response.status_code != 200:
                try:
                    error = response.json().get("detail", "Error desconocido")
                except ValueError:
                    # Cuerpo de error no-JSON: no romper la promesa de DaemonIPCError
                    error = f"HTTP {response.status_code}"
                raise DaemonIPCError(f"Error del daemon: {error}")

            audio_bytes: Optional[bytes] = None
            for raw in response.iter_lines():
                if not raw:
                    continue
                try:
                    ev = json.loads(raw)
                except ValueError:
                    # Línea no-JSON (no debería ocurrir): se ignora sin abortar.
                    continue

                kind = ev.get("event")
                if kind == "progress":
                    if on_progress is not None:
                        on_progress(ev)
                elif kind == "result":
                    audio_bytes = base64.b64decode(ev["audio_b64"])
                    # Timing por sub-etapa (equivalente a los antiguos headers
                    # X-T3-Time / X-S3Gen-Time). Se emite con el MISMO formato que
                    # el modo directo (engine.py usa estas cadenas exactas) y vía
                    # log(), coordinado con el spinner activo, sobre stderr.
                    t3_time = ev.get("t3_time")
                    s3gen_time = ev.get("s3gen_time")
                    if t3_time is not None and s3gen_time is not None:
                        log(f"   [Stage 2a] T3 autoregresivo: {float(t3_time):.1f}s")
                        log(f"   [Stage 2b] S3Gen vocoder:   {float(s3gen_time):.1f}s")
                elif kind == "error":
                    raise DaemonIPCError(
                        f"Error del daemon: {ev.get('detail', 'Error desconocido')}"
                    )

            if audio_bytes is None:
                # El stream terminó sin frame `result` ni `error`: contrato roto.
                raise DaemonIPCError("El daemon no devolvió audio")
            return audio_bytes

        except requests.ConnectionError as e:
            raise DaemonIPCError(f"No se puede conectar al daemon: {e}")
        except requests.Timeout as e:
            raise DaemonIPCError(f"Timeout del daemon: {e}")
        except requests.RequestException as e:
            raise DaemonIPCError(f"Error de comunicación con el daemon: {e}")

    def list_voices(self) -> list[str]:
        """Lista las voces registradas vía daemon."""
        try:
            response = requests.get(
                f"{self.base_url}/voices",
                timeout=self.TIMEOUT
            )
            if response.status_code == 200:
                try:
                    return response.json().get("voices", [])
                except ValueError:
                    # Cuerpo de éxito no-JSON: degradar a lista vacía en vez de propagar.
                    return []
            return []
        except (requests.ConnectionError, requests.Timeout):
            return []


def is_daemon_running() -> bool:
    """
    Comprueba si el daemon está corriendo y responde al health check.

    Función de conveniencia que crea un DaemonIPCClient temporal para
    verificar el estado sin necesidad de mantener una instancia del cliente.
    """
    try:
        client = DaemonIPCClient()
        return client.is_running()
    except Exception:
        return False
