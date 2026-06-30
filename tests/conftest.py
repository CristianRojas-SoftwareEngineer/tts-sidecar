"""Pytest fixtures for tts-sidecar tests."""

import pytest
import sys
from pathlib import Path

# Ensure src is on path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


@pytest.fixture
def mock_engine():
    """Mock ChatterboxEngine for CLI tests."""
    class MockEngine:
        def __init__(self):
            self.list_voices_calls = []

        def speak(self, text, voice_audio=None, speech_audio=None, output_path=None, verbose=False):
            # Return minimal WAV header (44 bytes)
            return b"RIFF" + b"\x00" * 40

        def add_voice(self, name, reference_audio, speech_audio):
            return f"/path/to/{name}/reference.wav", f"/path/to/{name}/speech.wav"

        def remove_voice(self, name):
            return True

        def list_voices(self):
            return ["crist", "testcli"]

    return MockEngine()


@pytest.fixture
def mock_daemon_client():
    """Mock DaemonIPCClient for CLI tests."""
    class MockDaemonClient:
        def __init__(self):
            self.calls = []

        def synthesize(self, text, voice_audio=None, speech_audio=None,
                        model=None, device=None):
            self.calls.append({"text": text})
            # Return minimal WAV
            return b"RIFF" + b"\x00" * 40

        def is_running(self):
            return True

    return MockDaemonClient()
