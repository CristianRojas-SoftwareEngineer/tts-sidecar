# Revisión: preparación para release de TTS Sidecar

## Resumen ejecutivo

Se auditaron las diez dimensiones de preparación para release de `tts-sidecar` (robustez de CLI, contrato programático, daemon, estado en disco/modelo, compatibilidad multiplataforma, UX de instalación/desinstalación, calidad y cobertura de tests, documentación como producto, licencias/compliance, y cadena de suministro/CI), bajo lente de **release readiness** y perfil **preventivo**. El material probado son los 47 hallazgos con evidencia `file:line` del audit del `48c6d8a`.

**Veredicto global: LISTO CON RESERVAS.** No hay hallazgos **S4 (Críticos)**: ninguno bloquea la publicación de v0.6.0. Persisten 7 hallazgos **S3 (Altos)** —concentrados en el endurecimiento del daemon, el contrato de cancelación programática, la oferta de fuente GPL en el release y la validación del binario congelado en CI— que deberían resolverse antes de la siguiente versión menor.

**Conteo por severidad:** 0 S4 · 7 S3 · 3 S2 · 33 S1 · 4 S0 (47 hallazgos).
**Conteo por prioridad:** 0 P0 · 6 P1 · 22 P2 · 19 P3.


### Índice de hallazgos

