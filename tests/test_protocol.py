"""Tests for daemon/protocol.py Pydantic models."""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from chatterbox_tts.daemon.protocol import (
    SynthesizeRequest,
    HealthResponse,
    VoicesResponse,
    ErrorResponse,
)


class TestSynthesizeRequest:
    def test_valid_request(self):
        req = SynthesizeRequest(text="hola mundo")
        assert req.text == "hola mundo"
        assert req.model == "es-latam"
        assert req.device == "cpu"

    def test_full_request(self):
        req = SynthesizeRequest(
            text="test",
            voice_audio="/path/to/voice.wav",
            speech_audio="/path/to/speech.wav",
            model="multilingual",
            device="cuda",
        )
        assert req.text == "test"
        assert req.voice_audio == "/path/to/voice.wav"
        assert req.speech_audio == "/path/to/speech.wav"
        assert req.model == "multilingual"
        assert req.device == "cuda"

    def test_missing_text(self):
        with pytest.raises(ValueError):
            SynthesizeRequest()


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


class TestErrorResponse:
    def test_error_response(self):
        resp = ErrorResponse(error="not found", code="NOT_FOUND")
        assert resp.error == "not found"
        assert resp.code == "NOT_FOUND"
