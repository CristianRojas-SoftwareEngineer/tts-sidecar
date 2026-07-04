"""Tests del progreso de síntesis del motor (Fase 2).

Cubren:
  - speak(progress_callback=...) emite los eventos de etapa esperados.
  - El shim de conteo de tokens (_token_counting_iter) reporta iteraciones con
    throttle sobre un iterable falso, sin romper la iteración.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def _engine_stub(tmp_path):
    """ChatterboxEngine sin cargar el modelo real (bypass de __init__)."""
    from tts_sidecar.engine import ChatterboxEngine

    eng = ChatterboxEngine.__new__(ChatterboxEngine)
    eng.compute_backend = "cpu"
    eng._conds_cache_key = None
    eng._active_progress_cb = None

    class FakeTTS:
        conds = None

        def generate(self, text, **kwargs):
            return [0.0]

    eng._tts = FakeTTS()
    return eng


class TestSpeakProgressCallback:
    def test_emite_eventos_de_etapa(self, tmp_path, monkeypatch):
        from tts_sidecar.engine import ChatterboxEngine

        eng = _engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")
        eng._prepare_conditionals_multi = lambda **kw: None

        speech = tmp_path / "speech.wav"
        speech.write_bytes(b"RIFF")

        events = []
        eng.speak(
            "hola",
            speech_audio=str(speech),
            progress_callback=lambda ev: events.append(ev),
        )

        stages = [ev["stage"] for ev in events]
        # generate() de FakeTTS no pasa por los wrappers timed_t3/timed_s3gen,
        # así que aquí verificamos las etapas emitidas directamente por speak().
        assert stages == ["conditionals", "tts", "encoding"]
        assert all(ev["event"] == "progress" for ev in events)

    def test_emite_saving_con_output_path(self, tmp_path, monkeypatch):
        from tts_sidecar.engine import ChatterboxEngine

        eng = _engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")
        monkeypatch.setattr(ChatterboxEngine, "_save_wav", lambda self, b, p: None)
        eng._prepare_conditionals_multi = lambda **kw: None

        speech = tmp_path / "speech.wav"
        speech.write_bytes(b"RIFF")
        out = tmp_path / "out.wav"

        events = []
        eng.speak(
            "hola",
            speech_audio=str(speech),
            output_path=str(out),
            progress_callback=lambda ev: events.append(ev),
        )
        assert [ev["stage"] for ev in events] == [
            "conditionals", "tts", "encoding", "saving",
        ]

    def test_callback_se_limpia_en_finally(self, tmp_path, monkeypatch):
        from tts_sidecar.engine import ChatterboxEngine

        eng = _engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")
        eng._prepare_conditionals_multi = lambda **kw: None
        speech = tmp_path / "speech.wav"
        speech.write_bytes(b"RIFF")

        eng.speak("hola", speech_audio=str(speech), progress_callback=lambda ev: None)
        assert eng._active_progress_cb is None

    def test_excepcion_del_callback_no_rompe_sintesis(self, tmp_path, monkeypatch):
        from tts_sidecar.engine import ChatterboxEngine

        eng = _engine_stub(tmp_path)
        monkeypatch.setattr(ChatterboxEngine, "_audio_to_wav", lambda self, w: b"RIFF")
        eng._prepare_conditionals_multi = lambda **kw: None
        speech = tmp_path / "speech.wav"
        speech.write_bytes(b"RIFF")

        def boom(ev):
            raise RuntimeError("callback roto")

        assert eng.speak("hola", speech_audio=str(speech), progress_callback=boom) == b"RIFF"


class TestTokenCountingIter:
    def test_reporta_iteraciones_con_throttle(self):
        from tts_sidecar.engine import ChatterboxEngine

        eventos = []
        # 100 iteraciones: con throttle de ~10 tokens el conteo reportado avanza
        # en múltiplos de 10 (el primer emit es en count==10).
        salida = list(
            ChatterboxEngine._token_counting_iter(range(100), lambda ev: eventos.append(ev))
        )

        # La iteración es transparente: yield de todos los elementos.
        assert salida == list(range(100))
        assert eventos, "el shim debe reportar al menos un evento de tokens"
        assert all(ev["stage"] == "t3" and ev["event"] == "progress" for ev in eventos)
        assert all(ev["tokens"] % 10 == 0 for ev in eventos)
        # El conteo es ascendente.
        counts = [ev["tokens"] for ev in eventos]
        assert counts == sorted(counts)

    def test_iterable_vacio_no_emite(self):
        from tts_sidecar.engine import ChatterboxEngine

        eventos = []
        salida = list(
            ChatterboxEngine._token_counting_iter([], lambda ev: eventos.append(ev))
        )
        assert salida == []
        assert eventos == []


class TestTokenShimInstall:
    def test_shim_envuelve_tqdm_de_sampling(self, monkeypatch):
        """Instalado el shim, un tqdm(desc='Sampling') con callback activo cuenta
        tokens; sin callback delega en el tqdm real."""
        from tts_sidecar.engine import ChatterboxEngine
        from chatterbox.models.t3 import t3 as t3_mod

        eng = ChatterboxEngine.__new__(ChatterboxEngine)
        eng._active_progress_cb = None

        # Restaura el símbolo real al terminar para no contaminar otros tests.
        real_tqdm = t3_mod.tqdm
        monkeypatch.setattr(t3_mod, "tqdm", real_tqdm, raising=False)

        eng._install_token_progress_shim()
        assert getattr(t3_mod.tqdm, "_is_tts_sidecar_shim", False)

        eventos = []
        eng._active_progress_cb = lambda ev: eventos.append(ev)
        salida = list(t3_mod.tqdm(range(50), desc="Sampling", dynamic_ncols=True))
        assert salida == list(range(50))
        assert eventos, "con callback activo y desc='Sampling' debe contar tokens"

        # Sin callback: delega en el tqdm real y solo itera.
        eng._active_progress_cb = None
        assert list(t3_mod.tqdm(range(5), desc="Sampling")) == list(range(5))
