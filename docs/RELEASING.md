# Publicación de una versión (RELEASING.md)

`tts-sidecar` publica sus releases de forma **semi-automática**: al pushear un
tag `v*`, CircleCI corre los tests, los 4 builds y el job `publish-release`, que
recolecta los artefactos, genera `SHA256SUMS.txt` y crea un **GitHub Release en
borrador (draft)**. El propietario solo revisa el draft y pulsa «publish». Sin
firma de código (R-38), el cotejo de checksums SHA-256 sigue siendo la cadena de
verificación de integridad para el usuario final.

## Prerequisitos

- No hay hallazgos Bloqueantes ni Mayores abiertos (criterios de
  aceptación del release; ver `docs/GOAL.md` §"Criterios de Aceptación").
- `CHANGELOG.md` tiene la sección de la versión a publicar cortada (no
  "No publicado"), con las entradas reales de esa versión. **El job de release
  falla si no encuentra la sección `[X.Y.Z]`** (X.Y.Z = tag sin la `v`), así que
  este corte es obligatorio antes de taggear.
- La suite pasa en los tres SO (`test-linux`, `test-windows`, `test-macos` en
  verde en CircleCI para el commit a taggear).
- **Prerequisito operativo (una sola vez):** existe el context `github-release`
  en CircleCI (Organization Settings → Contexts) con la variable `GH_TOKEN` = un
  fine-grained PAT con permiso `contents: write` sobre el repo. Está aislado al
  job `publish-release`; ningún otro job lo ve.

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
   - Crea el GitHub Release en **borrador** sobre el tag `vX.Y.Z`, con los 5
     assets (4 artefactos + `SHA256SUMS.txt`) y las notas.

Ya no hay descarga ni cotejo manual de artefactos: la recolección por workspace
es determinista (el mismo binario que pasó el smoke test es el que se adjunta).

## 3. Manual: revisar y publicar el draft

En la pestaña **Releases** del repo aparece el borrador `vX.Y.Z`. Revisa:

- Los **5 assets** están presentes (4 artefactos + `SHA256SUMS.txt`).
- Las **notas** corresponden a la sección `[X.Y.Z]` del `CHANGELOG.md`.
- Opcional: coteja los hashes de `SHA256SUMS.txt` contra los emitidos por cada
  build en el log del pipeline (step "Emit artifact SHA-256").

Si todo está bien, pulsa **«Publish release»**. Si algo falla (el job no corrió,
faltan assets, notas vacías), corrige e itera: borra el draft, arregla la causa
(p. ej. la sección del CHANGELOG) y **re-crea el tag** sobre el commit corregido.

> Si el tag ya tuviera un Release, `gh release create` falla ruidosamente en el
> CI (no re-publica en silencio): borra el Release/draft anterior antes de
> re-taggear.

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
