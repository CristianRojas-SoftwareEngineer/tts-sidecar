"""
Entry point del daemon de tts-sidecar.

Uso:
    python -m chatterbox_tts.daemon.run
"""

# Supresión de warnings antes de cualquier otro import
import warnings
warnings.filterwarnings("ignore")
import os
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("chatterbox.models.tokenizers.tokenizer").setLevel(logging.ERROR)
logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer").setLevel(logging.ERROR)

# Workaround para Python 3.13+ donde pkg_resources fue eliminado.
# El paquete perth (usado por chatterbox) lo importa en tiempo de import.
# Proveemos un mock mínimo antes de que perth sea importado.
#
# El mock DEBE ser un módulo real con __spec__: cuando este módulo corre en el
# mismo proceso que el entry point del CLI (p.ej. el subcomando congelado
# `daemon serve`), el entry point puede haber instalado el mock antes, y cualquier
# llamada posterior a importlib.util.find_spec('pkg_resources') lanzaría
# "pkg_resources.__spec__ is not set" sobre un objeto bare. El guard
# `not in sys.modules` replica el comportamiento de bin/tts-sidecar para no
# reinstalar el mock si ya está presente.
import sys
import importlib.util
if 'pkg_resources' not in sys.modules and importlib.util.find_spec('pkg_resources') is None:
    import types
    import importlib.machinery
    from pathlib import Path

    def _resource_filename(package, resource):
        spec = importlib.util.find_spec(package)
        if spec and spec.submodule_search_locations:
            return str(Path(spec.submodule_search_locations[0]) / resource)
        return resource

    _mock = types.ModuleType('pkg_resources')
    _mock.resource_filename = _resource_filename
    _mock.__spec__ = importlib.machinery.ModuleSpec('pkg_resources', None)
    sys.modules['pkg_resources'] = _mock

import argparse
import signal
import sys
import time

import uvicorn

from .server import app, set_engine, set_start_time, set_server
from .ipc import DEFAULT_PORT
from ..timing import StageTimer, log


def serve(port: int = DEFAULT_PORT, auto_restart: bool = False, max_retries: int = 0):
    """
    Arranca el servidor del daemon en primer plano (bloqueante).

    Reutilizable tanto por `main()` (modo `python -m chatterbox_tts.daemon.run`)
    como por el subcomando `daemon serve` del ejecutable congelado.
    """
    # Registrar intentos de reinicio
    retries = 0

    def signal_handler(signum, frame):
        log("Daemon: señal de cierre recibida")
        sys.exit(0)

    # Estos handlers solo cubren la ventana entre este registro y el arranque
    # de server.run(): uvicorn.Server instala sus propios manejadores de
    # SIGTERM/SIGINT al iniciar su event loop y, desde ese momento, es su
    # mecanismo (should_exit) el que gobierna el apagado ordenado.
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        set_start_time(time.time())

        with StageTimer("Startup", "Iniciando daemon..."):
            # Etapa 1: cargar modelo
            with StageTimer("1-Daemon", "Etapa 1/3: Cargando modelo"):
                from ..engine import ChatterboxEngine

                # El daemon decide el compute backend una sola vez al
                # arrancar y lo cachea en la instancia del motor: cualquier
                # speak posterior reutiliza esa decisión. TTS_SIDECAR_COMPUTE_BACKEND
                # es el override de bajo nivel; con "auto" (o sin la var),
                # _auto_detect_compute_backend() resuelve cuda → mps → cpu.
                compute_backend = (
                    os.environ.get("TTS_SIDECAR_COMPUTE_BACKEND")
                    or ChatterboxEngine._auto_detect_compute_backend()
                )

                # El engine ya aplica los parámetros de síntesis optimizados,
                # el timing por sub-etapa (_synthesis_timing) y el bypass del
                # watermark como comportamiento propio.
                engine = ChatterboxEngine.get_instance(
                    model="es-mx-latam",
                    compute_backend=compute_backend,
                )

                log(f"Daemon: compute_backend={compute_backend}")
                set_engine(engine)

            # Etapa 2: iniciar servidor
            with StageTimer("2-Daemon", "Etapa 2/3: Iniciando servidor"):
                log(f"Daemon listo en http://127.0.0.1:{port}")

            # Etapa 3: startup completo
            # El with vacío cierra el StageTimer de "Startup" total; el log de
            # duración acumulada se imprime al salir del bloque exterior.
            with StageTimer("3-Daemon", "Etapa 3/3: Startup completo"):
                pass

        if auto_restart and max_retries > 0 and retries >= max_retries:
            log(f"Daemon: máximo de intentos alcanzado ({max_retries}). Saliendo.")
            break

        try:
            # Instancia explícita de Server (en lugar de uvicorn.run) para que el
            # endpoint /shutdown pueda señalizar should_exit y cerrar de forma ordenada.
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="info",
                access_log=False,
            )
            server = uvicorn.Server(config)
            set_server(server)
            server.run()
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Daemon: error: {e}")

        if not auto_restart:
            break

        retries += 1
        log(f"Daemon: reiniciando (intento {retries})...")

        # Invalida la instancia cacheada para forzar una recarga real del
        # motor: si el crash se debió a un estado interno corrupto, revivir
        # el mismo objeto anularía el propósito de --auto-restart.
        from ..engine import ChatterboxEngine
        ChatterboxEngine._cache.pop(
            ChatterboxEngine.cache_key(model="es-mx-latam", compute_backend=compute_backend),
            None,
        )

        time.sleep(1)

    log("Daemon: detenido")


def main():
    """
    Punto de entrada CLI del daemon.

    Parsea argumentos y delega en serve(). Se invoca como:
        python -m chatterbox_tts.daemon.run [--auto-restart] [--max-retries N]

    El puerto es fijo (DEFAULT_PORT = 8765 en loopback); no hay flag --port.
    """
    parser = argparse.ArgumentParser(description="tts-sidecar daemon")
    parser.add_argument(
        "--auto-restart",
        action="store_true",
        help="Reiniciar automáticamente tras un crash"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Máximo de intentos de reinicio (0 = infinito)"
    )
    args = parser.parse_args()

    serve(
        auto_restart=args.auto_restart,
        max_retries=args.max_retries,
    )


if __name__ == "__main__":
    main()