El índice siguiente lista los 47 hallazgos ordenados por ID, con su severidad, prioridad, área/plataforma, si requieren decisión del propietario y su estado de resolución. El detalle de cada uno aparece en [Hallazgos por severidad](#hallazgos-por-severidad).

| ID    | Título                                                                | Severidad        | Prioridad | Área/plataforma             | Decisión requerida | Estado |
| ----- | --------------------------------------------------------------------- | ---------------- | --------- | --------------------------- | ------------------ |--------- |
| S3-01 | Ctrl+C en `setup`/descarga devuelve exit 1 en vez de 130              | S3 — Alto        | P1        | CLI / contrato programático | No                 | Resuelto |
| S3-02 | Ventana de carrera en `daemon start` (doble arranque)                 | S3 — Alto        | P1        | Daemon                      | No                 | Resuelto  |
| S3-03 | Bind del puerto 8765 sin manejo de `OSError`                          | S3 — Alto        | P1        | Daemon                      | No                 | Resuelto |
| S3-04 | Sin gestión de memoria del modelo en uso prolongado                   | S3 — Alto        | P2        | Daemon / CUDA               | No                 | Pendiente |
| S3-05 | Sin límite de concurrencia en `/synthesize`                           | S3 — Alto        | P2        | Daemon                      | Sí                 | Pendiente |
| S3-06 | Oferta de código fuente GPL no explícita en el release                | S3 — Alto        | P1        | Licencias / release         | No                 | Resuelto |
| S3-07 | Smoke test del binario congelado limitado a `version`                 | S3 — Alto        | P1        | CI / DevOps                 | No                 | Resuelto |
| S2-01 | `/shutdown` sin autenticación (loopback, riesgo aceptado)             | S2 — Medio       | P3        | Daemon / seguridad          | Sí                 | Resuelto  |
| S2-02 | Binario nativo de macOS solo `arm64` (sin Intel)                      | S2 — Medio       | P2        | Compatibilidad / macOS      | Sí                 | Resuelto  |
| S2-03 | `setup --force-update` no documentado en `USAGE.md`                   | S2 — Medio       | P1        | Documentación               | No                 | Resuelto  |
| S1-01 | Error de descarga genérico sin diferenciar red/disco/credenciales     | S1 — Bajo        | P2        | CLI                         | No                 | Resuelto  |
| S1-02 | `voice remove` con mensaje genérico ante `PermissionError`            | S1 — Bajo        | P3        | CLI / Windows               | No                 | Resuelto  |
| S1-03 | Los `.incomplete` de HuggingFace no se limpian solos                  | S1 — Bajo        | P3        | Estado en disco             | No                 | Resuelto  |
| S1-04 | Red de seguridad de `ve.safetensors` no ofrece `setup`                | S1 — Bajo        | P3        | Estado en disco             | No                 | Resuelto  |
| S1-05 | Detección de daemon huérfano por cmdline, no por PID file             | S1 — Bajo        | P2        | Daemon                      | No                 | Resuelto  |
| S1-06 | Timeout de síntesis fijo (5 min) sin reintentos                       | S1 — Bajo        | P3        | Daemon                      | No                 | Resuelto  |
| S1-07 | Contención de audio paths no protege symlinks multiusuario            | S1 — Bajo        | P3        | Daemon / seguridad          | No                 | Resuelto  |
| S1-08 | Braille del spinner puede corromperse en cp437                        | S1 — Bajo        | P3        | Contrato / Windows          | No                 | Resuelto  |
| S1-09 | `WARN` en `doctor --json` no documentado                              | S1 — Bajo        | P2        | Contrato / docs             | No                 | Resuelto  |
| S1-10 | Estado `"unknown"` del daemon no documentado                          | S1 — Bajo        | P2        | Contrato / docs             | No                 | Resuelto  |
| S1-11 | AVX2 requerido pero no auto-detectado por `doctor`                    | S1 — Bajo        | P2        | Compatibilidad / CPU        | No                 | Resuelto  |
| S1-12 | Advisory de RAM no verificado                                         | S1 — Bajo        | P2        | Compatibilidad              | No                 | Resuelto  |
| S1-13 | Sin matriz de SO mínimos probados                                     | S1 — Bajo        | P2        | Compatibilidad / macOS      | No                 | Resuelto  |
| S1-14 | glibc < 2.35 solo advierte; el AppImage falla en runtime              | S1 — Bajo        | P2        | UX instalación / Linux      | No                 | Resuelto  |
| S1-15 | Aviso de PATH estático en zsh sin recarga                             | S1 — Bajo        | P3        | UX instalación / macOS      | No                 | Resuelto  |
| S1-16 | PATH de Windows requiere terminal nueva sin indicarlo                 | S1 — Bajo        | P3        | UX instalación / Windows    | No                 | Resuelto  |
| S1-17 | Migración per-machine→per-user no detectada (PATH duplicado)          | S1 — Bajo        | P2        | UX instalación / Windows    | No                 | Resuelto  |
| S1-18 | Mac Intel sin alternativa sugerida en el instalador                   | S1 — Bajo        | P3        | UX instalación / macOS      | No                 | Resuelto  |
| S1-19 | Branches de error de `ensure_runtime_dependencies` sin test           | S1 — Bajo        | P2        | Testing / Linux             | No                 | Resuelto  |
| S1-20 | Timeout de `fetch_pinned_asset` no testeado                           | S1 — Bajo        | P2        | Testing                     | No                 | Resuelto  |
| S1-21 | `RequestException` del daemon no testeada                             | S1 — Bajo        | P2        | Testing                     | No                 | Resuelto  |
| S1-22 | Tests de symlink se saltan en Windows sin Developer Mode              | S1 — Bajo        | P3        | Testing / Windows           | No                 | Resuelto  |
| S1-23 | ARM64 Linux sin suite dedicada                                        | S1 — Bajo        | P2        | Testing / aarch64           | No                 | Resuelto  |
| S1-24 | Pascal Script de desinstalación sin test unitario                     | S1 — Bajo        | P2        | Testing / Windows           | No                 | Resuelto  |
| S1-25 | Branch `except Exception` del worker no cubierto                      | S1 — Bajo        | P2        | Testing / Daemon            | No                 | Resuelto  |
| S1-26 | `CLAUDE.md` dice 296 tests (real: 314)                                | S1 — Bajo        | P3        | Documentación               | No                 | Resuelto  |
| S1-27 | Sin plantilla de issue de bug                                         | S1 — Bajo        | P2        | Documentación / governance  | No                 | Resuelto  |
| S1-28 | `CONTRIBUTING.md` omite el smoke-test de Windows                      | S1 — Bajo        | P3        | Documentación               | No                 | Resuelto  |
| S1-29 | Atribución de PerthNet/`resemble-perth` débil                         | S1 — Bajo        | P2        | Licencias                   | No                 | Resuelto  |
| S1-30 | `pytest` pineado pero no sus plugins                                  | S1 — Bajo        | P2        | Cadena de suministro / CI   | No                 | Resuelto  |
| S1-31 | Installers mockeados; `docs/SELF-HOSTED-INSTALL.md` inexistente       | S1 — Bajo        | P2        | CI / docs                   | No                 | Resuelto  |
| S1-32 | ARM64 Linux sin test dedicado (decisión consciente)                   | S1 — Bajo        | P3        | CI / aarch64                | No                 | Resuelto  |
| S1-33 | Runbook de falsos positivos solo para Defender                        | S1 — Bajo        | P3        | Documentación / seguridad   | No                 | Resuelto  |
| S0-01 | `bootstrap.apply()` corre antes del `reconfigure` UTF-8 (riesgo nulo) | S0 — Informativo | P3        | Contrato                    | No                 | Resuelto  |
| S0-02 | `--force-update` sin log del tamaño liberado                          | S0 — Informativo | P3        | Observabilidad              | No                 | Resuelto  |
| S0-03 | AppImage Linux sin CUDA (documentado)                                 | S0 — Informativo | P3        | Compatibilidad / Linux      | No                 | Resuelto  |
| S0-04 | Lock universal con `nvidia-*` distinguido del binario (sin acción)    | S0 — Informativo | P3        | Licencias                   | No                 | Resuelto  |




### Verificación de evidencia (2026-07-11)

Pasada de re-lectura del código en HEAD (`48c6d8a`) tras elegir «Verificar/documentar más» en la compuerta de cierre. Objetivo: confirmar que las citas `file:line` de los 7 hallazgos **S3** siguen vigentes y no derivaron. Resultado:

- **Confirmados sin cambios:** `S3-02` (`daemon.py:45-51`, race documentada como SUGGESTION-03), `S3-04` (`daemon/run.py:66`, engine retenido), `S3-06` (oferta de fuente GPL), `S3-07` (smoke test solo `version` en `.circleci/config.yml:540/647/777`), y `S2-01` (`server.py:207-225`, `/shutdown` sin token, SUGGESTION-02).
- **Derivados y corregidos en su hallazgo:**
  - `S3-01` — las citas secundarias del audit legacy (`engine.py:288-432`, `cli.py:1135-1168`) derivaron de línea; el hecho central se re-confirmó con grep: `KeyboardInterrupt` aparece **solo** en `cli.py:1516` (dentro de `main()`).
  - `S3-03` — ya no hay traceback crudo: `daemon/run.py:103` tiene un `except Exception` genérico que solo hace `log(...)`; el gap es que no distingue `EADDRINUSE`. Refinados causa/impacto/corrección.
  - `S3-05` — la síntesis **ya está serializada** por `_synthesis_lock` (`server.py:147`); el gap real es que cada request lanza un `threading.Thread` ilimitado (`server.py:177`), sin admisión acotada. Refinados causa/impacto/corrección.

La severidad (S3) y la prioridad (P1/P2) de los tres hallazgos corregidos **no cambian**: la impacto sigue siendo alta; solo se precisó el mecanismo exacto. El resto de hallazgos S1/S0 conserva sus citas del audit legacy (no re-verificadas línea a línea en esta pasada).

## Hallazgos por severidad

Cada hallazgo se detalla a continuación, agrupado por nivel de severidad (de S3 a S0).



### S3 — Altos



#### S3-01 — Ctrl+C en `setup`/descarga devuelve exit 1 en vez de 130

- **Categoría**: Reliability (contrato programático)
- **Área/plataforma**: CLI / integración por subprocess (todos los SO)
- **Evidencia**: `cli.py:1516` (única ocurrencia de `KeyboardInterrupt` en todo `cli.py`, dentro de `main()`); `cmd_setup` arranca en `cli.py:1014` y su descarga no captura la interrupción (verificado por grep: no hay otro `except KeyboardInterrupt` en `cli.py`)
- **Confianza**: Alta
- **Causa**: al cancelar durante la descarga del modelo, `KeyboardInterrupt` se propaga como `Exception` genérica y cae en el handler que devuelve exit 1.
- **Impacto**: un consumidor programático (el caso de uso central: subprocess desde otro lenguaje) no puede distinguir «cancelado por el usuario» (130) de «error de red/disco» (1); se rompe la señal canónica de cancelación.
- **Corrección(es) propuesta(s)**: envolver `setup`/`_download_model` en manejo explícito de `KeyboardInterrupt` que devuelva 130 *(recomendada)*. Unifica `D1-R01` y `D2-R01` del legacy (mismo origen, dimensiones 1 y 2).
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D1-R01 / D2-R01)*



