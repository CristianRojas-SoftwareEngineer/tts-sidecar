"""
Entry point del daemon de tts-sidecar.

Uso:
    python -m chatterbox_tts.daemon.run --port 8765
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
from ..timing import StageTimer, log


def serve(port: int = 8765, auto_restart: bool = False, max_retries: int = 0):
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

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        set_start_time(time.time())

        with StageTimer("Startup", "Iniciando daemon..."):
            # Etapa 1: cargar modelo
            with StageTimer("1-Daemon", "Etapa 1/3: Cargando modelo"):
                from ..engine import ChatterboxEngine

                engine = ChatterboxEngine.get_instance(
                    model="es-mx-latam",
                    device="cpu",
                )

                # Parches de optimización para síntesis más rápida
                _patch_generate_defaults(engine)
                _patch_log_timing(engine)
                _patch_skip_watermark(engine)

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
        time.sleep(1)

    log("Daemon: detenido")


def main():
    """
    Punto de entrada CLI del daemon.

    Parsea argumentos y delega en serve(). Se invoca como:
        python -m chatterbox_tts.daemon.run [--port N] [--auto-restart] [--max-retries N]
    """
    parser = argparse.ArgumentParser(description="tts-sidecar daemon")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Puerto TCP en el que escuchar (default: 8765)"
    )
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
        port=args.port,
        auto_restart=args.auto_restart,
        max_retries=args.max_retries,
    )


def _patch_generate_defaults(engine):
    """
    Parcha generate() para establecer el valor por defecto de exaggeration.

    exaggeration=0.75: expresividad emocional (default del modelo: 0.5).
    """
    import functools

    _orig_generate = engine._tts.generate

    @functools.wraps(_orig_generate)
    def patched_generate(*args, **kwargs):
        kwargs.setdefault('exaggeration', 0.75)
        return _orig_generate(*args, **kwargs)

    engine._tts.generate = patched_generate


def _patch_log_timing(engine):
    """
    Añade logs de tiempo por sub-etapa para la Etapa 2 (generación TTS) y
    aplica parámetros de síntesis óptimos mediante asignación directa en los kwargs:

    - max_new_tokens=500: limita el output del T3 (default: 1000)
    - n_cfm_timesteps=4: pasos de flow matching (default: 10, 4 es ~2.5x más rápido)

    El timing se almacena en engine._synthesis_timing para exponerlo en
    los headers HTTP. Logs: [Stage 2a] T3 autoregresivo, [Stage 2b] S3Gen vocoder.
    """
    import functools
    import time as time_mod

    engine._synthesis_timing = {'t3': 0.0, 's3gen': 0.0}

    _orig_t3 = engine._tts.t3.inference

    @functools.wraps(_orig_t3)
    def timed_t3(*args, **kwargs):
        kwargs['max_new_tokens'] = 500
        t0 = time_mod.time()
        result = _orig_t3(*args, **kwargs)
        engine._synthesis_timing['t3'] = time_mod.time() - t0
        log(f"   [Stage 2a] T3 autoregresivo: {engine._synthesis_timing['t3']:.1f}s")
        return result

    engine._tts.t3.inference = timed_t3

    _orig_s3gen = engine._tts.s3gen.inference

    @functools.wraps(_orig_s3gen)
    def timed_s3gen(*args, **kwargs):
        kwargs['n_cfm_timesteps'] = 4
        t0 = time_mod.time()
        result = _orig_s3gen(*args, **kwargs)
        engine._synthesis_timing['s3gen'] = time_mod.time() - t0
        log(f"   [Stage 2b] S3Gen vocoder:   {engine._synthesis_timing['s3gen']:.1f}s")
        return result

    engine._tts.s3gen.inference = timed_s3gen


def _patch_skip_watermark(engine):
    """
    Omite el paso PerthImplicitWatermarker tras la generación de audio.

    El watermarker ejecuta una segunda red neuronal (PerthNet encoder) sobre el
    audio generado, añadiendo tiempo de post-procesado significativo. En este
    caso de uso local/offline lo bypaseamos reemplazando apply_watermark con
    un no-op que devuelve el audio sin modificar.
    """
    def noop_watermark(wav, sample_rate, **kwargs):
        return wav

    engine._tts.watermarker.apply_watermark = noop_watermark


if __name__ == "__main__":
    main()
