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

# Compilar binario Windows con PyInstaller
npm run build-windows

# Regenerar el lockfile de dependencias (universal, con hashes) tras editar pyproject.toml
uv pip compile --universal --generate-hashes --python-version 3.13 pyproject.toml -o requirements-lock.txt

# Regenerar el lock CPU-only de Linux (torch/torchaudio +cpu, sin nvidia-*; usado solo por build-linux-x64)
uv pip compile --generate-hashes --python-version 3.13 \
    --python-platform x86_64-unknown-linux-gnu \
    --extra-index-url https://download.pytorch.org/whl/cpu \
    --index-strategy unsafe-best-match \
    pyproject.toml -o requirements-lock-linux-cpu.txt

# Ejecutar tests
pytest tests/ -v

# Verificar sintaxis Python
python -m py_compile src/tts_sidecar/engine.py
python -m py_compile src/tts_sidecar/cli.py
```
<!-- </common_commands> -->

<!-- <architecture> -->
## Arquitectura

### Stack de implementación

```
bin/tts-sidecar              # Entry point (suprime warnings, delegar a cli.main)
src/tts_sidecar/
├── cli.py                   # CLI con argparse (speak, voice, daemon, devices, doctor, setup, version)
├── engine.py                # Wrapper Chatterbox + síntesis
├── audio.py                 # Playback multiplataforma
├── timing.py                # StageTimer, log(), timed_command
├── daemon/                  # Daemon mode (FastAPI + IPC)
│   ├── server.py            # /synthesize, /health, /voices endpoints
│   ├── daemon.py            # Lifecycle manager
│   ├── ipc.py               # HTTP client para daemon
│   ├── protocol.py           # Pydantic request/response models
│   └── run.py               # Entry point: python -m ...daemon.run
```

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
       _audio_to_wav() → WAV PCM 24kHz mono
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

- **Fábrica**: `voices/` en la raíz del repo, commiteadas y empaquetadas vía
  `--add-data`; de solo lectura. Se resuelven en `paths.bundled_voices_dir()`
  (raíz del repo en modo fuente, `sys._MEIPASS` congelado). Incluye la voz
  `default`, construida desde `assets/audios/`.
- **Usuario**: `data_root()/voices` (user-data-dir por SO congelado; `src/voices`
  en modo fuente, hoy sin uso). Escribibles vía `voice add`.

Sin `--voice`, `--voice-audio` ni `--speech-audio`, `cmd_speak` resuelve la voz
`default`, por lo que `tts-sidecar speak --text "Hola"` funciona sin audios.
El directorio `src/voices/` fue **eliminado** tras el rediseño.
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
macOS el `.dmg` incluye scripts de instalación (symlink en `/usr/local/bin` +
oferta de `setup`) y desinstalación.
<!-- </model_provisioning> -->

<!-- <license> -->
## Licencia

El código de `tts-sidecar` se distribuye bajo **GPL-3.0-or-later** (ver `LICENSE`). El
modelo Chatterbox y todas las dependencias empaquetadas conservan sus licencias permisivas
(MIT/BSD/Apache/ISC/PSF), compatibles con GPLv3; sus atribuciones están en
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
voices/                  # Voces de FÁBRICA (commiteadas, empaquetadas, solo lectura)
└── default/             # Voz por defecto (derivada de assets/audios/)
    ├── reference.wav    # Audio para timbre (cualquier largo)
    └── speech.wav       # Audio para conditioning (10s+)
# Las voces de USUARIO viven en el user-data-dir por SO (no en el repo)

assets/                  # Material fuente (audios de la voz default, logo)
├── audios/              # Audios fuente (voz default) y de prueba
│   ├── Voice Sampler.wav
│   └── Speech Sampler.wav
└── images/              # Logo del proyecto (fuente única de los iconos de build)
    └── TTS Sidecar - Logo.png

src/tts_sidecar/      # Código fuente Python
└── daemon/              # Daemon mode

tests/                   # Tests pytest (233 tests)
├── conftest.py
├── test_audio.py
├── test_build_utils.py
├── test_cli.py
├── test_daemon.py
├── test_engine_cache.py
├── test_protocol.py
├── test_timing.py
└── test_voices.py
```
<!-- </directory_structure> -->

<!-- <silenced_warnings> -->
## Warnings silenciados

`bin/tts-sidecar` silencia:
- `pkg_resources deprecation`
- `diffusers LoRACompatibleLinear`
- `huggingface_hub` HTTP warnings
- `chatterbox.models.tokenizers.tokenizer` pkuseg
- `chatterbox.models.t3.inference.alignment_stream_analyzer` repetition
<!-- </silenced_warnings> -->

<!-- <related_docs> -->
## Documentación relevante

- `USAGE.md` - Guía de uso detallada
- `docs/DESIGN.md` - Diseño del motor
- `docs/GOAL.md` - Meta del proyecto
- `docs/DAEMON-MODE.md` - Daemon mode (servidor persistente)
- `docs/BUILD.md` - Guía de compilación PyInstaller
- `docs/ARCHITECTURE.md` - Arquitectura del sistema
- `scripts/build_windows.py` - Build PyInstaller para Windows
<!-- </related_docs> -->
