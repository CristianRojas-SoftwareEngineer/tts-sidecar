# Revisión: instalación auto-hospedada por SO (script Linux, tap/Cask Homebrew; winget diferido)

Índice de hallazgos y roadmap de la extensión a una experiencia de instalación
**auto-hospedada** por SO, como refinamiento del canal nativo existente:

- **Linux**: script `curl | sh` sobre el `.AppImage` (Fase 1, activa).
- **macOS**: tap/Cask de Homebrew propio sobre el `.dmg` (Fase 2, activa; metadata
  publicada por el job `publish-metadata`).
- **Windows**: fuente winget (`Microsoft.PreIndexed.Package`) **diferida** a un
  roadmap futuro, condicionada a firma Authenticode vía SignPath Foundation y ROI
  positivo; ver Línea B y la sección «Roadmap futuro (diferido)».

Este documento es el insumo probado para el plan de implementación posterior; el
roadmap (sección final) fija el orden de fases, requisitos y criterios de cierre.
Fecha de la auditoría: 2026-07-08. Revisado el 2026-07-08 con la decisión del
propietario de mantener el CI **100% en CircleCI** (sin GitHub Actions) y **eliminar
el paso de draft** de `publish-release` (ver H-2 y la decisión «Arquitectura de CI»).
La eliminación del paso de draft **ya está implementada** (2026-07-08): `publish-release`
publica el Release directo sin `--draft` y `docs/RELEASING.md`, `docs/BUILD.md` y
`docs/DISTRIBUTION.md` están sincronizados con ese comportamiento. Es el único
entregable del ciclo materializado en el repo; el resto del roadmap (Fases 0-2 y
Línea A) sigue pendiente y es insumo de `create-plan`. El canal winget queda como
entrada futura diferida, sin alcance activo en este ciclo.

## Glosario (términos técnicos usados en este documento)

Definiciones breves para no asumir conocimiento previo:

- **Antivirus / alertas de seguridad del SO**: los sistemas que inspeccionan un
  archivo descargado y deciden si "avisar" al usuario. En Windows son
  **Microsoft Defender** y **SmartScreen**; en macOS es **Gatekeeper**; más los
  antivirus de terceros. Antes usé la sigla "AV" — significa simplemente
  *antivirus*.
- **Falso positivo**: cuando ese sistema marca como sospechoso un programa que en
  realidad es legítimo.
- **Firma de código (Authenticode en Windows, notarización en macOS)**: sellar el
  ejecutable con un certificado criptográfico que prueba quién lo creó y que no
  fue alterado. Es lo que más reduce las alertas.
- **Heurística**: cuando no hay firma ni reputación, el antivirus *estima* si un
  archivo "se parece" a malware analizando su estructura, no demostrando que lo
  sea. De ahí los falsos positivos.
- **Reputación**: confianza acumulada por volumen de descargas sin incidentes
  (VS Code, Git…). Un proyecto nuevo no la tiene.
- **Mark-of-the-Web (MOTW)**: una marca invisible que Windows/macOS añaden a todo
  archivo bajado de internet. Es lo que activa la revisión de SmartScreen/
  Gatekeeper. Un archivo *generado localmente* (como el que crea `pip`) no la
  lleva.
- **Bootloader de PyInstaller**: el pequeño programa que PyInstaller pone al
  frente del ejecutable para arrancar la app. Su estructura es genérica y algunos
  antivirus la asocian con malware ("culpable por asociación").
- **Patrón "dropper"**: comportamiento típico de malware que "suelta" un archivo
  oculto y lo ejecuta. El modo `--onefile` de PyInstaller se le parece (por eso
  este proyecto usa `--onedir`, que no lo hace).
- **UPX**: un compresor de ejecutables. El malware lo usa mucho para esconderse,
  así que su presencia sube la sospecha del antivirus.
- **Metadata PE**: los campos de identidad (empresa, producto, versión) que un
  `.exe` de Windows puede llevar embebidos. Su ausencia hace el ejecutable
  "anónimo" y más sospechoso.
- **Modelo ML del antivirus**: el clasificador de aprendizaje automático que
  Defender usa para puntuar archivos; se apoya en las señales anteriores (firma,
  metadata, empaquetador…).
- **WDSI**: el portal de Microsoft (*Windows Defender Security Intelligence*,
  `microsoft.com/wdsi`) donde se reportan los falsos positivos para que los
  reclasifiquen.
- **Canal pip / PyPI**: instalar con `pip`/`uv`/`pipx`. Descarga el *paquete* y
  genera el ejecutable **en la máquina del usuario**, por lo que no lleva MOTW y
  no dispara las alertas.
- **CI**: *integración continua*, la automatización que corre en servidores al
  publicar (aquí, **CircleCI**; por decisión del propietario el proyecto **no** usa
  GitHub Actions, para mantener un solo sistema de CI de forma consistente).
- **Spike / PoC**: una prueba de concepto pequeña y acotada para validar que algo
  incierto funciona **antes** de invertir en automatizarlo.
- **Backbone de CI**: la pieza de automatización compartida sobre la que se apoyan
  varias fases (aquí, el job `publish-metadata` dentro del workflow `build-all` de
  CircleCI, que corre tras `publish-release`).
- **Draft (borrador) de Release**: un GitHub Release aún no público; sus assets no
  son descargables hasta que alguien pulsa «Publish». Este ciclo **elimina** ese
  paso: `publish-release` publica directo (ver H-2).
- **Context (de CircleCI)**: un contenedor de variables de entorno secretas,
  aislado por job (solo lo ven los jobs que lo declaran). Es el mecanismo con el
  que este proyecto inyecta credenciales de publicación (`github-release`,
  `pypi-publish`), y el que reemplaza a los «secrets de GitHub Actions» del diseño
  anterior.
- **Asunto transversal**: un tema que **atraviesa todas las fases** en vez de ser
  una fase más (antes lo llamé, mal, "concern transversal").
- **Línea de trabajo**: un conjunto de tareas que avanza en paralelo a las fases
  (antes lo llamé, mal, "sub-track").

## Restricción rectora (aclaración del propietario)

La restricción de "cero dependencia de terceros" tiene un alcance **preciso**,
aclarado por el propietario y que gobierna todo este documento:

> **Aplica solo a la PUBLICACIÓN.** Publicar una versión nueva NO debe requerir
> la aprobación/revisión de un tercero ni un pull request a un proyecto externo
> (descarta `winget-pkgs` oficial, `homebrew-cask` oficial, Flathub, Snap Store).
>
> **NO aplica a la instalación.** La fricción del **usuario final** —ejecutar
> comandos, `chmod +x`, importar un certificado, `winget source add`, `brew tap`—
> es esperable y aceptable.

Herramientas de CI sobre el propio repo (CircleCI —y, en principio, cualquier CI
del propio repo—) y repos propios (un tap de Homebrew, un repo de fuente winget)
están 100% bajo control del propietario y **no** cuentan como terceros: un
`git push` directo a un repo propio no es un PR a un proyecto externo. (Que GitHub
Actions *también* cumpliría la restricción rectora es cierto en el plano de la
autonomía; aun así el propietario decide **no** usarlo, por consistencia de operar
un solo sistema de CI — ver la decisión «Arquitectura de CI».)

