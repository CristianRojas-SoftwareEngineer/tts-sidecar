# Auditoría Production-Readiness — tts-sidecar v0.6.0 (commit 39137bc)

**Fecha**: 2026-07-13  
**Lente**: Release-readiness (10 dimensiones canónicas)  
**Perfil**: Correctivo + Preventivo  
**Commit**: 39137bc  
**Versión actual**: 0.6.0  
**Revisión de refinamiento**: 2026-07-13 — cada hallazgo abierto re-verificado contra el código, con análisis de alternativas, trade-offs y solución recomendada con criterio arquitectónico. Los hallazgos cuya evidencia original resultó incorrecta se marcan «Resuelto (drift)»; los duplicados por causa raíz común se consolidan.  
**Revisión de remediación**: 2026-07-14 — implementadas y verificadas con tests las cuatro soluciones recomendadas de la Dimensión 2 (S2-01, S2-02, S2-05, S2-06); dimensión cerrada con veredicto LISTO. Suite: 536 tests.

---

## Resumen ejecutivo

Se audió el proyecto completo contra las 10 dimensiones de production-readiness. **El código base es sólido, bien testeado y con arquitectura limpia**. Se identificaron originalmente 0 S4, 1 S3, 15 S2, 2 S1 y 2 S0. Tras la remediación y la **revisión de refinamiento** (2026-07-13, verificación contra código): S3-01 y S2-13 **resueltos** en tests; S2-03 y S2-04 **cerrados por drift de la auditoría** (la evidencia original era incorrecta: `cleanup --json` y `setup --json` ya emitían sus payloads, con tests); S2-11 **consolidado** en S2-15 y S2-12 **subsumido** en S2-10 (misma causa raíz). Una segunda ronda de remediación (2026-07-14) implementó y verificó con tests las cuatro soluciones recomendadas de la Dimensión 2: S2-01, S2-02, S2-05 y S2-06 **resueltos**. Quedan **6 S2 abiertos**, **2 S1** y **2 S0**. Los gaps abiertos: cobertura sin instrumento de medición, ramas de fallo de build sin test, create-dmg sin pin, piso de glibc implícito en el build, riesgo OneDrive, y oferta de fuente GPLv3 §6 ausente de los artefactos nativos. Cada hallazgo abierto incluye ahora análisis de alternativas con trade-offs y una solución recomendada con criterio arquitectónico. **Veredicto global: LISTO-CON-RESERVAS** — apto para release 0.6.1 con plan de hardening pre-1.0.0.

### Conteo por severidad

| Severidad | Cuenta (abiertos) | Hallazgos clave |
|-----------|--------|-----------------|
| **S4 — Crítico** | 0 | — |
| **S3 — Alto** | 0 | — |
| **S2 — Medio** | 6 | Coverage sin instrumento (S2-09), ramas de fallo de build sin test (S2-10, incl. S2-12), create-dmg unpinned (S2-15, incl. S2-11), piso glibc implícito (S2-07), OneDrive (S2-08), GPL source offer (S2-14) |
| **S1 — Bajo** | 2 | DAEMON-MODE.md desactualizado (cancelación cooperativa), THIRD-PARTY-LICENSES sin verificación automatizada |
| **S0 — Informativo** | 2 | Anchor roto USAGE.md, orden de flags USAGE vs cli.py |

*Cerrados desde la emisión: S3-01 y S2-13 (resueltos en tests), S2-03 y S2-04 (drift de la auditoría — la evidencia era incorrecta), S2-11 → S2-15 y S2-12 → S2-10 (consolidados por causa raíz común), S2-01/S2-02/S2-05/S2-06 (implementados y verificados con tests en la remediación del 2026-07-14).*

### Conteo por prioridad recomendada

| Prioridad | Cuenta | Descripción |
|-----------|--------|-------------|
| **P0** | 2 | create-dmg pin (S2-15), coverage por módulo (S2-09) |
| **P1** | 4 | piso glibc como invariante del build (S2-07), check OneDrive en doctor (S2-08), ramas de fallo de build + normalización de criticidad (S2-10), SOURCE-OFFER en artefactos (S2-14) |
| **P2** | 2 | DAEMON-MODE.md cancelación cooperativa (S1-01), verificación THIRD-PARTY-LICENSES en CI (S1-02) |
| **P3** | 2 | S0 residuales (anchor + orden de flags; corregir junto a S1-01) |

### Conteo por dimensión (10 canónicas)

| Dimensión | S4 | S3 | S2 | S1 | S0 | Total abiertos | Veredicto |
|-----------|----|----|----|----|----|-------|-----------|
| 1. CLI robustness & error handling | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 2. Programmatic contract (--json) | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 3. Daemon lifecycle & concurrency | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 4. Model & on-disk state management | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 5. Real cross-platform compatibility | 0 | 0 | 2 | 0 | 0 | 2 | ⚠️ GAPS MEDIOS |
| 6. End-to-end install/uninstall UX | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 7. Test quality & coverage | 0 | 0 | 2 | 0 | 0 | 2 | ⚠️ GAPS MEDIOS |
| 8. Documentation as product | 0 | 0 | 0 | 1 | 2 | 3 | ⚠️ GAPS MENORES |
| 9. Licensing & compliance | 0 | 0 | 1 | 1 | 0 | 2 | ⚠️ GAPS MENORES |
| 10. Supply chain & CI | 0 | 0 | 1 | 0 | 0 | 1 | ⚠️ GAPS MEDIOS |
| **TOTAL** | **0** | **0** | **6** | **2** | **2** | **10** | **LISTO-CON-RESERVAS** |

*Dimensión 2: 4 → 0 (S2-01/S2-02/S2-05/S2-06 implementados y verificados en la remediación del 2026-07-14). Dimensión 7: 4 → 2 (S2-11 consolidado en S2-15 de la Dimensión 10; S2-12 subsumido en S2-10).*

---

## Hallazgos por dimensión (con veredicto [LISTO] / hallazgos abiertos)

### 1. CLI robustness & error handling — [LISTO]

**Qué está listo:**
- 7 exit codes congelados (0,1,2,3,4,5,130) — mapeo 1:1 a causas documentadas (cli.py:42-48)
- Todos los sys.exit() usan códigos del contrato; tests TestExitCodes cubren los 7 (test_cli.py:964-1080)
- Mensajes de error en español, accionables (sugieren setup, voice add, --no-daemon), sin rutas internas ni tracebacks
- KeyboardInterrupt → exit 130, una línea stderr "Interrumpido por el usuario.", sin traceback
- bootstrap.apply() idempotente, no crashea sin pkg_resources (Py 3.13+), reconfigura UTF-8 con try/except seguro (bootstrap.py:88-101)
- Warnings allow-list exacta: 2 entradas (pkg_resources por mensaje + diffusers por módulo); NO catch-all (test_cli.py:2081-2135)
- Paths de fallo por comando: validados via mocks exhaustivos en test_cli.py

**Hallazgos abiertos:** Ninguno

---

### 2. Programmatic contract (--json) — [LISTO]

