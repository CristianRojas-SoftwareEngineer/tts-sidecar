# Paridad de experiencia entre sistemas operativos

Este documento registra el **estado de equivalencia funcional y de experiencia de usuario** del canal nativo entre Windows, Linux y macOS, y enumera **qué falta para cerrar la paridad completa**. El criterio no es la paridad tecnológica (cada SO usa sus mecanismos idiomáticos: Inno Setup, AppImage, `.dmg`/Cask — eso es aceptable por diseño), sino que el **usuario final recorra un ciclo de vida equivalente**: instalar, usar, actualizar y desinstalar con la misma cantidad de fricción, privilegios y residuo.

Fecha de corte: **v0.5.0**. Cada brecha se identifica por un **nombre descriptivo** (no por número: la numeración secuencial se vuelve inconsistente a medida que se cierran brechas). Al cerrar una brecha, actualizar la tabla y la sección correspondiente.

## Resumen ejecutivo

| Fase | Windows | Linux | macOS | ¿Paridad? |
|---|---|---|---|---|
| Instalación de una línea sin prerequisitos | ✅ `irm \| iex` | ✅ `curl \| sh` | ✅ `curl \| sh` (`install-macos.sh`) | **Sí** |
| Instalación sin privilegios de admin | ✅ per-user, sin UAC | ✅ `~/.local` | ✅ `~/.local` (one-liner y `.command` sin `sudo`) | **Sí** |
| Modelo provisionado al terminar de instalar | ✅ encadena `setup` | ✅ encadena `setup` | ✅ one-liner/`.command` encadenan `setup` (Cask: *caveat*) | **Sí** |
| Verificación de checksum automática | ✅ | ✅ | ✅ (one-liner con `shasum`; Cask sí) | **Sí** |
| Primer arranque sin advertencia de reputación | ⚠️ one-liner esquiva MOTW; `.exe` de navegador dispara SmartScreen | ✅ (no aplica) | ⚠️ one-liner/Cask limpian cuarentena; `.dmg` de navegador dispara Gatekeeper | Parcial (brecha de *firma de código*, cross-SO) |
| Uso (CLI, daemon, voces, contratos `--json`) | ✅ | ✅ | ✅ | **Sí** |
| Actualización sin residuo ni trampa | ✅ Inno reemplaza en sitio | ✅ re-ejecutar one-liner limpia AppImages viejos | ✅ `brew upgrade --cask` / re-ejecutar one-liner | **Sí** |
| Desinstalación integrada y con residuo cero | ✅ desinstalador del SO + `cleanup` | ✅ `setup --uninstall` (un paso) | ⚠️ Cask: `brew uninstall --zap` (un paso); one-liner: 3 pasos (`.command` + Papelera + `cleanup`), sin `setup --uninstall` | Parcial (brecha de *desinstalación en un comando*, accionable) |
| Cobertura de arquitecturas | x86_64 | x86_64 + aarch64 | arm64 | Limitación de toolchain (aceptada) |

**Conclusión**: con v0.5.0 la paridad es **completa** en instalación, uso y actualización en los tres SO, y en desinstalación salvo la vía one-liner de macOS. Quedan dos brechas abiertas, en dos fases: la de **firma de código** (primer arranque en Windows y macOS, por binarios sin firmar) y la de **desinstalación en un comando** (vía one-liner de macOS). En desinstalación, Linux tiene `setup --uninstall` de un paso y macOS vía Cask tiene `brew uninstall --cask --zap`, pero la vía one-liner de macOS aún exige tres pasos manuales y carece de `setup --uninstall`. Las dos brechas se distinguen por su naturaleza: la de **desinstalación en un comando es accionable** (extender `setup --uninstall` a macOS y Windows es código interno, sin gate externo — pertenece al goal inmediato), mientras que la de **firma de código** está diferida por diseño al goal a largo plazo por depender de terceros (firma/notarización, [docs/GOAL.md](GOAL.md)). El detalle por fase, a continuación.

