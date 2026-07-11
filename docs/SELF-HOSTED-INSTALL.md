# Instalación auto-hospedada por sistema operativo

Este documento especifica la extensión del canal nativo de `tts-sidecar` (los
artefactos PyInstaller que se publican como GitHub Release en cada tag `v*`) hacia
una experiencia de **instalación auto-hospedada** por sistema operativo: descubrir →
instalar → comando disponible en el PATH → provisión guiada del modelo → desinstalar.

## Alcance

Se implementan cinco piezas:

1. **Instalador Linux** — un script `install.sh` servido por el propio repo, que se
   ejecuta con `curl … | sh` sobre el `.AppImage` del release.
2. **Cask de macOS** — un tap de Homebrew propio que instala el CLI desde el `.dmg`
   del release, actualizado automáticamente en cada publicación (vía complementaria
   para usuarios de Homebrew).
3. **Instalador macOS (`curl | sh`)** — un script `install-macos.sh` servido por el
   propio repo, homólogo a `install.sh`, que instala desde el `.dmg` del release sin
   Homebrew ni `sudo`. Es la vía de una línea sin prerequisitos para macOS.
4. **Instalador Windows** — un script `install.ps1` servido por el propio repo, que
   se ejecuta con `irm … | iex` sobre el instalador Inno Setup (per-user) del release.
5. **Endurecimiento del build** — ajustes al empaquetado que reducen los falsos
   positivos de antivirus en el ejecutable de Windows y en el resto de artefactos.

**Registro de cambio de decisión (Windows).** La versión inicial de este documento
declaró el instalador auto-hospedado de Windows «fuera de alcance», bajo la premisa
de que todo instalador descargado dispararía SmartScreen mientras el proyecto no
tuviera firma de código (Authenticode). La investigación empírica posterior refutó
esa premisa: **la descarga por CLI (`curl`, `Invoke-WebRequest`, `WebClient`, `gh`)
no aplica el Mark-of-the-Web**, así que un instalador bajado por script no dispara
SmartScreen; solo la descarga por navegador lo sella con `ZoneId=3`. El obstáculo
restante era el UAC del instalador per-machine original, eliminado al migrar el
Inno Setup a **per-user** (`PrivilegesRequired=lowest`,
`%LOCALAPPDATA%\Programs\tts-sidecar`, PATH en `HKCU\Environment`). Con ambas
premisas caídas, la vía auto-hospedada de Windows sí aporta valor y entra en
alcance. La reserva que persiste: Microsoft Defender **Antivirus** es independiente
del MOTW y puede marcar el binario sin firma (runbook WDSI en `SECURITY.md`); la
solución de SmartScreen para la descarga por navegador sigue siendo la firma de
código (`docs/GOAL.md`).

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

## Instalador Windows (`irm | iex`)

- **Entregable**: `install.ps1` en la raíz del repo, servido desde
  `raw.githubusercontent.com/<owner>/TTS-Sidecar/main/install.ps1`. Uso:
  `irm <url> | iex`. Al no ser un `.ps1` en disco, `irm | iex` no pasa por la
  Execution Policy; la alternativa inspeccionable es
  `iwr <url> -OutFile install.ps1; .\install.ps1`.
