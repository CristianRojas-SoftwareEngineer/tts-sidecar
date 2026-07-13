# Revisión: Auditoría sistémica de calidad y deuda técnica

## Resumen ejecutivo

Auditoría sistémica de **todo el repositorio TTS Sidecar** bajo la lente **calidad y deuda técnica** (perfil **perfectivo**: sin cambio funcional esperado, métrica de mantenibilidad). La investigación se delegó en 6 sub-agentes de exploración en paralelo, cada uno sobre una lonja concreta del código fuente, con evidencia `file:line` verificada.

Veredicto global: el proyecto está **maduro y disciplinado** (336 tests, semáforo de admisión en el daemon, lock de arranque atómico, sandbox de audio con `realpath`). La deuda es **moderada y localizada**, no estructural. No hay hallazgos S4 (críticos). Los riesgos más relevantes son de **observabilidad** (excepciones silenciadas en rutas críticas), **acoplamiento del daemon al engine** (globals, sin inyección de dependencias) y **brechas de cobertura en la funcionalidad central del engine y en el límite de seguridad del sandbox**.

Conteo por severidad: **0 S4, 2 S3, 18 S2, 18 S1, 5 S0** (43 hallazgos consolidados). Dos afirmaciones de alta severidad propuestas por los sub-agentes fueron **descartadas como falso positivo** tras verificación directa; además, la presunta discrepancia de conteo de tests no es defecto (ver «Nota de verificación» y «Provenance»). El conteo real es 350 tests recolectados por pytest (336 funciones `def test_`); `CLAUDE.md` (~350) y `GOAL.md` (336/336) son coherentes.

### Índice de hallazgos

| ID | Título | Severidad | Prioridad | Área/plataforma | Decisión requerida | Estado |
|----|--------|-----------|-----------|-----------------|--------------------|--------|
| S3-01 | Funcionalidad central del engine sin tests (gestión de voces, carga de modelo, conditionals) | S3 — Alto | P1 | engine / Testing | No | Resuelto |
| S3-02 | Límite de seguridad del sandbox del daemon sin tests directos | S3 — Alto | P1 | daemon / Testing-Security | No | Resuelto |
| S2-01 | Acoplamiento del servidor al engine vía globals, sin DI | S2 — Medio | P2 | daemon / Arquitectura | Sí | Pendiente |
| S2-02 | Excepciones silenciadas sin logging en rutas críticas | S2 — Medio | P1 | engine/audio/timing/daemon / Fiabilidad | Sí | Pendiente |
| S2-03 | Modelo no liberado en shutdown del daemon | S2 — Medio | P2 | daemon / Fiabilidad | No | Resuelto |
| S2-04 | Worker del daemon no cancelable al desconectar el cliente | S2 — Medio | P2 | daemon / Escalabilidad | Sí | Pendiente |
| S2-05 | `ipc.py` no reutiliza los modelos de `protocol.py` | S2 — Medio | P2 | daemon / Calidad de código | Sí | Pendiente |
| S2-06 | Lógica de dependencias duplicada entre build scripts | S2 — Medio | P1 | build / Mantenibilidad | No | Resuelto |
| S2-07 | Pines de versión duplicados en CI y scripts | S2 — Medio | P1 | CI / Mantenibilidad-DevOps | Sí | Pendiente |
| S2-08 | Smoke tests duplicados en CI | S2 — Medio | P2 | CI / DevOps | No | Resuelto |
| S2-09 | Lockfiles omiten herramienta de build (PyInstaller) | S2 — Medio | P1 | build / Dependencias | No | Resuelto |
| S2-10 | God object `ChatterboxEngine` | S2 — Medio | P2 | engine / Mantenibilidad | Sí | En progreso |
| S2-11 | Estado global `_active_spinner` en `timing.py` | S2 — Medio | P2 | timing / Mantenibilidad | Sí | Pendiente |
| S2-12 | `bootstrap` usa `warnings.filterwarnings("ignore")` global | S2 — Medio | P2 | bootstrap / Observabilidad | Sí | Pendiente |
| S2-13 | Creación de directorios duplicada `_emit_audio` vs `_save_wav` | S2 — Medio | P2 | cli/engine / Mantenibilidad | Sí | Pendiente |
| S2-14 | Orden de imports de `cli` acoplado a bootstrap + entry points duplicados | S2 — Medio | P1 | cli/bin / Mantenibilidad | Sí | Pendiente |
| S2-15 | `voice add`/`remove` exigen modelo en caché innecesariamente | S2 — Medio | P2 | cli / Diseño | Sí | Pendiente |
| S2-16 | Cobertura: `daemon run` (auto-restart, señales) y `setup`/`uninstall` subtesteados | S2 — Medio | P1 | daemon/cli / Testing | No | Resuelto |
| S2-17 | Cobertura: reproducción de audio por plataforma (macOS/Windows) sin tests | S2 — Medio | P2 | audio / Testing | No | Resuelto |
| S2-18 | Cobertura: `purge_incomplete_downloads` sin test | S2 — Medio | P2 | model_cache / Testing | No | Resuelto |
| S1-01 | Logging redundante en `_emit_audio` | S1 — Bajo | P3 | cli / Calidad | No | Pendiente |
| S1-02 | Filtro de warning redundante en `audio.py` | S1 — Bajo | P3 | audio / Calidad | No | Pendiente |
| S1-03 | `import subprocess` bajo guarda de plataforma | S1 — Bajo | P3 | cli / Calidad | No | Resuelto |
| S1-04 | `_paths_allowed_by_daemon` no valida existencia de archivos | S1 — Bajo | P3 | cli / Calidad | No | Pendiente |
| S1-05 | `list_voices` es O(n²) | S1 — Bajo | P3 | voices / Calidad | No | Resuelto |
| S1-06 | `__init__.py` declara `__all__ = []` | S1 — Bajo | P3 | package / Calidad | No | Resuelto |
| S1-07 | Valores mágicos sin nombrar | S1 — Bajo | P3 | varios / Calidad | No | Resuelto |
| S1-08 | `_install_pkg_resources_mock` (edge cases) sin test | S1 — Bajo | P2 | bootstrap / Testing | No | Resuelto |
| S1-09 | Decorador `timed()` sin test | S1 — Bajo | P2 | timing / Testing | No | Resuelto |
| S1-10 | `protocol.py`: edge cases (longitudes, unicode) sin test | S1 — Bajo | P2 | daemon / Testing | No | Resuelto |
| S1-11 | Fixtures muertas en `conftest.py` | S1 — Bajo | P2 | tests / Mantenibilidad | No | Resuelto |
| S1-12 | Patrones frágiles en tests (symlinks Windows, tempdir, `time.sleep`) | S1 — Bajo | P3 | tests / Testing | No | Resuelto |
| S1-13 | `render_cask.py` usa `.format()` sin validación de campos | S1 — Bajo | P3 | build / Calidad | No | Resuelto |
| S1-14 | `create_installer_windows.py`: rutas ISCC hardcodeadas | S1 — Bajo | P3 | build / Mantenibilidad | No | Resuelto |
| S1-15 | `clean_build.py` asume ubicación relativa al repo | S1 — Bajo | P3 | build / Mantenibilidad | No | Resuelto |
| S1-16 | `build_utils.py` importa PIL duplicado en `ensure_ico`/`ensure_icns` | S1 — Bajo | P3 | build / Calidad | No | Resuelto |
| S1-17 | Validación de nombre de voz no previene symlinks dentro del dir permitido | S1 — Bajo | P3 | voices / Seguridad | Sí | Pendiente |
| S1-18 | Deriva documental menor (árbol de CLAUDE.md y ruta de voces en DESIGN.md) | S1 — Bajo | P3 | docs / Documentación | No | Resuelto |
| S0-01 | `bundle_size_mb()` no referenciada externamente | S0 — Informativo | P3 | build / Calidad | No | Resuelto |
| S0-02 | Estrategia de lockfile CPU-only de Linux no documentada | S0 — Informativo | P3 | build / Dependencias | No | Resuelto |
| S0-03 | `pyenv` sin pin de versión (decisión consciente) | S0 — Informativo | P3 | CI / DevOps | No | Pendiente |
| S0-04 | Naming inconsistente de arquitectura en artefactos (aarch64/arm64/x86_64) | S0 — Informativo | P3 | build / Mantenibilidad | No | Pendiente |
| S0-05 | TOCTOU en validación de audio del daemon — verificado ya mitigado | S0 — Informativo | P3 | daemon / Seguridad | No | Resuelto |

## Hallazgos por severidad

### S4 — Críticos

_Ninguno._ No se encontró riesgo inaceptable ni fallo arquitectónico que impida el desarrollo o el release.

### S3 — Altos

