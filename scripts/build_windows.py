#!/usr/bin/env python3
"""
Build script for Windows x64 using PyInstaller --onedir.
Produces a folder with the executable + all dependencies, then wraps it
in an Inno Setup installer.
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# Import shared logging utilities
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import (
    log, StageTimer, BuildTimer, copy_license_files,
    check_pyinstaller, common_pyinstaller_args, bundle_size_mb,
    BUILD_SUBPROCESS_TIMEOUT, PYINSTALLER_TIMEOUT,
)


def ensure_runtime_dependencies():
    """Instala las dependencias runtime desde el lockfile (requerido para builds reproducibles)."""
    lockfile = PROJECT_ROOT / "requirements-lock.txt"
    if not lockfile.exists():
        log(f"ERROR: No se encontró {lockfile}; instala primero con: pip install -r requirements-lock.txt --require-hashes")
        sys.exit(1)

    log("Instalando dependencias runtime desde lockfile...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(lockfile), "--require-hashes"],
            check=True,
            timeout=BUILD_SUBPROCESS_TIMEOUT,
        )
    except subprocess.CalledProcessError as exc:
        log(f"ERROR: Falló la instalación del lockfile (rc={exc.returncode})")
        sys.exit(1)
    except subprocess.TimeoutExpired:
        log(f"ERROR: La instalación del lockfile excedió {BUILD_SUBPROCESS_TIMEOUT}s")
        sys.exit(1)


def check_dependencies():
    """Verifica que las dependencias requeridas estén instaladas."""
    check_pyinstaller()
    ensure_runtime_dependencies()


def build_windows(target_arch="x86_64"):
    """Compila tts-sidecar para Windows x64 con PyInstaller --onedir."""
    with BuildTimer():
        with StageTimer("Setup", "Preparando entorno de build"):
            log("Plataforma: Windows x64")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"
            log(f"Entry point: {entry_point}")

        with StageTimer("PyInstaller", "Compiling with PyInstaller (9-15 min)"):
            pyinstaller_args = common_pyinstaller_args(
                entry_point, PROJECT_ROOT, DIST_DIR, BUILD_DIR,
                data_sep=";",
                extra_collect_all=["pycaw"],
            )
            # [2:] omite [sys.executable, "-m"] del log para mostrar solo los args de PyInstaller
            log(f"Running: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(
                    pyinstaller_args,
                    # Heredar la consola para que la barra de progreso de PyInstaller se renderice;
                    # las cabeceras [HH:MM:SS] del padre enmarcan cada fase.
                    timeout=PYINSTALLER_TIMEOUT,
                ).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelado por el usuario.")
                sys.exit(130)  # 128 + 2 (SIGINT)
            except subprocess.TimeoutExpired:
                log(f"\n[TIMEOUT] PyInstaller excedió {PYINSTALLER_TIMEOUT}s.")
                sys.exit(1)

        if returncode != 0:
            log("PyInstaller falló", returncode)
            sys.exit(1)

        with StageTimer("Size", "Verificando tamaño del bundle"):
            onedir = DIST_DIR / "tts-sidecar"
            if onedir.exists():
                log(f"Tamaño del bundle: {bundle_size_mb(onedir):.1f} MB ({onedir})")

        with StageTimer("Licenses", "Empaquetando avisos de licencia"):
            copy_license_files(DIST_DIR / "tts-sidecar")

        with StageTimer("Installer", "Generando instalador Inno Setup"):
            installer_script = PROJECT_ROOT / "scripts" / "create_installer_windows.py"
            try:
                returncode = subprocess.run(
                    [sys.executable, str(installer_script), str(DIST_DIR / "tts-sidecar")],
                    check=False,
                    timeout=BUILD_SUBPROCESS_TIMEOUT,
                ).returncode
            except subprocess.TimeoutExpired:
                log(f"[TIMEOUT] La generación del instalador excedió {BUILD_SUBPROCESS_TIMEOUT}s")
                returncode = 1
            if returncode != 0:
                log(f"Generación del instalador fallida (rc={returncode})")
                # No fatal: el bundle onedir sigue siendo usable
                log("WARNING: Instalador no creado — el bundle onedir está disponible en dist/")
            else:
                log("Instalador creado correctamente")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Windows executable")
    parser.add_argument(
        "--arch", default="x86_64",
        choices=["x86_64"],
        help="Target architecture (default: x86_64; Windows-on-ARM no está soportado)",
    )
    args = parser.parse_args()
    check_dependencies()
    build_windows(args.arch)
