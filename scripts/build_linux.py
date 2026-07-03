#!/usr/bin/env python3
"""
Build script for Linux x64 and ARM64 using PyInstaller --onedir.
Produces a folder with the executable + all dependencies, then wraps it
in an AppImage for distribution.
"""

import os
import shutil
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

sys.path.insert(0, str(Path(__file__).parent))
from build_utils import (
    log, StageTimer, BuildTimer, copy_license_files, get_version,
    check_pyinstaller, common_pyinstaller_args, bundle_size_mb,
    ensure_png_icon, ensure_build_dependency, module_available,
    BUILD_SUBPROCESS_TIMEOUT, PYINSTALLER_TIMEOUT, APPIMAGE_BUILDER_PIN,
)


def check_dependencies():
    """Check required dependencies are installed."""
    check_pyinstaller()

    with StageTimer("CheckDeps", "Verificando dependencias"):
        # sounddevice es dependencia del producto (sin ella el bundle saldría
        # sin audio): required. Sin pin: es dependencia de runtime gobernada
        # por requirements.txt, no una herramienta de build.
        ensure_build_dependency(
            "sounddevice",
            lambda: module_available("sounddevice"),
            install_cmd=[sys.executable, "-m", "pip", "install", "sounddevice"],
            required=True,
        )

        # appimage-builder genera el AppImage a partir del bundle onedir;
        # es herramienta del empaquetador (opcional): sin ella el onedir
        # sigue siendo usable y el stage AppImage degrada con warning.
        ensure_build_dependency(
            "appimage-builder",
            lambda: module_available("appimagebuilder"),
            install_cmd=[sys.executable, "-m", "pip", "install",
                         f"appimage-builder=={APPIMAGE_BUILDER_PIN}"],
            required=False,
        )


def build_linux(target_arch="x86_64"):
    """Build Linux with PyInstaller --onedir and package as AppImage."""
    arch_map = {"x86_64": "x86_64", "arm64": "aarch64"}
    arch_suffix = arch_map.get(target_arch, "x86_64")
    appimage_arch = arch_suffix  # mismo mapeo; alias para mayor claridad en la sección AppImage

    with BuildTimer():
        with StageTimer("Setup", "Preparando entorno de build"):
            log(f"Plataforma: Linux {arch_suffix}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"

        with StageTimer("PyInstaller", "Compilando con PyInstaller (9-15 min)"):
            pyinstaller_args = common_pyinstaller_args(
                entry_point, PROJECT_ROOT, DIST_DIR, BUILD_DIR,
                data_sep=":",
                extra_collect_all=["sounddevice"],
            )
            log(f"Ejecutando: pyinstaller {' '.join(pyinstaller_args[2:])}")
            try:
                returncode = subprocess.run(
                    pyinstaller_args,
                    timeout=PYINSTALLER_TIMEOUT,
                ).returncode
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelado por el usuario.")
                sys.exit(130)
            except subprocess.TimeoutExpired:
                log(f"\n[TIMEOUT] PyInstaller excedió {PYINSTALLER_TIMEOUT}s.")
                sys.exit(1)

        if returncode != 0:
            log("PyInstaller falló", returncode)
            sys.exit(1)

        onedir = DIST_DIR / "tts-sidecar"
        with StageTimer("Size", "Verificando tamaño del bundle"):
            if onedir.exists():
                log(f"Tamaño del bundle: {bundle_size_mb(onedir):.1f} MB ({onedir})")

        with StageTimer("Licenses", "Empaquetando avisos de licencia"):
            copy_license_files(onedir)

        with StageTimer("AppImage", "Generando AppImage"):
            appimageyml = PROJECT_ROOT / "scripts" / "tts-sidecar.yml"
            if not appimageyml.exists():
                log("WARNING: tts-sidecar.yml no encontrado — AppImage no generado.")
                log(f"Crea {appimageyml} con la configuración de appimage-builder.")
                return

            if not shutil.which("appimage-builder"):
                log("WARNING: appimage-builder no disponible — AppImage no generado; "
                    "el bundle onedir sigue en dist/")
                return

            # El spec toma la versión y la arquitectura del entorno.
            version = get_version()
            env = os.environ.copy()
            env["APP_VERSION"] = version
            env["TARGET_ARCH"] = appimage_arch

            # appimage-builder requiere un icono presente en el AppDir; materializa
            # el logo del proyecto (o un placeholder 1×1 si la fuente faltara).
            ensure_png_icon(PROJECT_ROOT / "tts-sidecar.png")

            result = subprocess.run(
                ["appimage-builder", "--recipe", str(appimageyml), "--skip-test"],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True, text=True,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                log(f"La generación del AppImage falló (rc={result.returncode})")
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                log("WARNING: AppImage falló — el bundle onedir sigue en dist/")
                return

            # appimage-builder deja el .AppImage en el cwd (PROJECT_ROOT); localizarlo
            # y moverlo a dist/ con el nombre canónico versión + arquitectura.
            generated = DIST_DIR / f"tts-sidecar-{version}-{appimage_arch}.AppImage"
            candidates = sorted(PROJECT_ROOT.glob("*.AppImage")) + sorted(DIST_DIR.glob("*.AppImage"))
            src = next((c for c in candidates if c != generated), None)
            if src and src.exists():
                if generated.exists():
                    generated.unlink()
                src.rename(generated)
                log(f"AppImage creado: {generated}")
            elif generated.exists():
                log(f"AppImage creado: {generated}")
            else:
                log("WARNING: appimage-builder corrió pero no se encontró ningún .AppImage")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Linux executable")
    parser.add_argument(
        "--arch", default="x86_64", choices=["x86_64", "arm64"],
        help="Target architecture",
    )
    args = parser.parse_args()
    check_dependencies()
    build_linux(args.arch)
