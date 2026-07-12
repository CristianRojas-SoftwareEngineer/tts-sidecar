#!/bin/sh
# Instalador auto-hospedado de tts-sidecar para Linux.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/main/install.sh | sh
#
# Resuelve el último Release de GitHub, elige el .AppImage de la arquitectura
# del host, descarga el AppImage y SHA256SUMS.txt, verifica el checksum
# (abortando si no coincide), lo instala en ~/.local/opt/tts-sidecar/ y
# exporta APPIMAGE antes de invocar `setup`, que integra el PATH (symlink en
# ~/.local/bin) y ofrece descargar el modelo de voz. Ver
# docs/SELF-HOSTED-INSTALL.md para el diseño completo.
#
# POSIX sh: sin bashismos, para funcionar bajo `sh` en cualquier distro (dash,
# busybox sh, bash en modo POSIX).

set -eu

REPO="CristianRojas-SoftwareEngineer/TTS-Sidecar"
INSTALL_DIR="${HOME}/.local/opt/tts-sidecar"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"

log() {
    printf '%s\n' "$*" >&2
}

fail() {
    log "ERROR: $*"
    exit 1
}

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || fail "falta el comando requerido: $1"
}

require_cmd curl
require_cmd uname
require_cmd sha256sum
require_cmd chmod
require_cmd mkdir

# --- Selección de arquitectura -------------------------------------------
# Mapea uname -m al sufijo de arquitectura de los assets del release
# (build-linux-x64 → *-x86_64.AppImage, build-linux-arm64 → *-aarch64.AppImage).
machine="$(uname -m)"
case "$machine" in
    x86_64|amd64)
        ASSET_ARCH="x86_64"
        ;;
    aarch64|arm64)
        ASSET_ARCH="aarch64"
        ;;
    *)
        fail "arquitectura no soportada: $machine (tts-sidecar publica x86_64 y aarch64 para Linux)"
        ;;
esac
log "Arquitectura detectada: $machine -> $ASSET_ARCH"

# --- glibc: guard de versión mínima ----------------------------------------
# El AppImage se compila sobre glibc 2.35 (runner base Ubuntu 22.04); en distros
# más antiguas no arranca. Detectarlo aquí evita instalar un binario que
# fallaría en el primer uso: se aborta encaminando a las alternativas (PyPI o
# compilación desde fuente). Si la versión no puede parsearse se continúa: es
# preferible no bloquear a ciegas sobre un parseo fallido.
if command -v ldd >/dev/null 2>&1; then
    glibc_version="$(ldd --version 2>/dev/null | head -n1 | grep -o '[0-9]\+\.[0-9]\+$' || true)"
    if [ -n "$glibc_version" ]; then
        glibc_major="$(printf '%s' "$glibc_version" | cut -d. -f1)"
        glibc_minor="$(printf '%s' "$glibc_version" | cut -d. -f2)"
        if [ "$glibc_major" -lt 2 ] || { [ "$glibc_major" -eq 2 ] && [ "$glibc_minor" -lt 35 ]; }; then
            log "glibc $glibc_version detectada: el AppImage requiere glibc >= 2.35 y no funcionaría en este sistema."
            log "Alternativas: instala desde PyPI ('uv tool install tts-sidecar' o 'pipx install tts-sidecar') o compila desde la fuente (docs/BUILD.md)."
            fail "glibc insuficiente ($glibc_version < 2.35)"
        fi
    fi
fi

# --- Resolver el release y elegir los assets ------------------------------
log "Resolviendo el último release de $REPO..."
release_json="$(curl -fsSL "$API_URL")" || fail "no se pudo consultar $API_URL"

# Extrae las URLs de descarga de los assets sin depender de jq (no siempre
# está instalado): parseo de línea con grep/sed sobre el JSON de la API.
appimage_url="$(printf '%s' "$release_json" \
    | grep -o "\"browser_download_url\": *\"[^\"]*${ASSET_ARCH}\.AppImage\"" \
    | sed -E 's/.*"(https:[^"]+)"/\1/' \
    | head -n1)"
sums_url="$(printf '%s' "$release_json" \
    | grep -o '"browser_download_url": *"[^"]*SHA256SUMS\.txt"' \
    | sed -E 's/.*"(https:[^"]+)"/\1/' \
    | head -n1)"

[ -n "$appimage_url" ] || fail "no se encontró un .AppImage de $ASSET_ARCH en el último release"
[ -n "$sums_url" ] || fail "no se encontró SHA256SUMS.txt en el último release"

appimage_name="$(basename "$appimage_url")"
log "Asset seleccionado: $appimage_name"

# --- Descarga y verificación de checksum ----------------------------------
work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT

log "Descargando $appimage_name..."
curl -fsSL -o "$work_dir/$appimage_name" "$appimage_url" || fail "descarga del AppImage fallida"

log "Descargando SHA256SUMS.txt..."
curl -fsSL -o "$work_dir/SHA256SUMS.txt" "$sums_url" || fail "descarga de SHA256SUMS.txt fallida"

log "Verificando checksum..."
( cd "$work_dir" && grep "$appimage_name\$" SHA256SUMS.txt | sha256sum -c - ) \
    || fail "el checksum de $appimage_name no coincide con SHA256SUMS.txt; instalación abortada"

# --- Instalación -----------------------------------------------------------
mkdir -p "$INSTALL_DIR"
final_path="$INSTALL_DIR/$appimage_name"
mv "$work_dir/$appimage_name" "$final_path"
chmod +x "$final_path"
log "Instalado en: $final_path"

# --- Limpieza de versiones anteriores -------------------------------------
# El directorio de instalación es propiedad exclusiva del proyecto. Tras
# instalar y dar permisos al AppImage nuevo (nunca antes: no puede quedar el
# directorio sin ningún AppImage funcional), eliminar los AppImages previos
# para no acumular ~1-2 GB por versión en silencio. Solo borra archivos
# tts-sidecar-*.AppImage distintos del recién instalado.
for old in "$INSTALL_DIR"/tts-sidecar-*.AppImage; do
    [ -e "$old" ] || continue
    if [ "$old" != "$final_path" ]; then
        rm -f "$old" && log "Eliminada versión anterior: $old"
    fi
done

# --- Integración de PATH + provisión del modelo ---------------------------
# APPIMAGE es el contrato oficial que _integrate_linux_path() (cli.py) usa
# para crear el symlink en ~/.local/bin; exportarla aquí, fuera de un runtime
# AppImage real, es la vía soportada (docs/SELF-HOSTED-INSTALL.md).
export APPIMAGE="$final_path"
log "Ejecutando 'tts-sidecar setup' (integra el PATH y ofrece descargar el modelo)..."
"$final_path" setup

log "Instalación completa."
