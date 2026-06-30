"""Tests for CLI commands."""

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
        self.model = kwargs.get("model", "es-latam")
        self.device = kwargs.get("device", "cpu")
        self.name = kwargs.get("name", "testcli")
        self.reference = kwargs.get("reference", "ref.wav")
        self.speech = kwargs.get("speech", "speech.wav")
        self.daemon = kwargs.get("daemon", False)
        self.no_daemon = kwargs.get("no_daemon", False)
        self.json = kwargs.get("json", False)


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
        from chatterbox_tts.cli import _resolve_voice_paths
        args = MockArgs(
            voice_audio="/path/to/voice.wav",
            speech_audio="/path/to/speech.wav"
        )
        va, sa = _resolve_voice_paths(args)
        assert va == "/path/to/voice.wav"
        assert sa == "/path/to/speech.wav"


class TestCmdVoiceList:
    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_lists_voices(self, mock_list_voices, capsys):
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = ["crist", "testcli"]

        cmd_voice_list(MockArgs())

        out = capsys.readouterr().out
        assert "Registered voices:" in out
        assert "crist" in out
        assert "testcli" in out

    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_empty(self, mock_list_voices, capsys):
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = []

        cmd_voice_list(MockArgs())

        out = capsys.readouterr().out
        assert "No voices registered" in out

    @patch("chatterbox_tts.voices.list_voices")
    def test_cmd_voice_list_json(self, mock_list_voices, capsys):
        import json
        from chatterbox_tts.cli import cmd_voice_list

        mock_list_voices.return_value = ["crist", "testcli"]

        cmd_voice_list(MockArgs(json=True))

        out = capsys.readouterr().out
        assert json.loads(out) == {"voices": ["crist", "testcli"]}


class TestCmdVoiceAdd:
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    def test_cmd_voice_add_success(self, mock_engine_cls, capsys):
        from chatterbox_tts.cli import cmd_voice_add

        mock_engine = MagicMock()
        mock_engine.add_voice.return_value = ("/path/to/ref.wav", "/path/to/speech.wav")
        mock_engine_cls.return_value = mock_engine

        cmd_voice_add(MockArgs(name="newvoice", reference="ref.wav", speech="speech.wav"))

        out = capsys.readouterr().out
        assert "Voice 'newvoice' registered" in out
        mock_engine.add_voice.assert_called_once()


class TestCmdVoiceRemove:
    @patch("chatterbox_tts.voices.remove_voice")
    def test_cmd_voice_remove_success(self, mock_remove_voice, capsys):
        from chatterbox_tts.cli import cmd_voice_remove

        mock_remove_voice.return_value = True

        cmd_voice_remove(MockArgs(name="testcli"))

        out = capsys.readouterr().out
        assert "Voice 'testcli' removed" in out

    @patch("chatterbox_tts.voices.remove_voice")
    def test_cmd_voice_remove_not_found(self, mock_remove_voice, capsys):
        from chatterbox_tts.cli import cmd_voice_remove

        mock_remove_voice.return_value = False

        with pytest.raises(SystemExit):
            cmd_voice_remove(MockArgs(name="nonexistent"))


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
        assert "Audio output devices:" in out
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


class TestCmdSpeak:
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    def test_cmd_speak_saves_with_output(self, mock_engine_cls, capsys):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine

        cmd_speak(MockArgs(text="hola", output="out.wav", no_daemon=True))

        # engine.speak receives the output path so it writes the file itself
        _, kwargs = engine.speak.call_args
        assert kwargs["output_path"] == "out.wav"
        out = capsys.readouterr().out
        assert "Audio saved to: out.wav" in out

    @patch("chatterbox_tts.audio.AudioPlayer")
    @patch("chatterbox_tts.engine.ChatterboxEngine")
    def test_cmd_speak_plays_without_output(self, mock_engine_cls, mock_player_cls):
        from chatterbox_tts.cli import cmd_speak

        engine = MagicMock()
        engine.speak.return_value = b"RIFF"
        mock_engine_cls.get_instance.return_value = engine
        player = MagicMock()
        mock_player_cls.return_value = player

        cmd_speak(MockArgs(text="hola", output=None, no_daemon=True))

        player.play.assert_called_once_with(b"RIFF")