#### S3-02 — Ventana de carrera en `daemon start` (doble arranque)

- **Categoría**: Reliability (concurrencia)
- **Área/plataforma**: Daemon (todos los SO)
- **Evidencia**: `daemon.py:47-56`
- **Confianza**: Alta
- **Causa**: dos arranques rápidos pasan `is_running()` antes de que el segundo `Popen` falle al bindear; no hay lock activo ni reintento.
- **Impacto**: estado confuso de arranque (el segundo proceso falla al bindear el puerto) sin serialización; race condition en el ciclo de vida del daemon.
- **Corrección(es) propuesta(s)**: lock de arranque (archivo de lock o bind atómico) que serialice el `start` *(recomendada)*.
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D3-R01)*



#### S3-03 — Bind del puerto 8765 sin manejo de `OSError`

- **Categoría**: Reliability (manejo de errores)
- **Área/plataforma**: Daemon (todos los SO)
- **Evidencia**: `daemon/run.py:88-101`
- **Confianza**: Alta
- **Causa**: el bloque `try` que envuelve `uvicorn.Server(...).run()` (`daemon/run.py:88-104`) captura `KeyboardInterrupt` y un `except Exception` genérico que solo hace `log(...)`, pero no distingue `EADDRINUSE`/OSError de otros errores. *(Verificado 2026-07-11: ya no hay traceback crudo como indicaba el audit legacy; el bind sí está dentro de un* `try`*, pero el manejador es genérico.)*
- **Impacto**: cuando el puerto 8765 está ocupado, el arranque falla y se registra un error genérico sin identificar la causa — no hay mensaje accionable ni exit code específico para «puerto en uso»; falla de arranque poco diagnóstica.
- **Corrección(es) propuesta(s)**: dentro del `except`, detectar `OSError`/`EADDRINUSE` **antes** del `except Exception` genérico y emitir un mensaje accionable con un exit code coherente *(recomendada)*.
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D3-R02)*



#### S3-04 — Sin gestión de memoria del modelo en uso prolongado

- **Categoría**: Reliability / Performance
- **Área/plataforma**: Daemon / CUDA
- **Evidencia**: `daemon/run.py:66`
- **Confianza**: Media
- **Causa**: el engine se mantiene en memoria indefinidamente sin `torch.cuda.empty_cache()`/GC.
- **Impacto**: bajo uso prolongado en CUDA la memoria puede fragmentarse y degradar el servidor local persistente.
- **Corrección(es) propuesta(s)**: liberación/GC periódico de la caché CUDA entre síntesis o bajo presión de memoria *(recomendada)*.
- **Decisión requerida**: No
- **Prioridad**: P2 *(migra D3-R03)*



#### S3-05 — Sin límite de concurrencia en `/synthesize`

- **Categoría**: Reliability / Scalability
- **Área/plataforma**: Daemon (especialmente Windows/GIL)
- **Evidencia**: `server.py:147,177-178`
- **Confianza**: Alta
- **Causa**: cada petición a `/synthesize` lanza su propio `threading.Thread` (`server.py:177`) sin tope; la síntesis en sí está serializada por `_synthesis_lock` (`server.py:147`), pero el número de threads/handlers concurrentes no está acotado. *(Verificado 2026-07-11: el audit legacy afirmaba «sin límite de concurrencia de requests»; en verdad la síntesis ya está serializada por lock — el gap es la admisión de handlers, no la síntesis.)*
- **Impacto**: una ráfaga de N invocaciones `speak --daemon` en paralelo crea N threads que se encolan en el lock; no hay admisión acotada (backpressure) ni límite de concurrencia de handlers, lo que satura el proceso bajo GIL/Windows.
- **Corrección(es) propuesta(s)**: limitar los threads/handlers concurrentes con un semáforo de admisión configurable que rechace o encale con tope explícito al excederlo *(recomendada)*.
- **Decisión requerida**: Sí — elegir la política ante saturación (rechazar con código de error vs. encolar con espera) y el valor del tope.
- **Prioridad**: P2 *(migra D3-R04)*



#### S3-06 — Oferta de código fuente GPL no explícita en el release

- **Categoría**: Licensing / Compliance
- **Área/plataforma**: Artefactos del release (todos los SO)
- **Evidencia**: `LICENSE` (GPLv3 §6); `SECURITY.md:93-98`; `docs/BUILD.md:218`
- **Confianza**: Alta
- **Causa**: no hay un enlace canónico al código fuente del release en las notas/asset del GitHub Release; la §6 exige la oferta de fuente junto a los binarios.
- **Impacto**: la obligación se cumple de facto (repo público, el tag `v0.6.0` apunta al código exacto) pero no está materializada explícitamente en el release, dejando una brecha formal de compliance.
- **Corrección(es) propuesta(s)**: añadir un enlace al tarball/tag de fuente en las notas del release *(recomendada)*.
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D9-R01)*



#### S3-07 — Smoke test del binario congelado limitado a `version`

