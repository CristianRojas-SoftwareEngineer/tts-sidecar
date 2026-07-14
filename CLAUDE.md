# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

<!-- <project_overview> -->
## Proyecto

TTS Sidecar es un motor de síntesis de voz (TTS) offline en Python usando Chatterbox para clonación de voz en español latinoamericano.

**Rama actual**: `main`
<!-- </project_overview> -->

<!-- <common_commands> -->
## Comandos comunes

```bash
# Ejecutar CLI (desarrollo)
python bin/tts-sidecar <comando>

# Construir el paquete PyPI (sdist + wheel; ver docs/DISTRIBUTION.md)
uv build

# Instalar el paquete publicado desde PyPI (canal alternativo al binario nativo)
uv tool install tts-sidecar

# Compilar binario Windows con PyInstaller
npm run build-windows

# Compilar solo el onedir de Windows, sin generar el instalador Inno Setup
# (el CI usa este flag y genera el instalador como step separado). En Windows,
# PyInstaller se lanza vía scripts/pyinstaller_wrapper.py para evitar el cuelgue
# COM del análisis de pycaw/comtypes.
python scripts/build_windows.py --arch x86_64 --no-installer

# Regenerar el lockfile de dependencias (universal, con hashes) tras editar pyproject.toml
uv pip compile --universal --generate-hashes --python-version 3.13 pyproject.toml -o requirements-lock.txt

# Regenerar el lock CPU-only de Linux (torch/torchaudio +cpu, sin nvidia-*; usado por build-linux-x64, test-linux y coverage)
uv pip compile --generate-hashes --python-version 3.13 \
    --python-platform x86_64-unknown-linux-gnu \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    pyproject.toml -o requirements-lock-linux-cpu.txt

# Ejecutar tests
pytest tests/ -v

# Medir cobertura (opt-in: requiere pip install pytest-cov) y aplicar el gate por
# módulo de contrato (scripts/check_coverage.py::MODULE_FLOORS, fuente única de los pisos)
pytest tests/ --cov --cov-report=json --cov-report=term-missing
python scripts/check_coverage.py coverage.json

# Verificar sintaxis Python
python -m py_compile src/tts_sidecar/engine.py
python -m py_compile src/tts_sidecar/cli.py
```
<!-- </common_commands> -->

<!-- <architecture> -->
## Arquitectura

### Stack de implementación

```
bin/tts-sidecar              # Entry point de modo fuente: ajusta sys.path, delega a cli.main
src/tts_sidecar/
├── __main__.py              # Entry point de `python -m tts_sidecar`
├── bootstrap.py             # apply() idempotente: warnings, env vars, logging, mock pkg_resources
├── cli.py                   # CLI con argparse (speak, voice, daemon, devices, doctor, setup, version); llama bootstrap.apply()
├── engine.py                # Façade / composition root de síntesis (delega en los colaboradores de abajo)
├── compute_backend.py       # ComputeBackendResolver: detección/resolución de backend (cuda/mps/cpu) + cache key
├── audio_writer.py          # AudioWriter: audio → bytes WAV PCM 16-bit mono (en memoria o a disco)
├── synthesis.py             # SynthesisOrchestrator: flujo speak (conditionals → generate → encode → save)
├── model_loader.py          # ModelLoader: carga del checkpoint según caché (inyectable)
├── conditionals.py          # ConditionalsPreparer: cómputo/carga de conditionals (inyectable)
├── audio.py                 # Playback multiplataforma
├── timing.py                # StageTimer, log(), timed_command
├── model_cache.py           # Detección del modelo en la caché de HF (sin torch/chatterbox); usado por engine.py/cli.py
├── daemon/                  # Daemon mode (FastAPI + IPC)
│   ├── server.py            # /synthesize, /health, /voices endpoints
│   ├── daemon.py            # Lifecycle manager
│   ├── ipc.py               # HTTP client para daemon
│   ├── protocol.py           # Pydantic request/response models
│   └── run.py               # Entry point: python -m ...daemon.run (usa bootstrap.apply())
```