#### S3-01 — Funcionalidad central del engine sin tests
- **Categoría**: Testing / Cobertura
- **Área/plataforma**: `src/tts_sidecar/engine.py`
- **Evidencia**: `engine.py:128-870` (clase `ChatterboxEngine` con 15+ métodos). `tests/test_engine_cache.py` y `test_engine_progress.py` cubren caché y progreso, pero los métodos `add_voice`, `list_voices`, `remove_voice`, `resolve_voice`, `_compute_conditionals`, `_load_model` / `_load_es_latam` / `_load_multilingual` no tienen tests directos.
- **Confianza**: Alta
- **Causa**: La síntesis se ejerce mayormente vía el path `speak()` mockeado; la gestión de voces a nivel engine y la carga/precomputación de modelos quedaron sin aislar.
- **Impacto**: Regresiones en la función primaria (clonación de voz, selección de modelo, conditionals) podrían pasar desapercibidas; es la lógica de mayor valor del producto.
- **Corrección(es) propuesta(s)**: Añadir tests unitarios con modelos mockeados para `add_voice`/`list_voices`/`remove_voice`/`resolve_voice` y para el flujo de carga + `_compute_conditionals` (recomendada). Extraer la lógica de voz a un colaborador inyectable para facilitar el mock.
- **Decisión requerida**: No
- **Prioridad**: P1
- **Estado**: Resuelto
- **Re-scoping (S3-01)**: Durante la planificación se constató que la capa `voices.py` **ya estaba cubierta** por `tests/test_voices.py` (registro, resolución usuario→fábrica, listado, sanitización de nombres y colisión case-insensitive). La brecha real de S3-01 era la **capa engine**: `add_voice` (con su rama `precompute`), los delegates `list_voices`/`remove_voice`/`resolve_voice`, `_compute_conditionals` y la carga/precomputación de conditionals. Cerrada por `tests/test_engine_voices.py`, `tests/test_conditionals.py` y `tests/test_model_loader.py`. Como avance parcial de S2-10, se extrajeron `ModelLoader` (`src/tts_sidecar/model_loader.py`) y `ConditionalsPreparer` (`src/tts_sidecar/conditionals.py`) como colaboradores inyectables del engine (ver entrada S2-10).

#### S3-02 — Límite de seguridad del sandbox del daemon sin tests directos
- **Categoría**: Testing / Seguridad
- **Área/plataforma**: `src/tts_sidecar/voices.py`, `src/tts_sidecar/daemon/server.py`
- **Evidencia**: `voices.allowed_audio_dirs()` y `voices.daemon_session_dir()` (usadas en `daemon/server.py:129`) solo se ejercen de forma indirecta en `tests/test_daemon.py`; no había tests que aislaran la frontera (ruta fuera de `allowed_dirs` → rechazo; symlink que apunta fuera → rechazo; `daemon_session_dir` namespaceado bajo `<tempdir>/tts-sidecar`, **sin** aislamiento por PID — la afirmación original "aislado por PID" era inexacta: el código solo namespacea bajo el tempdir, no por PID).
- **Confianza**: Alta
- **Causa**: Los tests de daemon ejercen el sandbox a través del endpoint, no como unidad; los casos de borde de la frontera no estaban enumerados.
- **Impacto**: Una regresión en la frontera de seguridad (que hoy sí contiene escapes vía `realpath`, ver S0-05) quedaría sin detectar; es justo el tipo de defensa que debe tener cobertura explícita.
- **Corrección(es) propuesta(s)**: Tests unitarios directos añadidos en `tests/test_daemon_sandbox.py` (`allowed_audio_dirs`, `daemon_session_dir`, `_validate_audio_path` con matrices dentro/fuera y symlink inward/outward) tras extraer `_validate_audio_path` de `synthesize` (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P1
- **Estado**: Resuelto
- **Re-scoping (S3-02)**: La frontera de seguridad del sandbox ahora está aislada en tests unitarios (`tests/test_daemon_sandbox.py`): `TestAllowedAudioDirs` cubre la composición exacta de `allowed_audio_dirs()` (tres entradas, con el tempdir general excluido) y que `daemon_session_dir()` es `<tempdir>/tts-sidecar` sin PID; `TestValidateAudioPath` cubre `_validate_audio_path` —extraída de `synthesize` a `daemon/server.py`— con rechazo fuera de `allowed_dirs`, rechazo de symlink que escapa, aceptación de symlink inward, retorno del `realpath` canónico, y rechazo por extensión no `.wav`/archivo inexistente o header WAV inválido. Se corrigió además la afirmación del hallazgo original ("aislado por PID") que no correspondía al código. Sin cambio de comportamiento en runtime: `synthesize` delega en `_validate_audio_path` conservando los mismos chequeos y `HTTPException(400)`.

### S2 — Medios

#### S2-01 — Acoplamiento del servidor al engine vía globals, sin DI
- **Categoría**: Arquitectura / Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/daemon/server.py:28-48`
- **Evidencia**: Variables globales `_engine`, `_server`, `_start_time` asignadas por `set_engine()`/`set_server()`/`set_start_time()`; `/synthesize` accede a `_engine` directamente.
- **Confianza**: Alta
- **Causa**: Estado de servidor en globals mutados por funciones externas.
- **Impacto**: Dificulta testabilidad, extensibilidad y desacoplamiento del motor TTS; un motor alternativo exigiría tocar `server.py`.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — elegir el nivel de desacople (contenedor de estado vs. DI completa) y su alcance.
- **Alternativas y trade-offs**:
  - **A) Contenedor `DaemonState` (dataclass) vía `Depends(get_daemon_state)`**. Encapsula `engine`/`server`/`start_time`; `run.py` construye el estado y lo inyecta, eliminando los setters módulo-level.
    - *Pros*: cambio acotado y reversible; elimina los globals mutables; cada test crea su propio `DaemonState` sin ensuciar estado compartido.
    - *Contras*: persiste un punto de wiring en `run.py`; no habilita múltiples engines "gratis" salvo que se generalice; hay que tocar cada endpoint para recibir la dependencia.
  - **B) DI completa con factory `create_app(engine)`**. La app deja de ser un singleton a nivel módulo y se construye con sus dependencias.
    - *Pros*: desacople real; un motor alternativo no toca `server.py`; soporta múltiples instancias; es la opción más robusta a largo plazo.
    - *Contras*: cirugía mayor: afecta el wiring de uvicorn, y **toda la suite que hace `TestClient(server.app)` / importa `server.app`** debe migrar; mayor superficie de regresión.
  - **Trampa del parche barato**: envolver los tres globals en una dataclass pero **seguir mutándola desde `run.py` con funciones módulo-level**. Cambia la forma pero no rompe el acoplamiento: sigue sin poder instanciarse dos veces ni testearse sin estado global.
  - **Relación**: coordinar con **S2-11** (spinner global) y con la propuesta `SynthesisMetrics` del deep-dive (`_synthesis_timing` leído por `server.py` vía globals). Decidir si el alcance cubre solo el engine o también timing/metrics define si esto se cierra una vez o se reabre.

#### S2-02 — Excepciones silenciadas sin logging en rutas críticas
- **Categoría**: Fiabilidad / Mantenibilidad
- **Área/plataforma**: `engine.py:259, 361-363, 80/93/99`; `audio.py:186-205`; `timing.py:184-227`; `daemon/daemon.py:111/268/291/295/308/335/365`; `daemon/run.py:150-151`
- **Evidencia**: Múltiples `except Exception: pass` (sin traza) en callbacks de progreso (`engine.py:259`), shim de tokens (`361-363`), configuración de PyTorch (`80/93/99`), enumeración de dispositivos de audio (`audio.py`), operaciones de stream/spinner (`timing.py`), ciclo de vida del daemon (`daemon.py`) y `serve()` (`run.py:150`).
- **Confianza**: Alta
- **Causa**: Supresión defensiva de errores esperados sin registrar causa.
- **Impacto**: Degradación silenciosa (p. ej. configuración subóptima de PyTorch, pérdida de progreso de tokens, fallos de subsistema de audio) sin diagnóstico; erosiona la observabilidad del path principal.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — fijar la política de logging (niveles, `exc_info`) y, por sitio, decidir qué excepciones deben propagarse en vez de suprimirse.
- **Prioridad**: P1
- **Alternativas y trade-offs**:
  - **A) Política uniforme de logging** (reemplazo mecánico). Cada `except Exception: pass` pasa a `except Exception: logging.debug(..., exc_info=True)` conservando la supresión del control de flujo.
    - *Pros*: esfuerzo mínimo; mejora la observabilidad sin cambiar comportamiento; seguro (no introduce nuevos fallos).
    - *Contras*: **no distingue "error esperado" de "bug"**; puede inundar los logs; no corrige los swallows que en realidad ocultan defectos → es un parche que disfraza la degradación en lugar de eliminarla.
  - **B) Triage por sitio** (tipar + decidir supresión vs. propagación). En cada uno de los ~11 puntos: tipar la excepción realmente esperada y dejar propagar lo inesperado.
    - *Pros*: corrige la raíz; los fallos reales dejan de ser silenciosos; robusto.
    - *Contras*: caro; exige entender cada sitio; **cambia comportamiento** (algo que antes se tragaba ahora puede romper) — deseable, pero necesita tests que cubran cada ruta antes de tocarla.
  - **C) Híbrido (recomendado)**: aplicar la política de logging por defecto en los sitios inocuos (progreso, spinner) y hacer triage con tipado en los críticos (configuración de PyTorch `engine.py:80/93/99`, subsistema de audio `audio.py:186-205`, ciclo de vida del daemon `daemon.py`).
    - *Trade-off*: balancea costo y robustez, pero requiere el criterio humano para clasificar cada sitio.
  - **Trampa del parche barato**: el reemplazo masivo de la opción A aplicado a todo, incluidos los sitios críticos. Añade ruido y "cierra" el hallazgo sin arreglar ni un solo swallow incorrecto.
  - **Qué se necesita del humano**: (1) la política de logging (nivel por defecto, si se incluye `exc_info`); (2) la lista de sitios donde el error debe **propagarse** en vez de registrarse-y-seguir.

#### S2-03 — Modelo no liberado en shutdown del daemon
- **Categoría**: Fiabilidad / Fuga de recursos
- **Área/plataforma**: `src/tts_sidecar/daemon/server.py:246-264`
- **Evidencia**: `/shutdown` solo fija `_server.should_exit = True`; no libera `_engine` ni invoca `torch.cuda.empty_cache()`.
- **Confianza**: Alta
- **Causa**: Falta de hook de limpieza en el apagado graceful.
- **Impacto**: En auto-restart frecuente, la memoria GPU puede no liberarse completamente entre reinicios.
- **Corrección(es) propuesta(s)**: Hook de shutdown que libere referencias al engine y llame `torch.cuda.empty_cache()` (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P2

#### S2-04 — Worker del daemon no cancelable al desconectar el cliente
- **Categoría**: Escalabilidad / Fiabilidad
- **Área/plataforma**: `src/tts_sidecar/daemon/server.py:216-217`
- **Evidencia**: Thread worker creado con `daemon=True`; no hay mecanismo para cancelarlo si el cliente se desconecta.
- **Confianza**: Alta
- **Causa**: Ausencia de evento de cancelación ligado al estado de la conexión.
- **Impacto**: Consumo innecesario de GPU/CPU si el cliente se va a mitad de síntesis.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — elegir el mecanismo de cancelación y su profundidad.
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) Sondear `Request.is_disconnected()` desde el worker** (polling en el bucle de generación).
    - *Pros*: cambio acotado; no toca el núcleo del engine.
    - *Contras*: latencia de cancelación (el engine sigue corriendo hasta el próximo sondeo); consume GPU/CPU mientras tanto; un polling agresivo introduce thrashing.
  - **B) `threading.Event` de cancelación + cancelación cooperativa en el engine** (interrumpir el loop de generación T3/S3Gen).
    - *Pros*: cancelación casi inmediata; libera GPU pronto al irse el cliente.
    - *Contras*: requiere que el engine exponga un punto de cancelación — toca el núcleo de síntesis y el callback stateful (emparentado con S2-10); más invasivo y con superficie de regresión.
  - **C) No cancelar** (status quo).
    - *Pros*: cero cambio.
    - *Contras*: desperdicia GPU/CPU si el cliente se desconecta a mitad; riesgo bajo pero real en uso concurrente.
  - **Trampa del parche barato**: añadir el `Event` pero nunca conectarlo a la desconexión del cliente → queda "implementado" pero inerte; o hacer polling cada milisegundo (thrashing).
  - **Qué se necesita del humano**: (1) mecanismo (polling vs. cooperativo); (2) profundidad — ¿cancelar solo el worker o también interrumpir el engine en medio de la síntesis?

#### S2-05 — `ipc.py` no reutiliza los modelos de `protocol.py`
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/daemon/ipc.py:136-154`
- **Evidencia**: El cliente IPC parsea NDJSON manualmente (`json.loads`, `ev.get("event")`) en lugar de usar `ProgressEvent`/`ResultEvent`/`ErrorEvent` de `protocol.py`.
- **Confianza**: Alta
- **Causa**: Lógica de schema duplicada fuera de los modelos Pydantic ya existentes.
- **Impacto**: Cambios en el contrato exigen tocar dos sitios; riesgo de divergencia.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — decidir si el cliente IPC debe ser estricto o tolerante ante frames sucios.
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) `model_validate_json` estricto** por línea con los modelos de `protocol.py`.
    - *Pros*: una sola fuente de verdad del contrato; validación fuerte de cada frame.
    - *Contras*: pierde la tolerancia actual — hoy `ipc.py:132-134` hace `except ValueError: continue` ante líneas no-JSON; un frame malformado rompería el stream en vez de ignorarse; riesgo de regresión si el server emite algo no modelado.
  - **B) Mantener el parseo manual** (status quo).
    - *Pros*: tolerante a ruido de red/stream.
    - *Contras*: divergencia de schema; doble mantenimiento del contrato.
  - **C) Validadores Pydantic preservando la tolerancia**: `model_validate_json` dentro de `try`, y en `ValidationError` hacer `continue` como hoy.
    - *Pros*: une ambos mundos — validación fuerte cuando el frame es válido, tolerancia cuando no.
    - *Contras*: un poco más de código; hay que decidir si un `progress` inválido se ignora o aborta el stream.
  - **Trampa del parche barato**: cambiar a `model_validate_json` sin el `try/except` — rompe la tolerancia que hoy es intencional ("Línea no-JSON (no debería ocurrir): se ignora sin abortar").
  - **Qué se necesita del humano**: (1) estricto vs. tolerante ante frames sucios; (2) si un `result` inválido debe abortar o caer en `DaemonIPCError`.