**Qué está listo:**
- schema_version = "1" constante y presente en todos los payloads CLI (cli.py:54)
- stdout = solo JSON, stderr = logs/progreso (separación limpia)
- NDJSON daemon: ProgressEvent → ResultEvent/ErrorEvent con discriminador event, validación model_validate estricta línea a línea (ipc.py:133-199)
- Pydantic v2 = contrato formal en protocol.py; ambos extremos validan
- TTS_SIDECAR_REQUEST_TIMEOUT configurable (300s default)
- `speak --json` acoplado a `--output`, payload idéntico en ruta directa y daemon vía `SynthesisResult` (engine.py, synthesis.py, daemon/ipc.py); tests `TestSpeakJSON` (test_cli.py)
- `daemon start/stop/restart --json` con payload de acción `{"action","ok","pid"?}`; tests `TestDaemonVerbsJSON` (test_cli.py)
- Helper único `emit_json()` (cli.py) migró los 10 emisores existentes sin cambiar ningún payload congelado
- Protocolo NDJSON versionado: clase base `ProtocolModel` (`schema_version` + `extra="ignore"`) heredada por los 5 modelos de `daemon/protocol.py`; `version` en `HealthResponse`/`/health`; tests `TestProtocolVersioning` (test_protocol.py)
- `build_parser()` extraído de `main()`, introspeccionable; test estructural `TestJSONContractStructure` (test_cli.py) descubre desde el parser real qué subcomandos declaran `--json` y lo compara contra la cobertura declarada — protección bidireccional contra drift
- Tests TestWriteCommandsJSON, TestSchemaVersionJSON validan payloads exactos

**Hallazgos S2 (Medio):** Ninguno abierto — S2-01, S2-02, S2-05 y S2-06 resueltos en la remediación del 2026-07-14 (ver detalle abajo).

| ID | Estado | Título |
|----|--------|--------|
| S2-01 | **Resuelto** | `speak` sin contrato `--json` |
| S2-02 | **Resuelto** | `daemon start/stop/restart` sin `--json` |
| S2-03 | **Resuelto (drift)** | `cleanup --json` sí emite payload propio a stdout — `_emit_cleanup_json` (cli.py:1413-1420) cubre los 4 caminos (nada que borrar, dry-run, borrado real, sin flags); testeado en `test_cleanup_json_*` (test_cli.py:1683-1726). La evidencia original de la auditoría era incorrecta. |
| S2-04 | **Resuelto (drift)** | `setup --json` sí emite en provisión normal — `_emit_setup_json` (cli.py:1273-1284) cubre `already_cached` y `downloaded` (cli.py:1304, 1361), además de `--remove-path` y `--uninstall`; testeado en `test_setup_json_payload_already_cached` (test_cli.py:1622). La evidencia original era incorrecta. |
| S2-05 | **Resuelto** | `schema_version` ausente en el protocolo NDJSON del daemon |
| S2-06 | **Resuelto** | Cobertura `--json` enumerativa, sin verificación estructural del contrato |

#### S2-01 — `speak` sin contrato `--json` [Resuelto]

**Problema (refinado).** `speak` es el comando central del producto y el único de valor programático sin contrato máquina: un orquestador que invoca `speak --output audio.wav` no recibe confirmación estructurada de dónde quedó el audio ni las métricas de síntesis (`t3_time`/`s3gen_time` existen — `SynthesisMetrics` en `timing.py:20-31` y el frame `result` del daemon — pero solo se loguean como texto a stderr, `ipc.py:186-190`). El consumidor debe parsear stderr en español, que no es contrato y se rompe con cualquier reword.

**Alternativas evaluadas:**

1. **`audio_b64` en stdout** (propuesta original de esta auditoría): autocontenida, pero estructuralmente incorrecta. Un WAV de 24 kHz de una frase son varios MB; codificarlo en base64 dentro del único objeto JSON de stdout impone doble copia en memoria a ambos lados, latencia de parseo y un payload cuyo tamaño no acota el contrato. Además bifurca la semántica del comando (¿`speak --json` sin `--output` reproduce *y además* imprime MB?). El transporte `audio_b64` ya existe donde corresponde: el NDJSON del daemon, que es IPC loopback interno, no contrato público del CLI.
2. **`--json` acoplado a `--output`; payload de metadatos** — el archivo es el canal de datos y stdout el canal de control: `{"schema_version", "output": <ruta absoluta>, "voice", "t3_time", "s3gen_time", "daemon": bool}`. Payload pequeño y estable, coherente con los 10 payloads existentes del CLI. `--json` sin `--output` → exit 4 (entrada inválida), con el precedente ya congelado en el contrato de `cleanup --json`, que exige `--yes`/`--dry-run` (test_cli.py:1714).
3. **NDJSON en stdout** (progreso + result, espejo del daemon): máxima fidelidad, pero rompe la invariante «stdout = exactamente un objeto JSON» que cumplen los 10 comandos restantes; introduce un contrato dual que todo consumidor debería tratar como caso especial.

**Solución implementada: (2).** Criterio: el contrato programático del CLI debe tener una sola forma (un objeto por invocación) para que los consumidores puedan tratar todos los comandos uniformemente; los datos pesados viajan por el canal que ya existe (el filesystem, elegido por el propio consumidor vía `--output`). Prerequisito de diseño: se unificó la fuente de métricas de las dos rutas (directa y daemon) sobre un objeto de resultado `SynthesisResult` (`timing.py`, propagado por `engine.speak()`, `SynthesisOrchestrator.synthesize()` y `DaemonIPCClient.synthesize()`), de modo que el payload es idéntico campo a campo en ambas y `"daemon"` solo indica la vía. Evidencia: `cli.py::cmd_speak`/`_emit_speak_json`, `tests/test_cli.py::TestSpeakJSON` (payload exacto en ambas rutas, exit 4 sin `--output`, stdout vacío sin `--json`).

#### S2-02 — `daemon start/stop/restart` sin `--json` [Resuelto]

**Problema (refinado).** El ciclo de vida del daemon es una operación de primer orden para orquestadores (arrancar antes de un lote, detener al liberar recursos), pero `start`/`stop`/`restart` solo emiten texto (cli.py:1670-1679); únicamente `status` tiene `--json` (cli.py:1682). El problema de fondo es de mantenibilidad: el patrón JSON está repetido inline ~10 veces (`print(json.dumps({"schema_version": SCHEMA_VERSION, ...}))` con `import json` local en cada `cmd_*`), sin helper compartido — cada comando nuevo puede olvidar `schema_version` o emitir dos objetos, y nada estructural lo impide.

**Alternativas evaluadas:**

1. **Añadir `--json` ad hoc a los 3 subcomandos** repitiendo el patrón inline: cierra el gap funcional pero perpetúa la duplicación que ya causó los drifts S2-03/S2-04 de esta misma auditoría (la evidencia envejeció porque el contrato vive disperso).
2. **Extraer un helper único `emit_json(payload)` a nivel de módulo** (inyecta `schema_version`, garantiza un solo objeto por invocación) + migrar los emisores existentes + añadir los 3 subcomandos sobre esa base, con payloads mínimos de *resultado de acción*: `{"schema_version", "action": "start"|"stop"|"restart", "ok": bool, "pid"?}`.

