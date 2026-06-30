"""
Entry point for tts-sidecar daemon.

Usage:
    python -m chatterbox_tts.daemon.run --port 8765
"""

# Suppress warnings before any other imports
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

# Workaround for Python 3.13+ where pkg_resources was removed.
# The perth package (used by chatterbox) imports pkg_resources at import time.
# We provide a minimal mock before perth is imported.
import importlib.util
if importlib.util.find_spec('pkg_resources') is None:
    class _MockPkgResources:
        @staticmethod
        def resource_filename(package, resource):
            from pathlib import Path
            spec = importlib.util.find_spec(package)
            if spec and spec.submodule_search_locations:
                return str(Path(spec.submodule_search_locations[0]) / resource)
            return resource
    import sys
    sys.modules['pkg_resources'] = _MockPkgResources()

import argparse
import signal
import sys
import time

import uvicorn

from .server import app, set_engine, set_start_time
from ..timing import StageTimer, log


def serve(port: int = 8765, auto_restart: bool = False, max_retries: int = 0):
    """
    Arrancar el servidor del daemon en primer plano (bloqueante).

    Reutilizable tanto por `main()` (modo `python -m chatterbox_tts.daemon.run`)
    como por el subcomando `daemon serve` del ejecutable congelado.
    """
    # Track restarts
    retries = 0

    def signal_handler(signum, frame):
        log("Daemon: Received shutdown signal")
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    while True:
        set_start_time(time.time())

        with StageTimer("Startup", "Starting daemon..."):
            # Stage 1: Load model
            with StageTimer("1-Daemon", "Stage 1/3: Loading model"):
                from ..engine import ChatterboxEngine

                engine = ChatterboxEngine.get_instance(
                    model="es-latam",
                    device="cpu",
                )

                # Override generate() defaults for faster synthesis
                _patch_generate_defaults(engine)
                _patch_log_timing(engine)
                _patch_skip_watermark(engine)

                set_engine(engine)

            # Stage 2: Server startup
            with StageTimer("2-Daemon", "Stage 2/3: Starting server"):
                log(f"Daemon ready on http://127.0.0.1:{port}")

            # Stage 3: Startup complete
            with StageTimer("3-Daemon", "Stage 3/3: Startup complete"):
                pass

        if auto_restart and max_retries > 0 and retries >= max_retries:
            log(f"Daemon: Max retries ({max_retries}) reached. Exiting.")
            break

        try:
            uvicorn.run(
                app,
                host="127.0.0.1",
                port=port,
                log_level="info",
                access_log=False,
            )
        except KeyboardInterrupt:
            break
        except Exception as e:
            log(f"Daemon: Error: {e}")

        if not auto_restart:
            break

        retries += 1
        log(f"Daemon: Restarting daemon (attempt {retries})...")
        time.sleep(1)

    log("Daemon: Stopped")


def main():
    parser = argparse.ArgumentParser(description="tts-sidecar daemon")
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="TCP port to listen on (default: 8765)"
    )
    parser.add_argument(
        "--auto-restart",
        action="store_true",
        help="Auto-restart on crash"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=0,
        help="Max restart attempts (0 = infinite)"
    )
    args = parser.parse_args()

    serve(
        port=args.port,
        auto_restart=args.auto_restart,
        max_retries=args.max_retries,
    )


def _patch_generate_defaults(engine):
    """
    Patch generate() to set exaggeration default.

    exaggeration=0.75: emotional expressiveness (default=0.5).
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
    Add sub-stage timing logs for Stage 2 (TTS generation) and set
    optimal synthesis parameters.

    Applies:
    - max_new_tokens=500: caps T3 output (default is 1000)
    - n_cfm_timesteps=4: flow matching steps (default is 10, 4 is ~2.5x faster)

    Timing is stored in engine._synthesis_timing for HTTP header exposure.
    Logs: [Stage 2a] T3 autoregresivo, [Stage 2b] S3Gen vocoder.
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
    Skip the PerthImplicitWatermarker step after generation.

    The watermarker runs a second neural network (PerthNet encoder) on the
    generated audio, adding significant post-processing time. Since this is
    a local/offline use case, we bypass it entirely by replacing
    apply_watermark with a no-op that returns the audio unchanged.
    """
    _orig_apply = engine._tts.watermarker.apply_watermark

    def noop_watermark(wav, sample_rate, **kwargs):
        return wav

    engine._tts.watermarker.apply_watermark = noop_watermark


if __name__ == "__main__":
    main()
