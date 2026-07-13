"""Tests aislados del límite de seguridad del sandbox del daemon (S3-02).

Cubre como unidades, sin el stack FastAPI completo:
- `voices.allowed_audio_dirs()` y `voices.daemon_session_dir()` (fuente de la
  frontera de confianza), y
- `server._validate_audio_path()` (frontera extraída de `synthesize`), con
  matrices dentro/fuera y symlinks inward/outward.

Todos los casos son deterministas (basados en `tmp_path`) y no requieren el
modelo Chatterbox ni red. Los tests de symlink se omiten donde el SO no permite
crearlos (Windows sin Developer Mode).
"""

import os
import sys
import tempfile

import pytest
from fastapi import HTTPException
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _symlinks_supported(tmp_path) -> bool:
    """En Windows crear symlinks exige Developer Mode o privilegios; se sondea.

    Espejo de `tests/test_cli.py:_symlinks_supported` para omitir los tests de
    symlink en entornos sin soporte en lugar de fallar.
    """
    probe = tmp_path / "_symlink_probe"
    try:
        probe.symlink_to(tmp_path)
        probe.unlink()
        return True
    except OSError:
        return False


def _valid_wav_bytes() -> bytes:
    """Header RIFF/WAVE de 12 bytes + algo de relleno (no es un WAV real)."""
    return b"RIFF\x00\x00\x00\x00WAVE" + b"\x00" * 24


class TestAllowedAudioDirs:
    """Frontera de confianza: composición exacta de `allowed_audio_dirs()`."""

    def test_allowed_audio_dirs_returns_three_dirs(self):
        from tts_sidecar import voices

        assert voices.allowed_audio_dirs() == [
            voices.voices_root(),
            voices.factory_voices_root(),
            voices.daemon_session_dir(),
        ]

    def test_allowed_audio_dirs_excludes_general_tempdir(self):
        from tts_sidecar import voices

        # El tempdir compartido general NO entra en la frontera: acotarlo evita
        # que cualquier proceso local plante un .wav en %TEMP% para que el
        # daemon lo lea (WARNING-02).
        assert tempfile.gettempdir() not in voices.allowed_audio_dirs()

    def test_daemon_session_dir_is_namespaced(self):
        from tts_sidecar import voices

        # Namespaceado bajo <tempdir>/tts-sidecar, SIN aislamiento por PID.
        assert voices.daemon_session_dir() == os.path.join(
            tempfile.gettempdir(), "tts-sidecar"
        )
        assert voices.daemon_session_dir() != tempfile.gettempdir()

    def test_ensure_daemon_session_dir_matches(self):
        from tts_sidecar import voices

        target = voices.ensure_daemon_session_dir()
        assert target == voices.daemon_session_dir()
        assert os.path.isdir(target)


class TestValidateAudioPath:
    """Frontera extraída de `synthesize` (`_validate_audio_path`).

    Cubre rechazo fuera de `allowed_dirs`, symlink que escapa, aceptación de
    symlink inward, retorno del path canónico, y rechazo por extensión/header
    WAV inválidos.
    """

    def test_rejects_path_outside_allowed_dirs(self, tmp_path):
        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        outside = tmp_path / "fuera"
        outside.mkdir()
        wav = outside / "voz.wav"
        wav.write_bytes(_valid_wav_bytes())

        allowed_dirs = [os.path.realpath(str(allowed))]
        with pytest.raises(HTTPException) as exc:
            server._validate_audio_path(str(wav), "speech_audio", allowed_dirs)
        assert exc.value.status_code == 400

    def test_rejects_symlink_escaping_allowed_dir(self, tmp_path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")

        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        outside = tmp_path / "fuera"
        outside.mkdir()
        outside_wav = outside / "escaped.wav"
        outside_wav.write_bytes(_valid_wav_bytes())

        # Symlink DENTRO de allowed_dirs que apunta a un archivo FUERA: el
        # realpath debe resolverlo fuera y rechazarlo (contención WARNING-02).
        link = allowed / "escape.wav"
        link.symlink_to(outside_wav)

        allowed_dirs = [os.path.realpath(str(allowed))]
        with pytest.raises(HTTPException) as exc:
            server._validate_audio_path(str(link), "speech_audio", allowed_dirs)
        assert exc.value.status_code == 400

    def test_accepts_symlink_inward(self, tmp_path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("el entorno no permite crear symlinks")

        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        inner_wav = allowed / "inner.wav"
        inner_wav.write_bytes(_valid_wav_bytes())

        # Symlink DENTRO de allowed_dirs que apunta a un wav también dentro:
        # debe aceptarlo y devolver el realpath del wav interior.
        link = allowed / "inward.wav"
        link.symlink_to(inner_wav)

        allowed_dirs = [os.path.realpath(str(allowed))]
        result = server._validate_audio_path(str(link), "speech_audio", allowed_dirs)
        assert result == os.path.realpath(str(inner_wav))

    def test_returns_canonical_realpath(self, tmp_path):
        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        wav = allowed / "voz.wav"
        wav.write_bytes(_valid_wav_bytes())

        # Para una ruta válida, la función devuelve os.path.realpath(path),
        # resuelto una sola vez, para que el engine lo reutilice sin re-validar.
        allowed_dirs = [os.path.realpath(str(allowed))]
        result = server._validate_audio_path(str(wav), "speech_audio", allowed_dirs)
        assert result == os.path.realpath(str(wav))

    def test_rejects_non_wav_extension_or_missing_file(self, tmp_path):
        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        allowed_dirs = [os.path.realpath(str(allowed))]

        # Extensión distinta de .wav, aunque el contenido sea WAV válido.
        not_wav = allowed / "voz.txt"
        not_wav.write_bytes(_valid_wav_bytes())
        with pytest.raises(HTTPException) as exc:
            server._validate_audio_path(str(not_wav), "speech_audio", allowed_dirs)
        assert exc.value.status_code == 400

        # Archivo inexistente.
        missing = allowed / "no_existe.wav"
        with pytest.raises(HTTPException) as exc2:
            server._validate_audio_path(str(missing), "speech_audio", allowed_dirs)
        assert exc2.value.status_code == 400

    def test_rejects_invalid_wav_header(self, tmp_path):
        from tts_sidecar.daemon import server

        allowed = tmp_path / "permitido"
        allowed.mkdir()
        # Extensión .wav pero header distinto de RIFF/WAVE.
        wav = allowed / "voz.wav"
        wav.write_bytes(b"no soy un wav")

        allowed_dirs = [os.path.realpath(str(allowed))]
        with pytest.raises(HTTPException) as exc:
            server._validate_audio_path(str(wav), "speech_audio", allowed_dirs)
        assert exc.value.status_code == 400