**Solución implementada: (2).** Criterio: convertir las invariantes del contrato (un objeto, `schema_version` presente, stderr solo logs) de convención repetida a propiedad estructural con un único punto de cambio. Los verbos devuelven el **resultado de la acción**; el **estado** ya tiene su esquema en `daemon status --json` — no duplicado en los verbos. `daemon serve` queda excluido deliberadamente (proceso foreground cuyo contrato es el NDJSON del server), documentado como exclusión explícita en `USAGE.md` y en `TestJSONContractStructure`. Evidencia: `cli.py::emit_json`/`cmd_daemon` (start/stop/restart), `tests/test_cli.py::TestDaemonVerbsJSON` (payload exacto en éxito/fallo por verbo, stderr sin JSON).

#### S2-05 — `schema_version` ausente en el protocolo NDJSON del daemon [Resuelto]

**Problema (refinado).** El protocolo NDJSON es un contrato de red que hoy solo es compatible *por accidente*: los modelos de `protocol.py` (líneas 54-93) no declaran `model_config`, así que la tolerancia a campos extra es el default implícito de Pydantic v2 (`extra="ignore"`). Eso da compatibilidad hacia adelante no diseñada: si un mantenedor futuro añade `extra="forbid"` (práctica común para endurecer APIs), rompe silenciosamente el rolling upgrade. Peor: no hay forma de *detectar* skew de versiones — el escenario real es un daemon residente en memoria de la versión N mientras el CLI se actualiza a N+1 (el upgrade in-place de los 3 SO no detiene el daemon); un cambio semántico o un campo requerido nuevo produce `DaemonIPCError` crípticos sin diagnóstico posible, porque `/health` (`HealthResponse`: `status`, `model_loaded`, `uptime_seconds`) no expone ninguna versión.

**Alternativas evaluadas:**

1. **Añadir `schema_version: str = "1"` a cada uno de los 5 modelos** (propuesta original): funciona, pero duplica el campo 5 veces y un modelo futuro puede omitirlo — mismo defecto estructural que S2-02.
2. **Clase base común del protocolo** (`class ProtocolModel(BaseModel): schema_version: str = "1"` + `model_config = ConfigDict(extra="ignore")` explícito) de la que hereden los 5 modelos, **más** un campo `version` (la del paquete) en `HealthResponse`.
3. **Versionar el endpoint** (`/v1/synthesize` o content negotiation): sobredimensionado para IPC loopback en la misma máquina con un solo cliente conocido; añade superficie de routing sin consumidor que la necesite.

**Solución implementada: (2).** Criterio: un solo punto de verdad para la versión del esquema y para la política de extras — la herencia hace que todo modelo futuro nazca versionado y tolerante por contrato, no por default implícito. `version` en `HealthResponse` habilita el diagnóstico del caso real de skew: `is_running` (ipc.py:78) ya valida identidad estructural, y con la versión el CLI puede diagnosticar «daemon corriendo con versión anterior; ejecuta daemon restart». La política de compatibilidad (cambios aditivos con default ⇒ misma `schema_version`; ruptura ⇒ bump) quedó escrita en `docs/DAEMON-MODE.md` §«Versionado del protocolo». Cambio 100% aditivo: cliente viejo ignora los campos nuevos, server viejo + cliente nuevo se completa con los defaults. Evidencia: `daemon/protocol.py::ProtocolModel`, `daemon/server.py::health_check` (puebla `version=__version__`), `tests/test_protocol.py::TestProtocolVersioning` (schema_version en los 5 modelos, tolerancia a extras — skew hacia adelante, defaults ante campos ausentes — skew hacia atrás).

#### S2-06 — Cobertura `--json` enumerativa, sin verificación estructural del contrato [Resuelto]

**Problema (re-alcance).** La evidencia original («faltan tests para setup, cleanup») quedó obsoleta: `TestWriteCommandsJSON` (test_cli.py:1586-1726) y `TestSchemaVersionJSON` (test_cli.py:1740-1795) ya cubren esos comandos. El problema real es que la cobertura es **enumerativa y manual**: las clases listan comandos a mano, así que un subcomando nuevo con `--json` (p. ej. los de S2-01/S2-02) puede quedar fuera del contrato sin que ningún test falle. El drift de S2-03/S2-04 en esta auditoría es el síntoma de la misma causa: no existe una fuente única de «qué comandos participan del contrato JSON».

**Alternativas evaluadas:**

1. **Añadir los tests faltantes uno a uno** conforme aparezcan comandos: mantiene el modelo manual y su modo de fallo (olvido silencioso).
2. **Test parametrizado sobre un registro derivado del propio parser**: introspección del argparse (`build_parser()`) para descubrir todo subcomando que declare `--json`, y para cada uno validar las invariantes del contrato — stdout parsea como *exactamente un* objeto JSON, `schema_version` presente, stderr sin JSON. Una lista corta de exclusiones explícitas (`serve`) documenta las excepciones deliberadas.

**Solución implementada: (2).** Criterio: el contrato pasa de checklist a propiedad verificada — un comando nuevo con `--json` entra automáticamente al test, y quitar el flag de un comando existente rompe el test (protección bidireccional contra drift). Evidencia: `cli.py::build_parser`/`top_level_subparsers` (parser extraído de `main()`, introspeccionable), `tests/test_cli.py::TestJSONContractStructure` (descubre desde el parser real el conjunto de comandos con `--json` y lo compara contra `_JSON_COVERED_COMMANDS`; verifica la exclusión deliberada de `daemon serve`).

---

### 3. Daemon lifecycle & concurrency — [LISTO]

**Qué está listo:**
- Start idempotente + lock atómico os.open(O_CREAT\|O_EXCL) (daemon.py:377-397); PID escrito tras Popen
- PID file autoritativo: stop() detecta PID vivo en pidfile → avisa "arrancando" + exit 5 sin matar (daemon.py:153-172)
- Stale reclaim: PID muerto/ajeno → limpia; archivo vacío >120s → reclama (daemon.py:399-422)
- Admisión: BoundedSemaphore(4) (1 activa + 3 espera); 5ª request → 503 inmediato sin hilo (server.py:106,191-195)
- /health responde 200 durante síntesis (threadpool FastAPI desacopla) — test TestServerConcurrency ✅
- Sandbox audio: realpath único, .wav, existencia, contención allowed_dirs, header RIFF/WAVE; pasa real_path a engine (cierra symlink-swap) (server.py:109-144,177-187)
- Limpieza memoria: _clear_model_memory() (CUDA empty_cache + gc.collect) en finally de worker y en /shutdown (server.py:53-71,255,322)
- Bind exclusivo 127.0.0.1:8765 (run.py:135)
- EADDRINUSE/WSAEADDRINUSE → exit 6 (EXIT_DAEMON_PORT_IN_USE); auto-restart no reintenta bind fallido (run.py:143-152, test_daemon.py:1051-1079)
- Cancelación cooperativa: GeneratorExit → cancel_event.set() → push() eleva SynthesisCancelled → worker aborta, no emite result/error, libera semáforo/memoria (server.py:201-283, test_daemon.py:1093-1258)
- Shutdown graceful: server.should_exit=True, engine=None, clear_model_memory() (server.py:295-324)
- Kill verifica identidad por cmdline markers (tts_sidecar.daemon, daemon serve) — proceso ajeno no se mata (daemon.py:321-344)
- Cobertura de tests completa: 11/11 escenarios clave cubiertos en test_daemon.py (concurrencia, admisión, sandbox, PID lock, bind fail, cancelación, health identity, shutdown, kill verify, stop window, PID file)