Esta aclaración **habilita el mecanismo winget** bajo la restricción rectora, que
una iteración previa de este documento había descartado por leer erróneamente "el
usuario importa un certificado" como una violación de la restricción (ver H-1). El
propietario, sin embargo, **difiere su implementación** a un roadmap futuro
condicionado a firma Authenticode real vía SignPath Foundation y a ROI positivo;
winget queda **fuera del alcance activo** de este ciclo (ver la sección «Roadmap
futuro (diferido): winget + SignPath Foundation»).

## Resumen ejecutivo

Los **dos mecanismos activos** (Linux, macOS) son viables bajo la restricción
rectora, sin cambios de build en los artefactos actuales (o con cambios mínimos
identificados). El tercer mecanismo (Windows/winget) queda **diferido** a un
roadmap futuro (ver sección «Roadmap futuro (diferido): winget + SignPath
Foundation»). Se ordenan por esfuerzo/riesgo creciente dentro del alcance activo:

1. **Linux (script)** — el más simple: no requiere CI nuevo, ni repo externo, ni
   certificado. El script resuelve versión/URL/checksum en tiempo de ejecución
   vía la GitHub Releases API. Ver H-4.
2. **macOS (Cask)** — esfuerzo medio: requiere un repo tap propio y un job que
   actualice el Cask (`version`/`sha256`/`url`) en cada release. Introduce el
   backbone de CI compartido (job `publish-metadata` en CircleCI). Ver H-3, H-2.

El canal **Windows (winget)** se difiere en este ciclo: sin firma Authenticode real
no aporta reputación frente a SmartScreen (H-7) y solo añade superficie de fallos y
mantenimiento sin retorno actual o próximo; su entrada futura está condicionada a
una firma real vía SignPath Foundation (Línea B, `docs/GOAL.md:216-241`) y a un
ROI positivo. El conocimiento técnico ya acumulado (H-1, H-6) se preserva como
insumo de esa fase futura, sin eliminarlo.

El obstáculo estructural —publicar la metadata del Cask que apunte a los assets del
release— se resuelve **eliminando el paso de draft**: `publish-release` publica el
GitHub Release directo (sin `--draft`), con lo que sus assets son públicos en
cuanto el job termina. Un job siguiente en el **mismo pipeline de CircleCI**,
`publish-metadata`, con `requires: [publish-release]`, publica la **metadata del
Cask** leyendo sus insumos del propio release ya público (`CIRCLE_TAG` +
`SHA256SUMS.txt`), sin API de terceros ni un segundo sistema de CI. (La extensión
de `publish-metadata` a winget es una evolución futura, no operativa hoy.) El
proyecto se mantiene **100% en CircleCI** por decisión del propietario. El costo
del cambio es la pérdida del *gate* humano que daba el draft (el tag pasa a ser el
punto de no retorno, igual que ya ocurre con `publish-pypi`); recuperarlo de forma
opcional sin reintroducir el draft es una decisión de diseño (job `type: approval`
de CircleCI). Ver H-2.

**Dimensión antivirus / falsos positivos (requisito nuevo del propietario)**: la
auditoría concluye que los mecanismos auto-hospedados **no** son una estrategia
contra las alertas de antivirus, salvo el Cask de Homebrew (que limpia la
cuarentena y mitiga Gatekeeper en macOS). El canal Windows (winget) queda diferido
(ver sección «Roadmap futuro (diferido)»); en cualquier caso, winget **añadiría**
la marca Mark-of-the-Web (MOTW) al instalador y SmartScreen seguiría disparándose
sin firma real (H-7). Las únicas vías que evitan las alertas de raíz son
estructurales (el canal pip, que genera el ejecutable en la máquina del usuario,
sin MOTW) o de firma de código (estrategia B de `docs/GOAL.md`). Por eso la
estrategia antivirus se modela como un **asunto transversal** (atraviesa todas las
fases) acoplado a la estrategia B y a una **línea de trabajo** barata de
endurecimiento del build, **no** como una fase de los mecanismos auto-hospedados.
Ver H-7 y la sección «Auditoría de completitud del roadmap».

## Hallazgos

### Críticos

**H-1 — La fuente winget autofirmada ES viable y autónoma bajo la restricción rectora (ver subsección «Hallazgos diferidos (winget)»).**
- **Estado**: H-1 sigue siendo válido como *insumo técnico* de la fase winget
  futura —corrige el descarte previo de winget: la firma autofirmada es aceptable
  bajo la restricción rectora—. El propietario **difiere** su implementación a un
  roadmap futuro (firma real vía SignPath Foundation + ROI positivo), por lo que
  H-1 **no** está en el alcance activo de este ciclo. Su contenido íntegro se
  conserva en la subsección «Hallazgos diferidos (winget)».

**H-2 — La metadata de Cask/winget se publica desde un job `publish-metadata` en el mismo pipeline de CircleCI, tras eliminar el paso de draft de `publish-release`.**
- **Problema original**: `publish-release` (`.circleci/config.yml:729-807`) creaba
  el GitHub Release en borrador (`--draft`, línea 804) y terminaba ahí; los assets
  no eran públicos hasta que el propietario pulsaba "Publish release"
  (`docs/RELEASING.md` §3), un evento que CircleCI no observa de forma nativa. Un
  Cask o un índice winget generados en CI apuntarían a URLs de assets aún privadas.
- **Decisión del propietario (reabre la arquitectura de CI previa)**: (1) el
  proyecto se mantiene **100% en CircleCI**, sin introducir GitHub Actions, para
  no operar dos sistemas de CI; (2) `publish-release` **publica el Release directo**,
  eliminando el paso de draft.
- **Por qué el cambio disuelve el problema**: al quitar `--draft`, los assets del
  Release son públicos en cuanto el job `publish-release` termina, dentro del mismo
  pipeline. Ya no hay «evento de publicación manual» que un sistema externo deba
  observar; basta un job siguiente en el **mismo workflow** con
  `requires: [publish-release]`. Toda la maquinaria de GitHub Actions
  (`on: release: types: [published]`) que el diseño anterior necesitaba para
  puentear el draft **sobra**: existía solo para esperar ese clic manual.
- **Semántica verificada de la publicación directa**:
  - `gh release create` **sin `--draft`** publica el Release de inmediato; con
    `make_latest` en `true` por defecto (`cli.github.com/manual/gh_release_create`),
    el Release queda marcado como *latest* al instante.
  - `GET /repos/{owner}/{repo}/releases/latest` devuelve «el Release no-draft,
    no-prerelease más reciente» y **excluye drafts por diseño**
    (`docs.github.com/rest/releases/releases`). Es decir: publicar directo hace que
    `releases/latest` apunte a la versión nueva sin ventana de desfase, lo que
    **mejora** la Fase 1 (Linux), que resuelve la versión por ese endpoint (H-4);
    ya no existe la ventana en que `latest` devolvía la versión anterior mientras
    el draft esperaba el clic.
