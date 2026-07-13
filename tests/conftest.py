"""Fixtures de pytest para los tests de tts-sidecar."""

import sys
from pathlib import Path

# Asegura que src/ esté en el path para imports relativos al proyecto
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def pytest_configure(config):
    """Corre el bootstrap antes de la recolección.

    Asegura que la supresión de warnings (incl. `pkg_resources`) esté activa
    antes de que los tests importen módulos como `tts_sidecar.audio` a nivel
    de módulo, de modo que la supresión no dependa del filtro local de
    audio.py (eliminado). `bootstrap.apply()` es idempotente.
    """
    import tts_sidecar.bootstrap
    tts_sidecar.bootstrap.apply()
