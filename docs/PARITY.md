# Paridad de experiencia entre sistemas operativos

Este documento registra el **estado de equivalencia funcional y de experiencia
de usuario** del canal nativo entre Windows, Linux y macOS, y enumera **qué
falta para cerrar la paridad completa**. El criterio no es la paridad
tecnológica (cada SO usa sus mecanismos idiomáticos: Inno Setup, AppImage,
`.dmg`/Cask — eso es aceptable por diseño), sino que el **usuario final
recorra un ciclo de vida equivalente**: instalar, usar, actualizar y
desinstalar con la misma cantidad de fricción, privilegios y residuo.

Fecha de corte: **v0.5.0**. Al cerrar una brecha, actualizar la tabla y la
sección correspondiente.

## Resumen ejecutivo

| Fase | Windows | Linux | macOS | ¿Paridad? |
|---|---|---|---|---|
| Instalación de una línea sin prerequisitos | ✅ `irm \| iex` | ✅ `curl \| sh` | ✅ `curl \| sh` (`install-macos.sh`) | **Sí** |
| Instalación sin privilegios de admin | ✅ per-user, sin UAC | ✅ `~/.local` | ✅ `~/.local` (one-liner y `.command` sin `sudo`) | **Sí** |
| Modelo provisionado al terminar de instalar | ✅ encadena `setup` | ✅ encadena `setup` | ✅ one-liner/`.command` encadenan `setup` (Cask: *caveat*) | **Sí** |
| Verificación de checksum automática | ✅ | ✅ | ✅ (one-liner con `shasum`; Cask sí) | **Sí** |
| Primer arranque sin advertencia de reputación | ✅ (one-liner, sin MOTW) | ✅ (no aplica) | ⚠️ one-liner y Cask limpian cuarentena; `.dmg` de navegador dispara Gatekeeper | Parcial (brecha 4: firma) |
| Uso (CLI, daemon, voces, contratos `--json`) | ✅ | ✅ | ✅ | **Sí** |
| Actualización sin residuo ni trampa | ✅ Inno reemplaza en sitio | ✅ re-ejecutar one-liner limpia AppImages viejos | ✅ `brew upgrade --cask` / re-ejecutar one-liner | **Sí** |
| Desinstalación integrada y con residuo cero | ✅ desinstalador del SO + `cleanup` | ✅ `setup --uninstall` (un paso) | ✅ `.command` sin `sudo` + `cleanup`; `brew uninstall --zap` completo | **Sí** |
| Cobertura de arquitecturas | x86_64 | x86_64 + aarch64 | arm64 | Limitación de toolchain (aceptada) |

**Conclusión**: con v0.5.0 la paridad es **completa** en instalación, uso,
actualización y desinstalación en los tres SO. La única fase que no alcanza
paridad plena es el *primer arranque* en macOS (brecha 4): el one-liner y el
Cask limpian la cuarentena, pero el `.dmg` descargado por navegador sigue
disparando Gatekeeper. Su fondo es la firma de código/notarización, diferida
por diseño al goal a largo plazo ([docs/GOAL.md](GOAL.md)). El detalle por
fase, a continuación.

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

Asimetría documental (cerrada en v0.5.0): el README ahora se titula
«Instalación de una línea» y documenta los tres SO más el Cask como alternativa
de macOS.

### Estado tras v0.5.0

Las tres brechas de esta fase quedaron **cerradas**:

1. **[CERRADA]** Existe `install-macos.sh` (`curl | sh`): descarga el `.dmg`
   del release, verifica el checksum con `shasum -a 256 -c`, monta con
   `hdiutil attach`, copia el `.app` a `~/Applications` (per-user, sin `sudo`),
   limpia la cuarentena con `xattr -dr com.apple.quarantine`, crea el symlink
   per-user en `~/.local/bin` (con aviso de PATH) y encadena `setup`. Cierra de
   una vez: one-liner, sin admin, checksum y provisión; mitiga Gatekeeper (ver
   brecha 4). Smoke-test `bats` en el job CI `test-installer-macos`.
2. **[CERRADA]** El README documenta la instalación de una línea para los tres
   SO y presenta el Cask como alternativa de macOS para usuarios de Homebrew.
3. **[CERRADA]** Los scripts `.command` del `.dmg` crean el symlink **per-user**
   en `~/.local/bin` (con aviso de PATH), sin `sudo`. Ninguna vía de instalación
   del proyecto pide ya privilegios de administrador.

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

