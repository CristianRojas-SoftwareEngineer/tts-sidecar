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
        from tts_sidecar.daemon import server

        started = threading.Event()
        release = threading.Event()

        class SlowEngine:
            def speak(self, **kwargs):
                started.set()
                assert release.wait(timeout=10), "la síntesis nunca fue liberada"
                return b"RIFF" + b"\x00" * 40

        wav = tmp_path / "voz.wav"
        wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

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
                health = client.get("/health")
                assert health.status_code == 200

                release.set()
                t.join(timeout=10)
                assert result["resp"].status_code == 200
        finally:
            server.set_engine(old_engine)


class TestSynthesizeRutasPermitidas:
    def test_rechaza_ruta_fuera_de_directorios_permitidos(self, tmp_path, monkeypatch):
        """WARNING-02: una ruta .wav fuera de voices_root()/tempdir se rechaza con 400."""
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server
        from tts_sidecar import voices

        # Directorio ajeno a los permitidos (no es voices_root, factory ni tempdir).
        outside_root = tmp_path / "fuera_de_lo_permitido"
        outside_root.mkdir()
        wav = outside_root / "voz.wav"
        wav.write_bytes(b"RIFF")

        monkeypatch.setattr(voices, "allowed_audio_dirs", lambda: [str(tmp_path / "voices_permitido")])

        old_engine = server._engine
        server.set_engine(MagicMock())
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 400
                assert str(wav) not in resp.text
        finally:
            server.set_engine(old_engine)

    def test_acepta_ruta_dentro_de_voices_root(self, tmp_path, monkeypatch):
        """Una ruta dentro de voices_root() sigue siendo aceptada tras WARNING-02."""
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server
        from tts_sidecar import voices

        allowed_root = tmp_path / "voices_permitido"
        allowed_root.mkdir()
        wav = allowed_root / "voz.wav"
        wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

        monkeypatch.setattr(voices, "allowed_audio_dirs", lambda: [str(allowed_root)])

        fake_engine = MagicMock()
        fake_engine.speak.return_value = b"RIFF" + b"\x00" * 40
        fake_engine._synthesis_timing = {}

        old_engine = server._engine
        server.set_engine(fake_engine)
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 200
        finally:
            server.set_engine(old_engine)


class TestSynthesizeValidacionHeaderYRutaCanonica:
    def test_rechaza_extension_wav_con_header_no_wav(self, tmp_path, monkeypatch):
        """Extensión .wav pero contenido no-RIFF/WAVE: rechazado con 400."""
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server
        from tts_sidecar import voices

        allowed_root = tmp_path / "voices_permitido"
        allowed_root.mkdir()
        wav = allowed_root / "voz.wav"
        wav.write_bytes(b"no soy un wav")

        monkeypatch.setattr(voices, "allowed_audio_dirs", lambda: [str(allowed_root)])

        old_engine = server._engine
        server.set_engine(MagicMock())
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 400
        finally:
            server.set_engine(old_engine)

    def test_pasa_ruta_canonica_al_motor(self, tmp_path, monkeypatch):
        """El motor recibe os.path.realpath(path), resuelto una sola vez en la validación."""
        import os
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server
        from tts_sidecar import voices

        allowed_root = tmp_path / "voices_permitido"
        allowed_root.mkdir()
        wav = allowed_root / "voz.wav"
        wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")

        monkeypatch.setattr(voices, "allowed_audio_dirs", lambda: [str(allowed_root)])

        fake_engine = MagicMock()
        fake_engine.speak.return_value = b"RIFF" + b"\x00" * 40
        fake_engine._synthesis_timing = {}

        old_engine = server._engine
        server.set_engine(fake_engine)
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 200
                _, kwargs = fake_engine.speak.call_args
                assert kwargs["speech_audio"] == os.path.realpath(str(wav))
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
        from tts_sidecar.daemon.daemon import DaemonManager

        psutil_mock, proc = self._fake_psutil(["node", "otro-servidor.js"])
        with patch.dict(sys.modules, {"psutil": psutil_mock}):
            DaemonManager()._kill_pid(1234)

        proc.terminate.assert_not_called()
        assert "no parece ser el daemon" in capsys.readouterr().err

    def test_termina_el_daemon_propio(self):
        from tts_sidecar.daemon.daemon import DaemonManager

        psutil_mock, proc = self._fake_psutil(
            ["python", "-m", "tts_sidecar.daemon.run"]
        )
        with patch.dict(sys.modules, {"psutil": psutil_mock}):
            DaemonManager()._kill_pid(1234)

        proc.terminate.assert_called_once()


