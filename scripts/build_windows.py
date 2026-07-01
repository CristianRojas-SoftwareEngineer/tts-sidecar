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
from build_utils import log, StageTimer, BuildTimer, copy_license_files


def check_dependencies():
    """Verifica que las dependencias requeridas estén instaladas."""
    with StageTimer("CheckDeps", "Verificando dependencias"):
        try:
            import PyInstaller
            log(f"PyInstaller: {PyInstaller.__version__}")
        except ImportError:
            log("PyInstaller no encontrado, instalando...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                check=True,
            )
            if result.returncode != 0:
                sys.exit(1)


def build_windows():
    """Compila tts-sidecar para Windows x64 con PyInstaller --onedir."""
    with BuildTimer():
        with StageTimer("Setup", "Preparando entorno de build"):
            log("Plataforma: Windows x64")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"
            log(f"Entry point: {entry_point}")

        with StageTimer("PyInstaller", "Compiling with PyInstaller (9-15 min)"):
            pyinstaller_args = [
                sys.executable, "-m", "PyInstaller",
                "--onedir",
                "--console",
                "--name", "tts-sidecar",
                "--paths", str(PROJECT_ROOT / "src"),
                "--distpath", str(DIST_DIR),
                "--workpath", str(BUILD_DIR),
                "--specpath", str(PROJECT_ROOT / "scripts"),
                "--noconfirm",
                # Entry point
                str(entry_point),
                # Recolectar todos los paquetes que PyInstaller no puede seguir
                # automáticamente (imports perezosos, extensiones C, código compilado)
                "--collect-all", "chatterbox",
                "--collect-all", "chatterbox_tts",
                "--collect-all", "transformers",
                "--collect-all", "diffusers",
                "--collect-all", "s3tokenizer",
                "--collect-all", "perth",
                "--collect-all", "librosa",
                "--collect-all", "torch",
                "--collect-all", "sklearn",
                "--collect-all", "pandas",
                "--collect-all", "onnx",
                "--collect-all", "pycaw",
                # Data files
                "--collect-data", "soundfile",
                "--collect-data", "certifi",
                # Voces de fábrica (incluida la voz 'default') en la raíz del bundle,
                # resueltas en runtime por paths.bundled_voices_dir() (sys._MEIPASS).
                "--add-data", f"{PROJECT_ROOT / 'voices'};voices",
                # Metadata requerida por importlib.metadata / pkg_resources
                "--recursive-copy-metadata", "chatterbox-tts",
                "--copy-metadata", "requests",
                # Excluir bloat (nunca cargado en runtime)
                "--exclude-module", "tensorflow",
                "--exclude-module", "jax",
                "--exclude-module", "flax",
                "--exclude-module", "gradio",
                "--exclude-module", "gradio_client",
            ]
            # [2:] omite [sys.executable, "-m"] del log para mostrar solo los args de PyInstaller
            log(f"Running: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(
                    pyinstaller_args,
                    # Heredar la consola para que la barra de progreso de PyInstaller se renderice;
                    # las cabeceras [HH:MM:SS] del padre enmarcan cada fase.
                ).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelado por el usuario.")
                sys.exit(130)  # 128 + 2 (SIGINT)

        if returncode != 0:
            log("PyInstaller failed", returncode)
            sys.exit(1)

        with StageTimer("Size", "Verificando tamaño del bundle"):
            onedir = DIST_DIR / "tts-sidecar"
            if onedir.exists():
                size_mb = sum(f.stat().st_size for f in onedir.rglob("*") if f.is_file()) / 1024 / 1024
                log(f"Tamaño del bundle: {size_mb:.1f} MB ({onedir})")

        with StageTimer("Licenses", "Empaquetando avisos de licencia"):
            copy_license_files(DIST_DIR / "tts-sidecar")

        with StageTimer("Installer", "Generando instalador Inno Setup"):
            installer_script = PROJECT_ROOT / "scripts" / "create_installer_windows.py"
            result = subprocess.run(
                [sys.executable, str(installer_script), str(DIST_DIR / "tts-sidecar")],
                check=False,
            )
            if result.returncode != 0:
                log(f"Generación del instalador fallida (rc={result.returncode})")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                # No fatal: el bundle onedir sigue siendo usable
                log("WARNING: Instalador no creado — el bundle onedir está disponible en dist/")
            else:
                log("Instalador creado correctamente")


if __name__ == "__main__":
    check_dependencies()
    build_windows()
