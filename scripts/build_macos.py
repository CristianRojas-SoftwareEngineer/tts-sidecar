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
from build_utils import (
    log, StageTimer, BuildTimer, copy_license_files, get_version,
    check_pyinstaller, common_pyinstaller_args, bundle_size_mb,
    ensure_icns, ensure_build_dependency,
    BUILD_SUBPROCESS_TIMEOUT, PYINSTALLER_TIMEOUT,
)


def check_dependencies():
    """Check required dependencies are installed."""
    check_pyinstaller()

    with StageTimer("CheckDeps", "Verificando dependencias"):
        # create-dmg es un script de shell (Homebrew), no un paquete de
        # PyPI: se invoca como binario vía subprocess, no se importa como
        # módulo Python. Es herramienta del empaquetador (opcional): sin
        # ella el .app sigue siendo usable y el stage DMG degrada con warning.
        # brew no soporta pin simple de versión, así que se instala sin pin;
        # sin brew disponible solo queda el mensaje de instalación manual.
        has_brew = shutil.which("brew") is not None
        present = ensure_build_dependency(
            "create-dmg",
            lambda: shutil.which("create-dmg") is not None,
            install_cmd=["brew", "install", "create-dmg"] if has_brew else None,
            required=False,
        )
        if not present and not has_brew:
            log("Instalación manual: brew install create-dmg (requiere Homebrew)")