4. **[MITIGADA, fondo diferido]** La solución de fondo es la **firma de
   código/notarización**, registrada como goal a largo plazo (`docs/GOAL.md`).
   El one-liner `install-macos.sh` (brecha 1) y el Cask limpian la cuarentena y
   eliminan la fricción de Gatekeeper para quien los use, igualando la
   experiencia de Windows; solo el `.dmg` descargado por navegador sigue
   disparándolo. Es la **única brecha que permanece abierta** en este registro.

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
- **Linux**: re-ejecutar `install.sh` con una versión nueva instala el AppImage
  nuevo, reapunta el symlink y **elimina los AppImages anteriores** del
  directorio de instalación (cerrado en v0.5.0). En la vía manual, reemplazar el
  archivo sin re-correr `setup` sigue dejando el symlink de PATH colgante (trampa
  documentada en `USAGE.md`), pero la vía recomendada (re-ejecutar el one-liner)
  ya no la tiene.

### Qué falta para la paridad

5. **[CERRADA]** `install.sh` elimina las versiones anteriores tras instalar y
   dar permisos al AppImage nuevo: un bucle POSIX borra los
   `tts-sidecar-*.AppImage` previos de `~/.local/opt/tts-sidecar/` (de su
   propiedad exclusiva), dejando exactamente un AppImage. Cubierto por un test
   `bats` de actualización.

## Fase 5 — Desinstalación

### Estado

El contrato (`USAGE.md` §"Desinstalación completa") es: datos primero
(`cleanup --all`), binario después. Lo que cambia por SO es el paso del
binario:

- **Windows**: desinstalador integrado al SO (Configuración → Aplicaciones),
  sin admin, revierte el PATH de HKCU automáticamente. **Dos pasos.**
- **Linux**: `tts-sidecar setup --uninstall` lo hace en **un paso** (cerrado en
  v0.5.0): quita el symlink de PATH, borra `~/.local/opt/tts-sidecar/` y encadena
  `cleanup --all`. (`setup --remove-path` se conserva como reversión fina del
  symlink.)
- **macOS**: `.command` de desinstalación (ahora **sin `sudo`**, symlink
  per-user) + arrastrar a la Papelera + `cleanup --all`; o `brew uninstall
  --cask --zap`, cuya stanza `zap trash:` ya lista los **dos** repos del modelo
  (`Chatterbox-Multilingual-es-mx-latam` y el base `chatterbox`), cerrada en
  v0.5.0. Se propaga al tap en el release vía `publish-metadata`.

### Qué falta para la paridad

6. **[CERRADA]** El `zap` del Cask incluye el repo base del modelo
   (`~/.cache/huggingface/hub/models--ResembleAI--chatterbox`) además del
   multilingüe — corrección en `_CASK_TEMPLATE` de `scripts/render_cask.py`,
   cubierta por test; se propaga al tap con el release v0.5.0 vía
   `publish-metadata`.
7. **[CERRADA]** `tts-sidecar setup --uninstall` desinstala Linux en un paso:
   quita el symlink, borra `~/.local/opt/tts-sidecar/` y encadena `cleanup
   --all` (con confirmación o `--yes`), con contrato `--json` y tests pytest.

## Registro de brechas (orden de prioridad)

| # | Brecha | SO | Estado | Cierre |
|---|---|---|---|---|
| 1 | Sin one-liner de instalación sin prerequisitos ni `sudo` | macOS | ✅ Cerrada (v0.5.0) | `install-macos.sh` (`curl \| sh`) |
| 6 | `zap` del Cask no borra el repo base del modelo | macOS | ✅ Cerrada (v0.5.0) | Repo base añadido a `_CASK_TEMPLATE` |
| 5 | `install.sh` acumula AppImages viejos al actualizar | Linux | ✅ Cerrada (v0.5.0) | Limpieza de versiones en `install.sh` |
| 7 | Desinstalación en 3 pasos manuales, sin desinstalador | Linux | ✅ Cerrada (v0.5.0) | `setup --uninstall` |
| 2 | El Cask no figura en el README (sección "una línea" excluye macOS) | macOS | ✅ Cerrada (v0.5.0) | README con las tres plataformas + Cask |
| 3 | Vía `.dmg` exige `sudo` (única instalación con admin) | macOS | ✅ Cerrada (v0.5.0) | `.command` per-user en `~/.local/bin` |
| 4 | Gatekeeper en `.dmg` de navegador (vs. SmartScreen evitado en Windows) | macOS | ⚠️ Abierta (diferida) | Mitigada por one-liner y Cask; fondo = firma (goal a largo plazo) |

Con v0.5.0 quedan cerradas las seis brechas accionables (1-3, 5-7). La **única
brecha abierta es la 4** (Gatekeeper), mitigada por el one-liner y el Cask y con
su fondo —la firma de código/notarización— diferido por diseño al goal a largo
plazo de [docs/GOAL.md](GOAL.md). Ningún cierre rompió compatibilidad ni
re-publicó artefactos existentes: todos se materializan en el release v0.5.0.
