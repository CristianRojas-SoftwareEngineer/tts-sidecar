"""Tests para los comandos del CLI."""

import os
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class MockArgs:
    def __init__(self, **kwargs):
        self.text = kwargs.get("text", "test text")
        self.voice = kwargs.get("voice", None)
        self.voice_audio = kwargs.get("voice_audio", None)
        self.speech_audio = kwargs.get("speech_audio", None)
        self.output = kwargs.get("output", None)
        self.model = kwargs.get("model", "es-mx-latam")
        self.compute_backend = kwargs.get("compute_backend", "auto")
        self.name = kwargs.get("name", "testcli")
        self.reference = kwargs.get("reference", "ref.wav")
        self.speech = kwargs.get("speech", "speech.wav")
        self.daemon = kwargs.get("daemon", False)
        self.no_daemon = kwargs.get("no_daemon", False)
        self.json = kwargs.get("json", False)
        self.remove_path = kwargs.get("remove_path", False)


class TestResolveVoicePaths:
    def test_resolve_from_voice_name_not_found(self):
        from chatterbox_tts.cli import _resolve_voice_paths
        with patch("os.path.exists", return_value=False):
            args = MockArgs(voice="nonexistent")
            with pytest.raises(FileNotFoundError):
                _resolve_voice_paths(args)

    @patch("os.path.exists", return_value=True)
    def test_resolve_from_voice_name_found(self, mock_exists):
        from chatterbox_tts.cli import _resolve_voice_paths
        args = MockArgs(voice="crist")
        va, sa = _resolve_voice_paths(args)
        assert va is not None
        assert sa is not None

    def test_resolve_from_explicit_paths(self):
        from pathlib import Path
        from chatterbox_tts.cli import _resolve_voice_paths
        args = MockArgs(
            voice_audio="/path/to/voice.wav",
            speech_audio="/path/to/speech.wav"
        )
        va, sa = _resolve_voice_paths(args)
        assert va == str(Path("/path/to/voice.wav").resolve())
        assert sa == str(Path("/path/to/speech.wav").resolve())


class TestCmdVoiceList:
    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_lists_voices(self, mock_list_voices, capsys):
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = ["crist", "testcli"]

        cmd_voice_list(MockArgs())

        out = capsys.readouterr().out
        assert "Voces registradas:" in out
        assert "crist" in out
        assert "testcli" in out

    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_empty(self, mock_list_voices, capsys):
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = []

        cmd_voice_list(MockArgs())

        out = capsys.readouterr().out
        assert "No hay voces registradas" in out

    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_json(self, mock_list_voices, capsys):
        import json
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = ["crist", "testcli"]

        cmd_voice_list(MockArgs(json=True))

        out = capsys.readouterr().out
        assert json.loads(out) == {"voices": ["crist", "testcli"]}


class TestCmdVoiceAdd:
    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.voices.register_voice_files")
    def test_cmd_voice_add_success_sin_motor(self, mock_register, _cached, capsys):
        """R-01: voice add registra sin instanciar ChatterboxEngine."""
        from chatterbox_tts.cli import cmd_voice_add

        mock_register.return_value = ("/path/to/ref.wav", "/path/to/speech.wav")

        with patch("chatterbox_tts.engine.ChatterboxEngine") as mock_engine_cls:
            cmd_voice_add(MockArgs(name="newvoice", reference="ref.wav", speech="speech.wav"))
            mock_engine_cls.assert_not_called()

        out = capsys.readouterr().out
        assert "Voz 'newvoice' registrada" in out
        mock_register.assert_called_once()

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=False)
    def test_cmd_voice_add_sin_modelo_remite_a_setup(self, _cached, capsys):
        """R-01: sin modelo cacheado, voice add aborta remitiendo a setup."""
        from chatterbox_tts.cli import cmd_voice_add

        with pytest.raises(SystemExit):
            cmd_voice_add(MockArgs(name="newvoice", reference="ref.wav", speech="speech.wav"))

        err = capsys.readouterr().err
        assert "setup" in err


