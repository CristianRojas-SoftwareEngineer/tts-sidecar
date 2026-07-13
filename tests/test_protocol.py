"""Tests para los modelos Pydantic de daemon/protocol.py."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tts_sidecar.daemon.protocol import (
    MAX_TEXT_LENGTH,
    MAX_AUDIO_PATH_LENGTH,
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
    ProgressEvent,
    ResultEvent,
    ErrorEvent,
)


class TestSynthesizeRequest:
    def test_valid_request(self):
        req = SynthesizeRequest(text="hola mundo")
        assert req.text == "hola mundo"

    def test_full_request(self):
        req = SynthesizeRequest(
            text="test",
            voice_audio="/path/to/voice.wav",
            speech_audio="/path/to/speech.wav",
        )
        assert req.text == "test"
        assert req.voice_audio == "/path/to/voice.wav"
        assert req.speech_audio == "/path/to/speech.wav"

    def test_missing_text(self):
        with pytest.raises(ValueError):
            SynthesizeRequest()

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="")

    def test_excessive_text_rejected(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="a" * (MAX_TEXT_LENGTH + 1))

    def test_text_at_limit_accepted(self):
        assert len(SynthesizeRequest(text="a" * MAX_TEXT_LENGTH).text) == MAX_TEXT_LENGTH

    def test_protocol_without_model_or_compute_backend(self):
        campos = SynthesizeRequest.model_fields
        assert "model" not in campos
        assert "compute_backend" not in campos

    def test_excessive_audio_path_rejected(self):
        """SUGGESTION-01: voice_audio/speech_audio tienen tope de longitud."""
        ruta_excesiva = "a" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", voice_audio=ruta_excesiva)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", speech_audio=ruta_excesiva)

    def test_audio_path_at_limit_accepted(self):
        ruta = "a" * MAX_AUDIO_PATH_LENGTH
        req = SynthesizeRequest(text="hola", voice_audio=ruta)
        assert len(req.voice_audio) == MAX_AUDIO_PATH_LENGTH


class TestHealthResponse:
    def test_healthy_response(self):
        resp = HealthResponse(status="healthy", model_loaded=True, uptime_seconds=10.5)
        assert resp.status == "healthy"
        assert resp.model_loaded is True
        assert resp.uptime_seconds == 10.5

    def test_initializing_response(self):
        resp = HealthResponse(status="initializing", model_loaded=False, uptime_seconds=0.0)
        assert resp.status == "initializing"
        assert resp.model_loaded is False


class TestVoicesResponse:
    def test_voices_response(self):
        resp = VoicesResponse(voices=["crist", "testcli"])
        assert resp.voices == ["crist", "testcli"]

    def test_empty_voices(self):
        resp = VoicesResponse(voices=[])
        assert resp.voices == []


class TestStreamEvents:
    """Esquema NDJSON de /synthesize: progress / result / error."""

    def test_progress_event_defaults(self):
        ev = ProgressEvent()
        assert ev.event == "progress"
        assert ev.stage is None and ev.tokens is None and ev.elapsed is None

    def test_progress_event_with_tokens(self):
        ev = ProgressEvent(stage="t3", tokens=210)
        assert ev.event == "progress"
        assert ev.stage == "t3"
        assert ev.tokens == 210

    def test_progress_event_fixed_literal(self):
        """El discriminador `event` es un literal: no admite otros valores."""
        with pytest.raises(ValueError):
            ProgressEvent(event="result")

    def test_result_event(self):
        ev = ResultEvent(audio_b64="QUJD", t3_time=9.7, s3gen_time=7.0)
        assert ev.event == "result"
        assert ev.audio_b64 == "QUJD"
        assert ev.t3_time == 9.7
        assert ev.s3gen_time == 7.0

    def test_result_event_default_times(self):
        ev = ResultEvent(audio_b64="QUJD")
        assert ev.t3_time == 0.0 and ev.s3gen_time == 0.0

    def test_result_event_requires_audio(self):
        with pytest.raises(ValueError):
            ResultEvent()

    def test_error_event(self):
        ev = ErrorEvent(detail="Error interno de síntesis")
        assert ev.event == "error"
        assert ev.detail == "Error interno de síntesis"

    def test_error_event_requires_detail(self):
        with pytest.raises(ValueError):
            ErrorEvent()

    def test_json_serialization_includes_event(self):
        """Cada línea NDJSON lleva el discriminador `event` para el parseo del cliente."""
        import json

        assert json.loads(ProgressEvent(stage="t3", tokens=10).model_dump_json())["event"] == "progress"
        assert json.loads(ResultEvent(audio_b64="QUJD").model_dump_json())["event"] == "result"
        assert json.loads(ErrorEvent(detail="x").model_dump_json())["event"] == "error"


class TestUnicodeBoundaries:
    """S1-10: los topes de longitud (MAX_TEXT_LENGTH/MAX_AUDIO_PATH_LENGTH) se
    validan en Pydantic v2 por longitud de la cadena Python (code points), no
    por bytes UTF-8: un acento o un emoji no deben contar doble."""

    def test_multibyte_text_at_limit_accepted(self):
        text = "ñ" * MAX_TEXT_LENGTH
        req = SynthesizeRequest(text=text)
        assert len(req.text) == MAX_TEXT_LENGTH

    def test_multibyte_text_over_limit_rejected(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="ñ" * (MAX_TEXT_LENGTH + 1))

    def test_emoji_counts_as_single_codepoint(self):
        """Un emoji fuera del BMP es un solo code point en Python 3 (no un par
        de surrogates UTF-16): no debe contar doble contra el límite."""
        text = "😀" * MAX_TEXT_LENGTH
        req = SynthesizeRequest(text=text)
        assert len(req.text) == MAX_TEXT_LENGTH
        with pytest.raises(ValueError):
            SynthesizeRequest(text="😀" * (MAX_TEXT_LENGTH + 1))

    def test_unicode_audio_path_at_limit_accepted(self):
        ruta = "ñ" * MAX_AUDIO_PATH_LENGTH
        req = SynthesizeRequest(text="hola", voice_audio=ruta)
        assert len(req.voice_audio) == MAX_AUDIO_PATH_LENGTH

    def test_unicode_audio_path_over_limit_rejected(self):
        ruta = "ñ" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", voice_audio=ruta)

    def test_text_with_accents_and_spanish_punctuation_roundtrips(self):
        text = "¿Cómo estás? ¡Qué bien! Ñoño güiro."
        req = SynthesizeRequest(text=text)
        assert req.text == text


class TestCrossFieldValidation:
    """S1-10: voice_audio y speech_audio son independientes entre sí (ambos
    Optional, cada uno con su propio tope) — se valida que combinarlos no
    interfiera con la validación individual de cada campo."""

    def test_both_audio_fields_set_simultaneously(self):
        req = SynthesizeRequest(text="hola", voice_audio="/a/ref.wav", speech_audio="/a/speech.wav")
        assert req.voice_audio == "/a/ref.wav"
        assert req.speech_audio == "/a/speech.wav"

    def test_neither_audio_field_set_defaults_to_none(self):
        req = SynthesizeRequest(text="hola")
        assert req.voice_audio is None
        assert req.speech_audio is None

    def test_one_field_at_max_other_none(self):
        ruta = "a" * MAX_AUDIO_PATH_LENGTH
        req = SynthesizeRequest(text="hola", voice_audio=ruta, speech_audio=None)
        assert len(req.voice_audio) == MAX_AUDIO_PATH_LENGTH
        assert req.speech_audio is None

    def test_both_fields_at_max_simultaneously_accepted(self):
        ruta = "b" * MAX_AUDIO_PATH_LENGTH
        req = SynthesizeRequest(text="hola", voice_audio=ruta, speech_audio=ruta)
        assert len(req.voice_audio) == MAX_AUDIO_PATH_LENGTH
        assert len(req.speech_audio) == MAX_AUDIO_PATH_LENGTH

    def test_one_field_over_limit_rejects_even_if_other_valid(self):
        valid = "a" * MAX_AUDIO_PATH_LENGTH
        excessive = "b" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", voice_audio=valid, speech_audio=excessive)

    def test_speech_audio_over_limit_rejects_even_when_voice_audio_absent(self):
        excessive = "c" * (MAX_AUDIO_PATH_LENGTH + 1)
        with pytest.raises(ValueError):
            SynthesizeRequest(text="hola", speech_audio=excessive)


class TestUnicodeInStreamEvents:
    """Los eventos NDJSON (progress/result/error) también llevan texto libre
    (stage, detail): deben preservar unicode sin normalizarlo ni truncarlo."""

    def test_progress_event_stage_with_unicode(self):
        ev = ProgressEvent(stage="síntesis-de-audio", tokens=1)
        assert ev.stage == "síntesis-de-audio"

    def test_error_event_detail_with_unicode_and_emoji(self):
        ev = ErrorEvent(detail="Error de síntesis: voz no encontrada 🎙️")
        assert "síntesis" in ev.detail
        assert "🎙️" in ev.detail

    def test_error_event_detail_serializes_unicode_correctly_in_json(self):
        import json

        ev = ErrorEvent(detail="No se pudo cargar la voz «default»")
        payload = json.loads(ev.model_dump_json())
        assert payload["detail"] == "No se pudo cargar la voz «default»"
