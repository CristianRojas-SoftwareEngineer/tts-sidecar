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
    fetch_pinned_asset, APPIMAGE_TOOLING,
    BUILD_SUBPROCESS_TIMEOUT, PYINSTALLER_TIMEOUT,
)

# Mapea la arquitectura del CLI (--arch) al vocabulario `uname -m` que usan
# los assets del tooling y el nombre del artefacto final.
ARCH_MAP = {"x86_64": "x86_64", "arm64": "aarch64"}


def provision_appimage_tooling(appimage_arch):
    """Provisiona el tooling pineado del AppImage (appimagetool + runtime estático).

    Descarga (o reutiliza de la caché en build/) los binarios pineados por URL y
    SHA-256 en APPIMAGE_TOOLING. Es tooling del empaquetador (opcional): ante un
    fallo de red devuelve None y el llamador degrada con warning (el onedir sigue
    siendo usable). Un checksum que no coincide sí aborta (fetch_pinned_asset):
    un binario externo alterado nunca debe entrar al pipeline.
    """
    import urllib.error

    tooling = APPIMAGE_TOOLING[appimage_arch]
    cache_dir = BUILD_DIR / "appimage-tooling"
    try:
        tool_url, tool_sha = tooling["appimagetool"]
        appimagetool = fetch_pinned_asset(
            tool_url, tool_sha, cache_dir / f"appimagetool-{appimage_arch}.AppImage")
        runtime_url, runtime_sha = tooling["runtime"]
        runtime = fetch_pinned_asset(
            runtime_url, runtime_sha, cache_dir / f"runtime-{appimage_arch}")
    except (urllib.error.URLError, OSError) as exc:
        log(f"WARNING: no se pudo descargar el tooling del AppImage ({exc})")
        return None
    os.chmod(appimagetool, 0o755)
    return appimagetool, runtime


def check_dependencies(target_arch="x86_64"):
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

        # appimagetool + runtime estático empaquetan el AppImage a partir del
        # bundle onedir; es tooling del empaquetador (opcional): sin él el
        # onedir sigue siendo usable y el stage AppImage degrada con warning.
        if provision_appimage_tooling(ARCH_MAP.get(target_arch, "x86_64")) is None:
            log("WARNING: el stage AppImage se omitirá si el tooling sigue sin estar disponible")


def build_linux(target_arch="x86_64"):
    """Build Linux with PyInstaller --onedir and package as AppImage."""
    arch_suffix = ARCH_MAP.get(target_arch, "x86_64")
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
            # Tooling pineado (appimagetool + runtime estático de type2-runtime,
            # L-03): el runtime estático arranca sin libfuse2, ausente por
            # defecto en distros modernas. Provisión cacheada en build/ (si
            # check_dependencies ya descargó, esto es instantáneo).
            tooling = provision_appimage_tooling(appimage_arch)
            if tooling is None:
                log("WARNING: tooling del AppImage no disponible — AppImage no "
                    "generado; el bundle onedir sigue en dist/")
                return
            appimagetool, runtime = tooling

            version = get_version()

            # Prepara el AppDir a partir del bundle onedir de PyInstaller (ya
            # autocontenido: incluye su propio Python y todas las dependencias).
            appdir = BUILD_DIR / "AppDir"
            if appdir.exists():
                shutil.rmtree(appdir)
            usr_bin = appdir / "usr" / "bin"
            usr_bin.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(onedir, usr_bin, symlinks=True)

            # AppRun: el runtime del AppImage lo ejecuta como entry point; delega
            # en el ejecutable del bundle pasando los argumentos tal cual.
            apprun = appdir / "AppRun"
            apprun.write_text(
                '#!/bin/sh\n'
                'HERE="$(dirname "$(readlink -f "$0")")"\n'
                'exec "$HERE/usr/bin/tts-sidecar" "$@"\n',
                encoding="utf-8",
            )
            os.chmod(apprun, 0o755)

            # .desktop e icono: appimagetool los exige en la raíz del AppDir;
            # se replican en usr/share/ (ubicación estándar freedesktop).
            desktop_content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=tts-sidecar\n"
                "Exec=tts-sidecar\n"
                "Icon=tts-sidecar\n"
                "Categories=Utility;\n"
                "Terminal=true\n"
            )
            (appdir / "tts-sidecar.desktop").write_text(desktop_content, encoding="utf-8")
            applications_dir = appdir / "usr" / "share" / "applications"
            applications_dir.mkdir(parents=True, exist_ok=True)
            (applications_dir / "tts-sidecar.desktop").write_text(desktop_content, encoding="utf-8")

            # Icono del AppImage: el logo oficial del proyecto (placeholder 1×1
            # solo si la fuente del logo faltara).
            ensure_png_icon(appdir / "tts-sidecar.png")
            ensure_png_icon(appdir / "usr" / "share" / "icons" / "hicolor"
                            / "256x256" / "apps" / "tts-sidecar.png")

            # appimagetool escribe la ruta de salida directamente; el propio
            # appimagetool es un AppImage, así que --appimage-extract-and-run
            # evita requerir FUSE también en los executors del CI.
            generated = DIST_DIR / f"tts-sidecar-{version}-{appimage_arch}.AppImage"
            env = os.environ.copy()
            env["ARCH"] = appimage_arch
            result = subprocess.run(
                [str(appimagetool), "--appimage-extract-and-run",
                 "--runtime-file", str(runtime),
                 str(appdir), str(generated)],
                cwd=str(PROJECT_ROOT),
                env=env,
                capture_output=True, text=True,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0 or not generated.exists():
                log(f"La generación del AppImage falló (rc={result.returncode})")
                print(result.stdout)
                print(result.stderr, file=sys.stderr)
                log("WARNING: AppImage falló — el bundle onedir sigue en dist/")
                return

            log(f"AppImage creado: {generated}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build Linux executable")
    parser.add_argument(
        "--arch", default="x86_64", choices=["x86_64", "arm64"],
        help="Target architecture",
    )
    args = parser.parse_args()
    check_dependencies(args.arch)
    build_linux(args.arch)
