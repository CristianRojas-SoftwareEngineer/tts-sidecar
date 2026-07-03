# Guía de Construcción

`tts-sidecar` se compila con **PyInstaller** (empaquetado de Python bytecode) para obtener un ejecutable autocontenido multiplataforma, luego se envuelve en un instalador por SO.

---

## 1. Requisitos

- **Python 3.13+** ([python.org](https://www.python.org/downloads/))
- **PyInstaller** (`pip install pyinstaller`)

### Herramientas de empaquetado por plataforma

| Plataforma | Herramienta | Instalación |
|------------|-------------|-------------|
| Windows | Inno Setup 6 | `choco install innosetup -y --version=6.3.3` o [jrsoftware.org](https://jrsoftware.org/isdl.php) |
| Linux | appimagetool + runtime estático (type2-runtime) | Descarga automática pineada por URL + SHA-256 (`build_linux.py`); sin instalación manual |
| macOS | create-dmg | `brew install create-dmg` (script de shell de Homebrew, no existe en PyPI) |

### Política interactiva de dependencias de build

Los tres scripts de build comparten una única política, implementada en
`build_utils.ensure_build_dependency`: **verificar → avisar → preguntar →
instalar pineado o degradar**. Si una herramienta falta y hay TTY, el script
muestra el comando exacto de instalación y pregunta s/n; sin TTY (CI) no
pregunta, emite la instrucción manual y resuelve según criticidad:

- **Requeridas** (PyInstaller, sounddevice en Linux y macOS): sin ellas el
  build no tiene sentido; el script aborta si no se resuelven.
- **Empaquetadores** (appimagetool, create-dmg, Inno Setup): sin ellos el
  bundle onedir/.app sigue siendo usable; el stage degrada con warning.

Las versiones pineadas viven como constantes en `scripts/build_utils.py`
(`PYINSTALLER_PIN=6.21.0`, `INNOSETUP_PIN=6.3.3`), espejo de las que instala
`.circleci/config.yml`: un build local produce el mismo artefacto que el CI.
El tooling del AppImage no se instala vía pip: `APPIMAGE_TOOLING` pinea las
URLs de release de `appimagetool` (`APPIMAGETOOL_PIN=1.9.1`) y del runtime
estático de type2-runtime (`TYPE2_RUNTIME_PIN=20251108`) con su SHA-256 por
arquitectura; `build_linux.py` los descarga a `build/appimage-tooling/`
verificando el checksum (`fetch_pinned_asset`). El runtime estático arranca
sin `libfuse2` (ausente por defecto en distros modernas), garantizando el
primer arranque del AppImage en cualquier distro.

---

## 2. Plataformas Soportadas

| Plataforma | Comando | Artefacto |
|------------|---------|-----------|
| Windows x64 | `python scripts/build_windows.py` | `dist/tts-sidecar-0.1.0-x86_64-setup.exe` (instalador) |
| Linux x64 | `python scripts/build_linux.py --arch x86_64` | `dist/tts-sidecar-0.1.0-x86_64.AppImage` |
| Linux ARM64 | `python scripts/build_linux.py --arch arm64` | `dist/tts-sidecar-0.1.0-aarch64.AppImage` |
| macOS universal2 | `python scripts/build_macos.py --arch universal2` | `dist/tts-sidecar-0.1.0-universal2.dmg` |

> Los scripts de build también generan la carpeta `--onedir` en `dist/tts-sidecar/` (o
> `dist/tts-sidecar.app/` en macOS) con el ejecutable y todas las dependencias,
> útil para pruebas directas sin pasar por el instalador.

---

## 3. Compilación Local

### Verificación de sintaxis

Antes de compilar, verificar que el código Python no tenga errores:

```bash
python -m py_compile src/chatterbox_tts/engine.py
python -m py_compile src/chatterbox_tts/cli.py
python -m py_compile src/chatterbox_tts/audio.py
python -m py_compile src/chatterbox_tts/timing.py
python -m py_compile src/chatterbox_tts/daemon/*.py
```

### Scripts de build

```bash
# Windows (requiere Inno Setup instalado)
python scripts/build_windows.py

# Linux (descarga appimagetool + runtime estático, pineados por SHA-256)
python scripts/build_linux.py --arch x86_64

# macOS (requiere create-dmg)
python scripts/build_macos.py --arch universal2
```

Los scripts (`scripts/build_*.py`) ejecutan PyInstaller con `--onedir` y luego llaman
a la herramienta de empaquetado correspondiente para producir el instalador final.

> El entry point `bin/tts-sidecar` es la semilla que PyInstaller empaqueta. El bundle
> resultante hereda ese nombre en `dist/tts-sidecar/`. Véase `docs/ARCHITECTURE.md` para
> el detalle del entry point.

### Opciones clave de PyInstaller

```bash
python -m PyInstaller --onedir --console \
  --name tts-sidecar \
  --paths src \
  --collect-all chatterbox --collect-all transformers \
  --collect-all diffusers --collect-all torch \
  --collect-all sklearn --collect-all pandas \
  --recursive-copy-metadata chatterbox-tts \
  --copy-metadata requests \
  --exclude-module tensorflow --exclude-module gradio \
  bin/tts-sidecar
```

Los flags `--collect-all` aseguran que PyInstaller empaquete paquetes con extensiones
nativas o imports lazy que no siguen automáticamente. Los flags de metadata (`--recursive-copy-metadata`) son necesarios para que `importlib.metadata` y `pkg_resources` encuentren los metadatos de paquete en el bundle congelado.

### Verificación post-build

```bash
# Tests
pytest tests/ -v

# Ejecutable directo (carpeta onedir)
dist/tts-sidecar/tts-sidecar.exe version
dist/tts-sidecar/tts-sidecar.exe doctor

# Provisionar el modelo es-mx-latam (chequeos + descarga si falta; idempotente)
dist/tts-sidecar/tts-sidecar.exe setup

# Instalador (Windows)
dist/tts-sidecar-0.1.0-x86_64-setup.exe
```

### Matriz de integración con el SO

Cada plataforma integra `tts-sidecar` en el sistema con un mecanismo distinto,
pero la experiencia resultante es homóloga (comando en el PATH + provisión
guiada + desinstalación limpia):

| Aspecto | Windows | Linux | macOS |
|---------|---------|-------|-------|
| PATH | Automático: el instalador agrega `{app}` al PATH del sistema | `tts-sidecar setup` crea el symlink `~/.local/bin/tts-sidecar → $APPIMAGE` | Opt-in: `Instalar (PATH + modelo).command` del `.dmg` (symlink en `/usr/local/bin`, con sudo) |
| Guía hacia `setup` | Página informativa + casilla post-instalación que lo ejecuta en contexto de usuario | `setup` es el punto único de provisión (modelo + PATH) | El script de instalación ofrece ejecutar `setup` (sin sudo) tras enlazar |
| Desinstalación | Desinstalador de Inno Setup (revierte PATH y registro) | `tts-sidecar setup --remove-path` + borrar el `.AppImage` | `Desinstalar (quitar del PATH).command` del `.dmg` + arrastrar el `.app` a la Papelera |
| Dependencias de build | Política interactiva común (`ensure_build_dependency`) | Ídem | Ídem |

> El modelo `es-mx-latam` se descarga a `~/.cache/huggingface/hub` y no se
> empaqueta en el ejecutable; `speak` y `daemon start` fallan rápido remitiendo
> a `setup` mientras falte.

### Limitación conocida: firma de código y notarización

Los artefactos **no están firmados ni notarizados**: en macOS, Gatekeeper
bloquea la primera apertura del `.app`/`.dmg` (clic derecho → Abrir, o
`xattr -d com.apple.quarantine`); en Windows, SmartScreen muestra la advertencia
de editor desconocido en el instalador. Firmar/notarizar requiere certificados
de pago (Apple Developer ID, certificado Authenticode) y queda fuera del
alcance actual del pipeline.

---

## 4. CI/CD con CircleCI

El pipeline de CircleCI ejecuta los tests y, si pasan, compila el proyecto para todas las
plataformas automáticamente. El job `test` actúa como **puerta**: cada build depende de él
(`requires: [test]`).

### Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                         test                                 │
│              (pytest tests/ — puerta previa)                 │
└───────┬───────────────┬───────────────┬───────────────┬─────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│build-windows│ │build-linux- │ │build-linux- │ │ build-darwin-    │
│  + Inno     │ │    x64      │ │   arm64     │ │   universal2     │
│  Setup      │ │ + AppImage  │ │ + AppImage  │ │  + create-dmg    │
└─────────────┘ └─────────────┘ └─────────────┘ └──────────────────┘
```

### Jobs

| Job | Plataforma | Executor | Notas |
|-----|------------|----------|-------|
| `test` | — | docker `cimg/python:3.13` | `pytest tests/` (puerta previa) |
| `build-windows` | Windows x64 | `win/server-2022` | PyInstaller onedir + Inno Setup |
| `build-linux-x64` | Linux x64 | docker `cimg/python:3.13` | PyInstaller onedir + AppImage |
| `build-linux-arm64` | Linux ARM64 | machine `arm.medium` | PyInstaller onedir + AppImage |
| `build-darwin-universal2` | macOS universal2 | macos `m4pro.medium` (Xcode 26.4.0) | PyInstaller onedir + .app + .dmg |

El archivo de configuración completo está en `.circleci/config.yml`.

---

## 5. Distribución de artefactos

Los artefactos publicados por CI se almacenan en `dist/`:

```
dist/
├── tts-sidecar-0.1.0-x86_64-setup.exe   # Windows (instalador Inno Setup)
├── tts-sidecar/                          # Windows onedir (carpeta)
├── tts-sidecar-0.1.0-x86_64.AppImage    # Linux x64
├── tts-sidecar-0.1.0-aarch64.AppImage   # Linux ARM64
├── tts-sidecar-0.1.0-universal2.dmg     # macOS
└── tts-sidecar-universal2.app/           # macOS .app bundle (nombre estable: se arrastra a /Applications)
```

---

## 6. Paquetes excluidos (bloat)

Los siguientes paquetes no se usan en runtime y están excluidos del bundle:

| Paquete | Razón |
|---------|--------|
| `gradio` + `gradio_client` | UI web, fuera del path TTS |
| `tensorflow`, `jax`, `flax` | Shims de transformers no cargados en runtime |

---

## 7. Notas de dependencias

### `chatterbox-tts` metadata

`chatterbox/__init__.py` llama `importlib.metadata.version("chatterbox-tts")` al importar.
Sin `--recursive-copy-metadata chatterbox-tts`, el comando `doctor` reporta "NOT INSTALLED"
en el bundle congelado.

### Audio por plataforma

| Plataforma | Librería | Notas |
|------------|----------|-------|
| Windows | `pycaw` | Incluida (enumeración; reproduce `winsound`, built-in) |
| Linux | `sounddevice` | Incluida (reproducción y enumeración) |
| macOS | `afplay` (built-in) + `sounddevice` | `afplay` reproduce; `sounddevice` (incluida en el bundle) enumera dispositivos para `doctor`/`devices` |

### Paquetes recopilados con `--collect-all`

PyInstaller no sigue automáticamente imports lazy ni extensiones nativas en runtime.
Los paquetes que requieren `--collect-all` son: `chatterbox`, `transformers`,
`diffusers`, `torch`, `sklearn`, `pandas`, `s3tokenizer`, `perth`, `librosa`, `onnx`, `pycaw`.

---

## 8. Notas importantes

- **PyInstaller --onedir**: genera una carpeta con el ejecutable y todas las dependencias
  (~1.7 GB sin comprimir). Es el artefacto que el script de empaquetado consume.
- **Tiempo de build**: ~10 min en frío, ~5 min incremental.
- **Windows**: el instalador Inno Setup es el artefacto que recibe el usuario final;
  ajusta el `PATH`, muestra la página informativa del modelo y ofrece ejecutar `setup`.
- **Linux**: el AppImage es un único archivo ejecutable, compatible con la mayoría de
  distribuciones; `tts-sidecar setup` lo integra en el PATH (symlink en `~/.local/bin`).
- **macOS**: el `.dmg` es el instalador estándar de macOS; incluye el `.app` bundle más
  los scripts de instalación (PATH + oferta de `setup`) y desinstalación.
- **Firma de código**: ver la limitación conocida en la sección 3 (artefactos sin
  firmar/notarizar: Gatekeeper y SmartScreen advierten en el primer arranque).
