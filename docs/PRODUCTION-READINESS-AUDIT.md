# Auditoría Production-Readiness — tts-sidecar v0.6.0 (commit 39137bc)

**Fecha**: 2026-07-13  
**Lente**: Release-readiness (10 dimensiones canónicas)  
**Perfil**: Correctivo + Preventivo  
**Commit**: 39137bc  
**Versión actual**: 0.6.0

---

## Resumen ejecutivo

Se audió el proyecto completo contra las 10 dimensiones de production-readiness. **El código base es sólido, bien testeado y con arquitectura limpia**. Se identificaron **0 hallazgos S4 (Críticos)**, **0 S3 (Alto)**, **14 S2 (Medios)**, **2 S1 (Bajos)** y **2 S0 (Informativos)**. Los gaps principales están en: cobertura de tests automatizados (sin herramienta coverage), build scripts failure branches sin test, create-dmg sin pin, schema_version ausente en daemon NDJSON, contrato --json incompleto en 6 comandos, glibc check solo en installer, OneDrive risk, y GPLv3 source offer solo en GitHub Release (no en instaladores nativos). **Veredicto global: LISTO-CON-RESERVAS** — apto para release 0.6.1 con plan de hardening pre-1.0.0.

### Conteo por severidad

| Severidad | Cuenta | Hallazgos clave |
|-----------|--------|-----------------|
| **S4 — Crítico** | 0 | — |
| **S3 — Alto** | 0 | — |
| **S2 — Medio** | 14 | Coverage tool ausente, build failure branches sin test, create-dmg unpinned, --json incompleto (6), schema_version faltante en NDJSON, glibc check solo en installer, OneDrive risk, GPL offer solo en Release |
| **S1 — Bajo** | 2 | DAEMON-MODE.md desactualizado (cancelación cooperativa), THIRD-PARTY-LICENSES no verificado vs lockfiles |
| **S0 — Informativo** | 2 | Documentación ejemplar, suite determinista sin flakiness |

### Conteo por prioridad recomendada

| Prioridad | Cuenta | Descripción |
|-----------|--------|-------------|
| **P0** | 2 | create-dmg pin, coverage tool |
| **P1** | 11 | --json completeness (6), schema_version en NDJSON, glibc check en build_linux.py, OneDrive mitigation, build failure branches tests (2), GPL offer en instaladores, DAEMON-MODE.md update |
| **P2** | 3 | Anchor USAGE.md, DAEMON-MODE.md cancelación cooperativa, THIRD-PARTY-LICENSES verification |
| **P3** | 2 | S0 residuales |

### Conteo por dimensión (10 canónicas)

| Dimensión | S4 | S3 | S2 | S1 | S0 | Total | Veredicto |
|-----------|----|----|----|----|----|-------|-----------|
| 1. CLI robustness & error handling | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 2. Programmatic contract (--json) | 0 | 0 | 6 | 0 | 0 | 6 | ⚠️ GAPS MEDIOS |
| 3. Daemon lifecycle & concurrency | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 4. Model & on-disk state management | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 5. Real cross-platform compatibility | 0 | 0 | 2 | 0 | 0 | 2 | ⚠️ GAPS MEDIOS |
| 6. End-to-end install/uninstall UX | 0 | 0 | 0 | 0 | 0 | 0 | ✅ LISTO |
| 7. Test quality & coverage | 0 | 0 | 4 | 0 | 0 | 4 | ⚠️ GAPS MEDIOS |
| 8. Documentation as product | 0 | 0 | 0 | 1 | 2 | 3 | ⚠️ GAPS MENORES |
| 9. Licensing & compliance | 0 | 0 | 1 | 1 | 0 | 2 | ⚠️ GAPS MENORES |
| 10. Supply chain & CI | 0 | 0 | 1 | 0 | 0 | 1 | ⚠️ GAPS MEDIOS |
| **TOTAL** | **0** | **0** | **14** | **2** | **2** | **18** | **LISTO-CON-RESERVAS** |

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

### 2. Programmatic contract (--json) — GAPS MEDIOS

**Qué está listo:**
- schema_version = "1" constante y presente en todos los payloads CLI (cli.py:54)
- stdout = solo JSON, stderr = logs/progreso (separación limpia)
- NDJSON daemon: ProgressEvent → ResultEvent/ErrorEvent con discriminador event, validación model_validate estricta línea a línea (ipc.py:133-199)
- Pydantic v2 = contrato formal en protocol.py; ambos extremos validan
- TTS_SIDECAR_REQUEST_TIMEOUT configurable (300s default)
- Tests TestWriteCommandsJSON, TestSchemaVersionJSON validan payloads exactos

