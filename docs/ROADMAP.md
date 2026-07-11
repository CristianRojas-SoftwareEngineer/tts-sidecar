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
[docs/GOAL.md](GOAL.md#decisión-de-validación-e2e)):

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
- **Paridad de experiencia entre los 3 SO** (v0.5.0): cerradas a nivel de código/scripts/tests las brechas accionables de [docs/PARITY.md](PARITY.md) (one-liner macOS, `.command` sin `sudo`, limpieza de AppImages, `setup --uninstall`, `zap` del Cask completo, README con las tres plataformas); solo la brecha 4 (SmartScreen/Gatekeeper, binarios sin firmar, cross-SO) sigue diferida a la firma de código
- Tests pytest (305 tests: timing, protocolo, daemon, CLI, voces, rutas, caché de modelo, audio, Cask y utilidades de build), más los smoke-tests de instaladores (bats Linux/macOS y Pester Windows) en CI
- Documentación sincronizada

## Trabajo pendiente (roadmap al Goal inmediato)

Las brechas de paridad entre SO registradas en [docs/PARITY.md](PARITY.md)
quedaron cerradas a nivel de código/scripts/tests en v0.5.0 (solo la brecha 4,
SmartScreen/Gatekeeper, cross-SO, sigue diferida a la firma del goal a largo
plazo). Lo pendiente es la **marca de los criterios de aceptación 10, 1-3 y 9
por validación de feedback de usuarios reales** en Linux y macOS (la validación
E2E automatizable ya corre en CI; ver la «Decisión de validación E2E» en
[docs/GOAL.md](GOAL.md#decisión-de-validación-e2e)).

### Hacia el Goal inmediato

El objetivo, los [Criterios de aceptación](GOAL.md#criterios-de-aceptación) y la
[Condición de finalización](GOAL.md#condición-de-finalización) que definen la
meta están en [docs/GOAL.md](GOAL.md). Cuando esos criterios queden marcados
(vía feedback de usuarios reales en Linux y macOS), el Goal inmediato se
considera cumplido y la brecha 4 restante pasa a ser la única pieza diferida al
Goal a largo plazo.
