"""
Rutas de datos conscientes del modo congelado (frozen-aware).

Fuente única de verdad para la raíz de datos del proyecto, válida en los dos
modos de ejecución:

- **Desde fuente** (`python bin/tts-sidecar`): la raíz es la carpeta `src/`,
  reproduciendo el layout actual del repositorio.
- **Congelado** (ejecutable onefile de Nuitka): la raíz es el directorio de
  datos de usuario por SO, estable y escribible entre ejecuciones, ya que en
  onefile `__file__` resuelve a un directorio temporal de extracción efímero.

Ninguna función aquí importa ni carga el modelo: son operaciones puras de
sistema de archivos.
"""

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """True cuando corremos dentro del ejecutable onefile compilado."""
    return getattr(sys, "frozen", False)


def data_root() -> str:
    """
    Raíz de datos estable y escribible.

    Congelado: directorio de datos de usuario por SO (creado si no existe).
    Desde fuente: la carpeta `src/` del repositorio.
    """
    if not is_frozen():
        # src/chatterbox_tts/paths.py -> src/
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~\\AppData\\Local")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")

    root = os.path.join(base, "tts-sidecar")
    Path(root).mkdir(parents=True, exist_ok=True)
    return root
