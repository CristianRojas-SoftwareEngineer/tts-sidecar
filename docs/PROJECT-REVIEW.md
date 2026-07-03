# Auditoría de Preparación para Producción — `tts-sidecar`

## Introducción

Este documento constituye el reporte completo de la auditoría técnica independiente de producción (production-readiness audit) realizada sobre el proyecto `tts-sidecar`, un motor de síntesis de voz (TTS) offline basado en Chatterbox Multilingual V3 para español latinoamericano.

### Postura de la auditoría

La auditoría adopta una postura **adversarial-constructiva**: el objetivo no es confirmar que el proyecto está bien, sino identificar lo que impediría, degradaría o avergonzaría un primer release público. Cada afirmación de la documentación se verificó contra el código fuente como hipótesis, no como hecho dado.

### Punto de partida

El proyecto ya completó dos auditorías de equivalencia de UX entre sistemas operativos (ambas cerradas, la segunda en el commit `a0a77cc`). Esas auditorías cubrieron:

- Paridad de PATH entre plataformas
- Desinstalación limpia
- Naming de artefactos
- Consola persistente post-instalación en Windows
- Runtime AppImage sin FUSE
- Semántica setup-provisión vs. doctor-diagnóstico
- Sincronización documental asociada

**Esta auditoría parte de esos cierres como base** y audita las capas que ellas no cubrieron: robustez del CLI, contrato programático, daemon, gestión del modelo, compatibilidad multiplataforma real más allá de la equivalencia de UX, experiencia de instalación-to-desinstalación end-to-end, calidad de tests, documentación como producto, licenciamiento y cumplimiento, y cadena de suministro/CI.

### Alcance

Se auditaron las siguientes capas del proyecto:

| Capa | Archivos evaluados |
|------|-------------------|
| **Código fuente** | `src/chatterbox_tts/*.py` (cli.py, engine.py, audio.py, voices.py, paths.py, timing.py, model_cache.py, daemon/*) |
| **Scripts de build** | `scripts/build_*.py`, `scripts/build_utils.py`, `scripts/create_installer_windows.py` |
| **Configuración de CI** | `.circleci/config.yml` |
| **Dependencias** | `requirements.txt`, `pyproject.toml`, `package.json` |
| **Documentación** | `README.md`, `USAGE.md`, `docs/GOAL.md`, `docs/DESIGN.md`, `docs/ARCHITECTURE.md`, `docs/DAEMON-MODE.md`, `docs/BUILD.md` |
| **Licencias** | `LICENSE`, `THIRD-PARTY-LICENSES.md` |
| **Tests** | `tests/*.py` (cobertura y conteo) |

### Convenciones del documento

- Los hallazgos se identifican con código `R-XX` (Review, número secuencial).
- La severidad se clasifica en tres niveles:
  - **Bloqueante**: impide el release o hace que falle el caso de uso central.
  - **Mayor**: degradaría la primera impresión o complicaría el soporte.
  - **Menor**: trabajo de pulido que no bloquea el release.
- Cada hallazgo incluye:
  - Evidencia (archivo y línea, o cita documental).
  - Escenario concreto de usuario o integrador que lo sufre.
  - Propuesta de solución recomendada.
  - Análisis de tradeoffs de la propuesta.

### Metodología de la revisión

El reporte original se sometió a una **revisión adversarial-constructiva** posterior: se verificó cada referencia de línea contra el código fuente, se validó la existencia de archivos referenciados, se contaron los tests reales con `pytest --collect-only`, y se comprobó que la documentación existe donde se la cita. Los errores detectados (líneas incorrectas, conteos desactualizados, mezclas de idioma, nombres de archivos inexactos) fueron corregidos en este reporte. En las secciones siguientes se anota explícitamente cuando un hallazgo se matizó o se redujo su severidad respecto del primer borrador.

---

## Tabla de Contenido

1. [Robustez del CLI y Manejo de Errores](#dimensión-1--robustez-del-cli-y-manejo-de-errores)
2. [Contrato Programático](#dimensión-2--contrato-programático)
3. [Daemon](#dimensión-3--daemon)
4. [Gestión del Modelo y del Estado en Disco](#dimensión-4--gestión-del-modelo-y-del-estado-en-disco)
5. [Compatibilidad Multiplataforma Real](#dimensión-5--compatibilidad-multiplataforma-real)
6. [Experiencia de Instalación/Desinstalación End-to-End](#dimensión-6--experiencia-de-instalacióndesinstalación-end-to-end)
7. [Calidad y Cobertura de Tests](#dimensión-7--calidad-y-cobertura-de-tests)
8. [Documentación como Producto](#dimensión-8--documentación-como-producto)
9. [Licenciamiento y Cumplimiento](#dimensión-9--licenciamiento-y-cumplimiento)
10. [Cadena de Suministro y CI](#dimensión-10--cadena-de-suministro-y-ci)
11. [Resumen Ejecutivo y Gate de Release](#resumen-ejecutivo-y-gate-de-release)

---

## Estado de remediación del gate (actualización 2026-07-03)

> **Esta sección es la fuente autoritativa del estado ACTUAL del proyecto.** Se
> mantiene viva: refleja el resultado del gate de release (tareas T1–T16) y los
> refinamientos posteriores sobre los 38 hallazgos.
>
> **El resto del documento (Dimensiones 1–10) es una foto congelada de la auditoría
> del 2026-07-02** y describe los hallazgos en el estado en que se encontraron. Al
> retomar trabajo, esta sección manda: cualquier afirmación de las dimensiones que
> contradiga la tabla de abajo está superada por la remediación y no debe tomarse
> como estado vigente.

**Resultado:** los **4 bloqueantes**, los **23 mayores** y **4 de los 15 menores**
quedaron **resueltos**; los **11 menores** restantes siguen **pendientes** (todos de
pulido, ninguno bloquea el release). Suite de tests tras el gate: **162** (era 139).

**Refinamiento posterior al gate (2026-07-03):** la puerta de tests en CI se hizo
**simétrica en los tres SO** — el job `test` se renombró a `test-linux` y se añadió
`test-macos` (macOS nativo), de modo que `pytest tests/` corre en Linux, Windows y
macOS y los cuatro builds dependen de los tres (ver R-22).

Tres hallazgos se cerraron con una **solución distinta a la «Propuesta» original** del
reporte, por decisión de diseño pre-release: R-06 (mapa de exit codes del SO en vez de
`error_code` en JSON), R-08 (eliminación de `--port` en vez de cablearlo) y R-32
(regeneración manual única en vez de automatización en CI). Se anotan como tales abajo.

### Hallazgos resueltos

| ID | Sev | Solución implementada |
|----|-----|-----------------------|
| **R-10** | Bloq. | `hub_cache_path()` delega en `huggingface_hub.constants.HF_HUB_CACHE`; `setup`/`doctor` muestran la ruta efectiva; tests de precedencia `HF_HOME`/`HF_HUB_CACHE`. (T3) |
| **R-15** | Bloq. | Build macOS restringido a `arm64`; artefactos renombrados `-arm64.*`; toda mención a `universal2`/Mac Intel retirada de CI y docs. (T1) |
| **R-19** | Bloq. | Enlace de Releases del README corregido al repositorio real. (T2) |
| **R-35** | Bloq. | `requirements-lock.txt` **universal con hashes** (uv `--universal`, no pip-tools) instalado en CI con `--require-hashes`. Además se corrigió `chatterbox-tts>=0.3.0`→`>=0.1.7` (era insatisfacible en PyPI). (T11) |
| R-01 | Mayor | `_require_model_cached()` al inicio de `cmd_voice_add` + registro ligero sin instanciar el motor; precomputación diferida al primer `speak`. (T6) |
| R-02 | Mayor | `try/except KeyboardInterrupt` en `main()` → mensaje breve a stderr y `sys.exit(130)`. (T7) |
| R-05 | Mayor | `timing.log()` y los banners de `timed_command` emiten a `sys.stderr`; stdout queda solo para datos/JSON. (T8) |
| R-06 | Mayor | **Solución distinta a la propuesta:** mapa de exit codes del SO `0/1/2/3/4/5/130` como contrato público (constantes `EXIT_*`), en vez de `error_code` en JSON. Tests parametrizados por escenario. (T9) |
| R-08 | Mayor | **Solución distinta a la propuesta:** se **eliminó `--port`** por completo; puerto fijo 8765 (`DEFAULT_PORT` en `ipc.py`) como fuente única importada por `daemon.py`/`run.py`. (T10) |
| R-11 | Mayor | Comando `cleanup` con `--model`/`--voices`/`--all`/`--dry-run`, borrado quirúrgico de las carpetas del proyecto y confirmación interactiva. (T5) |
| R-12 | Mayor | `is_model_cached` verifica `ve.safetensors`; `setup` lo descarga explícitamente; el fallback del engine registra un log que remite a `setup`. (T4) |
| R-16 | Mayor | `LSMinimumSystemVersion` alineado a `12.0` en `Info.plist`. (T1) |
| R-20 | Mayor | Nombres de artefactos por SO del README corregidos a los reales (`-setup.exe`, `.AppImage`, `.dmg`). (T2) |
| R-22 | Mayor | **Triple puerta simétrica de tests:** `test-linux` (renombrado desde `test`), `test-windows` (`win/server-2022`) y `test-macos` (`m4pro.medium`) corren `pytest tests/` en los tres SO nativos; los 4 builds dependen de los tres. Cierra la brecha de que el código de Windows/macOS solo se ejercitaba con mocks. (T13) |
| R-23 | Mayor | Paso «Smoke test frozen binary» (`version`, exit 0) en los 4 jobs de build antes de publicar. (T12) |
| R-26 | Mayor | `CHANGELOG.md` (Keep a Changelog [0.1.0]), `CONTRIBUTING.md` y `SECURITY.md` creados y enlazados desde el README. (T16) |
| R-27 | Mayor | USAGE §«Experiencia unificada» corregido con la tabla de exit codes; docstring del contrato en `cli.py` reafirmado. (T8/T9) |
| R-30 | Mayor | Sección «Uso ético y responsable» en README y USAGE (consentimiento, no suplantación, divulgación del watermark anulado, canal de reporte); reframe del bypass en `engine.py`. (T14) |
| R-31 | Mayor | `libsndfile` (LGPL-2.1+, empaquetado vía `soundfile`) y `soxr` (LGPL) declarados en `THIRD-PARTY-LICENSES.md` con sus obligaciones. (T15) |
| R-32 | Mayor | **Solución distinta a la propuesta:** regeneración **manual única** (sin check CI) de `THIRD-PARTY-LICENSES.md` desde el lock (156 paquetes); se quitaron `simpleaudio`/`pyalsaaudio` y se añadieron transitivas + runtimes NVIDIA CUDA. (T15) |
| R-33 | Mayor | Licencia **MIT verificada** en HuggingFace de `Chatterbox-Multilingual-es-mx-latam` y de `ResembleAI/chatterbox`, citada con enlace. (T15) |
| R-36 | Mayor | Python 3.13 pineado vía `pyenv` en el job macOS de CI. (T11) |
| R-37 | Mayor | Cerrado junto con R-23 (smoke test en los 4 builds). (T12) |
| R-09 | Menor | Modelo de amenaza del daemon (loopback, sin auth, delega en el control de acceso del SO) documentado en `SECURITY.md`. (T16) |
| R-21 | Menor | Advertencia del prompt de sudo del `.command` de macOS añadida al README. (T2) |
| R-25 | Menor | Conteo de tests actualizado a **162** en `CLAUDE.md` y `docs/GOAL.md`. (cierre) |
| R-29 | Menor | README enlaza la licencia MIT verificada del modelo y aclara que GPLv3 es la licencia del proyecto. (T15) |

### Hallazgos pendientes (todos menores, no bloquean el release)

Checklist de reanudación: cada fila describe el trabajo que resta. El detalle completo
(evidencia, escenario, propuesta y tradeoffs) de cada hallazgo está en su sección de
Dimensión más abajo.

| ID | Sev | Trabajo pendiente |
|----|-----|-------------------|
| R-03 | Menor | Emitir un warning cuando el texto de entrada se trunca por exceder `max_new_tokens`. |
| R-04 | Menor | Verificar la integridad del header `.safetensors` del modelo al cargarlo. |
| R-07 | Menor | Versionar y documentar el esquema de la salida JSON del CLI. |
| R-13 | Menor | Añadir un flag `--force-update` para re-descargar el modelo. |
| R-14 | Menor | Pre-chequear el espacio libre en disco antes de descargar en `setup`. |
| R-17 | Menor | Documentar el requisito de permisos de administrador del instalador Windows. |
| R-18 | Menor | Documentar los requisitos mínimos de hardware (CPU/AVX/RAM). |
| R-24 | Menor | Añadir tests de los templates generados por `build_linux.py`/`build_macos.py`. |
| R-28 | Menor | Corregir el ejemplo de `doctor` en USAGE (muestra Python 3.11 en vez de 3.13). |
| R-34 | Menor | Añadir la oferta explícita de código fuente (GPLv3) en la InfoAfter del instalador. |
| R-38 | Menor | Firma/notarización de artefactos — reserva conocida; requiere financiación de certificados. |

---

## Dimensión 1 — Robustez del CLI y Manejo de Errores

### Veredicto **[PARCIALMENTE LISTO]**

El manejo de errores está deliberadamente implementado en los flujos principales:

- `cmd_speak` valida texto vacío (`cli.py:110`) y distingue `FileNotFoundError` de error genérico, remitiendo a `setup` solo cuando el faltante es el modelo (`cli.py:153-160`).
- `cmd_voice_remove` tiene una rama dedicada para `PermissionError`/`OSError` en Windows cuando el archivo está en uso por otro proceso (`cli.py:207-218`).
- `voices._validate_voice_name` neutraliza escapes de ruta (`..`, separadores) con defensa en profundidad en `voice_dir` (`voices.py:28-40, 65-74`).
- Los mensajes de error son accionables y consistentemente en español.

Sin embargo, existen rutas de fallo no gestionadas que contradicen el diseño documentado.

---

### Hallazgos

#### R-01 — `voice add` descarga el modelo saltándose el gate de `setup`

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `cli.py:166-185` (`cmd_voice_add` instancia `ChatterboxEngine(...)` en la línea 172) → `engine.py:216` (`__init__` llama `_download_model`). El gate `_require_model_cached` (`cli.py:93`) se invoca en `cmd_speak` (`cli.py:116`) y `cmd_daemon start` (`cli.py:521`), pero **no** desde `cmd_voice_add`. |
| **Escenario** | Usuario nuevo ejecuta `voice add` antes de `setup`. El código instancia `ChatterboxEngine` directamente, lo que dispara una descarga silenciosa de cientos de MB. Si está sin conexión, falla con un error críptico. Esto contradice el invariante documentado: «las descargas son responsabilidad exclusiva de `setup`» (CLAUDE.md, README, USAGE). |
| **Propuesta** | Añadir `_require_model_cached()` al inicio de `cmd_voice_add` (`cli.py:169`) para abortar temprano si el modelo no está cacheado. Adicionalmente, eliminar la inicialización en caliente del motor en `voice add` (línea 172): la firma de `add_voice` ya expone `precompute: bool = True` (`engine.py:616`), así que basta con extraer la validación (librosa.load, `engine.py:636-643`) y la copia de archivos a una función a nivel de módulo que no requiera instanciar el motor, difiriendo la precomputación de conditionals a la primera síntesis con esa voz. |
| **Tradeoffs y Justificación** | La opción elegida (Diferir precomputación) elimina el arranque en frío del motor TTS (~5s) en el registro de voces. Alternativas evaluadas: (A) Precomputar en `add` condicionalmente: mantiene rápido el primer `speak` pero hace que `voice add` tarde segundos en inicializar PyTorch. (B) Comando separado `voice prepare`: añade fricción y comandos extra al CLI. Justificación: Diferir es óptimo porque el comando `speak` de todos modos ya inicializa el motor por necesidad, por lo que el coste de cómputo adicional se absorbe con mínimo impacto relativo en el primer uso. |

#### R-02 — Ctrl+C a mitad de síntesis produce un traceback, no un cierre limpio

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `grep -n 'KeyboardInterrupt\|SIGINT\|signal' src/chatterbox_tts/cli.py` devuelve **0 coincidencias**. No hay manejador de `SIGINT` en el CLI. `KeyboardInterrupt` no es subclase de `Exception`, por lo que escapa del `except Exception` de `cmd_speak` (`cli.py:161`) y del wrapper `timed_command` (`timing.py:39`). |
| **Escenario** | Usuario interrumpe una síntesis larga con Ctrl+C y recibe un stack trace de Python en lugar de un mensaje de cierre limpio. Un integrador que parsee stderr para detección de errores ve ruido no estructurado. |
| **Propuesta** | Implementar una captura centralizada de `KeyboardInterrupt` en la función `main()` de `cli.py` (alrededor de `args.func(args)`) que imprima un mensaje breve a stderr y termine con `sys.exit(130)` (código estándar para procesos abortados por SIGINT). Nota de implementación: `daemon serve` corre uvicorn, que instala su propio manejo de SIGINT para el shutdown graceful; la captura en `main()` es compatible porque solo actúa si la excepción escapa hasta el CLI. |
| **Tradeoffs y Justificación** | La opción elegida (Captura centralizada en `main`) cubre todas las interfaces del CLI en un solo punto y garantiza una salida limpia y predecible. Alternativas evaluadas: (A) Handlers del sistema con `signal.signal`: puede interferir con el manejo de señales de red de uvicorn en el daemon. (B) Wrappers individuales por comando: duplica código innecesariamente. Justificación: La captura centralizada es no-invasiva, fácil de mantener y preserva el comportamiento natural de loops asíncronos en comandos especiales. |

#### R-03 — Texto largo se trunca en silencio sin advertencia

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `engine.py:130` define `MAX_NEW_TOKENS=500`, que topa la salida del T3. En modo directo no hay límite de entrada de texto. El daemon sí tiene límite (5000 chars, `protocol.py:10`). |
| **Escenario** | Usuario envía un texto de varios párrafos a `speak` y obtiene audio parcial sin ninguna advertencia de que se cortó. |
| **Propuesta** | Agregar una validación de longitud de texto en `cmd_speak` que verifique si el texto supera un umbral de 2000 caracteres. Si excede, emitirá un warning a `sys.stderr` sugiriendo fragmentar, y continuará truncando de acuerdo al límite estricto de tokens del motor. |
| **Tradeoffs y Justificación** | La opción elegida (Warning no bloqueante) alerta de la pérdida de contenido sin interrumpir el pipeline. Alternativas evaluadas: (A) Error duro bloqueante: rompe la compatibilidad con integraciones que envían textos largos esperando truncamiento implícito. (B) Fragmentador automático en el engine: requiere lógica compleja de procesamiento de lenguaje natural (NLP) para segmentar por puntuación y concatenar audio sin clics de fase, fuera del alcance del sidecar. Justificación: El warning es la solución pragmática de menor coste y riesgo técnico. |

#### R-04 — Caché truncada pasa el chequeo de existencia y falla al cargar

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `model_cache.py:79` solo verifica que exista `t3_es_mx_latam.safetensors` (`return (cached / "t3_es_mx_latam.safetensors").exists()`), no su integridad. |
| **Escenario** | Descarga interrumpida por disco lleno deja el archivo presente pero truncado. `doctor` reporta PASS y `speak` falla en `load_file` con error de safetensors ilegible y sin remediación. |
| **Propuesta** | Validar de forma rápida la integridad del archivo de pesos `.safetensors` en `is_model_cached` (leyendo los primeros 8 bytes que corresponden al tamaño del header de metadatos en safetensors) y reportar False si no coincide con el formato esperado. |
| **Tradeoffs y Justificación** | La opción elegida (Verificación ligera de header) es instantánea y evita arranques fallidos por descargas interrumpidas. Alternativas evaluadas: (A) Hash SHA-256 completo en cada inicio: inviable porque tarda segundos en procesar archivos de cientos de MB en disco. (B) Capturar el error en la carga del motor: el fallo se reporta tarde, después de perder tiempo cargando PyTorch en memoria. Justificación: Validar el header previene fallos silenciosos sin impactar el tiempo de respuesta del CLI. |

---

## Dimensión 2 — Contrato Programático

### Veredicto **[NO LISTO]**

El contrato está documentado en el docstring de `cli.py:1-13` y en USAGE §«Experiencia unificada». `main()` fuerza UTF-8 en stdout/stderr (`cli.py:566-570`), resolviendo el caso de consolas Windows no-UTF-8. Los comandos de lectura que emiten JSON (`voice list`, `devices`, `doctor`, `version`, `daemon status`) no usan `log()`/`timed_command`, por lo que su stdout JSON es limpio.

Sin embargo, las afirmaciones centrales del contrato son contradichas por la implementación.

---

### Hallazgos

#### R-05 — El contrato «diagnósticos van a stderr» es falso

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `timing.log()` (`timing.py:11-21`) y `timed_command` (`timing.py:33,37,41` — los banners `Starting …`, `Finished in Xs`, `Failed after Xs`) usan `print()` sin `file=sys.stderr`. Todo el progreso por etapas de `speak`/`voice add` va a **stdout**. Solo los mensajes `Error: …` de los handlers de excepción del CLI van correctamente a stderr. USAGE §«Experiencia unificada» (`USAGE.md:479-481`) repite el mismo contrato incorrecto. |
| **Escenario** | Integrador que sigue el contrato documentado y captura stderr para diagnósticos no obtiene nada. Quien capture stdout esperando «solo datos» recibe decenas de líneas `[HH:MM:SS]`. El audio no colisiona (va a archivo/altavoz), pero la afirmación del contrato engaña al consumidor programático. |
| **Propuesta** | Modificar `timing.py:log()` y `timed_command` para dirigir todo el flujo de progreso e instrumentación a `sys.stderr` por defecto, dejando `sys.stdout` limpio exclusivamente para datos (como la salida JSON o el flujo de audio). |
| **Tradeoffs y Justificación** | La opción elegida (Diagnósticos a stderr) respeta las directrices estándar UNIX y simplifica la vida del integrador. Alternativas evaluadas: (A) Añadir flags `--quiet` / `--verbose`: los integradores que deseen progreso y datos simultáneamente seguirán en conflicto. (B) Usar prefijos en stdout (ej: `[LOG] ...`): obliga a implementar parsers de cadenas en el consumidor programático. Justificación: Redirigir a stderr es el estándar de la industria y la solución más limpia para integradores. |

#### R-06 — Códigos de salida sin granularidad (20 sys.exit(1) sin distinción)

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `grep -n 'sys.exit' src/chatterbox_tts/cli.py` devuelve **20 llamadas a `sys.exit(1)`** (líneas 102, 112, 160, 163, 185, 202, 205, 218, 221, 247, 250, 261, 365, 378, 429, 471, 498, 531, 538, 545), todas con código 1. (Las líneas 679 y 684 son `sys.exit(0)` para casos de éxito). No hay distinción entre «modelo no cacheado», «argumento inválido», «fallo de síntesis» o «voz no encontrada». El contrato (`cli.py:9`) solo promete 0/≠0. |
| **Escenario** | Orquestador que quiera reintentar solo ante «modelo faltante» (llamando a `setup`) pero abortar ante «texto inválido» no puede diferenciarlos sin parsear texto en español de stderr. |
| **Propuesta** | Mantener los códigos de salida `0/1` a nivel del sistema operativo para máxima retrocompatibilidad, pero añadir un campo de grano fino `'error_code'` (entero estable) en el payload JSON de error para comandos que se invocan con `--json`. |
| **Tradeoffs y Justificación** | La opción elegida (error_code en JSON) provee granularidad sin romper integraciones simples que solo comparan códigos de salida binarios (`0` vs `!=0`). Alternativas evaluadas: (A) Mapa de exit codes del SO (ej. exit 2, 3, 4): rompe scripts de automatización antiguos que solo esperan `1` en caso de error. Justificación: Es la alternativa más segura y retrocompatible para exponer diagnóstico granular a nivel programático. Una taxonomía mínima suficiente: `1` genérico, `2` modelo no provisionado, `3` voz/audio no encontrado, `4` entrada inválida, `5` daemon inalcanzable — publicada en la documentación del contrato (ver R-07). |

#### R-07 — Esquema JSON no versionado ni documentado

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | Las salidas `--json` (`doctor`, `version`, `daemon status`, etc.) no llevan campo de versión de esquema. No hay `docs/API.md` ni sección en USAGE que documente formalmente los campos. |
| **Escenario** | Un cambio futuro en las claves de `doctor --json` rompe consumidores sin señal de deprecación. |
| **Propuesta** | Declarar una versión de esquema `'schema_version': '1'` en los payloads JSON e incorporar una sección en `USAGE.md` (o un archivo `docs/API.md` independiente) que defina formalmente los campos y su política de versionado semántico. |
| **Tradeoffs y Justificación** | La opción elegida (Versionado en payload + docs en MD) proporciona claridad contractual con mínimo esfuerzo de mantenimiento. Alternativas evaluadas: (A) Publicar esquemas formales JSON Schema independientes (.json): sobrediseño que añade latencia de lectura/red en runtime. Justificación: Documentar el esquema en markdown es el estándar de oro para APIs CLI ligeras y eficientes. |

---

## Dimensión 3 — Daemon

### Veredicto **[LISTO]**

El daemon presenta múltiples garantías de robustez:

- Bind exclusivo a `127.0.0.1` (`run.py:131`, `daemon.py:34`, `ipc.py:30`).
- Lock de síntesis que serializa el estado global mutable del modelo (`server.py:65, 120`).
- Endpoint síncrono despachado al threadpool para que `/health` responda durante síntesis (verificado por `test_health_responde_durante_sintesis`).
- Validación robusta de rutas de audio en `/synthesize`: existencia, extensión `.wav`, header RIFF/WAVE, contención en directorios permitidos, canonicalización única anti-symlink-swap (`server.py:85-117`).
- `_kill_pid` verifica el cmdline antes de terminar un proceso para no matar servicios ajenos en el puerto 8765 (`daemon.py:225-262`).
- Headers `X-T3-Time` y `X-S3Gen-Time` exponen tiempos por sub-etapa para diagnóstico (`server.py:128-133`).
- Límites duros en `SynthesizeRequest` previenen DoS trivial por payload (5000 chars texto, 4096 chars ruta, `protocol.py:10-27`).

---

### Hallazgos

#### R-08 — `--port` está medio cableado

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | Solo los subparsers `daemon start` (cli.py:649) y `daemon serve` (cli.py:665) definen `--port`; los subparsers `stop` (cli.py:654), `restart` (cli.py:657) y `status` (cli.py:660) no lo declaran, así que `getattr(args,"port",None)` en `cmd_daemon` (cli.py:516) cae a `None` y se usa el default 8765. Además, el cliente de síntesis crea `DaemonIPCClient()` sin puerto (`cli.py:81`, `ipc.py:28-30`) → siempre 8765; `is_daemon_running()` idem (`ipc.py:109-120`). |
| **Escenario** | Usuario arranca `daemon start --port 9000`; luego `daemon status` dice «no está en ejecución», `daemon stop` no lo detiene, y `speak` no lo usa (cae a modo directo en silencio). El daemon en puerto no-default queda huérfano e inalcanzable desde el CLI. |
| **Propuesta** | Declarar el flag `--port` en los subparsers `stop`, `restart` y `status` (`start` y `serve` ya lo tienen); `DaemonManager` ya acepta el puerto (`cli.py:516`), así que la propagación en `cmd_daemon` es inmediata. Para el camino de síntesis, pasar el puerto a `DaemonIPCClient` en `_speak_via_daemon` (`cli.py:81`) y a `is_daemon_running`, usando una variable de entorno `TTS_SIDECAR_DAEMON_PORT` como fallback implícito cuando `speak` no recibe flag. |
| **Tradeoffs y Justificación** | La opción elegida (Flag + Variable de entorno) es robusta, limpia y sin estado en disco. Alternativas evaluadas: (A) Guardar el puerto activo en un archivo de estado físico (ej: `daemon.port`): introduce la posibilidad de leer un archivo huérfano si el daemon crashea o es eliminado forzosamente. Justificación: Las variables de entorno son eficientes y previenen problemas de archivos corruptos o bloqueados en sistemas multiusuario. |

#### R-09 — `/shutdown` sin autenticación (superficie local no documentada)

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | Documentado como SUGGESTION-02 (`server.py:159-177`): cualquier proceso local puede apagar el daemon. `docs/DAEMON-MODE.md` no tiene sección de seguridad que documente el modelo de amenaza. |
| **Escenario** | Combinado con que `/synthesize` también es invocable por cualquier proceso local (DoS de CPU serializado por el lock), conviene declararlo explícitamente en la documentación de seguridad orientada al integrador, que hoy no existe. |
| **Propuesta** | Documentar transparentemente el modelo de amenazas de seguridad del daemon en `docs/DAEMON-MODE.md`, explicitando que al escuchar solo en loopback (`127.0.0.1`), se delega la seguridad en el control de acceso del sistema operativo. |
| **Tradeoffs y Justificación** | La opción elegida (Mitigación documental del riesgo residual) tiene costo-código cero. Alternativas evaluadas: (A) Implementar tokens de autenticación dinámicos en disco: añade complejidad I/O y potenciales fallas de permisos multiusuario. Justificación: Dado que el socket está restringido localmente, la seguridad del SO es suficiente y añadir criptografía local no aporta seguridad real contra un atacante que ya tiene privilegios de ejecución locales. |

---

## Dimensión 4 — Gestión del Modelo y del Estado en Disco

### Veredicto **[PARCIALMENTE LISTO]**

`setup` es idempotente real: si `is_model_cached` es True termina sin descargar (`cli.py:482-484`); `speak`/`daemon start` fallan rápido remitiendo a `setup`. `_resolve_cached_snapshot` resuelve el snapshot vigente de forma determinista (refs/main → mtime, `model_cache.py:38-60`), evitando el `os.listdir()[0]` no determinista. El diseño de dos niveles de voces con precedencia usuario→fábrica está bien encapsulado.

---

### Hallazgos

#### R-10 — La ruta de caché está hardcodeada e ignora `HF_HOME`

| | |
|---|---|
| **Severidad** | Bloqueante |
| **Evidencia** | `model_cache.py:28-30` (`hub_cache_path`) devuelve siempre `Path(os.path.expanduser("~/.cache/huggingface/hub"))`, y `setup` lo repite literal (`cli.py:477`). Pero `snapshot_download` (de `huggingface_hub`, usado en `engine.py:298-304`) **sí** respeta `HF_HOME`/`HF_HUB_CACHE`. |
| **Escenario** | Usuario con `HF_HOME` configurado (entornos corporativos, disco de sistema pequeño, o un alias de usuario con `HOME` redirigido) ejecuta `setup`; el modelo se descarga a la ruta efectiva de HuggingFace (típicamente `$HF_HOME/hub`), pero `is_model_cached` mira solo `~/.cache/huggingface/hub` → devuelve False → `speak` aborta con «modelo no descargado» pese a estar descargado. En la siguiente invocación de `setup`, `is_model_cached` re-evalúa a False, así que re-descarga a una ubicación que igual no detectará. Bucle sin salida. |
| **Propuesta** | Refactorizar `hub_cache_path()` en `model_cache.py` para consultar en el orden de precedencia estándar de Hugging Face: `HF_HUB_CACHE` → `$HF_HOME/hub` → `~/.cache/huggingface/hub` como fallback (o, más simple aún, delegar en `huggingface_hub.constants.HF_HUB_CACHE`, que ya implementa esa precedencia y es la misma fuente que consulta `snapshot_download`). Corregir también el mensaje de `setup` (`cli.py:477`), que imprime la ruta literal `~/.cache/huggingface/hub` en vez de la ruta efectiva. |
| **Tradeoffs y Justificación** | La opción elegida (Precedencia oficial de HF) corrige el bucle de falsos negativos de caché. Alternativas evaluadas: (A) Consultar solo `HF_HOME`: ignora la variable de entorno más específica `HF_HUB_CACHE`, rompiendo configuraciones avanzadas. Justificación: Replicar el comportamiento nativo del cliente de Hugging Face es la única forma de garantizar la consistencia en el estado de caché en entornos corporativos u offline. |

#### R-11 — Sin ruta de desaprovisionamiento del modelo ni de los datos de usuario

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | No existe ningún subcomando `cleanup`/`uninstall`/`purge` en `cli.py:577-677`. El instalador de Windows y los scripts `.command` de macOS solo revierten PATH y dejan `~/.cache/huggingface/hub` y `data_root()/voices` huérfanos. |
| **Escenario** | Usuario desinstala «limpiamente» y queda con cientos de MB de modelo y sus voces en disco, sin instrucción de cómo borrarlos. Una segunda instalación posterior redescarga el modelo y las voces del usuario desaparecen si el directorio de datos se elimina en la desinstalación del SO. |
| **Propuesta** | Crear un subcomando `tts-sidecar cleanup` con flags `--model` (elimina la caché Hugging Face del modelo), `--voices` (elimina el directorio de datos de voces de usuario) y `--all` (ambos), con soporte para `--dry-run` informativo. |
| **Tradeoffs y Justificación** | La opción elegida (Comando cleanup en la CLI) proporciona una experiencia de desinstalación limpia y prolija. Alternativas evaluadas: (A) Recomendar la eliminación manual de carpetas en la documentación: propenso a errores humanos (borrado de datos incorrectos) y fricción de cara al usuario. Justificación: Un software local que descarga gigabytes de datos debe proveer herramientas integradas para liberar espacio de forma segura. |

#### R-12 — Sin verificación de que `ve.safetensors` quede provisionado

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `es-mx-latam` no incluye `ve.safetensors`; se obtiene del modelo base vía `hf_hub_download` durante `_load_es_latam` (`engine.py:335-353`). En el primer `setup` esto se resuelve como efecto colateral de cargar el motor (que llama `_download_model` → `ChatterboxEngine.get_instance`). Pero `is_model_cached` (`model_cache.py:63-81`) solo verifica `t3_es_mx_latam.safetensors` en la carpeta del modelo es-mx-latam, **no** la presencia de `ve.safetensors` en la carpeta de `ResembleAI/chatterbox`. |
| **Escenario** | Si la caché del modelo base se poda o se corrompe externamente, pero `t3_es_mx_latam.safetensors` sigue presente, `doctor`/`setup` reportan todo OK y el primer `speak` **sin conexión** falla al intentar `hf_hub_download("ResembleAI/chatterbox", "ve.safetensors")` (`engine.py:348-353`), rompiendo el criterio de aceptación 8 (offline). |
| **Propuesta** | Modificar `is_model_cached` para validar la presencia de `ve.safetensors` en la caché del modelo base y refactorizar `setup` para que lo descargue explícitamente después del language-pack. |
| **Tradeoffs y Justificación** | La opción elegida (Verificación + Descarga explícita) asegura la autonomía en modo offline. Alternativas evaluadas: (A) Solo verificar el archivo y abortar: el usuario tendría que adivinar cómo descargar `ve.safetensors` si este falta en su caché local. Justificación: Garantiza el cumplimiento de la promesa de '100% offline' tras ejecutar setup, eliminando descargas de red en el primer comando speak. |

#### R-13 — Sin mecanismo de actualización del modelo

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | Un nuevo release del modelo en el repo de HF no se adopta: `refs/main` cacheado apunta a la revisión vieja y `is_model_cached` permanece True para siempre. |
| **Escenario** | El usuario no tiene forma de forzar una actualización del modelo salvo borrar la caché a mano. |
| **Propuesta** | Incorporar el flag `--force-update` a `setup` que descarte el checkpoint local y fuerce una nueva descarga desde el hub de Hugging Face. |
| **Tradeoffs y Justificación** | La opción elegida (Flag explícito de actualización) mantiene la inmutabilidad de la caché por defecto. Alternativas evaluadas: (A) Consultar actualizaciones de red en cada inicio: requiere internet en cada ejecución e incrementa el tiempo de arranque de la aplicación. Justificación: Respeta el diseño offline y la reproducibilidad de la síntesis, permitiendo una actualización bajo demanda del usuario. |

#### R-14 — Sin pre-chequeo de espacio en disco

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `setup` (cli.py:474-498) no verifica espacio en disco antes de la descarga. Una descarga que agota el disco deja caché parcial y propaga el error crudo de `huggingface_hub`. |
| **Propuesta** | Realizar un pre-chequeo del espacio en disco usando la dependencia `psutil` antes de iniciar la descarga en `setup` y abortar con un mensaje descriptivo si el espacio disponible es menor a 2 GB. |
| **Tradeoffs y Justificación** | La opción elegida (Pre-chequeo con psutil) evita descargas corruptas parciales por falta de espacio. Alternativas evaluadas: (A) Capturar el error en plena descarga de HuggingFace: deja archivos huérfanos a medias en disco que pueden confundir a futuras comprobaciones rápidas de presencia. Justificación: `psutil` ya es una dependencia de runtime; su uso inicial es de coste cero y previene la corrupción de la caché local. |

---

## Dimensión 5 — Compatibilidad Multiplataforma Real

### Veredicto **[NO LISTO]**

`paths.py` distingue correctamente raíz escribible (LOCALAPPDATA / `XDG_DATA_HOME` / Application Support) de raíz de fábrica (`sys._MEIPASS` congelado), creando el user-data-dir bajo demanda (`paths.py:34-54`). La autodetección de backend degrada con gracia a CPU envolviendo los probes de torch en try/except (`engine.py:142-161`). El hilo de CPU se topa a 8 por contención de ancho de banda de memoria (`engine.py:47-49`).

Sin embargo, hay inconsistencias en los artefactos y requisitos de plataforma que merecen atención.

---

### Hallazgos

#### R-15 — El build de macOS NO produce un binario universal2 real

| | |
|---|---|
| **Severidad** | Bloqueante |
| **Evidencia** | `build_macos.py` calcula `arch_flag` (líneas 66-67) solo para nombrar el `.app`/`.dmg` (líneas 109, 140), pero **nunca lo pasa a PyInstaller**: `common_pyinstaller_args` (`build_utils.py:191`) no emite `--target-arch` ni equivalente (verificado: `grep target-arch scripts/` → 0 coincidencias fuera del naming). El binario resultante es de la arquitectura nativa del runner de CI (m4pro.medium, máquina con Apple Silicon). El `.dmg` resultante, etiquetado `universal2.dmg`, es en realidad `arm64`. |
| **Escenario** | Usuario con Mac Intel descarga `tts-sidecar-<ver>-universal2.dmg` y el binario arm64 no arranca. Contradice directamente el criterio de aceptación 3 de `docs/GOAL.md:116` («El instalador de macOS funciona en macOS 12+») y la afirmación «universal2» de README, BUILD y CI. |
| **Propuesta** | Corregir el nombre del artefacto en el pipeline de macOS a la arquitectura del runner real (`arm64.dmg` o `x86_64.dmg`) y actualizar toda la documentación (README, USAGE y CI) para reflejar la realidad del binario distribuido. |
| **Tradeoffs y Justificación** | La opción elegida (Nombres reales de arquitectura) es honesta y evita falsas expectativas de compatibilidad en Mac Intel. Alternativas evaluadas: (A) Compilar dos veces y unificar con `lipo`: exige configurar runners duales en CircleCI y compilar cruzadamente dependencias C (Torch/ONNX), lo cual no es soportado de forma oficial y triplica el tamaño del bundle. Justificación: El tamaño y la complejidad de las librerías dinámicas de ML en macOS hacen que la compilación universal sea inviable; la claridad del artefacto es la solución correcta. |

#### R-16 — Versión mínima de macOS inconsistente

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `Info.plist` declara `LSMinimumSystemVersion` = **10.13** (`build_macos.py:294`), pero `docs/GOAL.md:116` dice «macOS 12+» y el sistema de build usa Python 3.13 (que requiere SDK reciente, no disponible en versiones anteriores a macOS 12). |
| **Escenario** | Usuario en macOS 10.13-11.x puede instalar según el plist, pero el binario (construido con Python 3.13 y toolchain recientes) probablemente no arranque, sin mensaje claro. |
| **Propuesta** | Modificar el archivo `Info.plist` de macOS para declarar `LSMinimumSystemVersion` en `12.0` (Monterey), alineándolo con los requisitos mínimos reales del toolchain de compilación (Python 3.13 y SDKs modernos). |
| **Tradeoffs y Justificación** | La opción elegida (Unificar versión mínima a macOS 12+) evita crasheos silenciosos en versiones obsoletas. Alternativas evaluadas: (A) Intentar compilar contra SDKs heredados para soportar 10.13: requiere degradar la versión de Python y dependencias críticas a versiones sin soporte. Justificación: Mantiene el código moderno e impide errores de ejecución difíciles de diagnosticar en sistemas sin compatibilidad de API real. |

#### R-17 — Instalación Windows es por-máquina y exige admin, sin declararlo

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | El `.iss` fija `PrivilegesRequired=admin`, `{autopf}` (Program Files) y escribe PATH en `HKLM` (`create_installer_windows.py:66, 73, 105`). No hay nota en README ni en la página de descarga sobre este requisito. |
| **Escenario** | Usuario sin derechos de administrador no puede instalar y ninguna documentación lo advierte como requisito. |
| **Propuesta** | Mantener la instalación por máquina en Windows (`HKLM`) para asegurar la disponibilidad del comando globalmente, pero documentar explícitamente en el README y la página de descarga que requiere privilegios de administrador. |
| **Tradeoffs y Justificación** | La opción elegida (Instalación global + documentación de privilegios) asegura la consistencia de PATH para servicios del sistema. Alternativas evaluadas: (A) Cambiar a instalación por usuario (`HKCU`): el ejecutable solo estará disponible para el usuario instalador, rompiendo integraciones con servicios web locales. Justificación: Es la mejor opción para herramientas de tipo 'sidecar' que suelen ser consumidas por daemon u orquestadores en cuentas de servicio. |

#### R-18 — Rendimiento declarado sin peor caso

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `USAGE.md:209-229` cita ~15-30 s de carga y ~12 s T3 / ~6 s S3Gen, pero son cifras de una máquina no especificada. No hay mención de CPU con/sin AVX, RAM mínima, ni del comportamiento en hardware modesto. El modelo es ~0.5 B params + vocoder, lo que implica >2 GB de RAM en uso activo. |
| **Escenario** | Usuario en hardware modesto (CPU sin AVX2, 4 GB de RAM) puede experimentar fallos por OOM o tiempos muy superiores a los declarados. |
| **Propuesta** | Documentar formalmente en `USAGE.md` los requisitos mínimos aproximados (CPU con AVX2, RAM de 8 GB recomendada y 4 GB mínima) e implementar warnings informativos no bloqueantes en `doctor` si no se cumplen. |
| **Tradeoffs y Justificación** | La opción elegida (Warnings en doctor + Documentación) orienta al usuario sin bloquear configuraciones personalizadas válidas. Alternativas evaluadas: (A) Bloquear la provisión en setup si el hardware no es el ideal: restringe el uso en máquinas virtuales o entornos con swap optimizado. Justificación: Evita reportes falsos de bugs de rendimiento sin imponer límites artificiales al software de código abierto. |

---

## Dimensión 6 — Experiencia de Instalación/Desinstalación End-to-End

### Veredicto **[NO LISTO]**

La auditoría por SO de las dos anteriores dejó una base sólida: el instalador Windows muestra página InfoAfter y ofrece ejecutar `setup` con la consola persistente (`create_installer_windows.py:113`), macOS provee scripts `.command` de instalación/desinstalación dentro del `.dmg`, y Linux integra `setup --remove-path` para la reversión del symlink de PATH. La actualización v2-sobre-v1 preserva modelo (caché de usuario) y voces de usuario (user-data-dir) en los tres SO por diseño de rutas.

Sin embargo, los errores de comunicación al usuario (enlaces y nombres de artefactos) contradicen este buen trabajo de fondo.

---

### Hallazgos

#### R-19 — El enlace de descarga del README apunta a un repositorio ajeno

| | |
|---|---|
| **Severidad** | Bloqueante |
| **Evidencia** | `README.md:22` reza: «Descarga el ejecutable para tu plataforma desde [Releases](https://github.com/resemble-ai/tts-sidecar/releases)». Pero el repo real es `github.com/CristianRojas-SoftwareEngineer/tts-sidecar` (`package.json:35`). `grep -c "resemble-ai" README.md USAGE.md` devuelve `1` y `0` respectivamente: el error está **solo en README**, no en USAGE (la guía completa). |
| **Escenario** | Primer paso del usuario nuevo —descargar el binario— lo lleva a un repositorio que no es el del proyecto (probablemente 404, o un proyecto homónimo no relacionado). Bloquea el onboarding completo. |
| **Propuesta** | Modificar el enlace de descarga en `README.md:22` para que apunte a la URL correcta del repositorio en Github. |
| **Tradeoffs y Justificación** | La opción elegida (Corrección directa) es obligatoria y no tiene alternativas lógicas. |

#### R-20 — Los nombres de artefacto del README no coinciden con los reales

| | |
|---|---|
| **Severidad** | Mayor (revisada desde el borrador original) |
| **Evidencia** | `README.md:30-35` instruye `chmod +x tts-sidecar-linux-x86_64` y `./tts-sidecar-linux-x86_64 setup`, y análogamente para macOS con `tts-sidecar-macos-universal2`. Pero los artefactos reales (verificados en `.circleci/config.yml:91, 169` y `scripts/build_linux.py:183`) son `tts-sidecar-<ver>-x86_64.AppImage` y `tts-sidecar-<ver>-universal2.dmg`. **Importante matiz**: USAGE.md (que es la guía completa del usuario, no el README de presentación) sí usa los nombres correctos con `.AppImage` (`USAGE.md:91-92`). El error está **solo en README**, que es la primera lectura del usuario. |
| **Escenario** | El usuario que sigue README no encuentra el archivo que se le dice descargar. La guía de macOS (`chmod +x` sobre un binario suelto) no aplica a un `.dmg` (que debe montarse y el `.app` debe arrastrarse a Aplicaciones). |
| **Propuesta** | Actualizar los comandos de ejemplo en el `README.md` para que utilicen los nombres exactos de los instaladores producidos por el CI (`.AppImage`, `.dmg`, `.exe`), sincronizándolos con el flujo de CircleCI. |
| **Tradeoffs y Justificación** | La opción elegida (Sincronización documental) es la única vía para evitar la fricción inicial de instalación. |

#### R-21 — macOS: fricción sudo del `.command` no anticipada en README

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | El script `Instalar (PATH + modelo).command` generado en `build_macos.py:190-235` invoca `sudo mkdir` y `sudo ln -sf`. README no lo anticipa; USAGE sí lo menciona en §«Primer uso». |
| **Escenario** | Usuario que solo leyó README (siguiendo el flujo de R-19/R-20) se topa con un prompt de contraseña inesperado al ejecutar el script del `.dmg`. |
| **Propuesta** | Incorporar una advertencia breve en la sección de instalación de macOS en el `README.md` sobre el requerimiento del prompt de sudo para la creación del symlink en `/usr/local/bin`. |
| **Tradeoffs y Justificación** | La opción elegida (Advertencia en README) previene el rechazo de usuarios no acostumbrados a peticiones de sudo en scripts locales. |

---

## Dimensión 7 — Calidad y Cobertura de Tests

### Veredicto **[PARCIALMENTE LISTO]**

La cobertura es real y bien dirigida en zonas críticas: validación de rutas de voces, seguridad del daemon, resolución de caché, semántica setup-vs-doctor, construcción del instalador Windows. El CI corre `compileall src/` como red de sintaxis (`config.yml:28-29`). **Conteo verificado: 139 tests** (`pytest tests/ --collect-only -q` → `139 tests collected`).

Sin embargo, los tests se ejecutan únicamente en Linux, y no hay smoke test del binario congelado.

---

### Hallazgos

#### R-22 — Los tests solo corren en Linux; Windows/macOS quedan sin ejercer

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | El job `test` usa el executor `docker cimg/python:3.13` (`config.yml:8-11`) y los jobs de build no ejecutan pytest. Todo el código específico de plataforma se prueba con mocks sobre Linux: `pycaw` (COM, ver `test_audio.py:test_fallo_de_pycaw_degrada_al_fallback`), `winsound` (Windows), la generación del `.iss` (verificada como string en `test_create_installer_windows.py`, no compilada por Inno Setup real), `afplay` (macOS). |
| **Escenario** | Bug en la enumeración COM de pycaw o en el player de winsound no se detecta en CI y llega al usuario Windows. |
| **Propuesta** | Añadir un job en el workflow de CircleCI (`build-windows` o uno dedicado de `test-windows`) que ejecute la suite de pruebas unitarias sobre el executor de Windows `win/server-2022`. |
| **Tradeoffs y Justificación** | La opción elegida (Job Windows de test en CI) detecta regresiones específicas en APIs de Windows (Winsound/Pycaw) de forma automática. Alternativas evaluadas: (A) Mantener solo mocks en Linux: ahorra créditos de CI pero incrementa el riesgo de introducir fallas silenciosas en la plataforma principal de los usuarios. Justificación: La paridad de audio exige validación real sobre la plataforma; el coste de CI se compensa con la fiabilidad. |

#### R-23 — Sin smoke test del binario congelado en CI

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | Los jobs compilan y hacen `store_artifacts` pero nunca ejecutan el ejecutable resultante. `docs/BUILD.md:114-127` («Verificación post-build») lista los comandos como **manuales**, no automatizados. |
| **Escenario** | Problema de empaquetado (metadata faltante, `--collect-all` incompleto, data-files ausentes, o `pkg_resources` mock no instalado) produce un binario que arranca con `ImportError` o falla con un `FileNotFoundError` al primer comando, y CI lo publica igualmente como artefacto «verde». |
| **Propuesta** | Introducir una etapa de validación automática post-compilación en los jobs de CI que ejecute el comando `tts-sidecar version` (o similar que no cargue el modelo) sobre el ejecutable congelado, verificando código de salida 0. |
| **Tradeoffs y Justificación** | La opción elegida (Smoke test en CI) previene la publicación de binarios congelados rotos (ej: imports perezosos ausentes). Alternativas evaluadas: (A) Verificación manual antes del release: propensa a omisiones humanas y no protege los builds continuos de desarrollo. Justificación: Es la medida de protección más barata en tiempo de CI con el mayor retorno en fiabilidad del empaquetado. |

#### R-24 — `build_linux.py` y `build_macos.py` sin tests; ramas de fallo de build sin cobertura

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | Solo `build_utils.py` y `create_installer_windows.py` tienen tests. La construcción del AppDir, el AppRun, la conversión a `.app`, y la generación del `.dmg` no se ejercen en tests. |
| **Propuesta** | Refactorizar la lógica de templates de scripts (`build_linux.py` y `build_macos.py`) en funciones modulares testeables y añadir pruebas de cadenas en pytest, delegando la compilación del empaque a los smoke tests. |
| **Tradeoffs y Justificación** | La opción elegida (Pruebas unitarias de templates + Smoke tests) cubre la lógica de generación sin la complejidad de simular empaquetadores del sistema (como `appimagetool` o `create-dmg`). Alternativas evaluadas: (A) Mockear el entorno de build completo: requiere un esfuerzo de ingeniería excesivo y frágil. Justificación: Valida las expresiones lógicas del script (donde ocurren los bugs) de manera rápida y mantenible. |

#### R-25 — Conteo de tests documentado desfasado

| | |
|---|---|
| **Severidad** | Menor (revisada — el conteo real es 139) |
| **Evidencia** | `docs/GOAL.md:140` dice «95/95» y `docs/GOAL.md:156` dice «95 tests». `CLAUDE.md:197` dice «95 tests». **Conteo real verificado en este repo: `pytest tests/ --collect-only -q` → `139 tests collected`**. |
| **Propuesta** | Actualizar las referencias de conteo de tests en `CLAUDE.md` y `docs/GOAL.md` al valor exacto de `139` pruebas. |
| **Tradeoffs y Justificación** | La opción elegida (Corrección documental) es la única alternativa para mantener la credibilidad técnica de los documentos. |

---

## Dimensión 8 — Documentación como Producto

### Veredicto **[PARCIALMENTE LISTO]**

La documentación de usuario es notablemente completa: USAGE.md recorre cada comando con ejemplos, documenta problemas comunes (binarios sin firmar, host sin audio, voz en uso), y la tabla de diferencias por SO es honesta. BUILD.md documenta la política de dependencias y confiesa la limitación de firma/notarización (§3). GOAL.md marca con honestidad los criterios pendientes de validación end-to-end.

Sin embargo, la gobernanza de release está ausente y hay inexactitudes en detalles visibles.

---

### Hallazgos

#### R-26 — Vacío total de gobernanza de release

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | Búsqueda exhaustiva: no existen `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`, plantilla de reporte de bugs, código de conducta, política de versionado ni canal de soporte declarado. El repo no tiene `.github/` con issue templates. |
| **Escenario** | Usuario que encuentra un bug no sabe dónde reportarlo ni bajo qué expectativa de tiempo de respuesta. Contribuidor no tiene guía de contribución. No hay historial de cambios para un primer release público, lo que dificulta a los adoptadores tempranos evaluar la velocidad de evolución del proyecto. |
| **Propuesta** | Crear archivos mínimos de gobernanza del proyecto (`CHANGELOG.md` en formato Keep a Changelog, `CONTRIBUTING.md` para guiar aportes, y `SECURITY.md` para reportar fallas) en la raíz del repositorio. |
| **Tradeoffs y Justificación** | La opción elegida (Gobernanza mínima) es esencial para la distribución abierta del software. Alternativas evaluadas: (A) Sin gobernanza: deja al proyecto expuesto a reportes desordenados y reduce la confianza de los adoptadores tempranos. Justificación: Establece las bases éticas y de soporte necesarias para una herramienta local de IA. |

#### R-27 — La afirmación «diagnósticos a stderr» de USAGE es incorrecta

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `USAGE.md:479-481` reza: «Contrato de salida estable: los datos van a stdout y los diagnósticos y errores a stderr, siempre en UTF-8; código de salida 0 en éxito y distinto de 0 en error». La realidad (ver R-05) es que `timing.log()` y `timed_command` usan stdout. |
| **Propuesta** | Actualizar el texto en `USAGE.md` para reflejar el contrato de salida correcto (los diagnósticos van a stderr y solo los datos estables a stdout) tras el cierre de R-05. |
| **Tradeoffs y Justificación** | La opción elegida (Sincronización de USAGE.md) es obligatoria para la coherencia de la documentación técnica. |

#### R-28 — Inexactitud del ejemplo de salida de `doctor`

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `USAGE.md:154` muestra `Python: 3.11.x ...` mientras el proyecto exige Python 3.13+ (`pyproject.toml:9`, `docs/BUILD.md:9`). |
| **Propuesta** | Reemplazar el ejemplo de salida del comando `doctor` en `USAGE.md` con un bloque que muestre Python 3.13 en consonancia con los requisitos reales. |
| **Tradeoffs y Justificación** | La opción elegida (Corrección cosmética) elimina inconsistencias que restan credibilidad a la documentación oficial. |

#### R-29 — README describe el modelo como «MIT» sin matiz de verificación

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | `README.md:4-7` y el diagrama de arquitectura mencionan «Chatterbox Multilingual V3 (MIT)». La licencia efectiva de los pesos en HuggingFace no está verificada desde el repo. |
| **Propuesta** | Especificar explícitamente en el README que la licencia del proyecto es GPLv3 y que la licencia 'MIT' aplica exclusivamente a los pesos del modelo de Chatterbox y ciertas dependencias empaquetadas. |
| **Tradeoffs y Justificación** | La opción elegida (Aclaración de licencias) evita confusiones comunes entre la licencia de código copyleft y la de los modelos de pesos permisivos. |

---

## Dimensión 9 — Licenciamiento y Cumplimiento

### Veredicto **[NO LISTO]**

La estructura básica de cumplimiento GPLv3 está: `LICENSE` presente, `pyproject.toml` y `package.json` declaran `GPL-3.0-or-later`, `copy_license_files` (`build_utils.py:259-275`) empaqueta `LICENSE` + `THIRD-PARTY-LICENSES.md` dentro de cada artefacto, el instalador Windows muestra la GPL como paso de aceptación (`create_installer_windows.py:81-82`), y THIRD-PARTY-LICENSES documenta la excepción del bootloader de PyInstaller. CLAUDE.md alerta correctamente de no confundir la licencia del proyecto con la del modelo.

Sin embargo, hay tres brechas materiales: la ausencia de aviso de uso responsable ante la combinación watermark-bypass + clonación de voz, la omisión de libsndfile (LGPL), y la inexactitud general de THIRD-PARTY-LICENSES.

---

### Hallazgos

#### R-30 — Ausencia total de aviso de uso responsable

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `engine.py:272-275` anula `apply_watermark` con un `noop_watermark`. La documentación del engine (`engine.py:11-13`) lo presenta solo como optimización de velocidad. Combinado con clonación de voz arbitraria (mediante `voice add`), el release público distribuye una herramienta que genera voz clonada **sin marca de agua**, sin ninguna nota de uso aceptable, sin advertencia ética, sin información de contacto para reportes de abuso. |
| **Escenario** | Riesgo reputacional/legal directo al publicar. Un actor malicioso puede usar la herramienta para generar deepfakes de voz sin ninguna señal detectable. La ausencia de advertencias no exime legalmente, pero sí establece un estándar de diligencia debida. |
| **Propuesta** | Añadir una sección prominente titulada «Uso Ético y Responsable» en el `README.md` y en `USAGE.md` con pautas claras sobre no suplantar identidades de voz sin consentimiento explícito. |
| **Tradeoffs y Justificación** | La opción elegida (Aviso destacado de uso ético) mitiga el riesgo legal y reputacional de la clonación de voz. Alternativas evaluadas: (A) Impedir técnicamente el bypass del watermark: fácilmente sorteable en código abierto. Justificación: Un aviso ético claro es el estándar adoptado por la industria de IA de código abierto para promover la diligencia debida. |

#### R-31 — Dependencia LGPL (libsndfile) no declarada

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `librosa` y `soundfile` enlazan dinámicamente con **libsndfile** (LGPL-2.1+). PyInstaller, al empaquetar las dependencias, lleva libsndfile dentro del bundle. `THIRD-PARTY-LICENSES.md` no menciona libsndfile ni la LGPL en ninguna sección. |
| **Escenario** | LGPL sobre binarios distribuidos exige, en general, la posibilidad de re-enlace. La GPLv3 del proyecto es compatible con LGPL, pero la LGPL **debe declararse** y, en la mayoría de interpretaciones, las obligaciones de re-enlace deben satisfacerse o documentarse como no aplicables. La omisión es un incumplimiento menor pero real. |
| **Propuesta** | Registrar explícitamente la dependencia LGPL de `libsndfile` en `THIRD-PARTY-LICENSES.md`, indicando que se enlaza dinámicamente y proveyendo enlaces a su código fuente original. |
| **Tradeoffs y Justificación** | La opción elegida (Declaración estricta de LGPL) cumple con los términos de redistribución de la licencia sin imponer re-enlazado complejo en el binario estático de PyInstaller. Justificación: Garantiza el cumplimiento de la licencia LGPL en sistemas que empaquetan libremente. |

#### R-32 — THIRD-PARTY-LICENSES inexacto e incompleto

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | `THIRD-PARTY-LICENSES.md:32` lista `simpleaudio` (MIT) y la línea 133 lista `pyalsaaudio` (PSF-2.0) — pero **ninguno está en `requirements.txt` ni en `pyproject.toml`**. El proyecto usa `sounddevice` como dependencia de audio, no `simpleaudio` ni `pyalsaaudio`. A la vez, omite transitivas que PyInstaller sí empaqueta: `certifi`, `soundfile`, `huggingface_hub` (Apache 2.0), `urllib3`, `idna`, `charset-normalizer`, `click`, `h11`, `anyio`, `starlette`-deps, `numba/llvmlite`, etc. |
| **Escenario** | Atribución incorrecta (lista paquetes no usados) e incompleta (omite paquetes sí usados) en un artefacto público. Una auditoría de cumplimiento por un abogado o por un proyecto downstream que verifique licencias detectará las inconsistencias. |
| **Propuesta** | Configurar una tarea automatizada en el pipeline que genere `THIRD-PARTY-LICENSES.md` a partir de `pip-licenses` en cada build, manteniendo el archivo de atribución siempre actualizado. |
| **Tradeoffs y Justificación** | La opción elegida (Automatización de atribución) elimina el error humano en la declaración de licencias. Alternativas evaluadas: (A) Actualización manual: propensa a omitir dependencias transitivas y a incluir paquetes obsoletos. Justificación: Asegura la exactitud legal y la reproducibilidad de la atribución sin coste manual de mantenimiento. |

#### R-33 — Licencia efectiva de los pesos del modelo no verificada

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | Todo el material (`README.md:4`, `THIRD-PARTY-LICENSES.md:28`) afirma MIT para el modelo `es-mx-latam`. Pero la licencia del repo `ResembleAI/Chatterbox-Multilingual-es-mx-latam` en HuggingFace no se verifica desde el repo. Adicionalmente, el bypass del watermark (`engine.py:272-275`) podría contravenir los términos de uso del modelo, si especifican que la marca de agua debe preservarse. |
| **Escenario** | Si los pesos son efectivamente MIT, la situación es clara. Si son otra licencia (CC-BY-NC, por ejemplo), hay incumplimiento en el release. Si los términos de uso prohíben el bypass, el diseño actual del engine los viola. |
| **Propuesta** | Verificar la licencia efectiva en Hugging Face del language pack y documentar detalladamente el link de su licencia original en `THIRD-PARTY-LICENSES.md`. |
| **Tradeoffs y Justificación** | La opción elegida (Verificación y enlace) da seguridad jurídica a los adoptadores comerciales de la herramienta. |

#### R-34 — Sin oferta de código fuente explícita en el artefacto

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | La GPLv3 §6 exige acompañar el binario de la fuente correspondiente o una oferta escrita de la fuente. La distribución via Releases del mismo repo en GitHub lo satisface de facto (el código fuente está disponible en la misma URL que el binario), pero ningún archivo del bundle apunta explícitamente a la fuente. |
| **Propuesta** | Incluir el enlace al repositorio de código fuente en la InfoAfter del instalador Windows, satisfaciendo la obligación de oferta de código de la GPLv3. |
| **Tradeoffs y Justificación** | La opción elegida (Oferta en instalador) es la vía más sencilla y robusta para cumplir con las condiciones de la licencia GPLv3. |

---

## Dimensión 10 — Cadena de Suministro y CI

### Veredicto **[PARCIALMENTE LISTO]**

El tooling de build está rigurosamente pineado: `PYINSTALLER_PIN=6.21.0`, `INNOSETUP_PIN=6.3.3` (`build_utils.py:44-45`), y el tooling del AppImage por **URL + SHA-256** con verificación en `fetch_pinned_asset` (`build_utils.py:134-172`). El CI espeja esos pines (Python 3.13.14, pyinstaller 6.21.0, innosetup 6.3.3 en `config.yml:43, 50, 51`). Las descargas externas verificadas son una fortaleza real de supply-chain.

Sin embargo, las dependencias de runtime **no** están pineadas, y el job de macOS no fija la versión de Python.

---

### Hallazgos

#### R-35 — Las dependencias de runtime NO están pineadas

| | |
|---|---|
| **Severidad** | Bloqueante |
| **Evidencia** | `requirements.txt:11-24` y `pyproject.toml:15-24` usan exclusivamente `>=` para todas las dependencias de runtime (`chatterbox-tts>=0.3.0`, `sounddevice>=0.4.0`, `requests>=2.28.0`, `psutil>=5.9.0`, `fastapi>=0.110.0`, `uvicorn[standard]>=0.29.0`, `pydantic>=2.0.0`, `pycaw>=20240210`). No hay lockfile ni hashes. El CI hace `pip install -r requirements.txt` sin `--require-hashes`. |
| **Escenario** | Dos builds en fechas distintas empaquetan versiones diferentes de torch/transformers/chatterbox-tts. Un release de cualquiera de esas puede romper el binario silenciosamente, y —dado que no hay smoke test (R-23)— publicarse como artefacto «verde». Adicionalmente, es el vector de supply-chain por excelencia: una versión comprometida de una transitiva (caso real reciente de `torchtriton`, `ctx-python`, `aiohttp`) entra al binario sin barrera. |
| **Propuesta** | Adoptar `pip-tools` para generar `requirements-lock.txt` con hashes verificados a partir de `pyproject.toml`, y configurar el CI para instalar dependencias con `--require-hashes`. |
| **Tradeoffs y Justificación** | La opción elegida (requirements-lock.txt con hashes de pip-tools) garantiza un build inmutable, reproducible y protegido contra inyecciones de código en dependencias. Alternativas evaluadas: (A) Migrar a Poetry: introduce sobrecarga en el flujo de desarrollo y CI heredado. (B) Pines simples en requirements.txt: no protege contra la manipulación de binarios en el hub de PyPI. Justificación: Mantiene el flujo de CircleCI sencillo pero introduce seguridad estricta a nivel de supply-chain. |

#### R-36 — macOS no pinea la versión de Python

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | Windows (`config.yml:43`: `choco install python313 -y --version=3.13.14`) y Linux (image `cimg/python:3.13`) fijan Python. El job macOS (`config.yml:137-175`) usa el `python3` del runner sin fijarlo: `python3 --version` se imprime, pero no se verifica ni se fuerza una versión. |
| **Escenario** | El intérprete embebido en el `.app` depende de la versión de Python que traiga el runner de macOS en cada momento, comprometiendo reproducibilidad y la coherencia del `requires-python>=3.13`. Si CircleCI actualiza el runner, el binario resultante cambia silenciosamente. |
| **Propuesta** | Fijar e instalar de forma explícita Python 3.13 en el job de macOS de CircleCI utilizando `pyenv` para garantizar que la compilación es 100% reproducible e independiente de las actualizaciones del runner. |
| **Tradeoffs y Justificación** | La opción elegida (Fijar Python vía Pyenv en macOS) garantiza la consistencia del runtime embebido. Alternativas evaluadas: (A) Usar el Python del sistema: introduce variabilidad silenciosa si CircleCI actualiza la imagen base. Justificación: Asegura la inmutabilidad absoluta del entorno de compilación de releases. |

#### R-37 — Sin validación post-build automatizada (reitera R-23)

| | |
|---|---|
| **Severidad** | Mayor |
| **Evidencia** | El pipeline compila y publica; no ejecuta el artefacto (ver R-23). |
| **Propuesta** | Aplicar R-23 en todos los jobs de build. |
| **Tradeoffs** | Ver análisis de R-23. |

#### R-38 — Artefactos sin firma de código

| | |
|---|---|
| **Severidad** | Menor |
| **Evidencia** | Limitación conocida y documentada en `docs/BUILD.md:147-154` y `USAGE.md:566-583` (sección «El sistema bloquea el primer arranque»). |
| **Propuesta** | Incorporar documentación detallada y enlaces en el README sobre SmartScreen (Windows) y Gatekeeper (macOS) para guiar al usuario sobre cómo permitir la ejecución de binarios auto-firmados. |
| **Tradeoffs y Justificación** | La opción elegida (Mitigación documental) es la única viable para un proyecto de código abierto sin financiación para certificados anuales de Apple/Microsoft. Justificación: Transparencia total ante el usuario sobre la ausencia de firma. |

---

## Resumen Ejecutivo y Gate de Release

### Tabla-Resumen de Hallazgos por Severidad

| ID | Dim | Sev | Resumen |
|----|-----|-----|---------|
| **R-10** | 4 | **Bloqueante** | Caché hardcodeada ignora `HF_HOME`/`HF_HUB_CACHE` → bucle «no descargado» |
| **R-15** | 5 | **Bloqueante** | macOS no genera universal2 real; artefacto mal etiquetado |
| **R-19** | 6 | **Bloqueante** | Enlace de descarga del README apunta a repo ajeno (resemble-ai) |
| **R-35** | 10 | **Bloqueante** | Dependencias de runtime sin pinear → build no reproducible + vector supply-chain |
| R-01 | 1 | Mayor | `voice add` descarga el modelo saltándose el gate de `setup` |
| R-02 | 1 | Mayor | Ctrl+C en síntesis → traceback en vez de cierre limpio (código 130) |
| R-05 | 2 | Mayor | Diagnósticos a stdout, no stderr: contrato programático falso |
| R-06 | 2 | Mayor | Códigos de salida sin granularidad (20 sys.exit(1)) |
| R-08 | 3 | Mayor | `--port` medio cableado: stop/status/speak ignoran puerto no-default |
| R-11 | 4 | Mayor | Sin desaprovisionamiento de modelo ni datos de usuario |
| R-12 | 4 | Mayor | `ve.safetensors` no verificado → fuga en «100% offline» |
| R-16 | 5 | Mayor | Versión mínima de macOS inconsistente (10.13 vs 12+) |
| R-20 | 6 | Mayor | Nombres de artefacto del README no coinciden con los reales |
| R-22 | 7 | Mayor | Tests solo en Linux; Windows/macOS sin ejercer |
| R-23 | 7 | Mayor | Sin smoke test del binario congelado en CI |
| R-26 | 8 | Mayor | Vacío de gobernanza: sin CHANGELOG/CONTRIBUTING/SECURITY/soporte |
| R-27 | 8 | Mayor | USAGE repite el contrato stderr incorrecto |
| R-30 | 9 | Mayor | Sin aviso de uso responsable (watermark bypass + clonación) |
| R-31 | 9 | Mayor | libsndfile (LGPL) empaquetado y no declarado |
| R-32 | 9 | Mayor | THIRD-PARTY inexacto e incompleto |
| R-33 | 9 | Mayor | Licencia de pesos del modelo no verificada |
| R-36 | 10 | Mayor | macOS no pinea Python |
| R-37 | 10 | Mayor | Sin validación post-build automatizada (alias de R-23) |
| R-03 | 1 | Menor | Texto largo truncado en silencio (sin warning) |
| R-04 | 1 | Menor | Caché truncada pasa el chequeo de existencia |
| R-07 | 2 | Menor | Esquema JSON no versionado ni documentado |
| R-09 | 3 | Menor | `/shutdown` sin auth; superficie local no documentada |
| R-13 | 4 | Menor | Sin mecanismo de actualización del modelo |
| R-14 | 4 | Menor | Sin pre-chequeo de espacio en disco |
| R-17 | 5 | Menor | Windows exige admin sin declararlo |
| R-18 | 5 | Menor | Rendimiento declarado sin peor caso (CPU/AVX/RAM) |
| R-21 | 6 | Menor | macOS: fricción sudo del `.command` no anticipada en README |
| R-24 | 7 | Menor | build_linux/macos sin tests |
| R-25 | 7 | Menor | Conteo de tests documentado desfasado (real: 139) |
| R-28 | 8 | Menor | Ejemplo `doctor` muestra Python 3.11 (exige 3.13) |
| R-29 | 8 | Menor | «Modelo MIT» sin matiz de verificación |
| R-34 | 9 | Menor | Sin oferta de fuente explícita en el artefacto |
| R-38 | 10 | Menor | Artefactos sin firma (mitigación solo documental) |

**Totales:** 4 Bloqueantes · 23 Mayores · 15 Menores

> **Nota sobre la revisión:** la revisión adversarial-constructiva del borrador original detectó (a) erratas y mezclas de idioma que fueron corregidas, (b) referencias de línea imprecisas que se verificaron, (c) el conteo real de tests (139, no 95 ni 148), y (d) matices sobre R-19, R-20 y R-25 que se incorporaron explícitamente en sus descripciones. El total de hallazgos pasó de 18 mayores a 23 mayores tras la revisión, porque se desglosaron hallazgos solapados (R-23 y R-37) y se precisaron otros con evidencia adicional. Una **segunda pasada de revisión** corrigió inconsistencias internas remanentes (conteo de tests 148 vs. 139 dentro del propio documento, conteo de `sys.exit(1)` 22 vs. 20 en la tabla-resumen, una severidad en inglés) y refinó las propuestas de R-01, R-02, R-06, R-08 y R-10 con detalles de implementación verificados contra el código (p. ej., el parámetro `precompute` ya existente en `add_voice`, y que `DaemonManager` ya acepta puerto).

---

### Gate de Release

Antes de publicar un primer release público, deben cerrarse los **4 bloqueantes** y, como mínimo, los **mayores** que tocan al usuario en su primer contacto y a la corrección legal:

#### 1. Onboarding roto (bloqueantes directos al primer uso)
- **R-19**: Corregir enlace de descarga en `README.md:22` → URL correcta del proyecto.
- **R-20**: Actualizar nombres de artefactos en README para reflejar la realidad (y opcionalmente en USAGE para que coincidan exactamente).
- **R-10**: Implementar soporte para `HF_HOME`/`HF_HUB_CACHE` en `hub_cache_path()`.

#### 2. Corrección del artefacto y reproducibilidad (confianza en lo que se entrega)
- **R-15**: Corregir el naming del artefacto macOS a la arquitectura real (`arm64.dmg` o `x86_64.dmg`) o implementar lipo con dos runners.
- **R-35**: Generar `requirements-lock.txt` con pins exactos y hashes; usar `--require-hashes` en CI.
- **R-36**: Fijar Python 3.13 explícitamente en el job macOS de CI.
- **R-23** + **R-37**: Añadir smoke test del binario congelado en CI (`tts-sidecar version` con exit 0).

#### 3. Contrato programático (razón de ser del producto)
- **R-05** + **R-27**: Redirigir output de progreso a stderr y actualizar documentación (USAGE, docstring cli.py, README).
- **R-06**: Añadir granularidad de códigos de salida (recomendado vía campo `error_code` en JSON para retrocompatibilidad).
- **R-08**: Completar implementación de `--port` en todos los subcomandos de daemon (start/stop/restart/status) y/o usar variable de entorno `TTS_SIDECAR_DAEMON_PORT`.

#### 4. Fiabilidad del flujo central
- **R-01**: Añadir check de modelo cacheado en `cmd_voice_add` (paralelo a `cmd_speak` y `cmd_daemon start`).
- **R-02**: Manejar `KeyboardInterrupt` con `try/except` en `main()` y `sys.exit(130)`.
- **R-12**: Verificar `ve.safetensors` en la caché del modelo base en `is_model_cached` y/o descargarlo explícitamente en `setup`.
- **R-11**: Crear comando `cleanup` con flags `--model` / `--voices` / `--all` / `--dry-run` para desaprovisionamiento.

#### 5. Cumplimiento y responsabilidad legal
- **R-30**: Añadir sección «Uso Responsable» en README y USAGE.
- **R-31** + **R-32**: Regenerar `THIRD-PARTY-LICENSES.md` con `pip-licenses` (incluyendo libsndfile LGPL).
- **R-33**: Verificar la licencia y los términos de uso del modelo `es-mx-latam` en HuggingFace.

#### 6. Gobernanza mínima para release público
- **R-26**: Crear `CHANGELOG.md`, `CONTRIBUTING.md`, `SECURITY.md`. Considerar `CODE_OF_CONDUCT.md` y plantillas de Issues.

#### 7. Mejoras paralelas recomendadas (mayores adicionales)
- **R-16**: Unificar `LSMinimumSystemVersion` a 12.0 en `Info.plist`.
- **R-22**: Añadir job de tests en Windows en CI.

---

### Recomendación Global de Madurez

**NO LISTO** para un primer release público.

El proyecto está **ingenierilmente maduro en su núcleo**: la lógica de voces, la seguridad del daemon, la resolución de caché, la política de dependencias de build pineadas por SHA-256, y la documentación de usuario reflejan un trabajo cuidadoso. Las dos auditorías previas de equivalencia de UX cerraron la mayoría de las fricciones de plataforma.

Sin embargo, la auditoría de las capas no cubiertas antes —y la revisión posterior del propio reporte— revelan una brecha sistemática entre **lo que el repo construye** y **lo que el usuario/integrador realmente recibe**:

- Los **4 bloqueantes** son fallos que un usuario nuevo encuentra en los primeros minutos: no puede descargar (R-19), el binario de macOS no es lo que dice ser (R-15), el modelo «no se descarga» en entornos con `HF_HOME` (R-10), y nadie puede reproducir el build (R-35).
- El **contrato programático** —la razón de existir del sidecar— tiene su afirmación central (stderr) desmentida por el código, carece de granularidad de códigos de salida, y rompe `--port` para la mitad de los subcomandos de daemon.
- El frente de **cumplimiento** (watermark sin aviso, LGPL no declarada, atribuciones inexactas, licencia del modelo sin verificar) expone al proyecto a riesgo legal y reputacional que un release público materializa de inmediato.
- La **revisión adversarial** del propio reporte descubrió erratas y mezclas de idioma que, aunque cosméticas, erosionan la confianza en un documento de gobernanza.

La distancia hasta «listo» es de **cierre de gate**, no de rediseño. Casi todos los hallazgos son acotados y localizados. Con los bloqueantes y los mayores del gate resueltos —y un smoke test del binario congelado en CI que cierre el lazo entre «compila» y «funciona»— el proyecto pasaría a **listo-con-reservas** (las reservas siendo la firma de código y la validación manual por SO que solo hardware real puede dar).

> **Actualización 2026-07-03 — gate cerrado.** El gate de release se ejecutó por
> completo (T1–T16). Los **4 bloqueantes**, los **23 mayores** y 4 menores quedaron
> resueltos (ver «Estado de remediación del gate» al inicio del documento); restan 11
> menores de pulido. Con ello el proyecto pasa de **NO LISTO** a
> **LISTO-CON-RESERVAS**: las reservas residuales son la **firma/notarización de
> código** (R-38) y la **validación manual end-to-end en hardware real por SO**
> (instaladores, `setup`, síntesis), que el CI no puede cubrir. El veredicto «NO LISTO»
> de arriba refleja el estado en el momento de la auditoría y se conserva como registro.

---

*Auditoría realizada el 2026-07-02. Primera revisión adversarial-constructiva aplicada el mismo día; segunda pasada de verificación el 2026-07-03. Código base: commit `a0a77cc`. Conteo de tests verificado: 139 (`pytest tests/ --collect-only -q`).*