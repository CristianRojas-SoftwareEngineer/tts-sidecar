# Arquitectura de TTS Sidecar

## Visión General

```
┌─────────────────────────────────────────────────────────────┐
│              tts-sidecar (Executable binary)                  │
│   Single-file executable per OS (Windows, Linux, macOS)      │
│   Built with Nuitka: embedded Python interpreter             │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                         │
│   Model: ResembleAI/chatterbox-multilingual               │
│   License: MIT                                            │
│   Languages: 23+ (Spanish, English, French, etc.)          │
│   Inference: CPU / CUDA / MPS                            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Audio Playback (Native APIs)                      │
│   Windows: pycaw (WASAPI) / winsound                     │
│   Linux: sounddevice (PortAudio) / pyalsaaudio          │
│   macOS: afplay (built-in) / AVFoundation               │
└─────────────────────────────────────────────────────────────┘
```

## Principios de Diseño

### Python + Nuitka

- **Python**: Motor TTS con Chatterbox
- **Nuitka**: Compila Python a ejecutable nativo con interpreter embebido
- **Resultado**: Un solo archivo binario por SO, sin dependencias externas

### El entry point `bin/tts-sidecar`

El archivo `bin/tts-sidecar` es el **punto de entrada único** de la aplicación. Está escrito en **Python 3**, pero deliberadamente **no lleva extensión `.py`**:

- **Convención de comando CLI**: el objetivo del proyecto es exponer una herramienta invocable como `tts-sidecar speak ...`, no como `tts-sidecar.py speak ...`. Los comandos de terminal no llevan extensión (igual que `git`, `node` o `pip`), de modo que el archivo se nombra como el comando final que representa.
- **Shebang en vez de extensión**: la primera línea es `#!/usr/bin/env python3`. En Linux/macOS, con el bit de ejecución activo (`chmod +x`), el sistema operativo lee esa línea para saber con qué intérprete ejecutarlo; la extensión `.py` solo orienta a editores y humanos, el SO nunca la necesita. Por eso `./tts-sidecar speak ...` funciona sin nombrar a Python.
- **Invocación en desarrollo bajo Windows**: Windows ignora el shebang, así que en desarrollo el entry point se invoca explícitamente a través del intérprete: `python bin/tts-sidecar speak --text "Hola"`.

El archivo no contiene lógica de negocio: prepara el entorno (silencia warnings, ajusta `sys.path`, parchea `pkg_resources` para Python 3.13+) y delega en `chatterbox_tts.cli.main`. Además es la **semilla de compilación** que reciben los scripts de `scripts/build_*.py`: Nuitka lo toma como entrada y produce el binario final (`tts-sidecar` en Linux/macOS, `tts-sidecar.exe` en Windows). Véase `docs/BUILD.md`.

### Estructura del Proyecto

```
tts-sidecar/
├── src/
│   └── chatterbox_tts/        # Python package
│       ├── __init__.py         # Lazy imports
│       ├── engine.py           # ChatterboxTTS wrapper
│       ├── audio.py           # Cross-platform audio playback
│       ├── timing.py           # Instrumentation y timing
│       ├── cli.py             # CLI interface (14 commands)
│       └── daemon/            # Daemon mode (FastAPI + IPC)
│           ├── daemon.py      # Lifecycle manager
│           ├── server.py      # FastAPI endpoints
│           ├── ipc.py         # HTTP client for daemon
│           ├── protocol.py    # Pydantic request/response models
│           └── run.py         # Entry point
├── bin/
│   └── tts-sidecar           # Entry point (Python, sin extensión; semilla de Nuitka)
├── scripts/
│   ├── build_windows.py      # Nuitka build for Windows
│   ├── build_linux.py       # Nuitka build for Linux
│   ├── build_macos.py       # Nuitka build for macOS
│   └── install.py            # Model download + setup
├── tests/                    # Pytest test suite
├── requirements.txt           # Python dependencies
├── pyproject.toml            # Python project config
└── docs/
    ├── DESIGN.md
    ├── GOAL.md
    └── DAEMON-MODE.md
```

## Modelos Disponibles

| Modelo | Descripción | Licencia |
|--------|-------------|----------|
| `multilingual` | Base model, 23+ idiomas | MIT |
| `es-latam` | Latin American Spanish (RECOMMENDED) | MIT |

## Flujo de Síntesis

```
speak --text "Hola" -v mi_voz
       │
       ▼
┌──────────────────┐
│ ChatterboxEngine │
│ speak()         │
│                 │
│ 1. Load model  │
│ 2. Generate    │
│ 3. Return WAV  │
└────────┬────────┘
         │ WAV bytes
         ▼
┌──────────────────┐
│ AudioPlayer      │
│ play()          │
│                 │
│ Native OS API   │
└─────────────────┘
```

## Clonación de Voz

Chatterbox permite clonar cualquier voz a partir de ~10 segundos de audio. Cada voz requiere dos archivos:

1. `voice-add --name mi_voz --reference timbre.wav --speech condicion.wav` registra la voz
2. Los archivos se guardan en `voices/mi_voz/reference.wav` y `voices/mi_voz/speech.wav`
   - `reference.wav` → Voice Encoder (timbre completo)
   - `speech.wav` → T3 conditioning + S3Gen decoder (patrón de habla)
3. `speak --text "..." -v mi_voz` usa ambos archivos automáticamente para la síntesis

## Extensibilidad

Para añadir un nuevo motor TTS:

1. Crear nuevo módulo en `src/chatterbox_tts/`
2. Mantener la misma interfaz en `cli.py`
3. Re-compilar con Nuitka para cada plataforma
