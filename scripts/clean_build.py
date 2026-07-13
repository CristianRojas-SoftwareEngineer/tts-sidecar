#!/usr/bin/env python3
"""
Clean build script — removes PyInstaller artifacts (dist/, build/, *.spec),
__pycache__ directories and the cached model.
Usage: python scripts/clean_build.py
       npm run clean-build
"""

import shutil
import time
from pathlib import Path

# Import shared logging utilities
import sys
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log


def _find_project_root(start: Path) -> Path:
    """Resuelve la raíz del repo subiendo desde `start` hasta un marcador conocido.

    Busca `pyproject.toml` (fuente de verdad del paquete) o, si falta, un
    directorio `.git`, en `start` y en cada padre. Evita asumir que la raíz
    está siempre a `parent.parent` de este script: ese supuesto se rompe si
    `clean_build.py` se ejecuta copiado fuera del checkout, symlinkeado, o
    de cualquier otra forma en la que su ruta en disco no refleje la
    estructura del repo. Falla con un mensaje accionable en vez de operar
    silenciosamente sobre una ruta equivocada (y potencialmente borrar
    directorios `dist`/`build`/`__pycache__` fuera del proyecto).
    """
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() or (candidate / ".git").exists():
            return candidate
    raise SystemExit(
        f"clean_build.py: no se pudo ubicar la raíz del repo (se buscó "
        f"pyproject.toml o .git subiendo desde {start}). Ejecuta este script "
        "dentro de un checkout de TTS Sidecar."
    )


PROJECT_ROOT = _find_project_root(Path(__file__).parent)
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"          # PyInstaller --workpath
SPEC_DIR = PROJECT_ROOT / "scripts"         # PyInstaller --specpath

# HuggingFace default cache location
HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
MODEL_CACHE_NAMES = [
    "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "models--ResembleAI--chatterbox",
]


def delete_folder(dir_path: Path):
    """Delete a folder if it exists, log the result."""
    if not dir_path.exists():
        log(f"Not found (skip): {dir_path}")
        return
    try:
        shutil.rmtree(dir_path)
        log(f"Deleted: {dir_path}")
    except Exception as e:
        log(f"Error deleting {dir_path}: {e}")


def main():
    start = time.time()
    print()
    log("=== CLEAN BUILD ===")

    log("Removing dist/...")
    delete_folder(DIST_DIR)

    log("Removing build/...")
    delete_folder(BUILD_DIR)

    log("Removing PyInstaller *.spec...")
    for spec in SPEC_DIR.glob("*.spec"):
        try:
            spec.unlink()
            log(f"Deleted: {spec}")
        except Exception as e:
            log(f"Error deleting {spec}: {e}")

    log("Removing __pycache__ directories...")
    for cache_dir in PROJECT_ROOT.rglob("__pycache__"):
        delete_folder(cache_dir)

    log("Removing HuggingFace model cache...")
    for name in MODEL_CACHE_NAMES:
        delete_folder(HF_CACHE / name)

    log("=== CLEAN DONE ===", time.time() - start)
    print()


if __name__ == "__main__":
    main()
