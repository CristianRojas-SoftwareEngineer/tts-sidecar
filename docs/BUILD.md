# Guía de Construcción

`tts-sidecar` se compila con **Nuitka** (Python → C → binario) para obtener un ejecutable standalone multiplataforma.

---

## 1. Requisitos

- **Python 3.13+** ([python.org](https://www.python.org/downloads/))
- **Nuitka** (`pip install nuitka==4.1.3`)
- **Visual Studio Build Tools 2022** (Windows) con:
  - "Desktop development with C++"
  - Windows 11 SDK
- **macOS**: Command Line Tools for Xcode
- **Linux**: GCC y dependencias de Python

---

## 2. Plataformas Soportadas

| Plataforma | Comando | Output |
|------------|---------|--------|
| Windows x64 | `npm run build-windows` | `bin/win32-x64/tts-sidecar.exe` |
| Linux x64 | `npm run build-linux` | `bin/linux-x64/tts-sidecar` |
| Linux ARM64 | `npm run build-linux-arm64` | `bin/linux-arm64/tts-sidecar` |
| macOS Intel | `npm run build-darwin` | `bin/darwin-x64/tts-sidecar` |
| macOS Apple Silicon | `npm run build-darwin-arm64` | `bin/darwin-arm64/tts-sidecar` |

---

## 3. Compilación Local

### Verificación de Sintaxis (py_compile)

Antes de compilar, se puede verificar que el código Python no tenga errores de sintaxis:

```bash
# Verificar todos los archivos Python del proyecto
python -m py_compile src/chatterbox_tts/engine.py
python -m py_compile src/chatterbox_tts/cli.py
python -m py_compile src/chatterbox_tts/audio.py
python -m py_compile src/chatterbox_tts/timing.py
python -m py_compile src/chatterbox_tts/daemon/*.py
```

Esto genera archivos `.pyc` en el directorio `__pycache__/` de cada módulo.

### Scripts de Build

```bash
# Windows
npm run build-windows

# Linux
npm run build-linux

# macOS
npm run build-darwin
```

Los scripts de build (`scripts/build_*.py`) ejecutan Nuitka con las opciones configuradas.

### Opciones de Nuitka

```bash
python -m nuitka --standalone --onefile \
  --enable-plugin=anti-bloat \
  --windows-icon=assets/icon.ico \
  --output-dir=bin \
  bin/tts-sidecar
```

### Verificación

Después de compilar:

```bash
bin/win32-x64/tts-sidecar.exe version
bin/win32-x64/tts-sidecar.exe doctor
```

---

## 4. CI/CD con CircleCI

El pipeline de CircleCI compila el proyecto para todas las plataformas automáticamente.

### Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                      Pipeline                                 │
│                   (multijob)                                │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-win64  │  │build-lin64  │  │build-linarm │          │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘          │
│         │                 │                 │                 │
│         ▼                 ▼                 ▼                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │build-darwin │  │build-darwin │                          │
│  │    x64      │  │   arm64     │                          │
│  └─────────────┘  └─────────────┘                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Jobs

| Job | Plataforma | Executor | Notas |
|-----|------------|----------|-------|
| `build-windows` | Windows x64 | windows-server | Nuitka onefile |
| `build-linux-x64` | Linux x64 | ubuntu | Nuitka onefile |
| `build-linux-arm64` | Linux ARM64 | ubuntu | Cross-compile |
| `build-darwin-x64` | macOS Intel | macos | Nuitka onefile |
| `build-darwin-arm64` | macOS Apple Silicon | macos | Nuitka onefile |

### Workflow

```yaml
workflows:
  version: 2
  build-all:
    jobs:
      - build-windows
      - build-linux-x64
      - build-linux-arm64
      - build-darwin-x64
      - build-darwin-arm64
```

El archivo de configuración completo está en `.circleci/config.yml`.

---

## 5. Distribución de Binarios

Los binarios compilados se almacenan en `bin/<platform>/`:

```bash
bin/
├── win32-x64/
│   └── tts-sidecar.exe
├── linux-x64/
│   └── tts-sidecar
├── linux-arm64/
│   └── tts-sidecar
├── darwin-x64/
│   └── tts-sidecar
└── darwin-arm64/
    └── tts-sidecar
```

---

## 6. Paquetes Excluidos (Bloat)

Los siguientes paquetes son dependencias transitivas de `chatterbox-tts` pero no son usados por el código local y están excluidos del build:

| Paquete | Razón | Tamaño estimado |
|---------|--------|----------------|
| `gradio` + 1865 archivos | No usado por el proyecto | ~50-100 MB |
| `gradio_client` | No usado por el proyecto | ~20 MB |
| `pandas` + templates | Dependencia de gradio | ~30 MB |
| `sklearn` + 4 DLLs | Dependencia de scipy/numba | ~30 MB |
| `numba` (JIT disabled) | Dependencia de librosa, JIT deshabilitado en standalone | ~50 MB |
| `onnx` + `onnxruntime` | No usado por chatterbox | ~100 MB |

---

## 7. Notas de Dependencias

### soundfile

`soundfile` es un módulo de archivo único (`soundfile.py`, ~1700 líneas) que usa CFFI para bindings nativos. Nuitka incluye automáticamente `_soundfile_data/` (datos CFFI).

### pycaw

`pycaw` es una librería de solo Windows para audio. Está incluida en el build para el comando `devices`.

### numba

numba tiene JIT deshabilitado en standalone mode. Esto puede afectar el rendimiento de algunas funciones de audio de `librosa`, pero no causa crashes.

### Zoneinfo

La estándar library `zoneinfo` añade ~5 MB al payload. Esto es necesario para algunas funcionalidades de Python.

---

## 8. Notas Importantes

- **Nuitka onefile**: El binario incluye el interpreter de Python embebido
- **Tamaño**: Los binarios Nuitka son más grandes (~100-200MB) pero no requieren Python instalado
- **macOS**: Los binarios deben ser firmados/notarized para distribución fuera de App Store
- **Windows**: El binario es autocontenido y no requiere Visual Studio
- **Linux**: Requiere GCC para compilar las extensiones C de Nuitka

---

## 9. Troubleshooting

### Windows: "Visual Studio not found"
```powershell
# Instalar Visual Studio Build Tools
winget install Microsoft.VisualStudio.2022.BuildTools
```

### macOS: "clang error"
```bash
# Instalar Command Line Tools
xcode-select --install
```

### Linux: "gcc not found"
```bash
# Ubuntu/Debian
sudo apt-get install build-essential

# CentOS/RHEL
sudo yum groupinstall "Development Tools"
```