#### S2-06 — Lógica de dependencias duplicada entre build scripts
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `scripts/build_windows.py`, `scripts/build_linux.py:92-121,123-137`, `scripts/build_macos.py:36-91`
- **Evidencia**: `check_dependencies` y `ensure_runtime_dependencies` casi idénticas en los tres scripts (verificación de sounddevice, instalación vía lockfile, manejo de timeout).
- **Confianza**: Alta
- **Causa**: Copia manual en lugar de abstracción común.
- **Impacto**: Riesgo de deriva al modificar el comportamiento en una plataforma y no en las otras.
- **Corrección(es) propuesta(s)**: Consolidar en `build_utils.py` con parámetros por plataforma (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P1

#### S2-07 — Pines de versión duplicados en CI y scripts
- **Categoría**: Mantenibilidad / DevOps
- **Área/plataforma**: `scripts/build_utils.py:53` (PyInstaller 6.21.0), `.circleci/config.yml:415,564,670,794`; Python `3.13.14` en `config.yml:115,170,369`; pytest `9.1.1` en `83,170,271`; Inno `6.3.3` en `build_utils.py` + `config.yml`; repo en `render_cask.py:19-22` + `config.yml:23,962,976,982,1037`
- **Evidencia**: Versiones hardcodeadas en múltiples lugares: PyInstaller ×5, Python ×4, pytest ×3, Inno ×2, repo ×5.
- **Confianza**: Alta
- **Causa**: Sin fuente única de verdad para los pines.
- **Impacto**: Una actualización de versión exige N cambios manuales sincronizados; alta probabilidad de desincronización.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — elegir la fuente única de verdad (YAML vs. Python) y su alcance.
- **Prioridad**: P1
- **Alternativas y trade-offs**:
  - **A) Anchors YAML centralizados** en `.circleci/config.yml`.
    - *Pros*: simple, declarativo, visible en el propio CI.
    - *Contras*: solo cubre CI; no sincroniza con `build_utils.py`/`render_cask.py` (que también hardcodean pines, ver evidencia); los scripts fuera de CircleCI quedan fuera.
  - **B) Generar los steps de instalación desde `build_utils.py`** (fuente única en Python).
    - *Pros*: una sola fuente para CI + scripts; elimina los N lugares de divergencia.
    - *Contras*: el CI deja de ser declarativo (los pines viven en código Python); más acoplamiento build↔CI; superficie mayor si `build_utils.py` cambia.
  - **C) Test/lint de consistencia** que falle si los pines divergen (sin cambiar la estructura).
    - *Pros*: no altera el flujo, solo vigila la deriva.
    - *Contras*: no elimina la duplicación, solo la detecta.
  - **Trampa del parche barato**: mover a anchors solo en `config.yml` y olvidar `build_utils.py`/`render_cask.py` → la deriva persiste en los scripts de build.
  - **Qué se necesita del humano**: (1) fuente única = YAML o Python; (2) si el alcance cubre también los scripts fuera de CI.