**Hallazgos S0/S1:** Ninguno bloqueante

---

### 4. Model & on-disk state management — [LISTO]

**Qué está listo:**
- setup idempotente: is_model_cached() valida snapshot pin + 3 checkpoints + ve.safetensors con header safetensors (model_cache.py:152-193); 2ª ejecución → "Provisión completa. No hay nada que descargar."
- Detección corrupto: _safetensors_header_ok() lee 8 bytes magic + header-length; truncado → False (model_cache.py:64-88, test_engine_cache.py:402-420)
- --force-update: borra SOLO models--ResembleAI--* (guarda quirúrgica RuntimeError si fuera) y re-descarga misma revisión + VE (cli.py:1247-1268,1337-1356)
- Offline: _describe_provision_failure() clasifica credenciales/red/disco/permisos → mensaje accionable (cli.py:1125-1178); speak/daemon start → exit 2 remitiendo a setup (cli.py:212-221,268,1497,1512)
- Pre-chequeo disco: shutil.disk_usage(probe) >= 2GB antes de snapshot_download (cli.py:1307-1325)
- VE provisionado en setup si falta (cli.py:1346-1356)
- cleanup --all quirúrgico: solo models--ResembleAI--* + voices_root(); --dry-run lista sin borrar; --yes omite confirmación; EOF → cancela limpio (exit 0, sin traceback) (cli.py:1386-1485, test_cli.py:1083-1201)
- data_root vacío → rmdir tras cleanup encadenado en uninstall (cli.py:828-835, test_cli.py:1461-1474)
- Gate _require_model_cached() en speak (L268), daemon start (L1512), serve (L1497)
- .incomplete purge tras provisión exitosa (_purge_incomplete() en cli.py:1285-1298,1303,1360)

**Hallazgos:** Ninguno

---

### 5. Real cross-platform compatibility — GAPS MEDIOS

**Qué está listo:**
- data_root() user-data-dir por SO, igual en 3 modos (paths.py:51-65)
- bundled_voices_dir() resuelve MEIPASS/voices (congelado) y pkg/voices (fuente/pip) (paths.py:82-94)
- Audio devices: enumera runtime real (pycaw/sounddevice/afplay); degraded=True si subsistema falla (audio.py:160-215)
- Compute backend: detección CUDA→MPS→CPU con try/except; cache_key incluye backend (compute_backend.py:16-49)
- macOS ARM64 only: build e installer rechazan x86_64 con mensaje + alternativa PyPI (build_macos.py:71-74, install-macos.sh:51-55)
- Windows per-user: Inno PrivilegesRequired=lowest, DefaultDirName={localappdata}\Programs\tts-sidecar, HKCU PATH, legacy HKLM detect+warn (create_installer_windows.py:65-76,116,120-140)
- AVX2 check: Linux /proc/cpuinfo, macOS sysctl, Windows SKIP informativo; WARN no FAIL en doctor/setup (cli.py:569-613)
- Paths con espacios/acentos/Unicode manejados ✅

**Hallazgos S2 (Medio):**

| ID | Estado | Título |
|----|--------|--------|
| S2-07 | Abierto (re-alcance) | El piso de glibc del AppImage no está declarado como invariante del build |
| S2-08 | Abierto | OneDrive puede redirigir el user-data-dir de Windows sin detección |

#### S2-07 — El piso de glibc del AppImage es implícito, no una invariante declarada del build

**Problema (re-alcance).** La propuesta original («mover el check de `install-linux.sh` a `build_linux.py`») confunde dos chequeos distintos. El de `install-linux.sh:59-76` valida la glibc de la **máquina del usuario final** contra el piso 2.35 — correcto y debe quedarse. Lo que falta en el build es otra cosa: el piso 2.35 es una consecuencia implícita de *dónde* se compila (Ubuntu 22.04 en CircleCI), no una invariante declarada. Si el runner de CI migra a Ubuntu 24.04 (glibc 2.39), el AppImage sube su piso real en silencio: el installer seguiría validando «≥2.35», dejaría instalar en máquinas 2.35-2.38, y el binario fallaría en runtime con un error de loader críptico. El número, además, está duplicado sin fuente única: hardcodeado en `install-linux.sh` y en la prosa de `USAGE.md`/`README.md`.

**Alternativas evaluadas:**

1. **Chequear la glibc del host de build con `ldd --version`** (lectura literal de la propuesta original): no protege nada — el build siempre pasa en su propio host; el riesgo es el *cambio* de host, no un host inválido.
2. **Declarar el piso como constante única (`GLIBC_FLOOR = (2, 35)` en `build_utils.py`) y verificarlo en `build_linux.py` contra la glibc del host de build**: si el host compila sobre una glibc **mayor** que el piso declarado, el build aborta con el mensaje «el AppImage resultante requeriría glibc > piso documentado: sube el piso deliberadamente o compila en la base correcta». `install-linux.sh` y la documentación derivan del mismo valor (inyectado al generar/testear el script, verificable con un test de consistencia como el existente `test_pin_consistency.py`).
3. **Verificación post-build del artefacto**: inspeccionar los símbolos versionados del bundle (`objdump -T ... | grep GLIBC_` sobre los `.so` del onedir) y abortar si aparece un requisito mayor al piso declarado. Es la verificación más veraz (mide el artefacto, no el entorno), a costa de un paso de build adicional.

**Solución recomendada: (2), con (3) como refuerzo opcional en CI.** Criterio: convertir un acoplamiento implícito entre infraestructura (imagen del runner) y contrato de compatibilidad (piso documentado al usuario) en una invariante declarada con fuente única y verificación fail-fast. El escenario que rompe usuarios —migración silenciosa del runner— pasa de indetectable a error de build explícito, y el número deja de poder divergir entre build, installer y docs porque solo existe en un lugar.

#### S2-08 — OneDrive puede redirigir el user-data-dir de Windows sin detección

**Problema (refinado).** `data_root()` en Windows resuelve `LOCALAPPDATA` (paths.py:56-57). `%LOCALAPPDATA%` **no** es redirigido por la función estándar «Known Folder Move» de OneDrive (que mueve Documents/Desktop/Pictures), pero sí queda dentro del perfil sincronizado en configuraciones corporativas de roaming/redirección de perfil, y hay entornos donde el perfil entero vive bajo la jerarquía de OneDrive. El impacto real: las voces de usuario (WAVs que el daemon lee durante síntesis) quedarían bajo un directorio con file locks intermitentes del cliente de sincronización y placeholders «archivos a petición» (el archivo existe en el namespace pero su contenido no está hidratado), produciendo fallos esporádicos de lectura difíciles de atribuir. Es un riesgo de **entorno del usuario**, no un defecto del código: la solución debe ser diagnóstico accionable, no reubicación.

**Alternativas evaluadas:**

