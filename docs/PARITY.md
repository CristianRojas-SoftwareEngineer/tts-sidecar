# Paridad de experiencia entre sistemas operativos

Este documento registra el **estado de equivalencia funcional y de experiencia
de usuario** del canal nativo entre Windows, Linux y macOS, y enumera **qué
falta para cerrar la paridad completa**. El criterio no es la paridad
tecnológica (cada SO usa sus mecanismos idiomáticos: Inno Setup, AppImage,
`.dmg`/Cask — eso es aceptable por diseño), sino que el **usuario final
recorra un ciclo de vida equivalente**: instalar, usar, actualizar y
desinstalar con la misma cantidad de fricción, privilegios y residuo.

Fecha de corte: **v0.4.0**. Al cerrar una brecha, actualizar la tabla y la
sección correspondiente.

## Resumen ejecutivo

| Fase | Windows | Linux | macOS | ¿Paridad? |
|---|---|---|---|---|
| Instalación de una línea sin prerequisitos | ✅ `irm \| iex` | ✅ `curl \| sh` | ❌ no existe | **No** |
| Instalación sin privilegios de admin | ✅ per-user, sin UAC | ✅ `~/.local` | ⚠️ Cask sí; vía `.dmg` pide `sudo` | Parcial |
| Modelo provisionado al terminar de instalar | ✅ encadena `setup` | ✅ encadena `setup` | ⚠️ Cask: solo *caveat*; `.command`: pregunta s/n | Parcial |
| Verificación de checksum automática | ✅ | ✅ | ⚠️ Cask sí; `.dmg` manual no | Parcial |
| Primer arranque sin advertencia de reputación | ✅ (one-liner, sin MOTW) | ✅ (no aplica) | ⚠️ Cask sí; `.dmg` de navegador dispara Gatekeeper | Parcial |
| Uso (CLI, daemon, voces, contratos `--json`) | ✅ | ✅ | ✅ | **Sí** |
| Actualización sin residuo ni trampa | ✅ Inno reemplaza en sitio | ❌ acumula AppImages; symlink colgante si no se re-corre `setup` | ✅ `brew upgrade --cask` | **No** |
| Desinstalación integrada y con residuo cero | ✅ desinstalador del SO + `cleanup` | ❌ 3 pasos manuales, sin desinstalador | ⚠️ `brew uninstall` con `zap` incompleto | **No** |
| Cobertura de arquitecturas | x86_64 | x86_64 + aarch64 | arm64 | Limitación de toolchain (aceptada) |

**Conclusión**: la paridad es total en el *uso* y muy alta en la *instalación*
Windows↔Linux. Las brechas se concentran en **macOS** (instalación y
provisión) y en la **desinstalación/actualización** (fricción asimétrica y dos
residuos concretos). El detalle y el trabajo pendiente, por fase, a
continuación.

## Fase 1 — Instalación

### Estado

- **Windows**: `install.ps1` (`irm | iex`) resuelve el release, verifica el
  checksum, instala en silencio per-user (sin UAC, PATH en HKCU) y encadena
  `tts-sidecar setup`. Cero prerequisitos: PowerShell viene con el SO.
- **Linux**: `install.sh` (`curl | sh`) hace lo análogo: checksum, instala en
  `~/.local/opt/tts-sidecar/`, exporta `APPIMAGE` y encadena `setup` (que crea
  el symlink de PATH en `~/.local/bin`). Cero prerequisitos en la práctica
  (`curl` + coreutils).
- **macOS**: **no existe one-liner equivalente.** Las dos vías actuales:
  - **Cask de Homebrew** (`brew tap … && brew install --cask tts-sidecar`):
    automatiza checksum, PATH y cuarentena, pero **exige tener Homebrew
    instalado** — un prerequisito de terceros que la audiencia declarada del
    canal nativo ("usuario final sin Python", `docs/DISTRIBUTION.md`) no
    necesariamente tiene. Además **no provisiona el modelo**: Homebrew no
    permite post-install arbitrario, así que el Cask solo imprime un *caveat*
    remitiendo a `tts-sidecar setup` (`scripts/render_cask.py`).
  - **`.dmg` manual**: montar, arrastrar el `.app`, ejecutar
    `Instalar (PATH + modelo).command`, **teclear la contraseña de
    administrador** (`sudo` para el symlink en `/usr/local/bin`,
    `scripts/build_macos.py::_path_install_script`) y responder el prompt de
    descarga del modelo. Es la única vía de instalación del proyecto que pide
    privilegios elevados, y el checksum queda a cargo del usuario.

