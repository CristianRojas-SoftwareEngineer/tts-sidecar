# Roadmap: estado actual y camino al Goal inmediato

Este documento es el **registro vivo** del estado de implementación de
`tts-sidecar` y del trabajo pendiente para alcanzar el **Goal inmediato**, cuya
especificación, criterios de aceptación y condición de finalización viven en
[docs/GOAL.md](GOAL.md). El **Goal a largo plazo** (firma de código /
notarización) también se define en
[docs/GOAL.md](GOAL.md#goal-a-largo-plazo).

Mantener el estado y el roadmap aquí (separados de la especificación ideal)
permite que [docs/GOAL.md](GOAL.md) siga siendo la fuente de verdad del *qué* y
el *cuándo está hecho*, mientras este archivo responde al *dónde estamos* y *qué
falta*.

## Estado actual

**Implementado y verificable en el repo** (la validación end-to-end de los
instaladores por SO es externa al pipeline por diseño; ver la «Decisión de
validación E2E» en
[docs/GOAL.md](GOAL.md#validación-e2e)):

- Motor Chatterbox Multilingual V3 implementado (Python)
- Sistema de audio playback nativo por SO (pycaw/winsound/sounddevice/afplay)
- Daemon mode con IPC HTTP (FastAPI, puerto 8765)
- Optimizaciones de síntesis (n_cfm=4, max_new_tokens=500)
- Bypass del watermark PerthNet: el audio generado no lleva marca de agua (ver «Uso ético y responsable» en README/USAGE)
- Scripts de build PyInstaller por SO (Windows/Linux/macOS)
- **Canal PyPI** (`uv tool install tts-sidecar` / `pipx install tts-sidecar`), publicado automáticamente en cada tag `v*` junto al canal nativo (ver [docs/DISTRIBUTION.md](DISTRIBUTION.md))
- Descarga automática del modelo Chatterbox desde HuggingFace
- CLI completa con todos los comandos
- **Instalación auto-hospedada de una línea por SO** (Linux y Cask de macOS en v0.3.0; Windows en v0.4.0; one-liner macOS `install-macos.sh` en v0.5.0): `install.sh` (`curl | sh`) en Linux, `install-macos.sh` (`curl | sh`, sin Homebrew ni `sudo`) y el Cask de Homebrew propio en macOS, e `install.ps1` (`irm | iex`) en Windows (instalador Inno Setup per-user, sin UAC; entró en alcance al refutarse la premisa de SmartScreen — la descarga por CLI no aplica el Mark-of-the-Web). Todos los canales publican de forma autónoma, sin aprobación ni pull request a terceros. Ver [docs/SELF-HOSTED-INSTALL.md](SELF-HOSTED-INSTALL.md)
- **Paridad de experiencia entre los 3 SO** (v0.5.0): cerradas a nivel de código/scripts/tests seis de las brechas accionables de [docs/PARITY.md](PARITY.md) (one-liner macOS, `.command` sin `sudo`, limpieza de AppImages, `setup --uninstall` en Linux, `zap` del Cask completo, README con las tres plataformas). Quedan dos brechas abiertas de distinta naturaleza: la brecha de *desinstalación en un comando* (`setup --uninstall` multiplataforma en macOS/Windows) es **accionable y pertenece al goal inmediato** (código interno, sin gate externo); solo la brecha de *firma de código* (SmartScreen/Gatekeeper, binarios sin firmar, cross-SO) sigue diferida al goal a largo plazo
- Tests pytest (305 tests: timing, protocolo, daemon, CLI, voces, rutas, caché de modelo, audio, Cask y utilidades de build), más los smoke-tests de instaladores (bats Linux/macOS y Pester Windows) en CI
- Documentación sincronizada

## Trabajo pendiente (roadmap al Goal inmediato)

Seis de las brechas de paridad entre SO registradas en
[docs/PARITY.md](PARITY.md) quedaron cerradas a nivel de código/scripts/tests
en v0.5.0. Queda **una brecha accionable pendiente para el goal inmediato**: la
brecha de *desinstalación en un comando* — extender `setup --uninstall` a macOS
y Windows (código interno, sin gate externo). Solo la brecha de *firma de código*
(cross-SO) sigue diferida al goal a largo plazo. Además, la **marca de los
criterios de aceptación 10, 1-3 y 9**
depende de la validación por feedback de usuarios reales en Linux y macOS (la
validación E2E automatizable ya corre en CI; ver «Validación E2E» en
[docs/GOAL.md](GOAL.md#validación-e2e)).

**Pendiente accionable (brecha de *desinstalación en un comando*)** — `tts-sidecar setup --uninstall`
multiplataforma: hoy un guard de SO lo limita a Linux (`cli.py:687`). Extenderlo
a macOS (self-removal del `.app` en `~/Applications`/`/Applications` + symlink +
`cleanup --all`) y Windows (desinstalador de Inno vía `UninstallString` del
registro + `cleanup --all`), con tests pytest que cubran los tres SO en la
sección `TestSetupUninstall`. Espeja la instalación one-line de cada plataforma.

### Hacia el Goal inmediato

El objetivo, los [Criterios de aceptación](GOAL.md#criterios-de-aceptación) y la
[Condición de finalización](GOAL.md#condición-de-finalización) que definen la
meta están en [docs/GOAL.md](GOAL.md). Para cumplir el Goal inmediato falta
cerrar la brecha de *desinstalación en un comando* (código) y marcar los
criterios pendientes vía feedback de usuarios reales en Linux y macOS. Cuando
eso ocurra, el Goal inmediato se considera cumplido y solo la brecha de *firma
de código* (cross-SO) queda como pieza diferida al
Goal a largo plazo.
