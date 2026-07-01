#!/usr/bin/env python3
"""
Build script for macOS x64 and ARM64 apps using PyInstaller --onedir.
Produces a .app bundle (macOS application) inside the --onedir folder.

macOS uses afplay (built-in) for audio — no sounddevice or pycaw needed.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log, StageTimer, BuildTimer, copy_license_files


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

        # create-dmg for .dmg packaging
        try:
            import create_dmg
            log("create-dmg: installed")
        except ImportError:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "create-dmg"],
                capture_output=True,
            )
            if result.returncode != 0:
                log("create-dmg not installed (optional for .dmg generation)")
            else:
                log("create-dmg: installed")


def build_macos(target_arch="universal2"):
    """Build macOS .app bundle with PyInstaller --onedir."""
    arch_options = {"x86_64": "x86_64", "arm64": "arm64", "universal2": "universal2"}
    arch_flag = arch_options.get(target_arch, "universal2")

    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log(f"Platform: macOS {arch_flag}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"

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
                str(entry_point),
                # Collect all packages (no sounddevice, no pycaw — afplay is built-in)
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
                "--collect-data", "soundfile",
                "--collect-data", "certifi",
                "--recursive-copy-metadata", "chatterbox-tts",
                "--copy-metadata", "requests",
                # Exclude bloat
                "--exclude-module", "tensorflow",
                "--exclude-module", "jax",
                "--exclude-module", "flax",
                "--exclude-module", "gradio",
                "--exclude-module", "gradio_client",
            ]
            log(f"Running: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(pyinstaller_args).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelled by user.")
                sys.exit(130)

        if returncode != 0:
            log("PyInstaller failed", returncode)
            sys.exit(1)

        onedir = DIST_DIR / "tts-sidecar"
        with StageTimer("Size", "Checking bundle size"):
            if onedir.exists():
                size_mb = sum(
                    f.stat().st_size for f in onedir.rglob("*") if f.is_file()
                ) / 1024 / 1024
                log(f"Bundle size: {size_mb:.1f} MB ({onedir})")

        with StageTimer("AppBundle", "Structuring as .app bundle"):
            # Convert: dist/tts-sidecar/ → dist/tts-sidecar.app/Contents/MacOS/
            app_bundle = DIST_DIR / f"tts-sidecar-{arch_flag}.app"
            macos_dir = app_bundle / "Contents" / "MacOS"
            macos_dir.mkdir(parents=True, exist_ok=True)

            if onedir.exists():
                # Move the executable and _internal/ into Contents/MacOS/
                for item in onedir.iterdir():
                    dest = macos_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    shutil.move(str(item), str(dest))
                shutil.rmtree(onedir)

            # Write Info.plist
            info_plist = app_bundle / "Contents" / "Info.plist"
            version = _get_version()
            info_plist.write_text(_info_plist_content(version), encoding="utf-8")

            # Empaqueta los avisos de licencia dentro de Contents/Resources
            copy_license_files(app_bundle / "Contents" / "Resources")
            log(f".app bundle: {app_bundle}")

        with StageTimer("DMG", "Creating .dmg"):
            dmg_path = DIST_DIR / f"tts-sidecar-{arch_flag}.dmg"
            result = subprocess.run(
                [
                    "create-dmg",
                    "--volname", "tts-sidecar",
                    "--window-pos", "200", "120",
                    "--icon-size", "100",
                    "--icon", "tts-sidecar", "150", "185",
                    "--hide-extension", "tts-sidecar.app",
                    "--app-drop-link", "480", "185",
                    "--format", "ULFO",
                    str(dmg_path),
                    str(app_bundle),
                ],
                capture_output=True, text=True,
            )
            if result.returncode != 0:
                log("dmg creation failed (create-dmg may need brew install create-dmg)",)
                log("WARNING: .dmg not created — .app bundle is still in dist/")
            else:
                log(f".dmg created: {dmg_path}")


def _get_version():
    """Read version from __init__.py."""
    init_path = PROJECT_ROOT / "src" / "chatterbox_tts" / "__init__.py"
    for line in init_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("__version__"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().strip('"').strip("'")
    return "0.1.0"


def _info_plist_content(version):
    """Genera el contenido XML del Info.plist del bundle .app para macOS.

    Define los metadatos del bundle (CFBundleIdentifier, CFBundleVersion, etc.)
    que macOS usa para identificar la aplicación en el sistema.
    """
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>tts-sidecar</string>
    <key>CFBundleIdentifier</key>
    <string>com.tts-sidecar.app</string>
    <key>CFBundleName</key>
    <string>tts-sidecar</string>
    <key>CFBundleDisplayName</key>
    <string>tts-sidecar</string>
    <key>CFBundleVersion</key>
    <string>{version}</string>
    <key>CFBundleShortVersionString</key>
    <string>{version}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleIconFile</key>
    <string></string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.utilities</string>
    <key>NSHumanReadableCopyright</key>
    <string>GPL-3.0-or-later</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
"""


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build macOS .app bundle")
    parser.add_argument(
        "--arch", default="universal2",
        choices=["x86_64", "arm64", "universal2"],
        help="Target architecture (default: universal2)",
    )
    args = parser.parse_args()
    check_dependencies()
    build_macos(args.arch)