- **Categoría**: DevOps / Testing
- **Área/plataforma**: CI (jobs `build-linux-x64`, `build-linux-arm64`, `build-darwin-arm64`)
- **Evidencia**: `.circleci/config.yml:541,647,773`
- **Confianza**: Alta
- **Causa**: el único smoke test del binario congelado es `version`; no se valida `voice add` ni que las voces de fábrica quedaron empaquetadas en el bundle.
- **Impacto**: un build con metadata o voces faltantes pasaría CI sin ser detectado.
- **Corrección(es) propuesta(s)**: ampliar el smoke test a `voice list`/`speak` mínimo con la voz `default` para validar el empaquetado *(recomendada)*.
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D10-R01)*



### S2 — Medios



#### S2-01 — `/shutdown` sin autenticación (loopback, riesgo aceptado)

- **Categoría**: Security
- **Área/plataforma**: Daemon (`127.0.0.1:8765`)
- **Evidencia**: `server.py:207-225`
- **Confianza**: Alta
- **Causa**: el endpoint `/shutdown` no exige token; el código lo marca como «riesgo aceptado (SUGGESTION-02)».
- **Impacto**: exposición menor (solo loopback): DoS local de bajo impacto. Es una brecha de defensa en profundidad, no un bug de correctness.
- **Corrección(es) propuesta(s)**: token/nonce local para `/shutdown` *(recomendada si se decide cerrar la brecha)*, o dejar constancia formal de la aceptación del riesgo.
- **Decisión requerida**: Sí — cerrar la brecha con un token vs. mantener el riesgo aceptado documentado.
- **Prioridad**: P3 *(migra D3-R05)*



#### S2-02 — Binario nativo de macOS solo `arm64` (sin Intel)

- **Categoría**: Compatibility / Portability
- **Área/plataforma**: macOS Intel (x86_64)
- **Evidencia**: `build_macos.py:40-42,88-90`
- **Confianza**: Alta
- **Causa**: solo se soporta `arm64` (Apple Silicon); macOS Intel se rechaza. Es una limitación de toolchain declarada.
- **Impacto**: los usuarios de Mac Intel no pueden usar el binario nativo (deben recurrir a PyPI o compilar desde fuente); excluye una porción real de la audiencia.
- **Corrección(es) propuesta(s)**: build universal2/x86_64 si el toolchain lo permite *(recomendada a mediano plazo)*, o documentar y encaminar explícitamente a Mac Intel hacia PyPI/fuente.
- **Decisión requerida**: Sí — invertir en soporte Intel vs. mantenerlo como limitación documentada.
- **Prioridad**: P2 *(migra D5-R01)*



#### S2-03 — `setup --force-update` no documentado en `USAGE.md`

- **Categoría**: Documentation
- **Área/plataforma**: Documentación de producto
- **Evidencia**: `cli.py:1434` expone el flag (y `CHANGELOG.md` lo documenta), pero el bloque `setup` de `USAGE.md` no lo incluye
- **Confianza**: Alta
- **Causa**: el flag existe y se comporta correctamente, pero falta su sección en la guía de uso.
- **Impacto**: un usuario avanzado que necesite re-descargar el modelo no encuentra el mecanismo documentado.
- **Corrección(es) propuesta(s)**: documentar `--force-update` en el bloque `setup` de `USAGE.md` *(recomendada; corrección trivial)*.
- **Decisión requerida**: No
- **Prioridad**: P1 *(migra D8-R02)*



### S1 — Bajos

Los 33 hallazgos de baja severidad se agrupan por área (en divisores en negrita) para facilitar la navegación; sus campos siguen el mismo esquema que S3/S2/S0.

**CLI**

#### S1-01 — Error de descarga genérico sin diferenciar causa

- **Categoría**: Reliability
- **Área/plataforma**: CLI
- **Evidencia**: `cli.py:1170-1172`
- **Confianza**: Alta
- **Causa**: cualquier fallo de descarga cae en el handler genérico (`[FAIL] La provisión falló: <exception>`) sin diferenciar red/disco/credenciales.
- **Impacto**: El diagnóstico se degrada al no distinguir la causa real del fallo.
- **Corrección(es) propuesta(s)**: clasificar la excepción y emitir mensajes accionables por causa. *(migra D1-R02)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-02 — `voice remove` con mensaje genérico ante `PermissionError`

- **Categoría**: Reliability
- **Área/plataforma**: CLI · Windows
- **Evidencia**: `cli.py:387-398`
- **Confianza**: Alta
- **Causa**: el manejo detecta `PermissionError` y sugiere cerrar el daemon, pero el mensaje es genérico.
- **Impacto**: No cubre todos los casos de archivo en uso en Windows, dejando al usuario sin guía completa.
- **Corrección(es) propuesta(s)**: enriquecer el mensaje con los casos de bloqueo de archivo típicos de Windows. *(migra D1-R03)*
- **Decisión requerida**: No
- **Prioridad**: P3



**Estado en disco**

#### S1-03 — Los `.incomplete` de HuggingFace no se limpian solos

- **Categoría**: Reliability
- **Área/plataforma**: Estado en disco
- **Evidencia**: `model_cache.py:64-88`
- **Confianza**: Alta
- **Causa**: un modelo parcialmente descargado se detecta como «no cacheado» y se redescarga.
- **Impacto**: los `.incomplete` de HuggingFace no se limpian solos, acumulando basura en disco.
- **Corrección(es) propuesta(s)**: limpiar los `.incomplete` huérfanos antes de redescargar. *(migra D1-R04)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-04 — Red de seguridad de `ve.safetensors` no ofrece `setup`

- **Categoría**: Reliability
- **Área/plataforma**: Estado en disco
- **Evidencia**: `engine.py:475-488`
- **Confianza**: Alta
- **Causa**: la red de seguridad redescarga `ve.safetensors` si falta y avisa que la caché está «podada».
- **Impacto**: no ofrece ejecutar `setup` automáticamente, dejando al usuario sin un camino claro de recuperación.
- **Corrección(es) propuesta(s)**: sugerir/ofrecer `setup` cuando se detecta caché podada. *(migra D4-R02)*
- **Decisión requerida**: No
- **Prioridad**: P3



