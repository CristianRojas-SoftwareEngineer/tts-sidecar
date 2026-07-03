"""
Utilidades de temporización compartidas para tts-sidecar.

Todo el flujo de progreso e instrumentación (log, StageTimer, los banners de
timed_command) se emite a **stderr**: stdout queda reservado para datos
(salidas --json, listados, confirmaciones de resultado), cumpliendo el contrato
de salida del CLI.
"""

import sys
import time
from datetime import datetime
from functools import wraps
from typing import Optional


def log(msg: str, duration: Optional[float] = None):
    """Imprime un mensaje de log con formato consistente (a stderr).

    Sin duration: [HH:MM:SS] Mensaje...
    Con duration: [HH:MM:SS] Mensaje -> Done (Xs)
    """
    now = datetime.now().strftime("%H:%M:%S")
    if duration is not None:
        print(f"[{now}] {msg} -> Done ({duration:.1f}s)", file=sys.stderr)
    else:
        print(f"[{now}] {msg}...", file=sys.stderr)


def timed_command(func):
    """Decorador que añade información de tiempo a funciones de comando CLI.

    Registra el inicio y el fin del comando (a stderr). Los timestamps los
    maneja StageTimer/log para evitar duplicación.
    """
    @wraps(func)
    def wrapper(args):
        start_time = time.time()
        print(f"Starting {func.__name__.replace('cmd_', '')}...", file=sys.stderr)
        try:
            result = func(args)
            elapsed = time.time() - start_time
            print(f"Finished in {elapsed:.1f}s", file=sys.stderr)
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"Failed after {elapsed:.1f}s: {e}", file=sys.stderr)
            raise
    return wrapper


def timed(stage_name: str):
    """Decorador que registra el tiempo de ejecución de una función como etapa.

    Usa log() para imprimir la duración al terminar la función.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            duration = time.time() - start
            log(f"[{stage_name}]", duration)
            return result
        return wrapper
    return decorator


class StageTimer:
    """Context manager para temporizar un bloque de código.

    Imprime el inicio con log() al entrar y la duración al salir.

    Uso:
        with StageTimer("MiEtapa", "Descripción"):
            # código a temporizar
    """

    def __init__(self, name: str, description: str = None):
        self.name = name
        self.description = description or name
        self.start = None

    def __enter__(self):
        self.start = time.time()
        log(f"[{self.name}] {self.description}...")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start
        log(f"[{self.name}]", duration)
        return False
