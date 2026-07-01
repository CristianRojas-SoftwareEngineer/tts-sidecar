"""
Gestión del registro de voces, libre de modelo.

Hogar único de las rutas del directorio de voces y de las operaciones de registro
(listar, eliminar, resolver rutas). El modelo de voces es de **dos niveles**:

- **Usuario**: voces escribibles en `data_root()/voices` (user-data-dir por SO
  cuando está congelado; `src/voices` en modo fuente históricamente, hoy vacío).
- **Fábrica**: voces de solo lectura empaquetadas en `bundled_voices_dir()`
  (raíz del repo en modo fuente; `sys._MEIPASS` congelado).

La resolución de un nombre busca primero en usuario y luego en fábrica, de modo
que un usuario puede sobrescribir una voz de fábrica registrando una propia con
el mismo nombre. Ninguna función aquí importa ni carga el modelo: son operaciones
puras de sistema de archivos.
"""

import os
import shutil

from . import paths


def voices_root() -> str:
    """Directorio base de las voces de usuario (escribible)."""
    return os.path.join(paths.data_root(), "voices")


def factory_voices_root() -> str:
    """Directorio base de las voces de fábrica (solo lectura)."""
    return paths.bundled_voices_dir()


def voice_dir(name: str) -> str:
    """Directorio de una voz de usuario concreta (destino de escritura)."""
    return os.path.join(voices_root(), name)


def _resolve_voice_dir(name: str) -> str | None:
    """Devuelve el directorio de una voz con precedencia usuario→fábrica, o None."""
    for root in (voices_root(), factory_voices_root()):
        candidate = os.path.join(root, name)
        if os.path.exists(os.path.join(candidate, "reference.wav")):
            return candidate
    return None


def list_voices() -> list[str]:
    """Listar todas las voces disponibles (usuario + fábrica, sin duplicados)."""
    seen = []
    for root in (voices_root(), factory_voices_root()):
        if not os.path.exists(root):
            continue
        for entry in sorted(os.listdir(root)):
            ref_path = os.path.join(root, entry, "reference.wav")
            if entry not in seen and os.path.isdir(os.path.join(root, entry)) and os.path.exists(ref_path):
                seen.append(entry)
    return seen


def remove_voice(name: str) -> bool:
    """Eliminar una voz de usuario. Devuelve True si existía y se borró.

    Solo opera sobre voces de usuario; las de fábrica son de solo lectura.
    """
    target = voice_dir(name)
    if os.path.exists(target):
        shutil.rmtree(target)
        return True
    return False


def voice_paths(name: str) -> tuple[str, str]:
    """
    Resolver el nombre de una voz a sus rutas de audio (reference, speech).

    Busca con precedencia usuario→fábrica y valida la existencia de ambos archivos.
    """
    target = _resolve_voice_dir(name)
    if target is None:
        raise FileNotFoundError(
            f"Voz '{name}' no encontrada (ni en las voces de usuario ni en las de fábrica). "
            f"Regístrala con 'tts-sidecar voice add' o usa la voz 'default'."
        )
    ref_path = os.path.join(target, "reference.wav")
    speech_path = os.path.join(target, "speech.wav")
    if not os.path.exists(ref_path):
        raise FileNotFoundError(f"Voz '{name}': reference.wav no encontrado en {ref_path}")
    if not os.path.exists(speech_path):
        raise FileNotFoundError(f"Voz '{name}': speech.wav no encontrado en {speech_path}")
    return (ref_path, speech_path)