#### S2-08 — Smoke tests duplicados en CI
- **Categoría**: DevOps
- **Área/plataforma**: `.circleci/config.yml:576-584, 689-694`
- **Evidencia**: Los smoke tests de AppImage x64 y ARM64 son idénticos salvo el path del ejecutable (mismo grep de la voz `default`).
- **Confianza**: Alta
- **Causa**: Paso repetido en lugar de parametrizado.
- **Impacto**: Toda validación nueva debe duplicarse.
- **Corrección(es) propuesta(s)**: Extraer a un command/step reutilizable parametrizado por ruta (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P2

#### S2-09 — Lockfiles omiten herramientas de build
- **Categoría**: Dependencias
- **Área/plataforma**: `requirements-lock.txt`, `requirements-lock-linux-cpu.txt` vs `requirements.txt`
- **Evidencia**: `pyinstaller` (declarado en `requirements.txt` como herramienta de build) **no** aparece en `requirements-lock.txt` ni en `requirements-lock-linux-cpu.txt`; el CI lo instala con `pip` directo. `pillow` **sí** está presente en `requirements-lock.txt` (verified line ~1370, `pillow==12.3.0`); la evidencia original afirmaba erróneamente que tampoco aparecía. La omisión real del lockfile es solo `pyinstaller`.
- **Confianza**: Alta
- **Causa**: Estrategia de lockfile enfocada solo en runtime (PyInstaller es la única herramienta de build que queda fuera).
- **Impacto**: Versión de PyInstaller no reproducible en build; posible desincronización entre entornos.
- **Corrección(es) propuesta(s)**: Añadir `pyinstaller` al lockfile o crear un lockfile separado de build (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P1

#### S2-10 — God object `ChatterboxEngine`
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/engine.py:128-870`
- **Evidencia**: La clase asume carga de modelos, síntesis TTS, caché, conversión de audio, precomputación de conditionals y gestión de voces (15+ métodos).
- **Confianza**: Alta
- **Causa**: Responsabilidad no separada (violación de SRP).
- **Impacto**: Alto acoplamiento interno, difícil de testear aisladamente.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — definir el alcance de la descomposición (qué colaboradores extraer) y el criterio de "terminado".
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) Detenerse tras las extracciones triviales**. Ya extraídos `ModelLoader` y `ConditionalsPreparer`; dejar el resto.
    - *Pros*: bajo esfuerzo; cierra algo de deuda inmediata.
    - *Contras*: **trampa del parche barato** — deja intacto el núcleo duro (síntesis `speak`, monkeypatch de `self._tts`, callback de progreso stateful). Repite el patrón "extraer lo fácil y declarar victoria" que perpetúa el God object.
  - **B) Descomposición completa** según el deep-dive: `ComputeBackendResolver`, `ModelCache` (afecta `run.py:107-110`), `AudioWriter`, `ConditionalsPreparer` (✓), `SynthesisInstrumentation`, más el `VoiceManager` señalado originalmente.
    - *Pros*: SRP real; el engine queda testeable por piezas; elimina la deuda estructural.
    - *Contras*: alto esfuerzo y riesgo (especialmente `ModelCache` en el arranque y el estado stateful del callback); exige tests de cada colaborador antes de mover lógica.
  - **C) Descomposición acotada de alto impacto**. Extraer solo `AudioWriter` y `ComputeBackendResolver` (responsabilidades aislables y bien delimitadas), y dejar `SynthesisInstrumentation`/callback para una fase posterior.
    - *Pros*: ganancia de testabilidad desproporcionada respecto al costo; menor superficie de regresión que B.
    - *Contras*: el God object sigue existiendo parcialmente; queda "en progreso" hasta completar el resto.
  - **Trampa del parche barato**: marcar S2-10 como "Resuelto" tras A. El hallazgo solo está cerrado cuando el núcleo deja de ser un único objeto de 15+ métodos con responsabilidad de síntesis.
  - **Qué se necesita del humano**: (1) aprobar el **arquitectura destino** (B vs. C); (2) fijar el **criterio de terminado** ("Resuelto" solo cuando el `speak`/`self._tts` stateful deje el God object) para no dejarlo a medias indefinidamente.

- **Estado**: En progreso
- **Avance parcial (S3-01)**: La extracción de `ModelLoader` y `ConditionalsPreparer` como colaboradores inyectables (Tareas 1-2 de la remediación de S3-01) ya segregó dos de las responsabilidades del God object: la carga/resolución de modelos y la preparación de conditionals. Ambos viven ahora en `src/tts_sidecar/model_loader.py` y `src/tts_sidecar/conditionals.py`, inyectables en `ChatterboxEngine` vía `model_loader`/`conditionals_prep` (kwargs opcionales de `__init__`, compatibles con `get_instance`). Restan por extraer las responsabilidades señaladas en el deep-dive (ComputeBackendResolver, ModelCache, AudioWriter, SynthesisInstrumentation).

#### S2-11 — Estado global `_active_spinner` en `timing.py`
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/timing.py:20-21, 244-263`
- **Evidencia**: Variable global que coordina `log()` y `Spinner`.
- **Confianza**: Alta
- **Causa**: Acoplamiento implícito vía estado global.
- **Impacto**: Dificulta pruebas unitarias y thread-safety en escenarios complejos.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — decidir si resolverlo junto con S2-01 y si el alcance incluye `_synthesis_timing`.
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) Pasar el spinner por contexto/parámetro a `log()`** (eliminar el global `_active_spinner`, `timing.py:20-21, 244-263`).
    - *Pros*: elimina el global; testeable aisladamente; thread-safe.
    - *Contras*: cambia la firma de `log()` y todos sus call sites (CLI, engine vía callbacks); emparentado con S2-01 (`server.py` lee `_synthesis_timing` vía globals).
  - **B) `threading.local()` para el spinner activo**.
    - *Pros*: menor superficie de cambio que A; preserva la API de `log()`.
    - *Contras*: sigue siendo estado implícito (ahora por hilo); no resuelve el acoplamiento con `server.py`; parche parcial.
  - **C) Mantener el global**.
    - *Pros*: cero cambio.
    - *Contras*: no testeable aisladamente; frágil en multithread.
  - **Trampa del parche barato**: envolver el global en una clase singleton — sigue siendo global mutable, solo cambia la forma, no el acoplamiento.
  - **Qué se necesita del humano**: (1) resolver aislado o junto con S2-01 (mismo tema de globals); (2) si el alcance incluye `_synthesis_timing`.

#### S2-12 — `bootstrap` usa `warnings.filterwarnings("ignore")` global
- **Categoría**: Observabilidad / Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/bootstrap.py:61`
- **Evidencia**: `warnings.filterwarnings("ignore")` silencia **todos** los warnings sin distinción, además de los filtros específicos de las líneas siguientes.
- **Confianza**: Media
- **Causa**: Supresión amplia "por si acaso".
- **Impacto**: Enmascara futuras deprecaciones o advertencias de runtime útiles.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — aprobar la allow-list de warnings a silenciar y confirmar que ningún flujo depende del silencio total.
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) Acotar a filtros específicos y eliminar el catch-all** (`bootstrap.py:61` `warnings.filterwarnings("ignore")`), dejando solo los `DeprecationWarning`/`pkg_resources` y los loggers ya fijados en `bootstrap.py:68-70`.
    - *Pros*: observabilidad real sin ruido innecesario; cierra el hallazgo.
    - *Contras*: riesgo de superficie de warnings en runtime si falta alguno en la allow-list; hay que verificar contra entornos reales (CI/build).
  - **B) Mantener el catch-all global**.
    - *Pros*: cero riesgo de warnings molestos.
    - *Contras*: enmascara deprecaciones futuras; el hallazgo no se cierra.
  - **C) Catch-all con allow-list explícita documentada** (lista blanca de módulos a silenciar).
    - *Pros*: controlado y documentado; reversible.
    - *Contras*: mantenimiento de la lista.
  - **Trampa del parche barato**: borrar la línea 61 sin verificar qué warnings reaparecen → CI ruidoso o, peor, warnings que ocultan errores reales.
  - **Qué se necesita del humano**: aprobar la allow-list de warnings a silenciar (debe preservar el contrato de arranque limpio de CLAUDE.md) y confirmar que ningún flujo depende del silencio total.

#### S2-13 — Creación de directorios duplicada `_emit_audio` vs `_save_wav`
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/cli.py:102-104` (`_emit_audio`) vs `src/tts_sidecar/engine.py:629-631` (`_save_wav`)
- **Evidencia**: `_emit_audio` (CLI) crea el directorio padre con `os.makedirs(parent, exist_ok=True)` (`cli.py:102-104`) y `_save_wav` (engine) hace `Path(path).parent.mkdir(parents=True, exist_ok=True)` (`engine.py:631`). Parecen duplicados, pero operan en **procesos distintos**: en modo daemon el servidor escribe vía `_save_wav` en su propio filesystem y devuelve los bytes; el cliente los escribe con `_emit_audio` en **su** filesystem. Por eso el comentario N-12 (`cli.py:99-101`) lo justifica explícitamente como simetría necesaria, no como descuido.
- **Confianza**: Alta
- **Causa**: El límite cliente/servidor del daemon hace que "el engine ya creó el archivo" no sea cierto en el filesystem del cliente; la creación del lado cliente es requerida, no redundante.
- **Impacto**: Borrar el `makedirs` de `_emit_audio` (el "arreglo obvio") rompería `--output` en modo daemon cuando el directorio no existe en la máquina del cliente — justo la trampa del parche barato.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — decidir si la duplicación se mantiene (documentada) o se extrae un helper compartido sin eliminar la creación del lado cliente.
- **Prioridad**: P2
- **Alternativas y trade-offs**:
  - **A) Dejar como está, documentando el porqué**. La creación del lado cliente es correcta por el límite daemon cliente/servidor; el comentario N-12 ya lo explica.
    - *Pros*: cero riesgo; preserva `--output` remoto; el comportamiento es el correcto.
    - *Contras*: hay dos llamadas de creación de directorio que "se ven" duplicadas en una lectura superficial; un revisor podría "limpiarlas" y romper el daemon.
  - **B) Extraer un helper `ensure_parent_dir(path)` compartido** (p. ej. en `paths` o un módulo util) usado por ambos `_save_wav` y `_emit_audio`, **sin** eliminar la llamada del lado cliente.
    - *Pros*: una sola implementación de la creación de dirs; elimina el código duplicado real sin tocar el contrato de archivos del daemon.
    - *Contras*: refactor menor que cruza cli/engine; hay que cuidar que el helper no asuma nada sobre el filesystem del otro proceso.
  - **C) Eliminar el `makedirs` de `_emit_audio` y "centralizar en `_save_wav`"** (la propuesta original del hallazgo).
    - *Pros*: aparenta eliminar duplicación.
    - *Contras*: **Trampa del parche barato** — `_save_wav` corre en el servidor, no en el cliente; quitar la creación del lado cliente rompe `--output` en modo daemon cuando el dir no existe localmente. No aplicar.
  - **Qué se necesita del humano**: aprobar A (mantener + documentar) o B (helper compartido sin eliminar creación del cliente); rechazar C.