class TestCmdVoiceRemove:
    @patch("chatterbox_tts.voices.remove_voice")
    def test_cmd_voice_remove_success(self, mock_remove_voice, capsys):
        from chatterbox_tts.cli import cmd_voice_remove

        mock_remove_voice.return_value = True

        cmd_voice_remove(MockArgs(name="testcli"))

        out = capsys.readouterr().out
        assert "Voz 'testcli' eliminada" in out

    @patch("chatterbox_tts.voices.remove_voice")
    def test_cmd_voice_remove_not_found(self, mock_remove_voice, capsys):
        from chatterbox_tts.cli import cmd_voice_remove

        mock_remove_voice.return_value = False

        with pytest.raises(SystemExit):
            cmd_voice_remove(MockArgs(name="nonexistent"))


class TestMensajesDeVoces:
    @patch("chatterbox_tts.voices._resolve_voice_dir")
    @patch("chatterbox_tts.voices.remove_voice", return_value=False)
    def test_remove_de_voz_de_fabrica_explica_solo_lectura(
        self, mock_remove, mock_resolve, capsys
    ):
        from chatterbox_tts.cli import cmd_voice_remove

        mock_resolve.return_value = "/fabrica/default"

        with pytest.raises(SystemExit):
            cmd_voice_remove(MockArgs(name="default"))

        err = capsys.readouterr().err
        assert "voz de fábrica" in err
        assert "no encontrada" not in err

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    def test_speak_no_remite_a_setup_si_falta_un_audio_de_usuario(self, _cached, capsys):
        from chatterbox_tts.cli import cmd_speak

        with pytest.raises(SystemExit):
            cmd_speak(MockArgs(text="hola", voice="voz_inexistente", no_daemon=True))

        err = capsys.readouterr().err
        assert "Error:" in err
        assert "setup" not in err


class TestCmdDevices:
    @patch("chatterbox_tts.audio.get_audio_devices")
    def test_cmd_devices(self, mock_get_devices, capsys):
        from chatterbox_tts.cli import cmd_devices

        mock_get_devices.return_value = [
            {"id": 0, "name": "Speaker 1", "latency": 0.01},
            {"id": 1, "name": "Speaker 2", "latency": 0.005},
        ]

        cmd_devices(MockArgs())

        out = capsys.readouterr().out
        assert "Dispositivos de salida de audio:" in out
        assert "Speaker 1" in out
        assert "Speaker 2" in out

    @patch("chatterbox_tts.audio.get_audio_devices")
    def test_cmd_devices_json(self, mock_get_devices, capsys):
        import json
        from chatterbox_tts.cli import cmd_devices

        devices = [{"id": 0, "name": "Speaker 1", "latency": 0.01}]
        mock_get_devices.return_value = devices

        cmd_devices(MockArgs(json=True))

        out = capsys.readouterr().out
        assert json.loads(out) == {"devices": devices}


class TestCmdVersion:
    def test_cmd_version_human(self, capsys):
        from chatterbox_tts.cli import cmd_version

        cmd_version(MockArgs())

        out = capsys.readouterr().out
        assert "tts-sidecar" in out

    def test_cmd_version_json(self, capsys):
        import json
        from chatterbox_tts import __version__
        from chatterbox_tts.cli import cmd_version

        cmd_version(MockArgs(json=True))

        out = capsys.readouterr().out
        assert json.loads(out) == {"name": "tts-sidecar", "version": __version__}


