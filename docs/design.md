# Diseño del Sistema TTS Sidecar con Chatterbox Multilingual V3

## Resumen ejecutivo

`tts-sidecar` es un motor de síntesis de voz (TTS) **100% local** que usa **Chatterbox Multilingual V3** para clonación de voz en español latinoamericano. El usuario puede clonar su propia voz a partir de ~10 segundos de audio y generar narración de alta calidad.

- **Licencia**: MIT (código y modelo)
- **Idiomas**: 23+ incluyendo Español (es)
- **Clonación**: Audio prompt path (~10 segundos)
- **Parámetros del modelo**: 500M
- **Hardware**: CPU, CUDA, MPS (Apple Silicon)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│              tts-sidecar (CLI binary)                       │
│   Single-file executable per OS (Windows, Linux, macOS)    │
│   Built with Nuitka: embedded Python interpreter            │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                         │
│   Model: ResembleAI/chatterbox-multilingual               │
│   License: MIT                                            │
│   Languages: 23+ (Spanish, English, French, etc.)          │
│   Inference: CPU / CUDA / MPS                             │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Audio Playback (Native APIs)                       │
│   Windows: pycaw (WASAPI) / winsound fallback             │
│   Linux: sounddevice (PortAudio) / pyalsaaudio            │
│   macOS: afplay (built-in) / AVFoundation                │
└─────────────────────────────────────────────────────────────┘
```

## Estructura del proyecto

```
tts-sidecar/
├── src/
│   └── chatterbox_tts/           # Python package
│       ├── __init__.py            # Lazy imports
│       ├── engine.py              # ChatterboxTTS wrapper
│       ├── audio.py               # Cross-platform audio playback
│       ├── timing.py              # Instrumentation and timing
│       ├── cli.py                 # CLI interface (14 commands)
│       └── daemon/                # Daemon mode (FastAPI + IPC)
│           ├── daemon.py          # Lifecycle manager
│           ├── server.py          # FastAPI endpoints
│           ├── ipc.py             # HTTP client for daemon
│           ├── protocol.py        # Pydantic models
│           └── run.py             # Entry point
├── bin/
│   └── tts-sidecar               # Entry point script
├── scripts/
│   ├── build_windows.py          # Nuitka build for Windows
│   ├── build_linux.py            # Nuitka build for Linux
│   ├── build_macos.py            # Nuitka build for macOS
│   └── install.py                 # Model download + setup
├── models/                       # Chatterbox model cache
│   └── chatterbox-multilingual/
├── voices/                       # User voice clones
│   └── mi_voz/
│       ├── reference.wav         # Voice timbre (any length)
│       └── speech.wav            # Conditioning (10s+)
├── config/
│   └── config.toml               # Configuration file
├── assets/                       # Audio samples
│   ├── Voice Sampler.wav
│   └── Speech Sampler.wav
├── tests/                        # Pytest test suite
├── requirements.txt               # Python dependencies
├── pyproject.toml                # Python project config
└── docs/
    ├── design.md                 # Este documento
    ├── goal.md                   # Meta del proyecto
    └── daemon-mode.md            # Daemon mode
```

## Motor Chatterbox Multilingual V3

| Aspecto | Detalle |
|---------|---------|
| **Modelo** | `ResembleAI/chatterbox-multilingual` |
| **Licencia** | MIT |
| **Parámetros** | 500M |
| **Idiomas** | 23+ (es, en, fr, de, pt, etc.) |
| **Clonación de voz** | Audio prompt path (~10s de audio) |
| **Inference** | CPU, CUDA, MPS |

## Flujo de síntesis

```
1. User runs: tts-sidecar speak --text "Hola" -v mi_voz
                    │
                    ▼
2. CLI parses args, loads ChatterboxEngine
                    │
                    ▼
3. ChatterboxTTS.generate(text, language=es, audio_prompt_path=voices/mi_voz/reference.wav)
                    │
                    ▼
4. Model outputs WAV audio (24kHz, mono)
                    │
                    ▼
5. AudioPlayer.play() → Native OS audio API
                    │
                    ▼
6. User hears speech in Spanish with voice clone
```

## Comandos CLI

```bash
# Instalación (primera vez)
tts-sidecar install

# Síntesis básica
tts-sidecar speak --text "Hola mundo"

# Síntesis con voz clonada
tts-sidecar speak --text "Hola" -v mi_voz

# Exportar a archivo
tts-sidecar synthesize --text "Hola" --output audio.wav -v mi_voz

# Clonación de voz (requiere dos archivos de audio)
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav

# Listar voces
tts-sidecar voices

# Diagnóstico
tts-sidecar doctor
tts-sidecar devices
```

## Invocación desde otros lenguajes

```bash
# Bash
./tts-sidecar speak --text "Hola"

# Python
subprocess.run(["./tts-sidecar", "speak", "--text", "Hola"])

# Node.js
child_process.spawn("./tts-sidecar", ["speak", "--text", "Hola"])

# Rust
std::process::Command::new("./tts-sidecar").args(["speak", "--text", "Hola"]).output()
```

## Por qué Python + Nuitka

| Criterio | Rust actual | Python + Nuitka |
|----------|-------------|-----------------|
| Motor TTS | ONNX (ort) | Chatterbox directo |
| Licencia | MIT | MIT |
| Single-file installer | No (Rust no bundlea Python) | ✅ Sí (Nuitka bundles interpreter) |
| Dependencias usuario | Rust toolchain | Ninguna |
| Tamaño estimado | ~100MB binario | ~500MB-1GB (con modelo) |

## Compilación Nuitka

```bash
# Windows
python scripts/build_windows.py

# Linux
python scripts/build_linux.py --arch x86_64
python scripts/build_linux.py --arch arm64

# macOS
python scripts/build_macos.py --arch universal2
```

## Extensibilidad

Para añadir un nuevo motor TTS:

1. Crear nuevo módulo en `src/chatterbox_tts/`
2. Mantener la misma interfaz CLI en `cli.py`
3. Re-compilar con Nuitka para cada plataforma

---

## Referencias

- [Chatterbox TTS - Resemble AI](https://huggingface.co/ResembleAI/chatterbox-multilingual)
- [Nuitka - Python to Executable](https://nuitka.net/)
- [Chatterbox GitHub](https://github.com/resemble-ai/chatterbox)
