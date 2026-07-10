# Instalación auto-hospedada por sistema operativo

Este documento especifica la extensión del canal nativo de `tts-sidecar` (los
artefactos PyInstaller que se publican como GitHub Release en cada tag `v*`) hacia
una experiencia de **instalación auto-hospedada** por sistema operativo: descubrir →
instalar → comando disponible en el PATH → provisión guiada del modelo → desinstalar.

## Alcance

Se implementan tres piezas:

1. **Instalador Linux** — un script `install.sh` servido por el propio repo, que se
   ejecuta con `curl … | sh` sobre el `.AppImage` del release.
2. **Cask de macOS** — un tap de Homebrew propio que instala el CLI desde el `.dmg`
   del release, actualizado automáticamente en cada publicación.
3. **Endurecimiento del build** — ajustes al empaquetado que reducen los falsos
   positivos de antivirus en el ejecutable de Windows y en el resto de artefactos.

**Fuera de alcance.** No se construye un instalador auto-hospedado para Windows
(fuente winget). Mientras Windows no cuente con firma de código (Authenticode), un
instalador descargado seguiría disparando SmartScreen, por lo que no aporta valor
frente a los canales ya disponibles. En Windows, la instalación sin alertas la provee
hoy el **canal pip** (`pip`/`uv`/`pipx`), que genera el ejecutable en la máquina del
usuario y no arrastra la marca de descarga (ver «Comportamiento frente a antivirus»).

## Principios

- **Publicación autónoma.** Publicar una versión nueva no requiere la aprobación ni
  la revisión de un tercero, ni un pull request a un proyecto externo. Los repos
  propios (el tap de Homebrew) y la automatización de CI sobre el propio repo están
  bajo control total del proyecto y no cuentan como terceros: un `git push` a un repo
  propio no es un PR a un proyecto externo. Esto descarta los catálogos oficiales
  (`winget-pkgs`, `homebrew-cask`, Flathub, Snap Store) como vía de publicación.
- **La fricción de instalación del usuario es aceptable.** Que el usuario ejecute
  comandos (`chmod +x`, `brew tap`, `brew install`) es esperable y no viola el
  principio anterior, que aplica solo a la publicación.
- **CI 100% en CircleCI.** Toda la automatización de publicación vive en
  `.circleci/config.yml`; el proyecto no usa GitHub Actions, para operar un solo
  sistema de CI.
- **Publicación directa del Release.** El job `publish-release` publica el GitHub
  Release directo, sin borrador: sus assets son públicos en cuanto el job termina, y
  `releases/latest` apunta a la versión nueva sin desfase. El tag es el punto de no
  retorno, igual que en `publish-pypi`. Esto es lo que permite que un job posterior
  del mismo pipeline lea los assets ya públicos.

## Glosario

Términos externos usados en este documento:

- **AppImage / `.dmg`**: los formatos de artefacto nativo de Linux y macOS que el
  canal nativo ya produce. El instalador Linux y el Cask de macOS se apoyan en ellos
  tal cual, sin rehornearlos.
- **Cask**: la receta de Homebrew (`Casks/tts-sidecar.rb`) que describe cómo instalar
  una aplicación distribuida como binario. Vive en un **tap**: un repositorio Git que
  Homebrew añade como fuente de recetas (`brew tap`).
- **Context de CircleCI**: un contenedor de variables de entorno secretas, visible
  solo por los jobs que lo declaran. Es el mecanismo con el que se inyectan las
  credenciales de publicación.
- **Canal pip / PyPI**: instalar con `pip`/`uv`/`pipx`. Descarga el paquete y genera
  el ejecutable en la máquina del usuario, por lo que no arrastra la marca de descarga
  ni dispara alertas del SO.
- **Gatekeeper (macOS) / SmartScreen (Windows)**: los sistemas que inspeccionan un
  archivo descargado de internet y advierten al usuario antes de ejecutarlo.
- **Mark-of-the-Web (MOTW)**: la marca que Windows y macOS añaden a todo archivo
  bajado de internet; es lo que activa a SmartScreen/Gatekeeper. Un archivo generado
  localmente (como el del canal pip) no la lleva.
