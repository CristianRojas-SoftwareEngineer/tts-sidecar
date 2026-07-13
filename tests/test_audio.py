"""Tests de la capa de reproducción y enumeración de audio."""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from tts_sidecar.audio import (
    SoundDevicePlayer,
    get_audio_devices,
    get_audio_devices_with_status,
)


def _wav_bytes(n_channels: int, n_frames: int = 480, sample_rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = np.zeros(n_frames * n_channels, dtype=np.int16)
        wf.writeframes(frames.tobytes())
    return buffer.getvalue()


class TestSoundDevicePlayer:
    def test_mono_plays_flat(self):
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=1))
        (audio_np,), kwargs = sd.play.call_args
        assert audio_np.ndim == 1
        assert kwargs["samplerate"] == 24000

    def test_stereo_plays_with_two_channels(self):
        """Sin el reshape, un WAV estéreo sonaría como mono al doble de velocidad."""
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=2, n_frames=480))
        (audio_np,), _ = sd.play.call_args
        assert audio_np.shape == (480, 2)

    def test_rejects_sample_width_other_than_16_bits(self):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(3)  # 24 bits, no soportado
            wf.setframerate(24000)
            wf.writeframes(b"\x00" * 3 * 480)
        with pytest.raises(ValueError, match="ancho de muestra"):
            SoundDevicePlayer(MagicMock()).play(buffer.getvalue())


class TestGetAudioDevicesWindows:
    @patch("platform.system", return_value="Windows")
    def test_pycaw_failure_degrades_to_fallback(self, _system):
        """Un fallo COM (RDP, host sin audio) no debe crashear 'devices'."""
        pycaw_mock = MagicMock()
        pycaw_mock.pycaw.AudioUtilities.GetDeviceEnumerator.side_effect = OSError("COM error")
        with patch.dict(sys.modules, {"pycaw": pycaw_mock, "pycaw.pycaw": pycaw_mock.pycaw}):
            devices = get_audio_devices()
        assert devices == [{"id": 0, "name": "Default", "latency": 0.1}]


class TestGetAudioDevicesLinuxMacOS:
    @patch("platform.system", return_value="Linux")
    def test_non_import_error_failure_degrades_to_fallback(self, _system, caplog):
        """Un PortAudioError en tiempo de enumeración no debe crashear 'devices'.

        Además de degradar, el fallo queda registrado a nivel debug con
        traza, en vez de tragarse en silencio.
        """
        import logging

        sd_mock = MagicMock()
        sd_mock.query_devices.side_effect = OSError("PortAudio error")
        with patch.dict(sys.modules, {"sounddevice": sd_mock}):
            with caplog.at_level(logging.DEBUG, logger="tts_sidecar.audio"):
                devices, degraded = get_audio_devices_with_status()
        assert degraded is True
        assert devices == [{"id": 0, "name": "Default", "latency": 0.1}]
        assert any(
            "enumeración" in r.message.lower() and r.exc_info for r in caplog.records
        ), "el fallo de enumeración debe registrar un debug con traza"
