# Changelog

Todos los cambios notables de TTS Sidecar se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [0.2.0] — 2026-07-08

Añade un segundo canal de distribución (PyPI / `uv tool install` / `pipx`)
junto al canal nativo de binarios PyInstaller existente, sin afectar su
funcionamiento. Requirió reestructurar la ubicación de las voces de fábrica y
el modelo de rutas para que sean válidos en los tres modos de ejecución
(fuente, pip-installed, congelado) sin bifurcaciones. Registra además la
estrategia de firma de código (SignPath + notarización Apple) como compromiso
de roadmap en `docs/GOAL.md`.

### Añadido

- **Canal de distribución PyPI**: `uv tool install tts-sidecar` / `pipx
  install tts-sidecar` instala el CLI completo, incluida la voz `default`.
  Publicación automática en cada tag `v*` vía el job `publish-pypi` de CI, en
  paralelo a los cuatro builds nativos. Documentado en el nuevo
  `docs/DISTRIBUTION.md`, con la matriz de trade-offs frente al canal nativo
  y el registro de la decisión de mantener ambos canales en paralelo.
- **`src/tts_sidecar/bootstrap.py`**: consolida en una única función
  idempotente (`apply()`) la supresión de warnings, las variables de entorno y
  el mock de `pkg_resources` que antes solo vivían en `bin/tts-sidecar`,
  duplicados parcialmente en `daemon/run.py`. Corre igual desde el entry point
  de pip, `bin/tts-sidecar`, `python -m tts_sidecar` y el daemon.
- **`src/tts_sidecar/__main__.py`**: habilita `python -m tts_sidecar` como
  vía de invocación adicional.

### Cambiado

- **Voces de fábrica reubicadas** a `src/tts_sidecar/voices/` (antes `voices/`
  en la raíz del repo), para que setuptools pueda empaquetarlas en el wheel
  (`package-data`); el bundle PyInstaller (`--add-data`) se actualizó al mismo
  origen.
- **Modelo de rutas uniforme** (`paths.py`): `bundled_voices_dir()` resuelve
  siempre relativa al paquete (sin distinguir fuente/congelado) y `data_root()`
  devuelve siempre el user-data-dir por SO, incluso en modo fuente (antes
  caía dentro del propio checkout).
- **`pyproject.toml` publicable**: entry point `tts-sidecar = "tts_sidecar.cli:main"`,
  versión dinámica (`dynamic = ["version"]`) resuelta desde
  `tts_sidecar.__version__` como fuente única, metadata de PyPI completa
  (`readme`, `urls`, `classifiers`, `keywords`) y `package-data` para las
  voces de fábrica.

## [0.1.1] — 2026-07-07

Ciclo perfectivo que corrige los 12 hallazgos Menores y el residuo `WARNING-01`
identificados durante la revisión final del release `0.1.0`, más el ciclo
correctivo de la auditoría de production-readiness: cierra la única grieta
funcional (el release gate del pin de revisiones en la carga del engine) y siete
Menores (gate de `daemon serve`, identidad del health check, sandbox acotado del
daemon, exactitud documental y procedencia del lockfile). Todos los cambios
de contrato son aditivos: los códigos de salida existentes no cambian y
`schema_version` permanece en `"1"`.

### Añadido

- **`--json` en los cuatro comandos de escritura** (R-03): `voice add`
  (`{name, reference, speech}`), `voice remove` (`{name, removed}`), `setup`
  (`{model, already_cached, downloaded, cache_dir}`, con variante para
  `--remove-path`) y `cleanup` (`{removed, dry_run}`). El contrato programático
  queda simétrico: ningún comando obliga a parsear texto. `cleanup --json`
  exige `--yes` o `--dry-run` (exit 4 sin ellos) y envía sus listados
  informativos a stderr.
- **Referencia de esquemas `--json` en `USAGE.md`** (R-04): las claves de los
  nueve payloads (tipo y significado) declaradas por escrito como parte del
  contrato, sin necesidad de ingeniería inversa.
- **Revisión fijada del modelo por release** (R-15): `setup` descarga ambos
  repos de HuggingFace con `revision=` (commit hash auditado, constantes
  `MODEL_REVISIONS`/`BASE_MODEL_REVISION` en `model_cache.py`) y la detección
  de caché valida el snapshot de esa revisión en ambos repos (ciclo posterior
  cerró el residuo `WARNING-01` del repo base); el bump del pin es un paso del
  runbook de release (`docs/RELEASING.md`) y su alcance está descrito en
  `SECURITY.md`.