#### S2-14 — Orden de imports de `cli` acoplado a bootstrap + entry points duplicados
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `src/tts_sidecar/cli.py:17,31`; `bin/tts-sidecar:23-24`
- **Evidencia**: `bootstrap.apply()` se ejecuta al inicio de `cli.py`, imponiendo que todo import posterior ocurra después; `bin/tts-sidecar` además ajusta `sys.path` y hay tres entry points (`bin/tts-sidecar`, `python -m tts_sidecar`, `python -m ...daemon.run`) con tratamiento distinto.
- **Confianza**: Alta
- **Causa**: Lógica de bootstrap/entry-point repartida.
- **Impacto**: Refactorizar imports tempranos rompe la supresión de warnings; patrón de arranque no unívoco.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — definir la capa de bootstrap única y el orden de los entry points.
- **Alternativas y trade-offs**:
  - **A) Capa de bootstrap única** (`bootstrap.apply()` idempotente invocada por los tres entry points, con un helper `ensure_path()` que ajusta `sys.path` solo cuando hace falta).
    - *Pros*: un solo punto de verdad para el orden de arranque; elimina la divergencia de los tres entry points; facil de testear el contrato de warnings.
    - *Contras*: requiere auditar `bin/tts-sidecar` (ajuste condicional de `sys.path` — el wheel pip no lo necesita), `python -m tts_sidecar` y `daemon.run`; el orden de `apply()` **gobierna la supresión de warnings** documentada en CLAUDE.md, así que hay que verificar que la lista resultante no cambia el contrato observable.
  - **B) Mantener los tres entry points pero documentar y testear el invariante** (sin unificar el código).
    - *Pros*: riesgo mínimo; no toca el wiring.
    - *Contras*: **trampa del parche barato** — deja la duplicación y la fragilidad ("mover un import rompe los warnings"); el hallazgo queda "mitigado por documentación", no resuelto.
  - **Trampa del parche barato**: reordenar imports de sitio "para que funcione" sin una capa única. El orden de `bootstrap.apply()` es un **invariante de arranque**, no detalle cosmético; un reorden ingenuo lo rompe silenciosamente.
  - **Qué se necesita del humano**: (1) aprobar la capa única (A); (2) confirmar la lista de warnings silenciados que el contrato de CLAUDE.md exige preservar.

#### S2-15 — `voice add`/`remove` exigen modelo en caché innecesariamente
- **Categoría**: Diseño
- **Área/plataforma**: `src/tts_sidecar/cli.py:185-194`
- **Evidencia**: `_require_model_cached` se invoca en `cmd_voice_add`/`cmd_voice_remove`; la validación y copia de archivos de audio no necesitan el modelo.
- **Confianza**: Alta
- **Causa**: Reutilización de un guard demasiado estricto.
- **Impacto**: Obliga a `setup` previo para registrar voces aunque solo se valide audio.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — decidir si relajar el requisito de modelo para `voice add`/`remove` (decisión de producto/UX, no técnica).
- **Alternativas y trade-offs**:
  - **A) Relajar el guard** (`cmd_voice_add`/`cmd_voice_remove` ya no invocan `_require_model_cached`; el registro/copia funciona sin `setup` previo).
    - *Pros*: UX mejor: se pueden registrar voces tras solo validar audio; elimina la dependencia innecesaria del modelo.
    - *Contras*: requiere verificar que ningún flujo aguas abajo asume "si la voz existe, el modelo está cacheado"; el `precompute` de conditionals ya se difiere al primer `speak`, así que el riesgo es bajo pero debe confirmarse.
  - **B) Mantener el guard** y documentar por qué (p.ej. para garantizar que el modelo está disponible antes de tocar voces).
    - *Pros*: comportamiento actual preservado; sin sorpresas.
    - *Contras*: obliga a `setup` aunque solo se quiera validar/copiar audio — la molestia que motiva el hallazgo.
  - **C) Relajar solo `voice add` pero mantener el guard en `voice remove`** (o viceversa).
    - *Pros*: granularidad fina; se puede relajar solo lo que aporte valor.
    - *Contras*: asimetría que complica el modelo mental del CLI; posible confusión del usuario.
  - **Trampa del parche barato**: quitar el guard sin rastrear los flujos dependientes — "funciona en el smoke test" pero rompe un caso de borde real.
  - **Qué se necesita del humano**: (1) el veredicto de producto (¿registrar voces sin modelo es el comportamiento deseado?); (2) confirmar que no hay consumidor que asuma modelo-presente a partir de una voz registrada.