- **Diseño del job `publish-metadata` (mismo pipeline)**:
  - Corre en `requires: [publish-release]` dentro de `build-all`, con los mismos
    filtros de tag `only: /^v.*/` que el resto de la cadena.
  - **Insumos sin API de terceros**: la versión viene de `CIRCLE_TAG` (variable de
    entorno del tag, siempre disponible, nunca expira); el `sha256` del `.dmg` se
    lee de `SHA256SUMS.txt`, ya generado por `publish-release`
    (`.circleci/config.yml:762-769`). Como el Release ya es público, `SHA256SUMS.txt`
    es recuperable de forma durable con `gh release download "$CIRCLE_TAG" -p SHA256SUMS.txt`,
    **sin depender del workspace** (importa para la idempotencia; ver más abajo y G-3).
  - **Secretos como contexts de CircleCI** (no «secrets de GitHub Actions»): un
    context `homebrew-tap` con `HOMEBREW_TAP_PAT` (PAT fine-grained, `Contents:RW`
    solo en el repo tap) para el push del Cask. Cada context lo ve solo el job que
    lo declara, igual que `github-release`/`pypi-publish` hoy. (El futuro
    `winget-sign` con el PFX sería un context análogo, pero queda **fuera del
    alcance activo**; ver la sección «Roadmap futuro (diferido): winget + SignPath
    Foundation».)
  - **Push cross-repo a repos propios**: el `HOMEBREW_TAP_PAT` permite `git commit` +
    `git push` directo a `main` del tap. **Push directo a un repo propio ≠ PR a
    proyecto externo**: no hay revisión ni merge de terceros; la restricción rectora
    queda intacta.
- **Costo del cambio (pérdida del ojo humano)**: el draft daba una revisión humana
  antes de exponer los assets. Al publicar directo, **el tag se convierte en el punto
  de no retorno**, exactamente como ya ocurre con `publish-pypi` (subida irreversible
  en el mismo tag). Es un costo aceptado y coherente con el canal existente. Si el
  propietario quisiera recuperar un gate humano **sin reintroducir el draft**, la vía
  nativa de CircleCI es un job `type: approval` (un «hold» manual) intercalado antes
  de `publish-release`; es compatible con los filtros de tag
  (`support.circleci.com/hc/en-us/articles/36487404271003`). Queda como decisión de
  diseño abierta (el propietario decidió «sin revisión manual» sin conocer aún esta
  alternativa intra-CircleCI).
- **Idempotencia y reintento (reformula G-3)**: si `publish-metadata` falla
  **después** de que el Release ya es público, queda un estado parcial. El rerun de
  CircleCI tiene un límite práctico: el workspace se retiene **15 días** por defecto,
  mientras que «Rerun from failed» se permite hasta 90 días
  (`circleci.com/docs/guides/orchestrate/workspaces/`). Un rerun tardío (>15 días)
  fallaría en `attach_workspace`. **Implicación de diseño**: `publish-metadata` **no
  debe depender del workspace** para sus insumos —debe reconstruirlos del Release
  público (`gh release download` + `CIRCLE_TAG`)— y debe ser **idempotente**
  (regenerar y re-empujar produce el mismo resultado), al estilo del
  `--skip-existing` de `publish-pypi`. Así el reintento es robusto aunque el
  workspace haya expirado.
- **Descartado**: el workflow de GitHub Actions (`release: published`) del diseño
  anterior queda descartado por completo — introducía un segundo sistema de CI que
  el propietario veta, y su única función (esperar el clic de publicación del draft)
  desaparece al eliminar el draft.

**H-7 — Los mecanismos auto-hospedados NO son una estrategia contra las alertas de antivirus (salvo Homebrew en macOS); la mitigación real atraviesa todas las fases y se acopla a la firma de código (estrategia B).**
- **Marco: los 3 mecanismos de confianza** con los que un SO decide si confía en
  un ejecutable: (1) **firma de código**, (2) **reputación** acumulada, y (3)
  **heurística** (la estimación de "esto se parece a malware" cuando no hay ni
  firma ni reputación). Un proyecto pequeño y sin firma cae en la heurística, que
  analiza la estructura interna del `.exe`, sus imports, si está comprimido y su
  "entropía" (cuán aleatorio parece el contenido, señal típica de datos ocultos).
  Referencia aportada por el propietario:
  `docs/external-references/ejemplo-de-distribución-multiplataforma.md`, caso
  Engram.
- **Por qué los ejecutables de PyInstaller disparan la heurística**: el patrón
  "desempaquetar-y-ejecutar" y el *bootloader* (el arrancador genérico que
  PyInstaller antepone) son "culpables por asociación", porque hay malware que usa
  el mismo empaquetador; la compresión UPX lo agrava; y un ejecutable sin metadata
  PE (los campos de identidad: empresa/producto/versión) ni firma no le da al
  clasificador automático de Defender ninguna señal de confianza que compense la
  sospecha. Fuentes: PyInstaller issues #6754 y #8164, guía de PythonGUIs.
- **Realidad por sistema operativo** (verificada):
  - **Linux**: no tiene un equivalente a Gatekeeper/SmartScreen que inspeccione al
    arrancar. La única superficie del `curl|sh` es ejecutar un script bajado de
    internet, mitigada porque el propio script verifica el checksum contra
    `SHA256SUMS.txt` antes de ejecutar nada. No hay problema de antivirus.
  - **macOS**: el Cask de Homebrew **borra el atributo de cuarentena**
    (`com.apple.quarantine`) al instalar, con lo que **mitiga Gatekeeper de forma
    estructural** (es el único mecanismo auto-hospedado que aporta algo frente al
    antivirus). Bajar el `.dmg` a mano, en cambio, sigue exigiendo notarización
    (estrategia B).
  - **Windows**: el canal Windows (winget) queda **diferido** a un roadmap futuro
    (ver sección «Roadmap futuro (diferido)»), pero su análisis técnico ya está
    hecho: winget **añadiría la marca Mark-of-the-Web** (el flujo `Zone.Identifier`)
    y lanzaría el instalador por una ruta que pasa por el shell, así que
    **SmartScreen se dispararía igual** sobre el instalador Inno sin firma real.
    Verificado en `microsoft/winget-cli` #6232 y en el caso `vim-win32-installer`
    #319 (los instaladores firmados pasan; los que no están firmados, no). **winget
    NO resolvería el antivirus**; solo aportaría descubrimiento e instalación.
- **Las únicas vías que evitan las alertas de raíz**:
  1. **Estructural — canal pip** (ya implementado): `pip`/`uv`/`pipx` generan el
     ejecutable **en la máquina del usuario**, así que no lleva MOTW ni cuarentena
     (`docs/DISTRIBUTION.md:82-95`). Es el mismo principio que el `go install` de
     Engram. Evita el problema en Windows **y** macOS, hoy.
  2. **Firma de código — estrategia B** (`docs/GOAL.md:216-241`): Authenticode vía
     SignPath en Windows + notarización Apple en macOS. Es la mitigación de fondo
     para el canal nativo (el que se descarga a mano).