def build_macos(target_arch="universal2"):
    """Build macOS .app bundle with PyInstaller --onedir."""
    arch_options = {"x86_64": "x86_64", "arm64": "arm64", "universal2": "universal2"}
    arch_flag = arch_options.get(target_arch, "universal2")

    with BuildTimer():
        with StageTimer("Setup", "Preparando entorno de build"):
            log(f"Plataforma: macOS {arch_flag}")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            BUILD_DIR.mkdir(parents=True, exist_ok=True)
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"

        with StageTimer("PyInstaller", "Compilando con PyInstaller (9-15 min)"):
            # No sounddevice, no pycaw — afplay (built-in) es el player de macOS.
            pyinstaller_args = common_pyinstaller_args(
                entry_point, PROJECT_ROOT, DIST_DIR, BUILD_DIR,
                data_sep=":",
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

        with StageTimer("AppBundle", "Estructurando como bundle .app"):
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

            # Genera el .icns del logo en Contents/Resources (None si Pillow o la
            # fuente faltan; en ese caso el .app queda sin icono nativo).
            icns_path = ensure_icns(app_bundle / "Contents" / "Resources")
            icon_name = icns_path.stem if icns_path else None

            # Write Info.plist
            info_plist = app_bundle / "Contents" / "Info.plist"
            version = get_version()
            info_plist.write_text(_info_plist_content(version, icon_name), encoding="utf-8")

            # Empaqueta los avisos de licencia dentro de Contents/Resources
            copy_license_files(app_bundle / "Contents" / "Resources")
            log(f".app bundle: {app_bundle}")

        with StageTimer("DMG", "Creando .dmg"):
            dmg_path = DIST_DIR / f"tts-sidecar-{get_version()}-{arch_flag}.dmg"

            # Staging del contenido del volumen: el .app + scripts de instalación y
            # desinstalación. Cada SO integra el PATH con un mecanismo distinto:
            # Windows lo hace automáticamente desde el instalador Inno Setup, Linux
            # vía `tts-sidecar setup` (symlink de $APPIMAGE en ~/.local/bin), y en
            # macOS estos scripts .command son el mecanismo opt-in (symlink en
            # /usr/local/bin con sudo, más la oferta de ejecutar `setup`).
            dmg_src = DIST_DIR / "dmg_src"
            if dmg_src.exists():
                shutil.rmtree(dmg_src)
            dmg_src.mkdir(parents=True)
            staged_app = dmg_src / app_bundle.name
            shutil.copytree(app_bundle, staged_app, symlinks=True)

            install_script = dmg_src / "Instalar (PATH + modelo).command"
            install_script.write_text(_path_install_script(app_bundle.name), encoding="utf-8")
            os.chmod(install_script, 0o755)

            uninstall_script = dmg_src / "Desinstalar (quitar del PATH).command"
            uninstall_script.write_text(_path_uninstall_script(), encoding="utf-8")
            os.chmod(uninstall_script, 0o755)

            create_dmg_args = [
                "create-dmg",
                "--volname", "tts-sidecar",
                "--window-pos", "200", "120",
                "--icon-size", "100",
                "--icon", app_bundle.name, "150", "185",
                "--hide-extension", app_bundle.name,
                "--app-drop-link", "480", "185",
                "--format", "ULFO",
            ]
            # Icono de volumen del .dmg (logo del proyecto) si el .icns está disponible.
            if icns_path and icns_path.exists():
                create_dmg_args += ["--volicon", str(icns_path)]
            create_dmg_args += [str(dmg_path), str(dmg_src)]

            result = subprocess.run(
                create_dmg_args,
                capture_output=True, text=True,
                timeout=BUILD_SUBPROCESS_TIMEOUT,
            )
            if result.returncode != 0:
                log("La creación del .dmg falló (create-dmg puede requerir brew install create-dmg)")
                log("WARNING: .dmg no creado — el bundle .app sigue en dist/")
            else:
                log(f".dmg creado: {dmg_path}")


def _path_install_script(app_name: str) -> str:
    """Genera el script de instalación del .dmg: PATH + oferta de provisión.

    Se incluye en el volumen del .dmg con doble función: enlaza tts-sidecar en
    /usr/local/bin y a continuación ofrece ejecutar `tts-sidecar setup` (descarga
    del modelo) como el usuario actual, replicando el checkbox post-instalación
    del instalador de Windows.

    Superficie de `sudo` (SUGGESTION-07): el script pide privilegios de administrador
    solo para `mkdir -p /usr/local/bin` y `ln -sf` — nunca se ejecuta con privilegios
    elevados como parte del build en CI; el usuario final lo ejecuta manualmente y ve
    el prompt de contraseña del sistema, igual que cualquier post-instalador de macOS
    que publique un binario fuera del propio bundle `.app`. `setup` se ejecuta SIN
    sudo para que la caché de HuggingFace quede en el perfil del usuario real.
    """
    return f"""#!/bin/bash
# Expone tts-sidecar en el PATH creando un symlink en /usr/local/bin y
# ofrece descargar el modelo de voz (tts-sidecar setup).
set -e

APP="/Applications/{app_name}"
TARGET="$APP/Contents/MacOS/tts-sidecar"
LINK="/usr/local/bin/tts-sidecar"

if [ ! -x "$TARGET" ]; then
    echo "No se encontró {app_name} en /Applications."
    echo "Arrastra primero {app_name} a la carpeta Aplicaciones y vuelve a ejecutar este script."
    exit 1
fi

sudo mkdir -p /usr/local/bin
sudo ln -sf "$TARGET" "$LINK"
echo "Listo: 'tts-sidecar' está disponible en la terminal (via $LINK)."
echo
echo "El modelo de voz (es-mx-latam, varios cientos de MB) no viene incluido:"
echo "se descarga una sola vez con 'tts-sidecar setup'."
read -p "¿Descargar ahora el modelo de voz? (s/n): " RESPUESTA
case "$RESPUESTA" in
    [sSyY]*)
        "$TARGET" setup
        ;;
    *)
        echo "Puedes hacerlo más tarde con: tts-sidecar setup"
        ;;
esac
"""


def _path_uninstall_script() -> str:
    """Genera el script de desinstalación del .dmg: revierte el symlink de PATH.

    Elimina /usr/local/bin/tts-sidecar (con sudo) solo si es un symlink; si no
    existe lo informa y termina sin error, y si es un archivo regular homónimo
    lo rechaza sin tocarlo. El .app se elimina arrastrándolo a la Papelera.
    """
    return """#!/bin/bash
# Quita el symlink de tts-sidecar de /usr/local/bin (reversión de la instalación).
set -e

LINK="/usr/local/bin/tts-sidecar"

if [ -L "$LINK" ]; then
    sudo rm "$LINK"
    echo "Symlink eliminado: $LINK"
    echo "Para completar la desinstalación, arrastra tts-sidecar.app a la Papelera."
elif [ -e "$LINK" ]; then
    echo "$LINK existe pero no es un symlink; no se elimina."
    exit 1
else
    echo "No hay nada que quitar: $LINK no existe."
fi
"""


def _info_plist_content(version, icon_name=None):
    """Genera el contenido XML del Info.plist del bundle .app para macOS.

    Define los metadatos del bundle (CFBundleIdentifier, CFBundleVersion, etc.)
    que macOS usa para identificar la aplicación en el sistema. `icon_name` es el
    nombre del .icns sin extensión (convención de CFBundleIconFile); si es None,
    el campo queda vacío (Finder muestra el icono genérico).
    """
    icon_value = icon_name or ""
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
    <string>{icon_value}</string>
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