- **Plantillas de Issue/PR en `.github/`** (R-12): formularios de bug (versión,
  SO, comando reproducible, salida) y de propuesta, `blank_issues_enabled:
  false` con la vía de seguridad señalizada, y checklist de PR alineado a
  `CONTRIBUTING.md`.

### Cambiado

- **Documentación del bloqueo SmartScreen/Gatekeeper ampliada**: `README.md`,
  `USAGE.md`, `SECURITY.md` y `docs/BUILD.md` explican por qué el sistema
  bloquea el primer arranque (binario sin firma + sin reputación por ser cada
  release un archivo nuevo), que no indica malware, cómo proceder paso a paso
  (incluido el bloqueo del navegador y la cuarentena de antivirus de terceros,
  siempre tras verificar el SHA-256) y la ruta prevista de firma de código vía
  SignPath Foundation (gratuita para proyectos open source).
- **`daemon stop` honesto durante la ventana de arranque** (R-05): detecta el
  daemon en arranque por cmdline (sin PID file), avisa «arrancando; aún no
  acepta conexiones» y termina con exit 5 en vez de reportar un éxito falso;
  no mata el proceso. Documentado en `docs/DAEMON-MODE.md`.
- **CI con imágenes fijadas por digest y pip pineado** (R-14): las tres
  referencias `cimg/python:3.13` usan `@sha256:<digest>` (manifest list
  multi-arch) y los siete `pip install --upgrade pip` pasaron a versión exacta.
  Excepciones documentadas: `brew upgrade pyenv` (necesario para el parche
  3.13.14; no altera el artefacto) y `create-dmg` (Homebrew no pinea).
  Implicaciones y procedimiento de bump en `docs/BUILD.md` §Reproducibilidad.
- **Exactitud documental** (R-11, R-13): stack de reproducción real
  (winsound/sounddevice/afplay) en `docs/DESIGN.md` y `docs/ARCHITECTURE.md`
  (antes describían pycaw-WASAPI/pyalsaaudio/AVFoundation); árboles de
  estructura con `voices.py`, `paths.py` y `model_cache.py`; CI descrito como
  Linux/Windows/macOS en `CONTRIBUTING.md`; conteo de tests actualizado a
  **268** en `docs/GOAL.md`; inventario de licencias consistente (dependencias
  copyleft-compatibles mencionadas en `USAGE.md`/`CLAUDE.md`; los runtimes
  NVIDIA no van en ningún artefacto distribuido — `README.md` y
  `THIRD-PARTY-LICENSES.md`).

- **El engine honra las revisiones fijadas en la carga y en las descargas de
  respaldo** (release gate de la auditoría de production-readiness): la
  resolución de snapshot en tiempo de carga (language pack y snapshot base del
  Voice Encoder) y las dos redes de seguridad de descarga (`snapshot_download`
  del modelo, `hf_hub_download` de `ve.safetensors`) pasan `revision=`
  (`MODEL_REVISIONS`/`BASE_MODEL_REVISION`). Cierra la asimetría por la que la
  detección honraba el pin pero la carga caía al fallback `refs/main`→mtime: tras
  un bump futuro de revisión ya no puede producirse síntesis silenciosa con el
  modelo viejo. Simétrico con `setup` y la detección de caché.
- **`daemon serve` exige el modelo en caché antes de arrancar** (auditoría de
  production-readiness): mismo gate que `daemon start`; sin modelo provisionado
  falla rápido remitiendo a `setup` (exit 2) sin cargar el engine ni disparar la
  descarga de su red de seguridad. Ningún subcomando descarga de forma implícita.
- **Sandbox de audio del daemon acotado a un subdirectorio namespaced**
  (auditoría de production-readiness): `/synthesize` acepta audio bajo los
  directorios de voces (fábrica/usuario) y `<tempdir>/tts-sidecar/`, pero ya no
  bajo el tempdir compartido general (`%TEMP%`/`/tmp`), reduciendo la superficie
  de temp compartido preservando el staging IPC. `docs/DAEMON-MODE.md` y
  `USAGE.md` describen la superficie real.