El entry point `tts-sidecar` instalado vía pip/`uv tool install` (`[project.scripts]`
en `pyproject.toml`) invoca directamente `tts_sidecar.cli:main`; `bootstrap.apply()`
corre dentro de `cli.py`, así que el bootstrap es idéntico en las tres vías de
invocación (pip, `bin/tts-sidecar`, `python -m tts_sidecar`).

### Motor TTS

Chatterbox (`chatterbox-tts` package) con arquitectura `ChatterboxMultilingualTTS`:
- **T3**: Modelo autoregresivo texto → tokens (2454-token vocab)
- **S3Gen**: Flow matching vocoder (24kHz)
- **Voice Encoder**: Embedding de timbre desde audio de referencia
- **PerthNet**: Watermarker (bypaseado por el engine en ambos modos)

### Parámetros de síntesis optimizados (engine, ambos modos)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `n_cfm_timesteps` | 4 | Flow matching steps (default: 10) |
| `max_new_tokens` | 500 | T3 output cap (default: 1000) |
| `exaggeration` | 0.75 | Emotional expressiveness (default: 0.5) |

### Flujo de síntesis

```
CLI → cmd_speak
              ↓ (daemon o directo)
       ChatterboxEngine.speak()
              ↓
       T3 autoregresivo [Etapa 2a] (~10-15s)
              ↓
       S3Gen vocoder [Etapa 2b] (~5-8s)
              ↓ (bypass watermark)
       AudioWriter.write() → WAV PCM 24kHz mono
              ↓
       AudioPlayer.play() / archivo
```
<!-- </architecture> -->

<!-- <voice_design> -->
## Diseño de voz dual-audio

Cada voz registrada contiene dos archivos:

| Archivo | Propósito | Largo |
|---------|-----------|-------|
| `reference.wav` | Voice Encoder (timbre) — audio completo promediado | Cualquier largo |
| `speech.wav` | T3 conditioning + S3Gen decoder | 10s+ recomendado |

`voice add` requiere ambos archivos:
```bash
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav
```

### Modelo de voces de dos niveles

Las voces se resuelven con precedencia **usuario→fábrica** (`voices.py`):

- **Fábrica**: `src/tts_sidecar/voices/`, commiteadas y empaquetadas tanto en
  el wheel PyPI (`package-data`) como en el bundle PyInstaller (`--add-data`);
  de solo lectura. Se resuelven en `paths.bundled_voices_dir()`, siempre
  relativa al paquete (misma expresión en fuente, pip-installed y congelado,
  sin bifurcar por modo). Incluye la voz `default`, construida desde
  `assets/audios/`.
- **Usuario**: `data_root()/voices` — user-data-dir por SO, incondicional en
  los tres modos de ejecución. Escribibles vía `voice add`.

Sin `--voice`, `--voice-audio` ni `--speech-audio`, `cmd_speak` resuelve la voz
`default`, por lo que `tts-sidecar speak --text "Hola"` funciona sin audios.
<!-- </voice_design> -->

<!-- <model_provisioning> -->
## Modelo y provisión

El alias de modelo expuesto por el CLI es **`es-mx-latam`** (repo oficial
`ResembleAI/Chatterbox-Multilingual-es-mx-latam`); el modelo no se empaqueta en el
ejecutable y se descarga a `~/.cache/huggingface/hub` mediante `setup`. `setup`
corre los chequeos de `doctor` y descarga el modelo solo si falta (idempotente).
En Linux, ejecutado desde un AppImage (variable `APPIMAGE` presente), `setup`
además integra el PATH creando el symlink `~/.local/bin/tts-sidecar → $APPIMAGE`;
`setup --remove-path` lo revierte sin correr chequeos ni descargas.
`speak` y `daemon start` **fallan rápido** (vía `is_model_cached`) si el modelo no
está cacheado, remitiendo a `tts-sidecar setup` sin disparar descargas. En Windows
el instalador agrega `{app}` al PATH y ofrece una casilla que ejecuta `setup`; en
macOS el `.dmg` incluye scripts de instalación (symlink per-user en `~/.local/bin`,
sin `sudo`, + oferta de `setup`) y desinstalación, y existe además el one-liner
`install-macos.sh` (`curl | sh`) homólogo a `install-linux.sh`.
<!-- </model_provisioning> -->