- **Firma de código (Authenticode en Windows, notarización en macOS)**: sellar el
  ejecutable con un certificado que prueba quién lo creó y que no fue alterado. Es lo
  que más reduce las alertas. Es un compromiso a futuro (ver `docs/GOAL.md`).
- **UPX**: un compresor de ejecutables. El malware lo usa para esconderse, así que su
  presencia eleva la sospecha del antivirus.
- **Metadata PE**: los campos de identidad (empresa, producto, versión) que un `.exe`
  de Windows puede llevar embebidos. Su ausencia hace el ejecutable más anónimo y
  sospechoso ante el clasificador de Microsoft Defender.
- **WDSI**: el portal de Microsoft (*Windows Defender Security Intelligence*,
  `microsoft.com/wdsi`) donde se reportan los falsos positivos de Defender para que
  los reclasifiquen.

## Requisitos previos de Homebrew (ya provistos)

El Cask de macOS necesita dos recursos de una sola vez, ya creados:

- El repositorio tap `homebrew-tts-sidecar` (público), que aloja
  `Casks/tts-sidecar.rb`.
- El context de CircleCI `homebrew-tap`, con la variable `HOMEBREW_TAP_PAT` (un PAT
  fine-grained con permiso `Contents:RW` solo sobre el tap), que autoriza el push del
  Cask actualizado.

El instalador Linux no necesita ningún recurso previo.

## Endurecimiento del build

Los ejecutables de PyInstaller disparan la heurística de los antivirus: el patrón de
«desempaquetar y ejecutar», el bootloader genérico y la falta de señales de identidad
hacen que el clasificador los puntúe como sospechosos. Estos ajustes, baratos y sin
dependencia de terceros, dan señales de confianza y una vía de remediación. Se hacen
antes del instalador Linux, porque el flag compartido es un cambio único que consumen
todos los artefactos.

- **`--noupx` en los flags compartidos** (`scripts/build_utils.py`,
  `common_pyinstaller_args()`): pasar el flag de forma explícita garantiza que el
  ejecutable nunca se comprima con UPX, aunque el servidor de CI tenga UPX instalado.
  Aplica a todos los builds de PyInstaller, incluido el bootloader del `.AppImage`.
  Se cubre con un test (la función no tiene test hoy; patrón de
  `tests/test_build_windows.py`).
- **Metadata PE en el `.exe` de Windows** (`scripts/build_windows.py`,
  `--version-file` con empresa, producto y versión): da al clasificador de Defender
  las señales de identidad que hoy faltan. Es exclusivo de Windows: el `.AppImage` es
  ELF, no PE. Se cubre con un test.
- **Runbook de reporte a WDSI** (`SECURITY.md`, sección de artefactos sin firmar): una
  guía paso a paso para reportar a Microsoft cuando un release sea marcado por
  Defender. Cubre solo la **detección de Defender Antivirus** —una firma concreta
  (p. ej. `Trojan:Win32/Wacatac`) que, tras revisión de un analista, Microsoft borra
  globalmente para todos los Defender—. **No** desactiva SmartScreen, que es
  reputación y solo la resuelve la firma de código. El reporte se puede hacer con el
  binario sin firmar, y firmar no borra una detección ya existente (solo el reporte lo
  hace). Sin firma, la reputación se acumula por archivo, así que cada versión nueva
  puede requerir un reporte propio; con firma de código, la reputación se hereda entre
  versiones y esa recurrencia disminuye mucho.

**Cierre**: el `.exe` lleva metadata PE, todos los builds pasan `--noupx`, ambos
cubiertos por test, y existe el runbook en `SECURITY.md`.

## Instalador Linux (`curl | sh`)

- **Entregable**: `install.sh` en la raíz del repo, servido desde
  `raw.githubusercontent.com/<owner>/TTS-Sidecar/main/install.sh`. Uso:
  `curl -fsSL <url> | sh`.
- **Flujo del script**: resolver `releases/latest` de la GitHub Releases API (no
  requiere autenticación en repos públicos) → leer `uname -m` → seleccionar el asset
  `.AppImage` de la arquitectura → descargar el AppImage y `SHA256SUMS.txt` →
  verificar el checksum → `chmod +x` → instalar en `~/.local/opt/tts-sidecar/` →
  `export APPIMAGE=<ruta>` e invocar `"$APPIMAGE" setup`, que integra el PATH y
  descarga el modelo.
- **Cambio de código**: `_integrate_linux_path()` (`src/tts_sidecar/cli.py`) activa el
  symlink de PATH cuando la variable de entorno `APPIMAGE` está presente. El script se
  apoya en esa vía, así que se **endurece el contrato** para que exportar `APPIMAGE`
  desde fuera sea una entrada oficial y soportada, cubierta por un test (patrón de
  `TestSetupLinuxPath` en `tests/test_cli.py`). `cmd_setup()` ya es no interactivo y
  apto para invocarse desde el script sin cambios.
- **Docs**: una línea de instalación en `README.md` y `USAGE.md`; nota en
  `SECURITY.md` sobre la ejecución de un script remoto y su mitigación (el propio
  script verifica el checksum antes de ejecutar nada).
- **Tests**: smoke-test de shell con `bats`, mockeando `curl`/`uname`/`sha256sum`, en
  un job de CI dedicado. Cubre la selección de arquitectura, la elección del asset y
  el aborto ante un checksum corrupto.
- **Cierre** (automatizado, sin intervención humana): el smoke-test `bats` pasa en CI,
  y el mecanismo de desinstalación limpia (ver «Desinstalación limpia») está
  implementado y cubierto por test.
- **Riesgos residuales**: glibc < 2.35 (el script lo detecta y advierte); el PATH no
  se propaga a la sesión actual (el CLI ya lo avisa; el script no modifica
  `.bashrc`/`.zshrc` sin consentimiento).

## Cask de macOS

- **Entregables**:
  - `Casks/tts-sidecar.rb` en el tap `homebrew-tts-sidecar`, con las stanzas:
    `version`, `sha256`, `url` (al `.dmg` del release), `binary` apuntando a
    `Contents/MacOS/tts-sidecar`, `livecheck` (`strategy :github_latest`),
    `zap trash:` (caché del modelo y datos de usuario) y `caveats` que sugiere
    `tts-sidecar setup`.
  - El job `publish-metadata` en `.circleci/config.yml`, con
    `requires: [publish-release]` y los filtros de tag `only: /^v.*/`. Tras el Release
    público, lee la versión de `CIRCLE_TAG` y el `sha256` del `.dmg` desde
    `SHA256SUMS.txt` (recuperado con `gh release download "$CIRCLE_TAG" -p
    SHA256SUMS.txt`, de forma durable e idempotente, sin depender del workspace),
    reescribe el Cask y hace push al tap con el context `homebrew-tap`. Regenerar y
    re-empujar produce el mismo resultado, así que el reintento es seguro en cualquier
    momento.
- **Experiencia de usuario**:
  `brew tap <owner>/tts-sidecar && brew install --cask tts-sidecar`. Homebrew enlaza
  el binario en el prefix (`/opt/homebrew/bin`, ya en el PATH) sin sudo, y elimina el
  atributo de cuarentena, con lo que mitiga Gatekeeper. Toda la integración de PATH,
  la desinstalación y la limpieza de cuarentena las resuelve Homebrew: el CLI no
  necesita lógica específica de macOS.
- **Build**: el `.dmg` se consume tal cual; no requiere cambios.
- **Docs**: actualizar `docs/RELEASING.md` (prerequisitos del tap y el context; paso
  de publicación automática del Cask tras `publish-release`), y afinar la sección de
  macOS en `docs/DISTRIBUTION.md` y `docs/BUILD.md`.
- **Tests**: test del generador del Cask (patrón de `tests/test_build_windows.py`) que
  valida que las stanzas se reescriben correctamente desde `CIRCLE_TAG` y
  `SHA256SUMS.txt`.
- **Cierre** (automatizado, sin intervención humana): el test del generador del Cask
  pasa; si son viables sin un Mac, checks estáticos en CI (`brew audit`/`brew style` o
  instalación headless); el Cask incluye `zap trash:` para la desinstalación limpia
  (ver «Desinstalación limpia»).
