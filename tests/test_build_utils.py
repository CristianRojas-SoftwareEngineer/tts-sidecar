"""Tests de las utilidades compartidas de los scripts de build."""

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import build_utils
from build_utils import (
    get_version, bundle_size_mb, ensure_build_dependency, fetch_pinned_asset,
    run_pyinstaller, INSTALLER_TIMEOUT, common_pyinstaller_args,
)


def test_reads_version_from_synthetic_init(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('__version__ = "1.2.3"\n', encoding="utf-8")
    assert get_version(init) == "1.2.3"


def test_accepts_single_quotes(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text("__version__ = '4.5.6'\n", encoding="utf-8")
    assert get_version(init) == "4.5.6"


def test_without_version_raises_runtime_error(tmp_path):
    init = tmp_path / "__init__.py"
    init.write_text('"""Módulo sin versión."""\n', encoding="utf-8")
    with pytest.raises(RuntimeError):
        get_version(init)


def test_default_reads_real_repo_version():
    from tts_sidecar import __version__
    assert get_version() == __version__


class TestEnsureBuildDependency:
    """Política interactiva única de dependencias de build (verificar → avisar →
    preguntar solo con TTY → instalar pineado o degradar/abortar por criticidad)."""

    def test_present_does_not_prompt_or_install(self, monkeypatch):
        preguntas = []
        monkeypatch.setattr("builtins.input", lambda *a: preguntas.append(a) or "s")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        assert ensure_build_dependency("herramienta", lambda: True, ["pip", "install", "x"]) is True
        assert preguntas == []
        assert instalaciones == []

    def test_absent_with_confirmation_installs_and_reverifies(self, monkeypatch):
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

    def test_absent_with_required_rejection_aborts(self, monkeypatch):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        with pytest.raises(SystemExit):
            ensure_build_dependency(
                "herramienta", lambda: False, ["pip", "install", "x"], required=True,
            )
        assert instalaciones == []

    def test_absent_with_optional_rejection_returns_false(self, monkeypatch):
        monkeypatch.setattr(build_utils.sys.stdin, "isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a: "n")
        instalaciones = []
        monkeypatch.setattr(build_utils.subprocess, "run", lambda *a, **k: instalaciones.append(a))

        resultado = ensure_build_dependency(
            "herramienta", lambda: False, ["pip", "install", "x"], required=False,
        )
        assert resultado is False
        assert instalaciones == []

    def test_absent_without_tty_does_not_prompt_and_resolves_by_criticality(self, monkeypatch, capsys):
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

    def test_downloads_and_verifies_checksum(self, tmp_path):
        url = self._servir(tmp_path)
        dest = tmp_path / "cache" / "asset.bin"

        resultado = fetch_pinned_asset(url, self.SHA_OK, dest)

        assert resultado == dest
        assert dest.read_bytes() == self.CONTENIDO

    def test_incorrect_checksum_aborts_and_removes_file(self, tmp_path):
        url = self._servir(tmp_path)
        dest = tmp_path / "cache" / "asset.bin"

        with pytest.raises(SystemExit):
            fetch_pinned_asset(url, "0" * 64, dest)
        assert not dest.exists()

    def test_cache_with_valid_checksum_does_not_download(self, tmp_path, monkeypatch):
        dest = tmp_path / "cache" / "asset.bin"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(self.CONTENIDO)

        import urllib.request

        def _red_prohibida(*a, **k):
            raise AssertionError("no debe descargar si la caché tiene el hash pineado")

        monkeypatch.setattr(urllib.request, "urlopen", _red_prohibida)

        resultado = fetch_pinned_asset("https://example.invalid/asset.bin", self.SHA_OK, dest)
        assert resultado == dest


def test_bundle_size_mb_sums_nested_files(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 1024)
    subdir = tmp_path / "sub"
    subdir.mkdir()
    (subdir / "b.bin").write_bytes(b"y" * 1024)

    esperado_mb = (1024 + 1024) / (1024 * 1024)
    assert bundle_size_mb(tmp_path) == pytest.approx(esperado_mb)


def _make_fake_popen(captured, returncode=0, timeout_on_first_wait=False):
    """Fabrica un Popen falso que registra su cmd/kwargs y simula wait()."""
    estado = {"waits": 0}

    class FakePopen:
        def __init__(self, cmd, **kwargs):
            captured.append({"cmd": cmd, "kwargs": kwargs})
            self.pid = 4242

        def wait(self, timeout=None):
            estado["waits"] += 1
            if timeout_on_first_wait and estado["waits"] == 1:
                raise subprocess.TimeoutExpired(cmd="pyinstaller", timeout=timeout)
            return returncode

    return FakePopen


class TestRunPyinstaller:
    """Lanzador común de PyInstaller: reescritura al wrapper COM en Windows,
    paso directo fuera de Windows y kill de árbol en timeout."""

    ARGS = ["/py", "-m", "PyInstaller", "--onedir", "--name", "tts-sidecar"]

    def test_non_win32_passes_args_intact(self, monkeypatch):
        captured = []
        monkeypatch.setattr(build_utils.sys, "platform", "linux")
        monkeypatch.setattr(build_utils.subprocess, "Popen", _make_fake_popen(captured))

        rc = run_pyinstaller(self.ARGS, 1800)

        assert rc == 0
        assert captured[0]["cmd"] == self.ARGS
        # Grupo de procesos propio para poder matar el árbol en timeout.
        assert captured[0]["kwargs"].get("start_new_session") is True

    def test_win32_rewrites_to_wrapper_omitting_prefix(self, monkeypatch):
        captured = []
        monkeypatch.setattr(build_utils.sys, "platform", "win32")
        monkeypatch.setattr(build_utils.subprocess, "Popen", _make_fake_popen(captured))

        rc = run_pyinstaller(self.ARGS, 1800)

        assert rc == 0
        cmd = captured[0]["cmd"]
        assert cmd[0] == build_utils.sys.executable
        assert cmd[1].endswith("pyinstaller_wrapper.py")
        # El prefijo de 3 ([py, -m, PyInstaller]) se omite: solo van los args de PyInstaller.
        assert cmd[2:] == ["--onedir", "--name", "tts-sidecar"]
        assert "PyInstaller" not in cmd[2:]

    def test_timeout_kills_tree_and_returns_1(self, monkeypatch):
        captured = []
        matados = []
        monkeypatch.setattr(build_utils.sys, "platform", "linux")
        monkeypatch.setattr(
            build_utils.subprocess, "Popen",
            _make_fake_popen(captured, timeout_on_first_wait=True),
        )
        monkeypatch.setattr(build_utils, "kill_process_tree", lambda pid: matados.append(pid))

        rc = run_pyinstaller(self.ARGS, 5)

        assert rc == 1
        assert matados == [4242]


def test_installer_timeout_defined():
    """INSTALLER_TIMEOUT existe con el valor holgado para ISCC sobre ~1.6 GB."""
    assert INSTALLER_TIMEOUT == 1800


def test_common_pyinstaller_args_includes_noupx(tmp_path):
    """--noupx debe estar presente para los tres scripts de build (endurecimiento
    contra la heurística de antivirus que penaliza binarios comprimidos con UPX)."""
    args = common_pyinstaller_args(
        entry_point=tmp_path / "entry.py",
        project_root=tmp_path,
        dist_dir=tmp_path / "dist",
        build_dir=tmp_path / "build",
        data_sep=":",
    )
    assert "--noupx" in args


def test_linux_cpu_lock_contains_no_nvidia_packages():
    """N-05: el AppImage x86_64 debe quedar libre del stack CUDA."""
    repo_root = Path(__file__).resolve().parent.parent
    lock_path = repo_root / "requirements-lock-linux-cpu.txt"
    assert lock_path.exists(), "requirements-lock-linux-cpu.txt no existe"

    lineas_nvidia = [
        linea
        for linea in lock_path.read_text(encoding="utf-8").splitlines()
        if linea.lower().startswith("nvidia-")
    ]
    assert not lineas_nvidia, f"paquetes nvidia-* en el lock CPU-only: {lineas_nvidia}"