1. **Fallback automático a otra base** (p. ej. `APPDATA`) si se detecta OneDrive: peligroso y regresivo — cambiar `data_root()` según el entorno rompería la invariante «misma ruta en los tres modos de ejecución» que el diseño de `paths.py` garantiza deliberadamente, partiría las instalaciones existentes (voces que "desaparecen" tras activar OneDrive) y crearía un estado bimodal imposible de soportar. Descartada.
2. **Check informativo en `doctor`/`setup`**: detectar si `data_root()` resuelve bajo una raíz de OneDrive (variables `OneDrive`/`OneDriveCommercial`, o el patrón de ruta) y emitir **WARN** (no FAIL) con el riesgo y la mitigación («excluye la carpeta de la sincronización o deshabilita Files On-Demand para ella»). Encaja en el patrón ya establecido del chequeo AVX2 (cli.py:569-613): WARN informativo por SO, sin bloquear.
3. **Hidratación forzada al leer** (abrir con flags que fuercen descarga del placeholder): trata el síntoma en un punto (lectura de voz) pero no cubre escrituras (`voice add`), locks del cliente de sync, ni deja rastro diagnóstico; complejidad Win32 (atributos `FILE_ATTRIBUTE_RECALL_*`) desproporcionada.

**Solución recomendada: (2).** Criterio: ante un riesgo ambiental que el software no controla, la respuesta arquitectónicamente honesta es visibilidad y diagnóstico en el punto de provisión (donde el usuario ya está mirando), no heurísticas que muten el layout de datos. Mantiene la invariante de rutas —el activo estructural más valioso de `paths.py`— intacta, es puramente aditiva (un chequeo más en la lista de `doctor`) y convierte un fallo esporádico inatribuible en una advertencia temprana con acción concreta.

---

### 6. End-to-end install/uninstall UX — [LISTO]

**Qué está listo:**
- 3 one-liners validan prereqs (install-linux.sh:36-40, install-macos.sh:40-46, install-windows.ps1:36-40,48,78,94)
- 3 verifican SHA256SUMS.txt antes de instalar (install-linux.sh:110-111, install-macos.sh:96-97, install-windows.ps1:84-99 + tests bats/ps1)
- 3 per-user, sin admin (Linux ~/.local/opt, macOS ~/Applications + ~/.local/bin, Win %LOCALAPPDATA%\Programs + HKCU PATH)
- 3 encadenan setup al final (install-linux.sh:137-139, install-macos.sh:159, install-windows.ps1:150, Inno [Run] checkbox)
- Linux limpia AppImages viejos, macOS ditto replace, Win Inno in-place ✅
- Modelo (HF cache) + voces (user-data-dir) sobreviven upgrade en 3 SO ✅
- setup --uninstall unificado data→PATH→binario, cancelación atómica ✅ (cli.py:882-1123, test_cli.py:1383-1404)
- Homebrew Cask deferral a brew uninstall --cask --zap ✅ (cli.py:988-1000)
- Windows: valida QuietUninstallString HKCU antes de cleanup; Inno revierte HKCU PATH antes de borrar archivos ✅ (cli.py:1074-1093, create_installer_windows.py:145-167)
- Upgrade v2 sobre v1: modelo + voces preservados (ubicaciones separadas) ✅
- Smoke tests BATS/Pester: mockean red + filesystem, validan flujo completo sin instalación real ✅

**Hallazgos:** Ninguno

---

### 7. Test quality & coverage — GAPS MEDIOS

**Qué está listo:**
- 536 tests, 100% deterministas (zero network, zero hardware, zero timing flakiness)
- CI triple-platform simétrico: test-linux (Docker), test-windows (Server 2022), test-macos (M4 Pro) — misma suite, gates obligatorios
- Smoke test binario congelado en cada build job: version + voice list \| grep 'default'
- Contract tests exhaustivos: exit codes, JSON schema_version, stdout/stderr separation, NDJSON events
- Unit/Integration ratio: ~75% unit (mocks pesados), ~25% integration (TestClient, installer scripts)

**Hallazgos:**

| ID | Estado | Título |
|----|--------|--------|
| S3-01 | **Resuelto** | PyInstaller timeout sin test — cubierto por `tests/test_build_utils.py::TestRunPyinstaller::test_timeout_kills_tree_and_returns_1` |
| S2-09 | Abierto | Sin herramienta de coverage: la cobertura se afirma, no se mide |
| S2-10 | Abierto | Ramas de fallo de los build scripts sin test |
| S2-11 | Abierto | create-dmg sin pin (consolidado con S2-15 — misma causa raíz, ver Dimensión 10) |
| S2-12 | Abierto | Rama «Inno Setup ausente» sin test (subcaso de S2-10) |
| S2-13 | **Resuelto** | `scripts/pyinstaller_wrapper.py` sin test dedicado — cubierto por `tests/test_build_utils.py::TestPyinstallerWrapper` (`main()` propaga `returncode` vía `os._exit` y limpia el temporal; `_BOOTSTRAP` fija `coinit_flags` antes del import) |

#### S2-09 — Sin herramienta de coverage: la cobertura se afirma, no se mide

**Problema (refinado).** La suite (536 tests, determinista, triple-plataforma) es fuerte, pero su cobertura es una afirmación sin instrumento: ni `pyproject.toml` tiene `pytest-cov`/`[tool.coverage.*]`, ni ningún job de CI lo ejecuta (comentario explícito en `.circleci/config.yml`: «Hoy el proyecto NO usa plugins de pytest»). Sin medición, los huecos son invisibles precisamente donde más duele: las ramas de fallo (S2-10) existieron durante meses sin que nadie pudiera verlas. El riesgo del remedio también es real y debe gobernar el diseño: un umbral global mal calibrado convierte coverage en ruido (tests triviales para «subir el número») o en fricción (PRs bloqueados por líneas inalcanzables).

**Alternativas evaluadas:**

1. **`--cov` global con `--cov-fail-under=80` en los 3 jobs** (propuesta original): mide, pero el umbral global es una métrica vanidosa — promedia módulos críticos con código defensivo por SO (las ramas darwin/win32/linux de `paths.py`, `audio.py` son estructuralmente inalcanzables desde un solo runner), invitando a excepciones ad hoc.
2. **Medición por módulo con umbrales diferenciados**: `pytest-cov` pineado (mismo mecanismo `pipeline.parameters` que ya pinea `pytest`), configuración en `[tool.coverage.*]` de `pyproject.toml` como fuente única; umbral estricto para los módulos del contrato (`cli.py`, `daemon/*`, `model_cache.py`, `voices.py`, `paths.py`) y reporte-sin-gate para el resto; exclusiones declaradas en config (`pragma: no cover` para ramas por-SO), no acordadas informalmente. Un solo job (test-linux) publica `coverage.xml` como artefacto; los otros dos no duplican el gate (la suite es la misma — medir tres veces triplica costo sin información nueva; las ramas específicas de SO se excluyen por config precisamente por eso).
3. **Coverage diferencial (solo líneas nuevas del PR)**: excelente régimen de crucero, pero requiere infraestructura de comparación base-vs-PR que el pipeline actual no tiene; prematuro como primer paso.

**Solución recomendada: (2), con (3) como evolución natural pos-1.0.0.** Criterio: el propósito de coverage aquí no es un número sino un detector de huecos en los módulos donde un hueco es un bug de contrato. Umbrales por módulo alinean el gate con el riesgo real; la config en `pyproject.toml` mantiene la fuente única que el proyecto ya practica (lockfiles, versión, pins); pinear `pytest-cov` preserva la política de supply chain existente. El comentario de CI que documenta «sin plugins» debe actualizarse en el mismo cambio — es parte del contrato del pipeline, no un detalle.

