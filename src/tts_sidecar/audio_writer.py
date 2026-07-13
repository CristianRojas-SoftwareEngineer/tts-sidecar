"""
Escritura de audio a WAV (en memoria o a archivo).

Extraído de `ChatterboxEngine`: fusiona `_audio_to_wav` (conversión de
un array/tensor a bytes WAV) y `_save_wav` (escritura a disco).
"""

import io
import wave
from pathlib import Path

from .paths import ensure_parent_dir

import numpy as np


class AudioWriter:
    """Convierte audio a bytes WAV PCM 16-bit mono y opcionalmente los guarda a disco."""

    def write(self, audio_data, sample_rate: int, path=None) -> bytes:
        """Convierte `audio_data` a bytes WAV PCM 16-bit mono.

        Si `path` se da, crea los directorios padre y escribe el archivo; en
        ambos casos retorna los bytes WAV. El sample rate se pasa explícitamente
        (el orquestador lo toma de `tts.sr`) en vez de leerse de `self._tts`.
        """
        if hasattr(audio_data, 'numpy'):
            audio_np = audio_data.numpy()
        elif hasattr(audio_data, 'cpu'):
            audio_np = audio_data.cpu().numpy()
        else:
            audio_np = np.array(audio_data)

        # Asegura que sea float32 en [-1, 1]
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)

        # Maneja la dimensión de batch
        if audio_np.ndim > 1:
            audio_np = audio_np.flatten()

        # Normaliza si hace falta
        max_val = np.abs(audio_np).max()
        if max_val > 1.0:
            audio_np = audio_np / max_val

        wav_bytes = self._to_wav_bytes(audio_np, sample_rate)

        if path is not None:
            ensure_parent_dir(path)
            with open(path, 'wb') as f:
                f.write(wav_bytes)

        return wav_bytes

    @staticmethod
    def _to_wav_bytes(audio_np: np.ndarray, sample_rate: int) -> bytes:
        """Codifica el array float32 aplanado a bytes WAV en un buffer en memoria."""
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16 bits
            wf.setframerate(sample_rate)
            audio_int16 = (audio_np * 32767).astype(np.int16)
            wf.writeframes(audio_int16.tobytes())
        return buffer.getvalue()
