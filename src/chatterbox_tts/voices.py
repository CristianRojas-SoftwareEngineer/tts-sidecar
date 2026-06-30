"""
Gestión del registro de voces, libre de modelo.

Hogar único de la ruta del directorio de voces y de las operaciones de registro
(listar, eliminar, resolver rutas). Ninguna función aquí importa ni carga el modelo:
son operaciones puras de sistema de archivos, reutilizables tanto por la CLI como
por el engine.
"""

import os
import shutil

from . import paths


def voices_root() -> str:
    """Directorio base que contiene todas las voces registradas."""
    return os.path.join(paths.data_root(), "voices")


def voice_dir(name: str) -> str:
    """Directorio de una voz concreta."""
    return os.path.join(voices_root(), name)


def list_voices() -> list[str]:
    """Listar todas las voces registradas (carpetas con reference.wav)."""
    root = voices_root()
    if not os.path.exists(root):
        return []

    voices = []
    for entry in os.listdir(root):
        ref_path = os.path.join(root, entry, "reference.wav")
        if os.path.isdir(os.path.join(root, entry)) and os.path.exists(ref_path):
            voices.append(entry)
    return voices


def remove_voice(name: str) -> bool:
    """Eliminar una voz registrada. Devuelve True si existía y se borró."""
    target = voice_dir(name)
    if os.path.exists(target):
        shutil.rmtree(target)
        return True
    return False


def voice_paths(name: str) -> tuple[str, str]:
    """
    Resolver el nombre de una voz a sus rutas de audio (reference, speech).

    Valida la existencia de ambos archivos.
    """
    target = voice_dir(name)
    ref_path = os.path.join(target, "reference.wav")
    speech_path = os.path.join(target, "speech.wav")
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"Voice '{name}': reference.wav not found at {ref_path}")
    if not os.path.exists(speech_path):
        raise FileNotFoundError(f"Voice '{name}': speech.wav not found at {speech_path}")
    return (ref_path, speech_path)
