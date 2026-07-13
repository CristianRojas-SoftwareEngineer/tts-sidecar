#!/usr/bin/env python3
"""
Lanzador de PyInstaller para Windows que evita el cuelgue COM del análisis.

Durante el análisis, PyInstaller importa pycaw -> comtypes (por `--collect-all
pycaw`). comtypes inicializa COM en modo apartment (STA) y, al terminar el
intérprete, `CoUninitialize()` bloquea el shutdown en el runner headless
`win/server-2022`: el proceso imprime «Build complete!» y nunca sale, dejando un
zombie que retiene el pipe stdout de CircleCI y cuelga el job entero.

El fix tiene dos partes, ambas imprescindibles:

1. `sys.coinit_flags = 0x8` (COINIT_MULTITHREADED) debe estar seteado en el
   proceso que realmente importa comtypes, ANTES de cualquier import. Es una
   variable del módulo `sys`, no una variable de entorno: no se hereda a
   subprocesos, así que hay que setearla dentro del propio proceso de análisis.
   Por eso se genera un bootstrap temporal cuya PRIMERA sentencia la fija, y ese
   bootstrap es quien invoca a PyInstaller.

2. Tanto el bootstrap como este lanzador terminan con `os._exit()`, que salta
   el cleanup de atexit (donde vive el `CoUninitialize()` que bloquea).

Los pipes se heredan sin redirección: el output natural de PyInstaller hace de
heartbeat para CircleCI, sin instrumentación adicional.
"""

import os
import subprocess
import sys
import tempfile

# Valor de sys.coinit_flags para inicializar COM en modo apartment libre
# (multithreaded): evita el CoUninitialize() bloqueante de atexit descrito
# arriba. Ver la constante homónima en pywin32/comtypes.constants.
COINIT_MULTITHREADED = 0x8

# El bootstrap se ejecuta como proceso hijo: fija coinit_flags antes de importar
# nada de PyInstaller (que arrastra pycaw -> comtypes) y sale con os._exit para
# saltarse el CoUninitialize() de atexit que cuelga el shutdown.
_BOOTSTRAP = f"""\
import sys
sys.coinit_flags = {COINIT_MULTITHREADED}  # COINIT_MULTITHREADED: antes de cualquier import de comtypes
import os
try:
    from PyInstaller.__main__ import run
    run()
except SystemExit as exc:
    os._exit(exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1))
os._exit(0)
"""


def main() -> None:
    """Ejecuta PyInstaller vía bootstrap temporal y propaga el exit code real."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        tmp_path = f.name
        f.write(_BOOTSTRAP)

    try:
        proc = subprocess.Popen([sys.executable, tmp_path, *sys.argv[1:]])
        proc.wait()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    os._exit(proc.returncode)


if __name__ == "__main__":
    main()