#### S2-10 — Ramas de fallo de los build scripts sin test (incluye S2-12)

**Problema (refinado).** Los caminos felices de los 3 build scripts están testeados (`test_build_linux.py`, `test_build_macos.py`, `test_build_windows.py`), pero las ramas de fallo — las que protegen al pipeline cuando el entorno se degrada — no: `create_installer_windows.py:247-260` aborta si falta Inno Setup (S2-12), `build_macos.py:211-214` aborta si `create-dmg` falla, y las degradaciones opcionales (tooling AppImage no provisionable) solo warnean. Son precisamente las ramas que se ejecutan cuando algo ya va mal, es decir, cuando un bug en ellas cuesta más (enmascara la causa raíz o convierte un abort limpio en un traceback). Hay además una incoherencia de diseño detectada al auditar: tanto Inno como create-dmg se declaran `required=False` en `ensure_build_dependency` pero su ausencia/fallo es fatal de facto vía `sys.exit(1)` manual — la criticidad real vive fuera del mecanismo que existe para declararla.

**Alternativas evaluadas:**

1. **Tests puntuales de cada rama con mocks** (propuesta original): cubre, pero deja la incoherencia `required=False`+abort-manual intacta; los tests certificarían un diseño confuso.
2. **Primero normalizar la semántica de criticidad, luego testearla**: declarar `required=True` donde el fallo es fatal (Inno, create-dmg) eliminando los `sys.exit(1)` manuales redundantes — la política de abort queda en un solo lugar (`ensure_build_dependency`, ya testeado exhaustivamente en `TestEnsureBuildDependency`) — y añadir los tests de rama de fallo por script: Inno ausente → abort con mensaje accionable (S2-12), `create-dmg` con returncode ≠ 0 → abort, tooling AppImage no disponible → degradación con warning (no abort). Mismo patrón de mocks/fakes ya establecido en `TestRunPyinstaller`/`TestPyinstallerWrapper`.

**Solución recomendada: (2).** Criterio: testear una rama de fallo incoherente la fosiliza; alinear primero la declaración de criticidad con el comportamiento real reduce el código a testear (menos ramas ad hoc) y concentra la política en el componente compartido cuyo contrato ya está verificado. S2-12 deja de ser un hallazgo aparte: es el caso Inno de esta misma corrección, y se cierra con ella.

#### S2-11 — create-dmg sin pin

Consolidado con **S2-15** (Dimensión 10): son el mismo defecto observado desde dos lentes (test/supply-chain). Análisis y solución únicos en S2-15 para evitar que dos correcciones divergentes ataquen la misma causa.

#### S2-12 — Rama «Inno Setup ausente» sin test

Subsumido en **S2-10** (es su caso Windows). Ver la solución allí.

**S0/S1 positivos:** Suite determinista, CI simétrico, smoke tests en todos los builds, contract tests completos.

---

### 8. Documentation as product — GAPS MENORES

