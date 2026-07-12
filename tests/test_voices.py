"""Tests de la resolución y listado de voces (criterio dual-audio).

Una voz solo es válida con sus dos archivos: reference.wav (timbre) y
speech.wav (conditioning). Cubre _resolve_voice_dir y list_voices con la
precedencia usuario→fábrica sobre directorios temporales.
"""

import os

import pytest

from tts_sidecar import voices


@pytest.fixture
def voice_roots(tmp_path, monkeypatch):
    """Redirige las raíces usuario/fábrica a directorios temporales vacíos."""
    user_root = tmp_path / "user"
    factory_root = tmp_path / "factory"
    user_root.mkdir()
    factory_root.mkdir()
    monkeypatch.setattr(voices, "voices_root", lambda: str(user_root))
    monkeypatch.setattr(voices, "factory_voices_root", lambda: str(factory_root))
    return user_root, factory_root


def _make_voice(root, name, reference=True, speech=True):
    voice = root / name
    voice.mkdir()
    if reference:
        (voice / "reference.wav").write_bytes(b"RIFF")
    if speech:
        (voice / "speech.wav").write_bytes(b"RIFF")
    return voice


class TestRegisterVoiceFiles:
    """R-01: el registro de voces valida y copia sin instanciar el motor."""

    def _audios(self, tmp_path):
        ref = tmp_path / "timbre.wav"
        speech = tmp_path / "habla.wav"
        ref.write_bytes(b"RIFF-ref")
        speech.write_bytes(b"RIFF-speech")
        return ref, speech

    def _mock_librosa(self, monkeypatch, fail_on=None):
        import types

        def fake_load(path, sr=None, duration=None):
            if fail_on and str(fail_on) in str(path):
                raise RuntimeError("audio ilegible")
            return ([0.0], sr)

        monkeypatch.setitem(
            __import__("sys").modules, "librosa", types.SimpleNamespace(load=fake_load)
        )

    def test_registers_without_engine(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        ref_path, speech_path = voices.register_voice_files("nueva", str(ref), str(speech))

        assert (user_root / "nueva" / "reference.wav").read_bytes() == b"RIFF-ref"
        assert (user_root / "nueva" / "speech.wav").read_bytes() == b"RIFF-speech"
        assert ref_path.endswith("reference.wav")
        assert speech_path.endswith("speech.wav")

    def test_unreadable_audio_leaves_no_broken_voice(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch, fail_on="habla.wav")

        with pytest.raises(ValueError, match="no es cargable"):
            voices.register_voice_files("rota", str(ref), str(speech))

        assert not (user_root / "rota").exists()

    def test_collision_without_force_is_rejected(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        _make_voice(user_root, "existente")
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        with pytest.raises(ValueError, match="ya existe"):
            voices.register_voice_files("existente", str(ref), str(speech))

    def test_force_overwrites(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        _make_voice(user_root, "existente")
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        voices.register_voice_files("existente", str(ref), str(speech), force=True)

        assert (user_root / "existente" / "reference.wav").read_bytes() == b"RIFF-ref"


class TestResolveVoiceDir:
    def test_complete_voice_resolves(self, voice_roots):
        user_root, _ = voice_roots
        expected = _make_voice(user_root, "mia")
        assert voices._resolve_voice_dir("mia") == str(expected)

    def test_reference_only_voice_does_not_resolve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", speech=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_speech_only_voice_does_not_resolve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", reference=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_user_precedence_over_factory(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(factory_root, "default")
        expected = _make_voice(user_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)

    def test_incomplete_user_falls_back_to_factory(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default", speech=False)
        expected = _make_voice(factory_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)


class TestListVoices:
    def test_lists_only_complete_voices(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "completa")
        _make_voice(user_root, "sin_speech", speech=False)
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["completa", "default"]

    def test_no_duplicates_between_levels(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default")
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["default"]


class TestNameSanitization:
    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs", "/abs", "", "."])
    def test_voice_dir_rejects_malicious_names(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_dir(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs"])
    def test_remove_voice_rejects_malicious_names(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.remove_voice(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b"])
    def test_voice_paths_rejects_malicious_names(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_paths(name)

    def test_remove_voice_does_not_delete_non_voice_dirs(self, voice_roots):
        user_root, _ = voice_roots
        intruso = user_root / "no_es_voz"
        intruso.mkdir()
        (intruso / "datos.txt").write_text("importante")
        assert voices.remove_voice("no_es_voz") is False
        assert intruso.exists()

    def test_remove_voice_deletes_valid_voice(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia")
        assert voices.remove_voice("mia") is True
        assert not (user_root / "mia").exists()


class TestCmdVoiceRemoveIOErrors:
    """WARNING-01: cmd_voice_remove distingue un archivo en uso de un error genérico."""

    def _args(self, name):
        import argparse
        return argparse.Namespace(name=name)

    def test_permission_error_gives_different_message_and_exits_1(self, voice_roots, monkeypatch, capsys):
        import shutil as shutil_module
        from tts_sidecar import cli

        user_root, _ = voice_roots
        _make_voice(user_root, "mia")

        def _raise_permission_error(path):
            raise PermissionError("[WinError 32] archivo en uso")

        monkeypatch.setattr(shutil_module, "rmtree", _raise_permission_error)

        with pytest.raises(SystemExit) as exc_info:
            cli.cmd_voice_remove(self._args("mia"))

        assert exc_info.value.code == 1
        err = capsys.readouterr().err
        assert "en uso" in err
        assert "no encontrada" not in err

    def test_nonexistent_voice_gives_different_message(self, voice_roots, capsys):
        from tts_sidecar import cli

        with pytest.raises(SystemExit) as exc_info:
            cli.cmd_voice_remove(self._args("no_existe"))

        # Contrato de exit codes (T9/R-06): voz no encontrada → EXIT_NOT_FOUND (3),
        # distinto del EXIT_ERROR (1) genérico del caso PermissionError de arriba.
        assert exc_info.value.code == 3
        err = capsys.readouterr().err
        assert "no encontrada" in err
        assert "en uso" not in err


class TestCapitalizationCollision:
    """SUGGESTION-06: los nombres de voz se normalizan a minúsculas.

    En filesystems case-insensitive (macOS APFS, Docker volumes sobre NTFS),
    `MiVoz` y `mivoz` colisionan. La solución implementada normaliza todos
    los nombres a minúsculas antes de cualquier operación de filesystem.
    """

    def test_names_differing_only_in_case(self, voice_roots):
        user_root, _ = voice_roots
        # La normalización a minúsculas hace que el nombre físico del
        # directorio sea siempre minúscula. Se crea con el nombre normalizado.
        _make_voice(user_root, "mivoz")

        # list_voices devuelve siempre minúsculas por la normalización.
        assert set(voices.list_voices()) == {"mivoz"}

        # voice_dir normaliza, por lo que cualquier variante de mayúsculas
        # devuelve el mismo directorio.
        assert voices.voice_dir("MiVoz") == voices.voice_dir("mivoz")


def test_voice_paths_of_listed_voice_never_fails(voice_roots):
    """La invariante que motivó el cambio: toda voz listada es resoluble."""
    user_root, _ = voice_roots
    _make_voice(user_root, "completa")
    _make_voice(user_root, "sin_speech", speech=False)
    for name in voices.list_voices():
        ref, speech = voices.voice_paths(name)
        assert ref.endswith("reference.wav")
        assert speech.endswith("speech.wav")


def test_factory_default_voice_is_bundled():
    """La voz de fábrica `default` viaja en el bundle (sin modelo).

    Valida a nivel de paquete que la voz por defecto está empaquetada, sin
    instanciar el engine (las voces de fábrica son de solo lectura y no
    requieren el modelo Chatterbox). No usa el fixture `voice_roots`, que
    redirige las raíces a directorios vacíos y ocultaría la voz de fábrica.
    """
    assert "default" in voices.list_voices()