**Hallazgos S2 (Medio):**

| ID | Título | Evidencia | Corrección propuesta |
|----|--------|-----------|----------------------|
| S2-01 | speak --json no emite payload a stdout | cli.py:224 cmd_speak no tiene bloque --json | Añadir {"schema_version","audio_b64","t3_time","s3gen_time"} en stdout al terminar |
| S2-02 | daemon status/start/stop/restart sin --json | cli.py:1681-1683 solo status tiene --json | Añadir flag y payload mínimo con schema_version a 4 subcomandos |
| S2-03 | cleanup --json no emite payload final a stdout | cli.py:1413-1420 redirige stdout interno a stderr, no emite propio | Emitir {"schema_version","removed":[],"dry_run":bool} en stdout |
| S2-04 | setup --json solo en --uninstall | cli.py:1273-1283 emite solo en modo uninstall | Emitir payload también en provisión normal (already_cached/downloaded) |
| S2-05 | schema_version ausente en daemon NDJSON | protocol.py:54-78 modelos sin campo; server.py:268-276 emite sin él | Añadir schema_version: str = "1" opcional a ProgressEvent/ResultEvent/ErrorEvent/HealthResponse/VoicesResponse; documentar aditividad |
| S2-06 | Tests --json incompletos | test_cli.py falta tests para speak, daemon status, setup, cleanup | Añadir TestSchemaVersionJSON parametrizado que itere todos los comandos |

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

| ID | Título | Evidencia | Corrección propuesta |
|----|--------|-----------|----------------------|
| S2-07 | glibc ≥2.35 check solo en install-linux.sh, NO en build_linux.py | install-linux.sh:65-76 tiene check; build_linux.py NO | Mover check a build_linux.py (fail-fast local); mantener en installer |
| S2-08 | OneDrive en Windows sin mitigación | paths.py:56-58 usa LOCALAPPDATA que puede redirigir a OneDrive → bloqueos sync | Detectar OneDrive en LOCALAPPDATA + warn/fallback a APPDATA no sincronizado |

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
- 508 tests, 100% deterministas (zero network, zero hardware, zero timing flakiness)
- CI triple-platform simétrico: test-linux (Docker), test-windows (Server 2022), test-macos (M4 Pro) — misma suite, gates obligatorios
- Smoke test binario congelado en cada build job: version + voice list \| grep 'default'
- Contract tests exhaustivos: exit codes, JSON schema_version, stdout/stderr separation, NDJSON events
- Unit/Integration ratio: ~75% unit (mocks pesados), ~25% integration (TestClient, installer scripts)

**Hallazgos S2:**

| ID | Severidad | Título | Evidencia | Corrección propuesta |
|----|-----------|--------|-----------|----------------------|
| S3-01 | **Alto** | PyInstaller timeout sin test (wrapper COM Windows) — **[Resuelto]** | timeout cubierto por `tests/test_build_utils.py::TestRunPyinstaller::test_timeout_kills_tree_and_returns_1` (rama de `run_pyinstaller` que mata el árbol y retorna 1) | Resuelto: la rama de timeout de `run_pyinstaller` está ejercida por `TestRunPyinstaller` |
| S2-09 | Medio | Sin configuración coverage tool | pyproject.toml sin pytest-cov, CI sin --cov | Añadir pytest-cov, coverage.xml en CI, umbral ≥80% en módulos críticos |
| S2-10 | Medio | Build scripts failure branches sin test | build_linux.py (patchelf/glibc), build_macos.py (codesign/ensure_icns), build_windows.py (Inno ausente) | Tests de fallo: PyInstaller timeout, checksum mismatch, tool missing |
| S2-11 | Medio | create-dmg sin pin (Homebrew) | build_macos.py:835 brew install create-dmg sin versión; comentario reconoce riesgo | Pinnear create-dmg via fetch_pinned_asset (patrón appimagetool) o bottle SHA256 |
| S2-12 | Medio | Inno Setup missing no testado | ensure_build_dependency mockeado siempre True en tests | Test que simula innosetup missing → build aborta |
| S2-13 | Medio | scripts/pyinstaller_wrapper.py sin test dedicado — **[Resuelto]** | Componente crítico Windows; ahora cubierto por `tests/test_build_utils.py::TestPyinstallerWrapper` (`main()` propaga `returncode` vía `os._exit` y limpia el archivo temporal; `_BOOTSTRAP` fija `coinit_flags` antes del import) | Resuelto: `TestPyinstallerWrapper` añadido cierra S2-13 y complementa `TestRunPyinstaller` |

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

