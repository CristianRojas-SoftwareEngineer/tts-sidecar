"""
Utilidades compartidas para los scripts de build.
Provee logging con timestamp [HH:MM:SS], tracking de etapas y el empaquetado
de los avisos de licencia en el bundle distribuible.
"""

import base64
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Archivos de cumplimiento de licencia que deben viajar dentro de cada artefacto
# distribuible (PyInstaller elimina los avisos de licencia de las dependencias).
LICENSE_FILES = ("LICENSE", "THIRD-PARTY-LICENSES.md")

# Fuente única del logo del proyecto (PNG 256×256), del que los tres builds
# derivan su icono nativo: PNG directo en Linux, .ico en Windows, .icns en macOS.
LOGO_SOURCE = Path(__file__).parent.parent / "assets" / "images" / "TTS Sidecar - Logo.png"

# PNG 1×1 transparente (base64) usado como placeholder de icono cuando la fuente
# del logo no existe. El AppImage exige un icono presente en el AppDir.
_PLACEHOLDER_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

# Timeout aplicado a los subprocesos de empaquetado de plataforma (appimagetool
# en Linux, create-dmg en macOS) para que un empaquetador colgado no cuelgue el job
# de CI indefinidamente; consistente con el timeout ya usado por el instalador de
# Windows (create_installer_windows.py) (SUGGESTION-05).
BUILD_SUBPROCESS_TIMEOUT = 600

# Timeout para el propio subprocess de PyInstaller, la etapa más larga del
# build (9-15 min típico según la plataforma): más holgado que
# BUILD_SUBPROCESS_TIMEOUT para no abortar una compilación legítima que
# simplemente tarda más en un runner de CI cargado (WARNING-05).
PYINSTALLER_TIMEOUT = 1800

# Versiones pineadas de las herramientas de build, espejo de las que instala
# .circleci/config.yml: un build local con estas versiones produce el mismo
# artefacto que el CI. Actualizar deliberadamente y en ambos lugares a la vez.
PYINSTALLER_PIN = "6.21.0"
INNOSETUP_PIN = "6.3.3"

# Tooling pineado del empaquetado AppImage (L-03): appimagetool empaqueta el
# AppDir y el runtime estático de type2-runtime (FUSE 3 estático con
# autoextracción de respaldo) se incrusta con --runtime-file, eliminando la
# dependencia de libfuse2 que las distros modernas ya no instalan por defecto.
# Pines por URL de release + SHA-256 (fetch_pinned_asset los verifica): misma
# política que los pines de versión de pip/choco. Actualizar deliberadamente
# URL y hash a la vez.
APPIMAGETOOL_PIN = "1.9.1"
TYPE2_RUNTIME_PIN = "20251108"
APPIMAGE_TOOLING = {
    "x86_64": {
        "appimagetool": (
            f"https://github.com/AppImage/appimagetool/releases/download/{APPIMAGETOOL_PIN}/appimagetool-x86_64.AppImage",
            "ed4ce84f0d9caff66f50bcca6ff6f35aae54ce8135408b3fa33abfc3cb384eb0",
        ),
        "runtime": (
            f"https://github.com/AppImage/type2-runtime/releases/download/{TYPE2_RUNTIME_PIN}/runtime-x86_64",
            "2fca8b443c92510f1483a883f60061ad09b46b978b2631c807cd873a47ec260d",
        ),
    },
    "aarch64": {
        "appimagetool": (
            f"https://github.com/AppImage/appimagetool/releases/download/{APPIMAGETOOL_PIN}/appimagetool-aarch64.AppImage",
            "f0837e7448a0c1e4e650a93bb3e85802546e60654ef287576f46c71c126a9158",
        ),
        "runtime": (
            f"https://github.com/AppImage/type2-runtime/releases/download/{TYPE2_RUNTIME_PIN}/runtime-aarch64",
            "00cbdfcf917cc6c0ff6d3347d59e0ca1f7f45a6df1a428a0d6d8a78664d87444",
        ),
    },
}


