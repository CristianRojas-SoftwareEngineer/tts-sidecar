# Goal: Sistema TTS con Chatterbox Multilingual V3

---

## Objetivo

Obtener un sistema TTS **100% local** con audio nativo por sistema operativo, para transformar texto a audio en **español latino** de la mejor calidad disponible, distribuido bajo **licencia GPL-3.0-or-later** (con dependencias y modelo bajo licencias permisivas compatibles).

Motor TTS: **Chatterbox Multilingual V3** (ResembleAI) — 23+ idiomas, clonación de voz, licencia MIT.

**El sistema debe ser consumible via línea de comandos** para que cualquier aplicación en cualquier lenguaje de programación pueda invocarlo (Python, JavaScript/Node, Rust, Go, Java, C#, etc.)

---

## Requisitos del instalador

Estos requisitos aplican al **canal nativo** (binarios PyInstaller por SO),
que sigue siendo el canal recomendado para usuarios sin Python instalado:

- **Un solo instalador por SO**: Windows (.exe), Linux (.AppImage/.bin), macOS (.app)
- **Cero dependencias externas**: El usuario final no instala Python, Node, Rust ni nada más
- **Descarga + instalación + configuración** en un solo paso
- **Audio nativo**: playback usando APIs nativas de cada SO

El proyecto distribuye además un **canal PyPI** complementario
(`uv tool install tts-sidecar` / `pipx install tts-sidecar`) para audiencia
técnica con Python 3.13+ ya instalado, que no está sujeto a estos requisitos
(sí requiere Python, y en Linux la librería del sistema `libportaudio2`). Ver
[docs/DISTRIBUTION.md](DISTRIBUTION.md) para la matriz de trade-offs completa
entre ambos canales.

---

## Alcance

Implementar y validar la síntesis en español latinoamericano con voz propia del usuario usando Chatterbox Multilingual V3.

---

## Estructura del proyecto migrado

```
TTS-Sidecar/
├── src/
│   └── tts_sidecar/       # Paquete Python (publicable en PyPI)
│       ├── __init__.py       # Fuente única de versión (__version__)
│       ├── __main__.py       # Entry point de `python -m tts_sidecar`
│       ├── bootstrap.py      # apply() idempotente: warnings, env vars, mock pkg_resources
│       ├── engine.py         # Wrapper de Chatterbox
│       ├── audio.py          # Reproducción de audio nativa
│       ├── cli.py            # Interfaz CLI (invoca bootstrap.apply())
│       ├── timing.py         # Instrumentación y timing
│       ├── voices.py         # Resolución de voces usuario→fábrica
│       ├── paths.py          # Rutas: fábrica relativa al paquete, datos en user-data-dir por SO
│       ├── model_cache.py    # Detección del modelo en la caché de HF
│       ├── voices/           # Voces de FÁBRICA (empaquetadas en wheel y bundle)
│       │   └── default/      # reference.wav + speech.wav
│       └── daemon/           # Daemon mode (FastAPI + IPC)
│           ├── daemon.py    # Gestor del ciclo de vida
│           ├── server.py    # Endpoints FastAPI
│           ├── ipc.py       # Cliente HTTP
│           ├── protocol.py  # Modelos Pydantic
│           └── run.py       # Entry point (usa bootstrap.apply())
├── bin/
│   └── tts-sidecar          # Script de entry point (modo fuente)
├── scripts/                  # Scripts de build por SO
├── tests/                    # Suite de tests pytest
└── docs/
```

> El modelo `es-mx-latam` no se almacena en el repo: reside en la caché de
> HuggingFace del usuario (`~/.cache/huggingface/hub`) tras `tts-sidecar setup`.

---

## Comandos CLI objetivo (invocable desde cualquier lenguaje)

Los comandos están ordenados en secuencia de dependencia: cada paso solo
requiere que los anteriores hayan funcionado. El daemon es el camino principal
de uso: carga el modelo una sola vez y lo mantiene en memoria, eliminando el
overhead de carga en cada invocación. Por eso su ciclo de vida envuelve toda la
sesión: se arranca antes de sintetizar y se detiene al final.

```bash
# 1. Provisión (primera vez - chequeos + descarga el modelo si falta)
./tts-sidecar setup

# 2. Diagnóstico del sistema (no depende de nada)
./tts-sidecar version              # Versión instalada
./tts-sidecar doctor               # Chequeo de entorno y modelo
./tts-sidecar devices              # Dispositivos de audio disponibles

# 3. Arrancar el daemon (camino principal: carga el modelo en memoria una vez)
./tts-sidecar daemon start         # Iniciar daemon
./tts-sidecar daemon status        # Verificar que está activo

# 4. Clonación de voz (requiere dos archivos de audio)
./tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav

# 5. Listar voces registradas (verifica que la voz quedó registrada)
./tts-sidecar voice list

# 6. Síntesis a través del daemon (añade -v mi_voz para usar la voz clonada)
./tts-sidecar speak --text "Hola mundo" [-v mi_voz]                    # Reproducir
./tts-sidecar speak --text "Hola mundo" [-v mi_voz] --output audio.wav  # Exportar WAV

# 7. Eliminar voz clonada (limpieza)
./tts-sidecar voice remove --name mi_voz

# 8. Detener el daemon (cierre de la sesión, libera el modelo de memoria)
./tts-sidecar daemon stop
```

---

## Restricciones

- **100% local**: Sin APIs externas ni conexiones a internet para síntesis
- **Instalador único por SO (canal nativo)**: Un archivo ejecutable por
  plataforma; el canal PyPI complementario (ver
  [docs/DISTRIBUTION.md](DISTRIBUTION.md)) no está sujeto a esta restricción
- **Sin dependencias externas (canal nativo)**: El usuario final no necesita
  instalar nada más; el canal PyPI requiere Python 3.13+ y, en Linux,
  `libportaudio2` del sistema
- **Licencia**: El código propio se distribuye bajo GPL-3.0-or-later; todas las dependencias y el modelo usados deben tener licencias compatibles con GPLv3 (permisivas — MIT/BSD/Apache/ISC/PSF — o copyleft compatible, como LGPL-2.1+/MPL-2.0)

---

## Criterios de Aceptación

<!-- Los criterios 1-3 y 9 son claims de ejecución por SO: el pipeline de build
(CI + scripts/build_*.py) produce los instaladores y un smoke test automatizado
del binario congelado (`tts-sidecar version`), pero la validación end-to-end
sobre cada SO es por diseño externa al pipeline (ver "Decisión de validación
E2E" más abajo). -->

1. [ ] El instalador de Windows (.exe) funciona en Windows 10/11 sin dependencias (validación E2E por SO, ver "Decisión de validación E2E" más abajo)
2. [ ] El instalador de Linux funciona en distribuciones principales (validación E2E por SO, ver "Decisión de validación E2E" más abajo)
3. [ ] El instalador de macOS funciona en el mínimo declarado por `LSMinimumSystemVersion` (Apple Silicon; Mac Intel no soportado) — derivado dinámicamente del `MACOSX_DEPLOYMENT_TARGET` del toolchain de build, no un número fijo (validación E2E por SO, ver "Decisión de validación E2E" más abajo)
4. [x] `tts-sidecar speak --text "Hola mundo"` reproduce audio en español
5. [x] `tts-sidecar voice add --name test --reference ref.wav --speech speech.wav` clona la voz
6. [x] El audio generado suena en español con las características de la voz de referencia
7. [x] El español latinoamericano suena natural y con buena prosodia
8. [x] La síntesis funciona sin conexión a internet (modelo en local)
9. [ ] El instalador incluye todo lo necesario (no requiere instalaciones adicionales) (validación E2E por SO, ver "Decisión de validación E2E" más abajo)

### Decisión de validación E2E

La validación end-to-end de los instaladores (instalar → `setup` → `speak` real
→ desinstalar) **no se ejecuta dentro del pipeline de CI** por una decisión
consciente de diseño: requiere cuota de runner significativa (carga del modelo
Chatterbox + descarga de ~2 GB de pesos + síntesis real con audio) y
reproducirla en cada push no aporta señal proporcional a su coste. El pipeline
sí ejecuta un **smoke test automatizado** del binario congelado (`tts-sidecar
version`, exit 0) en los cuatro jobs de build, que detecta empaquetados rotos
(metadata faltante, `--collect-all` incompleto) sin pagar el coste del modelo.

Fuera del pipeline, la validación se reparte así:

- **Windows**: la realiza el propietario manualmente sobre su equipo local,
  instalando el artefacto de cada release, ejecutando el recorrido
  `setup` → `speak` → desinstalar, y registrando el resultado.
- **Linux y macOS**: dependen de **feedback de usuarios reales** que prueben la
  instalación y ejecución en sus equipos. Ese feedback (positivo o negativo) es
  la entrada de issues que cierra el circuito y guía correcciones específicas
  por plataforma.

Por tanto, los criterios 1-3 y 9 no son "pendientes" en el sentido de tareas
olvidadas: son el **borde externo** del proceso de calidad, donde el propietario
más el feedback de la comunidad reemplazan a un runner de CI que no podría
ejercitar la matriz de hardware/SO real. Cualquier issue reportado en estos
criterios se incorpora al ciclo de desarrollo como bug prioritario y motiva
fixes versionados.

---

## Condición de Finalización

La implementación está completa únicamente cuando:

- [x] El motor Chatterbox Multilingual V3 está implementado y funcional
- [x] La clonación de voz funciona con una muestra de ~10 segundos
- [x] El audio generado preserva las características de la voz original
- [x] El español latinoamericano suena natural
- [x] Hay scripts de build e instalador por cada SO (Windows, Linux, macOS) en el pipeline de CI
- [ ] Los instaladores funcionan sin ninguna dependencia externa (validación E2E por SO, ver "Decisión de validación E2E" arriba: smoke test automatizado en CI + validación manual Windows del propietario + feedback de usuarios reales en Linux y macOS)
- [x] **README.md** refleja la nueva arquitectura con Chatterbox
- [x] **docs/DESIGN.md** corresponde al estado implementado
- [x] El daemon mode está implementado y funciona correctamente
- [x] Los logs están normalizados con estructura consistente
- [x] Los tests pytest pasan (280/280)

---

## Estado Actual

**Implementado y verificable en el repo** (la validación end-to-end de los
instaladores por SO es externa al pipeline por diseño; ver "Decisión de
validación E2E" arriba):
- Motor Chatterbox Multilingual V3 implementado (Python)
- Sistema de audio playback nativo por SO (pycaw/winsound/sounddevice/afplay)
- Daemon mode con IPC HTTP (FastAPI, puerto 8765)
- Optimizaciones de síntesis (n_cfm=4, max_new_tokens=500)
- Bypass del watermark PerthNet: el audio generado no lleva marca de agua (ver «Uso ético y responsable» en README/USAGE)
- Scripts de build PyInstaller por SO (Windows/Linux/macOS)
- **Canal PyPI** (`uv tool install tts-sidecar` / `pipx install tts-sidecar`),
  publicado automáticamente en cada tag `v*` junto al canal nativo (ver
  [docs/DISTRIBUTION.md](DISTRIBUTION.md))
- Descarga automática del modelo Chatterbox desde HuggingFace
- CLI completa con todos los comandos
- Tests pytest (280 tests: timing, protocolo, daemon, CLI, voces, rutas, caché de modelo, audio y utilidades de build)
- Documentación sincronizada

---

## Roadmap (compromisos a futuro)

### Instalación auto-hospedada por SO (Linux y macOS)

**Motivación**: además del canal nativo (descarga directa del artefacto) y el
canal PyPI, el proyecto ofrece una instalación auto-hospedada por SO que resuelve
descubrimiento, instalación, disponibilidad del comando en el PATH, provisión del
modelo y desinstalación en un flujo guiado, reutilizando los artefactos que el
canal nativo ya publica. La especificación completa está en
[docs/SELF-HOSTED-INSTALL.md](SELF-HOSTED-INSTALL.md).

**Compromiso**:
- **Linux**: un script `install.sh` servido por el propio repo, ejecutable con
  `curl … | sh` sobre el `.AppImage` del release.
- **macOS**: un tap de Homebrew propio con un Cask que instala el CLI desde el
  `.dmg` del release, actualizado automáticamente en cada publicación por un job
  de CI.

**Publicación autónoma**: ambos canales publican sin aprobación ni pull request a
terceros; se apoyan en repos propios y en la automatización de CI sobre el propio
repo.

### Firma de código Windows (SignPath) y notarización Apple (macOS)

**Motivación**: los binarios del canal nativo no están firmados, por lo que
Windows SmartScreen y macOS Gatekeeper bloquean el primer arranque (ver
`SECURITY.md` §"Artefactos sin firmar" y `docs/BUILD.md` §"Limitación
conocida: firma de código y notarización"). El canal PyPI (ver
[docs/DISTRIBUTION.md](DISTRIBUTION.md)) ya mitiga esta fricción para
audiencia técnica, pero no la elimina para el canal nativo, que sigue siendo
el recomendado para usuarios no técnicos.

**Compromiso**:
- **Windows**: firma Authenticode vía [SignPath Foundation](https://signpath.org/)
  (firma gratuita para proyectos open source), integrada al job de CI que
  produce el instalador `.exe`.
- **macOS**: notarización con una cuenta Apple Developer ID, integrada al job
  de CI que produce el `.dmg`.

**Condiciones de entrada**:
- Windows: aprobación del proyecto por el programa SignPath OSS.
- macOS: alta de una cuenta Apple Developer (de pago).

**Criterio de cierre**: los instaladores de Windows y macOS generados por CI
arrancan sin disparar SmartScreen ni Gatekeeper en una instalación limpia.

Una vez disponible la firma Authenticode, esta habilita además un canal de
instalación auto-hospedada en Windows análogo a los de Linux y macOS (ver
[docs/SELF-HOSTED-INSTALL.md](SELF-HOSTED-INSTALL.md)). Sin firma, la instalación
sin alertas en Windows la provee el canal PyPI, que genera el ejecutable en la
máquina del usuario.
