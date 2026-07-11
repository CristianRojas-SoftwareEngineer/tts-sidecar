"""Tests del generador puro del Cask de Homebrew (scripts/render_cask.py).

Patrón de tests/test_build_windows.py: sin I/O de red, monkeypatch/fixtures
puras. Dado un CIRCLE_TAG y un SHA256SUMS.txt de ejemplo, verifica que las
stanzas version/sha256/url del Cask se reescriben correctamente.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from render_cask import parse_dmg_sha256, render_cask, render_cask_from_tag

def _sha(label: str) -> str:
    import hashlib
    return hashlib.sha256(label.encode()).hexdigest()


DMG_SHA = _sha("dmg")

SAMPLE_SUMS = f"""\
{_sha("exe")}  tts-sidecar-1.2.3-x86_64-setup.exe
{_sha("appimage-x86_64")}  tts-sidecar-1.2.3-x86_64.AppImage
{_sha("appimage-aarch64")}  tts-sidecar-1.2.3-aarch64.AppImage
{DMG_SHA}  tts-sidecar-1.2.3-arm64.dmg
"""


class TestParseDmgSha256:
    def test_extracts_hash_of_matching_dmg(self):
        assert parse_dmg_sha256(SAMPLE_SUMS, "1.2.3") == DMG_SHA

    def test_missing_version_raises(self):
        with pytest.raises(ValueError):
            parse_dmg_sha256(SAMPLE_SUMS, "9.9.9")

    def test_does_not_match_other_artifacts(self):
        # No debe confundirse con el .exe o los .AppImage de la misma versión.
        resultado = parse_dmg_sha256(SAMPLE_SUMS, "1.2.3")
        assert resultado != _sha("exe")
        assert resultado != _sha("appimage-x86_64")


class TestRenderCask:
    def test_stanzas_reflect_version_and_sha256(self):
        contenido = render_cask("1.2.3", DMG_SHA)
        assert 'version "1.2.3"' in contenido
        assert f'sha256 "{DMG_SHA}"' in contenido
        assert "tts-sidecar-#{version}-arm64.dmg" in contenido
        assert 'cask "tts-sidecar" do' in contenido

    def test_url_points_to_versioned_tag(self):
        contenido = render_cask("1.2.3", DMG_SHA)
        assert "releases/download/v#{version}/" in contenido

    def test_zap_trash_present_for_clean_uninstall(self):
        contenido = render_cask("1.2.3", DMG_SHA)
        assert "zap trash:" in contenido

    def test_zap_trash_lists_both_model_repos(self):
        # La desinstalación con residuo cero requiere borrar los dos repos que
        # `setup` descarga: el modelo multilingüe y el repo base `chatterbox`
        # (Voice Encoder, ve.safetensors).
        contenido = render_cask("1.2.3", DMG_SHA)
        assert (
            "~/.cache/huggingface/hub/models--ResembleAI--Chatterbox-Multilingual-es-mx-latam"
            in contenido
        )
        assert "~/.cache/huggingface/hub/models--ResembleAI--chatterbox" in contenido

    def test_caveats_suggest_setup(self):
        contenido = render_cask("1.2.3", DMG_SHA)
        assert "tts-sidecar setup" in contenido


class TestRenderCaskFromTag:
    def test_strips_leading_v_from_tag(self):
        contenido = render_cask_from_tag("v1.2.3", SAMPLE_SUMS)
        assert 'version "1.2.3"' in contenido
        assert f'sha256 "{DMG_SHA}"' in contenido

    def test_regenerating_from_same_inputs_is_idempotent(self):
        first = render_cask_from_tag("v1.2.3", SAMPLE_SUMS)
        second = render_cask_from_tag("v1.2.3", SAMPLE_SUMS)
        assert first == second