#### S2-16 — Cobertura: `daemon run` (auto-restart, señales) y `setup`/`uninstall` subtesteados
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/daemon/run.py` (`serve()`, `signal_handler()`, `main()`); `tests/test_cli.py` (`cmd_setup` con `--uninstall`/`--remove-path`/`--force-update`)
- **Evidencia**: `test_daemon.py` cubre el semáforo y el bind en uso, pero `--auto-restart`/`--max-retries`, handlers de señal y `atexit` tienen cobertura limitada; `cmd_setup` con sus flags tiene pocos tests.
- **Confianza**: Alta
- **Causa**: Paths de arranque/parada y de desinstalación menos ejercitados que los de síntesis.
- **Impacto**: Regresiones en arranque/apagado del daemon y en el flujo de desinstalación pasarían desapercibidas.
- **Corrección(es) propuesta(s)**: Clase dedicada para `serve()` con escenarios de auto-restart y tests de `main()`/flags de `setup` (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P1

#### S2-17 — Cobertura: reproducción de audio por plataforma (macOS/Windows) sin tests
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/audio.py` (`MacOSAudioPlayer`, `WindowsAudioPlayer`, `AudioPlayer`)
- **Evidencia**: `test_audio.py` solo prueba `SoundDevicePlayer` mockeado; las implementaciones macOS/Windows no están testeadas.
- **Confianza**: Alta
- **Causa**: Dependencia de subsistemas de audio del SO difíciles de mockear.
- **Impacto**: Fallos de reproducción específicos de plataforma no se detectarían en CI.
- **Corrección(es) propuesta(s)**: Tests con `pytest.mark.skipif` por plataforma y dobles ligeros de los backends (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P2

#### S2-18 — Cobertura: `purge_incomplete_downloads` sin test
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/model_cache.py` (`purge_incomplete_downloads`)
- **Evidencia**: `test_engine_cache.py` (27 tests) no cubre la limpieza de descargas de HuggingFace abortadas.
- **Confianza**: Alta
- **Causa**: Funcionalidad de recuperación menos visible.
- **Impacto**: Regresiones en la limpieza de caché corrupta pasarían desapercibidas.
- **Corrección(es) propuesta(s)**: Test con archivos incompletos sintéticos en un directorio temporal (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P2

### S1 — Bajos

#### S1-01 — Logging redundante en `_emit_audio`
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/cli.py:280-303`
- **Evidencia**: `engine.speak` ya registra el guardado; `_emit_audio` lo vuelve a registrar.
- **Confianza**: Alta
- **Impacto**: Doble mensaje "Archivo guardado" para el mismo evento.
- **Corrección**: Eliminar el log redundante o suprimirlo en el engine con un flag.
- **Prioridad**: P3

#### S1-02 — Filtro de warning redundante en `audio.py`
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/audio.py:6-7`
- **Evidencia**: `warnings.filterwarnings("ignore", message="pkg_resources is deprecated")` duplica lo que ya hace `bootstrap.py`.
- **Confianza**: Media
- **Impacto**: Ruido de mantenimiento; inofensivo en runtime.
- **Corrección**: Remover o documentar como fallback para `import tts_sidecar.audio` sin bootstrap.
- **Prioridad**: P3

#### S1-03 — `import subprocess` bajo guarda de plataforma
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/cli.py:552-556`
- **Evidencia**: `subprocess` se importa dentro de la rama `darwin` para el chequeo AVX2.
- **Confianza**: Baja
- **Impacto**: Oculta la dependencia; confusión si se ejecuta fuera de la plataforma esperada.
- **Corrección**: Import local explícito al inicio de la función.
- **Prioridad**: P3

#### S1-04 — `_paths_allowed_by_daemon` no valida existencia de archivos
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/cli.py:127-136`
- **Evidencia**: Valida que la ruta caiga en `allowed_audio_dirs()` con `realpath`, pero no que el archivo exista; el fallo se pospone al daemon (404/400).
- **Confianza**: Media
- **Impacto**: Mensaje de error menos preciso de lo necesario.
- **Corrección**: Validar existencia antes de llamar a `_paths_allowed_by_daemon`.
- **Prioridad**: P3

#### S1-05 — `list_voices` es O(n²)
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/voices.py:119-129`
- **Evidencia**: Usa `seen = []` + `if entry not in seen` para deduplicar.
- **Confianza**: Alta
- **Impacto**: Ineficiencia algorítmica leve; irrelevante con pocas voces.
- **Corrección**: Usar `set` para los nombres vistos (manteniendo orden con `sorted`).
- **Prioridad**: P3

#### S1-06 — `__init__.py` declara `__all__ = []`
- **Categoría**: Calidad de código
- **Área/plataforma**: `src/tts_sidecar/__init__.py:27`
- **Evidencia**: `__all__ = []` vacío contradice la API pública implícita (`ChatterboxEngine`, `AudioPlayer` vía imports perezosos).
- **Confianza**: Alta
- **Impacto**: La API pública no está declarada explícitamente.
- **Corrección**: Declarar los símbolos públicos o eliminar la lista vacía.
- **Prioridad**: P3

#### S1-07 — Valores mágicos sin nombrar
- **Categoría**: Calidad de código
- **Área/plataforma**: `audio.py:144` (`32768.0`); `daemon/ipc.py:38` (`REQUEST_TIMEOUT = 300.0`); `scripts/pyinstaller_wrapper.py:37` (`0x8` COINIT); `model_cache.py:33-35` (SHAs de revisión)
- **Evidencia**: Constantes hardcodeadas sin nombre semántico ni comentario de origen.
- **Confianza**: Alta (audio/ipc), Media (resto)
- **Impacto**: Dificulta el mantenimiento y la actualización de revisiones/pines.
- **Corrección**: Extraer a constantes con nombre y documentar el rationale (SHAs → referenciar `RELEASING.md`; `0x8` → comentar `COINIT_MULTITHREADED`).
- **Prioridad**: P3

#### S1-08 — `_install_pkg_resources_mock` (edge cases) sin test
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/bootstrap.py`
- **Evidencia**: La resolución de recursos para paquetes sin `__spec__`/search locations no tiene test explícito.
- **Confianza**: Media
- **Impacto**: Un cambio de versión de Python podría romper el fallback sin detectarse.
- **Corrección**: Tests de los edge cases de resolución de recursos.
- **Prioridad**: P2

#### S1-09 — Decorador `timed()` sin test
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/timing.py` (`timed`)
- **Evidencia**: `test_timing.py` cubre `StageTimer` y `Spinner`, pero no el decorador `timed`.
- **Confianza**: Alta
- **Impacto**: Regresiones en la salida de temporización pasarían desapercibidas.
- **Corrección**: Tests del decorador con varias firmas de función.
- **Prioridad**: P2

#### S1-10 — `protocol.py`: edge cases sin test
- **Categoría**: Testing
- **Área/plataforma**: `src/tts_sidecar/daemon/protocol.py`
- **Evidencia**: `test_protocol.py` (22 tests) cubre validación básica, pero no límites de longitud (`MAX_AUDIO_PATH_LENGTH`), manejo de unicode ni validación cruzada.
- **Confianza**: Media
- **Impacto**: Casos borde de validación de entrada podrían fallar con entradas reales.
- **Corrección**: Tests parametrizados de fronteras y caracteres especiales.
- **Prioridad**: P2

#### S1-11 — Fixtures muertas en `conftest.py`
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `tests/conftest.py:14-34`
- **Evidencia**: `mock_engine` y `mock_daemon_client` no se usan en ningún test; los tests crean sus propios mocks.
- **Confianza**: Alta
- **Impacto**: Sobrecarga de mantenimiento; riesgo de usar fixtures desactualizados.
- **Corrección**: Eliminarlas o migrar los tests a usarlas consistentemente.
- **Prioridad**: P2

#### S1-12 — Patrones frágiles en tests
- **Categoría**: Testing
- **Área/plataforma**: `tests/test_cli.py` (symlinks Windows, `_symlinks_supported()` skips), `tests/test_daemon.py` (archivos en `tempfile.gettempdir()`, `time.sleep` + timeouts de 10s)
- **Evidencia**: Tests de symlinks se saltan en Windows sin Developer Mode; tests de daemon crean archivos en el temp global y usan `time.sleep` con timeouts largos.
- **Confianza**: Media
- **Impacto**: Cobertura silenciosa en Windows; posible flakiness en CI por contención de filesystem/tiempos.
- **Corrección**: Subdirectorios temporales aislados; reducir timeouts; documentar la limitación de symlinks en Windows.
- **Prioridad**: P3

#### S1-13 — `render_cask.py` usa `.format()` sin validación de campos
- **Categoría**: Calidad de código
- **Área/plataforma**: `scripts/render_cask.py:24-94`
- **Evidencia**: `_CASK_TEMPLATE` usa campos **nombrados** (`{cask_name}`, `{version}`, `{sha256}`, `{repo}`) resueltos vía `.format(...)` con kwargs (`render_cask.py:89`); un typo en un nombre daría `KeyError` en runtime, no al importar — sin validación en tiempo de parseo. (La evidencia original decía "{} posicionales", lo cual es impreciso: el template ya usa campos nombrados, pero el riesgo de fallo tardío persiste igual.)
- **Confianza**: Media
- **Impacto**: Fallo tardío en generación del Homebrew Cask (solo detectable en runtime/CI, no al importar el módulo).
- **Corrección(es) propuesta(s)**: Usar f-strings o validar explícitamente los campos (p. ej. un test que renderice con la versión real y afirme la presencia de las stanzas `cask`/`version`/`sha256`), de modo que un typo falle en CI y no en la generación del Cask.
- **Prioridad**: P3

#### S1-14 — `create_installer_windows.py`: rutas ISCC hardcodeadas
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `scripts/create_installer_windows.py:24-40`
- **Evidencia**: La evidencia original afirmaba que `get_inno_setup_path()` solo buscaba en ubicaciones fijas (`Program Files (x86)`, `Program Files`, `ProgramData/chocolatey/bin`) sin consultar `PATH`. La lectura directa del código (`create_installer_windows.py:35-38`) confirma que **sí** itera `os.environ.get("PATH", "").split(os.pathsep)` tras los candidatos fijos: los paths fijos son solo un fallback y el `PATH` ya se consulta. El hallazgo era un falso positivo de la evidencia (deriva documental, no deuda real).
- **Confianza**: Alta
- **Impacto**: Ninguno en la forma actual; el `PATH` ya se resuelve antes de abortar.
- **Corrección(es) propuesta(s)**: Ninguna (ya resuelto en código). Dejar constancia para evitar reabrirlo.
- **Decisión requerida**: No
- **Prioridad**: P3
- **Estado**: Resuelto

#### S1-15 — `clean_build.py` asume ubicación relativa al repo
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `scripts/clean_build.py:18-21`
- **Evidencia**: `PROJECT_ROOT = Path(__file__).parent.parent` asume que el script vive en `scripts/`.
- **Confianza**: Media
- **Impacto**: Falla silenciosamente si se ejecuta desde otra ruta o como módulo instalado.
- **Corrección**: Resolver la raíz de forma robusta o documentar el uso esperado.
- **Prioridad**: P3

#### S1-16 — `build_utils.py` importa PIL duplicado en `ensure_ico`/`ensure_icns`
- **Categoría**: Calidad de código
- **Área/plataforma**: `scripts/build_utils.py:322-323, 347-348`
- **Evidencia**: La lógica de lectura de logo, creación de directorio y logging de warning está duplicada entre ambas funciones.
- **Confianza**: Media
- **Impacto**: Mantenimiento repetitivo del placeholder.
- **Corrección**: Factor común para el manejo del placeholder.
- **Prioridad**: P3

#### S1-17 — Validación de nombre de voz no previene symlinks dentro del dir permitido
- **Categoría**: Seguridad
- **Área/plataforma**: `src/tts_sidecar/voices.py:39-44`
- **Evidencia**: `_validate_voice_name` rechaza `..`/`.` pero no symlinks; la defensa en profundidad con `realpath` en `voice_dir` (líneas 93-98) ya contiene el escape de directorio, por lo que un symlink dentro del dir permitido solo podría cargar un `.wav` controlado por el atacante (sin ejecución de código).
- **Confianza**: Media
- **Impacto**: Explotabilidad baja; posible carga de audio arbitrario dentro del sandbox.
- **Corrección(es) propuesta(s)**: Ver «Alternativas y trade-offs».
- **Decisión requerida**: Sí — decidir si aceptar el riesgo residual o endurecer la lectura con `O_NOFOLLOW`.
- **Prioridad**: P3
- **Alternativas y trade-offs**:
  - **A) Aceptar el límite y documentarlo** (status quo endurecido con documentación). La defensa en profundidad con `realpath` en `voice_dir` ya contiene el escape de directorio, así que un symlink dentro del dir permitido solo podría cargar un `.wav` controlado por el atacante, sin ejecución de código.
    - *Pros*: cero cambio de código; explotabilidad ya baja.
    - *Contras*: deja abierta la carga de audio arbitrario dentro del sandbox; es aceptar riesgo, no mitigarlo.
  - **B) Endurecer con `os.open(..., O_NOFOLLOW)`** al leer los archivos de voz, rechazando symlinks en la apertura.
    - *Pros*: cierra la ventana de symlink a nivel de syscall; defensa en la raíz de la lectura.
    - *Contras*: `O_NOFOLLOW` es POSIX (no portable a Windows sin equivalente); hay que manejar el `OSError` y dar un error accionable; toca el path de lectura de voz.
  - **C) Rechazar symlinks en `_validate_voice_name`/`voice_dir`** (validar que la ruta no sea symlink antes de aceptarla).
    - *Pros*: defensa explícita y temprana, antes de leer.
    - *Contras*: un symlink *legítimo* (p. ej. voce enlazada por el usuario) se rechazaría; posible molestia para usuarios avanzados.
  - **Trampa del parche barato**: "documentar" sin más — etiquetar el riesgo y cerrar el hallazgo sin endurecer nada; en seguridad, documentar un riesgo conocido no lo mitiga.
  - **Qué se necesita del humano**: (1) ¿aceptar el riesgo residual (A) o mitigarlo (B/C)?; (2) si mitigar, ¿`O_NOFOLLOW` (B, no portable) o rechazo de symlinks (C, más estricto)?

