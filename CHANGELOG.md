# Changelog

Todos los cambios notables de TTS Sidecar se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

### Añadido

- **Progreso real en vivo durante `speak`**: el motor expone un `progress_callback`
  en `speak()` que emite eventos de etapa (conditionals → T3 → S3Gen → encoding →
  guardado) y el conteo de tokens del T3 en vivo (shim best-effort del `tqdm`
  interno de Chatterbox, con degradación a solo etapas si el layout cambia). El CLI
  alimenta con esos eventos un indicador de progreso sobre stderr que muestra la
  etapa y el avance (p. ej. «Generando voz · 210 tokens»), en modo directo y daemon.

### Cambiado

- **Protocolo de `/synthesize` (daemon→cliente)**: la respuesta pasó de un cuerpo
  binario WAV (con headers `X-T3-Time`/`X-S3Gen-Time`) a un **stream NDJSON**: N
  líneas `progress` (etapa + tokens) seguidas de una línea `result` con el WAV en
  base64 y los tiempos por sub-etapa, o una línea `error`. El servidor sintetiza en
  un hilo worker y drena los eventos por una cola; el cliente los consume con
  `iter_lines()`. Cambio interno del transporte (no del contrato del CLI): daemon y
  cliente viajan siempre en la misma versión. Modelos `ProgressEvent`/`ResultEvent`/
  `ErrorEvent` en `daemon/protocol.py` como fuente única del esquema.

## [0.1.0] — 2026-07-03

Primer release del gate de preparación para producción. Motor TTS offline con
clonación de voz en español latinoamericano (Chatterbox Multilingual, alias
`es-mx-latam`), CLI multiplataforma y modo daemon.

### Añadido

- Motor de síntesis offline con voz por defecto empaquetada y clonación de voz
  vía `voice add` (modelo dual-audio: `reference.wav` + `speech.wav`).
- CLI con los comandos `speak`, `voice`, `daemon`, `devices`, `doctor`, `setup`,
  `cleanup` y `version`.
- **`cleanup`**: desaprovisionamiento quirúrgico del modelo y las voces de usuario
  (`--model`, `--voices`, `--all`, `--dry-run`).
- **`cleanup --yes`** y captura de `EOFError` como cancelación limpia (N-03):
  permite invocación programática vía `subprocess` con stdin cerrado.
- **Modo daemon**: servidor HTTP persistente en loopback que mantiene el modelo en
  memoria entre invocaciones.
- **UX `--voice-audio`/`--speech-audio` vía daemon** (N-02): degradación
  automática a modo directo con aviso en stderr (sondeo automático) o error
  accionable con exit 4 (`--daemon` explícito); sandbox de rutas intacta.
- **Mapa de códigos de salida** del CLI como contrato público: `0` éxito, `1` error
  genérico, `2` modelo no provisionado, `3` voz/audio no encontrado, `4` entrada
  inválida, `5` daemon inalcanzable, `130` interrupción (SIGINT).
- **Lockfile universal con hashes** (`requirements-lock.txt`) para builds
  reproducibles e íntegros; CI instala con `--require-hashes`.
- **Lock CPU-only de Linux** (`requirements-lock-linux-cpu.txt`, N-05): instala
  `torch`/`torchaudio` `+cpu` desde el índice oficial de PyTorch sin el stack
  `nvidia-*-cu12` (~41 paquetes), reduciendo el AppImage x86_64 a cientos de MB.
- **Smoke test** del binario congelado en los 4 jobs de build de CI.
- **Triple puerta de tests** en CI (`test-linux`, `test-windows`, `test-macos`):
  la suite `pytest` corre en los tres SO nativos y bloquea los builds, con
  cobertura equivalente entre plataformas.
- **Instalador Windows restaurado** (N-01): `scripts/create_installer_windows.py`
  compila el `.exe` con Inno Setup; CI aborta si el artefacto falta; InfoAfter
  corrige la oferta GPLv3 §6d (código en el repo, no `LICENSE.txt`).
- **Runbook de release** `docs/RELEASING.md` y **SHA-256 en CI** (N-04): cada job
  de build emite el hash del artefacto para verificación cruzada en el Release.