class TestDaemonManager:
    @patch("requests.get")
    def test_is_running_true(self, mock_get):
        from tts_sidecar.daemon import DaemonIPCClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_get.return_value = mock_resp

        client = DaemonIPCClient()
        assert client.is_running() is True

    @patch("requests.get")
    def test_is_running_false_connection_error(self, mock_get):
        import requests
        from tts_sidecar.daemon import DaemonIPCClient
        mock_get.side_effect = requests.ConnectionError("refused")

        client = DaemonIPCClient()
        assert client.is_running() is False

    @patch("requests.get")
    def test_list_voices(self, mock_get):
        from tts_sidecar.daemon import DaemonIPCClient
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
        from tts_sidecar.daemon import DaemonIPCClient
        mock_get.side_effect = requests.Timeout()

        client = DaemonIPCClient()
        voices = client.list_voices()
        assert voices == []

    @patch("requests.get")
    def test_list_voices_on_invalid_json(self, mock_get):
        """JSON inválido en el cuerpo de éxito degrada a [] igual que synthesize()."""
        from tts_sidecar.daemon import DaemonIPCClient
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("invalid json")
        mock_get.return_value = mock_resp

        client = DaemonIPCClient()
        voices = client.list_voices()
        assert voices == []

    @patch("requests.post")
    def test_synthesize_success(self, mock_post):
        """El cliente reconstruye el WAV desde el frame `result` (base64) y
        reenvía cada frame `progress` a on_progress."""
        import base64
        import json
        from tts_sidecar.daemon import DaemonIPCClient

        audio = b"RIFF" + b"\x00" * 40
        lines = [
            json.dumps({"event": "progress", "stage": "conditionals"}).encode(),
            json.dumps({"event": "progress", "stage": "t3", "tokens": 20}).encode(),
            json.dumps({
                "event": "result",
                "audio_b64": base64.b64encode(audio).decode("ascii"),
                "t3_time": 9.7,
                "s3gen_time": 7.0,
            }).encode(),
        ]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_post.return_value = mock_resp

        progreso = []
        client = DaemonIPCClient()
        audio_out = client.synthesize(text="hola", on_progress=progreso.append)
        assert audio_out == audio
        assert progreso == [
            {"event": "progress", "stage": "conditionals"},
            {"event": "progress", "stage": "t3", "tokens": 20},
        ]

    @patch("requests.post")
    def test_synthesize_error_frame(self, mock_post):
        """Un frame `error` del stream se convierte en DaemonIPCError."""
        import json
        from tts_sidecar.daemon import DaemonIPCClient, DaemonIPCError

        lines = [json.dumps({"event": "error", "detail": "internal error"}).encode()]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_post.return_value = mock_resp

        client = DaemonIPCClient()
        with pytest.raises(DaemonIPCError, match="Error del daemon: internal error"):
            client.synthesize(text="hola")

    @patch("requests.post")
    def test_synthesize_http_error_inmediato(self, mock_post):
        """Un 400/503 de validación (respuesta inmediata, no stream) → DaemonIPCError."""
        from tts_sidecar.daemon import DaemonIPCClient, DaemonIPCError

        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.json.return_value = {"detail": "ruta no permitida"}
        mock_post.return_value = mock_resp

        client = DaemonIPCClient()
        with pytest.raises(DaemonIPCError, match="Error del daemon: ruta no permitida"):
            client.synthesize(text="hola")

    @patch("requests.post")
    def test_synthesize_sin_frame_result_falla(self, mock_post):
        """Un stream que termina sin `result` ni `error` rompe el contrato → error."""
        import json
        from tts_sidecar.daemon import DaemonIPCClient, DaemonIPCError

        lines = [json.dumps({"event": "progress", "stage": "t3", "tokens": 10}).encode()]
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.iter_lines.return_value = iter(lines)
        mock_post.return_value = mock_resp

        client = DaemonIPCClient()
        with pytest.raises(DaemonIPCError, match="no devolvió audio"):
            client.synthesize(text="hola")


class TestSynthesizeStreaming:
    """El endpoint /synthesize emite NDJSON: N×progress → result, o error."""

    def _allowed_wav(self, tmp_path, monkeypatch):
        from tts_sidecar import voices

        allowed_root = tmp_path / "voices_permitido"
        allowed_root.mkdir()
        wav = allowed_root / "voz.wav"
        wav.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
        monkeypatch.setattr(voices, "allowed_audio_dirs", lambda: [str(allowed_root)])
        return wav

    def test_orden_progress_luego_result(self, tmp_path, monkeypatch):
        import base64
        import json
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server

        wav = self._allowed_wav(tmp_path, monkeypatch)
        audio = b"RIFF" + b"\x00" * 40

        class FakeEngine:
            _synthesis_timing = {"t3": 1.5, "s3gen": 2.5}

            def speak(self, progress_callback=None, **kwargs):
                progress_callback({"event": "progress", "stage": "conditionals"})
                progress_callback({"event": "progress", "stage": "t3", "tokens": 10})
                return audio

        old_engine = server._engine
        server.set_engine(FakeEngine())
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 200
                assert resp.headers["content-type"].startswith("application/x-ndjson")
                lines = [json.loads(l) for l in resp.text.splitlines() if l.strip()]
                assert [l["event"] for l in lines] == ["progress", "progress", "result"]
                assert lines[0]["stage"] == "conditionals"
                assert lines[1]["tokens"] == 10
                assert base64.b64decode(lines[-1]["audio_b64"]) == audio
                assert lines[-1]["t3_time"] == 1.5
                assert lines[-1]["s3gen_time"] == 2.5
        finally:
            server.set_engine(old_engine)

    def test_error_de_sintesis_emite_frame_error(self, tmp_path, monkeypatch):
        import json
        from fastapi.testclient import TestClient
        from tts_sidecar.daemon import server

        wav = self._allowed_wav(tmp_path, monkeypatch)

        class FakeEngine:
            _synthesis_timing = {}

            def speak(self, progress_callback=None, **kwargs):
                raise RuntimeError("boom interno con /ruta/secreta")

        old_engine = server._engine
        server.set_engine(FakeEngine())
        try:
            with TestClient(server.app) as client:
                resp = client.post(
                    "/synthesize", json={"text": "hola", "speech_audio": str(wav)}
                )
                assert resp.status_code == 200
                lines = [json.loads(l) for l in resp.text.splitlines() if l.strip()]
                assert lines[-1]["event"] == "error"
                # El detalle no filtra el mensaje/ruta interno real.
                assert lines[-1]["detail"] == "Error interno de síntesis"
                assert "secreta" not in resp.text
        finally:
            server.set_engine(old_engine)