**Daemon**

#### S1-05 — Detección de daemon huérfano por cmdline, no por PID file

- **Categoría**: Reliability
- **Área/plataforma**: Daemon
- **Evidencia**: `daemon.py:244-268`
- **Confianza**: Alta
- **Causa**: la detección de daemon huérfano depende de cmdline, no de un PID file.
- **Impacto**: un zombie puede reportarse como «arrancando» (exit 5) sin poder forzar su terminación.
- **Corrección(es) propuesta(s)**: complementar con PID file para desambiguar zombies. *(migra D3-R06)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-06 — Timeout de síntesis fijo (5 min) sin reintentos

- **Categoría**: Reliability
- **Área/plataforma**: Daemon
- **Evidencia**: `ipc.py:34` (`REQUEST_TIMEOUT = 300.0`)
- **Confianza**: Alta
- **Causa**: el timeout de síntesis es fijo (5 min) y no hay reintentos.
- **Impacto**: una síntesis colgada espera 5 min antes de fallar, retrasando al consumidor.
- **Corrección(es) propuesta(s)**: timeout configurable y/o reintento acotado. *(migra D3-R07)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-07 — Contención de audio paths no protege symlinks multiusuario

- **Categoría**: Security
- **Área/plataforma**: Daemon
- **Evidencia**: `server.py:114-121`
- **Confianza**: Alta
- **Causa**: la validación de audio paths con `realpath`+contención no considera symlinks multiusuario.
- **Impacto**: en un escenario multiusuario (improbable por el diseño single-user), la contención podría ser eludida.
- **Corrección(es) propuesta(s)**: endurecer la resolución de symlinks si el modelo de amenaza lo justifica. *(migra D3-R08)*
- **Decisión requerida**: No
- **Prioridad**: P3



**Contrato**

#### S1-08 — Braille del spinner puede corromperse en cp437

- **Categoría**: UX
- **Área/plataforma**: Contrato · Windows
- **Evidencia**: `timing.py:187-196`
- **Confianza**: Alta
- **Causa**: el `Spinner` solo desactiva braille en codepages no-UTF; en consola Windows con OEM cp437 evalúa `_enabled` tras emitir.
- **Impacto**: los caracteres braille pueden corromperse antes de desactivarse, mostrando basura en cp437.
- **Corrección(es) propuesta(s)**: detectar cp437 y degradar a ASCII antes de emitir. *(migra D2-R02)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-09 — `WARN` en `doctor --json` no documentado

- **Categoría**: Documentation
- **Área/plataforma**: Contrato
- **Evidencia**: `cli.py:447-590`; `USAGE.md` documenta solo `PASS/FAIL/SKIP`
- **Confianza**: Alta
- **Causa**: `doctor --json` emite `status: "WARN"` pero el esquema de salida no lo declara.
- **Impacto**: un integrador puede recibir un valor no documentado y fallar al parsear la respuesta.
- **Corrección(es) propuesta(s)**: documentar `WARN` en el contrato de `doctor --json`. *(migra D2-R04)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-10 — Estado `"unknown"` del daemon no documentado

- **Categoría**: Documentation
- **Área/plataforma**: Contrato
- **Evidencia**: `USAGE.md:211-216` (documenta `"healthy"`/`"initializing"`); `cli.py:1355` puede emitir `"unknown"`
- **Confianza**: Alta
- **Causa**: `cli.py:1355` puede emitir el estado `"unknown"` del daemon, pero `USAGE.md` solo documenta `"healthy"`/`"initializing"`.
- **Impacto**: integradores programáticos podrían recibir un valor no documentado y no manejarlo.
- **Corrección(es) propuesta(s)**: documentar `"unknown"` como estado posible. *(migra D8-R05)*
- **Decisión requerida**: No
- **Prioridad**: P2



**Compatibilidad**

#### S1-11 — AVX2 requerido pero no auto-detectado por `doctor`

- **Categoría**: Reliability
- **Área/plataforma**: CPU
- **Evidencia**: `USAGE.md:737-741`; sin auto-detección en `doctor`
- **Confianza**: Alta
- **Causa**: AVX2 es requerido pero `doctor` no lo auto-detecta.
- **Impacto**: PyTorch puede fallar en runtime en CPU antigua (~pre-2015) sin diagnóstico previo.
- **Corrección(es) propuesta(s)**: detectar AVX2 en `doctor` y advertir. *(migra D5-R02)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-12 — Advisory de RAM no verificado

- **Categoría**: Reliability
- **Área/plataforma**: Compatibilidad
- **Evidencia**: `USAGE.md:743-745`; `cli.py:57`
- **Confianza**: Alta
- **Causa**: el advisory de RAM (8GB; `WARN` a 4GB) no se verifica en `doctor`.
- **Impacto**: máquinas con <4GB no tienen ninguna guarda ni aviso.
- **Corrección(es) propuesta(s)**: verificar RAM disponible en `doctor`. *(migra D5-R03)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-13 — Sin matriz de SO mínimos probados

- **Categoría**: Testing
- **Área/plataforma**: Compatibilidad · macOS
- **Evidencia**: `build_macos.py:340-359` (`LSMinimumSystemVersion` derivado del SDK)
- **Confianza**: Alta
- **Causa**: no se define ni prueba una matriz de SO mínimos, aunque el deployment target es coherente.
- **Impacto**: no hay evidencia de los SO mínimos efectivamente probados para el release.
- **Corrección(es) propuesta(s)**: definir y probar una matriz mínima de SO. *(migra D5-R05)*
- **Decisión requerida**: No
- **Prioridad**: P2



**UX instalación**

#### S1-14 — glibc < 2.35 solo advierte; el AppImage falla en runtime

