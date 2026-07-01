# Chatterbox TTS

Sistema de síntesis de voz (TTS) **100% local** con clonación de voz en **español latinoamericano**.

- **Motor**: Chatterbox Multilingual V3 (MIT, 23+ idiomas)
- **Clonación de voz**: Usa tu propia voz como referencia
- **Multiplataforma**: Windows, Linux, macOS (x64 y ARM64)
- **Consumible via CLI**: Invocable desde cualquier lenguaje de programación

## Características

- **Clonación de voz**: ~10 segundos de audio de referencia
- **100% offline**: Sin APIs externas ni conexiones a internet
- **Instalador por plataforma**: Un instalador único por SO que despliega el bundle PyInstaller `--onedir` (carpeta de la aplicación)
- **CLI universal**: `subprocess.run(["./tts-sidecar", "speak", "--text", "..."])`
- **Audio nativo**: APIs nativas del sistema operativo

## Instalación

### Opción 1: Descargar binario pre-compilado

Descarga el ejecutable para tu plataforma desde [Releases](https://github.com/resemble-ai/tts-sidecar/releases):

```bash
# Windows (instalador): ejecuta el .exe del instalador. Agrega tts-sidecar al PATH,
# muestra una página informativa sobre el modelo y ofrece una casilla para
# descargarlo (ejecuta 'tts-sidecar setup') al terminar.

# Linux: deja el binario accesible (p. ej. en el PATH) y provisiona el modelo
chmod +x tts-sidecar-linux-x86_64
./tts-sidecar-linux-x86_64 setup

# macOS: igual que Linux
chmod +x tts-sidecar-macos-universal2
./tts-sidecar-macos-universal2 setup
```

### Provisión del modelo (`setup`)

El modelo de voz **`es-mx-latam`** (varios cientos de MB) **no** viene incluido en
el ejecutable: se descarga una sola vez a la caché de HuggingFace de tu usuario
(`~/.cache/huggingface/hub`). Esto es homólogo en los 3 SO:

- **Windows**: el instalador ofrece una casilla post-instalación que ejecuta
  `setup` por ti, en tu contexto de usuario.
- **Linux / macOS**: ejecuta `tts-sidecar setup` manualmente tras instalar.

`setup` corre los chequeos de entorno (igual que `doctor`) y descarga el modelo
solo si falta; si ya está cacheado, termina al instante sin descargar. Hasta que
el modelo esté provisionado, `speak` y `daemon start` **fallan de inmediato** y te
remiten a `tts-sidecar setup` (nunca disparan una descarga silenciosa).

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
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav

# Sintetizar con tu voz clonada
tts-sidecar speak --text "Hola mundo" -v mi_voz

# Generar archivo WAV (speak con --output guarda en vez de reproducir)
tts-sidecar speak --text "Hola mundo" -v mi_voz --output audio.wav
```

### Síntesis básica

```bash
# Sintetizar y reproducir
tts-sidecar speak --text "Hola mundo"

# Generar archivo WAV
tts-sidecar speak --text "Hola mundo" --output audio.wav
```

### Comandos disponibles

```bash
tts-sidecar speak --text "..."          # Sintetizar y reproducir (--output guarda a WAV)
tts-sidecar voice add --name X --reference ref.wav --speech speech.wav  # Agregar voz clonada
tts-sidecar voice remove --name X       # Eliminar voz
tts-sidecar voice list                  # Listar voces (--json disponible)
tts-sidecar devices                     # Dispositivos de audio (--json disponible)
tts-sidecar doctor                      # Diagnóstico (--json disponible)
tts-sidecar setup                       # Provisionar: chequeos + descargar modelo si falta
tts-sidecar version                     # Versión (--json disponible)
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
│              tts-sidecar (binario CLI)              │
│   Compilado con PyInstaller --onedir (carpeta de app) │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│           Chatterbox Multilingual V3                 │
│   Modelo: es-mx-latam (caché de HuggingFace)        │
│   Licencia: MIT                                     │
│   Idiomas: 23+ (incl. español es)                    │
└─────────────────────────────────────────────────────┘
```

## Licencia

**GPL-3.0-or-later** — el código de `tts-sidecar` se distribuye bajo la GNU General Public
License v3 (ver [LICENSE](LICENSE)). Es software libre y de uso comercial permitido, con la
condición copyleft de que los trabajos derivados que se distribuyan se liberen bajo la misma
licencia.

El **modelo de voz** Chatterbox Multilingual V3 y todas las **dependencias** empaquetadas
conservan sus propias licencias permisivas (MIT/BSD/Apache 2.0), compatibles con GPLv3. El
detalle de atribuciones está en [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).

## Documentación

- [docs/GOAL.md](docs/GOAL.md) - Meta del proyecto
- [docs/DESIGN.md](docs/DESIGN.md) - Diseño técnico
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arquitectura del sistema
- [docs/DAEMON-MODE.md](docs/DAEMON-MODE.md) - Daemon mode (servidor persistente)
- [docs/BUILD.md](docs/BUILD.md) - Guía de compilación PyInstaller
