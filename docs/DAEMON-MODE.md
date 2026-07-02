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
│                          Cliente CLI                                 │
│                            (cmd_speak)                               │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               │ ¿Daemon corriendo?
                               ▼
                    ┌──────────────────────┐
                    │  ¿Daemon corriendo?   │
                    └──────────┬───────────┘
                               │
              ┌────────────────┴────────────────┐
              │ NO                                 │ SÍ
              ▼                                    ▼
    ┌─────────────────┐                ┌─────────────────────────────┐
    │ Modo fallback   │                │  IPC (HTTP)                │
    │ (carga directa) │                │  127.0.0.1:8765           │
    └─────────────────┘                └──────────┬──────────────────┘
                                                  │
                                                  ▼
                                ┌───────────────────────────────────┐
                                │     tts-sidecar-daemon            │
                                │                                   │
                                │  - ChatterboxEngine (cacheado)    │
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
    ├── server.py       # Servidor FastAPI
    ├── daemon.py       # Gestor del ciclo de vida (start/stop/restart)
    ├── ipc.py          # Cliente HTTP para CLI → daemon
    ├── protocol.py     # Modelos Pydantic de request/response
    └── run.py          # Entry point: python -m chatterbox_tts.daemon.run
```

### Protocolo de Comunicación

**Request** (CLI → Daemon):
```json
POST /synthesize
{
  "text": "Hola mundo",
  "voice_audio": "/path/to/reference.wav",
  "speech_audio": "/path/to/speech.wav"
}
```

El protocolo no lleva `model` ni `device`: el daemon sirve un único modelo
fijado al arrancar. `text` está acotado a 5000 caracteres y las rutas de audio
deben existir y ser `.wav` (validación previa a la síntesis).

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

# Sin flags: speak sondea el daemon y lo usa si responde (directo si no)
tts-sidecar speak --text "Hola"

# Forzar daemon (sin sondeo previo; falla si el daemon no responde)
tts-sidecar speak --text "Hola" --daemon

# Forzar modo directo (sin sondear el daemon)
tts-sidecar speak --text "Hola" --no-daemon
```

## Parámetros Optimizados

Los parámetros optimizados son configuración propia del engine
(`ChatterboxEngine._apply_synthesis_optimizations`), no monkey-patches del
daemon: aplican por igual en modo directo y en el daemon, junto con el bypass
del watermark PerthNet y el timing por sub-etapa:

| Parámetro | Valor | Descripción |
|-----------|-------|-------------|
| `max_new_tokens` | 500 | Limita output del T3 (default: 1000) |
| `n_cfm_timesteps` | 4 | Pasos de flow matching (default: 10) |
| `exaggeration` | 0.75 | Expresividad emocional (default: 0.5) |

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

## Compatibilidad hacia atrás

- **100% compatible hacia atrás**
- Ningún comando existente cambia su comportamiento
- Si daemon no está corriendo, el CLI funciona exactamente igual que antes
- Flag `--no-daemon` permite forzar modo legacy
