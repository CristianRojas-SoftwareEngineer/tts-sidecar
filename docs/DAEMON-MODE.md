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
                                │  - Puerto fijo 8765 (TCP)      │
                                └───────────────────────────────────┘
```

## Arquitectura

### Estructura de Archivos

```
src/tts_sidecar/
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
    └── run.py          # Entry point: python -m tts_sidecar.daemon.run
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

El protocolo no lleva `model` ni `compute_backend`: el daemon sirve un único modelo
fijado al arrancar, con el backend de cómputo resuelto una sola vez (auto-detect o override vía variable de entorno). `text` está acotado a 5000 caracteres y las rutas de audio
deben existir y ser `.wav` (validación previa a la síntesis).

**Response** (Daemon → CLI):

La respuesta es un **stream NDJSON** (`Content-Type: application/x-ndjson`): una
línea JSON por evento. El daemon emite N líneas `progress` con el avance real de
la síntesis (etapa actual y conteo de tokens del T3 en vivo) y cierra con una
línea `result` que lleva el WAV completo codificado en base64 y los tiempos por
sub-etapa. Si la síntesis falla en el hilo worker, se emite una línea `error` en
lugar de `result` (el cliente la convierte en un fallo con código de salida 5).

```
HTTP/1.1 200 OK
Content-Type: application/x-ndjson

{"event":"progress","stage":"conditionals","tokens":null,"elapsed":null}
{"event":"progress","stage":"t3","tokens":10,"elapsed":null}
{"event":"progress","stage":"t3","tokens":210,"elapsed":null}
{"event":"progress","stage":"s3gen","tokens":null,"elapsed":null}
{"event":"result","audio_b64":"<WAV en base64>","t3_time":9.7,"s3gen_time":7.0}
```

El orden garantizado es N×`progress` → 1×`result`, o bien 1×`error`. El esquema de
cada línea lo define `daemon/protocol.py` (`ProgressEvent` / `ResultEvent` /
`ErrorEvent`), fuente única consumida por `server.py` (productor) e `ipc.py`
(consumidor). El cliente reenvía cada `progress` al spinner de `speak` para
mostrar progreso real (p. ej. «Generando voz · 210 tokens»); ver más abajo.

> **Errores de validación**: los rechazos de ruta de audio inválida (sandbox de
> directorios permitidos) o de modelo no cargado siguen siendo respuestas HTTP de
> error inmediatas (`400`/`503` con cuerpo JSON `{"detail": ...}`), **no** frames
> del stream: se validan antes de arrancar la síntesis.

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

> **Código de salida para integradores**: `speak --daemon` termina con código
> **5** (daemon inalcanzable) si el daemon no responde, en lugar del código de
> error genérico. Los comandos `daemon start/stop/restart` también devuelven `5`
> cuando la operación de ciclo de vida falla. Ver la tabla completa de códigos en
> `USAGE.md` (sección «Experiencia unificada entre sistemas operativos»).

> **Ventana de arranque (30-90 s)**: el puerto 8765 no abre hasta que el modelo
> termina de cargarse en memoria, lo que puede tardar entre 30 y 90 segundos
> según el hardware. `daemon start` bloquea internamente hasta confirmar
> «Daemon listo» (o el timeout de 120 s) antes de devolver el control, así que
> un script que lo invoca y espera esa confirmación no necesita hacer nada
> especial. Durante esa ventana, `daemon stop` **detecta el arranque en curso**
> (escaneo de procesos por cmdline, sin PID file): avisa por stderr que «el
> daemon está arrancando y aún no acepta conexiones», **no mata el proceso** y
> termina con exit **5**, para que un orquestador distinga «arrancando» de
> «detenido» sin parsear texto — reintenta `daemon stop` cuando la carga
> termine. `daemon status`, en cambio, sigue reportando «no está corriendo»
> durante la ventana (su fuente es el health check): un orquestador que lance
> `daemon start` en background debe esperar su confirmación (o sondear
> `/health`) antes de asumir que el daemon está listo.

