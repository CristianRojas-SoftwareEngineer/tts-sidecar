"""
Daemon lifecycle manager for tts-sidecar.
Handles start/stop/restart/status commands.
"""

import os
import platform
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Optional

import requests

from .. import paths


class DaemonManager:
    """
    Manages the tts-sidecar daemon lifecycle.

    Handles start/stop/restart/status commands.
    Works on Windows, Linux, and Mac.
    """

    DEFAULT_PORT = 8765
    START_TIMEOUT = 120.0  # Model loading + compilation takes 30-90s

    def __init__(self, port: int = None):
        self.system = platform.system()
        self.port = port or self.DEFAULT_PORT
        self.base_url = f"http://127.0.0.1:{self.port}"

    def start(
        self,
        background: bool = True,
        auto_restart: bool = False,
        max_retries: int = 0,
    ) -> bool:
        """
        Start the daemon. Idempotent - if daemon is already running, returns True.
        """
        # Check if already running
        if self.is_running():
            print("Daemon already running")
            return True

        # Prepare command. En modo congelado el ejecutable no acepta `-m módulo`,
        # así que se auto-invoca mediante su subcomando `daemon serve`.
        if paths.is_frozen():
            cmd = [sys.executable, "daemon", "serve", "--port", str(self.port)]
        else:
            cmd = [
                sys.executable,
                "-m", "chatterbox_tts.daemon.run",
                "--port", str(self.port),
            ]

        if auto_restart:
            cmd.append("--auto-restart")
        if max_retries > 0:
            cmd.extend(["--max-retries", str(max_retries)])

        if background:
            env = os.environ.copy()
            # Modo fuente: fijar PYTHONPATH para que el subproceso encuentre
            # chatterbox_tts. En modo congelado el ejecutable ya es autocontenido.
            if not paths.is_frozen():
                # __file__ is src/chatterbox_tts/daemon/daemon.py
                # 3 dirname gives us the src/ directory (project root)
                src_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                if os.path.exists(src_path):
                    env["PYTHONPATH"] = src_path

            if self.system == "Windows":
                subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=subprocess.DETACHED_PROCESS,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                subprocess.Popen(
                    cmd,
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )

            # Wait for daemon to be ready (model loading takes time)
            return self._wait_for_ready()
        else:
            # Foreground mode (for debugging)
            subprocess.run(cmd)
            return True

    def stop(self, timeout: float = 10.0) -> bool:
        """
        Stop the daemon. Returns True when stopped.
        """
        # Check if running
        if not self.is_running():
            # Even if health check fails, check if something is on the port
            pid = self._get_pid_from_port()
            if pid:
                self._kill_pid(pid)
            print("Daemon not running")
            return True

        # Try graceful shutdown via HTTP
        try:
            requests.post(
                f"{self.base_url}/shutdown",
                timeout=timeout
            )
        except requests.RequestException:
            pass

        # Give it a moment to shut down gracefully
        time.sleep(0.5)

        # If still running, force kill
        if self.is_running():
            pid = self._get_pid_from_port()
            if pid:
                self._kill_pid(pid)

        return not self.is_running()

    def restart(self) -> bool:
        """Restart the daemon. Kills existing and starts fresh."""
        print("Stopping daemon...")
        self.stop()
        time.sleep(1)
        print("Starting daemon...")
        return self.start()

    def status(self) -> dict:
        """Get daemon status."""
        if not self.is_running():
            return {"running": False}

        try:
            response = requests.get(f"{self.base_url}/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return {
                    "running": True,
                    "status": data.get("status"),
                    "model_loaded": data.get("model_loaded"),
                    "uptime_seconds": data.get("uptime_seconds"),
                }
        except requests.RequestException:
            pass

        return {"running": True, "status": "unknown"}

    def is_running(self) -> bool:
        """Check if daemon is running and healthy."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=2)
            return response.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            return False

    def _wait_for_ready(self, timeout: float = None) -> bool:
        """Wait for daemon to be ready to accept connections."""
        timeout = timeout or self.START_TIMEOUT
        start = time.time()

        print(f"Waiting for daemon to be ready (timeout={timeout}s)...")
        while time.time() - start < timeout:
            if self.is_running():
                print("Daemon ready")
                return True
            time.sleep(1)

        print("Timeout waiting for daemon")
        return False

    def _get_pid_from_port(self) -> Optional[int]:
        """Get PID of process listening on our port."""
        try:
            if self.system == "Windows":
                # Use netstat to get PID
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if f":{self.port}" in line and "LISTENING" in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == "LISTENING" and i < len(parts) - 1:
                                return int(parts[i + 1])
            else:
                # Unix - use lsof or ss
                result = subprocess.run(
                    ["ss", "-tlnp"],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.splitlines():
                    if f":{self.port}" in line:
                        # Extract PID from last column like "pid=1234"
                        import re
                        match = re.search(r"pid=(\d+)", line)
                        if match:
                            return int(match.group(1))
        except Exception:
            pass
        return None

    def _kill_pid(self, pid: int):
        """Kill a process by PID."""
        try:
            if self.system == "Windows":
                subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                             capture_output=True, timeout=5)
            else:
                os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
            pass