| ID | Título | Severidad | Evidencia |
|----|--------|-----------|-----------|
| S1-01 | **Bajo** | DAEMON-MODE.md no documenta cancelación cooperativa | S1 | CHANGELOG Unreleased líneas 12-22 describe SynthesisCancelled + GeneratorExit; DAEMON-MODE.md sin mención |
| S0-01 | **Info** | Anchor roto USAGE.md:175 | S0 | Anchor real en README es #instalación-de-una-línea |
| S0-02 | Info | USAGE/cli.py orden --voice-audio/--speech-audio difiere (no contradictorio) | S0 | USAGE:406-407 vs cli.py:1578-1582 |

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

| ID | Título | Severidad | Evidencia |
|----|--------|-----------|-----------|
| S2-14 | **Medio** | GPLv3 §6 source offer solo en GitHub Release, no en instaladores nativos | S2 | RELEASING.md:101-105 inyecta en Release notes; Inno InfoAfter / .dmg ReadMe / Cask no la tienen |
| S1-02 | **Bajo** | THIRD-PARTY-LICENSES.md no verificado vs lockfiles | S1 | Necesita script verificación automatizada (CI) |

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

| ID | Título | Evidencia | Corrección propuesta |
|----|--------|-----------|----------------------|
| S2-15 | **Medio** | create-dmg sin pin (Homebrew) | build_macos.py:835 brew install create-dmg sin versión; build macOS puede romper por release Homebrew | Pinnear via fetch_pinned_asset (descargar bottle con SHA256) o brew install create-dmg@<versión> si existe fórmula versionada |

---

## Release gate (S4 + S3 mínimos para release)

| Hallazgo | Severidad | Debe resolverse antes de release |
|----------|-----------|----------------------------------|
| S3-01 | S3 — Alto | **Resuelto** — cubierto por `tests/test_build_utils.py::TestRunPyinstaller` (timeout) y `tests/test_build_utils.py::TestPyinstallerWrapper` (wrapper COM) |
| S2-01 a S2-15 | S2 — Medio | **RECOMENDADO** — No bloquean técnicamente, pero degradan calidad y operabilidad |
| S1-01, S1-02 | S1 — Bajo | No — solo docs/compliance menor |
| S0 | S0 — Info | No — solo pulido |

---

## Recomendación global de madurez

**LISTO-CON-RESERVAS** — El proyecto **cumple funcionalmente** para un release 0.6.1 (todas las brechas accionables de PARITY.md cerradas en código/tests, paridad UX completa en 3 SO). Los hallazgos S3/S2 son **de hardening pre-1.0.0**, no bloquean release de mantenimiento. 

**Plan sugerido**: 
1. Release 0.6.1 con fixes P0 (coverage, create-dmg pin) 
2. Sprint 0.7.0 para cerrar P1 (contrato --json completo, glibc check build, OneDrive, GPL offer, build failure tests) 
3. 1.0.0 cuando P1/P2 cerrados + validación E2E usuarios reales Linux/macOS (criterio aceptación 10 GOAL.md)

---

## Confirmación en CI

| Hallazgo | Cómo se confirmará en CI |
|----------|---------------------------|
| Coverage ≥80% | pytest --cov=src/tts_sidecar --cov-fail-under=80 en job test-* |
| create-dmg pin | Build macOS usa fetch_pinned_asset (log muestra SHA256 verificado) |
| PyInstaller wrapper test | Implementado (`tests/test_build_utils.py::TestPyinstallerWrapper` pasa en CI; `TestRunPyinstaller` cubre el timeout) |
| Build failure tests | Tests mock subprocess.run → TimeoutExpired / FileNotFoundError / checksum mismatch |
| Inno missing test | Test ensure_build_dependency returns False → build aborta |
| --json completeness | TestSchemaVersionJSON parametrizado itera 9 comandos, valida stdout=1 JSON, schema_version, stderr=solo logs |
| glibc check build | build_linux.py aborta si ldd --version < 2.35 (log CI) |
| OneDrive detection | Log setup/install-windows.ps1 muestra [WARN] OneDrive detectado en LOCALAPPDATA si aplica |
| GPL offer installers | Inno InfoAfterFile incluye source offer; .dmg incluye ReadMe; Cask license "GPL-3.0-or-later" |
| DAEMON-MODE.md updated | PR incluye sección "Cancelación cooperativa del cliente" |

---

## Auditorías anteriores

*(Primera ejecución de este preset — sin histórico previo)*

---

*Generado por skill audit con preset production-readiness | commit 39137bc | perfil correctivo+preventivo*