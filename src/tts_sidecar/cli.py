"""
Interfaz CLI de TTS Sidecar.
Consumible desde cualquier lenguaje de programación vía subprocess.

Contrato de salida (estable entre SO y lenguajes):
  - Los datos van a stdout; los diagnósticos y errores van a stderr.
  - Los comandos de lectura (voice list, devices, version, daemon status, doctor)
    aceptan --json para salida legible por máquina.
  - Códigos de salida (contrato público congelado; un orquestador distingue la
    causa sin parsear texto):
      0   éxito
      1   error genérico (incluye chequeos fallidos de doctor)
      2   modelo no provisionado (ejecutar 'setup')
      3   voz o archivo de audio no encontrado
      4   entrada inválida (texto vacío, nombre de voz ilegal, colisión)
      5   daemon inalcanzable o no gestionable
      130 interrupción por el usuario (Ctrl+C)
  - stdout/stderr se fuerzan a UTF-8 para una codificación consistente en toda
    plataforma.
"""

from . import bootstrap
bootstrap.apply()

import argparse
import sys
import os
import platform
from pathlib import Path

from .timing import timed_command, StageTimer, Spinner, log, format_progress_event

# Mapa de códigos de salida del CLI — CONTRATO PÚBLICO CONGELADO (ver USAGE.md).
# Un orquestador distingue causas sin parsear texto: no cambiar los valores.
EXIT_OK = 0                   # éxito
EXIT_ERROR = 1                # error genérico (incluye chequeos fallidos de doctor)
EXIT_MODEL_MISSING = 2        # modelo no provisionado (ejecutar 'setup')
EXIT_NOT_FOUND = 3            # voz o archivo de audio no encontrado
EXIT_INVALID_INPUT = 4        # entrada inválida (texto vacío, nombre ilegal, colisión)
EXIT_DAEMON_UNREACHABLE = 5   # daemon inalcanzable o no gestionable
EXIT_INTERRUPTED = 130        # interrupción por el usuario (128 + SIGINT)

# Versión del esquema de la salida --json del CLI (contrato legible por máquina).
# Se emite como "schema_version" en TODOS los payloads JSON. Es un campo aditivo:
# los consumidores lo usan para detectar cambios de forma; añadir claves nuevas no
# incrementa la versión, solo lo haría un cambio incompatible de las existentes.
SCHEMA_VERSION = "1"

# Umbral mínimo de espacio libre en disco para descargar el modelo en 'setup'.
# El language pack + Voice Encoder ocupan varios cientos de MB; 2 GB deja margen
# para la descarga, la descompresión y la caché temporal de HuggingFace (R-14).
MIN_FREE_DISK_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB

# RAM recomendada para una síntesis fluida (chequeo advisory de 'doctor', R-18).
# Por debajo de este umbral la inferencia en CPU funciona pero puede paginar en
# textos largos; es un WARN, no un FAIL (no altera el exit code).
RECOMMENDED_RAM_BYTES = 8 * 1024 * 1024 * 1024  # 8 GB

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
        # N-12: simetría con engine._save_wav (modo directo), que ya crea los
        # directorios padres; sin esto, --output a un directorio inexistente
        # solo fallaba vía daemon.
        parent = os.path.dirname(output)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(output, 'wb') as f:
            f.write(audio_bytes)
        log(f"[Archivo] Audio guardado: {output}")
    else:
        log("[Reproducción] Reproduciendo audio...")
        from .audio import AudioPlayer
        player = AudioPlayer()
        player.play(audio_bytes)
        log("[Reproducción] Reproducción finalizada")


def _paths_allowed_by_daemon(voice_audio, speech_audio) -> bool:
    """Replica la sandbox de rutas del daemon (server.py) en el cliente.

    N-02: permite detectar ANTES del despacho si --voice-audio/--speech-audio
    quedarán fuera de los directorios que la sandbox del servidor acepta
    (voices.allowed_audio_dirs()), evitando el 400 opaco «la ruta no está en
    un directorio permitido». No relaja ni duplica la sandbox del servidor:
    solo la anticipa para dar un mensaje accionable en el cliente.
    """
    from . import voices

    allowed_dirs = [os.path.realpath(d) for d in voices.allowed_audio_dirs()]
    for path in (voice_audio, speech_audio):
        if path is None:
            continue
        real_path = os.path.realpath(path)
        if not any(
            real_path == d or real_path.startswith(d + os.sep) for d in allowed_dirs
        ):
            return False
    return True


