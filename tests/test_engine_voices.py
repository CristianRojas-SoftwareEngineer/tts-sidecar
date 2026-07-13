"""Tests de `ChatterboxEngine` a nivel voz.

Cubren `add_voice` (ramas precompute/force) y los delegates
`list_voices`/`remove_voice`/`resolve_voice`, inyectando colaboradores falsos
y monkeypatcheando el módulo `voices`, sin cargar el modelo real. El engine se
instancia con `ChatterboxEngine.__new__` (patrón ya usado en test_engine_cache.py).
"""

import pytest

import tts_sidecar.voices as voices_mod
from tts_sidecar.conditionals import ConditionalsPreparer
from tts_sidecar.engine import ChatterboxEngine
from tts_sidecar.model_loader import ModelLoader


class _FakePreparer:
    """Double de ConditionalsPreparer que registra las llamadas de precomputación."""

    def __init__(self):
        self.precompute_calls = []
        self.load_calls = []

    def compute(self, *args, **kwargs):
        return object()

    def precompute_and_save(self, voice_dir, reference_audio, speech_audio, tts, compute_backend):
        self.precompute_calls.append(
            (voice_dir, reference_audio, speech_audio, tts, compute_backend)
        )

    def load_precomputed(self, voice_dir, compute_backend):
        self.load_calls.append((voice_dir, compute_backend))
        return None


@pytest.fixture
def engine(monkeypatch):
    """Engine sin modelo real: colaboradores inyectados y register stubbeado."""
    eng = ChatterboxEngine.__new__(ChatterboxEngine)
    eng.compute_backend = "cpu"
    eng.model_name = "es-mx-latam"
    eng._model_loader = ModelLoader()  # no se usa en estos tests
    eng._conditionals_prep = ConditionalsPreparer()
    eng._tts = object()

    register_calls = {}

    def fake_register(name, reference_audio, speech_audio, force=False):
        register_calls["register"] = (name, reference_audio, speech_audio, force)
        return (f"/voices/{name}/reference.wav", f"/voices/{name}/speech.wav")

    monkeypatch.setattr(voices_mod, "register_voice_files", fake_register)
    eng._register_calls = register_calls
    return eng


def test_add_voice_precompute_true_invokes_preparer(engine):
    engine._conditionals_prep = _FakePreparer()

    ref, speech = engine.add_voice("v", "r.wav", "s.wav", precompute=True)

    assert (ref, speech) == ("/voices/v/reference.wav", "/voices/v/speech.wav")
    assert engine._conditionals_prep.precompute_calls == [
        ("/voices/v", "/voices/v/reference.wav", "/voices/v/speech.wav", engine._tts, "cpu")
    ]


def test_add_voice_precompute_false_skips_preparer(engine):
    engine._conditionals_prep = _FakePreparer()

    engine.add_voice("v", "r.wav", "s.wav", precompute=False)

    assert engine._conditionals_prep.precompute_calls == []


def test_add_voice_force_propagated(engine):
    engine._conditionals_prep = _FakePreparer()

    engine.add_voice("v", "r.wav", "s.wav", force=True)

    assert engine._register_calls["register"][3] is True


def test_list_voices_delegates(monkeypatch):
    eng = ChatterboxEngine.__new__(ChatterboxEngine)
    called = []
    monkeypatch.setattr(
        voices_mod, "list_voices", lambda: (called.append(1) or ["a", "b"])
    )

    assert eng.list_voices() == ["a", "b"]
    assert called == [1]


def test_remove_voice_delegates(monkeypatch):
    eng = ChatterboxEngine.__new__(ChatterboxEngine)
    names = []
    monkeypatch.setattr(
        voices_mod, "remove_voice", lambda name: (names.append(name) or True)
    )

    assert eng.remove_voice("foo") is True
    assert names == ["foo"]


def test_resolve_voice_delegates(monkeypatch):
    eng = ChatterboxEngine.__new__(ChatterboxEngine)
    names = []
    monkeypatch.setattr(
        voices_mod,
        "voice_paths",
        lambda name: (names.append(name) or ("r.wav", "s.wav")),
    )

    assert eng.resolve_voice("bar") == ("r.wav", "s.wav")
    assert names == ["bar"]