- **Categoría**: Reliability
- **Área/plataforma**: UX instalación · Linux
- **Evidencia**: `install.sh:69-73`
- **Confianza**: Alta
- **Causa**: en glibc < 2.35 (p. ej. Ubuntu 20.04) el instalador solo advierte.
- **Impacto**: el AppImage falla en runtime sin ofrecer una alternativa inmediata.
- **Corrección(es) propuesta(s)**: bloquear o encaminar a PyPI/fuente cuando glibc es insuficiente. *(migra D6-R01)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-15 — Aviso de PATH estático en zsh sin recarga

- **Categoría**: UX instalación
- **Área/plataforma**: macOS
- **Evidencia**: `install.sh:148-153`
- **Confianza**: Alta
- **Causa**: el aviso de PATH estático en zsh no indica recargar el shell.
- **Impacto**: el usuario puede seguir sin el binario en PATH hasta reiniciar la sesión manualmente.
- **Corrección(es) propuesta(s)**: instruir la recarga (`exec zsh`/`source`) o abrir shell nuevo. *(migra D6-R02)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-16 — PATH de Windows requiere terminal nueva sin indicarlo

- **Categoría**: UX instalación
- **Área/plataforma**: Windows
- **Evidencia**: `install.ps1:112-118`
- **Confianza**: Alta
- **Causa**: `Update-SessionPath` actualiza la sesión pero requiere abrir una terminal nueva.
- **Impacto**: no hay indicación post-instalación, y el comando no funciona hasta abrir terminal nueva.
- **Corrección(es) propuesta(s)**: mensaje post-instalación indicando abrir terminal nueva. *(migra D6-R03)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-17 — Migración per-machine→per-user no detectada (PATH duplicado)

- **Categoría**: UX instalación
- **Área/plataforma**: Windows
- **Evidencia**: `install.ps1:191-193`
- **Confianza**: Alta
- **Causa**: la migración per-machine→per-user de pre-0.4.0 no se detecta.
- **Impacto**: puede quedar una entrada PATH duplicada (per-machine) sin limpiar.
- **Corrección(es) propuesta(s)**: detectar y limpiar la entrada per-machine previa. *(migra D6-R04)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-18 — Mac Intel sin alternativa sugerida en el instalador

- **Categoría**: UX instalación
- **Área/plataforma**: macOS
- **Evidencia**: `install-macos.sh:52-54`
- **Confianza**: Alta
- **Causa**: el instalador de Mac Intel indica la limitación pero no sugiere alternativa.
- **Impacto**: usuarios de Mac Intel no ven la vía de PyPI o compilación desde fuente. Relacionado con S2-02.
- **Corrección(es) propuesta(s)**: sugerir explícitamente PyPI/compilación desde fuente. *(migra D6-R05)*
- **Decisión requerida**: No
- **Prioridad**: P3



**Testing**

#### S1-19 — Branches de error de `ensure_runtime_dependencies` sin test

- **Categoría**: Testing
- **Área/plataforma**: Linux
- **Evidencia**: `build_linux.py:103-120`; `tests/test_build_linux.py`
- **Confianza**: Alta
- **Causa**: las ramas `CalledProcessError`/`TimeoutExpired` de `ensure_runtime_dependencies` no tienen cobertura de test.
- **Impacto**: regresiones en esas ramas de fallo podrían pasar desapercibidas.
- **Corrección(es) propuesta(s)**: añadir tests de esas ramas de fallo. *(migra D7-R01)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-20 — Timeout de `fetch_pinned_asset` no testeado

- **Categoría**: Testing
- **Área/plataforma**: —
- **Evidencia**: `scripts/build_utils.py:169`
- **Confianza**: Alta
- **Causa**: el timeout de red expirado de `fetch_pinned_asset` no se testea.
- **Impacto**: solo se cubren éxito y checksum erróneo; el caso de timeout queda sin validar.
- **Corrección(es) propuesta(s)**: test del timeout expirado. *(migra D7-R02)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-21 — `RequestException` del daemon no testeada

- **Categoría**: Testing
- **Área/plataforma**: Daemon
- **Evidencia**: `daemon.py:155-156,192-193`
- **Confianza**: Alta
- **Causa**: las excepciones `RequestException` del daemon en `/shutdown` y `status()` no se testean.
- **Impacto**: regresiones en el manejo de esas excepciones no se detectarían.
- **Corrección(es) propuesta(s)**: cubrir las ramas de `RequestException`. *(migra D7-R03)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-22 — Tests de symlink se saltan en Windows sin Developer Mode

- **Categoría**: Testing
- **Área/plataforma**: Windows
- **Evidencia**: `tests/test_cli.py:522-530` (12 tests de `TestSetupLinuxPath`)
- **Confianza**: Alta
- **Causa**: sin Developer Mode en Windows, los tests de symlink se saltan.
- **Impacto**: se reduce la cobertura efectiva de esos tests en Windows.
- **Corrección(es) propuesta(s)**: documentar el prerequisito y/o alternativa de cobertura. *(migra D7-R04)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-23 — ARM64 Linux sin suite dedicada

- **Categoría**: Testing
- **Área/plataforma**: aarch64
- **Evidencia**: `.circleci/config.yml:643-646`
- **Confianza**: Alta
- **Causa**: solo el smoke `version` valida el stack aarch64; no hay suite dedicada.
- **Impacto**: un bug específico de aarch64 podría pasar desapercibido. Relacionado con S1-32.
- **Corrección(es) propuesta(s)**: suite mínima en aarch64. *(migra D7-R05)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-24 — Pascal Script de desinstalación sin test unitario

- **Categoría**: Testing
- **Área/plataforma**: Windows
- **Evidencia**: `scripts/create_installer_windows.py:145-167`
- **Confianza**: Alta
- **Causa**: `CurUninstallStepChanged` del Pascal Script solo tiene validación Ruby estática.
- **Impacto**: la lógica de desinstalación no tiene test unitario que respalde sus cambios.
- **Corrección(es) propuesta(s)**: test de la lógica de desinstalación. *(migra D7-R06)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-25 — Branch `except Exception` del worker no cubierto