- **Exactitud documental de estados, conteos y `doctor`** (auditoría de
  production-readiness): `daemon status` documenta los valores reales
  (`"healthy"`/`"initializing"`, ya no `"ready"`) en prosa y en la tabla del
  esquema JSON de `USAGE.md`; el ejemplo de `doctor` incluye el chequeo de RAM y
  el total de chequeos coherente (5); conteo de tests a **268**.
- **`requirements-lock.txt` regenerado con el comando canónico** (auditoría de
  production-readiness): sin el `--constraint` a un archivo externo al repo; su
  header ya no referencia ningún override y la procedencia vuelve a ser
  reproducible desde `CLAUDE.md`/`docs/BUILD.md`. La resolución de versiones es
  idéntica a la anterior; instala con `--require-hashes`.

### Corregido

- **`voice list` ante un directorio de voces ilegible** (R-01): el mensaje
  apunta al directorio de voces de usuario implicado en vez de remitir a
  `tts-sidecar setup` (que no resuelve un problema de filesystem); conserva
  exit 3.
- **`speak --daemon --no-daemon`** (R-02): los flags contradictorios producen
  un error claro en stderr y exit 4 antes de cualquier trabajo, en vez de que
  `--daemon` gane en silencio.
- **Validación de integridad de los tres checkpoints** (R-07): `is_model_cached`
  valida el header safetensors también de `s3gen_v3.safetensors` y
  `ve.safetensors` (antes solo del T3): una descarga truncada de cualquiera se
  reporta como «no cacheado» y `doctor` remite a `setup`, en vez de reventar
  con un error críptico en el primer `speak`.
- **Fixture `mock_daemon_client` alineada con el cliente real** (R-10): la
  firma de `synthesize` coincide con `DaemonIPCClient.synthesize`
  (`on_progress` en vez de los inexistentes `model`/`compute_backend`).
- **La detección de vida del daemon valida la identidad del servicio**
  (auditoría de production-readiness): `DaemonIPCClient.is_running` ya no acepta
  cualquier `200` en `/health`, sino que valida el cuerpo contra `HealthResponse`;
  si otro servicio local ocupara el puerto 8765 y respondiera `200`, ya no se
  confunde con un falso «daemon ya corriendo» (que derivaba en síntesis fallidas
  con exit 5 difícil de atribuir). `DaemonManager` delega en el mismo chequeo.
- **Detección del Voice Encoder honra la revisión fijada del repo base**
  (`WARNING-01`, residuo de R-06): `is_ve_cached` resuelve el snapshot del
  repo `ResembleAI/chatterbox` exclusivamente contra `BASE_MODEL_REVISION` (un
  VE de otra revisión ya no cuenta como caché válida), simétrico con la
  descarga de `setup` y con la rama del language pack. Cobertura nueva: caso
  positivo bajo `BASE_MODEL_REVISION` y caso negativo (revisión distinta) en
  `tests/test_engine_cache.py`. Párrafo de `USAGE.md` sobre actualización
  anclado al mecanismo real (revisión fijada por release + deduplicación por
  blob de la caché de HF).
- **Decisión de validación E2E documentada** (criterios 1-3, 9 de
  `docs/GOAL.md`): la validación end-to-end de los instaladores por SO es
  externa al pipeline por diseño (consume demasiada cuota de runner al cargar
  el modelo y los ~2 GB de pesos en cada build). El pipeline mantiene el smoke
  test automatizado del binario congelado. Fuera del pipeline: Windows la
  realiza el propietario sobre su equipo local; Linux y macOS dependen de
  feedback de usuarios reales. La decisión completa está en `docs/GOAL.md`
  §"Decisión de validación E2E" y `docs/BUILD.md` §"Verificación post-build".

## [0.1.0] — 2026-07-03

Release inaugural. Al ser la primera versión publicada, no hay base previa
respecto de la cual registrar cambios o correcciones: esta sección describe el
estado con el que nace el producto.

### Añadido

- **Motor de síntesis offline** con Chatterbox Multilingual (alias
  `es-mx-latam`, español latinoamericano): voz por defecto empaquetada
  (`default`, de fábrica) y clonación de voz vía `voice add` con modelo
  dual-audio (`reference.wav` para timbre + `speech.wav` para conditioning).
  El audio generado no lleva marca de agua (watermark de PerthNet desactivado
  por diseño; ver «Uso ético y responsable»).
