"""
TTS Sidecar — síntesis de voz con clonación de voz.
100% local, licencia GPL-3.0-or-later, soporte para español latinoamericano.
"""

__version__ = "0.5.0"
__author__ = "TTS Sidecar Team"
__license__ = "GPL-3.0-or-later"

# Imports perezosos: permite ejecutar --help sin que las dependencias pesadas estén instaladas
def __getattr__(name):
    """
    Resuelve imports perezosos de los símbolos públicos del paquete.

    ChatterboxEngine y AudioPlayer se importan solo cuando se acceden por primera
    vez, evitando cargar torch/chatterbox al invocar subcomandos ligeros como
    --help, version o devices.
    """
    if name == "ChatterboxEngine":
        from .engine import ChatterboxEngine
        return ChatterboxEngine
    if name == "AudioPlayer":
        from .audio import AudioPlayer
        return AudioPlayer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = []
