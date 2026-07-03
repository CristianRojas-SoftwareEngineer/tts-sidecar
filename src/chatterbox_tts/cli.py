"""
Interfaz CLI de Chatterbox TTS.
Consumible desde cualquier lenguaje de programación vía subprocess.

Contrato de salida (estable entre SO y lenguajes):
  - Los datos van a stdout; los diagnósticos y errores van a stderr.
  - Los comandos de lectura (voice list, devices, version, daemon status, doctor)
    aceptan --json para salida legible por máquina.
  - Códigos de salida: 0 = éxito; distinto de 0 = error (doctor devuelve 1 cuando
    falla un chequeo).
  - stdout/stderr se fuerzan a UTF-8 para una codificación consistente en toda
    plataforma.
"""

import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import argparse
import sys
import os
import platform
from pathlib import Path

from .timing import timed_command, StageTimer, log

# Imports perezosos (lazy): solo se cargan cuando se ejecutan los comandos.
# Esto permite que --help funcione sin las dependencias instaladas.


def _resolve_voice_paths(args):
    """Resuelve las rutas de audio de una voz a partir de su nombre SIN cargar el modelo."""
    from . import voices

    voice_audio = getattr(args, 'voice_audio', None)
    speech_audio = getattr(args, 'speech_audio', None)

    if getattr(args, 'voice', None):
        # Resuelve directamente desde el sistema de archivos: no se necesita el modelo.
        voice_audio, speech_audio = voices.voice_paths(args.voice)
    elif not voice_audio and not speech_audio:
        # Sin --voice ni audios explícitos: usar la voz de fábrica 'default'
        # (resolución usuario→fábrica), de modo que `speak --text "Hola"` funcione.
        voice_audio, speech_audio = voices.voice_paths("default")

    # Resuelve a rutas absolutas contra el CWD del cliente antes de que crucen la
    # frontera de proceso hacia el daemon, que tiene otro directorio de trabajo.
    if voice_audio:
        voice_audio = str(Path(voice_audio).resolve())
    if speech_audio:
        speech_audio = str(Path(speech_audio).resolve())

    return voice_audio, speech_audio


def _emit_audio(audio_bytes, output):
    """Reproduce los bytes de audio, o los escribe a un archivo si se da una ruta de salida."""
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
    """Sintetiza vía daemon y emite el audio (reproducción o archivo).

    Asume el daemon disponible: cualquier fallo de comunicación o síntesis
    propaga la excepción al llamador (sin fallback silencioso a modo directo).
    """
    import time

    from .daemon import DaemonIPCClient

    synth_start = time.time()
    log("[Daemon] Enviando solicitud de síntesis...")
    client = DaemonIPCClient()
    audio_bytes = client.synthesize(
        text=args.text,
        voice_audio=voice_audio,
        speech_audio=speech_audio,
    )
    elapsed = time.time() - synth_start
    log(f"[Daemon] Síntesis completada ({elapsed:.1f}s)")

    _emit_audio(audio_bytes, args.output)


