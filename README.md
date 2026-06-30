# Chatterbox TTS

Sistema de síntesis de voz (TTS) **100% local** con clonación de voz en **español latinoamericano**.

- **Motor**: Chatterbox Multilingual V3 (MIT, 23+ idiomas)
- **Clonación de voz**: Usa tu propia voz como referencia
- **Multiplataforma**: Windows, Linux, macOS (x64 y ARM64)
- **Consumible via CLI**: Invocable desde cualquier lenguaje de programación

## Características

- **Clonación de voz**: ~10 segundos de audio de referencia
- **100% offline**: Sin APIs externas ni conexiones a internet
- **Single-file installer**: Un ejecutable por plataforma
- **CLI universal**: `subprocess.run(["./tts-sidecar", "speak", "--text", "..."])`
- **Audio nativo**: APIs nativas del sistema operativo

## Instalación

### Opción 1: Descargar binario pre-compilado

Descarga el ejecutable para tu plataforma desde [Releases](https://github.com/resemble-ai/tts-sidecar/releases):

```bash
# Windows
tts-sidecar-windows.exe install

# Linux
chmod +x tts-sidecar-linux-x86_64
./tts-sidecar-linux-x86_64 install

# macOS
chmod +x tts-sidecar-macos-universal2
./tts-sidecar-macos-universal2 install
```

### Opción 2: Compilar desde código

```bash
# Instalar dependencias de build
pip install -r requirements.txt

# Compilar
python scripts/build_windows.py    # Windows
python scripts/build_linux.py     # Linux
python scripts/build_macos.py     # macOS
```

## Uso Rápido

### Clonación de voz

```bash
# Agregar tu voz (requiere ~10 segundos de audio en español)
# Se necesitan DOS archivos: reference (timbre) y speech (conditioning)
tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav

# Sintetizar con tu voz clonada
tts-sidecar speak --text "Hola mundo" -v mi_voz

# Generar archivo WAV
tts-sidecar synthesize --text "Hola mundo" -v mi_voz --output audio.wav
```

### Síntesis básica

```bash
# Sintetizar y reproducir
tts-sidecar speak --text "Hola mundo"

# Generar archivo WAV
tts-sidecar synthesize --text "Hola mundo" --output audio.wav
```

### Comandos disponibles

```bash
tts-sidecar speak --text "..."          # Sintetizar y reproducir
tts-sidecar synthesize --text "..."    # Generar archivo WAV
tts-sidecar voice-add --name X --reference ref.wav --speech speech.wav  # Agregar voz clonada
tts-sidecar voice-remove --name X      # Eliminar voz
tts-sidecar voices                     # Listar voces
tts-sidecar devices                    # Dispositivos de audio
tts-sidecar doctor                     # Diagnóstico
tts-sidecar install                    # Descargar modelo
```

## Invocación desde cualquier lenguaje

```bash
# Bash/shell
./tts-sidecar speak --text "Hola mundo"

# Python
subprocess.run(["./tts-sidecar", "speak", "--text", "Hola mundo"])

# Node.js
child_process.spawn("./tts-sidecar", ["speak", "--text", "Hola mundo"])

# Rust
std::process::Command::new("./tts-sidecar")
    .args(["speak", "--text", "Hola"])
    .output()?;

# Go
exec.Command("./tts-sidecar", "speak", "--text", "Hola")

# Java
new ProcessBuilder("./tts-sidecar", "speak", "--text", "Hola").start()
```

## Arquitectura

```
┌─────────────────────────────────────────────────────┐
│              tts-sidecar (CLI binary)                │
│   Built with Nuitka: single-file, no dependencies   │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                 │
│   Model: ResembleAI/chatterbox-multilingual         │
│   License: MIT                                      │
│   Languages: 23+ (incl. Spanish es)                  │
└─────────────────────────────────────────────────────┘
```

## Licencia

MIT — Uso comercial libre.

## Documentación

- [docs/goal.md](docs/goal.md) - Meta del proyecto
- [docs/design.md](docs/design.md) - Diseño técnico
- [docs/daemon-mode.md](docs/daemon-mode.md) - Daemon mode (servidor persistente)
