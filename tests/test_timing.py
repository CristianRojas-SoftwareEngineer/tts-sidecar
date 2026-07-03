"""Tests para las utilidades de timing.py.

R-05/R-27: todo el flujo de progreso (log, StageTimer, banners de
timed_command) se emite a stderr; stdout queda reservado para datos.
"""

import pytest
import sys
from pathlib import Path
from io import StringIO

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from chatterbox_tts.timing import log, timed_command, timed, StageTimer


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
