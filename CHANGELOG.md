# Changelog

Todos los cambios notables de `tts-sidecar` se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [No publicado]

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
- **Modo daemon**: servidor HTTP persistente en loopback que mantiene el modelo en
  memoria entre invocaciones.
- **Mapa de códigos de salida** del CLI como contrato público: `0` éxito, `1` error
  genérico, `2` modelo no provisionado, `3` voz/audio no encontrado, `4` entrada
  inválida, `5` daemon inalcanzable, `130` interrupción (SIGINT).
- **Lockfile universal con hashes** (`requirements-lock.txt`) para builds
  reproducibles e íntegros; CI instala con `--require-hashes`.
- **Smoke test** del binario congelado en los 4 jobs de build de CI.
- **Triple puerta de tests** en CI (`test-linux`, `test-windows`, `test-macos`):
  la suite `pytest` corre en los tres SO nativos y bloquea los builds, con
  cobertura equivalente entre plataformas.
- Sección de **uso ético y responsable** en README y USAGE (consentimiento, no
  suplantación, divulgación del watermark desactivado, canal de reporte).
- Documentos de gobernanza: `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`.

### Cambiado

- **Puerto del daemon fijo en 8765** (loopback): se eliminó el flag `--port` por
  completo. **Breaking**: ya no es posible configurar el puerto ni correr dos
  daemons simultáneos.
- Diagnósticos e instrumentación de progreso redirigidos a **stderr**; stdout
  queda reservado para datos (salidas `--json`, rutas de resultado).
- `voice add` ya no instancia el motor de inferencia: valida y copia los audios en
  menos de un segundo; la precomputación se difiere al primer `speak` con la voz.
- `model_cache` respeta `HF_HOME`/`HF_HUB_CACHE` al resolver la caché del modelo.
- Build de macOS: artefacto renombrado a `arm64` (Apple Silicon); se retiró la
  falsa promesa `universal2`/Mac Intel. `LSMinimumSystemVersion` alineada a 12.0.
- Dependencia `chatterbox-tts` corregida a `>=0.1.7` (la versión declarada
  `>=0.3.0` era insatisfacible en PyPI).
- `THIRD-PARTY-LICENSES.md` regenerado desde el lockfile: licencias de modelo
  verificadas (MIT), declaración de libsndfile (LGPL-2.1+), `soxr` (LGPL),
  `pykakasi` (GPLv3+) y los runtimes NVIDIA CUDA; se retiraron `simpleaudio` y
  `pyalsaaudio` (no usados).

### Corregido

- Cierre limpio ante `Ctrl+C`: mensaje breve en stderr y código 130, sin traceback.
- `setup` provisiona explícitamente `ve.safetensors`; `doctor`/`is_model_cached`
  verifican su presencia (cierra la fuga de red en el primer `speak`).
- Onboarding del README: enlace de Releases al repositorio real y nombres de
  artefactos por SO corregidos.

[No publicado]: https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/releases/tag/v0.1.0
