"""Tests estáticos del script Inno Setup generado para el instalador de Windows."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from create_installer_windows import generate_iss


@pytest.fixture
def iss(tmp_path):
    """ISS generado con rutas temporales y versión sintética."""
    source_dir = tmp_path / "onedir"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    info_after = tmp_path / "info.txt"
    info_after.write_text("info", encoding="utf-8")
    return generate_iss(source_dir, output_dir, "9.9.9", info_after)


def test_nombre_del_instalador_incluye_version_y_sufijo(iss):
    # A-03: vocabulario de arquitectura unificado al estilo `uname -m` (x86_64),
    # en paridad con los AppImage de Linux.
    assert "OutputBaseFilename=tts-sidecar-9.9.9-x86_64-setup" in iss


def test_setup_postinstalacion_persiste_la_consola(iss):
    # W-03: el setup post-instalación se lanza vía `cmd /k` para que la consola
    # quede abierta mostrando el resultado (éxito o fallo) hasta que el usuario
    # la cierre — paridad con la Terminal persistente del .command de macOS.
    assert 'Filename: {cmd}; Parameters: "/k ""{app}\\tts-sidecar.exe"" setup"' in iss
    assert "postinstall skipifsilent runasoriginaluser nowait" in iss


def test_agrega_path_condicionado_por_needsaddpath(iss):
    assert "function NeedsAddPath(Param: string): boolean;" in iss
    assert "Check: NeedsAddPath(ExpandConstant('{app}'))" in iss


def test_desinstalacion_recorta_la_entrada_de_path(iss):
    # W-01: el desinstalador debe revertir la entrada {app} del PATH de HKLM.
    assert "procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);" in iss
    assert "usUninstall" in iss
    assert "RegWriteExpandStringValue(HKLM," in iss


def test_sin_clave_uninstall_manual(iss):
    # W-02: Inno Setup genera su propia entrada ({AppId}_is1); la clave manual
    # duplicaría el programa en «Aplicaciones y características».
    assert "CurrentVersion\\Uninstall\\tts-sidecar" not in iss
