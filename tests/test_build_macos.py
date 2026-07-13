"""Tests estáticos de los templates generados por build_macos.py.

Aserciones de cadena sobre las funciones puras: _path_install_script,
_path_uninstall_script, _info_plist_content.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from build_macos import (
    _info_plist_content,
    _minimum_system_version,
    _path_install_script,
    _path_uninstall_script,
)


def test_info_plist_version_and_lsminimum():
    """Info.plist debe llevar la versión y el LSMinimumSystemVersion derivado del toolchain ."""
    plist = _info_plist_content("9.9.9", icon_name="tts-sidecar")
    assert "<key>CFBundleShortVersionString</key>" in plist
    assert "<string>9.9.9</string>" in plist
    assert "<key>LSMinimumSystemVersion</key>" in plist
    assert f"<string>{_minimum_system_version()}</string>" in plist
    assert "GPL-3.0-or-later" in plist


def test_minimum_system_version_uses_deployment_target(monkeypatch):
    """Prioriza MACOSX_DEPLOYMENT_TARGET; cae a mac_ver() si falta."""
    import build_macos

    monkeypatch.setattr(
        build_macos.sysconfig, "get_config_var", lambda name: "14.4"
    )
    assert build_macos._minimum_system_version() == "14.4"

    monkeypatch.setattr(build_macos.sysconfig, "get_config_var", lambda name: None)
    monkeypatch.setattr(
        build_macos.platform, "mac_ver", lambda: ("15.1.1", ("", "", ""), "")
    )
    assert build_macos._minimum_system_version() == "15.0"

    monkeypatch.setattr(build_macos.platform, "mac_ver", lambda: ("", ("", "", ""), ""))
    assert build_macos._minimum_system_version() == "12.0"


def test_install_script_per_user_symlink_no_sudo_and_setup_offer():
    """El .command de instalación: symlink per-user en ~/.local/bin, SIN sudo,
    aviso de PATH y oferta de setup."""
    script = _path_install_script("tts-sidecar-arm64.app")
    assert script.startswith("#!/bin/bash\n")
    assert "set -e" in script
    # Per-user, sin privilegios de admin: nada de sudo ni /usr/local/bin.
    assert "sudo" not in script
    assert "/usr/local/bin" not in script
    assert '$HOME/.local/bin/tts-sidecar' in script
    assert 'mkdir -p "$HOME/.local/bin"' in script
    assert "ln -sf" in script
    # Aviso de PATH (~/.local/bin no está en el PATH por defecto de zsh en macOS).
    assert "no está en tu PATH" in script
    assert 'export PATH="$HOME/.local/bin:$PATH"' in script
    # Oferta de descargar el modelo (tts-sidecar setup) en el contexto del usuario
    assert "tts-sidecar setup" in script
    assert "Descargar ahora el modelo de voz" in script
    assert "s/n" in script  # prompt interactivo


def test_uninstall_script_per_user_no_sudo_and_legacy_note():
    """Desinstalación per-user: elimina el symlink de ~/.local/bin sin sudo,
    rechaza archivo regular homónimo e informa del symlink legado."""
    script = _path_uninstall_script()
    assert script.startswith("#!/bin/bash\n")
    assert "set -e" in script
    assert 'LINK="$HOME/.local/bin/tts-sidecar"' in script
    assert 'if [ -L "$LINK" ]; then' in script
    assert 'elif [ -e "$LINK" ]; then' in script
    assert "no es un symlink" in script
    assert "exit 1" in script
    # La eliminación del symlink per-user no usa sudo.
    assert "rm \"$LINK\"" in script
    # Detección informativa del symlink legado en /usr/local/bin (transición).
    assert 'LEGACY="/usr/local/bin/tts-sidecar"' in script
    assert "symlink legado" in script
    assert "sudo rm $LEGACY" in script


def test_create_dmg_failure_is_fatal(tmp_path, monkeypatch):
    """create-dmg con rc != 0 debe abortar el build con SystemExit(1),
    heredando la consola (sin capture_output) para que su output sea visible."""
    import build_macos

    dist = tmp_path / "dist"
    build = tmp_path / "build"
    dist.mkdir()
    build.mkdir()
    onedir = dist / "tts-sidecar"
    onedir.mkdir()
    (onedir / "tts-sidecar").write_text("bin", encoding="utf-8")

    monkeypatch.setattr(build_macos, "DIST_DIR", dist)
    monkeypatch.setattr(build_macos, "BUILD_DIR", build)
    monkeypatch.setattr(build_macos, "run_pyinstaller", lambda args, timeout: 0)
    monkeypatch.setattr(build_macos, "bundle_size_mb", lambda o: 0.0)
    monkeypatch.setattr(build_macos, "copy_license_files", lambda d: None)
    monkeypatch.setattr(build_macos, "ensure_icns", lambda d: None)
    monkeypatch.setattr(build_macos, "get_version", lambda: "9.9.9")

    captured = {}

    class Result:
        returncode = 1

    def fake_run(*a, **k):
        captured.update(k)
        return Result()

    monkeypatch.setattr(build_macos.subprocess, "run", fake_run)

    with pytest.raises(SystemExit) as exc:
        build_macos.build_macos("arm64")
    assert exc.value.code == 1
    assert "capture_output" not in captured