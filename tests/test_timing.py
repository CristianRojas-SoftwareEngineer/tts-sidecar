"""Tests para las utilidades de timing.py.

R-05/R-27: todo el flujo de progreso (log, StageTimer, banners de
timed_command) se emite a stderr; stdout queda reservado para datos.
"""

import pytest
import sys
import time
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from tts_sidecar import timing
from tts_sidecar.timing import (
    log, timed_command, timed, StageTimer, Spinner, format_progress_event,
)


class TestFormatProgressEvent:
    def test_t3_con_tokens(self):
        assert format_progress_event(
            {"event": "progress", "stage": "t3", "tokens": 210}
        ) == "Generando voz · 210 tokens"

    def test_t3_sin_tokens(self):
        assert format_progress_event({"event": "progress", "stage": "t3"}) == "Generando voz…"

    def test_etapas_conocidas(self):
        assert format_progress_event({"stage": "conditionals"}) == "Preparando la voz…"
        assert format_progress_event({"stage": "s3gen"}).startswith("Sintetizando audio")
        assert format_progress_event({"stage": "encoding"}) == "Codificando audio…"
        assert format_progress_event({"stage": "saving"}) == "Guardando…"

    def test_etapa_desconocida_cae_al_default(self):
        assert format_progress_event({"stage": "otra"}) == "Sintetizando…"
        assert format_progress_event({}) == "Sintetizando…"


class FakeTTY(StringIO):
    """Stream de texto en memoria que se hace pasar por terminal interactiva."""

    def __init__(self, encoding="utf-8"):
        super().__init__()
        self._encoding = encoding

    def isatty(self):
        return True

    @property
    def encoding(self):
        return self._encoding


class TestLog:
    def test_log_without_duration(self, capsys):
        log("test message")
        captured = capsys.readouterr()
        assert "test message..." in captured.err
        assert captured.out == ""

    def test_log_with_duration(self, capsys):
        log("test operation", duration=1.5)
        captured = capsys.readouterr()
        assert "test operation" in captured.err
        assert "Done (1.5s)" in captured.err
        assert captured.out == ""


class TestTimedCommand:
    def test_timed_command_start_finish(self, capsys):
        @timed_command
        def dummy_cmd(args):
            print("inside command")
            return 42

        class Args:
            pass

        result = dummy_cmd(Args())
        captured = capsys.readouterr()
        assert "Starting dummy_cmd..." in captured.err
        assert "Finished in" in captured.err
        # Los datos del comando siguen yendo a stdout
        assert "inside command" in captured.out
        assert result == 42

    def test_timed_command_error(self, capsys):
        @timed_command
        def failing_cmd(args):
            raise ValueError("test error")

        class Args:
            pass

        with pytest.raises(ValueError):
            failing_cmd(Args())
        captured = capsys.readouterr()
        assert "Failed after" in captured.err
        assert "test error" in captured.err
        assert captured.out == ""


class TestTimedDecorator:
    def test_timed_decorator(self, capsys):
        @timed("MyStage")
        def some_work():
            print("working")

        some_work()
        captured = capsys.readouterr()
        assert "[MyStage]" in captured.err
        assert "working" in captured.out


class TestStageTimer:
    def test_stage_timer_entry_exit(self, capsys):
        with StageTimer("TestStage", "doing work"):
            print("inside stage")
        captured = capsys.readouterr()
        assert "[TestStage] doing work..." in captured.err
        assert "Done (" in captured.err
        assert "inside stage" in captured.out

    def test_stage_timer_no_description(self, capsys):
        with StageTimer("X"):
            pass
        assert "[X] X..." in capsys.readouterr().err

    def test_stage_timer_exception(self, capsys):
        with pytest.raises(RuntimeError):
            with StageTimer("Fail"):
                raise RuntimeError("boom")
        # Debe registrar el fin de la etapa incluso cuando hay excepción
        assert "[Fail]" in capsys.readouterr().err


class TestSpinner:
    def test_noop_when_not_tty(self, capsys):
        # stderr bajo capsys no es TTY: el spinner debe ser un no-op total.
        with Spinner("trabajando") as sp:
            assert sp._enabled is False
            time.sleep(0.05)
        captured = capsys.readouterr()
        assert captured.out == ""
        # No deja el global activo ni caracteres de control tras de sí.
        assert timing._active_spinner is None

    def test_update_headless_does_not_fail(self):
        with Spinner("a") as sp:
            sp.update("b")  # no debe lanzar aunque esté deshabilitado
        assert True

    def test_active_writes_only_to_its_stream(self):
        stream = FakeTTY()
        with Spinner("sintetizando", stream=stream) as sp:
            assert sp._enabled is True
            assert timing._active_spinner is sp
            time.sleep(0.25)  # al menos un par de frames
        # Escribió frames a su stream; nunca a stdout real.
        out = stream.getvalue()
        assert "sintetizando" in out
        assert "\r" in out  # redibujado en el sitio
        # Tras salir, el global queda limpio.
        assert timing._active_spinner is None

    def test_ascii_fallback_for_non_utf8(self):
        stream = FakeTTY(encoding="cp1252")
        sp = Spinner("x", stream=stream)
        # Sin UTF-8 usa frames ASCII, no braille.
        assert sp._frames == Spinner._FRAMES_ASCII

    def test_utf8_uses_braille(self):
        sp = Spinner("x", stream=FakeTTY(encoding="utf-8"))
        assert sp._frames == Spinner._FRAMES_UNICODE

    def test_log_coordinates_with_active_spinner(self):
        stream = FakeTTY()
        with Spinner("trabajo", stream=stream):
            log("evento intermedio")
        out = stream.getvalue()
        # La línea de log se intercaló en el mismo stream del spinner.
        assert "evento intermedio" in out

    def test_render_reflects_update(self):
        sp = Spinner("inicial", stream=FakeTTY())
        sp._start = time.time()
        assert "inicial" in sp._render(sp._frames[0])
        sp.update("nuevo")
        assert "nuevo" in sp._render(sp._frames[0])

    def test_exception_cleans_up_global(self, capsys):
        stream = FakeTTY()
        with pytest.raises(RuntimeError):
            with Spinner("x", stream=stream):
                raise RuntimeError("boom")
        # No debe tragar la excepción ni dejar el spinner registrado.
        assert timing._active_spinner is None