class TestCmdSpeakDaemonDispatch:
    """Las tres ramas del despacho daemon/auto/directo (WARNING-06)."""

    def _args(self, **kw):
        kw.setdefault("voice_audio", "v.wav")
        kw.setdefault("speech_audio", "s.wav")
        kw.setdefault("output", "out.wav")
        return MockArgs(**kw)

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.daemon.DaemonIPCClient")
    @patch("chatterbox_tts.daemon.is_daemon_running", return_value=True)
    def test_sin_flags_usa_daemon_si_responde(self, mock_running, mock_client_cls, _cached, tmp_path):
        from chatterbox_tts.cli import cmd_speak

        client = MagicMock()
        client.synthesize.return_value = b"RIFF"
        mock_client_cls.return_value = client

        cmd_speak(self._args(output=str(tmp_path / "out.wav")))

        mock_running.assert_called_once()
        client.synthesize.assert_called_once()

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    @patch("chatterbox_tts.daemon.is_daemon_running", return_value=False)
    def test_sin_flags_cae_a_directo_si_no_responde(self, mock_running, mock_engine_cls, _cached, tmp_path):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine

        cmd_speak(self._args(output=str(tmp_path / "out.wav")))

        mock_running.assert_called_once()
        engine.speak.assert_called_once()

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.daemon.DaemonIPCClient")
    @patch("chatterbox_tts.daemon.is_daemon_running")
    def test_daemon_explicito_no_sondea_y_falla_en_error(self, mock_running, mock_client_cls, _cached):
        from chatterbox_tts.cli import cmd_speak
        from chatterbox_tts.daemon import DaemonIPCError

        client = MagicMock()
        client.synthesize.side_effect = DaemonIPCError("no conecta")
        mock_client_cls.return_value = client

        with pytest.raises(SystemExit):
            cmd_speak(self._args(daemon=True))

        mock_running.assert_not_called()

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    @patch("chatterbox_tts.daemon.is_daemon_running")
    def test_no_daemon_no_sondea(self, mock_running, mock_engine_cls, _cached, tmp_path):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine

        cmd_speak(self._args(no_daemon=True, output=str(tmp_path / "out.wav")))

        mock_running.assert_not_called()
        engine.speak.assert_called_once()


class TestCmdSpeak:
    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    def test_cmd_speak_saves_with_output(self, mock_engine_cls, mock_cached, capsys):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine

        cmd_speak(MockArgs(text="hola", output="out.wav", no_daemon=True))

        # engine.speak recibe el output_path y escribe el archivo directamente
        _, kwargs = engine.speak.call_args
        assert kwargs["output_path"] == "out.wav"
        err = capsys.readouterr().err
        assert "Audio guardado: out.wav" in err

    @patch("chatterbox_tts.model_cache.is_model_cached", return_value=True)
    @patch("chatterbox_tts.audio.AudioPlayer")
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    def test_cmd_speak_plays_without_output(self, mock_engine_cls, mock_player_cls, mock_cached):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine
        player = MagicMock()
        mock_player_cls.return_value = player

        cmd_speak(MockArgs(text="hola", output=None, no_daemon=True))

        player.play.assert_called_once_with(b"RIFF")


class TestEnvironmentChecksAudio:
    """WARNING-03: el chequeo de audio de doctor/setup refleja el estado real
    de la enumeración COM en Windows, no solo la disponibilidad del import."""

    def test_windows_audio_real_da_pass(self, monkeypatch):
        import platform as platform_module
        from chatterbox_tts import cli

        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        monkeypatch.setattr(
            "chatterbox_tts.audio.get_audio_devices_with_status",
            lambda: ([{"id": 0, "name": "Altavoces"}], False),
        )

        checks = cli._environment_checks()
        audio_check = next(c for c in checks if c[1] == "Audio library")
        assert audio_check[0] == "PASS"
        assert "1 dispositivo" in audio_check[2]

    def test_windows_audio_degradado_da_fail(self, monkeypatch):
        import platform as platform_module
        from chatterbox_tts import cli

        monkeypatch.setattr(platform_module, "system", lambda: "Windows")
        monkeypatch.setattr(
            "chatterbox_tts.audio.get_audio_devices_with_status",
            lambda: ([{"id": 0, "name": "Default", "latency": 0.1}], True),
        )

        checks = cli._environment_checks()
        audio_check = next(c for c in checks if c[1] == "Audio library")
        assert audio_check[0] == "FAIL"
        assert "no se pudo enumerar" in audio_check[2]

    def test_linux_audio_degradado_da_fail(self, monkeypatch):
        """WARNING-03: Linux/macOS ahora usan la misma enumeración real que Windows."""
        import platform as platform_module
        from chatterbox_tts import cli

        monkeypatch.setattr(platform_module, "system", lambda: "Linux")
        monkeypatch.setattr(
            "chatterbox_tts.audio.get_audio_devices_with_status",
            lambda: ([{"id": 0, "name": "Default", "latency": 0.1}], True),
        )

        checks = cli._environment_checks()
        audio_check = next(c for c in checks if c[1] == "Audio library")
        assert audio_check[0] == "FAIL"
        assert "no se pudo enumerar" in audio_check[2]

    def test_macos_audio_real_da_pass(self, monkeypatch):
        import platform as platform_module
        from chatterbox_tts import cli

        monkeypatch.setattr(platform_module, "system", lambda: "Darwin")
        monkeypatch.setattr(
            "chatterbox_tts.audio.get_audio_devices_with_status",
            lambda: ([{"id": 0, "name": "Built-in Output"}], False),
        )

        checks = cli._environment_checks()
        audio_check = next(c for c in checks if c[1] == "Audio library")
        assert audio_check[0] == "PASS"
        assert "1 dispositivo" in audio_check[2]


