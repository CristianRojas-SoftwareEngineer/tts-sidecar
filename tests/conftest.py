"""Fixtures de pytest para los tests de tts-sidecar."""

import sys
from pathlib import Path

# Asegura que src/ esté en el path para imports relativos al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