def module_available(module_name: str) -> bool:
    """Comprueba si un módulo Python es importable, sin importarlo.

    Invalida las cachés de los finders para que una instalación pip hecha en
    este mismo proceso (ensure_build_dependency) sea visible al re-verificar.
    """
    import importlib
    import importlib.util

    importlib.invalidate_caches()
    return importlib.util.find_spec(module_name) is not None


def ensure_build_dependency(name, check, install_cmd=None, required=False) -> bool:
    """Verifica una dependencia de build y, si falta, avisa y ofrece instalarla.

    Política única de los tres scripts de build (misma UX en Windows, Linux y
    macOS, sobre pip/brew/choco):

    - `check` (callable → bool) presente: no pregunta nada, retorna True.
    - Ausente con TTY: muestra el comando exacto (`install_cmd`, lista argv) y
      pregunta s/n; instala solo con confirmación y re-verifica con `check`.
    - Ausente sin TTY (CI) o sin `install_cmd`: no pregunta; emite la
      instrucción de instalación manual y resuelve según criticidad.
    - `required=True` distingue las dependencias del producto o del compilador
      (sin ellas el build no tiene sentido: aborta con sys.exit(1) si no se
      resuelven) de las herramientas del empaquetador (retorna False y el
      llamador degrada con warning).
    """
    if check():
        log(f"{name}: instalado")
        return True

    log(f"WARNING: {name} no está instalado")
    manual_cmd = " ".join(install_cmd) if install_cmd else None

    if install_cmd and sys.stdin.isatty():
        answer = input(f"¿Instalar {name} ahora con '{manual_cmd}'? (s/n): ")
        if answer.strip().lower() in ("s", "si", "sí", "y", "yes"):
            log(f"Instalando {name}: {manual_cmd}")
            subprocess.run(install_cmd, check=True, timeout=BUILD_SUBPROCESS_TIMEOUT)
            if check():
                log(f"{name}: instalado correctamente")
                return True
            log(f"WARNING: {name} sigue sin estar disponible tras la instalación")

    if manual_cmd:
        log(f"Instalación manual: {manual_cmd}")
    if required:
        log(f"ERROR: {name} es una dependencia requerida del build; abortando")
        sys.exit(1)
    return False


def fetch_pinned_asset(url: str, sha256: str, dest) -> Path:
    """Descarga un binario pineado verificando su SHA-256, con caché en dest.

    Si dest ya existe con el hash esperado, no descarga (caché). Si el hash
    del archivo descargado no coincide con el pin, elimina el archivo y aborta
    el build: un binario externo alterado nunca debe entrar al artefacto.
    Devuelve la ruta de dest.
    """
    import hashlib
    import urllib.request

    dest = Path(dest)

    def _sha256_of(path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()

    if dest.exists() and _sha256_of(dest) == sha256:
        log(f"{dest.name}: en caché (checksum OK)")
        return dest

    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"Descargando {url} -> {dest}")
    with urllib.request.urlopen(url, timeout=BUILD_SUBPROCESS_TIMEOUT) as resp, \
            open(dest, "wb") as out:
        shutil.copyfileobj(resp, out)

    actual = _sha256_of(dest)
    if actual != sha256:
        dest.unlink()
        log(f"ERROR: checksum de {dest.name} no coincide con el pin")
        log(f"  esperado: {sha256}")
        log(f"  obtenido: {actual}")
        sys.exit(1)
    log(f"{dest.name}: descargado y verificado (SHA-256 OK)")
    return dest


def check_pyinstaller() -> None:
    """Verifica que PyInstaller esté instalado (ofrece instalarlo si falta).

    Fuente única para los tres scripts de build: antes cada uno duplicaba este
    mismo bloque de try/except (SUGGESTION-04). Criticidad required: sin el
    compilador el build no tiene sentido.
    """
    with StageTimer("CheckDeps", "Verificando dependencias"):
        ensure_build_dependency(
            "PyInstaller",
            lambda: module_available("PyInstaller"),
            install_cmd=[sys.executable, "-m", "pip", "install", f"pyinstaller=={PYINSTALLER_PIN}"],
            required=True,
        )