class TestCmdDevicesError:
    @patch("chatterbox_tts.audio.get_audio_devices")
    def test_cmd_devices_excepcion_sale_con_codigo_1(self, mock_get_devices, capsys):
        from chatterbox_tts.cli import cmd_devices

        mock_get_devices.side_effect = RuntimeError("PortAudio no disponible")

        with pytest.raises(SystemExit):
            cmd_devices(MockArgs())

        err = capsys.readouterr().err
        assert "Error" in err


def _symlinks_supported(tmp_path) -> bool:
    """En Windows crear symlinks exige Developer Mode o privilegios; se sondea."""
    probe = tmp_path / "_symlink_probe"
    try:
        probe.symlink_to(tmp_path)
        probe.unlink()
        return True
    except OSError:
        return False


class TestSetupLinuxPath:
    """Integración de PATH de setup en Linux (symlink $APPIMAGE → ~/.local/bin)."""

    def _fake_home(self, monkeypatch, tmp_path):
        home = tmp_path / "home"
        home.mkdir()
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
        return home

    def _linux_appimage_env(self, monkeypatch, tmp_path):
        appimage = tmp_path / "tts-sidecar-x86_64.AppImage"
        appimage.write_bytes(b"fake appimage")
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("APPIMAGE", str(appimage))
        return appimage

    def test_crea_symlink_desde_appimage(self, monkeypatch, tmp_path, capsys):
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")
        from chatterbox_tts.cli import _integrate_linux_path

        home = self._fake_home(monkeypatch, tmp_path)
        appimage = self._linux_appimage_env(monkeypatch, tmp_path)

        _integrate_linux_path()

        link = home / ".local" / "bin" / "tts-sidecar"
        assert link.is_symlink()
        assert link.resolve() == appimage.resolve()
        assert "symlink creado" in capsys.readouterr().err

    def test_actualiza_symlink_existente_idempotente(self, monkeypatch, tmp_path, capsys):
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")
        from chatterbox_tts.cli import _integrate_linux_path

        home = self._fake_home(monkeypatch, tmp_path)
        appimage = self._linux_appimage_env(monkeypatch, tmp_path)
        link = home / ".local" / "bin" / "tts-sidecar"
        link.parent.mkdir(parents=True)
        link.symlink_to(tmp_path / "otro-viejo.AppImage")

        _integrate_linux_path()
        _integrate_linux_path()  # segunda pasada: idempotente

        assert link.is_symlink()
        assert link.resolve() == appimage.resolve()

    def test_sin_appimage_no_toca_el_filesystem(self, monkeypatch, tmp_path, capsys):
        from chatterbox_tts.cli import _integrate_linux_path

        home = self._fake_home(monkeypatch, tmp_path)
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("APPIMAGE", raising=False)

        _integrate_linux_path()

        assert not (home / ".local").exists()

    def test_no_sobrescribe_archivo_regular(self, monkeypatch, tmp_path, capsys):
        from chatterbox_tts.cli import _integrate_linux_path

        home = self._fake_home(monkeypatch, tmp_path)
        self._linux_appimage_env(monkeypatch, tmp_path)
        link = home / ".local" / "bin" / "tts-sidecar"
        link.parent.mkdir(parents=True)
        link.write_text("no soy un symlink", encoding="utf-8")

        _integrate_linux_path()

        assert not link.is_symlink()
        assert link.read_text(encoding="utf-8") == "no soy un symlink"
        assert "no se modifica" in capsys.readouterr().err

    def test_remove_path_elimina_symlink(self, monkeypatch, tmp_path, capsys):
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")
        from chatterbox_tts.cli import cmd_setup

        home = self._fake_home(monkeypatch, tmp_path)
        link = home / ".local" / "bin" / "tts-sidecar"
        link.parent.mkdir(parents=True)
        link.symlink_to(tmp_path)

        cmd_setup(MockArgs(remove_path=True))

        assert not link.exists()
        assert "Symlink eliminado" in capsys.readouterr().err

    def test_remove_path_sin_symlink_informa(self, monkeypatch, tmp_path, capsys):
        from chatterbox_tts.cli import cmd_setup

        self._fake_home(monkeypatch, tmp_path)

        cmd_setup(MockArgs(remove_path=True))

        assert "No hay nada que quitar" in capsys.readouterr().err

    def test_remove_path_rechaza_archivo_regular(self, monkeypatch, tmp_path, capsys):
        from chatterbox_tts.cli import cmd_setup

        home = self._fake_home(monkeypatch, tmp_path)
        link = home / ".local" / "bin" / "tts-sidecar"
        link.parent.mkdir(parents=True)
        link.write_text("no soy un symlink", encoding="utf-8")

        with pytest.raises(SystemExit):
            cmd_setup(MockArgs(remove_path=True))

        assert link.exists()
        assert "no es un symlink" in capsys.readouterr().err

    def test_advertencia_de_path_usa_rutas_posix(self, monkeypatch, tmp_path, capsys):
        # L-01: la línea sugerida debe ser bash válido (forward slashes),
        # nunca rutas con backslashes que romperían el shell profile.
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")
        from chatterbox_tts.cli import _integrate_linux_path

        self._fake_home(monkeypatch, tmp_path)
        self._linux_appimage_env(monkeypatch, tmp_path)
        # Garantiza que ~/.local/bin no esté en el PATH de la sesión.
        monkeypatch.setenv("PATH", "/usr/bin")

        _integrate_linux_path()

        out = capsys.readouterr().err
        assert 'export PATH="$HOME/.local/bin:$PATH"' in out
        assert "~/.bashrc, ~/.zshrc" in out
        # La línea sugerida y los profiles nunca deben llevar backslashes
        # (las rutas absolutas del symlink sí pueden, si el test corre en Windows).
        assert "$HOME\\.local" not in out and "~\\.bashrc" not in out

    def test_setup_integra_path_antes_de_chequeos_fallidos(self, monkeypatch, tmp_path, capsys):
        # L-02: un host degradado (chequeo FAIL) debe obtener igualmente el
        # comando en el PATH, en paridad con Windows y macOS. Se usa un FAIL
        # no-audio porque el de audio ya no aborta setup (A-01).
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")
        import chatterbox_tts.cli as cli

        home = self._fake_home(monkeypatch, tmp_path)
        appimage = self._linux_appimage_env(monkeypatch, tmp_path)
        monkeypatch.setattr(
            cli, "_environment_checks",
            lambda: [("FAIL", "Chatterbox TTS", "NO INSTALADO")],
        )

        with pytest.raises(SystemExit):
            cli.cmd_setup(MockArgs(remove_path=False))

        link = home / ".local" / "bin" / "tts-sidecar"
        assert link.is_symlink()
        assert link.resolve() == appimage.resolve()


