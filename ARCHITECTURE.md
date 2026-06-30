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
│   └── tts-sidecar           # Entry point
├── scripts/
│   ├── build_windows.py      # Nuitka build for Windows
│   ├── build_linux.py       # Nuitka build for Linux
│   ├── build_macos.py       # Nuitka build for macOS
│   └── install.py            # Model download + setup
├── tests/                    # Pytest test suite
├── requirements.txt           # Python dependencies
├── pyproject.toml            # Python project config
└── docs/
    ├── design.md
    ├── goal.md
    └── daemon-mode.md
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
