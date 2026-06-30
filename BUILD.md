# Guía de Construcción

`tts-sidecar` se compila con **Nuitka** (Python → C → binario) para obtener un ejecutable standalone multiplataforma.

## Requisitos

- **Python 3.13+** ([python.org](https://www.python.org/downloads/))
- **Nuitka** (`pip install nuitka`)
- **Visual Studio Build Tools 2022** (Windows) con:
  - "Desktop development with C++"
  - Windows 11 SDK

## Plataformas Soportadas

| Plataforma | Comando | Output |
|------------|---------|--------|
| Windows x64 | `npm run build-windows` | `bin/win32-x64/tts-sidecar.exe` |
| Linux x64 | `npm run build-linux` | `bin/linux-x64/tts-sidecar` |
| Linux ARM64 | `npm run build-linux-arm64` | `bin/linux-arm64/tts-sidecar` |
| macOS Intel | `npm run build-darwin` | `bin/darwin-x64/tts-sidecar` |
| macOS Apple Silicon | `npm run build-darwin-arm64` | `bin/darwin-arm64/tts-sidecar` |

## Compilación

### Rápido (usa Nuitka)

```bash
# Windows
npm run build-windows

# Linux
npm run build-linux

# macOS
npm run build-darwin
```

El script `scripts/build_windows.py` ejecuta:

```bash
python -m nuitka --standalone --onefile \
  --enable-plugin=anti-bloat \
  --windows-icon=assets/icon.ico \
  --output-dir=bin \
  bin/tts-sidecar
```

## Verificación

Después de compilar:

```bash
bin/win32-x64/tts-sidecar.exe version
bin/win32-x64/tts-sidecar.exe doctor
```

## Paquetes Excluidos (Bloat)

Los siguientes paquetes son dependencias transitivas de `chatterbox-tts` pero no son usados por el código local y están excluidos del build:

| Paquete | Razón | Tamaño estimado |
|---------|--------|----------------|
| `gradio` + 1865 archivos | No usado por el proyecto | ~50-100 MB |
| `gradio_client` | No usado por el proyecto | ~20 MB |
| `pandas` + templates | Dependencia de gradio | ~30 MB |
| `sklearn` + 4 DLLs | Dependencia de scipy/numba | ~30 MB |
| `numba` (JIT disabled) | Dependencia de librosa, JIT deshabilitado en standalone | ~50 MB |
| `onnx` + `onnxruntime` | No usado por chatterbox | ~100 MB |

## Notas de Dependencias

### soundfile

`soundfile` es un módulo de archivo único (`soundfile.py`, ~1700 líneas) que usa CFFI para bindings nativos. Nuitka incluye automáticamente `_soundfile_data/` (datos CFFI).

### pycaw

`pycaw` es una librería de solo Windows para audio. Está incluida en el build para el comando `devices`.

### numba

numba tiene JIT deshabilitado en standalone mode. Esto puede afectar el rendimiento de algunas funciones de audio de `librosa`, pero no causa crashes.

### Zoneinfo

La estándar library `zoneinfo` añade ~5 MB al payload. Esto es necesario para algunas funcionalidades de Python.