<!-- <license> -->
## Licencia

El código de `tts-sidecar` se distribuye bajo **GPL-3.0-or-later** (ver `LICENSE`). El
modelo Chatterbox es MIT; las dependencias empaquetadas conservan sus propias licencias,
en su mayoría permisivas (MIT/BSD/Apache/ISC/PSF) y algunas de copyleft compatible con
GPLv3 (LGPL-2.1+, MPL-2.0, GPLv3+ de pykakasi); sus atribuciones están en
`THIRD-PARTY-LICENSES.md`. Al editar documentación, no confundir la licencia del **proyecto**
(GPLv3) con las menciones «MIT» que describen el **modelo** o las dependencias.
<!-- </license> -->

<!-- <cli_commands> -->
## Comandos CLI

```bash
# Provisión del modelo (chequeos + descarga si falta; idempotente).
# En Linux (AppImage) también crea el symlink de PATH en ~/.local/bin.
tts-sidecar setup
tts-sidecar setup --remove-path   # revierte el symlink de PATH (Linux)
# Desinstala en un comando en los 3 SO (canal nativo): encadena cleanup --all,
# revierte el PATH y borra el binario, en ese orden (datos→PATH→ancla). Dispatch
# por SO: Linux (symlink+dir), macOS (.app; con Homebrew difiere a brew --zap),
# Windows (datos en proceso + binario/PATH delegados al desinstalador de Inno).
tts-sidecar setup --uninstall
tts-sidecar setup --uninstall --yes   # omite la confirmación del cleanup encadenado

# Desaprovisionamiento (borrado quirúrgico: solo las carpetas del proyecto)
tts-sidecar cleanup --model       # elimina el modelo descargado
tts-sidecar cleanup --voices      # elimina las voces de usuario
tts-sidecar cleanup --all         # ambos
tts-sidecar cleanup --all --dry-run   # lista sin borrar

# Daemon mode
tts-sidecar daemon start              # Iniciar daemon
tts-sidecar daemon stop                 # Detener daemon
tts-sidecar daemon restart              # Reiniciar
tts-sidecar daemon status               # Ver estado

# Síntesis (speak reproduce; con --output guarda a archivo)
tts-sidecar speak --text "Hola"        # Reproducir audio
tts-sidecar speak --text "Hola" --daemon
tts-sidecar speak --text "Hola" --no-daemon
tts-sidecar speak --text "Hola" --output audio.wav

# Clonación de voz
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav
tts-sidecar voice list
tts-sidecar speak --text "Hola" --voice mi_voz
tts-sidecar voice remove --name mi_voz

# Diagnóstico (--json para salida legible por máquina)
tts-sidecar doctor [--json]
tts-sidecar devices [--json]
tts-sidecar version [--json]
```
<!-- </cli_commands> -->

<!-- <directory_structure> -->
## Estructura de directorios

