# Changelog

Todos los cambios notables de TTS Sidecar se documentan en este archivo.

El formato se basa en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el proyecto adhiere a [Versionado Semántico](https://semver.org/lang/es/).

## [Unreleased]

### Añadido

- **`speak --json`** (auditoría production-readiness, S2-01): acoplado a
  `--output` (el archivo es el canal de datos; `--json` solo emite metadatos a
  stdout), emite `{"schema_version","output","voice","t3_time","s3gen_time","daemon"}`
  a stdout, idéntico campo a campo en modo directo y vía daemon. `--json` sin
  `--output` falla con exit 4 antes de cualquier trabajo.
- **`daemon start/stop/restart --json`** (S2-02): payload de resultado de la
  acción `{"schema_version","action","ok","pid"?}` a stdout; los mensajes
  informativos pasan a stderr en modo `--json`. `daemon serve` queda
  deliberadamente sin `--json` (su contrato es el stream NDJSON del server).
- **Versionado del protocolo NDJSON del daemon** (S2-05): los 5 modelos de
  `daemon/protocol.py` (`ProgressEvent`, `ResultEvent`, `ErrorEvent`,
  `HealthResponse`, `VoicesResponse`) heredan de una clase base común
  (`ProtocolModel`) con `schema_version` y `extra="ignore"` explícitos;
  `HealthResponse`/`/health` gana el campo `version` (la del paquete), que
  permite diagnosticar el skew entre un daemon residente y un CLI actualizado.
  Política de compatibilidad documentada en `docs/DAEMON-MODE.md`.
- **Test estructural del contrato `--json`** (S2-06): `build_parser()` se
  extrajo de `main()` para ser introspeccionable; un test nuevo descubre desde
  el parser real qué subcomandos declaran `--json` y lo compara contra la
  cobertura declarada en los tests, rompiendo ante un comando nuevo sin cubrir
  o un flag retirado.
- **Oferta de código fuente GPLv3 §6 en los 4 artefactos** (S2-14):
  `SOURCE-OFFER.md` (generado por `scripts/render_source_offer.py` desde la
  versión single-source, con la URL del tarball del tag y el enlace al
  release) viaja ahora dentro de los 3 bundles nativos (vía `LICENSE_FILES`)
  y del wheel/sdist de PyPI (vía `license-files`), de modo que la oferta
  acompaña al binario por cualquier vía de redistribución. Un test de
  consistencia byte-exacto falla si el archivo commiteado diverge del
  generador o de la versión.
- **Cobertura de tests medida y gateada por módulo** (S2-09): `pytest-cov`
  pineado vía `pipeline.parameters.pytest_cov_version` (mismo mecanismo que el
  pin de `pytest`), configuración única en `[tool.coverage.*]` de
  `pyproject.toml`. Nuevo job `coverage` independiente en CI (Linux, no
  duplicado en los tres SO) que corre la suite bajo `pytest --cov` y aplica
  `scripts/check_coverage.py`, un gate diferenciado por módulo (`MODULE_FLOORS`
  como fuente única de los pisos, fijados por ratchet-desde-lo-medido) para los
  módulos de contrato (`cli.py`, `daemon/*`, `model_cache.py`, `voices.py`,
  `paths.py`); el resto se reporta sin gatear. Publica `coverage.xml` como
  artefacto. Coverage queda opt-in: `pytest tests/ -v` sigue verde sin
  `pytest-cov` instalado.
- **Verificación automatizada del inventario de licencias** (S1-02):
  `scripts/check_third_party_licenses.py` compara el conjunto de paquetes de
  `requirements-lock.txt` contra la tabla de `THIRD-PARTY-LICENSES.md`
  (nombres normalizados PEP 503) y un test de la suite falla con diff legible
  ante cualquier faltante o sobrante — la desincronización del inventario
  legal deja de ser silenciosa.
- **Caveats de licencia en el Cask de Homebrew**: el Cask informa la licencia
  GPL-3.0-or-later y la ubicación de `SOURCE-OFFER.md` y
  `THIRD-PARTY-LICENSES.md` dentro del `.app` instalado (la stanza `license`
  no existe en el DSL de Casks).

### Cambiado

- Todos los cambios de contrato anteriores son **aditivos**: `schema_version`
  del CLI y del protocolo NDJSON permanecen en `"1"`. Internamente,
  `engine.speak()`, `SynthesisOrchestrator.synthesize()` y
  `DaemonIPCClient.synthesize()` ahora retornan un objeto de resultado
  `SynthesisResult` (audio + métricas `t3`/`s3gen`) en vez de `bytes` desnudos,
  unificando la fuente de métricas de ambas rutas de síntesis; y los emisores
  `--json` existentes del CLI se migraron a un helper único `emit_json()`
  (mismos payloads, sin cambios de clave).
- **create-dmg pineado por contenido** (S2-15): el build de macOS ya no
  instala create-dmg vía `brew install` sin versión; `build_macos.py` descarga
  el tarball del release v1.3.0 pineado por URL + SHA-256 (`fetch_pinned_asset`,
  misma política que appimagetool) y ejecuta el script extraído. El step de
  Homebrew desapareció de `.circleci/config.yml` y la dependencia pasa a ser
  dura (su fallo aborta el build en vez de degradar con warning): el 100% del
  tooling de build queda fijado por contenido.
- **Wheel PyPI con inventario legal completo**: `THIRD-PARTY-LICENSES.md`
  (antes ausente del canal PyPI) y `SOURCE-OFFER.md` se incluyen ahora en el
  wheel y el sdist junto a `LICENSE`.

### Arreglado

- **Normalización de la criticidad de Inno Setup** (auditoría
  production-readiness, S2-10): `create_installer_windows.py` declaraba Inno
  Setup con `required=False` y luego lo hacía fatal con un `sys.exit(1)` manual
  redundante, desacoplando la criticidad real del mecanismo declarativo. Ahora
  se resuelve con `required=True` en `ensure_build_dependency` y se elimina el
  `sys.exit` manual: el aborto por dependencia faltante queda gobernado en un
  único punto (igual que PyInstaller y sounddevice). Se añaden los tests de
  rama de fallo `tests/test_create_installer_windows.py::
  test_main_inno_missing_is_fatal` (Inno ausente → aborta) y
  `tests/test_build_linux.py::test_appimage_tooling_missing_degrades_without_abort`
  (tooling del AppImage ausente → degrada sin abortar), y se corrige el drift de
  `docs/BUILD.md`, que aún clasificaba a Inno Setup como empaquetador que degrada.

- **Cancelación cooperativa de la síntesis al desconectar el cliente**:
  en el modo daemon, `/synthesize` ahora detecta la desconexión del cliente y
  aborta la síntesis en curso en vez de malgastar GPU/CPU hasta completarla. El
  generador del stream setea un `threading.Event` al detectar la desconexión
  (vía `GeneratorExit`/`OSError`), el callback de progreso del worker eleva
  `SynthesisCancelled` (nueva excepción compartida en `exceptions.py`) y el
  engine la re-lanza selectivamente desde `_emit_progress`/`_token_counting_iter`
  sin romper el contrato best-effort para otras excepciones del callback. El
  `finally` del worker sigue liberando el semáforo de admisión y la memoria. Es
  la opción A híbrida: cancelación cooperativa en la fase T3, sin instrumentar
  S3Gen.

- **Test dedicado de `scripts/pyinstaller_wrapper.py`** (auditoría
  production-readiness, S2-13): el componente crítico que evita el cuelgue COM
  del build Windows (`sys.coinit_flags = 0x8` antes del `import` de comtypes +
  `os._exit` para saltar el `CoUninitialize()` de `atexit`) ahora tiene
  `tests/test_build_utils.py::TestPyinstallerWrapper`. Cubre `main()` (propagación
  del `returncode` vía `os._exit` y limpieza del archivo temporal bootstrap) y el
  `_BOOTSTRAP` (la fijación de `coinit_flags` antes del `import` de PyInstaller).
  Es puramente aditivo y usa mocks, sin ejecutar PyInstaller ni tocar red/disco.
  Complementa `tests/test_build_utils.py::TestRunPyinstaller`, que ya ejercía la
  rama de timeout de `run_pyinstaller` (mata el árbol de procesos y retorna 1),
  dejando S3-01 cubierto de extremo a extremo.

## [0.6.0] — 2026-07-11

Cierra la última brecha accionable de paridad de experiencia entre los 3 SO
registrada en `docs/PARITY.md`: la de *desinstalación en un comando*. Con ella,
`tts-sidecar setup --uninstall` deja de ser solo-Linux y pasa a ser un comando
único en los tres SO (dispatch por SO sobre un contrato compartido: datos → PATH
→ binario, con cancelación atómica y guard de canal nativo). MINOR: capacidad
nueva en macOS y Windows, más un cambio de comportamiento deliberado en Linux.
Solo la brecha de *firma de código* (SmartScreen/Gatekeeper, binarios sin firmar)
queda diferida al goal a largo plazo.

### Añadido

- **`setup --uninstall` en macOS** (`_uninstall_macos`): desinstalación de un
  comando que encadena `cleanup --all`, quita el symlink per-user de
  `~/.local/bin` y borra el `.app` (localizado desde `sys.executable` con
  `resolve()`; cubre `~/Applications`, `/Applications` y el Cask con una sola
  expresión, con guard de sufijo `.app`). Si la instalación proviene de Homebrew
  (metadata del Caskroom), aborta sin borrar nada y remite a `brew uninstall
  --cask --zap tts-sidecar` para no dejar el Caskroom inconsistente.
- **`setup --uninstall` en Windows** (`_uninstall_windows`): valida primero el
  `QuietUninstallString` del registro (HKCU, clave `{AppId}_is1`) sin efectos,
  borra los datos en proceso con `cleanup --all` y **delega** el binario y la
  reversión del PATH al desinstalador de Inno, lanzado desacoplado con
  `subprocess.Popen` (el SO mantiene el lock del `.exe`). El payload `--json`
  atestigua las rutas de datos en `removed` y el directorio de instalación en el
  campo aditivo `delegated`.
- **Guard de canal nativo** (`is_frozen`) en `setup --uninstall`, común a los
  tres SO: desde fuente o desde una instalación pip/uv, aborta remitiendo a `pip
  uninstall tts-sidecar` en lugar de operar sobre rutas que no le pertenecen.

### Cambiado

- **Reorden de la rama Linux de `setup --uninstall`** al orden unificado del
  contrato compartido (`cleanup --all` → symlink → directorio de instalación, en
  vez de symlink → directorio → cleanup). Habilita la **cancelación atómica**:
  cancelar la confirmación del cleanup aborta la desinstalación sin borrar nada
  (salida 0), imposible con el orden anterior (el binario caía antes de la
  pregunta). Además el uninstall borra ahora el directorio raíz de datos
  (`data_root()`) si queda vacío tras el cleanup.
- **Payload `--json` de `setup --uninstall`**: `removed` incluye ahora las rutas
  de datos del `cleanup` encadenado (corrección de una omisión de la rama Linux)
  y el `data_root()` si se eliminó. En Windows se añade el campo `delegated`
  (directorio de instalación, borrado por Inno tras la salida del proceso).
  Ambos son cambios aditivos: `schema_version` no cambia.

## [0.5.0] — 2026-07-10

Cierra las brechas de paridad de experiencia entre los 3 SO registradas en
`docs/PARITY.md`: iguala macOS y Linux con la experiencia objetivo de Windows
(instalación de una línea sin admin, actualización sin residuo, desinstalación
con residuo cero). MINOR: añade capacidades y cambia el comportamiento de
instalación en macOS. Solo la brecha de *firma de código* (SmartScreen/Gatekeeper,
binarios sin firmar) queda diferida al goal a largo plazo.

### Añadido

- **Instalador macOS de una línea** (`install-macos.sh`, `curl | sh`): vía sin
  Homebrew ni `sudo`, homóloga a `install.sh`. Descarga el `.dmg` de arm64 y
  `SHA256SUMS.txt`, verifica el checksum con `shasum -a 256 -c` (aborta si no
  coincide), monta con `hdiutil`, copia el `.app` a `~/Applications` con
  `ditto`, limpia la cuarentena de Gatekeeper con `xattr`, crea el symlink
  per-user en `~/.local/bin` (con aviso de PATH) y encadena `setup`. Guard de
  arquitectura arm64 (Mac Intel no soportado). Smoke-test `bats` en el job CI
  `test-installer-macos` (executor macOS) como puerta de los 4 builds.
- **Desinstalador Linux de un paso** (`tts-sidecar setup --uninstall`): quita
  el symlink de PATH, borra `~/.local/opt/tts-sidecar/` y encadena `cleanup
  --all` (con confirmación; `--yes` la omite). Mutuamente excluyente con
  `--remove-path`/`--force-update`, con guard de SO y contrato `--json`
  (requiere `--yes`). Reemplaza los tres pasos manuales anteriores.

### Cambiado

- **Scripts `.command` del `.dmg` sin `sudo`**: la instalación y desinstalación
  incluidas en el `.dmg` de macOS crean/eliminan el symlink per-user en
  `~/.local/bin` en lugar de `/usr/local/bin` con `sudo`. Ninguna vía de
  instalación del proyecto pide ya la contraseña de administrador. **Nota de
  transición**: quien tenga un symlink legado en `/usr/local/bin` (de una
  versión anterior a 0.5.0) verá en el script de desinstalación la instrucción
  para quitarlo (`sudo rm /usr/local/bin/tts-sidecar`).
- **`install.sh` limpia los AppImages anteriores**: tras instalar y dar
  permisos al AppImage nuevo, elimina los `tts-sidecar-*.AppImage` previos de
  `~/.local/opt/tts-sidecar/`, que antes se acumulaban (~1-2 GB por versión).
  Re-ejecutar el one-liner es ahora la vía de actualización limpia de Linux.

### Corregido

- **`zap` del Cask completo**: la stanza `zap trash:` del Cask de Homebrew ahora
  lista los **dos** repos del modelo en la caché de HuggingFace (el multilingüe
  `Chatterbox-Multilingual-es-mx-latam` y el base `chatterbox` del Voice
  Encoder); antes omitía el segundo, dejando cientos de MB de residuo a quien
  desinstalara con `brew uninstall --zap`. Se propaga al tap con este release
  vía `publish-metadata`.

## [0.4.0] — 2026-07-10

Extiende la instalación auto-hospedada de una línea a Windows y migra el
instalador Inno Setup a per-user, sin tocar el contrato del CLI (códigos de
salida, esquemas `--json`). MINOR: cambia el comportamiento de instalación
en Windows.

### Añadido

- **Instalador Windows de una línea** (`install.ps1`, `irm | iex`): resuelve
  el release más reciente, descarga el instalador x86_64 y `SHA256SUMS.txt`,
  verifica el checksum SHA-256 antes de instalar (aborta si no coincide),
  instala en silencio sin UAC y ejecuta `tts-sidecar setup`. La descarga por
  CLI no aplica el Mark-of-the-Web, así que no dispara SmartScreen (detalle
  en `docs/SELF-HOSTED-INSTALL.md` y `SECURITY.md`). Smoke-test Pester en CI
  (`test-installer-windows`) como puerta de los 4 builds.

### Cambiado

- **Instalador de Windows per-user**: Inno Setup pasa de per-machine a
  per-user — `PrivilegesRequired=lowest` (sin prompt de UAC), instalación en
  `%LOCALAPPDATA%\Programs\tts-sidecar` (antes Program Files) y PATH de
  usuario en `HKCU\Environment` (antes HKLM), incluida su reversión al
  desinstalar. **Nota de migración**: si tienes instalada una versión
  per-machine (anterior a 0.4.0), desinstálala primero desde el Panel de
  control (con admin) antes de instalar 0.4.0+; instalar la per-user encima
  puede dejar dos instalaciones y PATH duplicado.

## [0.3.0] — 2026-07-10

Extiende el canal nativo con instalación auto-hospedada por SO y reduce los
falsos positivos de antivirus en los binarios PyInstaller, sin tocar el
contrato del CLI (códigos de salida, esquemas `--json`) ni los canales
existentes (nativo/PyPI).

### Añadido

- **Instalador Linux de una línea** (`install.sh`): resuelve el release más
  reciente, elige el `.AppImage` por arquitectura (`uname -m`), verifica el
  checksum SHA-256 contra `SHA256SUMS.txt` antes de instalar, integra el PATH
  vía la variable `APPIMAGE` y ejecuta `setup`. Documentado en `README.md` y
  `USAGE.md` con su desinstalación limpia de 3 pasos.
- **Cask de Homebrew propio** (`homebrew-tts-sidecar`): `brew install --cask
  tts-sidecar` instala desde el `.dmg` del release; `publish-metadata` en CI
  reescribe el Cask con la versión y el `sha256` del `.dmg` en cada release
  (idempotente). Ver `docs/RELEASING.md` y `docs/DISTRIBUTION.md`.
- **Runbook de reporte de falso positivo** a Windows Defender Security
  Intelligence (WDSI) en `SECURITY.md`, acotado a la detección de Defender
  Antivirus (no afecta SmartScreen).

### Cambiado

- **Endurecimiento del build PyInstaller**: `--noupx` en los flags compartidos
  y metadata PE (`--version-file`) en el `.exe` de Windows, para mitigar las
  heurísticas de antivirus sobre el patrón de empaquetado. Cubierto por tests.

## [0.2.1] — 2026-07-08

Corrige la instalación vía `uv tool install tts-sidecar`: quedaba rota por un
conflicto de resolución de dependencias entre `numpy` y `numba` (transitiva de
`librosa`/`chatterbox-tts`).

### Corregido

- **`uv tool install tts-sidecar` fallaba** al intentar compilar
  `llvmlite==0.36.0` desde fuente en Python 3.13 (`RuntimeError: Cannot
  install on Python version 3.13.14; only versions >=3.6,<3.10 are
  supported`). Causa: `chatterbox-tts` declara `numpy>=2.0.0` sin tope
  superior para Python ≥3.13, mientras que `numba` (dependencia transitiva vía
  `librosa`) exige `numpy<2.5`. El resolvedor de `uv` fijaba primero la
  versión más reciente de `numpy` (sin tope) y, al no poder satisfacer el tope
  de `numba`, retrocedía sobre `numba` hasta versiones sin soporte para Python
  3.13, en vez de retroceder sobre `numpy`. `pip` no caía en esta trampa por
  las heurísticas de su propio resolvedor, por lo que el smoke test de CI
  (que usa `pip install`) no lo detectó. Fix: se fija explícitamente
  `numpy<2.5` como dependencia directa en `pyproject.toml`, acotando el rango
  antes de que cualquier resolvedor tenga que elegir entre `numpy` y `numba`.

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

Ciclo perfectivo que corrige los 12 hallazgos Menores 
identificados durante la revisión final del release `0.1.0`, más el ciclo
correctivo de la auditoría de production-readiness: cierra la única grieta
funcional (el release gate del pin de revisiones en la carga del engine) y siete
Menores (gate de `daemon serve`, identidad del health check, sandbox acotado del
daemon, exactitud documental y procedencia del lockfile). Todos los cambios
de contrato son aditivos: los códigos de salida existentes no cambian y
`schema_version` permanece en `"1"`.

### Añadido

- **`--json` en los cuatro comandos de escritura**: `voice add`
  (`{name, reference, speech}`), `voice remove` (`{name, removed}`), `setup`
  (`{model, already_cached, downloaded, cache_dir}`, con variante para
  `--remove-path`) y `cleanup` (`{removed, dry_run}`). El contrato programático
  queda simétrico: ningún comando obliga a parsear texto. `cleanup --json`
  exige `--yes` o `--dry-run` (exit 4 sin ellos) y envía sus listados
  informativos a stderr.
- **Referencia de esquemas `--json` en `USAGE.md`**: las claves de los
  nueve payloads (tipo y significado) declaradas por escrito como parte del
  contrato, sin necesidad de ingeniería inversa.
- **Revisión fijada del modelo por release**: `setup` descarga ambos
  repos de HuggingFace con `revision=` (commit hash auditado, constantes
  `MODEL_REVISIONS`/`BASE_MODEL_REVISION` en `model_cache.py`) y la detección
  de caché valida el snapshot de esa revisión en ambos repos (ciclo posterior
  cerró el residuo del repo base); el bump del pin es un paso del
  runbook de release (`docs/RELEASING.md`) y su alcance está descrito en
  `SECURITY.md`.
- **Plantillas de Issue/PR en `.github/`**: formularios de bug (versión,
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
- **`daemon stop` honesto durante la ventana de arranque**: detecta el
  daemon en arranque por cmdline (sin PID file), avisa «arrancando; aún no
  acepta conexiones» y termina con exit 5 en vez de reportar un éxito falso;
  no mata el proceso. Documentado en `docs/DAEMON-MODE.md`.
- **CI con imágenes fijadas por digest y pip pineado**: las tres
  referencias `cimg/python:3.13` usan `@sha256:<digest>` (manifest list
  multi-arch) y los siete `pip install --upgrade pip` pasaron a versión exacta.
  Excepciones documentadas: `brew upgrade pyenv` (necesario para el parche
  3.13.14; no altera el artefacto) y `create-dmg` (Homebrew no pinea).
  Implicaciones y procedimiento de bump en `docs/BUILD.md` §Reproducibilidad.
- **Exactitud documental**: stack de reproducción real
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

- **`voice list` ante un directorio de voces ilegible**: el mensaje
  apunta al directorio de voces de usuario implicado en vez de remitir a
  `tts-sidecar setup` (que no resuelve un problema de filesystem); conserva
  exit 3.
- **`speak --daemon --no-daemon`**: los flags contradictorios producen
  un error claro en stderr y exit 4 antes de cualquier trabajo, en vez de que
  `--daemon` gane en silencio.
- **Validación de integridad de los tres checkpoints**: `is_model_cached`
  valida el header safetensors también de `s3gen_v3.safetensors` y
  `ve.safetensors` (antes solo del T3): una descarga truncada de cualquiera se
  reporta como «no cacheado» y `doctor` remite a `setup`, en vez de reventar
  con un error críptico en el primer `speak`.
- **Fixture `mock_daemon_client` alineada con el cliente real**: la
  firma de `synthesize` coincide con `DaemonIPCClient.synthesize`
  (`on_progress` en vez de los inexistentes `model`/`compute_backend`).
- **La detección de vida del daemon valida la identidad del servicio**
  (auditoría de production-readiness): `DaemonIPCClient.is_running` ya no acepta
  cualquier `200` en `/health`, sino que valida el cuerpo contra `HealthResponse`;
  si otro servicio local ocupara el puerto 8765 y respondiera `200`, ya no se
  confunde con un falso «daemon ya corriendo» (que derivaba en síntesis fallidas
  con exit 5 difícil de atribuir). `DaemonManager` delega en el mismo chequeo.
- **Detección del Voice Encoder honra la revisión fijada del repo base**
  (residuo): `is_ve_cached` resuelve el snapshot del
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
  `setup`), AppImages de Linux x86_64/arm64 (runtime estático, sin `libfuse2`;
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
