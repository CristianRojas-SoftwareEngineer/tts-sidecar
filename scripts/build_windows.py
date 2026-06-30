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
from build_utils import log, StageTimer, BuildTimer


def check_dependencies():
    """Check required dependencies are installed."""
    with StageTimer("CheckDeps", "Checking dependencies"):
        try:
            import PyInstaller
            log(f"PyInstaller: {PyInstaller.__version__}")
        except ImportError:
            log("PyInstaller not found, installing...")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "pyinstaller"],
                check=True,
            )
            if result.returncode != 0:
                sys.exit(1)


def build_windows():
    """Build Windows x64 with PyInstaller --onedir."""
    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log("Platform: Windows x64")
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
                # Collect all packages that PyInstaller can't follow automatically
                # (lazy imports, C extensions, compiled code)
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
                # Metadata required by importlib.metadata / pkg_resources
                "--recursive-copy-metadata", "chatterbox-tts",
                "--copy-metadata", "requests",
                # Exclude bloat (never loaded at runtime)
                "--exclude-module", "tensorflow",
                "--exclude-module", "jax",
                "--exclude-module", "flax",
                "--exclude-module", "gradio",
                "--exclude-module", "gradio_client",
            ]
            log(f"Running: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(
                    pyinstaller_args,
                    # Inherit console so PyInstaller progress bar renders.
                    # The parent's [HH:MM:SS] stage headers bracket each phase.
                ).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelled by user.")
                sys.exit(130)  # 128 + 2 (SIGINT)

        if returncode != 0:
            log("PyInstaller failed", returncode)
            sys.exit(1)

        with StageTimer("Size", "Checking bundle size"):
            onedir = DIST_DIR / "tts-sidecar"
            if onedir.exists():
                size_mb = sum(f.stat().st_size for f in onedir.rglob("*") if f.is_file()) / 1024 / 1024
                log(f"Bundle size: {size_mb:.1f} MB ({onedir})")

        with StageTimer("Installer", "Building Inno Setup installer"):
            installer_script = PROJECT_ROOT / "scripts" / "create_installer_windows.py"
            result = subprocess.run(
                [sys.executable, str(installer_script), str(DIST_DIR / "tts-sidecar")],
                check=False,
            )
            if result.returncode != 0:
                log(f"Installer build failed (rc={result.returncode})")
                if result.stdout:
                    print(result.stdout)
                if result.stderr:
                    print(result.stderr, file=sys.stderr)
                # Non-fatal: the onedir bundle is still usable
                log("WARNING: Installer failed — onedir bundle is still available in dist/")
            else:
                log("Installer created successfully")


if __name__ == "__main__":
    check_dependencies()
    build_windows()