- **Límite unificado de texto** en `speak` (N-11): `MAX_TEXT_LENGTH = 5000`
  validado en el cliente antes de cualquier despacho; exit 4 (`INVALID_INPUT`) en
  ambas rutas (directa y daemon).
- **Warning `--compute-backend` ignorado vía daemon** (N-10): aviso por stderr
  cuando el flag explícito no es `auto` y la síntesis va por daemon.
- **`_emit_audio` crea directorios padres** (N-12): simetría con
  `engine._save_wav` para `--output` en modo daemon.
- **Flag muerta `voice add --compute-backend` eliminada** (N-15): error ruidoso
  de argparse (flag desconocida) en lugar de ignoración silenciosa.
- **Provisión ligera en `setup` vía `snapshot_download`** (N-17): descarga el
  modelo sin instanciar `ChatterboxEngine` (pico de RAM ~2 GB evitado); la carga
  real queda para `doctor`/primer `speak`.
- Sección de **uso ético y responsable** en README y USAGE (consentimiento, no
  suplantación, divulgación del watermark desactivado, canal de reporte).
- Documentos de gobernanza: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.

### Cambiado

- **Puerto del daemon fijo en 8765** (loopback): se eliminó el flag `--port` por
  completo. **Breaking**: ya no es posible configurar el puerto ni correr dos
  daemons simultáneos.
- Diagnósticos e instrumentación de progreso redirigidos a **stderr**; stdout
  queda reservado para datos (salidas `--json`, rutas de resultado). Incluye
  mensajes de progreso de `DaemonManager` (N-09).
- `voice add` ya no instancia el motor de inferencia: valida y copia los audios en
  menos de un segundo; la precomputación se difiere al primer `speak` con la voz.
- `model_cache` respeta `HF_HOME`/`HF_HUB_CACHE` al resolver la caché del modelo.
- **Build de macOS**: `LSMinimumSystemVersion` dinámica (N-07) derivada de
  `sysconfig.get_config_var("MACOSX_DEPLOYMENT_TARGET")` con fallback a
  `platform.mac_ver()`; ya no hay literal `12.0` que se desincronice del toolchain.
- **Requisito de glibc ≥ 2.35 documentado** (N-06) en README y USAGE (Ubuntu
  22.04+, Debian 12+, Fedora 36+); entrada de troubleshooting para
  `GLIBC_2.35 not found`.
- **Ventana de arranque del daemon (30–90 s) documentada** (N-13) en
  `docs/DAEMON-MODE.md`: `status`/`stop` no ven el proceso hasta que el puerto
  abre; orquestadores deben esperar confirmación de `daemon start` o sondear
  `/health`.
- **Sección "Actualizar de versión" en USAGE.md** (N-16): tres caminos por SO
  (Windows: instalar nuevo `.exe`; Linux: nuevo AppImage + `setup` para
  re-apuntar symlink; macOS: re-arrastrar `.app` + re-ejecutar `.command`).
- Dependencia `chatterbox-tts` corregida a `>=0.1.7` (la versión declarada
  `>=0.3.0` era insatisfacible en PyPI).
- `THIRD-PARTY-LICENSES.md` regenerado desde el lockfile: licencias de modelo
  verificadas (MIT), declaración de libsndfile (LGPL-2.1+), `soxr` (LGPL),
  `pykakasi` (GPLv3+) y los runtimes NVIDIA CUDA; se retiraron `simpleaudio` y
  `pyalsaaudio` (no usados).
- Conteo de tests actualizado a **199** en `docs/GOAL.md` y `CLAUDE.md`.

### Corregido

- Cierre limpio ante `Ctrl+C`: mensaje breve en stderr y código 130, sin traceback.
- `setup` provisiona explícitamente `ve.safetensors`; `doctor`/`is_model_cached`
  verifican su presencia (cierra la fuga de red en el primer `speak`).
- Onboarding del README: enlace de Releases al repositorio real y nombres de
  artefactos por SO corregidos.

[No publicado]: https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/releases/tag/v0.1.0
