#!/usr/bin/env python3
"""
Build script for macOS x64 and ARM64 (Apple Silicon) apps using Nuitka.
Produces a single-file executable with embedded Python interpreter.
"""

import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

# Import shared logging utilities
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log, StageTimer, BuildTimer


def check_dependencies():
    """Check required dependencies are installed."""
    with StageTimer("CheckDeps", "Checking dependencies"):
        # nuitka --version prompts for Zig download if not found; answer Yes
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True, input="Yes\n"
        )
        if result.returncode == 0:
            log(f"Nuitka: {result.stdout.strip().splitlines()[0]}")
        else:
            log("Nuitka not found, installing...")
            # Inherit the console so pip's own progress output renders natively.
            result = subprocess.run([sys.executable, "-m", "pip", "install", "nuitka"])
            if result.returncode != 0:
                sys.exit(1)


def build_macos(target_arch="universal2"):
    """Build macOS executable (x64, arm64, or universal2)."""
    arch_options = {"x86_64": "x86_64", "arm64": "arm64", "universal2": "universal2"}
    arch_flag = arch_options.get(target_arch, "universal2")

    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log(f"Platform: macOS {arch_flag}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            output_path = DIST_DIR / f"tts-sidecar-macos-{arch_flag}"
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"
            env = os.environ.copy()
            src_path = str(PROJECT_ROOT / "src")
            env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

        with StageTimer("Configure", "Configuring Nuitka options"):
            # Order: mode → output → includes → excludes → python-flags → module-params → entry
            # macOS uses afplay (built-in) — no sounddevice or pycaw needed
            nuitka_args = [
                # Mode
                sys.executable,
                "-m", "nuitka",
                "--standalone",
                "--onefile",
                # Output
                f"--output-filename={output_path.name}",
                f"--output-dir={DIST_DIR}",
                # Includes — project package first, then others alphabetically
                f"--include-plugin-directory={PROJECT_ROOT / 'src'}",
                "--include-package=chatterbox_tts",
                "--include-package=chatterbox",
                "--include-package=certifi",
                "--include-package=diffusers",
                "--include-package=huggingface_hub",
                "--include-package=librosa",
                "--include-package=numpy",
                "--include-package=onnx",
                "--include-package=pandas",
                "--include-package=perth",
                "--include-package=pydantic",
                "--include-package=requests",
                "--include-package=s3tokenizer",
                "--include-package=safetensors",
                "--include-package=scipy",
                "--include-package=sklearn",
                "--include-package=soundfile",
                "--include-package=torch",
                "--include-package=tokenizers",
                "--include-package=transformers",
                "--include-package=fastapi",
                "--include-package=httpx",
                "--include-package=uvicorn",
                # Noinclude / nofollow
                "--noinclude-numba-mode=nofollow",  # only include if imported directly
                # Excludes — bloat not used by the project.
                # VERIFIED safe to exclude: gradio/gradio_client are not referenced
                # anywhere in chatterbox nor loaded by the runtime import trace.
                # The model-load chain pulls transformers/diffusers/sklearn/pandas/
                # s3tokenizer/onnx at runtime via lazy/conditional imports
                # (t3 -> transformers -> sklearn -> pandas; s3gen -> diffusers;
                #  s3tokenizer -> onnx); they are force-included above (NOT excluded)
                # so the .exe cannot fail at runtime on a missing lazy submodule.
                "--nofollow-import-to=gradio",
                "--nofollow-import-to=gradio_client",
                # transformers ships modeling_tf_*/modeling_flax_* shims that
                # Nuitka would try to follow; tensorflow/jax/flax are never
                # loaded by the runtime trace, so excluding them only silences
                # warnings and trims weight (VERIFIED: not in the import graph).
                "--nofollow-import-to=tensorflow",
                "--nofollow-import-to=jax",
                "--nofollow-import-to=flax",
                # Python flags
                "--python-flag=no_site",
                # Module parameters
                "--module-parameter=numba-disable-jit=yes",
                "--module-parameter=torch-disable-jit=yes",
                # Compiler (required for Python 3.13+)
                "--zig",
                # Download policy
                "--assume-yes-for-downloads",
                # Entry point
                str(entry_point),
            ]
            log(f"Entry point: {entry_point}")
            log(f"Output:     {output_path}")

        with StageTimer("Compile", "Compiling with Nuitka (30-60 min)"):
            # Inherit the real console (no stdout pipe). Nuitka gates its progress
            # bar on a TTY, so piping its output suppresses the bar and leaves the
            # console silent for minutes during import analysis. Letting Nuitka write
            # directly to the console preserves its native progress bar; the parent's
            # [HH:MM:SS] stage headers still bracket each phase.
            try:
                returncode = subprocess.run(nuitka_args, env=env).returncode
            except KeyboardInterrupt:
                # Ctrl+C reaches Nuitka directly (shared console); it exits on its own.
                log("\n[CANCEL] Build cancelled by user.")
                sys.exit(130)

        if returncode == 0:
            size_mb = output_path.stat().st_size / 1024 / 1024
            output_path.chmod(0o755)
            log(f"Build successful: {output_path}")
            log(f"Size: {size_mb:.1f} MB")
        else:
            log("Build failed", returncode)
            sys.exit(1)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build macOS executable")
    parser.add_argument("--arch", default="universal2",
                       choices=["x86_64", "arm64", "universal2"],
                       help="Target architecture (default: universal2)")
    args = parser.parse_args()
    check_dependencies()
    build_macos(args.arch)
