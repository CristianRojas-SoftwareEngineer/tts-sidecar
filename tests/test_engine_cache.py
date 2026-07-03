"""Tests de la selección determinista de snapshot en la caché de HuggingFace.

Cubre _resolve_cached_snapshot (refs/main con fallback a mtime), la resolución
de hub_cache_path (precedencia HF_HUB_CACHE/HF_HOME/default) e is_model_cached
sobre una caché sintética en tmp_path.
"""

import contextlib
import importlib
import os
import time
from pathlib import Path

from chatterbox_tts.model_cache import (
    _resolve_cached_snapshot,
    hub_cache_path,
    is_model_cached,
)

ES_MX_FOLDER = "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam"


def _make_snapshot(model_dir, name, mtime=None):
    snap = model_dir / "snapshots" / name
    snap.mkdir(parents=True)
    if mtime is not None:
        os.utime(snap, (mtime, mtime))
    return snap


def _set_ref_main(model_dir, revision):
    refs = model_dir / "refs"
    refs.mkdir(exist_ok=True)
    (refs / "main").write_text(revision + "\n", encoding="utf-8")


class TestResolveCachedSnapshot:
    def test_sin_directorio_devuelve_none(self, tmp_path):
        assert _resolve_cached_snapshot(tmp_path / "inexistente") is None

    def test_snapshots_vacio_devuelve_none(self, tmp_path):
        (tmp_path / "snapshots").mkdir()
        assert _resolve_cached_snapshot(tmp_path) is None

    def test_refs_main_gana_sobre_mtime(self, tmp_path):
        now = time.time()
        _make_snapshot(tmp_path, "aaa", mtime=now)  # el más reciente
        target = _make_snapshot(tmp_path, "bbb", mtime=now - 1000)
        _set_ref_main(tmp_path, "bbb")
        assert _resolve_cached_snapshot(tmp_path) == target

    def test_sin_refs_elige_mtime_mas_reciente(self, tmp_path):
        now = time.time()
        _make_snapshot(tmp_path, "vieja", mtime=now - 1000)
        newest = _make_snapshot(tmp_path, "nueva", mtime=now)
        assert _resolve_cached_snapshot(tmp_path) == newest

    def test_ref_a_snapshot_ausente_cae_a_mtime(self, tmp_path):
        only = _make_snapshot(tmp_path, "aaa")
        _set_ref_main(tmp_path, "borrada")
        assert _resolve_cached_snapshot(tmp_path) == only


class TestConditionalsCorruptos:
    def _engine_sin_modelo(self):
        """Instancia de ChatterboxEngine sin cargar el modelo real."""
        from chatterbox_tts.engine import ChatterboxEngine

        eng = ChatterboxEngine.__new__(ChatterboxEngine)
        eng.compute_backend = "cpu"
        return eng

    def test_load_devuelve_false_con_archivo_corrupto(self, tmp_path):
        eng = self._engine_sin_modelo()
        eng._tts = object()
        (tmp_path / "conditionals.pt").write_bytes(b"no es un checkpoint")
        assert eng.load_precomputed_conditionals(str(tmp_path)) is False

    def test_speak_recomputa_con_conditionals_corruptos(self, tmp_path, monkeypatch):
        from chatterbox_tts.engine import ChatterboxEngine

        eng = self._engine_sin_modelo()
        voice = tmp_path / "voz"
        voice.mkdir()
        (voice / "conditionals.pt").write_bytes(b"basura")
        speech = voice / "speech.wav"
        speech.write_bytes(b"RIFF")

        recomputos = []
        eng._prepare_conditionals_multi = lambda **kw: recomputos.append(kw)

        class FakeTTS:
            conds = None

            def generate(self, text, **kwargs):
                return [0.0]

        eng._tts = FakeTTS()
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")

        assert eng.speak("hola", speech_audio=str(speech)) == b"RIFF"
        assert recomputos, "speak debe recomputar los conditionals cuando el .pt es corrupto"


