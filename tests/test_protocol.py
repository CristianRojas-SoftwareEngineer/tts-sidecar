"""Tests para los modelos Pydantic de daemon/protocol.py."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from chatterbox_tts.daemon.protocol import (
    MAX_TEXT_LENGTH,
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
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

    def test_texto_vacio_rechazado(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="")

    def test_texto_excesivo_rechazado(self):
        with pytest.raises(ValueError):
            SynthesizeRequest(text="a" * (MAX_TEXT_LENGTH + 1))

    def test_texto_en_el_limite_aceptado(self):
        assert len(SynthesizeRequest(text="a" * MAX_TEXT_LENGTH).text) == MAX_TEXT_LENGTH

    def test_protocolo_sin_model_ni_device(self):
        campos = SynthesizeRequest.model_fields
        assert "model" not in campos
        assert "device" not in campos


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