- **Flujo del script**: resolver `releases/latest` de la GitHub Releases API →
  seleccionar el asset `tts-sidecar-*-x86_64-setup.exe` (solo hay build x86_64
  para Windows: sin selección de arquitectura) → descargar el instalador y
  `SHA256SUMS.txt` con `Invoke-WebRequest` (sin MOTW: no dispara SmartScreen) →
  verificar el checksum (`Get-FileHash`; aborta si no coincide) → ejecutar el
  instalador en silencio (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`, sin
  `-Verb RunAs`: la instalación es per-user, sin UAC) → recomponer el PATH de la
  sesión desde el registro (el `HKCU\Environment` nuevo no llega solo a la sesión
  en curso) → ejecutar `tts-sidecar setup` (necesario porque `skipifsilent` omite
  el checkbox de setup en instalación silenciosa; `-NoSetup` lo desactiva).
- **Cambio de código**: el Inno Setup generado por
  `scripts/create_installer_windows.py` migra de per-machine a **per-user**:
  `PrivilegesRequired=lowest`, instalación en `%LOCALAPPDATA%\Programs\tts-sidecar`
  (patrón convencional, p. ej. VS Code) y PATH en `HKCU\Environment` en lugar de
  HKLM, con la reversión del PATH al desinstalar sobre la misma clave. Nota de
  migración: quien tenga la versión per-machine debe desinstalarla primero (Panel
  de control, con admin); instalar la per-user encima puede dejar dos
  instalaciones y PATH duplicado.
- **Docs**: línea de instalación en `README.md` y `USAGE.md`; nota en `SECURITY.md`
  espejo de la de Linux (checksum previo, sin privilegios, sin MOTW por CLI,
  remisión al runbook WDSI).
- **Tests**: smoke-test Pester (`tests/installer/install.tests.ps1`) que hace
  dot-source de `install.ps1` y mockea sus funciones propias, en el job de CI
  `test-installer-windows` (espejo de `test-installer-linux`). Cubre el flujo
  exitoso, el aborto ante checksum corrupto y el release sin asset de Windows.
  El generador `.iss` per-user se cubre en `tests/test_create_installer_windows.py`.
- **Cierre** (automatizado, sin intervención humana): el smoke-test Pester y los
  tests del generador `.iss` pasan en CI; la desinstalación limpia la provee el
  desinstalador de Inno Setup (revierte PATH HKCU) más `cleanup --all`.
- **Riesgos residuales**: Defender Antivirus puede marcar el binario sin firma
  (independiente del MOTW; runbook WDSI); el instalador descargado por navegador
  sí lleva MOTW y dispara SmartScreen (lo resuelve la firma de código, no este
  script).

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

## Instalador macOS (`curl | sh`)

- **Entregable**: `install-macos.sh` en la raíz del repo, servido desde
  `raw.githubusercontent.com/<owner>/TTS-Sidecar/main/install-macos.sh`. Uso:
  `curl -fsSL <url> | sh`. Es la vía de una línea de macOS sin prerequisitos:
  ni Homebrew (a diferencia del Cask) ni `sudo` (a diferencia del `.dmg` manual).
- **Herramientas del host**: solo binarios del sistema base de macOS. No existe
  `sha256sum` (se usa `shasum -a 256 -c`) ni `jq` (parseo con `grep`/`sed`, como
  `install.sh`); montaje con `hdiutil`, copia con `ditto`, limpieza de cuarentena
  con `xattr`.
- **Flujo del script**: resolver `releases/latest` de la GitHub Releases API →
  **guard de arquitectura** `uname -m` = `arm64` (Mac Intel no soportado; mensaje
  claro) → seleccionar el asset `tts-sidecar-*-arm64.dmg` → descargar el `.dmg` y
  `SHA256SUMS.txt` → verificar el checksum con `shasum` (aborta si no coincide) →
  `hdiutil attach -nobrowse -readonly -mountpoint <tmp>` → localizar el `.app` en
  el volumen → copiar a `~/Applications` con `ditto` (reemplazando la versión
  anterior si existe) → `hdiutil detach` → `xattr -dr com.apple.quarantine` sobre
  el `.app` copiado (legítimo: el usuario ya expresó intención ejecutando el
  script) → crear el symlink de PATH `~/.local/bin/tts-sidecar → <app>/Contents/
  MacOS/tts-sidecar` → invocar `"<app>/Contents/MacOS/tts-sidecar" setup`.
- **Integración de PATH per-user**: `~/.local/bin` **no** está en el PATH por
  defecto de zsh en macOS; el script detecta esa ausencia y emite el aviso con la
  línea exacta para `~/.zshrc`, sin mutar dotfiles (mismo patrón que
  `_integrate_linux_path`). Sin cambios de código en el CLI: la integración vive
  en el propio script.
- **Docs**: línea de instalación en `README.md` y `USAGE.md`; nota en
  `SECURITY.md` generalizada a los tres scripts (checksum previo).
- **Tests**: smoke-test `bats` (`tests/installer/install-macos.bats`) que mockea
  `curl`/`uname`/`hdiutil`/`xattr`/`ditto` por PATH (`shasum` real), en el job de
  CI `test-installer-macos` que corre en el executor macOS real (mismo que
  `test-macos`). Cubre el rechazo de arquitectura no-arm64, la selección del
  asset, el aborto ante checksum corrupto, la instalación feliz y el reemplazo de
  una instalación anterior.
- **Cierre** (automatizado): el smoke-test `bats` pasa en CI; la validación E2E
  real, sin un Mac del propietario, se difiere al circuito de feedback de usuarios
  (ver `docs/GOAL.md` §«Validación E2E»).
- **Riesgos residuales**: solo Apple Silicon (el guard aborta en Intel); la firma
  de código/notarización sigue diferida (goal a largo plazo), pero la limpieza de
  cuarentena elimina la fricción de Gatekeeper para quien use el one-liner.

## Desinstalación limpia

`tts-sidecar setup --uninstall` deja el sistema idéntico a antes de instalar **en
un comando en los tres SO**: encadena `cleanup --all` (caché del modelo + datos de
usuario), revierte la integración de PATH y borra el binario, **en ese orden**
(datos independientes primero, ancla al final). Es un dispatch por SO sobre un
contrato compartido: cancelar el cleanup aborta la desinstalación sin borrar nada
(cancelación atómica, salida 0), y solo aplica al canal nativo (guard `is_frozen`;
desde fuente o pip/uv remite a `pip uninstall`).

- **Linux**: quita el symlink de PATH y borra `~/.local/opt/tts-sidecar/`.
  (`setup --remove-path` sigue disponible como reversión fina de solo el symlink.)
- **macOS**: quita el symlink de `~/.local/bin` y borra el `.app` (resuelto desde
  el ejecutable, cubre `~/Applications`, `/Applications` y el Cask). Con **Homebrew
  Cask** el comando lo detecta por la metadata del Caskroom y **difiere a `brew
  uninstall --cask --zap tts-sidecar`** sin borrar nada (borrar el `.app` a mano
  dejaría el Caskroom inconsistente; su `zap trash:` incluye los **dos** repos del
  modelo: el multilingüe y el base `chatterbox`).
- **Windows**: borra los datos en proceso y **delega** el binario y la reversión
  del PATH (`HKCU\Environment`) al desinstalador de Inno, lanzado desacoplado con
  el `QuietUninstallString` del registro (el SO mantiene el lock del `.exe`). La
  vía idiomática (Configuración → Aplicaciones, sin admin) sigue como alternativa.

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
- **Windows**: SmartScreen depende del MOTW, y el MOTW depende del **medio de
  descarga**: el navegador sella el archivo con `ZoneId=3` y dispara SmartScreen;
  la descarga por CLI o script (`curl`, `Invoke-WebRequest`, `WebClient`, `gh`) no
  aplica la marca, así que el instalador bajado por `install.ps1` no dispara
  SmartScreen al ejecutarse. Microsoft Defender **Antivirus** es independiente del
  MOTW: puede marcar el binario sin firma venga de donde venga; el endurecimiento
  del build reduce esos falsos positivos y el runbook WDSI da la vía de
  remediación. El canal pip evita ambas alertas de raíz, porque genera el
  ejecutable en la máquina del usuario. El instalador descargado por navegador
  seguirá disparando SmartScreen hasta que el proyecto tenga firma de código
  (Authenticode).

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
4. **Instalador Windows** — depende de la migración per-user del `.iss` (el script
   requiere instalación silenciosa sin elevación); sin infraestructura nueva.

Los tres instaladores son entregables independientes: se pueden publicar y anunciar
por separado, y ninguno bloquea los canales nativo o pip existentes.

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