class TestParametrosUnificados:
    def _engine_stub(self, tmp_path):
        from chatterbox_tts.engine import ChatterboxEngine

        eng = ChatterboxEngine.__new__(ChatterboxEngine)
        eng.compute_backend = "cpu"
        eng._conds_cache_key = None

        class FakeTTS:
            conds = None

            def generate(self, text, **kwargs):
                self.last_generate_kwargs = kwargs
                return [0.0]

        eng._tts = FakeTTS()
        return eng

    def test_get_instance_incluye_models_dir_en_la_clave(self, monkeypatch):
        from chatterbox_tts.engine import ChatterboxEngine

        monkeypatch.setattr(ChatterboxEngine, "_cache", {})
        monkeypatch.setattr(
            ChatterboxEngine, "__init__", lambda self, model, compute_backend, models_dir=None: None
        )
        a = ChatterboxEngine.get_instance(models_dir="/ruta/a")
        b = ChatterboxEngine.get_instance(models_dir="/ruta/b")
        assert a is not b
        assert ChatterboxEngine.get_instance(models_dir="/ruta/a") is a

    def test_modo_directo_usa_exaggeration_unificada(self, tmp_path, monkeypatch):
        from chatterbox_tts.engine import ChatterboxEngine

        eng = self._engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")
        speech = tmp_path / "speech.wav"
        speech.write_bytes(b"RIFF")
        eng._prepare_conditionals_multi = lambda **kw: None

        eng.speak("hola", speech_audio=str(speech))

        assert eng._tts.last_generate_kwargs["exaggeration"] == ChatterboxEngine.EXAGGERATION

    def test_memoizacion_de_conditionals_por_mtime(self, tmp_path, monkeypatch):
        import os
        from chatterbox_tts.engine import ChatterboxEngine

        eng = self._engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")

        voice = tmp_path / "voz"
        voice.mkdir()
        conds = voice / "conditionals.pt"
        conds.write_bytes(b"valido")
        speech = voice / "speech.wav"
        speech.write_bytes(b"RIFF")

        loads = []

        def fake_load(voice_dir):
            loads.append(voice_dir)
            eng._tts.conds = object()
            return True

        eng.load_precomputed_conditionals = fake_load

        eng.speak("hola", speech_audio=str(speech))
        eng.speak("hola otra vez", speech_audio=str(speech))
        assert len(loads) == 1, "la segunda síntesis de la misma voz no debe releer disco"

        # Un conditionals.pt regenerado (mtime nuevo) invalida la memoización
        mtime = os.path.getmtime(conds) + 10
        os.utime(conds, (mtime, mtime))
        eng.speak("hola de nuevo", speech_audio=str(speech))
        assert len(loads) == 2


@contextlib.contextmanager
def _hf_env(**env):
    """Fija las variables de entorno de HF y recarga constants; restaura al salir.

    huggingface_hub.constants computa HF_HUB_CACHE en tiempo de import, así que
    cambiar el entorno exige recargar el módulo para que el cambio surta efecto
    (y recargarlo de nuevo al salir para no contaminar otros tests).
    """
    from huggingface_hub import constants

    keys = ("HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "XDG_CACHE_HOME")
    saved = {k: os.environ.get(k) for k in keys}
    try:
        for k in keys:
            os.environ.pop(k, None)
        for k, v in env.items():
            os.environ[k] = v
        importlib.reload(constants)
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        importlib.reload(constants)


class TestHubCachePath:
    def test_hf_hub_cache_tiene_precedencia(self, tmp_path):
        custom = tmp_path / "hub-custom"
        with _hf_env(HF_HUB_CACHE=str(custom), HF_HOME=str(tmp_path / "hf-home")):
            assert hub_cache_path() == custom

    def test_hf_home_define_la_raiz(self, tmp_path):
        home = tmp_path / "hf-home"
        with _hf_env(HF_HOME=str(home)):
            assert hub_cache_path() == home / "hub"

    def test_fallback_al_default(self):
        with _hf_env():
            assert hub_cache_path() == Path("~/.cache/huggingface/hub").expanduser()


class TestIsModelCached:
    def _fake_hub(self, tmp_path, monkeypatch):
        """Redirige la caché de HuggingFace a una caché sintética."""
        hub = tmp_path / "hub"
        hub.mkdir()
        from huggingface_hub import constants
        monkeypatch.setattr(constants, "HF_HUB_CACHE", str(hub))
        return hub

    def test_sin_cache_devuelve_false(self, tmp_path, monkeypatch):
        self._fake_hub(tmp_path, monkeypatch)
        assert is_model_cached("es-mx-latam") is False

    def test_snapshot_con_checkpoint_y_ve_devuelve_true(self, tmp_path, monkeypatch):
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        snap = _make_snapshot(model_dir, "abc123")
        _set_ref_main(model_dir, "abc123")
        (snap / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")
        (snap / "ve.safetensors").write_bytes(b"\x00")
        assert is_model_cached("es-mx-latam") is True

    def test_t3_presente_sin_ve_devuelve_false(self, tmp_path, monkeypatch):
        """El Voice Encoder es obligatorio: sin ve.safetensors resoluble, el
        primer speak dispararía una descarga (fuga de la promesa offline)."""
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        snap = _make_snapshot(model_dir, "abc123")
        _set_ref_main(model_dir, "abc123")
        (snap / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")
        assert is_model_cached("es-mx-latam") is False

    def test_ve_en_el_modelo_base_tambien_cuenta(self, tmp_path, monkeypatch):
        """ve.safetensors puede residir en la caché del modelo base."""
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        snap = _make_snapshot(model_dir, "abc123")
        _set_ref_main(model_dir, "abc123")
        (snap / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")

        base_dir = hub / "models--ResembleAI--chatterbox"
        base_snap = _make_snapshot(base_dir, "base01")
        _set_ref_main(base_dir, "base01")
        (base_snap / "ve.safetensors").write_bytes(b"\x00")
        assert is_model_cached("es-mx-latam") is True

    def test_valida_el_snapshot_de_refs_main_no_otro(self, tmp_path, monkeypatch):
        """Con dos snapshots, el checkpoint debe estar en el que apunta refs/main."""
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        now = time.time()
        stale = _make_snapshot(model_dir, "vieja", mtime=now)
        (stale / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")
        (stale / "ve.safetensors").write_bytes(b"\x00")
        _make_snapshot(model_dir, "actual", mtime=now - 1000)  # sin checkpoint
        _set_ref_main(model_dir, "actual")
        assert is_model_cached("es-mx-latam") is False
