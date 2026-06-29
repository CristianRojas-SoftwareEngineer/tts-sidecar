# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

`tts-sidecar` es un motor de síntesis de voz (TTS) offline en Python usando Chatterbox para clonación de voz en español latinoamericano.

**Rama actual**: `main`

## Comandos comunes

```bash
# Ejecutar CLI (desarrollo)
python bin/tts-sidecar <comando>

# Compilar binario Windows con Nuitka
npm run build-windows

# Ejecutar tests
pytest tests/ -v

# Verificar sintaxis Python
python -m py_compile src/chatterbox_tts/engine.py
python -m py_compile src/chatterbox_tts/cli.py
```

## Arquitectura

### Stack de implementación

```
bin/tts-sidecar              # Entry point (suprime warnings, delegar a cli.main)
src/chatterbox_tts/
├── cli.py                   # CLI con argparse (14 comandos)
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
- **PerthNet**: Watermarker (bypaseado en daemon para velocidad)

### Parámetros de síntesis optimizados (daemon)

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `n_cfm_timesteps` | 4 | Flow matching steps (default: 10) |
| `max_new_tokens` | 500 | T3 output cap (default: 1000) |
| `exaggeration` | 0.75 | Emotional expressiveness (default: 0.5) |

### Flujo de síntesis

```
CLI → cmd_speak/cmd_synthesize
              ↓ (daemon o directo)
       ChatterboxEngine.speak()
              ↓
       T3 autoregresivo [Stage 2a] (~10-15s)
              ↓
       S3Gen vocoder [Stage 2b] (~5-8s)
              ↓ (bypass watermark)
       _audio_to_wav() → WAV PCM 24kHz mono
              ↓
       AudioPlayer.play() / archivo
```

## Diseño de voz dual-audio

Cada voz registrada contiene dos archivos:

| Archivo | Propósito | Largo |
|---------|-----------|-------|
| `reference.wav` | Voice Encoder (timbre) — audio completo promediado | Cualquier largo |
| `speech.wav` | T3 conditioning + S3Gen decoder | 10s+ recomendado |

`voice-add` requiere ambos archivos:
```bash
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav
```

## Comandos CLI

```bash
# Daemon mode
tts-sidecar daemon start              # Iniciar daemon
tts-sidecar daemon stop                 # Detener daemon
tts-sidecar daemon restart              # Reiniciar
tts-sidecar daemon status               # Ver estado

# Síntesis
tts-sidecar speak --text "Hola"        # Reproducir audio
tts-sidecar speak --text "Hola" --daemon
tts-sidecar speak --text "Hola" --no-daemon
tts-sidecar synthesize --text "Hola" --output audio.wav

# Clonación de voz
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav
tts-sidecar voices
tts-sidecar speak --text "Hola" --voice mi_voz
tts-sidecar voice-remove --name mi_voz

# Diagnóstico
tts-sidecar doctor
tts-sidecar devices
tts-sidecar version
```

## Estructura de directorios

```
voices/                  # Voces registradas del usuario
mi_voz/
├── reference.wav        # Audio para timbre (cualquier largo)
└── speech.wav          # Audio para conditioning (10s+)

assets/                  # Audios de prueba
└── Voice Sampler.wav

src/chatterbox_tts/      # Código fuente Python
├── daemon/              # Daemon mode
├── tests/               # Tests pytest (31 tests)
│   ├── conftest.py
│   ├── test_timing.py
│   ├── test_protocol.py
│   ├── test_daemon.py
│   └── test_cli.py
```

## Warnings silenciados

`bin/tts-sidecar` silencie:
- `pkg_resources deprecation`
- `diffusers LoRACompatibleLinear`
- `huggingface_hub` HTTP warnings
- `chatterbox.models.tokenizers.tokenizer` pkuseg
- `chatterbox.models.t3.inference.alignment_stream_analyzer` repetition

## Documentación relevante

- `USAGE.md` - Guía de uso detallada
- `docs/design.md` - Diseño del motor
- `docs/goal.md` - Meta del proyecto
- `docs/migration-plan.md` - Historia del daemon mode (completado)
- `BUILD.md` - Guía de compilación Nuitka
- `scripts/build_windows.py` - Build Nuitka para Windows
