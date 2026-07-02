"""Tests de la capa de reproducción y enumeración de audio (SUGGESTION-03)."""

import io
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from chatterbox_tts.audio import SoundDevicePlayer, get_audio_devices


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
    def test_mono_se_reproduce_plano(self):
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=1))
        (audio_np,), kwargs = sd.play.call_args
        assert audio_np.ndim == 1
        assert kwargs["samplerate"] == 24000

    def test_estereo_se_reproduce_con_dos_canales(self):
        """Sin el reshape, un WAV estéreo sonaría como mono al doble de velocidad."""
        sd = MagicMock()
        SoundDevicePlayer(sd).play(_wav_bytes(n_channels=2, n_frames=480))
        (audio_np,), _ = sd.play.call_args
        assert audio_np.shape == (480, 2)


class TestGetAudioDevicesWindows:
    @patch("platform.system", return_value="Windows")
    def test_fallo_de_pycaw_degrada_al_fallback(self, _system):
        """Un fallo COM (RDP, host sin audio) no debe crashear 'devices'."""
        pycaw_mock = MagicMock()
        pycaw_mock.pycaw.AudioUtilities.GetDeviceEnumerator.side_effect = OSError("COM error")
        with patch.dict(sys.modules, {"pycaw": pycaw_mock, "pycaw.pycaw": pycaw_mock.pycaw}):
            devices = get_audio_devices()
        assert devices == [{"id": 0, "name": "Default", "latency": 0.1}]