#### S1-18 — Deriva documental menor (árbol de CLAUDE.md y ruta de voces en DESIGN.md)
- **Categoría**: Documentación
- **Área/plataforma**: `CLAUDE.md`, `DESIGN.md`
- **Evidencia**: El árbol de arquitectura de `CLAUDE.md` (sección «Estructura de directorios») no lista `model_cache.py` (módulo real en `src/tts_sidecar/model_cache.py`, usado por `engine.py`/`cli.py`) ni el directorio `tests/installer/` (smoke-tests bats/Pester). `DESIGN.md:131` afirma que las voces de fábrica están «`voices/` en la raíz del repo», pero `paths.py:82` resuelve `src/tts_sidecar/voices/` desde `835b767` («refactor: mover voces de fábrica al paquete»).
- **Confianza**: Alta
- **Causa**: Documentación no actualizada tras refactors (en particular `835b767` movió las voces al paquete sin tocar `DESIGN.md`).
- **Impacto**: Contribuidores buscan `model_cache.py` o las voces en ubicaciones equivocadas.
- **Corrección(es) propuesta(s)**: Añadir `model_cache.py` y `tests/installer/` al árbol de `CLAUDE.md`; corregir `DESIGN.md:131` a `src/tts_sidecar/voices/` (recomendada).
- **Decisión requerida**: No
- **Prioridad**: P3

Nota: el conteo de tests **no** es una discrepancia. `pytest --collect-only` recolecta **350 tests** (exit 0, 0.76s); el conteo estático de funciones `def test_` es 336. `CLAUDE.md` («~350 tests») y `GOAL.md` («336/336») son coherentes con ambas cifras; `USAGE.md` no declara ningún conteo. La afirmación de que GOAL/USAGE decían «314» era un falso positivo del sub-agente.

### S0 — Informativos

#### S0-01 — `bundle_size_mb()` no referenciada externamente
- **Categoría**: Calidad de código
- **Área/plataforma**: `scripts/build_utils.py:269-276`
- **Evidencia**: La evidencia original afirmaba que `bundle_size_mb()` no era invocada por otros módulos (código muerto leve). La lectura directa del código confirma que **sí** está referenciada externamente: se importa y usa en `scripts/build_linux.py:180`, `scripts/build_macos.py:133` y `scripts/build_windows.py:154` (log del tamaño del bundle tras el build de PyInstaller) y además tiene un test dedicado `tests/test_build_utils.py:181` (`test_bundle_size_mb_sums_nested_files`). El hallazgo era un falso positivo de la evidencia (deriva documental, no deuda real).
- **Confianza**: Alta
- **Impacto**: Ninguno en la forma actual; la función está vigente y cubierta por test.
- **Corrección(es) propuesta(s)**: Ninguna (ya resuelto en código). Dejar constancia para evitar reabrirlo.
- **Decisión requerida**: No
- **Prioridad**: P3
- **Estado**: Resuelto

#### S0-02 — Estrategia de lockfile CPU-only de Linux no documentada
- **Categoría**: Dependencias
- **Área/plataforma**: `requirements-lock-linux-cpu.txt`
- **Evidencia**: Generado con `--index-strategy unsafe-best-match` contra `https://download.pytorch.org/whl/cpu`; la razón no está documentada en el repo.
- **Confianza**: Media
- **Impacto**: Futuras regeneraciones podrían romper si cambia la estructura de wheels de PyTorch.
- **Corrección**: Documentar el procedimiento en `docs/DISTRIBUTION.md` o `BUILD.md`.
- **Prioridad**: P3

#### S0-03 — `pyenv` sin pin de versión (decisión consciente)
- **Categoría**: DevOps
- **Área/plataforma**: `.circleci/config.yml:215, 748`
- **Evidencia**: Comentario explicita que Homebrew no fija pyenv y que la imagen puede no traer el patch más reciente.
- **Confianza**: Alta
- **Impacto**: Ninguno; es una excepción documentada.
- **Corrección**: Mantener como está.
- **Prioridad**: P3

#### S0-04 — Naming inconsistente de arquitectura en artefactos
- **Categoría**: Mantenibilidad
- **Área/plataforma**: `scripts/build_linux.py:231` (`aarch64`), `.circleci/config.yml:373` (`x86_64`), macOS usa `arm64`
- **Evidencia**: Linux usa `aarch64` (estilo `uname -m`), Windows `x86_64`, macOS `arm64`.
- **Confianza**: Media
- **Impacto**: Confusión cosmética para el usuario final.
- **Corrección**: Documentar la convención por SO; no unificar forzosamente.
- **Prioridad**: P3

#### S0-05 — TOCTOU en validación de audio del daemon — verificado ya mitigado
- **Categoría**: Seguridad
- **Área/plataforma**: `src/tts_sidecar/daemon/server.py` (`_validate_audio_path`, extraída de `synthesize` en la remediación de S3-02)
- **Evidencia**: Un sub-agente reportó una carrera entre la validación de directorio y la del header WAV. La lectura directa confirma que `real_path = os.path.realpath(path)` se calcula **una sola vez** dentro de `_validate_audio_path` y se devuelve al caller (`synthesize`), que lo pasa directo al engine para ambas comprobaciones (directorio y header WAV) sin volver a resolver la ruta; el comentario WARNING-02 documenta que esto ya cierra la ventana de symlink swap. El `realpath` canónico hace que la ventana de "validar y usar" no exista como se describió.
- **Confianza**: Alta
- **Impacto**: Ninguno en la forma actual; el hallazgo de severidad alta propuesto era un falso positivo.
- **Corrección**: Ninguna (ya mitigado). Dejar constancia para evitar reabrirlo.
- **Decisión requerida**: No
- **Prioridad**: P3
- **Estado**: Resuelto

## Orden de corrección recomendado

**Fase 1 — Observabilidad y fiabilidad de release (P1 de mayor impacto/esfuerzo bajo)**
- S2-02 (logging de excepciones silenciadas) — bajo esfuerzo, alto valor de diagnóstico.
- S2-06, S2-07, S2-09 (deriva de build/CI: dependencias duplicadas, pines, lockfiles de build) — fiabilidad de release.
- S3-01, S3-02 (cerrar brechas de cobertura en engine core y sandbox del daemon).
- S2-16 (tests de `daemon run` y `setup`/`uninstall`).
- S2-14 (consolidar entry points/bootstrap) — requiere decisión de diseño.

**Fase 2 — Acoplamiento y arquitectura (P2)**
- S2-01 (DI del engine en el daemon) — requiere decisión de diseño.
- S2-10, S2-11 (God object engine, estado global en timing).
- S2-03, S2-04 (liberación de modelo y cancelación de worker en shutdown).
- S2-05, S2-13, S2-12 (reuso de protocol en ipc, makedirs, bootstrap global).
- S2-15 (relajar requisito de modelo en `voice add`/`remove`) — requiere decisión de diseño.
- S2-08, S2-17, S2-18 (smoke tests CI, audio por plataforma, purge).

**Fase 3 — Pulido y deuda menor (P3 / S1-S0)**
- S1-01…S1-17 (logging redundante, imports, O(n²), magic numbers, fixtures muertas, patrones frágiles de test, rutas hardcodeadas).
- S0-01…S0-04 (código muerto leve, documentación de estrategia de lockfile, naming de arquitectura).

## Confirmación en CI

Hallazgos cuya evidencia ya está establecida por lectura de código y que se confirman al correr CI (no son hipótesis):

- **S3-01 / S3-02 / S2-16 / S2-17 / S2-18**: la cobertura real se confirma con el reporte de cobertura de pytest en CI (jobs `test-*`). El descubrimiento de tests se confirmó en ejecución: `pytest --collect-only -q` recolecta **350 tests** en 0.76s (exit 0); el conteo estático de funciones `def test_` es 336. Ambas cifras coinciden con `CLAUDE.md` (~350) y `GOAL.md` (336/336).
- **S2-06 / S2-07 / S2-08 / S2-09 / S0-03**: la estructura y los pines de `.circleci/config.yml` se validan en cada push; cualquier divergencia de pines aparecerá como fallo de instalación en los jobs de build.
- **S2-02**: la ausencia de trazas ante fallos de subsistemas (audio/PyTorch) se hace evidente en los logs de CI cuando un job de build/smoke-test encuentra un entorno diverso.
- **S0-05**: la mitigación TOCTOU ya está en el código (`_validate_audio_path` en `server.py`, que resuelve `realpath` una sola vez y lo reusa); los tests de sandbox en `tests/test_daemon_sandbox.py` (`TestValidateAudioPath`) y `tests/test_daemon.py` (`TestDaemonSessionSandbox`) la ejercen directa e indirectamente y la confirmarán al correr.

