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
  previa, sino el propio grafo de dependencias: `build-windows-x64`,
  `build-linux-x64`, `build-linux-arm64`, `build-darwin-arm64` y
  `publish-pypi` declaran `requires: [test-linux, test-windows, test-macos]`,
  así que si los tests fallan en el pipeline del tag, ni los builds ni
  `publish-pypi` llegan a ejecutarse. Correr la suite en local antes de
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
triple puerta de tests + 4 builds **y además** el job `publish-release` (que solo
corre en tags `v*`, nunca en ramas).

## 2. Automático: lo que hace el CI

Una vez pushado el tag, el pipeline ejecuta sin intervención:

1. **Tests + builds**: la triple puerta de tests y los 4 builds nativos
   (`build-windows-x64`, `build-linux-x64`, `build-linux-arm64`,
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

Ya no hay descarga ni cotejo manual de artefactos: la recolección por workspace
es determinista (el mismo binario que pasó el smoke test es el que se adjunta).

## 3. Verificación post-publicación

En la pestaña **Releases** del repo aparece el Release `vX.Y.Z` **ya público**
(marcado como *latest* por defecto), con sus 5 assets y las notas del CHANGELOG.
Verifica:

- Los **5 assets** están presentes (4 artefactos + `SHA256SUMS.txt`).
- Las **notas** corresponden a la sección `[X.Y.Z]` del `CHANGELOG.md`.
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