def _require_model_cached(model: str = "es-mx-latam"):
    """Verifica que el modelo esté en caché y, si no lo está, aborta remitiendo a 'setup'."""
    from .model_cache import is_model_cached
    if not is_model_cached(model):
        print(
            f"Error: el modelo '{model}' no está descargado.",
            file=sys.stderr,
        )
        print("Ejecuta 'tts-sidecar setup' para descargarlo antes de continuar.", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_speak(args):
    """Sintetiza texto; reproduce el audio, o lo guarda a un archivo si se da --output."""

    try:
        if not args.text or not args.text.strip():
            print("Error: --text no puede estar vacío.", file=sys.stderr)
            sys.exit(1)

        # Exige que el modelo esté en caché antes de sintetizar.
        # Las descargas son responsabilidad exclusiva de 'setup'.
        _require_model_cached()

        # Resuelve las rutas de audio de la voz SIN cargar el modelo.
        voice_audio, speech_audio = _resolve_voice_paths(args)

        # Despacho de tres ramas:
        #   --daemon:    usar el daemon sin sondeo previo; un fallo se reporta.
        #   --no-daemon: modo directo sin sondear.
        #   sin flags:   health check corto; daemon si responde, directo si no.
        if getattr(args, 'daemon', False):
            _synthesize_via_daemon(args, voice_audio, speech_audio)
            return
        if not getattr(args, 'no_daemon', False):
            from .daemon import is_daemon_running
            if is_daemon_running():
                _synthesize_via_daemon(args, voice_audio, speech_audio)
                return
            log("[Daemon] Daemon no disponible; usando modo directo")

        # Modo directo: los imports solo se cargan cuando no se usa el daemon.
        from .engine import ChatterboxEngine

        engine = ChatterboxEngine.get_instance(compute_backend=args.compute_backend)

        audio_bytes = engine.speak(
            text=args.text,
            output_path=args.output,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
        )

        if args.output:
            # engine.speak ya escribió el archivo vía output_path
            log(f"[I/O] Audio guardado: {args.output}")
        else:
            _emit_audio(audio_bytes, None)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        # Remitir a setup solo cuando el faltante es el modelo: un audio o una
        # voz ausentes no se resuelven descargando el modelo.
        from .model_cache import is_model_cached
        if not is_model_cached("es-mx-latam"):
            print("Ejecuta 'tts-sidecar setup' primero.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_add(args):
    """Registra una voz clonada a partir de los audios de referencia."""
    try:
        from .engine import ChatterboxEngine

        engine = ChatterboxEngine(compute_backend=args.compute_backend)
        ref_path, speech_path = engine.add_voice(
            name=args.name,
            reference_audio=args.reference,
            speech_audio=args.speech,
            force=getattr(args, "force", False),
        )
        print(f"Voz '{args.name}' registrada:")
        print(f"  timbre (reference): {ref_path}")
        print(f"  habla (conditioning): {speech_path}")

    except Exception as e:
        print(f"Error al registrar la voz: {e}", file=sys.stderr)
        sys.exit(1)


@timed_command
def cmd_voice_remove(args):
    """Elimina una voz registrada."""
    from . import voices

    try:
        if voices.remove_voice(args.name):
            print(f"Voz '{args.name}' eliminada.")
        elif voices._resolve_voice_dir(args.name) is not None:
            # Existe pero no como voz de usuario: es una voz de fábrica
            print(
                f"Voz '{args.name}' es una voz de fábrica (solo lectura) y no puede eliminarse.",
                file=sys.stderr,
            )
            sys.exit(1)
        else:
            print(f"Voz '{args.name}' no encontrada.", file=sys.stderr)
            sys.exit(1)

    except (PermissionError, OSError) as e:
        # WARNING-01: en Windows, shutil.rmtree falla con PermissionError si
        # reference.wav/speech.wav están abiertos por otro proceso (p. ej. el
        # daemon o un reproductor). Sin esta rama, el except genérico de abajo
        # reportaba el mismo mensaje que un nombre de voz inválido.
        print(
            f"Error al eliminar la voz '{args.name}': uno de sus archivos parece "
            "estar en uso (por ejemplo, por el daemon u otro proceso). "
            f"Ciérralo y vuelve a intentarlo. Detalle: {e}",
            file=sys.stderr,
        )
        sys.exit(1)
    except Exception as e:
        print(f"Error al eliminar la voz: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_voice_list(args):
    """Lista todas las voces registradas."""
    from . import voices

    try:
        voice_list = voices.list_voices()

        if getattr(args, "json", False):
            import json
            print(json.dumps({"voices": voice_list}))
            return

        if voice_list:
            print("Voces registradas:")
            for voice in voice_list:
                print(f"  - {voice}")
        else:
            print("No hay voces registradas. Ejecuta:")
            print("  tts-sidecar voice add --name mi_voz --reference timbre.wav --speech habla.wav")

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        print("Ejecuta 'tts-sidecar setup' primero.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error al listar las voces: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_devices(args):
    """Lista los dispositivos de salida de audio."""
    from .audio import get_audio_devices

    try:
        devices = get_audio_devices()
    except Exception as e:
        print(f"Error al enumerar los dispositivos de audio: {e}", file=sys.stderr)
        sys.exit(1)

    if getattr(args, "json", False):
        import json
        print(json.dumps({"devices": devices}))
        return

    print("Dispositivos de salida de audio:")
    for dev in devices:
        print(f"  [{dev['id']}] {dev['name']} (latency: {dev['latency']*1000:.1f}ms)")


def cmd_version(args):
    """Muestra la versión de tts-sidecar."""
    from . import __version__

    if getattr(args, "json", False):
        import json
        print(json.dumps({"name": "tts-sidecar", "version": __version__}))
    else:
        print(f"tts-sidecar {__version__}")


def _environment_checks() -> list[tuple[str, str, str]]:
    """Chequeos de entorno compartidos por doctor y setup.

    Devuelve una lista de (status, name, detail) con status en PASS/FAIL:
    Chatterbox importable + librería de audio de la plataforma.
    """
    checks = []

    # Chequea Chatterbox
    try:
        import chatterbox
        checks.append(("PASS", "Chatterbox TTS", chatterbox.__version__))
    except ImportError:
        checks.append(("FAIL", "Chatterbox TTS", "NO INSTALADO (pip install chatterbox-tts)"))

    # Chequea la librería de audio. En las tres plataformas se reutiliza la
    # enumeración real de audio.py (no solo la disponibilidad del import), de
    # modo que el chequeo refleje el estado efectivo del subsistema: un host
    # sin audio real (sesiones RDP/headless, sin backend ALSA/CoreAudio)
    # importa la librería sin problema pero falla al enumerar en runtime
    # (WARNING-03).
    try:
        from .audio import get_audio_devices_with_status
        devices, degraded = get_audio_devices_with_status()
        system = platform.system()
        lib_name = {"Windows": "pycaw", "Linux": "sounddevice", "Darwin": "sounddevice"}.get(system, "audio")
        if degraded:
            checks.append((
                "FAIL",
                "Audio library",
                f"{lib_name} importado pero no se pudo enumerar ningún dispositivo real "
                "(host sin audio o sin subsistema de sonido)",
            ))
        else:
            checks.append(("PASS", "Audio library", f"{lib_name} ({system}) — {len(devices)} dispositivo(s)"))
    except ImportError:
        checks.append(("FAIL", "Audio library", "NO INSTALADO"))
    except Exception as e:
        checks.append(("FAIL", "Audio library", str(e)))

    return checks


def cmd_doctor(args):
    """Ejecuta los chequeos de diagnóstico."""
    from . import voices

    # lista de (status, name, detail) con status en PASS/FAIL/SKIP
    checks = _environment_checks()

    # Chequea el modelo: verifica que es-mx-latam esté en caché (sin cargar ni descargar)
    try:
        from .model_cache import is_model_cached
        if is_model_cached("es-mx-latam"):
            checks.append(("PASS", "Chatterbox model", "es-mx-latam presente en la caché"))
        else:
            checks.append(("FAIL", "Chatterbox model", "es-mx-latam no está en caché (ejecuta: tts-sidecar setup)"))
    except Exception as e:
        checks.append(("FAIL", "Chatterbox model", f"{e} (ejecuta: tts-sidecar setup)"))

    # Chequea el directorio de voces de usuario
    voices_path = voices.voices_root()
    count = len(voices.list_voices())
    if os.path.exists(voices_path) or count:
        checks.append(("PASS", "Voices directory", f"{count} voz(voces) disponible(s)"))
    else:
        checks.append(("SKIP", "Voices directory", "sin voces de usuario aún (opcional)"))

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
    print(f"Plataforma: {platform.system()} {platform.release()}")
    print()
    for status, name, detail in checks:
        print(f"[{status}] {name}: {detail}")
    print()
    print(f"Chequeos: {checks_passed} exitosos, {checks_failed} fallidos")

    if checks_failed > 0:
        sys.exit(1)


def _linux_path_symlink() -> Path:
    """Ruta del symlink de PATH que setup gestiona en Linux (~/.local/bin/tts-sidecar)."""
    return Path.home() / ".local" / "bin" / "tts-sidecar"


def _integrate_linux_path():
    """Crea/actualiza el symlink ~/.local/bin/tts-sidecar → $APPIMAGE.

    Solo actúa en Linux cuando el proceso corre desde un AppImage (el runtime
    expone la ruta absoluta del archivo en la variable de entorno APPIMAGE).
    Fuera de ese contexto no toca el filesystem. ~/.local/bin es el directorio
    de usuario estándar XDG, presente en el PATH por defecto de las distros
    modernas, sin necesidad de sudo.
    """
    appimage = os.environ.get("APPIMAGE")
    if sys.platform != "linux" or not appimage:
        return

    link = _linux_path_symlink()
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        # Un archivo regular homónimo no es nuestro: no se sobrescribe.
        print(f"\n[SKIP] PATH: {link} existe y no es un symlink; no se modifica.")
        return
    link.symlink_to(appimage)
    print(f"\n[PASS] PATH: symlink creado {link} -> {appimage}")
    print("El comando 'tts-sidecar' queda disponible por nombre en la terminal.")
    print("Para revertirlo: tts-sidecar setup --remove-path")

    if str(link.parent) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"[WARN] {link.parent} no está en el PATH de esta sesión.")
        print('Añade esta línea a tu shell profile (~/.bashrc, ~/.zshrc, ...):')
        print('    export PATH="$HOME/.local/bin:$PATH"')


def _remove_linux_path():
    """Elimina el symlink de PATH creado por setup (rama --remove-path)."""
    link = _linux_path_symlink()
    if link.is_symlink():
        link.unlink()
        print(f"Symlink eliminado: {link}")
    elif link.exists():
        print(
            f"Error: {link} existe pero no es un symlink; no se elimina.",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(f"No hay nada que quitar: {link} no existe.")


def cmd_setup(args):
    """Provisiona el runtime: corre los chequeos de entorno y descarga el modelo si falta.

    En Linux, ejecutado desde un AppImage, también integra el comando en el PATH
    (symlink de $APPIMAGE en ~/.local/bin); --remove-path revierte ese symlink
    sin correr chequeos ni descargas.
    """
    if getattr(args, "remove_path", False):
        _remove_linux_path()
        return

    print("=== Chatterbox TTS Setup ===\n")

    # 1. Integración de PATH (solo Linux desde AppImage; no-op en el resto).
    # Va antes de los chequeos para que un host degradado (p. ej. sin audio)
    # obtenga igualmente el comando en el PATH, en paridad con Windows y macOS;
    # el symlink es inocuo y reversible con --remove-path.
    _integrate_linux_path()

    # 2. Chequeos de entorno (implementación compartida con doctor).
    for status, name, detail in _environment_checks():
        if status == "FAIL":
            print(f"[FAIL] {name}: {detail}", file=sys.stderr)
            sys.exit(1)
        print(f"[{status}] {name}: {detail}")

    # 3. Provisión del modelo (idempotente): descarga solo si no está ya en caché.
    # El modelo se descarga a la caché de HuggingFace (ver engine._download_model),
    # estable tanto desde fuente como en el ejecutable onedir.
    model_dir = os.path.join(os.path.expanduser("~"), ".cache", "huggingface", "hub")

    try:
        from .model_cache import is_model_cached

        if is_model_cached("es-mx-latam"):
            print(f"\n[PASS] El modelo 'es-mx-latam' ya está en caché en: {model_dir}")
            print("Provisión completa. No hay nada que descargar.")
            return

        print("\nDescargando el modelo es-mx-latam...")
        print("(Puede tardar varios minutos en la primera ejecución)\n")

        from .engine import ChatterboxEngine
        ChatterboxEngine.get_instance(model="es-mx-latam", compute_backend="auto")

        print("\n[PASS] ¡Modelo descargado correctamente!")
        print(f"  Ubicación: {model_dir}")

    except Exception as e:
        print(f"[FAIL] La provisión falló: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_daemon(args):
    """Gestiona el daemon de tts-sidecar."""
    if args.action == "serve":
        # Servidor en primer plano. Lo usa el ejecutable congelado para autoinvocar
        # el daemon (el .exe no puede ejecutar `python -m ...`).
        from .daemon.run import serve
        serve(
            port=args.port,
            auto_restart=getattr(args, "auto_restart", False),
            max_retries=getattr(args, "max_retries", 0) or 0,
        )
        return

    from .daemon import DaemonManager

    manager = DaemonManager(port=getattr(args, "port", None))

    if args.action == "start":
        # Exige que el modelo esté en caché antes de lanzar el servidor.
        # Las descargas son responsabilidad exclusiva de 'setup'.
        _require_model_cached("es-mx-latam")
        success = manager.start(
            background=True,
            auto_restart=args.autorestart,
            max_retries=args.max_retries or 0,
        )
        if success:
            print("Daemon iniciado correctamente")
        else:
            print("No se pudo iniciar el daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "stop":
        if manager.stop():
            print("Daemon detenido")
        else:
            print("No se pudo detener el daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "restart":
        if manager.restart():
            print("Daemon reiniciado")
        else:
            print("No se pudo reiniciar el daemon", file=sys.stderr)
            sys.exit(1)

    elif args.action == "status":
        status = manager.status()

        if getattr(args, "json", False):
            import json
            print(json.dumps(status))
            return

        if status.get("running"):
            print(f"Daemon en ejecución:")
            print(f"  Estado: {status.get('status', 'desconocido')}")
            print(f"  Modelo cargado: {status.get('model_loaded', False)}")
            print(f"  Tiempo activo: {status.get('uptime_seconds', 0):.1f}s")
        else:
            print("Daemon no está en ejecución")


def main():
    """Punto de entrada principal de la CLI."""
    # Fuerza salida UTF-8 para una codificación consistente en Windows/Linux/macOS.
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        prog="tts-sidecar",
        description="Chatterbox TTS - TTS 100% local con clonación de voz"
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # comando speak (unificado: reproduce el audio, o lo guarda a archivo con --output)
    speak_parser = subparsers.add_parser("speak", help="Sintetiza voz; la reproduce, o la guarda con --output")
    speak_parser.add_argument("--text", "-t", required=True, help="Texto a sintetizar")
    speak_parser.add_argument("--voice", "-v", help="Nombre de la voz a usar (auto-carga reference.wav + speech.wav)")
    speak_parser.add_argument("--output", "-o", help="Ruta del archivo WAV de salida (si se omite, se reproduce el audio)")
    speak_parser.add_argument("--compute-backend", "-cb", default="auto",
                              choices=["auto", "cpu", "cuda", "mps"],
                              help="Backend de cómputo para la inferencia; 'auto' detecta el mejor "
                                   "disponible (default: auto)")
    speak_parser.add_argument("--voice-audio",
                              help="Archivo de audio para el Voice Encoder (audio completo para el embedding de timbre)")
    speak_parser.add_argument("--speech-audio",
                              help="Archivo de audio para el conditioning del T3 (6s) + decoder S3Gen (10s). "
                                   "Usa un segmento de habla limpia (10s+ recomendado).")
    speak_parser.add_argument("--daemon", action="store_true",
                              help="Usar el daemon sin sondeo previo; si falla, se reporta el error "
                                   "(sin flags, se sondea el daemon y se usa solo si responde)")
    speak_parser.add_argument("--no-daemon", action="store_true",
                              help="Forzar modo directo, sin sondear el daemon")
    speak_parser.set_defaults(func=cmd_speak)

    # grupo de comandos voice (list / add / remove)
    voice_parser = subparsers.add_parser("voice", help="Gestiona las voces registradas")
    voice_subparsers = voice_parser.add_subparsers(dest="action", help="Acciones de voz")

    voice_list = voice_subparsers.add_parser("list", help="Lista las voces registradas")
    voice_list.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    voice_list.set_defaults(func=cmd_voice_list)

    voice_add = voice_subparsers.add_parser("add", help="Registra una voz clonada")
    voice_add.add_argument("--name", "-n", required=True, help="Nombre de la voz")
    voice_add.add_argument("--reference", "-r", required=True,
                           help="Archivo de audio de referencia para el timbre (cualquier largo, se usa el audio completo)")
    voice_add.add_argument("--speech", "-s", required=True,
                           help="Archivo de audio de habla para el conditioning del T3 (10+ segundos de habla limpia)")
    voice_add.add_argument("--compute-backend", "-cb", default="auto",
                           choices=["auto", "cpu", "cuda", "mps"],
                           help="Backend de cómputo para la inferencia; 'auto' detecta el mejor "
                                "disponible (default: auto)")
    voice_add.add_argument("--force", "-f", action="store_true",
                           help="Sobrescribir la voz si ya existe (usuario o fábrica homónima)")
    voice_add.set_defaults(func=cmd_voice_add)

    voice_remove = voice_subparsers.add_parser("remove", help="Elimina una voz registrada")
    voice_remove.add_argument("--name", "-n", required=True, help="Nombre de la voz")
    voice_remove.set_defaults(func=cmd_voice_remove)

    # comando devices
    devices_parser = subparsers.add_parser("devices", help="Lista los dispositivos de audio")
    devices_parser.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    devices_parser.set_defaults(func=cmd_devices)

    # comando doctor
    doctor_parser = subparsers.add_parser("doctor", help="Ejecuta diagnósticos")
    doctor_parser.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    doctor_parser.set_defaults(func=cmd_doctor)

    # comando setup
    setup_parser = subparsers.add_parser("setup", help="Provisiona el runtime: corre chequeos, descarga el modelo si falta "
                                                       "y en Linux (AppImage) integra el comando en el PATH")
    setup_parser.add_argument("--remove-path", action="store_true",
                              help="Elimina el symlink de PATH (~/.local/bin/tts-sidecar) creado por setup en Linux "
                                   "y termina sin correr chequeos ni descargas")
    setup_parser.set_defaults(func=cmd_setup)

    # comando daemon
    daemon_parser = subparsers.add_parser("daemon", help="Gestión del ciclo de vida del daemon")
    daemon_subparsers = daemon_parser.add_subparsers(dest="action", help="Acciones del daemon")

    daemon_start = daemon_subparsers.add_parser("start", help="Inicia el daemon")
    daemon_start.add_argument("--port", type=int, default=8765, help="Puerto TCP donde escuchar (default: 8765)")
    daemon_start.add_argument("--autorestart", action="store_true", help="Auto-reinicio en caso de crash")
    daemon_start.add_argument("--max-retries", type=int, help="Máximo de intentos de reinicio")
    daemon_start.set_defaults(func=cmd_daemon)

    daemon_stop = daemon_subparsers.add_parser("stop", help="Detiene el daemon")
    daemon_stop.set_defaults(func=cmd_daemon)

    daemon_restart = daemon_subparsers.add_parser("restart", help="Reinicia el daemon")
    daemon_restart.set_defaults(func=cmd_daemon)

    daemon_status = daemon_subparsers.add_parser("status", help="Muestra el estado del daemon")
    daemon_status.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    daemon_status.set_defaults(func=cmd_daemon)

    daemon_serve = daemon_subparsers.add_parser("serve", help="Ejecuta el servidor del daemon en primer plano")
    daemon_serve.add_argument("--port", type=int, default=8765, help="Puerto TCP donde escuchar (default: 8765)")
    daemon_serve.add_argument("--auto-restart", action="store_true", help="Auto-reinicio en caso de crash")
    daemon_serve.add_argument("--max-retries", type=int, default=0, help="Máximo de intentos de reinicio (0 = infinito)")
    daemon_serve.set_defaults(func=cmd_daemon)

    # comando version
    version_parser = subparsers.add_parser("version", help="Muestra la versión")
    version_parser.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    version_parser.set_defaults(func=cmd_version)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Los grupos de comandos (voice, daemon) sin sub-acción no tienen func: mostrar ayuda.
    if not hasattr(args, "func"):
        subparsers.choices[args.command].print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