def common_pyinstaller_args(
    entry_point: Path,
    project_root: Path,
    dist_dir: Path,
    build_dir: Path,
    data_sep: str,
    extra_collect_all=(),
) -> list:
    """Flags de PyInstaller compartidas por los tres scripts de build (SUGGESTION-04).

    `data_sep` es el separador de `--add-data` según el SO: ';' en Windows,
    ':' en Linux/macOS. `extra_collect_all` añade paquetes `--collect-all`
    específicos de la plataforma (p. ej. pycaw en Windows, sounddevice en
    Linux y macOS).
    """
    return [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--console",
        "--name", "tts-sidecar",
        "--paths", str(project_root / "src"),
        "--distpath", str(dist_dir),
        "--workpath", str(build_dir),
        "--specpath", str(project_root / "scripts"),
        "--noconfirm",
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
        *[flag for pkg in extra_collect_all for flag in ("--collect-all", pkg)],
        # Data files
        "--collect-data", "soundfile",
        "--collect-data", "certifi",
        # Voces de fábrica (incluida la voz 'default') en la raíz del bundle,
        # resueltas en runtime por paths.bundled_voices_dir() (sys._MEIPASS).
        "--add-data", f"{project_root / 'voices'}{data_sep}voices",
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


def bundle_size_mb(onedir) -> float:
    """Calcula el tamaño total en MB de un directorio de bundle (onedir de PyInstaller).

    Fuente única para los tres scripts de build, que antes duplicaban este
    mismo cálculo (SUGGESTION-13).
    """
    total_bytes = sum(f.stat().st_size for f in Path(onedir).rglob("*") if f.is_file())
    return total_bytes / (1024 * 1024)


def copy_license_files(dest_dir) -> None:
    """Copia LICENSE y THIRD-PARTY-LICENSES.md desde la raíz del proyecto a dest_dir.

    Se invoca tras PyInstaller en cada plataforma para que el bundle distribuible
    (onedir de Windows/Linux, .app de macOS) incluya los avisos de licencia que
    GPLv3 y las licencias permisivas de terceros exigen preservar al redistribuir.
    """
    project_root = Path(__file__).parent.parent
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    for name in LICENSE_FILES:
        src = project_root / name
        if src.exists():
            shutil.copy2(src, dest / name)
            log(f"Licencia empaquetada: {name} -> {dest}")
        else:
            log(f"WARNING: no se encontró {name} en la raíz; no se empaquetó")


def ensure_png_icon(dest_path) -> Path:
    """Copia el logo del proyecto a dest_path como icono PNG.

    Si LOGO_SOURCE no existe, materializa un PNG 1×1 transparente como
    placeholder (preserva el comportamiento previo del AppImage, que exige un
    icono presente en el AppDir). Devuelve siempre la ruta de destino.
    """
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if LOGO_SOURCE.exists():
        shutil.copy2(LOGO_SOURCE, dest)
        log(f"Icono PNG: {LOGO_SOURCE.name} -> {dest}")
    else:
        dest.write_bytes(base64.b64decode(_PLACEHOLDER_PNG_1X1))
        log(f"WARNING: no se encontró {LOGO_SOURCE}; se usó placeholder 1×1 en {dest}")
    return dest


def ensure_ico(dest_dir) -> Path:
    """Genera un .ico multi-resolución (16/32/48/256) desde el logo del proyecto.

    Devuelve la ruta del .ico generado, o None si Pillow o la fuente faltan
    (degradación con gracia: el build sigue sin icono nativo).
    """
    try:
        from PIL import Image

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        ico_path = dest / "tts-sidecar.ico"
        with Image.open(LOGO_SOURCE) as img:
            img.save(
                ico_path,
                format="ICO",
                sizes=[(16, 16), (32, 32), (48, 48), (256, 256)],
            )
        log(f"Icono ICO generado: {ico_path}")
        return ico_path
    except (ImportError, FileNotFoundError, OSError) as exc:
        log(f"WARNING: no se pudo generar el .ico ({exc}); build sin icono nativo")
        return None


def ensure_icns(dest_dir) -> Path:
    """Genera un .icns desde el logo del proyecto para el bundle .app de macOS.

    Devuelve la ruta del .icns generado, o None si Pillow o la fuente faltan
    (degradación con gracia: el .app mantiene el CFBundleIconFile vacío).
    """
    try:
        from PIL import Image

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        icns_path = dest / "tts-sidecar.icns"
        with Image.open(LOGO_SOURCE) as img:
            # Pillow escribe .icns a partir de la imagen fuente; los tamaños del
            # iconset se derivan internamente. El logo es 256×256, tamaño válido.
            img.save(icns_path, format="ICNS")
        log(f"Icono ICNS generado: {icns_path}")
        return icns_path
    except (ImportError, FileNotFoundError, OSError) as exc:
        log(f"WARNING: no se pudo generar el .icns ({exc}); .app sin icono nativo")
        return None


def get_version(init_path: Path = None) -> str:
    """Lee la versión de src/chatterbox_tts/__init__.py.

    Fuente única de versión para los tres scripts de build (Windows, Linux,
    macOS) y el generador del instalador Inno Setup. `init_path` permite
    apuntar a otro __init__.py (tests).
    """
    if init_path is None:
        init_path = Path(__file__).parent.parent / "src" / "chatterbox_tts" / "__init__.py"
    for line in init_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("__version__"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                return parts[1].strip().strip('"').strip("'")
    raise RuntimeError("Could not find __version__ in __init__.py")


def _format_duration(seconds: float) -> str:
    """Formatea segundos a string legible.

    - < 60s       → '45.2s'
    - 60s–3599s   → '1m 32.5s'
    - ≥ 3600s     → '1h 23m 45.0s'
    """
    if seconds >= 3600:
        h = int(seconds // 3600)
        remainder = seconds - h * 3600
        m = int(remainder // 60)
        s = remainder - m * 60
        return f"{h}h {m}m {s:.1f}s"
    if seconds >= 60:
        m = int(seconds // 60)
        s = seconds - m * 60
        return f"{m}m {s:.1f}s"
    return f"{seconds:.1f}s"


def log(msg: str, duration: float = None):
    """Imprime un mensaje de log con formato consistente.

    Sin duration: [HH:MM:SS] Mensaje...
    Con duration: [HH:MM:SS] Mensaje -> Done (1m 32s)
    """
    now = datetime.now().strftime("%H:%M:%S")
    if duration is not None:
        print(f"[{now}] {msg} -> Done ({_format_duration(duration)})")
    else:
        print(f"[{now}] {msg}...")


class StageTimer:
    """Context manager para temporizar una etapa de build.

    Uso:
        with StageTimer("NombreEtapa", "Descripción"):
            # código a temporizar
    """

    def __init__(self, name: str, description: str = None):
        self.name = name
        self.description = description or name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        print()
        log(f"[{self.name}] {self.description}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start
        log(f"[{self.name}]", duration)
        print()
        return False


class BuildTimer:
    """Context manager para temporizar el proceso de build completo.

    A diferencia de StageTimer (que mide etapas individuales), BuildTimer
    envuelve todo el build e imprime cabeceras de inicio y fin globales.
    """

    def __init__(self):
        self.start = None
        self.duration = None

    def __enter__(self):
        self.start = time.time()
        print()
        log("=== BUILD INICIADO ===")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.duration = time.time() - self.start
        if exc_type is None:
            log("=== BUILD COMPLETADO ===", self.duration)
        else:
            log("=== BUILD FALLIDO ===", self.duration)
        print()
        return False