> **Indicador de progreso durante `speak`**: aunque la síntesis ocurre en el
> proceso del daemon, su progreso **real** viaja al cliente por el stream NDJSON
> de `/synthesize` (etapa actual + conteo de tokens del T3 en vivo). `speak`
> alimenta con esos eventos un **spinner** sobre **stderr** que muestra la etapa
> y el avance (p. ej. «Generando voz · 210 tokens», subiendo) — tanto en modo
> daemon (eventos del stream) como en modo directo (mismo `progress_callback` del
> motor, sin HTTP). Es un indicador de etapa y avance de tokens, **no un
> porcentaje** del total. Solo aparece en terminales interactivas (TTY): si la
> salida está redirigida a un archivo o pipe, o corre en CI, el spinner se
> desactiva por completo y stdout queda intacto (contrato del CLI: stdout =
> datos, stderr = progreso).

> **Timeout de síntesis del cliente**: el cliente IPC espera la respuesta de
> `/synthesize` hasta **300 s** por defecto (audio largo en CPU lenta). Un
> consumidor programático que prefiera fallar antes puede reducirlo con la
> variable de entorno **`TTS_SIDECAR_REQUEST_TIMEOUT`** (segundos, admite
> decimales; un valor inválido o no positivo se ignora y se conserva el
> default). Al expirar, `speak --daemon` falla con el error IPC estándar; no
> hay reintento automático.

## Seguridad: directorios de audio permitidos

El endpoint `/synthesize` **no acepta rutas de audio arbitrarias del sistema
de archivos**: `voice_audio`/`speech_audio` deben resolver (tras seguir
symlinks) dentro de un directorio permitido —un directorio de voces conocido
(fábrica o usuario) o el subdirectorio de sesión del daemon bajo el tempdir del
SO (`<tempdir>/tts-sidecar/`), donde los clientes IPC preparan audio de sesión;
ver `voices.allowed_audio_dirs()` en `src/tts_sidecar/voices.py`. El tempdir
compartido general (`%TEMP%`/`/tmp`) **no** es un directorio permitido: acotarlo
al subdirectorio namespaced evita que cualquier proceso local plante un `.wav`
en el temp compartido para que el daemon lo lea. Cualquier otra ruta se rechaza
con `400`.

Esta restricción evita que un proceso local cualquiera use el daemon como
lector arbitrario de `.wav` del sistema (el daemon escucha en loopback sin
autenticación; ver `SECURITY.md`). **No se relaja bajo ninguna circunstancia.**
El CLI (`speak --voice-audio`/`--speech-audio`) anticipa esta restricción del
lado cliente antes de despachar al daemon: sin `--daemon` explícito degrada a
modo directo con un aviso; con `--daemon` explícito falla con un mensaje
accionable (ver USAGE.md, sección de `speak`).

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
| **Puerto** | Fijo 8765 en loopback (sin flag `--port`) | Puerto configurable |
| **Fallback** | Automático a modo directo | Error si daemon no disponible |
| **Lifecycle** | start/stop/restart/status | Solo auto-start |
| **Resiliencia** | Retry + auto-restart flag | Ninguna |
| **torch.compile** | Compartido via proceso daemon | Memory-mapped files |

## Compatibilidad

- El **contrato del CLI** (comandos, flags, códigos de salida, stdout = datos /
  stderr = progreso) no cambia: `speak`, `--daemon`, `--no-daemon` y el resto se
  comportan igual desde el punto de vista del integrador.
- El **protocolo interno daemon→cliente** de `/synthesize` sí cambió: pasó de un
  cuerpo binario WAV a un stream NDJSON (progreso + `result` con audio base64).
  Daemon y cliente viajan siempre en la misma versión (no hay usuarios externos
  desplegados), así que no se conserva la variante binaria ni se negocia
  capacidad; si actualizas el binario, actualiza ambos lados a la vez.
- Si el daemon no está corriendo, el CLI degrada a modo directo exactamente como
  antes; `--no-daemon` fuerza ese modo directo.
