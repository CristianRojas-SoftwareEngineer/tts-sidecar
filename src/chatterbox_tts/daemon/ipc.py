"""
IPC client to communicate with tts-sidecar daemon.
Uses HTTP over TCP (works on all platforms).
"""

from typing import Optional

import requests


class DaemonIPCError(Exception):
    """IPC communication error with daemon."""
    pass


class DaemonIPCClient:
    """
    IPC client to communicate with tts-sidecar daemon.

    Uses HTTP over TCP (127.0.0.1:8765) - works on Windows, Linux, and Mac.
    """

    DEFAULT_PORT = 8765
    TIMEOUT = 5.0  # Connection timeout
    REQUEST_TIMEOUT = 300.0  # Synthesis timeout (5 min for long audio)

    def __init__(self, port: int = None):
        self.port = port or self.DEFAULT_PORT
        self.base_url = f"http://127.0.0.1:{self.port}"

    def is_running(self) -> bool:
        """Check if daemon is running."""
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
        model: str = "es-latam",
        device: str = "cpu",
    ) -> bytes:
        """
        Synthesize text via daemon.

        Returns WAV audio bytes.

        Raises:
            DaemonIPCError: If communication fails
        """
        try:
            response = requests.post(
                f"{self.base_url}/synthesize",
                json={
                    "text": text,
                    "voice_audio": voice_audio,
                    "speech_audio": speech_audio,
                    "model": model,
                    "device": device,
                },
                timeout=self.REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                # Print sub-stage timing if available
                t3_time = response.headers.get("X-T3-Time")
                s3gen_time = response.headers.get("X-S3Gen-Time")
                if t3_time and s3gen_time:
                    print(f"   [Stage 2a] T3 autoregresivo: {t3_time}s")
                    print(f"   [Stage 2b] S3Gen vocoder:   {s3gen_time}s")
                return response.content
            else:
                error = response.json().get("detail", "Unknown error")
                raise DaemonIPCError(f"Daemon error: {error}")

        except requests.ConnectionError as e:
            raise DaemonIPCError(f"Cannot connect to daemon: {e}")
        except requests.Timeout as e:
            raise DaemonIPCError(f"Daemon timeout: {e}")

    def list_voices(self) -> list[str]:
        """List voices via daemon."""
        try:
            response = requests.get(
                f"{self.base_url}/voices",
                timeout=self.TIMEOUT
            )
            if response.status_code == 200:
                return response.json().get("voices", [])
            return []
        except (requests.ConnectionError, requests.Timeout):
            return []


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    try:
        client = DaemonIPCClient()
        return client.is_running()
    except Exception:
        return False