- **CLI multiplataforma** (Windows/Linux/macOS, idéntica en los tres SO) con
  los comandos `speak`, `voice` (`add`/`list`/`remove`), `daemon`
  (`start`/`stop`/`restart`/`status`/`serve`), `devices`, `doctor`, `setup`,
  `cleanup` y `version`; salidas de usuario en español.
- **Contrato programático para orquestadores** (consumo vía `subprocess`):
  stdout reservado para datos y diagnóstico/progreso por stderr (UTF-8 forzado);
  mapa de códigos de salida congelado — `0` éxito, `1` error genérico, `2`
  modelo no provisionado, `3` voz/audio no encontrado, `4` entrada inválida,
  `5` daemon inalcanzable, `130` interrupción (Ctrl+C, sin traceback) —;
  `--json` con `schema_version` en los comandos de lectura (`version`,
  `doctor`, `devices`, `voice list`, `daemon status`).
- **Progreso real en vivo durante `speak`**: eventos de etapa (conditionals →
  T3 → S3Gen → encoding → guardado) y conteo de tokens del T3 alimentan un
  indicador sobre stderr (solo en TTY), en modo directo y daemon.
- **Modo daemon**: servidor HTTP persistente en loopback (puerto fijo 8765,
  sin autenticación — control de acceso delegado al SO) que mantiene el modelo
  en memoria entre invocaciones; `/synthesize` responde un stream NDJSON
  (`progress` → `result`/`error`, modelos Pydantic en `daemon/protocol.py`);
  sandbox de rutas de audio (solo directorios de voces) con degradación
  automática a modo directo o error accionable según el despacho; auto-reinicio
  opcional (`--autorestart`, `--max-retries`).
- **Validación de entrada en `speak`**: `--text` acotado a 5000 caracteres
  (exit 4 en ambas rutas, directa y daemon) con advertencia no bloqueante por
  encima de 2000; `--compute-backend` (`auto`/`cpu`/`cuda`/`mps`) con aviso
  cuando el daemon lo ignora; `--output` crea los directorios padres.
- **Ciclo de vida de provisión completo**: `setup` idempotente (chequeos de
  entorno + descarga ligera vía `snapshot_download`, sin cargar el modelo en
  RAM; incluye `ve.safetensors` para que ningún `speak` posterior necesite
  red), pre-chequeo de espacio en disco, `--force-update` para re-descarga
  limpia, e integración de PATH en Linux/AppImage (`--remove-path` la
  revierte); `speak`/`daemon start` fallan rápido remitiendo a `setup` sin
  descargas silenciosas; `cleanup` desaprovisiona quirúrgicamente
  (`--model`/`--voices`/`--all`/`--dry-run`, confirmación interactiva, `--yes`
  y EOF tratado como cancelación limpia para uso programático).
- **Distribución por SO**: instalador de Windows (Inno Setup, PATH + casilla de
  `setup`), AppImages de Linux x86_64/aarch64 (runtime estático, sin `libfuse2`;
  requiere glibc ≥ 2.35, documentado con troubleshooting) y `.dmg` de macOS
  arm64 con scripts de instalación/desinstalación y `LSMinimumSystemVersion`
  derivada dinámicamente del toolchain.
- **Cadena de suministro y CI**: lockfile universal con hashes
  (`requirements-lock.txt`, instalado con `--require-hashes`) y lock CPU-only
  de Linux x86_64 (sin el stack `nvidia-*-cu12`, AppImage de cientos de MB en
  vez de GB); triple puerta de tests en CI (Linux/Windows/macOS nativos) que
  bloquea los 4 builds; smoke test del binario congelado en cada build; SHA-256
  de cada artefacto emitido en el log y `SHA256SUMS.txt` en el Release; runbook
  de publicación en `docs/RELEASING.md`.
- **Documentación y gobernanza**: `USAGE.md` (guía por caso de uso),
  `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DAEMON-MODE.md`,
  `docs/BUILD.md`, `docs/RELEASING.md`, sección de uso ético y responsable
  (README/USAGE), `CONTRIBUTING.md`, `SECURITY.md`, este `CHANGELOG.md` y
  `THIRD-PARTY-LICENSES.md` (inventario de licencias generado del lockfile).
  Código propio bajo GPL-3.0-or-later; modelo MIT.

[0.1.1]: https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/releases/tag/v0.1.0