```
assets/                  # Material fuente (audios de la voz default, logo)
├── audios/              # Audios fuente (voz default) y de prueba
│   ├── Voice Sampler.wav
│   └── Speech Sampler.wav
└── images/              # Logo del proyecto (fuente única de los iconos de build)
    └── TTS Sidecar - Logo.png

src/tts_sidecar/         # Código fuente Python
├── voices/              # Voces de FÁBRICA (commiteadas, empaquetadas en wheel y bundle, solo lectura)
│   └── default/         # Voz por defecto (derivada de assets/audios/)
│       ├── reference.wav    # Audio para timbre (cualquier largo)
│       └── speech.wav       # Audio para conditioning (10s+)
└── daemon/              # Daemon mode
# Las voces de USUARIO viven en el user-data-dir por SO (no en el repo)

tests/                   # Tests pytest (~559 tests) + smoke-tests de instaladores
├── conftest.py
├── installer/           # Smoke-tests de los instaladores de una línea (corren en CI, no en pytest)
│   ├── install-linux.bats     # install-linux.sh (bats, job test-installer-linux)
│   ├── install-macos.bats # install-macos.sh (bats, job test-installer-macos, executor macOS)
│   └── install-windows.tests.ps1 # install-windows.ps1 (Pester v5, job test-installer-windows)
├── test_audio.py
├── test_build_linux.py
├── test_build_macos.py
├── test_build_utils.py
├── test_build_windows.py
├── test_cask.py
├── test_check_coverage.py
├── test_ci_smoke.py
├── test_cli.py
├── test_create_installer_windows.py
├── test_daemon.py
├── test_engine_cache.py
├── test_engine_progress.py
├── test_paths.py
├── test_pin_consistency.py
├── test_protocol.py
├── test_third_party_licenses.py
├── test_timing.py
└── test_voices.py
```
<!-- </directory_structure> -->

<!-- <silenced_warnings> -->
## Warnings silenciados

`src/tts_sidecar/bootstrap.py` (`apply()`) silencia mediante una **allow-list explícita**
(`_SILENCED_WARNINGS`), **no** un catch-all global `warnings.filterwarnings("ignore")`
ni `PYTHONWARNINGS=ignore` (para no enmascarar deprecaciones propias
ni de terceros). La allow-list acota solo dos warnings benignos del módulo `warnings`:

- `pkg_resources is deprecated` — por **mensaje**; lo emite `perth` al importar
  `pkg_resources` en Python 3.13. Con `category=Warning` (no `DeprecationWarning`)
  porque `perth` lo emite como `UserWarning` en este entorno; así queda acotado por
  mensaje y cubre ambas categorías.
- `diffusers LoRACompatibleLinear` — por **módulo** (`r"^diffusers\."`), al importar
  `chatterbox`, para no atarse al texto exacto del mensaje.

Las tres supresiones siguientes son de `logging` (no las gobierna el catch-all) y se
conservan intactas:
- `huggingface_hub` HTTP warnings
- `chatterbox.models.tokenizers.tokenizer` pkuseg
- `chatterbox.models.t3.inference.alignment_stream_analyzer` repetition
<!-- </silenced_warnings> -->

<!-- <related_docs> -->
## Documentación relevante

- `USAGE.md` - Guía de uso detallada
- `docs/DESIGN.md` - Diseño del motor
- `docs/GOAL.md` - Meta del proyecto
- `docs/ROADMAP.md` - Estado actual y roadmap al goal inmediato
- `docs/DAEMON-MODE.md` - Daemon mode (servidor persistente)
- `docs/BUILD.md` - Guía de compilación PyInstaller
- `docs/DISTRIBUTION.md` - Canales de distribución (nativo + PyPI)
- `docs/PARITY.md` - Estado de paridad de experiencia entre los 3 SO y brechas pendientes
- `docs/RELEASING.md` - Publicación de una versión (release + PyPI)
- `docs/ARCHITECTURE.md` - Arquitectura del sistema
- `docs/CLAUDE-CODE-PLUGIN.md` - Puntero al plugin de narración `tts-sidecar-narrator` (repo propio)
- `docs/NARRATION-INTEGRATION.md` - Contrato de integración con el plugin de narración (superficies del CLI a mantener estables)
- `scripts/build_windows.py` - Build PyInstaller para Windows
- `scripts/pyinstaller_wrapper.py` - Wrapper COM que evita el cuelgue de PyInstaller en Windows (COINIT_MULTITHREADED + os._exit)
- `scripts/check_coverage.py` - Gate de cobertura por módulo (job `coverage` de CI; `MODULE_FLOORS` es la fuente única de los pisos)
<!-- </related_docs> -->
