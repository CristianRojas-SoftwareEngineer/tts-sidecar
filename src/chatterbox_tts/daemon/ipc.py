"""
Cliente IPC para comunicarse con el daemon de tts-sidecar.
Usa HTTP sobre TCP (funciona en todas las plataformas).
"""

from typing import Optional

import requests

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
    ) -> bytes:
        """
        Sintetiza texto vía daemon.

        Devuelve los bytes del audio WAV.

        Raises:
            DaemonIPCError: Si la comunicación falla
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
            )

            if response.status_code == 200:
                # Imprimir timing por sub-etapa si el daemon lo expone en headers
                t3_time = response.headers.get("X-T3-Time")
                s3gen_time = response.headers.get("X-S3Gen-Time")
                if t3_time and s3gen_time:
                    print(f"   [Stage 2a] T3 autoregresivo: {t3_time}s")
                    print(f"   [Stage 2b] S3Gen vocoder:   {s3gen_time}s")
                return response.content
            else:
                try:
                    error = response.json().get("detail", "Error desconocido")
                except ValueError:
                    # Cuerpo de error no-JSON: no romper la promesa de DaemonIPCError
                    error = f"HTTP {response.status_code}"
                raise DaemonIPCError(f"Error del daemon: {error}")

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