- **Línea de trabajo de endurecimiento del build (barata, independiente de la
  firma)**: el build ya hace dos cosas correctas —usa `--onedir` (no `--onefile`,
  con lo que evita el patrón "dropper") y `--exclude-module` para recortar
  dependencias sobrantes (`build_utils.py:220`, `:256-260`)—. **Faltan**, a bajo
  costo: (a) pasar `--noupx` de forma explícita (hoy no se hace: si el servidor de
  CI tuviera UPX instalado, PyInstaller comprimiría el ejecutable y subiría la
  sospecha); (b) embeber la metadata PE (`--version-file` con empresa/producto/
  versión) para darle señales de confianza al clasificador; (c) reportar los
  falsos positivos al portal WDSI de Microsoft (`microsoft.com/wdsi`) cuando
  ocurran. Ninguna depende de aprobación de terceros.
- **Conclusión**: la estrategia antivirus **atraviesa todas las fases**, no es una
  fase de los mecanismos auto-hospedados. Se divide en (a) la línea de trabajo de
  endurecimiento del build (barata, sin dependencia de terceros) y (b) la
  estrategia B (firma), ya comprometida en `docs/GOAL.md`. Presentar el script o el
  Cask como "solución al antivirus" sería un error de categoría: el Cask solo
  mitiga Gatekeeper en macOS (H-3); Windows nativo solo lo logra vía firma real
  (Línea B). El canal winget, de implementarse en el futuro, tampoco resolvería el
  antivirus sin firma real (H-7).

### Advertencias

**H-3 — El `.dmg` actual no es un Cask "de copiar y listo": expone el binario CLI solo vía script `.command` con `sudo`, redundante frente a Homebrew.**
- Evidencia: `scripts/build_macos.py` líneas 180-238 (staging del volumen:
  `tts-sidecar-arm64.app` + `Instalar (PATH + modelo).command` +
  `Desinstalar (quitar del PATH).command`), líneas 240-311
  (`_path_install_script`/`_path_uninstall_script`: symlink `sudo` en
  `/usr/local/bin`). El binario real vive en `Contents/MacOS/tts-sidecar`.
- Determinación (`docs.brew.sh/Cask-Cookbook`): la stanza `binary` puede apuntar
  directamente a `#{appdir}/tts-sidecar-arm64.app/Contents/MacOS/tts-sidecar` y
  enlazarla en el prefix de Homebrew (`/opt/homebrew/bin` en Apple Silicon), que
  ya está en el PATH del usuario, **sin sudo**. Homebrew además limpia
  `com.apple.quarantine` automáticamente al instalar — mitigación real de
  Gatekeeper, a diferencia de la descarga manual del `.dmg`.
- El `.dmg` es consumible tal cual (no bloquea el Cask), pero los dos `.command`
  quedan redundantes/confusos en la vía Homebrew: la oferta de `tts-sidecar setup`
  debe expresarse como `caveats` (o `postflight` no interactivo) del Cask, no vía
  el `read -p` del `.command`, que Homebrew no puede invocar de forma no
  interactiva. No hay rama `darwin` equivalente a `_integrate_linux_path()` en el
  CLI: toda la integración de PATH de macOS vive fuera del CLI, en el `.command`.

**H-4 — El script Linux es viable hoy sin cambios de build ni CI, apoyándose en un comportamiento hoy no documentado de `_integrate_linux_path()`.**
- Evidencia: `src/tts_sidecar/cli.py:597-626` — `_integrate_linux_path()` activa
  el symlink de PATH verificando únicamente `sys.platform == "linux"` y la
  presencia de la env var `APPIMAGE`, sin validar que el proceso corra realmente
  desde un runtime AppImage montado. Un script que exporte `APPIMAGE=<ruta>` antes
  de invocar `setup` obtiene la misma integración de PATH. Conviene **documentar
  este contrato** (o endurecerlo intencionalmente) para que el script pueda
  depender de él con garantía.
- `cmd_setup()` no tiene prompts bloqueantes (el único `input()` de `cli.py`
  vive en `cmd_cleanup`, línea 875, y está gateado por `--yes`/`--dry-run`) y ya
  soporta `--json`/`--force-update`/`--remove-path`: apto para invocación no
  interactiva sin cambios.
- `GET /repos/{owner}/{repo}/releases/latest` (GitHub REST API) no requiere
  autenticación en repos públicos y **excluye drafts por diseño** — resuelve
  versión/URL/asset en tiempo de ejecución del usuario, sin necesidad de metadata
  generada en CI. Por eso el script Linux **no requiere ningún job de CI nuevo**.
- Fricciones residuales del script (no bloqueantes): glibc ≥ 2.35 (detectable, no
  evitable), ausencia de alias `latest.AppImage` (parsear el nombre versionado del
  asset), y el aviso de PATH-no-persistente que ya emite el CLI (línea 623-626)
  pero que el script no debe propagar a `.bashrc`/`.zshrc` sin consentimiento.

### Sugerencias

**H-5 — Superficie documental y de tests a extender (una vez fijado el alcance).**
- `docs/DISTRIBUTION.md`: los dos mecanismos activos (Linux, macOS) se documentan
  como **refinamientos del canal nativo** (mismo artefacto ya publicado), sin nueva
  fila en la matriz
  de dos-canales (líneas 10-23); el detalle iría en "Instalación por canal"
  §"Canal nativo" (líneas 28-34) y un registro de decisión análogo al de A-vs-B
  (líneas 97-125).
- `docs/RELEASING.md`: reescribir §3 «Manual: revisar y publicar el draft» (líneas
  101-116) para reflejar la **publicación directa** (el tag es el punto de no
  retorno, como `publish-pypi`; iterar ante error implica **borrar un Release
  público**, no descartar un draft); agregar los prerequisitos operativos
  una-sola-vez del alcance activo (context `homebrew-tap`, repo tap) junto a los
  contexts existentes (líneas 42-48) y un paso que describa la publicación
  automática de metadata del Cask por `publish-metadata` tras `publish-release`.
  (Los prerequisitos de winget —context `winget-sign`, certificado, hosting— quedan
  para la fase futura diferida.)
- `docs/GOAL.md` §"Roadmap (compromisos a futuro)" (líneas 216-241): registrar
  los mecanismos comprometidos como entrada(s) de roadmap, análogas a la entrada
  de firma/notarización.
- `docs/BUILD.md` §"Matriz de integración con el SO" (líneas 183-199): fila nueva
  "Descubrimiento/instalación auto-hospedada" por SO.
- `SECURITY.md` §"Artefactos sin firmar" (líneas 65-87): nota sobre la superficie
  del script `curl|sh` (ejecución de script remoto) y su mitigación (verificación
  de `SHA256SUMS.txt` dentro del propio script); nota sobre el certificado
  autofirmado de la fuente winget (qué garantiza y qué no).
- Tests (`tests/test_build_windows.py:1-65` como patrón: `monkeypatch` sobre
  `subprocess.run`/utilidades, sin disco ni red): un generador de Cask y un
  generador de manifiestos/índice winget son testeables con el mismo patrón; el
  script Linux se testea con un runner de shell (`bats`) o tests de integración
  que mockeen `curl`/`uname`.

