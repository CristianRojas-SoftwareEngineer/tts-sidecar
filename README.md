# Chatterbox TTS

Sistema de síntesis de voz (TTS) **100% local** con clonación de voz en **español latinoamericano**.

- **Motor**: Chatterbox Multilingual V3 ([modelo MIT](https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-mx-latam), 23+ idiomas)
- **Clonación de voz**: Usa tu propia voz como referencia
- **Multiplataforma**: Windows x64, Linux x64/ARM64, macOS ARM64 (Apple Silicon)
- **Consumible via CLI**: Invocable desde cualquier lenguaje de programación

## Uso ético y responsable

`tts-sidecar` clona voces arbitrarias y **el audio que genera no lleva marca de
agua** (el watermark de PerthNet está desactivado), por lo que no es distinguible
por medios técnicos de una grabación real. Esto exige un uso responsable:

- **Consentimiento**: clona únicamente voces para las que tengas permiso explícito
  de la persona titular. No clones la voz de nadie sin su autorización.
- **No suplantación**: no uses la herramienta para hacerte pasar por otra persona,
  cometer fraude, difamar, ni producir contenido engañoso.
- **Divulgación**: al publicar o compartir audio sintetizado, indícalo como tal.
  Recuerda que el audio no contiene marca de agua que lo identifique.
- **Reporte**: si detectas un uso indebido de este proyecto, repórtalo abriendo un
  [Issue](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/issues).

El proyecto no impone barreras técnicas (fácilmente sorteables en software libre):
la responsabilidad del uso legítimo recae en quien lo emplea.

## Características

- **Clonación de voz**: ~10 segundos de audio de referencia
- **100% offline**: Sin APIs externas ni conexiones a internet
- **Instalador por plataforma**: Un instalador único por SO que despliega el bundle PyInstaller `--onedir` (carpeta de la aplicación)
- **CLI universal**: `subprocess.run(["./tts-sidecar", "speak", "--text", "..."])`
- **Audio nativo**: APIs nativas del sistema operativo

## Instalación

### Opción 1: Descargar binario pre-compilado

Descarga el ejecutable para tu plataforma desde [Releases](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/releases):

```bash
# Windows: ejecuta el instalador tts-sidecar-<versión>-x86_64-setup.exe.
# Agrega tts-sidecar al PATH, muestra una página informativa sobre el modelo y
# ofrece una casilla para descargarlo (ejecuta 'tts-sidecar setup') al terminar.

# Linux: descarga el AppImage de tu arquitectura, hazlo ejecutable y provisiona
chmod +x tts-sidecar-<versión>-x86_64.AppImage    # o -aarch64.AppImage en ARM64
./tts-sidecar-<versión>-x86_64.AppImage setup
# → setup también crea el symlink ~/.local/bin/tts-sidecar para invocarlo por nombre

# macOS (Apple Silicon): monta tts-sidecar-<versión>-arm64.dmg, arrastra el .app
# a Aplicaciones y ejecuta el script "Instalar (PATH + modelo).command" incluido
# en el volumen. El script pide tu contraseña de administrador (sudo) para crear
# el symlink en /usr/local/bin y luego ofrece ejecutar 'setup' como tu usuario.
```

> Mac Intel (x86_64) no está soportado: el toolchain actual (torch≥2.3) no
> publica wheels macOS x86_64.

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
# Sintetizar y reproducir con la voz de fábrica 'default' (no requiere audios)
tts-sidecar speak --text "Hola mundo"

# Sobrescribir la voz por defecto con una voz registrada
tts-sidecar speak --text "Hola mundo" --voice mi_voz

# Generar archivo WAV
tts-sidecar speak --text "Hola mundo" --output audio.wav
```

> Sin `--voice` ni audios explícitos, `speak` usa la voz de fábrica **`default`**
> (empaquetada, de solo lectura). Ver [Modelo de voces](#modelo-de-voces).

### Modelo de voces

Las voces se resuelven en **dos niveles**, con precedencia usuario→fábrica:

- **Fábrica**: empaquetadas en el ejecutable (solo lectura), incluida la voz
  `default`. Idénticas en desarrollo y en cualquier instalación.
- **Usuario**: registradas con `voice add`, escribibles, guardadas en el
  directorio de datos de usuario por SO (estables entre ejecuciones).

Registrar una voz de usuario con el mismo nombre que una de fábrica la sobrescribe.

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

El **modelo de voz** Chatterbox Multilingual V3 se distribuye bajo licencia
[**MIT**](https://huggingface.co/ResembleAI/Chatterbox-Multilingual-es-mx-latam) (verificada
en HuggingFace), al igual que el modelo base
[`ResembleAI/chatterbox`](https://huggingface.co/ResembleAI/chatterbox). Las **dependencias**
empaquetadas conservan sus propias licencias, en su mayoría permisivas (MIT/BSD/Apache 2.0),
con algunas de copyleft compatible con GPLv3 (MPL-2.0, LGPL-2.1+, GPLv3+) y los runtimes
propietarios redistribuibles de NVIDIA CUDA en el build de Linux. El detalle completo y
verificado está en [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).

## Documentación

- [docs/GOAL.md](docs/GOAL.md) - Meta del proyecto
- [docs/DESIGN.md](docs/DESIGN.md) - Diseño técnico
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) - Arquitectura del sistema
- [docs/DAEMON-MODE.md](docs/DAEMON-MODE.md) - Daemon mode (servidor persistente)
- [docs/BUILD.md](docs/BUILD.md) - Guía de compilación PyInstaller

## Comunidad y soporte

- [CHANGELOG.md](CHANGELOG.md) - Historial de cambios por versión
- [CONTRIBUTING.md](CONTRIBUTING.md) - Cómo contribuir (setup, tests, estilo, flujo de PR)
- [SECURITY.md](SECURITY.md) - Política de seguridad y cómo reportar vulnerabilidades
- [Issues](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/issues) - Reporte de bugs y solicitudes de función
