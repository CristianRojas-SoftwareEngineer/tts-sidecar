#!/usr/bin/env python3
"""
Build script for Windows x64 executable using Nuitka.
Produces a single-file executable with embedded Python interpreter.
"""

import os
import sys
import subprocess
import threading
import signal
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

# Import shared logging utilities
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log, StageTimer, BuildTimer


def stream_output(proc, prefix=""):
    """Print subprocess output in real-time with [HH:MM:SS] timestamp.

    Buffers incoming bytes and emits complete lines (ending with \\n or \\r)
    with a timestamp. Progress bars (\\r) are timestamped on their line.
    """
    import os, sys
    from datetime import datetime

    line_buf = ""
    last_cr = False  # Track if previous char was \r (progress bar)

    def flush_line(text, is_progress=False):
        ts = datetime.now().strftime("%H:%M:%S")
        if is_progress:
            sys.stdout.write(f"\r[{ts}] {prefix}{text}")
        else:
            sys.stdout.write(f"[{ts}] {prefix}{text}")
        sys.stdout.flush()

    try:
        while True:
            chunk = os.read(proc.stdout.fileno(), 16384)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            line_buf += text

            # Process complete units (lines ending in \n or progress bars with \r)
            while "\n" in line_buf or "\r" in line_buf:
                # Find next newline or carriage return
                nl_pos = line_buf.find("\n")
                cr_pos = line_buf.find("\r")

                # Only treat as progress bar if \r is at position 0 AND
                # the next char is not \n (blank line is not a progress bar).
                if cr_pos == 0 and (nl_pos == -1 or cr_pos < nl_pos):
                    next_char = line_buf[1:2] if len(line_buf) > 1 else ""
                    if next_char and next_char != "\n":
                        # Real progress bar — content follows \r
                        unit = line_buf[:cr_pos + 1]
                        line_buf = line_buf[cr_pos + 1:]
                        flush_line(unit, is_progress=True)
                        last_cr = True
                    else:
                        # Blank line (just \r\n) — treat as regular line
                        unit = line_buf[:cr_pos + 1]
                        line_buf = line_buf[cr_pos + 1:]
                        flush_line(unit, is_progress=last_cr)
                        last_cr = False
                elif cr_pos > 0 and (nl_pos == -1 or cr_pos < nl_pos):
                    # \r found but not at start — treat as regular content with \r included
                    unit = line_buf[:cr_pos + 1]
                    line_buf = line_buf[cr_pos + 1:]
                    flush_line(unit, is_progress=last_cr)
                    last_cr = False
                elif nl_pos != -1:
                    unit = line_buf[:nl_pos + 1]
                    line_buf = line_buf[nl_pos + 1:]
                    flush_line(unit, is_progress=last_cr)
                    last_cr = False
                else:
                    break

            # If buffer grows very large without newlines, flush as raw text to avoid
            # memory pressure. This should rarely trigger since nuitka args fit < 10 KB.
            if len(line_buf) > 100000 and "\n" not in line_buf and "\r" not in line_buf:
                sys.stdout.write(line_buf)
                sys.stdout.flush()
                line_buf = ""

        # Flush any remaining content
        if line_buf:
            flush_line(line_buf, is_progress=last_cr)
    except Exception as e:
        sys.stdout.write(f"[{datetime.now().strftime('%H:%M:%S')}] {prefix}[stream error: {e}]\n")
        sys.stdout.flush()
    finally:
        proc.wait()


def check_dependencies():
    """Check required dependencies are installed."""
    with StageTimer("CheckDeps", "Checking dependencies"):
        # nuitka --version prompts for Zig download if not found; answer Yes automatically
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True, input="Yes\n"
        )
        if result.returncode == 0:
            log(f"Nuitka: {result.stdout.strip().splitlines()[0]}")
        else:
            log("Nuitka not found, installing...")
            pip_proc = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "nuitka"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            stream_output(pip_proc, "[pip] ")
            if pip_proc.returncode != 0:
                sys.exit(1)


def build_windows():
    """Build Windows x64 executable."""
    with BuildTimer():
        with StageTimer("Setup", "Setting up build environment"):
            log("Platform: Windows x64")
            DIST_DIR.mkdir(parents=True, exist_ok=True)
            output_path = DIST_DIR / "tts-sidecar.exe"
            entry_point = PROJECT_ROOT / "bin" / "tts-sidecar"
            env = os.environ.copy()
            src_path = str(PROJECT_ROOT / "src")
            env["PYTHONPATH"] = src_path + os.pathsep + env.get("PYTHONPATH", "")

        with StageTimer("Configure", "Configuring Nuitka options"):
            # Order: mode → output → includes → excludes → python-flags → module-params → platform → entry
            nuitka_args = [
                # Mode
                sys.executable,
                "-m", "nuitka",
                "--standalone",
                "--onefile",
                # Output
                f"--output-filename={output_path.name}",
                f"--output-dir={DIST_DIR}",
                # Includes — project package first, then others alphabetically
                f"--include-plugin-directory={PROJECT_ROOT / 'src'}",
                "--include-package=chatterbox_tts",
                "--include-package=chatterbox",
                "--include-package=certifi",
                "--include-package=huggingface_hub",
                "--include-package=librosa",
                "--include-package=numpy",
                "--include-package=perth",
                "--include-package=pycaw",
                "--include-package=pydantic",
                "--include-package=requests",
                "--include-package=safetensors",
                "--include-package=scipy",
                "--include-package=soundfile",
                "--include-package=torch",
                "--include-package=tokenizers",
                "--include-package=fastapi",
                "--include-package=httpx",
                "--include-package=uvicorn",
                # Noinclude / nofollow
                "--noinclude-numba-mode=nofollow",  # only include if imported directly
                # Excludes — bloat not used by the project
                "--nofollow-import-to=gradio",
                "--nofollow-import-to=gradio_client",
                "--nofollow-import-to=pandas",
                "--nofollow-import-to=sklearn",
                # Python flags
                "--python-flag=no_site",
                # Module parameters
                "--module-parameter=numba-disable-jit=yes",
                "--module-parameter=torch-disable-jit=yes",
                # Platform
                "--windows-console-mode=attach",
                "--zig",
                # Download policy
                "--assume-yes-for-downloads",
                # Entry point
                str(entry_point),
            ]
            log(f"Entry point: {entry_point}")
            log(f"Output:     {output_path}")

        with StageTimer("Compile", "Compiling with Nuitka (30-60 min)"):
            nuitka_proc = subprocess.Popen(
                nuitka_args, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            stream_thread = threading.Thread(
                target=stream_output, args=(nuitka_proc, "[nuitka] ")
            )
            stream_thread.start()
            try:
                nuitka_proc.wait()
                stream_thread.join()
            except KeyboardInterrupt:
                log("\n[CANCEL] Build cancelled by user. Terminating Nuitka...")
                nuitka_proc.terminate()
                try:
                    nuitka_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    nuitka_proc.kill()
                stream_thread.join()
                sys.exit(130)  # 128 + 2 (SIGINT)

        if nuitka_proc.returncode == 0:
            size_mb = output_path.stat().st_size / 1024 / 1024
            log(f"Build successful: {output_path}")
            log(f"Size: {size_mb:.1f} MB")
        elif nuitka_proc.returncode == -2:
            pass  # Already handled by KeyboardInterrupt handler above
        else:
            log("Build failed", nuitka_proc.returncode)
            sys.exit(1)


if __name__ == "__main__":
    check_dependencies()
    build_windows()