class TestSetupAudioAdvisory:
    """A-01: setup es provisión, no diagnóstico — el FAIL de audio se degrada
    a WARN y la provisión continúa; doctor conserva el FAIL con salida 1."""

    def test_fail_de_audio_no_aborta_setup_y_llega_a_la_provision(self, monkeypatch, capsys):
        import chatterbox_tts.cli as cli

        monkeypatch.setattr(
            cli, "_environment_checks",
            lambda: [("PASS", "Chatterbox TTS", "0.1.7"),
                     ("FAIL", "Audio library", "sin subsistema de sonido")],
        )
        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True):
            cli.cmd_setup(MockArgs(remove_path=False))  # no debe lanzar SystemExit

        out = capsys.readouterr().err
        assert "[WARN] Audio library" in out
        assert "speak --output" in out
        assert "Provisión completa" in out

    def test_fail_no_audio_sigue_abortando_setup(self, monkeypatch, capsys):
        import chatterbox_tts.cli as cli

        monkeypatch.setattr(
            cli, "_environment_checks",
            lambda: [("FAIL", "Chatterbox TTS", "NO INSTALADO")],
        )
        with pytest.raises(SystemExit):
            cli.cmd_setup(MockArgs(remove_path=False))

        assert "[FAIL] Chatterbox TTS" in capsys.readouterr().err

    def test_doctor_conserva_el_fail_de_audio_con_salida_1(self, monkeypatch, capsys):
        import chatterbox_tts.cli as cli

        monkeypatch.setattr(
            cli, "_environment_checks",
            lambda: [("FAIL", "Audio library", "sin subsistema de sonido")],
        )
        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                cli.cmd_doctor(MockArgs(json=False))

        assert exc_info.value.code == 1
        assert "[FAIL] Audio library" in capsys.readouterr().out