## Fase 1 — Instalación

### Estado

- **Windows**: `install.ps1` (`irm | iex`) resuelve el release, verifica el checksum, instala en silencio per-user (sin UAC, PATH en HKCU) y encadena `tts-sidecar setup`. Cero prerequisitos: PowerShell viene con el SO.
- **Linux**: `install.sh` (`curl | sh`) hace lo análogo: checksum, instala en `~/.local/opt/tts-sidecar/`, exporta `APPIMAGE` y encadena `setup` (que crea el symlink de PATH en `~/.local/bin`). Cero prerequisitos en la práctica (`curl` + coreutils).
- **macOS**: **no existe one-liner equivalente.** Las dos vías actuales:
  - **Cask de Homebrew** (`brew tap … && brew install --cask tts-sidecar`): automatiza checksum, PATH y cuarentena, pero **exige tener Homebrew instalado** — un prerequisito de terceros que la audiencia declarada del canal nativo ("usuario final sin Python", `docs/DISTRIBUTION.md`) no necesariamente tiene. Además **no provisiona el modelo**: Homebrew no permite post-install arbitrario, así que el Cask solo imprime un *caveat* remitiendo a `tts-sidecar setup` (`scripts/render_cask.py`).
  - **`.dmg` manual**: montar, arrastrar el `.app`, ejecutar `Instalar (PATH + modelo).command`, **teclear la contraseña de administrador** (`sudo` para el symlink en `/usr/local/bin`, `scripts/build_macos.py::_path_install_script`) y responder el prompt de descarga del modelo. Es la única vía de instalación del proyecto que pide privilegios elevados, y el checksum queda a cargo del usuario.

Asimetría documental (cerrada en v0.5.0): el README ahora se titula «Instalación de una línea» y documenta los tres SO más el Cask como alternativa de macOS.

### Estado tras v0.5.0

Las tres brechas de esta fase quedaron **cerradas**:

- **Brecha de *one-liner de instalación en macOS* [CERRADA]**: existe `install-macos.sh` (`curl | sh`): descarga el `.dmg` del release, verifica el checksum con `shasum -a 256 -c`, monta con `hdiutil attach`, copia el `.app` a `~/Applications` (per-user, sin `sudo`), limpia la cuarentena con `xattr -dr com.apple.quarantine`, crea el symlink per-user en `~/.local/bin` (con aviso de PATH) y encadena `setup`. Cierra de una vez: one-liner, sin admin, checksum y provisión; mitiga Gatekeeper (ver brecha de *firma de código*). Smoke-test `bats` en el job CI `test-installer-macos`.
- **Brecha de *Cask en el README* [CERRADA]**: el README documenta la instalación de una línea para los tres SO y presenta el Cask como alternativa de macOS para usuarios de Homebrew.
- **Brecha de *instalación sin `sudo` en macOS* [CERRADA]**: los scripts `.command` del `.dmg` crean el symlink **per-user** en `~/.local/bin` (con aviso de PATH), sin `sudo`. Ninguna vía de instalación del proyecto pide ya privilegios de administrador.

## Fase 2 — Primer arranque (reputación del binario sin firmar)

### Estado

- **Windows**: el one-liner descarga por CLI (sin Mark-of-the-Web) y no dispara SmartScreen. La descarga por navegador sí, con salida de dos clics («Más información → Ejecutar de todas formas»).
- **Linux**: no existe un sistema de reputación equivalente. Sin fricción.
- **macOS**: el Cask limpia la cuarentena. El `.dmg` descargado por navegador dispara Gatekeeper, cuya salida (clic derecho → Abrir, o `xattr`) es menos descubrible que la de SmartScreen.

### Qué falta para la paridad