- **Categoría**: Testing
- **Área/plataforma**: Daemon
- **Evidencia**: `daemon/server.py:167-173`
- **Confianza**: Alta
- **Causa**: el branch `except Exception` del worker no se cubre explícitamente (solo `RuntimeError`).
- **Impacto**: regresiones en ese branch genérico no se detectarían en los tests.
- **Corrección(es) propuesta(s)**: test del branch genérico del worker. *(migra D7-R07)*
- **Decisión requerida**: No
- **Prioridad**: P2



**Documentación**

#### S1-26 — `CLAUDE.md` dice 296 tests (real: 314)

- **Categoría**: Documentation
- **Área/plataforma**: —
- **Evidencia**: `CLAUDE.md` (sección «tests/») dice «296 tests»; el conteo real es 314 (`docs/GOAL.md:220` correcto)
- **Confianza**: Alta
- **Causa**: `CLAUDE.md` dice «296 tests» pero el conteo real es 314.
- **Impacto**: inexactitud documental menor que puede confundir a quien lea.
- **Corrección(es) propuesta(s)**: actualizar el conteo en `CLAUDE.md`. *(migra D8-R01)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-27 — Sin plantilla de issue de bug

- **Categoría**: Documentation
- **Área/plataforma**: governance
- **Evidencia**: solo existe `.github/PULL_REQUEST_TEMPLATE.md`
- **Confianza**: Alta
- **Causa**: solo existe `.github/PULL_REQUEST_TEMPLATE.md`; no hay plantilla de issue de bug.
- **Impacto**: brecha de governance de release al no estandarizar reportes de bug.
- **Corrección(es) propuesta(s)**: añadir plantilla de issue de bug. *(migra D8-R03)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-28 — `CONTRIBUTING.md` omite el smoke-test de Windows

- **Categoría**: Documentation
- **Área/plataforma**: —
- **Evidencia**: `CONTRIBUTING.md` no menciona `test-installer-windows` (`install.ps1`)
- **Confianza**: Alta
- **Causa**: `CONTRIBUTING.md` omite el smoke-test de Windows (`install.ps1`).
- **Impacto**: falta de completitud documental para quien quiera contribuir en Windows.
- **Corrección(es) propuesta(s)**: documentar el smoke-test de Windows en `CONTRIBUTING.md`. *(migra D8-R04)*
- **Decisión requerida**: No
- **Prioridad**: P3



#### S1-33 — Runbook de falsos positivos solo para Defender

- **Categoría**: Documentation
- **Área/plataforma**: seguridad
- **Evidencia**: `SECURITY.md:124-156`
- **Confianza**: Alta
- **Causa**: el runbook de falsos positivos solo cubre Defender.
- **Impacto**: no documenta cómo reportar falsos positivos a otros AV (ClamAV, Gatekeeper).
- **Corrección(es) propuesta(s)**: extender el runbook a otros AV. *(migra D10-R05)*
- **Decisión requerida**: No
- **Prioridad**: P3



**Licencias**

#### S1-29 — Atribución de PerthNet/`resemble-perth` débil

- **Categoría**: Licensing
- **Área/plataforma**: —
- **Evidencia**: `THIRD-PARTY-LICENSES.md:29-33,264`
- **Confianza**: Alta
- **Causa**: la atribución de PerthNet (`resemble-perth`, MIT) es débil y carece de sección de atribución clara.
- **Impacto**: riesgo de cumplimiento de licencias por atribución insuficiente del componente.
- **Corrección(es) propuesta(s)**: añadir sección de atribución explícita para `resemble-perth`. *(migra D9-R02)*
- **Decisión requerida**: No
- **Prioridad**: P2



**Cadena de suministro / CI**

#### S1-30 — `pytest` pineado pero no sus plugins

- **Categoría**: Cadena de suministro
- **Área/plataforma**: CI
- **Evidencia**: `.circleci/config.yml:74,153` (`pytest==9.1.1`, sin pin de `pytest-xdist`/otros)
- **Confianza**: Alta
- **Causa**: `pytest` está pineado pero no sus plugins.
- **Impacto**: si se añaden plugins sin pin, la suite podría romperse por drift de versiones.
- **Corrección(es) propuesta(s)**: pinear los plugins de pytest. *(migra D10-R02)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-31 — Installers mockeados; `docs/SELF-HOSTED-INSTALL.md` inexistente

- **Categoría**: CI
- **Área/plataforma**: Documentation
- **Evidencia**: `.circleci/config.yml:253-277,304-327` (mock de `curl`/`sha256sum`/`hdiutil`); `docs/BUILD.md:210` referencia `docs/SELF-HOSTED-INSTALL.md`, ausente del árbol
- **Confianza**: Alta
- **Causa**: los smoke-tests mockean `curl`/`sha256sum`/`hdiutil` y no ejercen el flujo real; además `docs/BUILD.md` referencia `docs/SELF-HOSTED-INSTALL.md`, ausente.
- **Impacto**: el flujo real de instalación queda sin validar y hay un enlace roto en la documentación.
- **Corrección(es) propuesta(s)**: crear `docs/SELF-HOSTED-INSTALL.md` (o corregir la referencia) y valorar un smoke-test menos mockeado. *(migra D10-R03)*
- **Decisión requerida**: No
- **Prioridad**: P2



#### S1-32 — ARM64 Linux sin test dedicado (decisión consciente)

- **Categoría**: CI
- **Área/plataforma**: aarch64
- **Evidencia**: `.circleci/config.yml:669-673`
- **Confianza**: Alta
- **Causa**: no hay test dedicado en aarch64 (decisión consciente: la suite mockea el engine).
- **Impacto**: un bug específico de aarch64 podría pasar desapercibido. Relacionado con S1-23.
- **Corrección(es) propuesta(s)**: valorar un test dedicado aarch64. *(migra D10-R04)*
- **Decisión requerida**: No
- **Prioridad**: P3



### S0 — Informativos



#### S0-01 — `bootstrap.apply()` corre antes del `reconfigure` UTF-8 (riesgo nulo)