class TestManejoDeInterrupciones:
    """R-02: Ctrl+C termina con código 130 y una línea a stderr, sin traceback."""

    def test_ctrl_c_sale_130_sin_traceback(self, monkeypatch, capsys):
        import chatterbox_tts.cli as cli

        def _interrumpe(args):
            raise KeyboardInterrupt

        monkeypatch.setattr(sys, "argv", ["tts-sidecar", "version"])
        monkeypatch.setattr(cli, "cmd_version", _interrumpe)

        with pytest.raises(SystemExit) as exc_info:
            cli.main()

        assert exc_info.value.code == 130
        captured = capsys.readouterr()
        assert "Interrumpido por el usuario." in captured.err
        assert "Traceback" not in captured.err
        assert "KeyboardInterrupt" not in captured.err


class TestCodigosDeSalida:
    """R-06: cada causa de error mapea a su código del contrato público congelado."""

    def test_modelo_faltante_sale_2(self, capsys):
        from chatterbox_tts.cli import _require_model_cached, EXIT_MODEL_MISSING

        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=False):
            with pytest.raises(SystemExit) as exc:
                _require_model_cached()
        assert exc.value.code == EXIT_MODEL_MISSING
        assert "setup" in capsys.readouterr().err

    def test_texto_vacio_sale_4(self):
        from chatterbox_tts.cli import cmd_speak, EXIT_INVALID_INPUT

        with pytest.raises(SystemExit) as exc:
            cmd_speak(MockArgs(text="   ", no_daemon=True))
        assert exc.value.code == EXIT_INVALID_INPUT

    def test_voz_inexistente_sale_3(self):
        from chatterbox_tts.cli import cmd_speak, EXIT_NOT_FOUND

        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True):
            with pytest.raises(SystemExit) as exc:
                cmd_speak(MockArgs(text="hola", voice="voz_inexistente", no_daemon=True))
        assert exc.value.code == EXIT_NOT_FOUND

    def test_daemon_inalcanzable_con_flag_sale_5(self):
        from chatterbox_tts.cli import cmd_speak, EXIT_DAEMON_UNREACHABLE
        from chatterbox_tts.daemon import DaemonIPCError

        def _falla(args, va, sa):
            raise DaemonIPCError("no se puede conectar al daemon")

        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True), \
                patch("chatterbox_tts.cli._synthesize_via_daemon", side_effect=_falla):
            with pytest.raises(SystemExit) as exc:
                cmd_speak(MockArgs(
                    text="hola",
                    voice_audio="/audio/voz.wav",
                    speech_audio="/audio/habla.wav",
                    daemon=True,
                ))
        assert exc.value.code == EXIT_DAEMON_UNREACHABLE

    def test_error_generico_sale_1(self):
        from chatterbox_tts.cli import cmd_devices, EXIT_ERROR

        with patch("chatterbox_tts.audio.get_audio_devices", side_effect=RuntimeError("boom")):
            with pytest.raises(SystemExit) as exc:
                cmd_devices(MockArgs())
        assert exc.value.code == EXIT_ERROR

    def test_voice_add_colision_sale_4(self):
        from chatterbox_tts.cli import cmd_voice_add, EXIT_INVALID_INPUT

        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True), \
                patch("chatterbox_tts.voices.register_voice_files",
                      side_effect=ValueError("La voz 'dup' ya existe")):
            with pytest.raises(SystemExit) as exc:
                cmd_voice_add(MockArgs(name="dup"))
        assert exc.value.code == EXIT_INVALID_INPUT

    def test_daemon_start_fallido_sale_5(self):
        import argparse
        from chatterbox_tts.cli import cmd_daemon, EXIT_DAEMON_UNREACHABLE

        args = argparse.Namespace(action="start", autorestart=False, max_retries=0, port=None)
        manager = MagicMock()
        manager.start.return_value = False

        with patch("chatterbox_tts.model_cache.is_model_cached", return_value=True), \
                patch("chatterbox_tts.daemon.DaemonManager", return_value=manager):
            with pytest.raises(SystemExit) as exc:
                cmd_daemon(args)
        assert exc.value.code == EXIT_DAEMON_UNREACHABLE