Asimetría documental derivada: la sección del README se titula «Instalación de
una línea (Linux y Windows)» y **no menciona el Cask**; el usuario de Mac que
llega al README solo ve la vía manual con `sudo`.

### Qué falta para la paridad

1. **Una vía de instalación macOS de una línea, sin Homebrew y sin `sudo`**
   (la brecha mayor). Diseño candidato, homólogo a `install.sh`: un
   `install-macos.sh` (`curl | sh`) que descargue el `.dmg` del release,
   verifique el checksum, monte con `hdiutil attach`, copie el `.app` a
   `~/Applications` (per-user, sin `sudo`), limpie la cuarentena con
   `xattr -dr com.apple.quarantine` (legítimo: el usuario ya expresó intención
   ejecutando el script), cree el symlink en `~/.local/bin` (o instruya sobre
   el PATH) y encadene `setup`. Cerraría de una vez: one-liner, sin admin,
   checksum, Gatekeeper y provisión.
2. Mientras (1) no exista: **documentar el Cask en el README** como vía
   preferente de macOS (retitular la sección a «Instalación de una línea» con
   las tres plataformas) y aceptar explícitamente sus dos huecos (Homebrew
   como prerequisito, `setup` manual post-instalación).
3. Evaluar si la vía `.dmg` puede ofrecer un symlink **per-user**
   (`~/.local/bin` con aviso de PATH, como Linux) en lugar de
   `/usr/local/bin` + `sudo`, dejando el `sudo` solo como opción.

## Fase 2 — Primer arranque (reputación del binario sin firmar)

### Estado

- **Windows**: el one-liner descarga por CLI (sin Mark-of-the-Web) y no
  dispara SmartScreen. La descarga por navegador sí, con salida de dos clics
  («Más información → Ejecutar de todas formas»).
- **Linux**: no existe un sistema de reputación equivalente. Sin fricción.
- **macOS**: el Cask limpia la cuarentena. El `.dmg` descargado por navegador
  dispara Gatekeeper, cuya salida (clic derecho → Abrir, o `xattr`) es menos
  descubrible que la de SmartScreen.

### Qué falta para la paridad

4. La solución de fondo es la **firma de código/notarización**, ya registrada
   como goal a largo plazo (`docs/GOAL.md`); la vía (1) de arriba elimina
   entretanto la fricción de Gatekeeper para quien use el one-liner, igualando
   la experiencia de Windows.

## Fase 3 — Uso

### Estado

**Paridad completa.** Mismos comandos, mismo daemon (puerto 8765), mismos
esquemas `--json` y exit codes, mismas voces de fábrica y de usuario
(`data_root()` por SO), mismo fail-fast de `speak`/`daemon start` sin modelo.
Las diferencias de backend de audio (pycaw/sounddevice/afplay) son tecnologías
equivalentes, no diferencias de experiencia.

Única salvedad, aceptada como limitación de toolchain y documentada en el
README: la cobertura de arquitecturas no es simétrica (sin Windows ARM64, sin
Mac Intel).

### Qué falta para la paridad

Nada pendiente en esta fase.

## Fase 4 — Actualización

### Estado

- **Windows**: repetir el one-liner (o el instalador nuevo); Inno reemplaza la
  instalación per-user en el mismo directorio y conserva el PATH. Limpio.
- **macOS (Cask)**: `brew upgrade --cask tts-sidecar` con `livecheck` — la
  mejor experiencia de actualización de las tres plataformas.