- **Categoría / Área**: Contrato · **Prioridad**: P3 · **Decisión requerida**: No
- **Evidencia**: `cli.py:22-27`; `__main__.py`
- **Observación**: `bootstrap.apply()` corre antes del `reconfigure` UTF-8 de `main()`; riesgo teórico si el bootstrap falla muy temprano, pero no emite texto estructurado, así que el impacto práctico es nulo. No es un defecto. *(migra D2-R03)*



#### S0-02 — `--force-update` sin log del tamaño liberado

- **Categoría / Área**: Observabilidad · **Prioridad**: P3 · **Decisión requerida**: No
- **Evidencia**: `cli.py:1083-1092`
- **Observación**: `--force-update` borra solo carpetas `models--ResembleAI--`* (correcto), pero sin logging explícito del tamaño liberado. Mejora opcional de observabilidad. *(migra D4-R01)*



#### S0-03 — AppImage Linux sin CUDA (documentado)

- **Categoría / Área**: Compatibilidad / Linux · **Prioridad**: P3 · **Decisión requerida**: No
- **Evidencia**: `build_linux.py`; `requirements-lock-linux-cpu.txt`
- **Observación**: el AppImage excluye CUDA (lock CPU-only) y está documentado; quien necesite GPU usa PyPI. Decisión de diseño, no un defecto. *(migra D5-R04)*



#### S0-04 — Lock universal con `nvidia-*` distinguido del binario (sin acción)

- **Categoría / Área**: Licencias · **Prioridad**: P3 · **Decisión requerida**: No
- **Evidencia**: `requirements-lock.txt`; `THIRD-PARTY-LICENSES.md:115-123`
- **Observación**: el lock universal incluye `nvidia-`* (CUDA EULA), correctamente distinguido de los binarios distribuidos. Sin acción; un auditor podría confundirlo. *(migra D9-R03)*



## Orden de corrección recomendado

No hay **P0**: sin hallazgos S4 y sin S3 que bloqueen el release de v0.6.0. Las fases agrupan los IDs por prioridad, dependencia y esfuerzo/impacto para alimentar la numeración de tareas de un plan posterior.

- **Fase 1 — P1 (antes de la próxima versión menor; alto impacto / bajo esfuerzo):** (sin pendientes). (Ya resueltos y fuera de esta fase: `S3-06` —oferta de fuente GPL en el release, cerrado el 2026-07-12: `publish-release` inyecta en las notas del Release el tarball de fuente GPLv3 §6 (`archive/refs/tags/<tag>.tar.gz`)—; `S3-07` —smoke test del binario congelado, cerrado el 2026-07-12: los smoke tests de los 4 bins corren `voice list` y validan que la voz `default` quedó empaquetada—; `S3-01` —contrato de cancelación, cerrado el 2026-07-12: el handler de `main()` en `cli.py:1661` ya devuelve `EXIT_INTERRUPTED` (130)—; `S3-02` —carrera del doble arranque, cerrada el 2026-07-12 con un PID/lock file atómico—; `S3-03` —bind del puerto sin manejo de `OSError`, cerrado el 2026-07-12: `serve()` en `daemon/run.py` ahora distingue `EADDRINUSE` y sale con `EXIT_DAEMON_PORT_IN_USE` (6)—; `S2-03` —documentar `--force-update` en `USAGE.md`, cerrado el 2026-07-12.)
- **Fase 2 — P2 (agendadas):** endurecimiento del daemon `S3-04` (memoria) y `S3-05` (concurrencia). (Ya resueltos y fuera de esta fase: `S1-05` —detección de daemon huérfano/zombie, cerrada el 2026-07-12 junto con `S3-02` mediante el PID/lock file compartido, tal como estaba previsto—, `S2-02` —macOS Intel, limitación aceptada—, `S1-23` —divergencia arm64 aceptada—, y el ciclo S1 del 2026-07-12: `S1-01`, `S1-09`, `S1-10`, `S1-11`, `S1-12`, `S1-13`, `S1-14`, `S1-17`, `S1-19`, `S1-20`, `S1-21`, `S1-24`, `S1-25`, `S1-27`, `S1-29`, `S1-30`, `S1-31`.)
- **Fase 3 — P3 (backlog):** sin pendientes. (Ya resueltos y fuera del backlog: riesgo aceptado `S2-01` —`/shutdown` sin token, aceptado formalmente el 2026-07-12 en `SECURITY.md`—, `S1-23` y `S1-32` —divergencia arm64 aceptada—, `S2-02` —macOS Intel, limitación aceptada—, `S1-33`, los informativos `S0-01`…`S0-04`, y el ciclo S1 del 2026-07-12: `S1-02`, `S1-03`, `S1-04`, `S1-06`, `S1-07`, `S1-08`, `S1-15`, `S1-16`, `S1-18`, `S1-22`, `S1-26`, `S1-28`.)



## Confirmación en CI

Hallazgos ya probados por lectura de código cuya evidencia multiplataforma o de runtime se confirma al correr CI:

- `S3-07` — la ampliación del smoke test se verifica en los jobs `build-linux-x64`, `build-linux-arm64` y `build-darwin-arm64` (`.circleci/config.yml:541,647,773`): un bundle sin voces de fábrica debe hacer fallar el job.
- `S1-22` — la omisión de los tests de symlink en Windows se observa en el job de Windows sin Developer Mode (`tests/test_cli.py:522-530`).
- `S1-23` / `S1-32` — la ausencia de suite dedicada aarch64 se confirma en los jobs ARM64 Linux (`.circleci/config.yml:643-646,669-673`), donde hoy solo corre el smoke `version`.
- `S1-31` — el grado de mockeo de los smoke-tests de instaladores se verifica en los jobs `test-installer-*` (`.circleci/config.yml:253-277,304-327`).
- `S1-11` / `S1-12` — la falta de auto-detección de AVX2/RAM solo se manifiesta en runtime sobre hardware real (CPU sin AVX2, <4GB), fuera del alcance del CI actual; se confirma su impacto solo en esas máquinas objetivo, no en el pipeline.

