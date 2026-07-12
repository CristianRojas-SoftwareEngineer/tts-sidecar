# Publicación de una versión (RELEASING.md)

`tts-sidecar` publica sus releases de forma **automática**: al pushear un
tag `v*`, CircleCI corre los tests, los 4 builds y el job `publish-release`, que
recolecta los artefactos, genera `SHA256SUMS.txt` y **publica el GitHub Release
directo** (sin borrador) sobre el tag. Sin firma de código (R-38), el cotejo de
checksums SHA-256 sigue siendo la cadena de verificación de integridad para el
usuario final.

En paralelo a los 4 builds nativos corre el job **`publish-pypi`**, que publica
el paquete al canal PyPI (ver [docs/DISTRIBUTION.md](DISTRIBUTION.md)). Igual que
`publish-release`, `publish-pypi` **no tiene paso de revisión manual**: ambos
publican en firme en el mismo tag, sin generar un borrador ni requerir un clic
humano.

## Prerequisitos

- No hay hallazgos Bloqueantes ni Mayores abiertos (criterios de
  aceptación del release; ver `docs/GOAL.md` §"Criterios de Aceptación").
- `CHANGELOG.md` tiene la sección de la versión a publicar cortada (no
  "No publicado"), con las entradas reales de esa versión. **El job de release
  falla si no encuentra la sección `[X.Y.Z]`** (X.Y.Z = tag sin la `v`), así que
  este corte es obligatorio antes de taggear.
- La suite pasa localmente (`pytest tests/ -v`) en el commit a taggear. **No
  hay forma de verificar esto en CircleCI antes de taggear**: el workflow
  `build-all` tiene `branches: ignore: /.*/` en todos sus jobs, así que
  CircleCI no corre nada en pushes a `main` — el tag es lo único que dispara
  el pipeline. La protección dentro del pipeline no es una comprobación
  previa, sino el propio grafo de dependencias: los 4 builds
  (`build-windows-x64`, `build-linux-x64`, `build-linux-arm64`,
  `build-darwin-arm64`) declaran `requires` sobre la triple puerta de tests
  (`test-linux`, `test-windows`, `test-macos`) **más** los tres smoke-tests de
  instaladores (`test-installer-linux`, `test-installer-windows`,
  `test-installer-macos`);
  `publish-pypi` declara solo la triple puerta de tests (los instaladores de
  una línea no participan del canal PyPI). Si cualquiera de esas puertas falla
  en el pipeline del tag, ni los builds ni `publish-pypi` llegan a ejecutarse. Correr la suite en local antes de
  taggear sigue siendo la única manera de anticipar ese resultado.
- **Revisiones fijadas del modelo auditadas** (R-15): las constantes
  `MODEL_REVISIONS` y `BASE_MODEL_REVISION` de `src/tts_sidecar/model_cache.py`
  apuntan a los commit hashes de HuggingFace que este release distribuye. Si el
  release debe incorporar una versión nueva del modelo: consultar el `sha`
  vigente (`https://huggingface.co/api/models/<repo>`), auditar el diff de esa
  revisión en HF, actualizar las constantes y verificar con
  `setup --force-update` + `doctor`. Si no hay cambio de modelo, no hay nada
  que hacer (el pin existente sigue vigente).
- **Prerequisito operativo (una sola vez):** existe el context `github-release`
  en CircleCI (Organization Settings → Contexts) con la variable `GH_TOKEN` = un
  fine-grained PAT con permiso `contents: write` sobre el repo. Está aislado al
  job `publish-release`; ningún otro job lo ve.
- **Prerequisito operativo (una sola vez):** existe el context `pypi-publish`
  en CircleCI con la variable `PYPI_API_TOKEN` = un token API de PyPI con scope
  al proyecto. Está aislado al job `publish-pypi`; ningún otro job lo ve.
- **Prerequisitos del canal Cask de macOS (una sola vez):** existe el
  repositorio tap `homebrew-tts-sidecar` (público), y el context de CircleCI
  `homebrew-tap` con la variable `HOMEBREW_TAP_PAT` (un PAT fine-grained con
  permiso `Contents:RW` solo sobre el tap). Está aislado al job
  `publish-metadata`. Además, **el primer Cask del tap es un bootstrap manual
  único**: `publish-metadata` reescribe `Casks/tts-sidecar.rb`, pero asume que
  el archivo ya existe en el tap la primera vez (crearlo a mano con el
  generador: `python scripts/render_cask.py --tag vX.Y.Z --sums-file
  SHA256SUMS.txt --out Casks/tts-sidecar.rb` y commitear/pushear al tap antes
  del primer release que dependa de este job). Detalle del diseño completo en
  [docs/SELF-HOSTED-INSTALL.md](SELF-HOSTED-INSTALL.md).
- **La publicación a PyPI es irreversible**: al igual que el GitHub Release —que
  se publica directo sobre el tag y, para revertirlo, hay que borrar un Release
  ya público—, el tag dispara la publicación en firme a PyPI: un paquete subido
  no se puede sobrescribir, solo yankear una versión y publicar una nueva. Por
  eso el corte del `CHANGELOG.md` y la versión en `__init__.py` deben estar
  correctos **antes** de crear el tag, no después.

## 1. Corte: crear y publicar el tag

