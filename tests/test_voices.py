"""Tests de la resolución y listado de voces (criterio dual-audio).

Una voz solo es válida con sus dos archivos: reference.wav (timbre) y
speech.wav (conditioning). Cubre _resolve_voice_dir y list_voices con la
precedencia usuario→fábrica sobre directorios temporales.
"""

import pytest

from chatterbox_tts import voices


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

    def test_registra_sin_motor(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        ref_path, speech_path = voices.register_voice_files("nueva", str(ref), str(speech))

        assert (user_root / "nueva" / "reference.wav").read_bytes() == b"RIFF-ref"
        assert (user_root / "nueva" / "speech.wav").read_bytes() == b"RIFF-speech"
        assert ref_path.endswith("reference.wav")
        assert speech_path.endswith("speech.wav")

    def test_audio_ilegible_no_deja_voz_rota(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch, fail_on="habla.wav")

        with pytest.raises(ValueError, match="no es cargable"):
            voices.register_voice_files("rota", str(ref), str(speech))

        assert not (user_root / "rota").exists()

    def test_colision_sin_force_se_rechaza(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        _make_voice(user_root, "existente")
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        with pytest.raises(ValueError, match="ya existe"):
            voices.register_voice_files("existente", str(ref), str(speech))

    def test_force_sobrescribe(self, voice_roots, tmp_path, monkeypatch):
        user_root, _ = voice_roots
        _make_voice(user_root, "existente")
        ref, speech = self._audios(tmp_path)
        self._mock_librosa(monkeypatch)

        voices.register_voice_files("existente", str(ref), str(speech), force=True)

        assert (user_root / "existente" / "reference.wav").read_bytes() == b"RIFF-ref"


class TestResolveVoiceDir:
    def test_voz_completa_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        expected = _make_voice(user_root, "mia")
        assert voices._resolve_voice_dir("mia") == str(expected)

    def test_voz_solo_reference_no_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", speech=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_voz_solo_speech_no_se_resuelve(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia", reference=False)
        assert voices._resolve_voice_dir("mia") is None

    def test_precedencia_usuario_sobre_fabrica(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(factory_root, "default")
        expected = _make_voice(user_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)

    def test_usuario_incompleta_cae_a_fabrica(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default", speech=False)
        expected = _make_voice(factory_root, "default")
        assert voices._resolve_voice_dir("default") == str(expected)


class TestListVoices:
    def test_lista_solo_voces_completas(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "completa")
        _make_voice(user_root, "sin_speech", speech=False)
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["completa", "default"]

    def test_sin_duplicados_entre_niveles(self, voice_roots):
        user_root, factory_root = voice_roots
        _make_voice(user_root, "default")
        _make_voice(factory_root, "default")
        assert voices.list_voices() == ["default"]


class TestSanitizacionDeNombres:
    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs", "/abs", "", "."])
    def test_voice_dir_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_dir(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b", "a\\b", "C:\\abs"])
    def test_remove_voice_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.remove_voice(name)

    @pytest.mark.parametrize("name", ["..", "../x", "a/b"])
    def test_voice_paths_rechaza_nombres_maliciosos(self, voice_roots, name):
        with pytest.raises(ValueError):
            voices.voice_paths(name)

    def test_remove_voice_no_borra_directorios_que_no_son_voces(self, voice_roots):
        user_root, _ = voice_roots
        intruso = user_root / "no_es_voz"
        intruso.mkdir()
        (intruso / "datos.txt").write_text("importante")
        assert voices.remove_voice("no_es_voz") is False
        assert intruso.exists()

    def test_remove_voice_borra_voz_valida(self, voice_roots):
        user_root, _ = voice_roots
        _make_voice(user_root, "mia")
        assert voices.remove_voice("mia") is True
        assert not (user_root / "mia").exists()


class TestCmdVoiceRemoveErroresDeIO:
    """WARNING-01: cmd_voice_remove distingue un archivo en uso de un error genérico."""

    def _args(self, name):
        import argparse
        return argparse.Namespace(name=name)

    def test_permission_error_da_mensaje_distinto_y_sale_1(self, voice_roots, monkeypatch, capsys):
        import shutil as shutil_module
        from chatterbox_tts import cli

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

    def test_voz_inexistente_da_mensaje_distinto(self, voice_roots, capsys):
        from chatterbox_tts import cli

        with pytest.raises(SystemExit) as exc_info:
            cli.cmd_voice_remove(self._args("no_existe"))

        # Contrato de exit codes (T9/R-06): voz no encontrada → EXIT_NOT_FOUND (3),
        # distinto del EXIT_ERROR (1) genérico del caso PermissionError de arriba.
        assert exc_info.value.code == 3
        err = capsys.readouterr().err
        assert "no encontrada" in err
        assert "en uso" not in err


class TestColisionPorCapitalizacion:
    """SUGGESTION-06: `_validate_voice_name` no normaliza mayúsculas/minúsculas.

    Este test confirma o descarta, sin modificar `voices.py`, si dos nombres
    que difieren solo en capitalización colisionan en el filesystem donde
    corre la suite. El resultado es evidencia para decidir si se introduce
    normalización a minúsculas en una iteración posterior.
    """

    def test_nombres_que_difieren_solo_en_mayusculas(self, voice_roots):
        user_root, _ = voice_roots
        dir_a = _make_voice(user_root, "MiVoz")

        try:
            dir_b = _make_voice(user_root, "mivoz")
        except FileExistsError:
            # Filesystem case-insensitive (Windows/macOS por defecto): el
            # segundo mkdir() colisiona con el directorio ya creado para
            # "MiVoz". Además, voice_dir("mivoz") rechaza el nombre porque su
            # defensa anti-escape (realpath) resuelve al nombre ya presente
            # en disco ("MiVoz"), no al nombre pedido ("mivoz") — confirma la
            # colisión también a nivel de voices.py, no solo del filesystem.
            with pytest.raises(ValueError, match="escapa del registro de voces"):
                voices.voice_dir("mivoz")
            return

        # Filesystem case-sensitive (Linux por defecto): ambas voces coexisten
        # como directorios distintos.
        assert dir_a != dir_b
        assert voices.voice_dir("MiVoz") != voices.voice_dir("mivoz")
        assert set(voices.list_voices()) == {"MiVoz", "mivoz"}


def test_voice_paths_de_voz_listada_nunca_falla(voice_roots):
    """La invariante que motivó el cambio: toda voz listada es resoluble."""
    user_root, _ = voice_roots
    _make_voice(user_root, "completa")
    _make_voice(user_root, "sin_speech", speech=False)
    for name in voices.list_voices():
        ref, speech = voices.voice_paths(name)
        assert ref.endswith("reference.wav")
        assert speech.endswith("speech.wav")
