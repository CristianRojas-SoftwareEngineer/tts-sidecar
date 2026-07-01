"""
Rutas de datos conscientes del modo congelado (frozen-aware).

Fuente única de verdad para las raíces de datos del proyecto. Se distinguen dos
raíces según su propósito:

- **Raíz de usuario** (`data_root`): estable y **escribible** entre ejecuciones,
  donde viven las voces de usuario. Desde fuente es la carpeta `src/`; congelado
  es el directorio de datos de usuario por SO.
- **Raíz de fábrica** (`bundled_root`): de **solo lectura**, con los recursos
  empaquetados (p. ej. la voz de fábrica `default`). Desde fuente es la raíz del
  repositorio; congelado es `sys._MEIPASS`, el directorio donde PyInstaller
  extrae los datos incluidos vía `--add-data`.

El build es **onedir** (no onefile): el ejecutable convive con su directorio
`_internal/`. Se usa el user-data-dir por SO para las voces de usuario porque el
directorio de instalación puede ser de solo lectura (p. ej. `Program Files`,
`/Applications`), no por un temporal efímero de extracción.

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


def bundled_root() -> str:
    """
    Raíz de recursos de fábrica (solo lectura).

    Congelado: `sys._MEIPASS`, donde PyInstaller extrae los datos empaquetados
    vía `--add-data`.
    Desde fuente: la raíz del repositorio (un nivel por encima de `src/`).
    """
    if is_frozen():
        return getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))

    # src/chatterbox_tts/paths.py -> src/ -> raíz del repo
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.dirname(src_dir)


def bundled_voices_dir() -> str:
    """Directorio de voces de fábrica empaquetadas (solo lectura)."""
    return os.path.join(bundled_root(), "voices")