- **Brecha de *firma de código* [MITIGADA, diferida al goal a largo plazo, cross-SO]**: la solución de fondo es la **firma de código/notarización** (goal a largo plazo, `docs/GOAL.md`): firma Authenticode en Windows (SmartScreen) y notarización en macOS (Gatekeeper). Los one-liners de ambos SO descargan por CLI y esquivan el Mark-of-the-Web, y el Cask de macOS limpia además la cuarentena; pero el `.exe` de Windows y el `.dmg` de macOS **descargados por navegador** disparan la advertencia del SO respectivo, porque ambos binarios son sin firmar. No es una asimetría exclusiva de macOS: Windows tiene el mismo comportamiento con SmartScreen. Es cross-SO por naturaleza, y está diferida porque su fondo depende de terceros (SignPath OSS, Apple Developer).

## Fase 3 — Uso

### Estado

**Paridad completa.** Mismos comandos, mismo daemon (puerto 8765), mismos esquemas `--json` y exit codes, mismas voces de fábrica y de usuario (`data_root()` por SO), mismo fail-fast de `speak`/`daemon start` sin modelo. Las diferencias de backend de audio (pycaw/sounddevice/afplay) son tecnologías equivalentes, no diferencias de experiencia.

Única salvedad, aceptada como limitación de toolchain y documentada en el README: la cobertura de arquitecturas no es simétrica (sin Windows ARM64, sin Mac Intel).

### Qué falta para la paridad

Nada pendiente en esta fase.

## Fase 4 — Actualización

### Estado

- **Windows**: repetir el one-liner (o el instalador nuevo); Inno reemplaza la instalación per-user en el mismo directorio y conserva el PATH. Limpio.
- **macOS (Cask)**: `brew upgrade --cask tts-sidecar` con `livecheck` — la mejor experiencia de actualización de las tres plataformas.
- **Linux**: re-ejecutar `install.sh` con una versión nueva instala el AppImage nuevo, reapunta el symlink y **elimina los AppImages anteriores** del directorio de instalación (cerrado en v0.5.0). En la vía manual, reemplazar el archivo sin re-correr `setup` sigue dejando el symlink de PATH colgante (trampa documentada en `USAGE.md`), pero la vía recomendada (re-ejecutar el one-liner) ya no la tiene.

### Qué falta para la paridad

- **Brecha de *acumulación de AppImages* [CERRADA]**: `install.sh` elimina las versiones anteriores tras instalar y dar permisos al AppImage nuevo: un bucle POSIX borra los `tts-sidecar-*.AppImage` previos de `~/.local/opt/tts-sidecar/` (de su propiedad exclusiva), dejando exactamente un AppImage. Cubierto por un test `bats` de actualización.

## Fase 5 — Desinstalación

### Estado

El contrato (`USAGE.md` §"Desinstalación completa") es: datos primero (`cleanup --all`), binario después. Lo que cambia por SO es el paso del binario:

- **Windows**: desinstalador integrado al SO (Configuración → Aplicaciones), sin admin, revierte el PATH de HKCU automáticamente. **Dos pasos.**
- **Linux**: `tts-sidecar setup --uninstall` lo hace en **un paso** (cerrado en v0.5.0): quita el symlink de PATH, borra `~/.local/opt/tts-sidecar/` y encadena `cleanup --all`. (`setup --remove-path` se conserva como reversión fina del symlink.)
- **macOS**: dos vías con experiencia distinta. Vía **Cask**: `brew uninstall --cask --zap` en **un paso** (app + symlink + los dos repos del modelo). Vía **one-liner / `.dmg`**: **tres pasos manuales** — ejecutar el `.command` de desinstalación (quita el symlink per-user, sin `sudo`), arrastrar el `.app` a la Papelera y correr `tts-sidecar cleanup --all`; `setup --uninstall` **no existe en macOS** (su guard de SO lo limita a Linux, `cli.py:687`).

### Qué falta para la paridad

