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
    check_pyinstaller, common_pyinstaller_args, bundle_size_mb, run_pyinstaller,
    ensure_png_icon, check_sounddevice,
    install_lockfile_dependencies, fetch_pinned_asset, APPIMAGE_TOOLING,
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


def _apprun_script() -> str:
    """Contenido del entry point AppRun del AppImage.

    El runtime del AppImage ejecuta este script; se limita a localizar el
    directorio real del AppDir (resolviendo symlinks) y delegar en el ejecutable
    del bundle onedir con los argumentos tal cual. Pura función (sin I/O) para
    poder testearla desde tests/test_build_linux.py (R-24).
    """
    return (
        '#!/bin/sh\n'
        'HERE="$(dirname "$(readlink -f "$0")")"\n'
        'exec "$HERE/usr/bin/tts-sidecar" "$@"\n'
    )


def _desktop_entry() -> str:
    """Contenido del archivo .desktop del AppImage (estándar freedesktop).

    Appimagetool exige este archivo en la raíz del AppDir; se replica en
    usr/share/applications/ para la convención del estándar. El Terminal=true
    mantiene visible la salida del CLI (paridad con el .command de macOS).
    """
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=tts-sidecar\n"
        "Exec=tts-sidecar\n"
        "Icon=tts-sidecar\n"
        "Categories=Utility;\n"
        "Terminal=true\n"
    )


def ensure_runtime_dependencies(target_arch="x86_64"):
    """Instala las dependencias runtime desde el lockfile (requerido para builds reproducibles).

    En x86_64 usa requirements-lock-linux-cpu.txt (CPU-only, sin paquetes nvidia-*).
    En arm64 usa requirements-lock.txt (universal, los wheels CPU-only se resuelven
    automáticamente por platform_machine == 'arm64' en el lockfile). Solo resuelve
    el lockfile correcto por arquitectura; la instalación en sí (existencia, pip
    --require-hashes, manejo de timeout/fallo) vive en
    build_utils.install_lockfile_dependencies, fuente única compartida con
    build_windows.py y build_macos.py (S2-06).
    """
    if target_arch == "x86_64":
        lockfile = PROJECT_ROOT / "requirements-lock-linux-cpu.txt"
    else:
        lockfile = PROJECT_ROOT / "requirements-lock.txt"
    install_lockfile_dependencies(lockfile)


def check_dependencies(target_arch="x86_64"):
    """Check required dependencies are installed."""
    check_pyinstaller()
    ensure_runtime_dependencies(target_arch)

    with StageTimer("CheckDeps", "Verificando dependencias"):
        # sounddevice es dependencia del producto (sin ella el bundle saldría
        # sin audio): required. check_sounddevice es fuente única compartida
        # con build_macos.py (S2-06).
        check_sounddevice()

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
            # run_pyinstaller gestiona el timeout con kill de árbol de procesos
            # (build_utils); en Linux la invocación es directa (sin wrapper COM).
            try:
                returncode = run_pyinstaller(pyinstaller_args, PYINSTALLER_TIMEOUT)
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelado por el usuario.")
                sys.exit(130)

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
            apprun.write_text(_apprun_script(), encoding="utf-8")
            os.chmod(apprun, 0o755)

            # .desktop e icono: appimagetool los exige en la raíz del AppDir;
            # se replican en usr/share/ (ubicación estándar freedesktop).
            desktop_content = _desktop_entry()
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
            # Consola heredada (sin capture_output): el output de appimagetool es
            # el heartbeat del step de CI. Su fallo es fatal: un build sin AppImage
            # nunca debe reportar éxito (publish-release exige el artefacto).
            result = subprocess.run(
                [str(appimagetool), "--appimage-extract-and-run",
                 "--runtime-file", str(runtime),
                 str(appdir), str(generated)],
                cwd=str(PROJECT_ROOT),
                env=env,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0 or not generated.exists():
                log(f"ERROR: La generación del AppImage falló (rc={result.returncode})")
                sys.exit(1)

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
