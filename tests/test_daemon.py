"""Tests para el gestor del ciclo de vida del daemon."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestServerConcurrency:
    def test_health_responde_durante_sintesis(self, tmp_path):
        """Una síntesis bloqueada no debe congelar /health (WARNING-03)."""
        import threading
        from fastapi.testclient import TestClient
        from chatterbox_tts.daemon import server

        started = threading.Event()
        release = threading.Event()

        class SlowEngine:
            def speak(self, **kwargs):
                started.set()
                assert release.wait(timeout=10), "la síntesis nunca fue liberada"
                return b"RIFF" + b"\x00" * 40

        wav = tmp_path / "voz.wav"
        wav.write_bytes(b"RIFF")

        old_engine = server._engine
        server.set_engine(SlowEngine())
        server.set_start_time(0.0)
        try:
            with TestClient(server.app) as client:
                result = {}

                def synth():
                    result["resp"] = client.post(
                        "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                    )

                t = threading.Thread(target=synth)
                t.start()
                assert started.wait(timeout=10), "la síntesis no arrancó"

                # Con la síntesis en curso, /health debe responder
                health = client.get("/health", timeout=5)
                assert health.status_code == 200

                release.set()
                t.join(timeout=10)
                assert result["resp"].status_code == 200
        finally:
            server.set_engine(old_engine)


class TestKillPidVerificado:
    def _fake_psutil(self, cmdline):
        proc = MagicMock()
        proc.cmdline.return_value = cmdline
        psutil_mock = MagicMock()
        psutil_mock.Process.return_value = proc
        return psutil_mock, proc

    def test_no_termina_procesos_ajenos(self, capsys):
        """WARNING-04: si otro servicio ocupa el puerto, no se le hace terminate()."""
        from chatterbox_tts.daemon.daemon import DaemonManager

        psutil_mock, proc = self._fake_psutil(["node", "otro-servidor.js"])
        with patch.dict(sys.modules, {"psutil": psutil_mock}):
            DaemonManager()._kill_pid(1234)

        proc.terminate.assert_not_called()
        assert "no parece ser el daemon" in capsys.readouterr().err

    def test_termina_el_daemon_propio(self):
        from chatterbox_tts.daemon.daemon import DaemonManager

        psutil_mock, proc = self._fake_psutil(
            ["python", "-m", "chatterbox_tts.daemon.run", "--port", "8765"]
        )
        with patch.dict(sys.modules, {"psutil": psutil_mock}):
            DaemonManager()._kill_pid(1234)

        proc.terminate.assert_called_once()


class TestDaemonManager:
    @patch("requests.get")
    def test_is_running_true(self, mock_get):
        from chatterbox_tts.daemon import DaemonIPCClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        client = DaemonIPCClient()
        assert client.is_running() is True

    @patch("requests.get")
    def test_is_running_false_connection_error(self, mock_get):
        import requests
        from chatterbox_tts.daemon import DaemonIPCClient
        mock_get.side_effect = requests.ConnectionError("refused")

        client = DaemonIPCClient()
        assert client.is_running() is False

    @patch("requests.get")
    def test_list_voices(self, mock_get):
        from chatterbox_tts.daemon import DaemonIPCClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"voices": ["crist", "testcli"]}
        mock_get.return_value = mock_resp

        client = DaemonIPCClient()
        voices = client.list_voices()
        assert voices == ["crist", "testcli"]

    @patch("requests.get")
    def test_list_voices_on_error(self, mock_get):
        import requests
        from chatterbox_tts.daemon import DaemonIPCClient
        mock_get.side_effect = requests.Timeout()

        client = DaemonIPCClient()
        voices = client.list_voices()
        assert voices == []

    @patch("requests.post")
    def test_synthesize_success(self, mock_post):
        from chatterbox_tts.daemon import DaemonIPCClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"RIFF" + b"\x00" * 40
        mock_resp.headers = {"X-T3-Time": "9.7", "X-S3Gen-Time": "7.0"}
        mock_post.return_value = mock_resp

        client = DaemonIPCClient()
        audio = client.synthesize(text="hola")
        assert audio == b"RIFF" + b"\x00" * 40

    @patch("requests.post")
    def test_synthesize_error(self, mock_post):
        from chatterbox_tts.daemon import DaemonIPCClient, DaemonIPCError
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"detail": "internal error"}
        mock_post.return_value = mock_resp

        client = DaemonIPCClient()
        with pytest.raises(DaemonIPCError, match="Error del daemon: internal error"):
            client.synthesize(text="hola")