def _warn_compute_backend_ignored(args):
    """N-10: avisa si --compute-backend se ignora porque la síntesis va vía daemon.

    El daemon fija su compute backend una sola vez al arrancar (ver
    docs/DAEMON-MODE.md); un --compute-backend explícito distinto de "auto" en
    una invocación individual no tiene efecto en esa ruta, y antes se ignoraba
    en silencio.
    """
    backend = getattr(args, "compute_backend", "auto")
    if backend and backend != "auto":
        print(
            f"Advertencia: --compute-backend {backend} se ignora; el daemon usa "
            "el backend fijado a su arranque.",
            file=sys.stderr,
        )


def _synthesize_via_daemon(args, voice_audio, speech_audio):
    """Sintetiza vía daemon y emite el audio (reproducción o archivo).

    Asume el daemon disponible: cualquier fallo de comunicación o síntesis
    propaga la excepción al llamador (sin fallback silencioso a modo directo).
    """
    import time

    from .daemon import DaemonIPCClient

    synth_start = time.time()
    log("[Servidor] Enviando solicitud de síntesis...")
    client = DaemonIPCClient()
    # El daemon transmite su progreso real por el stream NDJSON; on_progress
    # actualiza la etiqueta del spinner en vivo (etapa y tokens del T3). En
    # no-TTY el spinner es un no-op y la salida es idéntica a antes.
    with Spinner("Sintetizando vía daemon…") as sp:
        audio_bytes = client.synthesize(
            text=args.text,
            voice_audio=voice_audio,
            speech_audio=speech_audio,
            on_progress=lambda ev: sp.update(format_progress_event(ev)),
        )
    elapsed = time.time() - synth_start
    log(f"[Servidor] Síntesis completada ({elapsed:.1f}s)")

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
        sys.exit(EXIT_MODEL_MISSING)