- **Linux**: la más frágil, con dos problemas:
  - Re-ejecutar `install.sh` con una versión nueva instala el AppImage
    versionado nuevo y reapunta el symlink, pero **no elimina el AppImage
    anterior**: `~/.local/opt/tts-sidecar/` acumula ~1-2 GB por versión en
    silencio (ni el script ni `cleanup` lo limpian).
  - En la vía manual, reemplazar el archivo sin re-correr `setup` deja el
    symlink de PATH colgante (trampa documentada en `USAGE.md` §"Actualizar de
    versión", pero trampa al fin).

### Qué falta para la paridad

5. **`install.sh` debe limpiar las versiones anteriores** al instalar una
   nueva: tras verificar e instalar el AppImage nuevo y reapuntar el symlink,
   eliminar los `tts-sidecar-*-<arch>.AppImage` previos del directorio de
   instalación (es de su propiedad exclusiva: `~/.local/opt/tts-sidecar/`).

## Fase 5 — Desinstalación

### Estado

El contrato (`USAGE.md` §"Desinstalación completa") es: datos primero
(`cleanup --all`), binario después. Lo que cambia por SO es el paso del
binario:

- **Windows**: desinstalador integrado al SO (Configuración → Aplicaciones),
  sin admin, revierte el PATH de HKCU automáticamente. **Dos pasos.**
- **Linux**: **tres pasos manuales sin desinstalador**: `setup --remove-path`,
  borrar `~/.local/opt/tts-sidecar/` a mano y `cleanup --all`. Olvidar el
  segundo deja gigabytes.
- **macOS**: `.command` de desinstalación (con `sudo`) + arrastrar a la
  Papelera + `cleanup --all`; o `brew uninstall --cask`. **Defecto concreto**:
  la stanza `zap trash:` del Cask (`scripts/render_cask.py`) solo lista
  `models--ResembleAI--Chatterbox-Multilingual-es-mx-latam` — **falta
  `models--ResembleAI--chatterbox`**, el repo base que `setup` descarga para el
  Voice Encoder (`cli.py::cmd_setup`). Quien confíe en `brew uninstall --zap`
  (la promesa idiomática de limpieza total de Homebrew) queda con cientos de
  MB de residuo que `cleanup --all` sí elimina en los otros SO.

### Qué falta para la paridad

6. **Completar el `zap` del Cask** con el repo base del modelo
   (`~/.cache/huggingface/hub/models--ResembleAI--chatterbox`) — corrección de
   una línea en `_CASK_TEMPLATE` de `scripts/render_cask.py`; se propaga al
   tap en el siguiente release vía `publish-metadata`.
7. **Un desinstalador de un paso para Linux**: candidato natural, un flag
   `setup --uninstall` (o subcomando `uninstall`) que encadene lo que hoy son
   tres pasos — quitar el symlink, borrar `~/.local/opt/tts-sidecar/` y
   ofrecer `cleanup --all` — dejando `USAGE.md` con un solo comando por SO.

## Registro de brechas (orden de prioridad)

| # | Brecha | SO | Impacto | Esfuerzo |
|---|---|---|---|---|
| 1 | Sin one-liner de instalación sin prerequisitos ni `sudo` | macOS | Alto: audiencia no técnica con experiencia de segunda clase | Medio (`install-macos.sh` homólogo a `install.sh`) |
| 6 | `zap` del Cask no borra el repo base del modelo | macOS | Alto: rompe la promesa de desinstalación limpia | Trivial (una línea + release) |
| 5 | `install.sh` acumula AppImages viejos al actualizar | Linux | Medio: residuo de GB silencioso | Bajo |
| 7 | Desinstalación en 3 pasos manuales, sin desinstalador | Linux | Medio | Medio (`setup --uninstall`) |
| 2 | El Cask no figura en el README (sección "una línea" excluye macOS) | macOS | Medio: la vía menos fricción de Mac es invisible | Trivial (docs) |
| 3 | Vía `.dmg` exige `sudo` (única instalación con admin) | macOS | Bajo si (1) se implementa | Bajo |
| 4 | Gatekeeper en `.dmg` de navegador (vs. SmartScreen evitado en Windows) | macOS | Bajo: mitigado por Cask y por (1); fondo = firma (roadmap) | Alto (firma) |

Las brechas 1-3 y 6 son de macOS; 5 y 7 de Linux; Windows no tiene brechas
abiertas. Ninguna requiere romper compatibilidad ni re-publicar artefactos
existentes: todas se cierran con scripts/documentación nuevos o en el
siguiente ciclo de release.