**H-6 — El riesgo real de winget es la madurez del tooling de generación del índice, no la firma (ver subsección «Hallazgos diferidos (winget)»).**
- **Estado**: válido como *insumo técnico* de la fase winget futura —el riesgo real
  está en el tooling `WinGetSourceCreator`, no en la firma—. Diferido junto con H-1;
  su contenido íntegro se conserva en la subsección «Hallazgos diferidos (winget)».

### Hallazgos diferidos (winget)

Los dos hallazgos siguientes **no** están en el alcance activo de este ciclo: el
propietario difiere la implementación del canal Windows (winget) a un roadmap
futuro condicionado a firma Authenticode real vía SignPath Foundation (Línea B,
`docs/GOAL.md:216-241`) y a ROI positivo. Se conservan íntegros como **insumo
técnico** de esa fase futura, sin eliminar el conocimiento acumulado.

**H-1 — La fuente winget autofirmada ES viable y autónoma bajo la restricción rectora (corrige el descarte previo).**
- **Corrección**: una versión anterior de este documento clasificó winget como
  "descartado" porque la firma del `index.msix` con certificado autofirmado
  obliga al usuario a importar el `.cer`. Bajo la restricción rectora aclarada,
  esa fricción del usuario final **es aceptable** y no descalifica el mecanismo.
- **Evidencia de autonomía de publicación**: `learn.microsoft.com/windows/msix/package/signing-package-overview`
  y `.../create-certificate-package-signing` — el certificado autofirmado es una
  opción de firma legítima, generable con `New-SelfSignedCertificate` (PowerShell
  PKI, sin red ni aprobación externa), exportable a PFX y usable con `signtool.exe`
  en CI. Generar el certificado, firmar el `index.msix` y publicarlo en hosting
  estático propio es un proceso 100% bajo control del propietario, sin aprobación
  de Microsoft ni PR a repo externo alguno.
- **Flujo del usuario final (aceptable, una sola vez)**, con comandos exactos:
  1. Importar el certificado público a `LocalMachine\TrustedPeople` (Microsoft
     advierte explícitamente **no** usar `Trusted Root` salvo CA real), elevado:
     `Import-Certificate -FilePath tts-sidecar-source.cer -CertStoreLocation Cert:\LocalMachine\TrustedPeople`.
  2. `winget source add --name tts-sidecar --arg https://<hosting-propio> --type Microsoft.PreIndexed.Package --accept-source-agreements` (requiere admin).
  3. `winget install tts-sidecar --source tts-sidecar`.
- **Dependencias residuales, clasificadas honestamente** (ninguna es gate de
  terceros para publicar):
  - Certificado autofirmado: expira a 1 año por defecto; renovarlo es
    mantenimiento propio, no aprobación externa. **No es gate.**
  - Timestamp server RFC 3161 (`signtool /tr <url> /td sha256`): servicio de red
    gratuito (Sectigo/DigiCert/etc.), sin cuenta ni contrato — equivalente a un
    NTP server; mantiene válidos los paquetes ya firmados tras expirar el cert.
    **No es gate.**
  - Hosting estático (GitHub Pages/Releases): TOS genérico de uso, no aprobación
    por release. **No es gate.**
- **Riesgo real desplazado a H-6** (tooling de generación del índice).

**H-6 — El riesgo real de winget es la madurez del tooling de generación del índice, no la firma.**
- `src/WinGetSourceCreator` en `github.com/microsoft/winget-cli` es el componente
  que el propio equipo de winget usa para construir fuentes
  `Microsoft.PreIndexed.Package` firmadas, pero **no se publica como paquete
  reutilizable** (no existe `Microsoft.WinGet.Source` en NuGet.org): es código
  C#/.NET dentro del repo, consumible por referencia/copia. El `index.db` (SQLite)
  se construye vía `WinGetUtil` (librería nativa C++ del mismo repo). No hay una
  CLI pública turnkey "genera-tu-index.msix".
- Alternativa comunitaria: `winget.pro` (repositorio privado de winget, open
  source, autohospedable) reduce el esfuerzo de integración frente a reimplementar
  `WinGetSourceCreator`.
- **Implicación para el roadmap**: la fase Windows debe empezar por un
  **spike/PoC** que genere y firme un `index.msix` mínimo y valide el flujo
  `winget source add` + `winget install` en una VM limpia, **antes** de
  comprometer la automatización en CI. Es el punto de mayor incertidumbre técnica
  de todo el ciclo.

## Decisiones cerradas

Todas las decisiones de diseño de este ciclo están resueltas; el roadmap de abajo
es su materialización.

- **Restricción rectora**: la autonomía aplica solo a *publicar* (sin
  aprobación/PR de terceros por versión); la fricción del usuario final es
  aceptable. Habilita winget vía fuente autofirmada `Microsoft.PreIndexed.Package`
  (H-1), pero el propietario **difiere** su implementación a un roadmap futuro
  (ver la decisión «Diferir winget» más abajo).
- **Arquitectura de CI (decisión del propietario que reabre H-2)**: el proyecto se
  mantiene **100% en CircleCI**; **no** se introduce GitHub Actions. Además,
  `publish-release` **publica el Release directo, sin el paso de draft (implementado
  el 2026-07-08)**. La metadata
  de **Cask** la publica un job `publish-metadata` en el mismo pipeline, con
  `requires: [publish-release]`, insumos leídos del Release público
  (`CIRCLE_TAG` + `SHA256SUMS.txt`) y secretos vía contexts de CircleCI. Costo
  aceptado: se pierde el gate humano del draft (el tag es el punto de no retorno,
  como en `publish-pypi`). Ver H-2.
- **Alcance**: los **dos mecanismos activos** (Linux, macOS) en el roadmap de
  este ciclo, cada fase un entregable liberable por separado. El mecanismo Windows
  (winget) queda **diferido** a un roadmap futuro (ver decisión «Diferir winget»).
- **Estrategia antivirus**: **asunto transversal** acoplado a la firma de código,
  no una fase (H-7). La **Línea A** (endurecimiento del build) entra en el alcance
  de este ciclo; la Línea B (firma/notarización) permanece en `docs/GOAL.md`.
- **Fase 0**: los prerequisitos de una sola vez (repo tap, context de CircleCI
  `homebrew-tap`) se formalizan como hito previo a la **Fase 2** (la Fase 1 no lo
  necesita). El repo de fuente winget, sus GitHub Pages y el context `winget-sign`
  quedan fuera del alcance activo (ver decisión «Diferir winget»).
- **Contrato de `_integrate_linux_path()`**: se **endurece** con una vía soportada
  explícita para exportar `APPIMAGE`, cubierta por un test, antes de la Fase 1 (no
  solo documentación).
- **Nombres y hosting (alcance activo)**: repo tap `homebrew-tts-sidecar`; context
  de CircleCI `homebrew-tap` con `HOMEBREW_TAP_PAT`. El context `winget-sign`, su
  PFX y las GitHub Pages de la fuente winget quedan **fuera del alcance activo**
  (se activarían solo al retomar winget en el futuro; ver decisión «Diferir
  winget»).
