"""Tests estructurales del pipeline de CI (CircleCI).

Verifican que ciertos comportamientos del release y de los smoke tests de
binario congelado no se eliminen silenciosamente en `.circleci/config.yml`,
pues son la única barrera automática de compliance (GPLv3 §6) y de integridad
del empaquetado de voces.
"""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / ".circleci" / "config.yml"


@pytest.fixture(scope="module")
def config_text():
    return CONFIG_PATH.read_text(encoding="utf-8")


def test_config_exists(config_text):
    # Fixture indirecto: si el archivo no existe, la lectura falla antes.
    assert isinstance(config_text, str) and config_text.strip()


def test_publish_release_offers_source_tarball(config_text):
    """El job `publish-release` debe inyectar la oferta de fuente GPL.

    Si se elimina el pie en CI (tarball + nota GPLv3 §6), este test falla.
    """
    assert "archive/refs/tags/" in config_text, (
        "Falta el tarball de fuente en publish-release (GPLv3 §6)"
    )
    assert "GPL" in config_text, (
        "Falta la referencia a la licencia GPL en publish-release"
    )


def test_smoke_tests_validate_bundled_default_voice(config_text):
    """Los 4 smoke tests de binario congelado deben correr `voice list`.

    `voice list` debe aparecer al menos 4 veces (una por cada job de build:
    build-windows-x64, build-linux-x64, build-linux-arm64, build-darwin-arm64).
    """
    count = config_text.count("voice list")
    assert count >= 4, (
        f"Se esperaban >=4 ocurrencias de 'voice list' en los smoke tests "
        f"de los 4 bins congelados; encontradas: {count}"
    )
