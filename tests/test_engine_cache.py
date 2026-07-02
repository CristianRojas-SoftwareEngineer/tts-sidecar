"""Tests de la selección determinista de snapshot en la caché de HuggingFace.

Cubre _resolve_cached_snapshot (refs/main con fallback a mtime) e
is_model_cached sobre una caché sintética en tmp_path.
"""

import os
import time

from chatterbox_tts.model_cache import _resolve_cached_snapshot, is_model_cached

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
        eng.device = "cpu"
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


class TestIsModelCached:
    def _fake_hub(self, tmp_path, monkeypatch):
        """Redirige ~/.cache/huggingface/hub a una caché sintética."""
        hub = tmp_path / "hub"
        hub.mkdir()
        real_expanduser = os.path.expanduser
        monkeypatch.setattr(
            os.path,
            "expanduser",
            lambda p: str(hub) if p == "~/.cache/huggingface/hub" else real_expanduser(p),
        )
        return hub

    def test_sin_cache_devuelve_false(self, tmp_path, monkeypatch):
        self._fake_hub(tmp_path, monkeypatch)
        assert is_model_cached("es-mx-latam") is False

    def test_snapshot_con_checkpoint_devuelve_true(self, tmp_path, monkeypatch):
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        snap = _make_snapshot(model_dir, "abc123")
        _set_ref_main(model_dir, "abc123")
        (snap / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")
        assert is_model_cached("es-mx-latam") is True

    def test_valida_el_snapshot_de_refs_main_no_otro(self, tmp_path, monkeypatch):
        """Con dos snapshots, el checkpoint debe estar en el que apunta refs/main."""
        hub = self._fake_hub(tmp_path, monkeypatch)
        model_dir = hub / ES_MX_FOLDER
        now = time.time()
        stale = _make_snapshot(model_dir, "vieja", mtime=now)
        (stale / "t3_es_mx_latam.safetensors").write_bytes(b"\x00")
        _make_snapshot(model_dir, "actual", mtime=now - 1000)  # sin checkpoint
        _set_ref_main(model_dir, "actual")
        assert is_model_cached("es-mx-latam") is False