@timed_command
def cmd_speak(args):
    """Sintetiza texto; reproduce el audio, o lo guarda a un archivo si se da --output."""

    try:
        # R-02: --daemon y --no-daemon son contradictorios; un consumidor
        # programático espera un diagnóstico, no que uno gane en silencio.
        # Validación manual (no add_mutually_exclusive_group): el exit 2 nativo
        # de argparse colisionaría con EXIT_MODEL_MISSING del contrato congelado.
        if getattr(args, "daemon", False) and getattr(args, "no_daemon", False):
            print("Error: --daemon y --no-daemon son mutuamente excluyentes.", file=sys.stderr)
            sys.exit(EXIT_INVALID_INPUT)

        if not args.text or not args.text.strip():
            print("Error: --text no puede estar vacío.", file=sys.stderr)
            sys.exit(EXIT_INVALID_INPUT)

        # N-11: límite único de texto validado en el cliente antes de cualquier
        # despacho, con el mismo exit code (4) sin importar la ruta (directo o
        # daemon). El límite del daemon (protocol.MAX_TEXT_LENGTH) queda como
        # defensa en profundidad, no como la única fuente de la validación.
        from .daemon.protocol import MAX_TEXT_LENGTH
        if len(args.text) > MAX_TEXT_LENGTH:
            print(
                f"Error: el texto tiene {len(args.text)} caracteres; el máximo "
                f"permitido es {MAX_TEXT_LENGTH}. Fragmenta el texto en varias "
                "llamadas a 'speak'.",
                file=sys.stderr,
            )
            sys.exit(EXIT_INVALID_INPUT)

        # Advertencia no bloqueante para textos muy largos: el T3 topa a
        # MAX_NEW_TOKENS=500, así que una entrada larga puede truncarse en la
        # síntesis. Se avisa por stderr (sin abortar) sugiriendo fragmentar (R-03).
        if len(args.text) > 2000:
            print(
                f"Advertencia: el texto tiene {len(args.text)} caracteres; los textos "
                "muy largos pueden truncarse al sintetizar (límite interno de tokens). "
                "Considera fragmentarlo en oraciones o párrafos para mejores resultados.",
                file=sys.stderr,
            )

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
            _warn_compute_backend_ignored(args)
            if not _paths_allowed_by_daemon(voice_audio, speech_audio):
                print(
                    "Error: --daemon está activo pero la ruta de audio está fuera de "
                    "los directorios que el daemon tiene permitido leer (sandbox de "
                    "server.py). Alternativas:",
                    file=sys.stderr,
                )
                print("  1. Registra el audio como voz: tts-sidecar voice add --name <nombre> --reference <ref> --speech <habla>", file=sys.stderr)
                print("  2. Usa --no-daemon para sintetizar en modo directo con esta ruta", file=sys.stderr)
                print("  3. Copia el audio dentro del directorio de voces del usuario", file=sys.stderr)
                sys.exit(EXIT_INVALID_INPUT)
            _synthesize_via_daemon(args, voice_audio, speech_audio)
            return
        if not getattr(args, 'no_daemon', False):
            from .daemon import is_daemon_running
            if is_daemon_running():
                if _paths_allowed_by_daemon(voice_audio, speech_audio):
                    _warn_compute_backend_ignored(args)
                    _synthesize_via_daemon(args, voice_audio, speech_audio)
                    return
                print(
                    "[Servidor] La ruta de audio está fuera de los directorios permitidos "
                    "por el daemon; usando modo directo",
                    file=sys.stderr,
                )
            else:
                log("[Servidor] No disponible; usando modo directo")

        # Modo directo: los imports solo se cargan cuando no se usa el daemon.
        from .engine import ChatterboxEngine

        # Spinner de liveness durante los dos tramos largos y opacos: la carga del
        # modelo (primer speak) y la síntesis. Las líneas [Stage N/4] que emite el
        # engine vía log() se intercalan de forma coordinada (timing._active_spinner).
        with Spinner("Cargando modelo…") as _sp:
            engine = ChatterboxEngine.get_instance(compute_backend=args.compute_backend)
            _sp.update("Sintetizando voz…")
            # Mismo formateador de progreso que el modo daemon: los eventos del
            # motor (etapa y tokens del T3) actualizan la etiqueta del spinner.
            audio_bytes = engine.speak(
                text=args.text,
                output_path=args.output,
                voice_audio=voice_audio,
                speech_audio=speech_audio,
                progress_callback=lambda ev: _sp.update(format_progress_event(ev)),
            )

        if args.output:
            # engine.speak ya escribió el archivo vía output_path
            log(f"[Archivo] Audio guardado: {args.output}")
        else:
            _emit_audio(audio_bytes, None)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        # Remitir a setup solo cuando el faltante es el modelo: un audio o una
        # voz ausentes no se resuelven descargando el modelo.
        from .model_cache import is_model_cached
        if not is_model_cached("es-mx-latam"):
            print("Ejecuta 'tts-sidecar setup' primero.", file=sys.stderr)
            sys.exit(EXIT_MODEL_MISSING)
        sys.exit(EXIT_NOT_FOUND)
    except Exception as e:
        # Un fallo del daemon (--daemon o sondeo automático) es inalcanzabilidad,
        # no un error genérico de síntesis: se distingue con su propio código.
        from .daemon import DaemonIPCError
        if isinstance(e, DaemonIPCError):
            print(f"Error: no se pudo sintetizar vía daemon: {e}", file=sys.stderr)
            sys.exit(EXIT_DAEMON_UNREACHABLE)
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