- **Brecha de *`zap` completo del Cask* [CERRADA]**: el `zap` del Cask incluye el repo base del modelo (`~/.cache/huggingface/hub/models--ResembleAI--chatterbox`) además del multilingüe — corrección en `_CASK_TEMPLATE` de `scripts/render_cask.py`, cubierta por test; se propaga al tap con el release v0.5.0 vía `publish-metadata`.
- **Brecha de *desinstalador de Linux* [CERRADA]**: `tts-sidecar setup --uninstall` desinstala Linux en un paso: quita el symlink, borra `~/.local/opt/tts-sidecar/` y encadena `cleanup --all` (con confirmación o `--yes`), con contrato `--json` y tests pytest.
- **Brecha de *desinstalación en un comando* [ABIERTA — accionable, goal inmediato]**: la desinstalación de un comando solo existe en Linux (`setup --uninstall`) y en macOS vía Cask (`brew uninstall --cask --zap`); la vía one-liner de macOS aún requiere tres pasos manuales (`.command` + Papelera + `cleanup --all`) porque `setup --uninstall` tiene un guard de SO que lo limita a Linux (`cli.py:687`). Solución (pendiente de implementación): hacer `setup --uninstall` multiplataforma — macOS con self-removal del `.app` (en `~/Applications` o `/Applications`) + symlink + `cleanup --all`; Windows invocando el desinstalador de Inno vía registro + `cleanup --all` — espejando la instalación one-line de cada SO. No está diferida: es código interno sin gate externo ni dependencia de la cristalización del producto, así que pertenece al goal inmediato (ver [docs/GOAL.md](GOAL.md#desinstalación-en-un-comando)).

## Registro de brechas

| Brecha | Fase | SO | Estado | Cierre |
|---|---|---|---|---|
| *one-liner de instalación en macOS* | Instalación | macOS | ✅ Cerrada (v0.5.0) | `install-macos.sh` (`curl \| sh`) |
| *Cask en el README* | Instalación | macOS | ✅ Cerrada (v0.5.0) | README con las tres plataformas + Cask |
| *instalación sin `sudo` en macOS* | Instalación | macOS | ✅ Cerrada (v0.5.0) | `.command` per-user en `~/.local/bin` |
| *acumulación de AppImages* | Actualización | Linux | ✅ Cerrada (v0.5.0) | Limpieza de versiones en `install.sh` |
| *`zap` completo del Cask* | Desinstalación | macOS | ✅ Cerrada (v0.5.0) | Repo base añadido a `_CASK_TEMPLATE` |
| *desinstalador de Linux* | Desinstalación | Linux | ✅ Cerrada (v0.5.0) | `setup --uninstall` |
| *desinstalación en un comando* | Desinstalación | macOS + Windows | ⚠️ Abierta (accionable, goal inmediato) | Mitigada en Cask; solución = `setup --uninstall` multiplataforma (pendiente) |
| *firma de código* | Primer arranque | Windows + macOS | ⚠️ Abierta (diferida, cross-SO) | Mitigada por los one-liners (CLI sin MOTW) y el Cask; fondo = firma/notarización (goal a largo plazo) |

Con v0.5.0 quedan cerradas las seis brechas accionables originales. Hay **dos brechas abiertas**, de naturaleza distinta: la de **desinstalación en un comando** (vía one-liner de macOS) es **accionable y pertenece al goal inmediato** — su solución, `setup --uninstall` multiplataforma, es código interno sin gate externo ni dependencia de la cristalización del producto; la de **firma de código** (primer arranque, cross-SO) permanece **diferida al goal a largo plazo** porque su fondo (firma/notarización) depende de terceros. Ambas están mitigadas en su síntoma pero no resueltas en código: la de firma la esquivan los one-liners y el Cask, y la de desinstalación la resuelve el Cask en macOS aunque no la vía one-liner. Ningún cierre rompió compatibilidad ni re-publicó artefactos existentes: todos se materializan en el release v0.5.0.
