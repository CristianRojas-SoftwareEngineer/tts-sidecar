"""Tests de las utilidades compartidas de los scripts de build."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_utils
from build_utils import (
    get_version, bundle_size_mb, ensure_build_dependency, fetch_pinned_asset,
)


def test_lee_version_de_init_sintetico(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    assert get_version(init) == "1.2.3"


def test_acepta_comillas_simples(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text("__version__ = '4.5.6'\n", encoding="utf-8")
    assert get_version(init) == "4.5.6"


def test_sin_version_lanza_runtime_error(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""Módulo sin versión."""\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        get_version(init)


def test_default_lee_la_version_real_del_repo():
    from chatterbox_tts import __version__
    assert get_version() == __version__


class TestEnsureBuildDependency:
    """Política interactiva única de dependencias de build (verificar → avisar →
    preguntar solo con TTY → instalar pineado o degradar/abortar por criticidad)."""

    def test_presente_no_pregunta_ni_instala(self, monkeypatch):
        preguntas = []
        monkeypatch.setattr("builtins.input", lambda *a: preguntas.append(a) or "s")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        assert ensure_build_dependency("herramienta", lambda: True, ["pip", "install", "x"]) is True
        assert preguntas == []
        assert instalaciones == []

    def test_ausente_con_confirmacion_instala_y_reverifica(self, monkeypatch):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a: "s")
        instalaciones = []
        estados = iter([False, True])  # ausente antes, presente tras instalar
        monkeypatch.setattr(
            build_utils.subprocess, "run",
            lambda cmd, **k: instalaciones.append(cmd),
        )

        resultado = ensure_build_dependency(
            "herramienta", lambda: next(estados), ["pip", "install", "x==1.0"],
        )

        assert resultado is True
        assert instalaciones == [["pip", "install", "x==1.0"]]

    def test_ausente_con_rechazo_required_aborta(self, monkeypatch):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        with pytest.raises(SystemExit):
            ensure_build_dependency(
                "herramienta", lambda: False, ["pip", "install", "x"], required=True,
            )
        assert instalaciones == []

    def test_ausente_con_rechazo_opcional_retorna_false(self, monkeypatch):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        resultado = ensure_build_dependency(
            "herramienta", lambda: False, ["pip", "install", "x"], required=False,
        )
        assert resultado is False
        assert instalaciones == []

    def test_ausente_sin_tty_no_pregunta_y_resuelve_por_criticidad(self, monkeypatch, capsys):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: False)

        def _input_prohibido(*a):
            raise AssertionError("no debe preguntar sin TTY")

        monkeypatch.setattr("builtins.input", _input_prohibido)
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        resultado = ensure_build_dependency(
            "herramienta", lambda: False, ["pip", "install", "x"], required=False,
        )
        assert resultado is False
        assert instalaciones == []
        assert "Instalación manual: pip install x" in capsys.readouterr().out

        with pytest.raises(SystemExit):
            ensure_build_dependency(
                "herramienta", lambda: False, ["pip", "install", "x"], required=True,
            )


class TestFetchPinnedAsset:
    """L-03: descarga pineada por URL + SHA-256 del tooling del AppImage
    (appimagetool y runtime estático). Sin red: se sirve un archivo local
    vía file:// y se verifica la rama de caché y la de checksum."""

    CONTENIDO = b"binario pineado de prueba"
    # SHA-256 precomputado de CONTENIDO.
    SHA_OK = __import__("hashlib").sha256(CONTENIDO).hexdigest()

    def _servir(self, tmp_path) -> str:
        src = tmp_path / "asset.bin"
        src.write_bytes(self.CONTENIDO)
        return src.resolve().as_uri()

    def test_descarga_y_verifica_checksum(self, tmp_path):
        url = self._servir(tmp_path)
        dest = tmp_path / "cache" / "asset.bin"

        resultado = fetch_pinned_asset(url, self.SHA_OK, dest)

        assert resultado == dest
        assert dest.read_bytes() == self.CONTENIDO

    def test_checksum_incorrecto_aborta_y_elimina_el_archivo(self, tmp_path):
        url = self._servir(tmp_path)
        dest = tmp_path / "cache" / "asset.bin"

        with pytest.raises(SystemExit):
            fetch_pinned_asset(url, "0" * 64, dest)
        assert not dest.exists()

    def test_cache_con_checksum_valido_no_descarga(self, tmp_path, monkeypatch):
        dest = tmp_path / "cache" / "asset.bin"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(self.CONTENIDO)

        import urllib.request

        def _red_prohibida(*a, **k):
            raise AssertionError("no debe descargar si la caché tiene el hash pineado")

        monkeypatch.setattr(urllib.request, "urlopen", _red_prohibida)

        resultado = fetch_pinned_asset("https://example.invalid/asset.bin", self.SHA_OK, dest)
        assert resultado == dest


def test_bundle_size_mb_suma_archivos_anidados(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "b.bin").write_bytes(b"y" * 1024)

    esperado_mb = (1024 + 1024) / (1024 * 1024)
    assert bundle_size_mb(tmp_path) == pytest.approx(esperado_mb)