- **Bootstrap y riesgos residuales**: el **primer** push del Cask al tap es manual (un
  paso de arranque único, porque `publish-metadata` actualiza un Cask que ya debe
  existir); a partir de ahí el job lo mantiene. Verificar que el nombre del Cask sea
  único y que `livecheck` resuelva bien contra los GitHub Releases.

## Desinstalación limpia

Ambos instaladores dejan el sistema idéntico a antes de instalar: se eliminan el
binario, la integración de PATH, la caché del modelo y los datos de usuario.

- **Linux**: `tts-sidecar setup --remove-path` revierte el symlink de PATH, y se
  borra el AppImage de `~/.local/opt/tts-sidecar/`; `tts-sidecar cleanup --all` elimina
  la caché del modelo y los datos de usuario.
- **macOS**: `brew uninstall --cask tts-sidecar` quita el binario y el enlace, y la
  stanza `zap trash:` borra la caché del modelo y los datos de usuario.

El cierre de cada instalador exige que este mecanismo esté implementado y cubierto por
test; la comprobación de que no queda ningún residuo en un sistema real pertenece a la
validación E2E final.

## Comportamiento frente a antivirus

Los instaladores auto-hospedados no eliminan las alertas de antivirus por sí mismos,
salvo el Cask en macOS. El panorama real por sistema operativo:

- **Linux**: no hay un inspector equivalente a Gatekeeper/SmartScreen que actúe al
  arrancar. La única superficie es ejecutar un script bajado de internet, mitigada
  porque el script verifica el checksum antes de ejecutar nada.
- **macOS**: el Cask elimina el atributo de cuarentena al instalar, lo que mitiga
  Gatekeeper de forma estructural. Descargar el `.dmg` a mano, en cambio, sigue
  requiriendo notarización (firma de código).
- **Windows**: el canal pip evita las alertas de raíz, porque genera el ejecutable en
  la máquina del usuario, sin MOTW. El ejecutable nativo descargado seguirá disparando
  SmartScreen y, ocasionalmente, Defender, hasta que el proyecto tenga firma de código
  (Authenticode); el endurecimiento del build reduce los falsos positivos de Defender
  pero no toca SmartScreen.

Las dos vías que eliminan las alertas de raíz son estructurales (el canal pip) o de
firma de código (compromiso a futuro, `docs/GOAL.md`).

## Orden de implementación

1. **Endurecimiento del build** — `--noupx` y la metadata PE son un cambio único en
   los scripts de build que consumen todos los artefactos; se hace primero para que el
   `.AppImage` de Linux y el `.exe` de Windows salgan ya endurecidos. El runbook WDSI
   puede escribirse en paralelo.
2. **Instalador Linux** — independiente, sin infraestructura nueva.
3. **Cask de macOS** — introduce el job `publish-metadata` en CircleCI y se apoya en
   los requisitos previos de Homebrew.

Los dos instaladores son entregables independientes: se pueden publicar y anunciar por
separado, y ninguno bloquea los canales nativo o pip existentes.

## Validación E2E (fase final del proyecto)

La validación end-to-end no forma parte del alcance de implementación de este
documento ni es criterio de cierre de ninguna de sus piezas. Es la última validación
del proyecto completo:

- **Presupone el proyecto entero implementado** —motor, CLI, daemon, canales de
  distribución, estos instaladores y todo lo demás— y listo para publicarse en su
  versión final.
- **Es costosa y se ejecuta una sola vez**, no por commit: valida el sistema completo
  sobre artefactos reales en sistemas limpios por SO —instalación real (`curl | sh` en
  una VM Linux con glibc ≥ 2.35; `brew install --cask` en un Mac limpio), provisión
  del modelo y desinstalación sin residuos—, además de los procesos de build y release
  de cada SO.
- **Cierra la primera versión**: cuando pasa, se da por finalizado el release de la
  primera versión del proyecto. Es el único punto, junto con el bootstrap inicial del
  Cask, donde hay intervención humana.

Hasta ese punto, toda validación de cada cambio es completamente automatizada (tests
unitarios, tests de generadores, smoke-tests `bats`, checks estáticos en CI).