- **Diferir winget (decisión de diseño del propietario)**: el canal Windows
  (fuente `Microsoft.PreIndexed.Package`) **no** se implementa en este ciclo.
  **Justificación**: sin firma Authenticode *real* (Línea B, `docs/GOAL.md:216-241`)
  winget no aporta reputación frente a SmartScreen —de hecho añadiría la marca
  Mark-of-the-Web y SmartScreen seguiría disparándose sobre el instalador sin
  firmar (H-7)—, y solo añadiría superficie de fallos y mantenimiento (madurez de
  `WinGetSourceCreator`, H-6) sin retorno actual ni próximo (ROI negativo hasta
  tener firma real). **Condición de reapertura**: aprobación del proyecto por el
  programa SignPath OSS + certificado, y ROI positivo. Hasta entonces, el
  conocimiento técnico se preserva en la subsección «Hallazgos diferidos (winget)».

### Decisiones del propietario resueltas en esta revisión (2026-07-08)

Emergentes del audit adversarial de la propuesta de cambio de CI; cerradas antes de
construir el plan:

- **Gate humano de publicación**: **NO** se añade gate. `publish-release` publica
  directo (sin draft) y el **tag es el punto de no retorno**, coherente con
  `publish-pypi`. Se evaluó y **descartó** el job `type: approval` de CircleCI (que
  habría recuperado la revisión humana sin draft ni GitHub Actions): reintroduce la
  fricción manual que el propietario quiere eliminar y rompe la simetría con
  `publish-pypi`. Iterar ante un tag erróneo implica borrar el Release público y
  re-taggear (documentar en `RELEASING.md`).
- **Idempotencia de `publish-metadata`** (cierra **G-3**): el job **reconstruye sus
  insumos del Release ya público** (`gh release download SHA256SUMS.txt` +
  `CIRCLE_TAG`), **no del workspace**, y su regeneración es **idempotente**
  (regenerar y re-empujar da el mismo resultado). Así el reintento es robusto en
  cualquier momento, inmune a la expiración de 15 días del workspace, en el mismo
  espíritu que el `--skip-existing` de `publish-pypi`.

---

## Estado de implementación (al 2026-07-08)

Este documento es un **insumo de planificación** (`create-plan`), no código. Su
grado de materialización en el repo es:

- **Implementado**: la eliminación del paso de draft de `publish-release` (H-2,
  decisión «Arquitectura de CI»). `.circleci/config.yml` ya no lleva `--draft` y
  `docs/RELEASING.md`, `docs/BUILD.md` y `docs/DISTRIBUTION.md` describen la
  publicación directa. Es el único entregable materializado del ciclo y el
  prerrequisito de CI que habilita la Fase 2 del roadmap.
- **Pendiente (resto del roadmap activo)**: Fase 0 (prerequisitos de Homebrew),
  Fase 1 (Linux), Fase 2 (macOS) y Línea A (endurecimiento del build). Ninguno
  existe aún en el repo (no hay `install.sh`, job `publish-metadata`, repos
  propios, ni `--noupx`/`--version-file`), y debe planificarse con `create-plan` y
  ejecutarse fase por fase. El canal Windows (winget) queda **diferido** fuera de
  este ciclo (ver «Roadmap futuro (diferido)»).

# Roadmap: instalación auto-hospedada por SO

Principio rector: **cada versión se publica de forma 100% autónoma** (sin
aprobación ni PR a terceros), reutilizando los artefactos que el canal nativo ya
produce, y entregando una experiencia de instalación equivalente por SO
(descubrir → instalar → comando en el PATH → provisión guiada → desinstalar).

El alcance activo de este ciclo es **Fase 1 (Linux) + Fase 2 (macOS) + Línea A**,
con la **Fase 0** reducida a los prerequisitos de Homebrew. La Fase 2 introduce el
backbone de CI (job `publish-metadata` en CircleCI, tras `publish-release` sin
draft). El canal **Windows (winget)** queda **diferido** a un roadmap futuro
(acoplado a la Línea B de `docs/GOAL.md:216-241`); ver la subsección «Roadmap
futuro (diferido): winget + SignPath Foundation».

## Infraestructura compartida (backbone de CI)

Un único job nuevo, `publish-metadata`, dentro del workflow `build-all` de CircleCI,
con `requires: [publish-release]` y los mismos filtros de tag `only: /^v.*/`. Corre
**después** de que `publish-release` publica el Release directo (sin draft), de modo
que sus assets ya son públicos, y publica la **metadata del Cask** de la Fase 2. El
único cambio en `publish-release` —**quitar `--draft`**— **ya está implementado**
(`.circleci/config.yml`: `gh release create` sin `--draft`, sincronizado en
`docs/RELEASING.md`/`BUILD.md`/`DISTRIBUTION.md`); no se introdujo GitHub Actions.
(La extensión de `publish-metadata` a winget queda para el roadmap futuro; ver la
subsección «Roadmap futuro (diferido)»). Todos los recursos propios de la tabla se
crean en la **Fase 0**; la columna "Consume" indica qué fase los usa.

| Recurso propio | Propósito | Consume |
|---|---|---|
| Job `publish-metadata` en `.circleci/config.yml` (`requires: [publish-release]`) | Tras el Release público, publica la metadata del Cask | 2 |
| Repo `homebrew-tts-sidecar` (público) | Tap de Homebrew (`Casks/tts-sidecar.rb`) | 2 |
| Context de CircleCI `homebrew-tap` con `HOMEBREW_TAP_PAT` (fine-grained, `Contents:RW` solo en el tap) | Push del Cask actualizado al tap | 2 |

## Fase 0 — Prerequisitos de Homebrew (una sola vez)

Hito de arranque, con acciones manuales del propietario, que **gatea la Fase 2**
(la Fase 1 no lo necesita). No se repite por release. El canal Windows (winget)
queda diferido y **no** aporta prerequisitos activos en este ciclo (ver la
subsección «Roadmap futuro (diferido)»).

- **Entregables**:
  - Repo tap `homebrew-tts-sidecar` (público) creado.
  - Context de CircleCI `homebrew-tap` configurado con `HOMEBREW_TAP_PAT`
    (fine-grained, `Contents:RW` solo en el tap).
- **Nota sobre el primer publish**: el **primer** push del Cask (Fase 2) es manual
  y se hace como paso de bootstrap **al inicio de la fase** (requiere que el
  `.dmg` ya exista); a partir de ahí `publish-metadata` lo actualiza solo.
- **Criterio de cierre**: el repo tap y el context existen; el push inicial del
  Cask al tap es viable con el `HOMEBREW_TAP_PAT`.

## Fase 1 — Linux (`curl \| sh`)

**Menor esfuerzo. Sin CI nuevo, sin repo externo, sin certificado.**

- **Entregable**: `install.sh` en la raíz del repo, servido desde
  `raw.githubusercontent.com/<owner>/TTS-Sidecar/main/install.sh` (hosting propio,
  sin terceros). Uso: `curl -fsSL <url> | sh`.