class TestCmdCleanup:
    """El comando cleanup borra solo las rutas del proyecto, con confirmación."""

    def _args(self, **kw):
        import argparse
        ns = argparse.Namespace(
            model=kw.get("model", False),
            voices=kw.get("voices", False),
            all=kw.get("all", False),
            dry_run=kw.get("dry_run", False),
            cleanup_parser=MagicMock(),
        )
        return ns

    def _fake_env(self, tmp_path, monkeypatch):
        """Caché HF sintética con las dos carpetas del proyecto, una ajena,
        y un directorio de voces de usuario."""
        hub = tmp_path / "hub"
        propio1 = hub / "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam"
        propio2 = hub / "models--ResembleAI--chatterbox"
        ajeno = hub / "models--otro--proyecto"
        for d in (propio1, propio2, ajeno):
            d.mkdir(parents=True)
        from huggingface_hub import constants
        monkeypatch.setattr(constants, "HF_HUB_CACHE", str(hub))

        voces = tmp_path / "voces"
        (voces / "mi_voz").mkdir(parents=True)
        monkeypatch.setattr("chatterbox_tts.voices.voices_root", lambda: str(voces))
        return propio1, propio2, ajeno, voces

    def test_dry_run_lista_sin_borrar(self, tmp_path, monkeypatch, capsys):
        from chatterbox_tts.cli import cmd_cleanup

        propio1, propio2, ajeno, voces = self._fake_env(tmp_path, monkeypatch)

        cmd_cleanup(self._args(all=True, dry_run=True))

        out = capsys.readouterr().out
        assert "dry-run" in out
        assert str(propio1) in out and str(propio2) in out and str(voces) in out
        assert propio1.exists() and propio2.exists() and voces.exists()

    def test_borrado_selectivo_de_modelo_con_confirmacion(self, tmp_path, monkeypatch, capsys):
        from chatterbox_tts.cli import cmd_cleanup

        propio1, propio2, ajeno, voces = self._fake_env(tmp_path, monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "s")

        cmd_cleanup(self._args(model=True))

        assert not propio1.exists() and not propio2.exists()
        assert ajeno.exists(), "cleanup nunca toca carpetas ajenas de la caché HF"
        assert voces.exists(), "--model no borra las voces de usuario"

    def test_borrado_de_voces_no_toca_el_modelo(self, tmp_path, monkeypatch, capsys):
        from chatterbox_tts.cli import cmd_cleanup

        propio1, propio2, ajeno, voces = self._fake_env(tmp_path, monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "s")

        cmd_cleanup(self._args(voices=True))

        assert not voces.exists()
        assert propio1.exists() and propio2.exists() and ajeno.exists()

    def test_confirmacion_negativa_no_borra(self, tmp_path, monkeypatch, capsys):
        from chatterbox_tts.cli import cmd_cleanup

        propio1, propio2, ajeno, voces = self._fake_env(tmp_path, monkeypatch)
        monkeypatch.setattr("builtins.input", lambda _: "n")

        cmd_cleanup(self._args(all=True))

        assert "Cancelado" in capsys.readouterr().out
        assert propio1.exists() and propio2.exists() and voces.exists()

    def test_sin_flags_muestra_ayuda_y_no_borra(self, tmp_path, monkeypatch, capsys):
        from chatterbox_tts.cli import cmd_cleanup

        propio1, propio2, ajeno, voces = self._fake_env(tmp_path, monkeypatch)
        args = self._args()

        cmd_cleanup(args)

        args.cleanup_parser.print_help.assert_called_once()
        assert propio1.exists() and voces.exists()


class TestCmdSpeakTextVacio:
    def test_text_vacio_se_rechaza(self, capsys):
        from chatterbox_tts.cli import cmd_speak

        with pytest.raises(SystemExit):
            cmd_speak(MockArgs(text="   "))

        err = capsys.readouterr().err
        assert "--text" in err