```bash
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

El push del tag dispara el workflow `build-all` en CircleCI sobre ese commit:
triple puerta de tests + 3 smoke-tests de instaladores + 4 builds **y además**
el job `publish-release` (que solo corre en tags `v*`, nunca en ramas).

## 2. Automático: lo que hace el CI

Una vez pushado el tag, el pipeline ejecuta sin intervención:

1. **Tests + builds**: la triple puerta de tests, los smoke-tests de
   instaladores (`test-installer-linux`, `test-installer-windows`,
   `test-installer-macos`) y los 4
   builds nativos (`build-windows-x64`, `build-linux-x64`, `build-linux-arm64`,
   `build-darwin-arm64`). Cada build emite el SHA-256 de su artefacto en el log
   (step "Emit artifact SHA-256") y **persiste el artefacto versionado** al
   workspace compartido.
2. **`publish-release`** (tras los 4 builds):
   - Recolecta los 4 artefactos del workspace (`attach_workspace`) — ya con su
     nombre de release: `tts-sidecar-X.Y.Z-x86_64-setup.exe`,
     `tts-sidecar-X.Y.Z-x86_64.AppImage`, `tts-sidecar-X.Y.Z-aarch64.AppImage`,
     `tts-sidecar-X.Y.Z-arm64.dmg`.
   - Genera `SHA256SUMS.txt` con los checksums de los 4.
   - Extrae las notas de la sección `[X.Y.Z]` de `CHANGELOG.md`.
   - Inyecta en `notes.md` (tras el recorte del CHANGELOG) un pie con la oferta
     de código fuente **GPLv3 §6**: el tarball del tag
     (`archive/refs/tags/vX.Y.Z.tar.gz`) y el enlace al tag, para que todo
     release cumpla el compliance de fuente de forma automática sin depender de
     que el humano la añada a mano.
   - Publica el GitHub Release directo (sin borrador) sobre el tag `vX.Y.Z`, con
     los 5 assets (4 artefactos + `SHA256SUMS.txt`) y las notas.
3. **`publish-pypi`** (en paralelo a los 4 builds, solo requiere la triple
   puerta de tests): construye el sdist y el wheel, valida la metadata
   (`twine check`), instala el wheel en un venv limpio para verificar que
   `tts-sidecar version` coincide con el tag y que la voz `default` está
   presente, y publica a PyPI con `twine upload --skip-existing`. Detalle
   completo en [docs/DISTRIBUTION.md](DISTRIBUTION.md#flujo-de-publicación-ci).
   El `--skip-existing` hace idempotente el job ante un re-tag: si falla un
   build nativo y hay que borrar y recrear el tag (Ej. sección "1. Corte"),
   el pipeline nuevo vuelve a correr `publish-pypi` desde cero — si esa
   versión ya se había publicado con éxito en el intento anterior, twine
   detecta que el archivo ya existe en PyPI y termina en éxito sin reintentar
   el upload, en vez de fallar ruidosamente.

3. **`publish-metadata`** (tras `publish-release`, solo en tags `v*`): recupera
   `SHA256SUMS.txt` del Release recién publicado (`gh release download`,
   idempotente y sin depender del workspace del pipeline), reescribe
   `Casks/tts-sidecar.rb` con la versión del tag y el sha256 del `.dmg` arm64
   (`scripts/render_cask.py`), y hace push al tap `homebrew-tts-sidecar`. Si el
   Cask no cambia (regeneración con los mismos inputs), el commit es un no-op y
   no se empuja nada; reintentar este job en cualquier momento es seguro.

Ya no hay descarga ni cotejo manual de artefactos: la recolección por workspace
es determinista (el mismo binario que pasó el smoke test es el que se adjunta).

## 3. Verificación post-publicación

En la pestaña **Releases** del repo aparece el Release `vX.Y.Z` **ya público**
(marcado como *latest* por defecto), con sus 5 assets y las notas del CHANGELOG.
Verifica:

- Los **5 assets** están presentes (4 artefactos + `SHA256SUMS.txt`).
- Las **notas** corresponden a la sección `[X.Y.Z]` del `CHANGELOG.md`.
- Las **notas** incluyen el pie de oferta de código fuente GPLv3 §6: el enlace al
  tarball de fuente (`.../archive/refs/tags/vX.Y.Z.tar.gz`) aparece en el Release.
- Opcional: coteja los hashes de `SHA256SUMS.txt` contra los emitidos por cada
  build en el log del pipeline (step "Emit artifact SHA-256").

El tag es el **punto de no retorno**: el Release es público en cuanto el job
termina. Si algo falla (faltan assets, notas incorrectas, artefacto roto), la
iteración ya no es descartar un borrador: **borra el Release público** y
**re-crea el tag** sobre el commit corregido (p. ej. tras arreglar la sección del
CHANGELOG).

> Si el tag ya tuviera un Release, `gh release create` falla ruidosamente en el
> CI (no re-publica en silencio): borra el Release anterior antes de re-taggear.

## 4. Verificación del usuario final

El usuario final puede verificar la integridad de su descarga contra
`SHA256SUMS.txt` publicado en el Release:

```bash
# Linux/macOS
sha256sum -c SHA256SUMS.txt --ignore-missing

# Windows (PowerShell)
Get-FileHash tts-sidecar-X.Y.Z-x86_64-setup.exe -Algorithm SHA256
# comparar manualmente contra la línea correspondiente de SHA256SUMS.txt
```

Ver también `SECURITY.md` para el modelo de amenaza y la nota sobre binarios
sin firmar.