- **Flujo del script** (H-4): resolver `releases/latest` (excluye drafts) →
  `uname -m` → seleccionar el asset `.AppImage` de la arquitectura → descargar
  AppImage + `SHA256SUMS.txt` → verificar checksum → `chmod +x` → instalar en
  `~/.local/opt/tts-sidecar/` → `export APPIMAGE=<ruta>` + `"$APPIMAGE" setup`
  (dispara la integración de PATH y la descarga del modelo).
- **Cambios de código**: **endurecer el contrato de `_integrate_linux_path()`**
  con una vía soportada explícita para que el `export APPIMAGE` externo del script
  sea una entrada oficial (no un efecto colateral), cubierta por un test (H-4).
  Sin otros cambios de build.
- **Docs/tests**: sección de instalación de una línea en `README.md`/`USAGE.md`;
  nota de seguridad en `SECURITY.md` (verificación de checksum dentro del script);
  tests de shell (`bats`) mockeando `curl`/`uname`/`sha256sum`.
- **Criterio de cierre**: (a) **smoke-test automatizado** (`bats` mockeando
  `curl`/`uname`/`sha256sum`, ver línea 550) en CI como regresión continua; (b) en
  una VM Linux limpia (glibc ≥ 2.35), `curl … | sh` deja `tts-sidecar` invocable
  por nombre y el modelo provisionado, sin pasos manuales; (c) **desinstalación
  limpia (paridad estricta, G-5)**: `setup --remove-path` + borrado del AppImage
  dejan binario, PATH, caché del modelo y datos de usuario eliminados.
- **Riesgos residuales**: glibc < 2.35 (detectar y advertir); PATH no persistente
  en la sesión (el CLI ya lo avisa).

## Fase 2 — macOS (tap/Cask de Homebrew propio)

**Esfuerzo medio. Introduce el backbone de CI y el primer repo propio externo.**

- **Entregables**:
  - Repo `homebrew-tts-sidecar` con `Casks/tts-sidecar.rb`. Stanzas mínimas
    (H-3): `version`, `sha256`, `url` (al `.dmg` del Release), `binary` apuntando
    a `Contents/MacOS/tts-sidecar`, `livecheck` (`strategy :github_latest`),
    `zap trash:` (caché del modelo + datos de usuario), y `caveats` que sugiera
    `tts-sidecar setup`. `app` opcional (solo si se quiere el bundle en
    `/Applications`).
  - Job `publish-metadata` (en `.circleci/config.yml`) que, tras el Release público,
    lee la `version` del tag (`CIRCLE_TAG`) y el `sha256` del `.dmg` desde
    `SHA256SUMS.txt`, reescribe el Cask y hace push al tap con el context
    `homebrew-tap` (`HOMEBREW_TAP_PAT`).
- **Experiencia de usuario**: `brew tap <owner>/tts-sidecar && brew install --cask tts-sidecar`;
  Homebrew limpia la cuarentena (mitiga Gatekeeper) y expone el CLI en el PATH sin
  sudo.
- **Cambios de build**: el `.dmg` sirve tal cual; opcionalmente, simplificar el
  volumen para la vía Homebrew (los `.command` con `sudo` son redundantes ahí).
  No bloqueante.
- **Docs/tests**: `docs/RELEASING.md` (prerequisito del context + repo tap;
  reescritura de §3 «revisar y publicar el draft» → publicación directa + paso de
  publicación automática de metadata); `docs/DISTRIBUTION.md`/`docs/BUILD.md`
  (refinamiento macOS); test del generador de Cask (patrón de
  `tests/test_build_windows.py`).
- **Criterio de cierre**: publicar un release y verificar que `brew install
  --cask` instala la versión nueva (Cask actualizado automáticamente por el job) y
  expone `tts-sidecar` por nombre; la verificación es **automática si es viable**
  (`brew audit`/`brew style` o instalación headless en CI) y **manual en Mac limpio**
  si no (G-2). **Desinstalación limpia (paridad estricta, G-5)**: `brew uninstall
  --cask` + `zap trash:` (línea 568) dejan binario, PATH, caché del modelo y datos
  de usuario eliminados.
- **Riesgos residuales**: unicidad del nombre de Cask; `livecheck` correcto contra
  GitHub Releases; primer release manual del Cask antes de automatizar.

*(Canal Windows/winget diferido — ver la subsección «Roadmap futuro (diferido):
winget + SignPath Foundation», más abajo.)*

## Asunto transversal — antivirus / falsos positivos (no es una fase)

Requisito nuevo del propietario. **No** es una cuarta fase de los mecanismos
auto-hospedados: ninguno resuelve las alertas de antivirus salvo el Cask
(Gatekeeper en macOS). Se modela como dos líneas de trabajo paralelas,
independientes del orden de las Fases 1-2 (H-7):

- **Línea A — endurecimiento del build (comprometida en este ciclo; barata, sin
  dependencia de terceros)**:
  - Pasar `--noupx` de forma explícita en los flags compartidos
    (`build_utils.py`) para garantizar que el ejecutable nunca se comprima con UPX.
  - Embeber la metadata PE en el `.exe` de Windows (`--version-file`:
    empresa, producto, versión) para darle señales de confianza al clasificador
    de Defender.
  - Procedimiento documentado (*runbook*, guía paso a paso) para reportar los
    falsos positivos al portal WDSI de Microsoft (`microsoft.com/wdsi`) cuando un
    release sea marcado. **Alcance del runbook**: cubre solo la detección de
    **Defender Antivirus** (una firma concreta —p. ej. `Trojan:Win32/Wacatac`— que,
    tras revisión de un analista, Microsoft **borra globalmente** para todos los
    Defender). **No** apaga **SmartScreen**, que es reputación (no una firma de
    malware) y solo la resuelve la firma de código de la Línea B; ningún reporte
    WDSI lo desactiva. El reporte WDSI es **independiente de la firma** en dos
    sentidos: se puede reportar un binario sin firmar, y firmar por sí solo **no**
    borra una detección ya existente (solo el reporte lo hace). Lo que **sí** cambia
    con la firma es la **frecuencia** con la que hay que reportar: sin firma, la
    reputación se acumula **por archivo**, así que cada versión nueva parte de cero,
    puede volver a marcarse y el reporte **puede requerir repetirse en cada
    release** (cinta de correr); con la firma de la Línea B, la reputación pasa a
    acumularse **por editor/certificado** y las versiones nuevas la heredan, lo que
    **reduce mucho —sin eliminar del todo— esa recurrencia** (un binario firmado aún
    puede recibir algún falso positivo de la nube que haya que reportar).
  - **Criterio de cierre**: el `.exe` lleva metadata PE y `--noupx`; existe la guía
    de reporte a WDSI (con su alcance —Defender Antivirus, no SmartScreen— y las
    expectativas de recurrencia —re-reporte por release sin firma, decreciente con
    la firma de la Línea B— documentados).