@timed_command
def cmd_voice_add(args):
    """Registra una voz clonada a partir de los audios de referencia.

    Registro ligero: valida y copia los audios sin instanciar el motor de
    inferencia; la precomputación de conditionals se difiere al primer
    `speak --voice <nombre>`. El gate de modelo se mantiene por coherencia con
    `speak`/`daemon start`: las descargas son responsabilidad exclusiva de setup.
    """
    try:
        _require_model_cached()

        from . import voices
        ref_path, speech_path = voices.register_voice_files(
            name=args.name,
            reference_audio=args.reference,
            speech_audio=args.speech,
            force=getattr(args, "force", False),
        )

        if getattr(args, "json", False):
            import json
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "name": args.name,
                "reference": str(ref_path),
                "speech": str(speech_path),
            }))
            return

        print(f"Voz '{args.name}' registrada:")
        print(f"  timbre (reference): {ref_path}")
        print(f"  habla (conditioning): {speech_path}")

    except ValueError as e:
        # Audio ilegible, nombre de voz inválido o colisión sin --force.
        print(f"Error al registrar la voz: {e}", file=sys.stderr)
        sys.exit(EXIT_INVALID_INPUT)
    except Exception as e:
        print(f"Error al registrar la voz: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


@timed_command
def cmd_voice_remove(args):
    """Elimina una voz registrada."""
    from . import voices

    try:
        if voices.remove_voice(args.name):
            if getattr(args, "json", False):
                import json
                print(json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "name": args.name,
                    "removed": True,
                }))
                return
            print(f"Voz '{args.name}' eliminada.")
        elif voices._resolve_voice_dir(args.name) is not None:
            # Existe pero no como voz de usuario: es una voz de fábrica
            print(
                f"Voz '{args.name}' es una voz de fábrica (solo lectura) y no puede eliminarse.",
                file=sys.stderr,
            )
            sys.exit(EXIT_INVALID_INPUT)
        else:
            print(f"Voz '{args.name}' no encontrada.", file=sys.stderr)
            sys.exit(EXIT_NOT_FOUND)

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
        sys.exit(EXIT_ERROR)
    except ValueError as e:
        # Nombre de voz inválido (escapes de ruta, caracteres no permitidos).
        print(f"Error al eliminar la voz: {e}", file=sys.stderr)
        sys.exit(EXIT_INVALID_INPUT)
    except Exception as e:
        print(f"Error al eliminar la voz: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def cmd_voice_list(args):
    """Lista todas las voces registradas."""
    from . import voices

    try:
        voice_list = voices.list_voices()

        if getattr(args, "json", False):
            import json
            print(json.dumps({"schema_version": SCHEMA_VERSION, "voices": voice_list}))
            return

        if voice_list:
            print("Voces registradas:")
            for voice in voice_list:
                print(f"  - {voice}")
        else:
            print("No hay voces registradas. Ejecuta:")
            print("  tts-sidecar voice add --name mi_voz --reference timbre.wav --speech habla.wav")

    except FileNotFoundError as e:
        # R-01: listar voces es una operación pura de filesystem; remitir a
        # 'setup' (provisión del modelo) no resuelve un directorio de voces
        # ilegible. Se orienta al directorio real implicado.
        print(f"Error: {e}", file=sys.stderr)
        print(
            f"Revisa el directorio de voces de usuario: {voices.voices_root()}",
            file=sys.stderr,
        )
        sys.exit(EXIT_NOT_FOUND)
    except Exception as e:
        print(f"Error al listar las voces: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def cmd_devices(args):
    """Lista los dispositivos de salida de audio."""
    from .audio import get_audio_devices

    try:
        devices = get_audio_devices()
    except Exception as e:
        print(f"Error al enumerar los dispositivos de audio: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)

    if getattr(args, "json", False):
        import json
        print(json.dumps({"schema_version": SCHEMA_VERSION, "devices": devices}))
        return

    print("Dispositivos de salida de audio:")
    for dev in devices:
        print(f"  [{dev['id']}] {dev['name']} (latencia: {dev['latency']*1000:.1f}ms)")


def cmd_version(args):
    """Muestra la versión de tts-sidecar."""
    from . import __version__

    if getattr(args, "json", False):
        import json
        print(json.dumps({"schema_version": SCHEMA_VERSION, "name": "tts-sidecar", "version": __version__}))
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

    # Chequea la RAM total (advisory, R-18): por debajo del umbral recomendado la
    # síntesis funciona pero puede paginar en textos largos. Es un WARN, no un
    # FAIL: no cuenta como chequeo fallido ni altera el exit code.
    try:
        import psutil
        total = psutil.virtual_memory().total
        total_gb = total / (1024 ** 3)
        if total < RECOMMENDED_RAM_BYTES:
            checks.append((
                "WARN", "RAM",
                f"{total_gb:.1f} GB detectados; se recomiendan 8 GB "
                "(4 GB mínimo). La síntesis puede paginar con textos largos.",
            ))
        else:
            checks.append(("PASS", "RAM", f"{total_gb:.1f} GB"))
    except Exception as e:
        # psutil no disponible o error de lectura: se omite sin penalizar.
        checks.append(("SKIP", "RAM", f"no se pudo determinar ({e})"))

    # Solo FAIL cuenta como fallo: WARN/SKIP no penalizan el exit code.
    checks_failed = sum(1 for status, _, _ in checks if status == "FAIL")
    checks_passed = sum(1 for status, _, _ in checks if status == "PASS")

    if getattr(args, "json", False):
        import json
        print(json.dumps({
            "schema_version": SCHEMA_VERSION,
            "python": sys.version,
            "platform": f"{platform.system()} {platform.release()}",
            "checks": [{"status": s, "name": n, "detail": d} for s, n, d in checks],
            "passed": checks_passed,
            "failed": checks_failed,
        }))
        if checks_failed > 0:
            sys.exit(EXIT_ERROR)
        return

    print("=== TTS Sidecar Doctor ===\n")
    print(f"Python: {sys.version}")
    print(f"Plataforma: {platform.system()} {platform.release()}")
    print()
    for status, name, detail in checks:
        print(f"[{status}] {name}: {detail}")
    print()
    print(f"Chequeos: {checks_passed} exitosos, {checks_failed} fallidos")

    if checks_failed > 0:
        sys.exit(EXIT_ERROR)


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
        print(f"\n[SKIP] PATH: {link} existe y no es un symlink; no se modifica.", file=sys.stderr)
        return
    link.symlink_to(appimage)
    print(f"\n[PASS] PATH: symlink creado {link} -> {appimage}", file=sys.stderr)
    print("El comando 'tts-sidecar' queda disponible por nombre en la terminal.", file=sys.stderr)
    print("Para revertirlo: tts-sidecar setup --remove-path", file=sys.stderr)

    if str(link.parent) not in os.environ.get("PATH", "").split(os.pathsep):
        print(f"[WARN] {link.parent} no está en el PATH de esta sesión.", file=sys.stderr)
        print('Añade esta línea a tu shell profile (~/.bashrc, ~/.zshrc, ...):', file=sys.stderr)
        print('    export PATH="$HOME/.local/bin:$PATH"', file=sys.stderr)


def _remove_linux_path() -> bool:
    """Elimina el symlink de PATH creado por setup (rama --remove-path).

    Devuelve True si el symlink existía y se eliminó, False si no había nada
    que quitar (el caso de error — un archivo regular homónimo — aborta).
    """
    link = _linux_path_symlink()
    if link.is_symlink():
        link.unlink()
        print(f"Symlink eliminado: {link}", file=sys.stderr)
        return True
    elif link.exists():
        print(
            f"Error: {link} existe pero no es un symlink; no se elimina.",
            file=sys.stderr,
        )
        sys.exit(EXIT_ERROR)
    else:
        print(f"No hay nada que quitar: {link} no existe.", file=sys.stderr)
        return False


def cmd_setup(args):
    """Provisiona el runtime: corre los chequeos de entorno y descarga el modelo si falta.

    En Linux, ejecutado desde un AppImage, también integra el comando en el PATH
    (symlink de $APPIMAGE en ~/.local/bin); --remove-path revierte ese symlink
    sin correr chequeos ni descargas.

    setup es provisión, no diagnóstico: el FAIL del chequeo de audio se degrada
    a WARN y la provisión continúa (la síntesis a archivo con `speak --output`
    funciona sin subsistema de sonido, p. ej. en hosts headless/SSH). Cualquier
    otro FAIL sigue abortando. El rol diagnóstico lo cumple `doctor`, que
    conserva el FAIL de audio con salida 1.
    """
    if getattr(args, "remove_path", False):
        removed = _remove_linux_path()
        if getattr(args, "json", False):
            import json
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "remove_path": True,
                "removed": removed,
            }))
        return

    print("=== TTS Sidecar Setup ===\n", file=sys.stderr)

    # 1. Integración de PATH (solo Linux desde AppImage; no-op en el resto).
    # Va antes de los chequeos para que un host degradado (p. ej. sin audio)
    # obtenga igualmente el comando en el PATH, en paridad con Windows y macOS;
    # el symlink es inocuo y reversible con --remove-path.
    _integrate_linux_path()

    # 2. Chequeos de entorno (implementación compartida con doctor). El FAIL
    # de audio es advisory aquí: sin sonido la reproducción no funcionará,
    # pero la síntesis a archivo sí, y bloquear la descarga del modelo dejaría
    # al host permanentemente sin provisión. Los demás FAIL abortan.
    for status, name, detail in _environment_checks():
        if status == "FAIL":
            if name == "Audio library":
                print(f"[WARN] {name}: {detail}", file=sys.stderr)
                print("[WARN] La reproducción de audio no estará disponible; "
                      "la síntesis a archivo (speak --output) funciona igual.", file=sys.stderr)
                continue
            print(f"[FAIL] {name}: {detail}", file=sys.stderr)
            sys.exit(EXIT_ERROR)
        print(f"[{status}] {name}: {detail}", file=sys.stderr)

    # 3. Provisión del modelo (idempotente): descarga solo si no está ya en caché.
    # El modelo se descarga a la caché de HuggingFace (ver engine._download_model),
    # estable tanto desde fuente como en el ejecutable onedir. La ruta efectiva
    # respeta HF_HUB_CACHE/HF_HOME (misma resolución que el descargador).
    from .model_cache import hub_cache_path
    model_dir = str(hub_cache_path())

    # --force-update: borra los snapshots del modelo antes del gate para forzar
    # una re-descarga limpia (R-13). Borrado quirúrgico acotado a las carpetas
    # models--ResembleAI--* del proyecto, misma defensa en profundidad que cleanup.
    if getattr(args, "force_update", False):
        import shutil
        from .model_cache import model_cache_dirs
        print("\n[force-update] Eliminando el modelo en caché para re-descargarlo...", file=sys.stderr)
        for p in model_cache_dirs():
            if not p.name.startswith("models--ResembleAI--"):
                raise RuntimeError(f"Ruta inesperada fuera del proyecto: {p}")
            if p.exists():
                shutil.rmtree(p)
                print(f"[force-update] Eliminado: {p}", file=sys.stderr)

    try:
        from .model_cache import is_model_cached

        def _emit_setup_json(already_cached: bool, downloaded: bool):
            """Payload --json de setup (los [PASS]/[FAIL] de progreso van a stderr)."""
            if getattr(args, "json", False):
                import json
                print(json.dumps({
                    "schema_version": SCHEMA_VERSION,
                    "model": "es-mx-latam",
                    "already_cached": already_cached,
                    "downloaded": downloaded,
                    "cache_dir": model_dir,
                }))

        if is_model_cached("es-mx-latam"):
            print(f"\n[PASS] El modelo 'es-mx-latam' ya está en caché en: {model_dir}", file=sys.stderr)
            print("Provisión completa. No hay nada que descargar.", file=sys.stderr)
            _emit_setup_json(already_cached=True, downloaded=False)
            return

        # Pre-chequeo de espacio en disco antes de descargar (R-14): el modelo
        # pesa varios cientos de MB; con menos de 2 GB libres la descarga puede
        # fallar a medias y dejar una caché truncada. Se aborta antes de empezar.
        # disk_usage exige una ruta existente: en una máquina limpia la caché aún
        # no existe, así que se sube al primer ancestro presente.
        import shutil
        probe = hub_cache_path()
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        free = shutil.disk_usage(probe).free
        if free < MIN_FREE_DISK_BYTES:
            free_gb = free / (1024 ** 3)
            print(
                f"[FAIL] Espacio en disco insuficiente: {free_gb:.1f} GB libres, "
                "se requieren al menos 2 GB para descargar el modelo. "
                "Libera espacio y reintenta 'tts-sidecar setup'.",
                file=sys.stderr,
            )
            sys.exit(EXIT_ERROR)

        print("\nDescargando el modelo es-mx-latam...", file=sys.stderr)
        print("(Puede tardar varios minutos en la primera ejecución)\n", file=sys.stderr)

        # N-17: snapshot_download es solo red/disco, sin cargar el modelo en RAM
        # (~2 GB) como hacía ChatterboxEngine.get_instance; la carga real queda
        # para doctor/el primer 'speak', que ya validan el header safetensors.
        # revision= fijada (R-15): la descarga es determinista y un push
        # posterior al repo del modelo no se propaga a los usuarios.
        from huggingface_hub import snapshot_download
        from .model_cache import MODELS, MODEL_REVISIONS
        snapshot_download(
            repo_id=MODELS["es-mx-latam"],
            revision=MODEL_REVISIONS["es-mx-latam"],
            token=os.getenv("HF_TOKEN"),
        )

        # El language pack no incluye ve.safetensors (Voice Encoder): se comparte
        # con el modelo base. Se provisiona aquí explícitamente para que ningún
        # 'speak' posterior necesite red tras un setup exitoso.
        from .model_cache import is_ve_cached, BASE_MODEL_REPO, BASE_MODEL_REVISION
        if not is_ve_cached():
            print("\nDescargando el Voice Encoder (ve.safetensors)...", file=sys.stderr)
            from huggingface_hub import hf_hub_download
            hf_hub_download(
                repo_id=BASE_MODEL_REPO,
                filename="ve.safetensors",
                revision=BASE_MODEL_REVISION,
                token=os.getenv("HF_TOKEN"),
            )
            print("[PASS] Voice Encoder descargado.", file=sys.stderr)

        print("\n[PASS] ¡Modelo descargado correctamente!", file=sys.stderr)
        print(f"  Ubicación: {model_dir}", file=sys.stderr)
        _emit_setup_json(already_cached=False, downloaded=True)

    except Exception as e:
        print(f"[FAIL] La provisión falló: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


def cmd_cleanup(args):
    """Desaprovisiona los datos del proyecto: modelo en caché y/o voces de usuario.

    Borrado quirúrgico: solo las carpetas de los dos repos HF del proyecto
    (model_cache_dirs) y el directorio de voces de usuario; nunca la caché de
    HuggingFace completa ni datos de otros proyectos.
    """
    import shutil

    json_mode = getattr(args, "json", False)
    # Con --json los listados informativos van a stderr: stdout queda reservado
    # para el único objeto JSON final (contrato stdout-datos/stderr-diagnóstico).
    info_out = sys.stderr if json_mode else sys.stdout

    if json_mode and not (getattr(args, "yes", False) or getattr(args, "dry_run", False)):
        print(
            "Error: cleanup --json requiere --yes o --dry-run (la confirmación "
            "interactiva contaminaría stdout).",
            file=sys.stderr,
        )
        sys.exit(EXIT_INVALID_INPUT)

    def _emit_cleanup_json(removed_paths):
        if json_mode:
            import json
            print(json.dumps({
                "schema_version": SCHEMA_VERSION,
                "removed": [str(p) for p in removed_paths],
                "dry_run": getattr(args, "dry_run", False),
            }))

    do_model = getattr(args, "model", False) or getattr(args, "all", False)
    do_voices = getattr(args, "voices", False) or getattr(args, "all", False)

    if not do_model and not do_voices:
        # Sin flags no se borra nada: se muestra la ayuda del comando
        # (a stderr en modo --json, para no contaminar stdout).
        if json_mode:
            args.cleanup_parser.print_usage(sys.stderr)
            _emit_cleanup_json([])
            return
        args.cleanup_parser.print_help()
        return

    targets = []
    if do_model:
        from .model_cache import model_cache_dirs
        for p in model_cache_dirs():
            # Defensa en profundidad: solo carpetas de modelos del proyecto.
            if not p.name.startswith("models--ResembleAI--"):
                raise RuntimeError(f"Ruta inesperada fuera del proyecto: {p}")
            targets.append((p, "modelo"))
    if do_voices:
        from . import voices
        targets.append((Path(voices.voices_root()), "voces de usuario"))

    existing = [(p, kind) for p, kind in targets if p.exists()]

    if not existing:
        print("No hay nada que limpiar: ninguna de las rutas del proyecto existe.", file=info_out)
        _emit_cleanup_json([])
        return

    print("Rutas a eliminar:", file=info_out)
    for p, kind in existing:
        print(f"  [{kind}] {p}", file=info_out)

    if getattr(args, "dry_run", False):
        print("\n(dry-run) No se borró nada.", file=info_out)
        _emit_cleanup_json([p for p, _kind in existing])
        return

    if not getattr(args, "yes", False):
        # Inalcanzable en modo --json (el gate de arriba exige --yes o --dry-run).
        try:
            respuesta = input("\n¿Eliminar estas rutas? (s/n): ").strip().lower()
        except EOFError:
            # N-03: stdin cerrado (invocado vía subprocess sin --yes) no debe
            # producir un traceback crudo indistinguible de un error real.
            print("\nCancelado: no se borró nada.")
            return
        if respuesta not in ("s", "si", "sí", "y", "yes"):
            print("Cancelado: no se borró nada.")
            return

    for p, _kind in existing:
        shutil.rmtree(p)
        print(f"Eliminado: {p}", file=info_out)
    print(
        "Limpieza completa. 'tts-sidecar setup' reprovisiona el modelo cuando lo necesites.",
        file=info_out,
    )
    _emit_cleanup_json([p for p, _kind in existing])


def cmd_daemon(args):
    """Gestiona el daemon de tts-sidecar."""
    if args.action == "serve":
        # Servidor en primer plano. Lo usa el ejecutable congelado para autoinvocar
        # el daemon (el .exe no puede ejecutar `python -m ...`).
        # Exige el modelo en caché antes de cargar el engine, igual que 'start':
        # sin este gate, 'daemon serve' sin 'setup' dispararía la red de seguridad
        # del engine (descarga de cientos de MB). Las descargas son responsabilidad
        # exclusiva de 'setup'.
        _require_model_cached("es-mx-latam")
        from .daemon.run import serve
        serve(
            auto_restart=getattr(args, "auto_restart", False),
            max_retries=getattr(args, "max_retries", 0) or 0,
        )
        return

    from .daemon import DaemonManager

    manager = DaemonManager()

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
            sys.exit(EXIT_DAEMON_UNREACHABLE)

    elif args.action == "stop":
        if manager.stop():
            print("Daemon detenido")
        else:
            print("No se pudo detener el daemon", file=sys.stderr)
            sys.exit(EXIT_DAEMON_UNREACHABLE)

    elif args.action == "restart":
        if manager.restart():
            print("Daemon reiniciado")
        else:
            print("No se pudo reiniciar el daemon", file=sys.stderr)
            sys.exit(EXIT_DAEMON_UNREACHABLE)

    elif args.action == "status":
        status = manager.status()

        if getattr(args, "json", False):
            import json
            print(json.dumps({"schema_version": SCHEMA_VERSION, **status}))
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
        description="TTS Sidecar - TTS 100% local con clonación de voz"
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
                                   "(sin flags, se sondea el daemon y se usa solo si responde). "
                                   "Mutuamente excluyente con --no-daemon (exit 4 si se combinan)")
    speak_parser.add_argument("--no-daemon", action="store_true",
                              help="Forzar modo directo, sin sondear el daemon. "
                                   "Mutuamente excluyente con --daemon (exit 4 si se combinan)")
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
    voice_add.add_argument("--force", "-f", action="store_true",
                           help="Sobrescribir la voz si ya existe (usuario o fábrica homónima)")
    voice_add.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    voice_add.set_defaults(func=cmd_voice_add)

    voice_remove = voice_subparsers.add_parser("remove", help="Elimina una voz registrada")
    voice_remove.add_argument("--name", "-n", required=True, help="Nombre de la voz")
    voice_remove.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
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
    setup_parser.add_argument("--force-update", action="store_true",
                              help="Elimina el modelo en caché y lo vuelve a descargar (fuerza una "
                                   "re-descarga limpia, p. ej. para actualizarlo)")
    setup_parser.add_argument("--json", action="store_true", help="Emitir JSON legible por máquina")
    setup_parser.set_defaults(func=cmd_setup)

    # comando cleanup
    cleanup_parser = subparsers.add_parser(
        "cleanup",
        help="Desaprovisiona los datos del proyecto (modelo descargado y/o voces de usuario)",
    )
    cleanup_parser.add_argument("--model", action="store_true",
                                help="Elimina el modelo descargado (solo las carpetas de este proyecto "
                                     "dentro de la caché de HuggingFace)")
    cleanup_parser.add_argument("--voices", action="store_true",
                                help="Elimina las voces de usuario registradas con 'voice add'")
    cleanup_parser.add_argument("--all", action="store_true",
                                help="Elimina el modelo y las voces de usuario")
    cleanup_parser.add_argument("--dry-run", action="store_true",
                                help="Lista lo que se borraría sin borrar nada")
    cleanup_parser.add_argument("--yes", "-y", action="store_true",
                                help="Omite la confirmación interactiva")
    cleanup_parser.add_argument("--json", action="store_true",
                                help="Emitir JSON legible por máquina (requiere --yes o --dry-run)")
    cleanup_parser.set_defaults(func=cmd_cleanup, cleanup_parser=cleanup_parser)

    # comando daemon
    daemon_parser = subparsers.add_parser("daemon", help="Gestión del ciclo de vida del daemon")
    daemon_subparsers = daemon_parser.add_subparsers(dest="action", help="Acciones del daemon")

    daemon_start = daemon_subparsers.add_parser("start", help="Inicia el daemon")
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
        sys.exit(EXIT_OK)

    # Los grupos de comandos (voice, daemon) sin sub-acción no tienen func: mostrar ayuda.
    if not hasattr(args, "func"):
        subparsers.choices[args.command].print_help()
        sys.exit(EXIT_OK)

    try:
        args.func(args)
    except KeyboardInterrupt:
        # Cierre limpio ante Ctrl+C: sin traceback, mensaje de una línea a stderr
        # y el código 130 convencional (128 + SIGINT). Solo actúa si la excepción
        # escapa hasta aquí: el shutdown graceful de uvicorn en 'daemon serve'
        # la maneja antes y no pasa por esta rama.
        print("Interrumpido por el usuario.", file=sys.stderr)
        sys.exit(EXIT_INTERRUPTED)


if __name__ == "__main__":
    main()
