# Daemon Mode

El daemon mode mantiene el modelo de Chatterbox en memoria entre invocaciones del CLI, eliminando el overhead de carga (~15-30s) en cada llamada.

## Problema

Sin daemon, cada ejecución del CLI funciona así:

```
$ tts-sidecar speak --text "Hola"
→ Nuevo proceso Python
→ Importa engine.py
→ ChatterboxEngine.__init__() carga modelo (~5-8s)
→ Genera audio (~45s)
→ Proceso termina
→ Modelo en RAM se libera
```

**Problemas:**
1. El modelo se carga desde disco en cada invocación
2. `torch.compile` no persiste entre llamadas (overhead de ~30-60s)
3. El caché de clase en `ChatterboxEngine._cache` no se comparte entre procesos

## Solución

El daemon es un servidor HTTP persistente que mantiene el modelo cargado:

```
┌─────────────────────────────────────────────────────────────────────┐
│                           CLI Client                                 │
│                    (cmd_speak / cmd_synthesize)                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ ¿Daemon corriendo?
                               ▼
                    ┌──────────────────────┐
                    │   Daemon Running?     │
                    └──────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              │ NO                                 │ YES
              ▼                                    ▼
    ┌─────────────────┐                ┌─────────────────────────────┐
    │ Fallback Mode   │                │  IPC (HTTP)                │
    │ (direct load)   │                │  127.0.0.1:8765           │
    └─────────────────┘                └──────────┬──────────────────┘
                                                  │
                                                  ▼
                                ┌───────────────────────────────────┐
                                │     tts-sidecar-daemon            │
                                │                                   │
                                │  - ChatterboxEngine (cached)      │
                                │  - torch.compile (aplicado)      │
                                │  - Puerto 8765 (TCP)            │
                                └───────────────────────────────────┘
```

## Arquitectura

### Estructura de Archivos

```
src/chatterbox_tts/
├── cli.py              # CLI con fallback a daemon
├── engine.py           # ChatterboxEngine
├── audio.py            # AudioPlayer
├── timing.py           # Instrumentation
└── daemon/
    ├── __init__.py
    ├── server.py       # FastAPI server
    ├── daemon.py       # Lifecycle manager (start/stop/restart)
    ├── ipc.py          # Cliente HTTP para CLI → daemon
    ├── protocol.py     # Pydantic request/response models
    └── run.py          # Entry point: python -m chatterbox_tts.daemon.run
```

### Protocolo de Comunicación

**Request** (CLI → Daemon):
```json
POST /synthesize
{
  "text": "Hola mundo",
  "voice_audio": "/path/to/reference.wav",
  "speech_audio": "/path/to/speech.wav",
  "model": "es-latam",
  "device": "cpu",
  "compile_mode": "default"
}
```

**Response** (Daemon → CLI):
```
HTTP/1.1 200 OK
Content-Type: audio/wav
<binary WAV data>
```

## Comandos del Daemon

```bash
# Iniciar daemon (background)
tts-sidecar daemon start

# Iniciar daemon con auto-restart
tts-sidecar daemon start --autorestart --max-retries 3

# Detener daemon
tts-sidecar daemon stop

# Reiniciar daemon
tts-sidecar daemon restart

# Ver estado del daemon
tts-sidecar daemon status

# Ejecutar con daemon (comportamiento por defecto)
tts-sidecar speak --text "Hola" --daemon

# Forzar modo directo (ignorar daemon)
tts-sidecar speak --text "Hola" --no-daemon
```

## Parámetros Optimizados

El daemon aplica valores optimizados automáticamente:

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `max_new_tokens` | 500 | Limita output del T3 (default: 1000) |
| `n_cfm_timesteps` | 4 | Pasos de flow matching (default: 10) |
| `exaggeration` | 0.75 | Expressiveness emocional (default: 0.5) |

## Métricas de Rendimiento

| Métrica | Sin Daemon | Con Daemon |
|---------|------------|------------|
| Tiempo síntesis | ~50s | ~15-20s |
| Carga de modelo | 5-8s por llamada | 5-8s solo al iniciar |
| Overhead compilación | ~30s por llamada | ~1.6s solo al inicio |

## Decisiones de Diseño

| Aspecto | Decisión | Alternativa Considerada |
|---------|----------|------------------------|
| **IPC** | HTTP (FastAPI) | Named pipes, gRPC |
| **Fallback** | Automático a modo directo | Error si daemon no disponible |
| **Lifecycle** | start/stop/restart/status | Solo auto-start |
| **Resiliencia** | Retry + auto-restart flag | Ninguna |
| **torch.compile** | Compartido via proceso daemon | Memory-mapped files |

## Backwards Compatibility

- **100% backwards compatible**
- Ningún comando existente cambia su comportamiento
- Si daemon no está corriendo, el CLI funciona exactamente igual que antes
- Flag `--no-daemon` permite forzar modo legacy