- **Línea B — firma de código / notarización (= estrategia B, ya comprometida)**
  (`docs/GOAL.md:216-241`): Authenticode vía SignPath (Windows) + notarización
  Apple (macOS). Es la mitigación de fondo del canal nativo que se descarga a
  mano. Este ciclo **no** la reabre; solo la señala como el destino de la
  estrategia antivirus. La paridad de "ausencia de alertas" entre los 3 SO **solo**
  se alcanza hoy por el canal pip (estructural) y, en macOS, por el Cask (borra la
  cuarentena); Windows nativo la logrará únicamente con la Línea B.

## Roadmap futuro (diferido): winget + SignPath Foundation

El canal **Windows (winget, `Microsoft.PreIndexed.Package`)** se implementa **solo
en un ciclo futuro**, condicionado a dos hitos que hoy no se dan:

- **Firma Authenticode real vía SignPath Foundation** (Línea B de
  `docs/GOAL.md:216-241`): el proyecto debe ser aprobado por el programa SignPath
  OSS y obtener un certificado con cadena de confianza reconocida. Sin esto, winget
  no aporta reputación frente a SmartScreen —de hecho añadiría la marca
  Mark-of-the-Web y SmartScreen seguiría disparándose sobre el instalador sin
  firmar (H-7)—, y solo añadiría superficie de fallos y mantenimiento (madurez de
  `WinGetSourceCreator`, H-6) sin retorno actual ni próximo.
- **ROI positivo**: el esfuerzo de automatizar la fuente winget (y su mantenimiento
  anual de certificado, renovación, hosting) debe justificarse frente a los canales
  ya operativos (nativo + PyPI) y al Cask de macOS.

**Insumo ya acumulado** (preservado, no eliminado): H-1 documenta la viabilidad y
autonomía de la fuente autofirmada bajo la restricción rectora; H-6 documenta que el
riesgo real está en el tooling de generación del índice (`WinGetSourceCreator`), no
en la firma, y que la fase debe arrancar con un spike/PoC que valide
`winget source add` + `winget install` en una VM limpia. Ambos viven en la
subsección «Hallazgos diferidos (winget)».

**Condición de entrada para reabrir**: aprobación SignPath OSS + certificado real,
y ROI positivo. Hasta entonces el canal winget **no** figura en el alcance activo
del roadmap ni en el `create-plan` subsiguiente.

## Orden recomendado y dependencias

1. **Fase 1 (Linux)** — independiente, entregable de inmediato, sin infraestructura
   nueva ni Fase 0.
2. **Fase 0 (prerequisitos de Homebrew)** — crear el repo tap y el context
   `homebrew-tap`; gatea la Fase 2.
3. **Fase 2 (macOS)** — establece el backbone de CI (job `publish-metadata` en
   CircleCI + eliminación del draft en `publish-release`) y el patrón de repo propio
   + context + push; es el único consumidor del backbone en el alcance activo.
4. **(Futuro) Fase Windows/winget** — **no** en este ciclo; queda en la subsección
   «Roadmap futuro (diferido)», condicionada a SignPath Foundation + ROI positivo.

La **Línea A** (endurecimiento del build, sección «Asunto transversal») es
transversal, pero su *orden* conviene matizar. Los **build flags** (`--noupx`,
`--version-file`) se adelantan **antes de la Fase 1** porque son un cambio único en
`build_utils.py` que consumen todos los artefactos: `--noupx` evita la compresión
UPX en cualquier build de PyInstaller (incluido el bootloader del `.AppImage` de
Linux) y `--version-file` (metadata PE) es Windows-only y beneficia el `.exe`/
instalador Inno de la Fase 2 (y, en el futuro, de winget). Con este adelanto, el
`.AppImage` de Linux ya sale sin UPX y el `.exe` de Windows ya lleva la metadata PE
embebida. El **runbook WDSI** sí puede quedar suelto en paralelo, sin depender del
orden de las fases. La Línea A es **independiente de winget** y se ejecuta igual con
winget diferido.

Las fases activas (Fase 1 y Fase 2) son entregables independientes: se pueden
publicar y anunciar por separado. Ninguna bloquea el canal nativo ni el canal PyPI
existentes.

---

# Auditoría de completitud del roadmap (brechas)

Resultado de auditar el roadmap anterior contra los objetivos rectores
(experiencia equivalente por SO · publicación sin dependencia de terceros ·
estrategia antivirus).
El roadmap está **completo** para su propósito (insumo del plan, no el plan): cada
fase tiene entregables, cambios de build, docs/tests, criterio de cierre y riesgos
residuales. De las brechas detectadas en la auditoría, **todas** las de decisión
están cerradas: G-1/G-3/G-4/G-6 en la revisión y **G-2/G-5 el 2026-07-08** (ver
abajo). No quedan refinamientos abiertos que bloqueen el plan.

**Cerradas por decisión** (reflejadas en el roadmap de arriba):

- **G-1 — Fase 0 explícita**: formalizada como hito de prerequisitos compartidos.
- **G-3 — Fallo/idempotencia de `publish-metadata`**: resuelta en esta revisión
  (ver «Decisiones del propietario resueltas en esta revisión»). El job reconstruye
  sus insumos del Release público (`gh release download SHA256SUMS.txt` +
  `CIRCLE_TAG`), no del workspace, y su regeneración es idempotente — robusto ante
  la expiración de 15 días del workspace, al estilo del `--skip-existing` de
  `publish-pypi`.
- **G-4 — Contrato de `_integrate_linux_path()`**: se endurece con una vía
  soportada + test (Fase 1), no solo documentación.
- **G-6 — Estrategia antivirus**: modelada como asunto transversal (H-7), con la
  Línea A comprometida en este ciclo.
- **G-2 — Criterios de cierre (resuelta 2026-07-08)**: política mixta por SO.
  **Linux (Fase 1)** se certifica con **smoke-test automatizado** (`bats` mockeando
  `curl`/`uname`/`sha256sum`) por ser barato de automatizar y dar regresión continua.
  **macOS (Fase 2)** se automatiza si es viable (`brew audit`/`brew style` o
  instalación headless); si no, manual en Mac limpio. El canal Windows (winget)
  queda diferido y su criterio de cierre se reabrirá con la fase futura (ver
  «Roadmap futuro (diferido)»). No se exige automatización donde no aporte valor.
- **G-5 — Paridad de desinstalación (resuelta 2026-07-08)**: se fija **paridad
  estricta total** como criterio de cierre por fase. "Limpio" = quitar binario +
  integración de PATH + caché del modelo **y** datos de usuario, dejando el sistema
  idéntico a antes de instalar. Aplica a las fases activas (Linux, macOS); el canal
  Windows (winget) diferido retomará este criterio en su fase futura (ver
  «Roadmap futuro (diferido)»).

**Veredicto**: el roadmap simplificado (Fase 1 Linux + Fase 2 macOS + Línea A
activas; Fase 0 reducida a Homebrew; winget diferido a la sección futura) es
auditable, viable y **listo para `create-plan`**, con la arquitectura de CI
actualizada (100% CircleCI, sin draft), G-3 cerrada por decisión y **G-2/G-5
cerradas el 2026-07-08**. Sin brechas de decisión abiertas; el plan puede
redactarse sobre el alcance reducido.
