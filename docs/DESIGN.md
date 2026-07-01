# Diseño del Sistema TTS Sidecar con Chatterbox Multilingual V3

## Resumen ejecutivo

`tts-sidecar` es un motor de síntesis de voz (TTS) **100% local** que usa **Chatterbox Multilingual V3** para clonación de voz en español latinoamericano. El usuario puede clonar su propia voz a partir de ~10 segundos de audio y generar narración de alta calidad.

- **Licencia**: GPL-3.0-or-later (código del proyecto); el modelo y las dependencias conservan sus licencias permisivas (MIT/BSD/Apache)
- **Idiomas**: 23+ incluyendo Español (es)
- **Clonación**: diseño dual-audio (`reference.wav` + `speech.wav`, ~10 segundos)
- **Parámetros del modelo**: 500M
- **Hardware**: CPU, CUDA, MPS (Apple Silicon)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│              tts-sidecar (binario CLI)                     │
│   Instalador por SO (Windows, Linux, macOS)                │
│   Bundle PyInstaller --onedir con intérprete embebido      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                         │
│   Modelo: es-mx-latam (caché de HuggingFace)              │
│   Licencia: MIT                                           │
│   Idiomas: 23+ (español, inglés, francés, etc.)            │
│   Inferencia: CPU / CUDA / MPS                            │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│           Reproducción de audio (APIs nativas)              │
│   Windows: pycaw (WASAPI) / winsound (fallback)          │
│   Linux: sounddevice (PortAudio) / pyalsaaudio          │
│   macOS: afplay (nativo) / AVFoundation                 │
└─────────────────────────────────────────────────────────────┘
```

## Estructura del proyecto

```
tts-sidecar/
├── src/
│   └── chatterbox_tts/           # Paquete Python
│       ├── __init__.py            # Imports perezosos (lazy)
│       ├── engine.py              # Wrapper de ChatterboxTTS
│       ├── audio.py               # Reproducción de audio multiplataforma
│       ├── timing.py              # Instrumentación y timing
│       ├── cli.py                 # Interfaz CLI
│       └── daemon/                # Daemon mode (FastAPI + IPC)
│           ├── daemon.py          # Gestor del ciclo de vida
│           ├── server.py          # Endpoints FastAPI
│           ├── ipc.py             # Cliente HTTP del daemon
│           ├── protocol.py        # Modelos Pydantic
│           └── run.py             # Entry point
├── bin/
│   └── tts-sidecar               # Script de entry point
├── scripts/
│   ├── build_windows.py          # Build PyInstaller para Windows
│   ├── build_linux.py            # Build PyInstaller para Linux
│   ├── build_macos.py            # Build PyInstaller para macOS
│   └── install.py                 # Descarga del modelo + setup
├── voices/                       # Voces de FÁBRICA (commiteadas, empaquetadas, solo lectura)
│   └── default/                  # Voz por defecto (derivada de assets/)
│       ├── reference.wav         # Timbre de voz (cualquier largo)
│       └── speech.wav            # Conditioning (10s+)
│   # Las voces de USUARIO viven en el user-data-dir por SO, no en el repo
├── assets/                       # Audios de prueba
│   ├── Voice Sampler.wav
│   └── Speech Sampler.wav
├── tests/                        # Pytest test suite
├── requirements.txt               # Python dependencies
├── pyproject.toml                # Python project config
└── docs/
    ├── DESIGN.md                 # Este documento
    ├── GOAL.md                   # Meta del proyecto
    └── DAEMON-MODE.md            # Daemon mode
```

> El modelo `es-mx-latam` no vive en el repo ni en el bundle: reside en la caché
> de HuggingFace del usuario (`~/.cache/huggingface/hub`) tras `tts-sidecar setup`.

## Motor Chatterbox Multilingual V3

| Aspecto | Detalle |
|---------|---------|
| **Modelo** | `es-mx-latam` (`ResembleAI/Chatterbox-Multilingual-es-mx-latam`) |
| **Licencia** | MIT |
| **Parámetros** | 500M |
| **Idiomas** | 23+ (es, en, fr, de, pt, etc.) |
| **Clonación de voz** | Diseño dual-audio (`reference.wav` + `speech.wav`, ~10s) |
| **Inferencia** | CPU, CUDA, MPS |

## Flujo de síntesis

```
1. El usuario ejecuta: tts-sidecar speak --text "Hola" -v mi_voz
                    │
                    ▼
2. La CLI parsea argumentos y carga ChatterboxEngine
                    │
                    ▼
3. ChatterboxTTS.generate(text, language=es,
       reference.wav → Voice Encoder (timbre),
       speech.wav    → T3 conditioning + S3Gen decoder)
                    │
                    ▼
4. El modelo produce audio WAV (24kHz, mono)
                    │
                    ▼
5. AudioPlayer.play() → API de audio nativa del SO
                    │
                    ▼
6. El usuario escucha el habla en español con la voz clonada
```

## Modelo de voces de dos niveles

Las voces se separan en dos orígenes y se resuelven por nombre con precedencia
**usuario→fábrica** (`voices.py`):

- **Fábrica**: `voices/` en la raíz del repo, versionadas y empaquetadas en el
  ejecutable vía `--add-data`; de solo lectura. Se resuelven en
  `paths.bundled_voices_dir()` (raíz del repo en modo fuente, `sys._MEIPASS`
  congelado). Incluye la voz `default`, derivada de `assets/`.
- **Usuario**: `data_root()/voices` (user-data-dir por SO congelado; escribible),
  registradas con `voice add`. Una voz de usuario homónima sobrescribe a la de
  fábrica.

Sin `--voice` ni audios explícitos, la CLI usa la voz `default`, de modo que
`tts-sidecar speak --text "Hola"` funciona sin registrar nada. El repositorio ya
no usa `src/voices/` como origen de voces.

## Comandos CLI

```bash
# Provisión (primera vez - chequeos + descarga el modelo si falta)
tts-sidecar setup

# Síntesis básica
tts-sidecar speak --text "Hola mundo"

# Síntesis con voz clonada
tts-sidecar speak --text "Hola" -v mi_voz

# Exportar a archivo (speak con --output guarda en vez de reproducir)
tts-sidecar speak --text "Hola" --output audio.wav -v mi_voz

# Clonación de voz (requiere dos archivos de audio)
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav

# Listar voces
tts-sidecar voice list

# Diagnóstico (--json para salida legible por máquina)
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

## Compilación PyInstaller

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
3. Re-empaquetar con PyInstaller para cada plataforma

---

## Referencias

- [Chatterbox TTS - Resemble AI](https://huggingface.co/ResembleAI/chatterbox-multilingual)
- [PyInstaller - Python to Executable](https://pyinstaller.org/)
- [Chatterbox GitHub](https://github.com/resemble-ai/chatterbox)