## Provenance y refinamiento arquitectónico (verificación adicional)

Como parte de la verificación solicitada, se cruzó la deuda con `git log` y se encargó un deep-dive arquitectónico. Conclusiones:

**Provenance (git)**
- `engine.py` y `daemon/server.py` aparecen por primera vez en `cc1092f` («refactor: rename estructural completo del producto a TTS Sidecar»); el patrón `except Exception: pass` (S2-02) lleva ahí desde entonces (no introducido en un cambio reciente). La deuda de acoplamiento (S2-01, S2-10) es **heredada**, no reciente.
- Hay mantenimiento activo y reciente del daemon: `44fdbb4` (semáforo de admisión, S3-05) y `a50fc6c` (liberar caché CUDA **por síntesis**, S3-04) ya están resueltos. Por tanto **S2-03** (modelo no liberado en **shutdown**) sigue vigente y es distinto de S3-04.
- `voices.py` se movió al paquete en `835b767` («mover voces de fábrica al paquete») sin actualizar `DESIGN.md:131` → origen de la deriva documental S1-18.
- Los build scripts (`scripts/build_*.py`) tienen actividad reciente (`75af155` release v0.5.0 paridad, `995d93f` endurecer antivirus, `9aaffbb`/`a42dfc2` macOS) pero conservan la duplicación D1/D2 (S2-06).

**Deep-dive arquitectónico (engine/daemon)**
- **S2-10 (God object) confirmado.** `ChatterboxEngine` concentra ~10 responsabilidades. Refactor incremental sugerido: (1) `ComputeBackendResolver`, (2) `ModelCache` (afecta `run.py:107-110`), (3) `AudioWriter`, (4) `ConditionalsPreparer`, (5) `SynthesisInstrumentation`. Los monkeypatches de `self._tts` y el callback de progreso stateful son los puntos más frágiles.
- **S2-01 (globals sin DI) confirmado.** Mínimo cambio: introducir `DaemonState` (dataclass con `engine`/`server`/`start_time`) y pasarlo vía `Depends(get_daemon_state)`; `run.py:107-110` dejaría de llamar `set_engine`/`set_server`. `daemon.py` no tiene estado global acoplado a `server.py`.
- **Hallazgo conectado**: `timing.py` mezcla timing, logging y el shim de progreso; `_synthesis_timing` es estado compartido escrito por el engine y leído por `server.py:195` vía globals. Sugerido: clase `SynthesisMetrics` dentro de `DaemonState` para romper el acoplamiento (refuerza S2-01/S2-11).

## Nota de verificación de falsos positivos

Durante la consolidación se verificaron dos afirmaciones de alta severidad propuestas por los sub-agentes y **se descartaron**:

1. **`npm run build-windows` inexistente (F6)**: `package.json:19` define `build-windows` → el comando documentado en `CLAUDE.md` es válido. Se eliminó el hallazgo.
2. **Carrera TOCTOU en validación de audio del daemon (B8)**: `server.py:143` resuelve `real_path` una vez y lo reusa para ambas validaciones; el comentario WARNING-02 documenta la mitigación. No es una ventana viva → degradado a S0-05 (informacional/cerrado).

Esto confirma la disciplina de rigor de evidencia del flujo: ningún hallazgo se promueve a severidad alta sin lectura directa del código.

3. **Discrepancia de conteo de tests (F1/F10 del sub-agente de docs)**: verificado en ejecución que `pytest --collect-only` recolecta **350 tests** y hay 336 funciones `def test_`. `CLAUDE.md` («~350») y `GOAL.md` («336/336») son coherentes; `USAGE.md` no declara ningún conteo. La afirmación de que GOAL/USAGE decían «314» era incorrecta → se eliminó la parte de conteos de S2-19 (reclasificado a S1-18 con solo las omisiones reales del árbol de `CLAUDE.md` y la ruta de `DESIGN.md:131`).

## Remediación en lote (hallazgos sin decisión, resolución robusta)

Se remediaron en paralelo los **21 hallazgos sin decisión requerida** cuya corrección es directa y sistémica (no parche), delegando en 4 sub-agentes por área (archivos disjuntos), integrados en la rama `chore/project-review-batch` y validados con **`pytest tests/ -q` → 443 passed, 0 failed** (baseline 350). Quedan deliberadamente fuera de este lote los hallazgos «Decisión requerida: Sí» y las no-acciones/parches (S0-03 «mantener como está», S0-04 «documentar sin unificar», S1-01/S1-02/S1-04 por depender de un criterio o verificación previa).

**Grupo 1 — Consolidación DRY build/CI**
- **S2-06**: extraídos `install_lockfile_dependencies(lockfile)` y `check_sounddevice()` a `scripts/build_utils.py`; `build_windows/macos.py` delegan directamente y `build_linux.py` conserva `ensure_runtime_dependencies(target_arch)` (requerido por `tests/test_build_linux.py`) reducido a resolver el lockfile y delegar.
- **S1-16**: helper `_generate_pillow_icon(...)` común a `ensure_ico`/`ensure_icns` (texto de log/warning preservado).
- **S2-09**: nuevo `requirements-lock-build.txt` (con hashes, pin de PyInstaller alineado a `PYINSTALLER_PIN`); `check_pyinstaller()` instala con `--require-hashes` y los 4 steps de CI consumen ese lockfile.
- **S2-08**: nuevo `command` `smoke_test_frozen_bundle` en `.circleci/config.yml` parametrizado por `executable_path`, invocado por los jobs x64 y ARM64.

**Grupo 2 — Corrección de raíz en runtime**
- **S2-03**: `/shutdown` libera `_engine = None` y llama `_clear_model_memory()` (mismo helper que la limpieza por-síntesis). Cambio de comportamiento intencional (fiabilidad).
- **S1-05**: `list_voices()` deduplica con `set` (membership O(1)) preservando el orden usuario→fábrica.
- **S1-07**: `INT16_MAX_F = 32768.0` (`audio.py`), `COINIT_MULTITHREADED = 0x8` (`pyinstaller_wrapper.py`); `ipc.py`/`model_cache.py` ya tenían nombre+rationale (sin cambio).
- **S1-06**: `__all__ = ["ChatterboxEngine", "AudioPlayer"]` (símbolos reales de `__getattr__`).
- **S1-03**: `import subprocess` movido al inicio de `_check_avx2()`.
- **S1-15**: `PROJECT_ROOT` vía `_find_project_root()` (busca `pyproject.toml`/`.git`, `SystemExit` accionable).
- **S1-13**: **verificado ya cubierto** — `tests/test_cask.py` ejercita `render_cask()`/`render_cask_from_tag()` con datos reales y afirma las stanzas `cask`/`version`/`sha256`/`url`; un typo en los campos de `_CASK_TEMPLATE.format(...)` produce `KeyError` atrapado en CI. Cerrado por cobertura preexistente, sin cambio de código (patrón de re-scoping, cf. S3-01/S3-02).

**Grupo 3 — Cobertura de tests** (net +93 tests recolectados)
- **S2-16**: `tests/test_daemon_run.py` (13) — `serve()`/`signal_handler`/`atexit`/`main()`, auto-restart y `max_retries`, `EADDRINUSE` sin reintento, SIGTERM/SIGINT. `cmd_setup --uninstall/--remove-path/--force-update` ya cubierto en `test_cli.py`.
- **S2-17**: `tests/test_audio_platform.py` (18) — `WindowsAudioPlayer`, `MacOSAudioPlayer`, dispatch de `AudioPlayer`, rama Darwin de `get_audio_devices_with_status`.
- **S2-18**: `tests/test_model_cache.py` (11) — `purge_incomplete_downloads()` sobre caché HF sintética.
- **S1-08** (`test_cli.py::TestBootstrap`, +4), **S1-09** (`test_timing.py::TestTimedDecorator`, +7), **S1-10** (`test_protocol.py`, +15: unicode/límites/validación cruzada).
- **S1-11**: eliminadas `mock_engine`/`mock_daemon_client` de `conftest.py` (verificado sin referencias).
- **S1-12**: `tmp_path` aislado en vez del tempdir global; skip de symlinks Windows centralizado y accionable; timeouts de `test_daemon.py` revisados (son cotas de sincronización, no `sleep`; sin cambio).

**Grupo 4 — Documentación**
- **S1-18**: `CLAUDE.md` añade `model_cache.py` al árbol (`tests/installer/` ya estaba); `DESIGN.md` corrige la ruta de voces de fábrica a `src/tts_sidecar/voices/` y la descripción de `bundled_voices_dir()`.
- **S0-02**: `docs/BUILD.md` documenta el porqué de `--index-strategy unsafe-best-match` (mecanismo `first-index` de `uv`, índice CPU de PyTorch, trade-off de dependency-confusion y cuándo regenerar).