**Qué está listo:**
- 100% CLI commands/flags/docs coinciden con implementación (cli.py argparse vs README/USAGE)
- 3 audiencias servidas: usuario final (README/USAGE), integrador (exit codes, JSON schemas, subprocess patterns), empaquetador (BUILD.md)
- CHANGELOG Keep a Changelog + SemVer ✅
- PARITY.md v0.6.0 refleja estado real ✅
- DAEMON-MODE.md falta sección cancelación cooperativa (añadida en CHANGELOG Unreleased) ❌ (S1)
- README/USAGE/SECURITY/BUILD tienen troubleshooting actionable (SmartScreen, Gatekeeper, glibc, AVX2, headless) ✅
- Cross-refs: USAGE.md:175 anchor roto (README.md#instalación-de-una-línea-linux-y-windows no existe; real es #instalación-de-una-línea) ❌ (S0)
- GPLv3 source offer solo en GitHub Release notes, NO en instaladores nativos ⚠️

**Hallazgos S0/S1:**

| ID | Estado | Severidad | Título |
|----|--------|-----------|--------|
| S1-01 | Abierto | S1 — Bajo | DAEMON-MODE.md no documenta la cancelación cooperativa |
| S0-01 | Abierto | S0 — Info | Anchor roto USAGE.md:175 |
| S0-02 | Abierto | S0 — Info | Orden de flags `--voice-audio`/`--speech-audio` difiere entre USAGE y cli.py (no contradictorio) |

#### S1-01 — DAEMON-MODE.md no documenta la cancelación cooperativa

**Problema (refinado).** La cancelación al desconectar el cliente (S2-04 del sprint anterior: `GeneratorExit` → `cancel_event` → `SynthesisCancelled`, server.py:201-283) cambió el comportamiento observable del daemon —una request abandonada ya **no** consume GPU/CPU hasta terminar, no emite `result`/`error`, y libera el slot de admisión— pero `docs/DAEMON-MODE.md` sigue describiendo el modelo anterior. Para un integrador que consume el NDJSON, «qué pasa si cierro la conexión a mitad de síntesis» es parte del contrato, no un detalle interno: sin documentarlo, el comportamiento correcto parece un bug (stream sin evento terminal).

**Solución recomendada.** Añadir a `DAEMON-MODE.md` la sección «Cancelación cooperativa del cliente» describiendo el contrato observable (desconexión ⇒ aborto best-effort durante la fase T3, sin frame terminal, semáforo y memoria liberados) y su límite deliberado (S3Gen no instrumentado: la cancelación durante el vocoder espera a que la etapa termine). Documentar el límite es tan importante como la funcionalidad — evita el reporte de bug «cancelé y siguió consumiendo unos segundos». Criterio de mantenibilidad: la fuente ya existe (entrada del CHANGELOG `[Unreleased]`); la tarea es promoverla de historial de cambios a documento de contrato, que es donde el integrador la busca.

#### S0-01 / S0-02 — Exactitud documental menor

**Problema.** Anchor roto en `USAGE.md:175` (apunta a `#instalación-de-una-línea-linux-y-windows`; el real es `#instalación-de-una-línea`) y orden de flags distinto entre `USAGE.md:406-407` y `cli.py:1578-1582` (cosmético, no contradictorio).

**Solución recomendada.** Corregir el anchor y alinear el orden de flags en la misma pasada documental de S1-01 (un solo commit `docs:`). Sin análisis de alternativas: son correcciones deterministas. Nota preventiva con criterio de largo plazo: los anchors entre documentos son enlaces sin verificación automática — si vuelven a romperse con frecuencia, considerar un chequeo de enlaces internos en CI (p. ej. lychee sobre `*.md`), pero no antes de que el problema reincida; instrumentar contra un incidente único es sobre-ingeniería.

---

### 9. Licensing & compliance — GAPS MENORES

**Qué está listo:**
- Código GPL-3.0-or-later, deps compatibles ✅
- Chatterbox MIT confirmado compatible ✅
- Watermark bypass documentado en README/USAGE/SECURITY ✅
- GPLv3 §6 source offer inyectado en Release notes (RELEASING.md:101-105) ✅
- THIRD-PARTY-LICENSES.md vs lockfiles: no verificado exhaustivamente ⚠️
- Voice cloning ethics notice presente ✅
- SECURITY.md: política reporte, unsigned artifacts note, supply chain ✅

**Hallazgos S1/S2:**

| ID | Estado | Severidad | Título |
|----|--------|-----------|--------|
| S2-14 | Abierto | S2 — Medio | GPLv3 §6 source offer solo en GitHub Release, no en los artefactos nativos |
| S1-02 | Abierto | S1 — Bajo | THIRD-PARTY-LICENSES.md sin verificación automatizada contra los lockfiles |

#### S2-14 — La oferta de código fuente GPLv3 §6 no viaja con los artefactos nativos

**Problema (refinado).** El pipeline inyecta la oferta de fuente (tarball del tag + enlace) en las Release notes de GitHub (`docs/RELEASING.md:101-105`), pero la obligación de GPLv3 §6 acompaña a la **distribución del binario**, no a la página desde donde se descargó: quien recibe el instalador por otra vía (copia directa, mirror, one-liner que no muestra las notes) recibe el objeto sin la oferta. Los artefactos ya llevan `LICENSE` y `THIRD-PARTY-LICENSES.md` dentro del bundle (`copy_license_files`, build_utils.py:349-361; Inno además muestra `LicenseFile` en el wizard, create_installer_windows.py:87-88) — lo que falta es específicamente la **oferta escrita de dónde obtener la fuente correspondiente a esa versión exacta**.

**Alternativas evaluadas:**

1. **Añadir la oferta a las superficies de cada instalador** (Inno `InfoAfterFile`, ReadMe en la raíz del `.dmg`, `caveats` del Cask — propuesta original): tres superficies distintas, tres plantillas por-SO que mantener sincronizadas, y ninguna cubre el AppImage (que no tiene «pantalla» de instalación). Frágil por multiplicidad.
2. **Un archivo canónico dentro del bundle** — `SOURCE-OFFER.md` (o sección al final de `THIRD-PARTY-LICENSES.md`) generado en build con la URL del tarball del tag y el enlace al tag de esa versión, distribuido por el mecanismo ya existente (`copy_license_files`/`LICENSE_FILES`): viaja **dentro de los 4 artefactos** (AppImage, `.dmg`, instalador Inno, wheel) por construcción, con un solo punto de generación. Las superficies visibles (Inno `InfoAfterFile`, Cask `caveats`) pueden *referenciarlo*, pero dejan de ser el mecanismo de compliance.
3. **Solo documentar que la oferta está en las Release notes**: no resuelve la obligación (la nota no acompaña al binario redistribuido).

**Solución recomendada: (2).** Criterio: el compliance debe ser una propiedad del artefacto, no del canal de distribución — un archivo dentro del bundle sobrevive a cualquier vía de redistribución, cubre los 4 formatos con un mecanismo que ya existe y ya está testeado, y tiene un único punto de verdad (la plantilla + la versión, ambas ya únicas en el build). La stanza `license "GPL-3.0-or-later"` del Cask (`render_cask.py`) es un complemento trivial del mismo cambio: metadata correcta en el índice de Homebrew, aunque no sustituye la oferta.

#### S1-02 — THIRD-PARTY-LICENSES.md sin verificación automatizada

**Problema (refinado).** El inventario se regenera **manualmente** con `pip-licenses` desde `requirements-lock.txt` (las instrucciones viven dentro del propio archivo, líneas 337-339); `docs/RELEASING.md` ni siquiera lo menciona como paso del release. Consecuencia estructural: cada cambio de dependencias puede desincronizar el inventario en silencio — es exactamente la misma clase de drift documental que esta auditoría encontró en sí misma (S2-03/S2-04), aplicada a un documento con peso legal (GPLv3 exige atribuciones correctas de lo que se redistribuye).

**Alternativas evaluadas:**

1. **Regeneración automática en CI en cada build**: elimina el drift pero introduce no-determinismo (el formato/metadata de `pip-licenses` puede variar entre versiones) y commits generados por el pipeline, que el flujo actual (release desde tag humano) no contempla.
2. **Verificación (no regeneración) en CI**: un script en `scripts/` que derive el conjunto de paquetes del lockfile, lo compare con los paquetes listados en `THIRD-PARTY-LICENSES.md`, y falle con diff legible si hay faltantes/sobrantes; correr como paso barato del job test-linux. La regeneración sigue siendo humana (con el script como guía), pero la **desincronización deja de ser silenciosa**. Añadir la regeneración como paso del runbook en `docs/RELEASING.md`.
3. **Solo documentar el paso en el runbook**: depende de disciplina humana; es el estado que ya falló.

**Solución recomendada: (2).** Criterio: distinguir entre *generar* (proceso humano, deliberado, con revisión — apropiado para un documento legal) y *verificar* (proceso mecánico, barato, sin juicio — apropiado para CI). El gate convierte el contrato «el inventario refleja el lockfile» en propiedad verificada con el mismo patrón que el proyecto ya usa para pins (`test_pin_consistency.py`), sin ceder la autoría del documento al pipeline.

---

### 10. Supply chain & CI — GAPS MEDIOS

**Qué está listo:**
- 3 lockfiles totalmente pinned con hashes, --require-hashes en CI ✅
- Tooling pins: appimagetool+runtime (SHA256), Inno 6.3.3, pyenv git tag ✅
- create-dmg sin pin (Homebrew) ❌ (S2)
- Build reproducibility: lockfiles + --noupx + single-source version ✅
- Unsigned artifacts: solo SHA-256 en Release logs, mitigación documentada (one-liners, PyPI) ⚠️
- Post-build validation: smoke test en todos los 4 builds ✅
- Publish gates: 3 contextos aislados + regeneración Cask ✅
- fetch_pinned_asset valida SHA256 antes de usar; mismatch = abort ✅ (build_utils.py:157-195)
- CUDA isolation: CPU-only lock + extra-index-url pytorch/cpu + unsafe-best-match, nvidia-* solo x86_64 (requirements-lock.txt:1050-1203)
- PyPI smoke test pre-publish (venv limpio + version + voice default) ✅
- Release = público = irreversible (borrar Release + re-tag); PyPI solo yank+nueva versión; Cask idempotente ✅

**Hallazgos S2:**

| ID | Estado | Título |
|----|--------|--------|
| S2-15 | Abierto | create-dmg sin pin — única dependencia de build no reproducible (consolida S2-11) |

#### S2-15 — create-dmg sin pin: la única dependencia de build fuera de la política de reproducibilidad

**Problema (refinado; consolida S2-11).** Todo el tooling de build está pineado (lockfiles con hashes + `--require-hashes`, appimagetool/runtime por SHA-256 vía `fetch_pinned_asset`, Inno 6.3.3, pyenv por git tag) **excepto** `create-dmg`: el job macOS ejecuta `brew install create-dmg` sin versión (`.circleci/config.yml`, con `HOMEBREW_NO_AUTO_UPDATE=1` que mitiga la variabilidad intra-runner pero no fija nada entre ejecuciones), y `build_macos.py:60-68` lo detecta vía `ensure_build_dependency(..., required=False)` aunque su fallo en el stage DMG es fatal (`sys.exit(1)`, líneas 211-214). Dos datos del código acotan el problema mejor que el enunciado original: (a) `create-dmg` es un **script de shell puro** distribuido por Homebrew — no un binario compilado ni un paquete Python; (b) su papel aquí es esencialmente de empaquetado con layout (el paso cosmético de Finder ya se omite con `--skip-jenkins` en CI). Es decir: la única pieza no reproducible del pipeline es también una de las más simples de fijar.

**Alternativas evaluadas:**

1. **`brew install create-dmg@<versión>`**: no existe fórmula versionada de create-dmg en homebrew-core; Homebrew no soporta instalar versiones arbitrarias de fórmulas sin tap propio. No viable tal cual.
2. **Pinnear el bottle de Homebrew por SHA-256**: los bottles de create-dmg son artefactos de la infraestructura interna de Homebrew (GitHub Packages con tokens de rotación); descargarlos fuera de `brew` es frágil y no soportado. Descartada.
3. **`fetch_pinned_asset` sobre el tarball del release de GitHub de create-dmg** (patrón appimagetool ya existente): descargar `https://github.com/create-dmg/create-dmg/archive/refs/tags/v<X.Y.Z>.tar.gz` con SHA-256 pineado en `build_utils.py`, extraer y ejecutar el script directamente (es shell puro, sin instalación ni dependencias más allá de las herramientas del sistema `hdiutil`/`osascript` que macOS trae). Elimina Homebrew de la ecuación para esta dependencia.
4. **Sustituir create-dmg por `hdiutil` directo**: máximo control (herramienta del SO, cero dependencia externa) al precio de reimplementar el layout del volumen (background, posiciones, applink) a mano en `build_macos.py`; más código propio que mantener para replicar lo que create-dmg ya resuelve.

**Solución recomendada: (3).** Criterio: reutilizar el patrón de pinning que el proyecto ya tiene implementado, testeado (`TestFetchPinnedAsset`) y documentado, aplicado al origen canónico del tool (su release en GitHub) en lugar de a un empaquetador intermedio (Homebrew) que no ofrece pinning. Uniformiza la política de supply chain — toda dependencia de build queda fijada por contenido, no por «lo último que Homebrew tenga» — y de paso permite eliminar el step `brew install` del job macOS (menos superficie de red y menos tiempo de job). El cambio debe acompañarse de la normalización de criticidad de S2-10 (`required=True`, ya que sin create-dmg no hay `.dmg`) y del bump documentado del pin en `docs/BUILD.md` §Reproducibilidad, donde hoy la excepción de create-dmg está reconocida como deuda («Homebrew no pinea»). (4) queda registrada como salida de emergencia si upstream create-dmg quedara sin mantenimiento: el formato del volumen es estable y `hdiutil` es API del SO.

---

## Release gate (S4 + S3 mínimos para release)

| Hallazgo | Severidad | Debe resolverse antes de release |
|----------|-----------|----------------------------------|
| S3-01 | S3 — Alto | **Resuelto** — cubierto por `tests/test_build_utils.py::TestRunPyinstaller` (timeout) y `tests/test_build_utils.py::TestPyinstallerWrapper` (wrapper COM) |
| S2 abiertos (6) | S2 — Medio | **RECOMENDADO** — No bloquean técnicamente, pero degradan calidad y operabilidad |
| S1-01, S1-02 | S1 — Bajo | No — solo docs/compliance menor |
| S0 | S0 — Info | No — solo pulido |

---

## Recomendación global de madurez

**LISTO-CON-RESERVAS** — El proyecto **cumple funcionalmente** para un release 0.6.1 (todas las brechas accionables de PARITY.md cerradas en código/tests, paridad UX completa en 3 SO). Los hallazgos S2 abiertos son **de hardening pre-1.0.0**, no bloquean release de mantenimiento.

**Plan sugerido** (con las dependencias entre soluciones refinadas):
1. Release 0.6.1 con fixes P0: pin de create-dmg vía `fetch_pinned_asset` (S2-15) + coverage por módulo con `pytest-cov` pineado (S2-09).
2. ~~Sprint 0.7.0 — contrato `--json` completo~~ — **completado el 2026-07-14**: helper `emit_json` + `--json` en `daemon start/stop/restart` (S2-02), `speak --json` acoplado a `--output` sobre `SynthesisResult` (S2-01), test estructural del contrato derivado de `build_parser()` (S2-06), y clase base versionada del protocolo NDJSON + `version` en `/health` + política de compatibilidad en DAEMON-MODE.md (S2-05). Ver detalle y evidencia en la Dimensión 2.
3. Sprint 0.7.x — P1 restante: normalización de criticidad en `ensure_build_dependency` + tests de ramas de fallo (S2-10, cierra S2-12); `GLIBC_FLOOR` como invariante única del build (S2-07); check OneDrive en `doctor` (S2-08); `SOURCE-OFFER.md` en los 4 artefactos (S2-14).
4. Pasada documental única: DAEMON-MODE.md cancelación cooperativa (S1-01) + anchor y orden de flags (S0-01/S0-02); verificación de THIRD-PARTY-LICENSES en CI (S1-02).
5. 1.0.0 cuando P1/P2 cerrados + validación E2E usuarios reales Linux/macOS (criterio aceptación 10 GOAL.md).

---

## Confirmación en CI

| Hallazgo | Cómo se confirmará en CI |
|----------|---------------------------|
| S2-09 coverage | `pytest --cov` con `[tool.coverage.*]` en pyproject.toml; gate por módulo en módulos de contrato; `coverage.xml` como artefacto del job test-linux |
| S2-15 create-dmg pin | Build macOS obtiene create-dmg vía `fetch_pinned_asset` (log muestra SHA-256 verificado); step `brew install create-dmg` eliminado del job |
| S3-01/S2-13 wrapper | Implementado (`TestPyinstallerWrapper` y `TestRunPyinstaller` pasan en CI) |
| S2-10 (incl. S2-12) | Tests de ramas de fallo por build script (Inno ausente → abort; create-dmg falla → abort; tooling AppImage ausente → degradación); `required=True` donde el fallo es fatal |
| S2-01/S2-02/S2-06 | **Implementado.** `TestSpeakJSON`/`TestDaemonVerbsJSON` validan los payloads exactos; `TestJSONContractStructure` descubre todo subcomando con `--json` desde `build_parser()` y valida: stdout = exactamente 1 objeto JSON, `schema_version` presente, stderr sin JSON |
| S2-05 | **Implementado.** `TestProtocolVersioning` valida `schema_version` en los 5 modelos vía `ProtocolModel` y `version` en `/health`; tests de rolling upgrade (payload con campos extra → cliente no falla; payload sin schema_version/version → defaults completan) |
| S2-07 | `build_linux.py` falla si la glibc del host de build > `GLIBC_FLOOR` declarado; test de consistencia valida que installer y docs derivan del mismo valor |
| S2-08 | Test de `doctor` con `data_root` simulado bajo OneDrive → check WARN presente; log muestra `[WARN]` con mitigación |
| S2-14 | Los 4 artefactos contienen `SOURCE-OFFER.md` con la URL del tarball del tag (verificable en el smoke test post-build); Cask con stanza `license` |
| S1-01 | PR incluye sección «Cancelación cooperativa del cliente» en DAEMON-MODE.md |
| S1-02 | Script de verificación lockfile ↔ THIRD-PARTY-LICENSES.md corre en job test-linux; falla con diff legible |

---

## Auditorías anteriores

*(Primera ejecución de este preset — sin histórico previo)*

---

*Generado por skill audit con preset production-readiness | commit 39137bc | perfil correctivo+preventivo*