"""
CLI interface for Chatterbox TTS.
Consumable from any programming language via subprocess.

Output contract (stable across OS and languages):
  - Data goes to stdout; diagnostics and errors go to stderr.
  - Read commands (voice list, devices, version, daemon status, doctor) accept
    --json for machine-readable output.
  - Exit codes: 0 = success; non-zero = error (doctor returns 1 when a check fails).
  - stdout/stderr are forced to UTF-8 for consistent encoding on every platform.
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import argparse
import sys
import os
import platform
from pathlib import Path

from .timing import timed_command, StageTimer, log

# Lazy imports - only loaded when commands are executed
# This allows --help to work without dependencies installed


def _resolve_voice_paths(args):
    """Resolve voice audio paths from voice name WITHOUT loading the model."""
    from . import voices

    voice_audio = getattr(args, 'voice_audio', None)
    speech_audio = getattr(args, 'speech_audio', None)

    if getattr(args, 'voice', None):
        # Resolve from filesystem directly - no model needed
        voice_audio, speech_audio = voices.voice_paths(args.voice)

    return voice_audio, speech_audio


def _emit_audio(audio_bytes, output):
    """Play audio bytes, or write them to a file when an output path is given."""
    if output:
        with open(output, 'wb') as f:
            f.write(audio_bytes)
        log(f"[I/O] Audio guardado: {output}")
    else:
        log("[Playback] Reproduciendo audio...")
        from .audio import AudioPlayer
        player = AudioPlayer()
        player.play(audio_bytes)
        log("[Playback] Reproducción finalizada")


def _synthesize_via_daemon(args, voice_audio, speech_audio):
    """Try to synthesize via daemon, return True if successful.

    Plays the audio or writes it to a file depending on args.output.
    """
    import time
    import traceback

    try:
        from .daemon import DaemonIPCClient, is_daemon_running
        if not is_daemon_running():
            log("[Daemon] Daemon no está corriendo")
            return False

        synth_start = time.time()
        log("[Daemon] Enviando solicitud de síntesis...")
        client = DaemonIPCClient()
        audio_bytes = client.synthesize(
            text=args.text,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
            model=args.model,
            device=args.device,
            compile_mode=getattr(args, 'compile', None),
        )
        elapsed = time.time() - synth_start
        log(f"[Daemon] Síntesis completada ({elapsed:.1f}s)")

        _emit_audio(audio_bytes, args.output)
        return True
    except Exception as e:
        log(f"[Daemon] Error: {e}")
        traceback.print_exc()
        return False


@timed_command
def cmd_speak(args):
    """Synthesize text; play the audio, or save it to a file when --output is given."""

    try:
        # Resolve voice audio paths WITHOUT loading model
        voice_audio, speech_audio = _resolve_voice_paths(args)

        # Try daemon if --daemon flag is set (default: try if available)
        use_daemon = getattr(args, 'daemon', False) or os.getenv('TTS_DAEMON_AUTOSTART')
        no_daemon = getattr(args, 'no_daemon', False)

        if use_daemon and not no_daemon:
            if _synthesize_via_daemon(args, voice_audio, speech_audio):
                return

        # Use direct mode - imports only loaded when daemon not used
        from .engine import ChatterboxEngine

        compile_mode = getattr(args, 'compile', None)
        engine = ChatterboxEngine.get_instance(model=args.model, device=args.device, compile_mode=compile_mode)

        audio_bytes = engine.speak(
            text=args.text,
            output_path=args.output,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
        )

        if args.output:
            # engine.speak already wrote the file via output_path
            print(f"Audio saved to: {args.output}")
        else:
            log("[Playback] Reproduciendo audio...")
            from .audio import AudioPlayer
            player = AudioPlayer()
            player.play(audio_bytes)
            log("[Playback] Reproducción finalizada")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'tts-sidecar install' first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_add(args):
    """Add a voice clone from reference audio."""
    try:
        from .engine import ChatterboxEngine

        engine = ChatterboxEngine(device=args.device)
        ref_path, speech_path = engine.add_voice(
            name=args.name,
            reference_audio=args.reference,
            speech_audio=args.speech,
        )
        print(f"Voice '{args.name}' registered:")
        print(f"  timbre (reference): {ref_path}")
        print(f"  speech (conditioning): {speech_path}")

    except Exception as e:
        print(f"Error adding voice: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_remove(args):
    """Remove a registered voice."""
    from . import voices

    try:
        if voices.remove_voice(args.name):
            print(f"Voice '{args.name}' removed.")
        else:
            print(f"Voice '{args.name}' not found.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Error removing voice: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_voice_list(args):
    """List all registered voices."""
    from . import voices

    try:
        voice_list = voices.list_voices()

        if getattr(args, "json", False):
            import json
            print(json.dumps({"voices": voice_list}))
            return

        if voice_list:
            print("Registered voices:")
            for voice in voice_list:
                print(f"  - {voice}")
        else:
            print("No voices registered. Run:")
            print("  tts-sidecar voice add --name myvoice --reference timbre.wav --speech speech.wav")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Run 'tts-sidecar install' first.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error listing voices: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_devices(args):
    """List audio output devices."""
    from .audio import get_audio_devices

    devices = get_audio_devices()

    if getattr(args, "json", False):
        import json
        print(json.dumps({"devices": devices}))
        return

    print("Audio output devices:")
    for dev in devices:
        print(f"  [{dev['id']}] {dev['name']} (latency: {dev['latency']*1000:.1f}ms)")


def cmd_version(args):
    """Show the tts-sidecar version."""
    from . import __version__

    if getattr(args, "json", False):
        import json
        print(json.dumps({"name": "tts-sidecar", "version": __version__}))
    else:
        print(f"tts-sidecar {__version__}")


def cmd_doctor(args):
    """Run diagnostic checks."""
    from . import voices

    checks = []  # list of (status, name, detail) with status in PASS/FAIL/SKIP

    # Check Chatterbox
    try:
        import chatterbox
        checks.append(("PASS", "Chatterbox TTS", chatterbox.__version__))
    except ImportError:
        checks.append(("FAIL", "Chatterbox TTS", "NOT INSTALLED (pip install chatterbox-tts)"))

    # Check audio library
    try:
        if platform.system() == "Windows":
            import pycaw
            checks.append(("PASS", "Audio library", "pycaw (Windows)"))
        elif platform.system() == "Linux":
            import sounddevice
            checks.append(("PASS", "Audio library", "sounddevice (Linux)"))
        elif platform.system() == "Darwin":
            import subprocess
            subprocess.run(["afplay"], check=True, capture_output=True)
            checks.append(("PASS", "Audio library", "afplay (macOS)"))
    except ImportError:
        checks.append(("FAIL", "Audio library", "NOT INSTALLED"))
    except Exception as e:
        checks.append(("FAIL", "Audio library", str(e)))

    # Check model - verify Chatterbox can load (uses HF cache)
    try:
        from chatterbox.tts import ChatterboxTTS
        ChatterboxTTS.from_pretrained(device="cpu")
        checks.append(("PASS", "Chatterbox model", "loaded from cache"))
    except Exception as e:
        checks.append(("FAIL", "Chatterbox model", f"{e} (run: tts-sidecar install)"))

    # Check voices directory (single source of truth)
    voices_path = voices.voices_root()
    if os.path.exists(voices_path):
        count = len(voices.list_voices())
        checks.append(("PASS", "Voices directory", f"{count} voice(s) registered"))
    else:
        checks.append(("SKIP", "Voices directory", "not created yet (optional)"))

    checks_failed = sum(1 for status, _, _ in checks if status == "FAIL")
    checks_passed = len(checks) - checks_failed

    if getattr(args, "json", False):
        import json
        print(json.dumps({
            "python": sys.version,
            "platform": f"{platform.system()} {platform.release()}",
            "checks": [{"status": s, "name": n, "detail": d} for s, n, d in checks],
            "passed": checks_passed,
            "failed": checks_failed,
        }))
        if checks_failed > 0:
            sys.exit(1)
        return

    print("=== Chatterbox TTS Doctor ===\n")
    print(f"Python: {sys.version}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print()
    for status, name, detail in checks:
        print(f"[{status}] {name}: {detail}")
    print()
    print(f"Checks: {checks_passed} passed, {checks_failed} failed")

    if checks_failed > 0:
        sys.exit(1)


def cmd_install(args):
    """Download and install the Chatterbox model."""
    print("=== Chatterbox TTS Installer ===\n")

    # El modelo se descarga a la caché de HuggingFace (ver engine._download_model),
    # estable tanto desde fuente como en el ejecutable onefile.
    model_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

    print(f"Installing to: {model_dir}\n")

    try:
        from chatterbox.tts import ChatterboxTTS
        print("Downloading Chatterbox Multilingual V3 model...")
        print("(This may take several minutes on first run)\n")

        tts = ChatterboxTTS.from_pretrained(device="cpu")

        print("\n[PASS] Model downloaded successfully!")
        print(f"  Location: {model_dir}")

    except Exception as e:
        print(f"[FAIL] Installation failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_daemon(args):
    """Manage the tts-sidecar daemon."""
    if args.action == "serve":
        # Foreground server. Used by the frozen executable to self-invoke the
        # daemon (the .exe cannot run `python -m ...`).
        from .daemon.run import serve
        serve(
            port=args.port,
            auto_restart=getattr(args, "auto_restart", False),
            max_retries=getattr(args, "max_retries", 0) or 0,
        )
        return

    from .daemon import DaemonManager

    manager = DaemonManager()

    if args.action == "start":
        success = manager.start(
            background=True,
            auto_restart=args.autorestart,
            max_retries=args.max_retries or 0,
        )
        if success:
            print("Daemon started successfully")
        else:
            print("Failed to start daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "stop":
        if manager.stop():
            print("Daemon stopped")
        else:
            print("Failed to stop daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "restart":
        if manager.restart():
            print("Daemon restarted")
        else:
            print("Failed to restart daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "status":
        status = manager.status()

        if getattr(args, "json", False):
            import json
            print(json.dumps(status))
            return

        if status.get("running"):
            print(f"Daemon running:")
            print(f"  Status: {status.get('status', 'unknown')}")
            print(f"  Model loaded: {status.get('model_loaded', False)}")
            print(f"  Uptime: {status.get('uptime_seconds', 0):.1f}s")
        else:
            print("Daemon not running")


def main():
    """Main CLI entry point."""
    # Force UTF-8 output for consistent encoding across Windows/Linux/macOS.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="tts-sidecar",
        description="Chatterbox TTS - 100% local voice cloning TTS"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # speak command (unified: plays audio, or saves to file when --output is given)
    speak_parser = subparsers.add_parser("speak", help="Synthesize speech; play it, or save with --output")
    speak_parser.add_argument("--text", "-t", required=True, help="Text to synthesize")
    speak_parser.add_argument("--voice", "-v", help="Voice name to use (auto-loads reference.wav + speech.wav)")
    speak_parser.add_argument("--output", "-o", help="Output WAV file path (if omitted, audio is played)")
    speak_parser.add_argument("--device", "-d", default="cpu",
                              choices=["cpu", "cuda", "mps"],
                              help="Device for inference (default: cpu)")
    speak_parser.add_argument("--model", "-m", default="es-latam",
                              choices=["multilingual", "es-latam"],
                              help="Model to use: 'es-latam' (LatAm Spanish, RECOMMENDED) or 'multilingual' (default: es-latam)")
    speak_parser.add_argument("--voice-audio",
                              help="Audio file for Voice Encoder (full audio for timbre embedding)")
    speak_parser.add_argument("--speech-audio",
                              help="Audio file for T3 conditioning (6s) + S3Gen decoder (10s). "
                                   "Use a clean speech segment (10s+ recommended).")
    speak_parser.add_argument("--compile", "-c", nargs="?", const="default",
                              choices=["default", "reduce-overhead", "max-autotune"],
                              help="Enable torch.compile for faster CPU inference. "
                                   "Modes: default, reduce-overhead, max-autotune. "
                                   "Default mode is 'default' if flag is present without a value.")
    speak_parser.add_argument("--daemon", action="store_true",
                              help="Use daemon if available (default: auto)")
    speak_parser.add_argument("--no-daemon", action="store_true",
                              help="Force direct mode, ignore daemon")
    speak_parser.set_defaults(func=cmd_speak)

    # voice command group (list / add / remove)
    voice_parser = subparsers.add_parser("voice", help="Manage registered voices")
    voice_subparsers = voice_parser.add_subparsers(dest="action", help="Voice actions")

    voice_list = voice_subparsers.add_parser("list", help="List registered voices")
    voice_list.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    voice_list.set_defaults(func=cmd_voice_list)

    voice_add = voice_subparsers.add_parser("add", help="Add a voice clone")
    voice_add.add_argument("--name", "-n", required=True, help="Voice name")
    voice_add.add_argument("--reference", "-r", required=True,
                           help="Reference audio file for voice timbre (any length, full audio used)")
    voice_add.add_argument("--speech", "-s", required=True,
                           help="Speech audio file for T3 conditioning (10+ seconds of clean speech)")
    voice_add.add_argument("--device", "-d", default="cpu",
                           choices=["cpu", "cuda", "mps"],
                           help="Device for inference (default: cpu)")
    voice_add.set_defaults(func=cmd_voice_add)

    voice_remove = voice_subparsers.add_parser("remove", help="Remove a registered voice")
    voice_remove.add_argument("--name", "-n", required=True, help="Voice name")
    voice_remove.set_defaults(func=cmd_voice_remove)

    # devices command
    devices_parser = subparsers.add_parser("devices", help="List audio devices")
    devices_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    devices_parser.set_defaults(func=cmd_devices)

    # doctor command
    doctor_parser = subparsers.add_parser("doctor", help="Run diagnostics")
    doctor_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    doctor_parser.set_defaults(func=cmd_doctor)

    # install command
    install_parser = subparsers.add_parser("install", help="Install the TTS model")
    install_parser.set_defaults(func=cmd_install)

    # daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Daemon lifecycle management")
    daemon_subparsers = daemon_parser.add_subparsers(dest="action", help="Daemon actions")

    daemon_start = daemon_subparsers.add_parser("start", help="Start the daemon")
    daemon_start.add_argument("--autorestart", action="store_true", help="Auto-restart on crash")
    daemon_start.add_argument("--max-retries", type=int, help="Max restart attempts")
    daemon_start.set_defaults(func=cmd_daemon)

    daemon_stop = daemon_subparsers.add_parser("stop", help="Stop the daemon")
    daemon_stop.set_defaults(func=cmd_daemon)

    daemon_restart = daemon_subparsers.add_parser("restart", help="Restart the daemon")
    daemon_restart.set_defaults(func=cmd_daemon)

    daemon_status = daemon_subparsers.add_parser("status", help="Show daemon status")
    daemon_status.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    daemon_status.set_defaults(func=cmd_daemon)

    daemon_serve = daemon_subparsers.add_parser("serve", help="Run the daemon server in the foreground")
    daemon_serve.add_argument("--port", type=int, default=8765, help="TCP port to listen on (default: 8765)")
    daemon_serve.add_argument("--auto-restart", action="store_true", help="Auto-restart on crash")
    daemon_serve.add_argument("--max-retries", type=int, default=0, help="Max restart attempts (0 = infinite)")
    daemon_serve.set_defaults(func=cmd_daemon)

    # version command
    version_parser = subparsers.add_parser("version", help="Show version")
    version_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Command groups (voice, daemon) without a sub-action have no func: show help.
    if not hasattr(args, "func"):
        subparsers.choices[args.command].print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
