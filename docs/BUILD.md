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
| Windows x64 | `npm run build-windows` | `dist/tts-sidecar.exe` |
| Linux x64 | `npm run build-linux` | `dist/tts-sidecar-linux-x86_64` |
| Linux ARM64 | `python scripts/build_linux.py --arch arm64` | `dist/tts-sidecar-linux-aarch64` |
| macOS universal2 | `npm run build-macos` | `dist/tts-sidecar-macos-universal2` |

> El script de macOS compila por defecto un binario **universal2** (x86_64 + arm64).
> Se puede acotar la arquitectura con `python scripts/build_macos.py --arch {x86_64\|arm64\|universal2}`.

---

## 3. Compilación Local

### Verificación de Sintaxis (py_compile)

`py_compile` es parte de la **biblioteca estándar de Python**. No es una dependencia extra - viene incluido con Python automáticamente.

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
npm run build-macos
```

Los scripts de build (`scripts/build_*.py`) ejecutan Nuitka con las opciones configuradas.

> El entry point `bin/tts-sidecar` (un script Python sin extensión) es la semilla que Nuitka
> compila. El binario resultante hereda ese nombre: `tts-sidecar.exe` en Windows (donde la
> extensión es obligatoria) y `tts-sidecar-*` sin extensión en Linux/macOS. Véase
> `docs/ARCHITECTURE.md` para el detalle del entry point y el shebang.

### Opciones de Nuitka

```bash
python -m nuitka --standalone --onefile \
  --enable-plugin=anti-bloat \
  --windows-icon=assets/icon.ico \
  --output-dir=dist \
  bin/tts-sidecar
```

### Verificación

Después de compilar:

```bash
dist/tts-sidecar.exe version
dist/tts-sidecar.exe doctor
```

---

## 4. CI/CD con CircleCI

El pipeline de CircleCI ejecuta los tests y, si pasan, compila el proyecto para todas las
plataformas automáticamente. El job `test` actúa como **puerta**: cada build depende de él
(`requires: [test]`), de modo que no se empaqueta ningún binario si la suite falla.

### Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                         test                                 │
│              (pytest tests/ — puerta previa)                 │
└───────┬───────────────┬───────────────┬───────────────┬─────┘
        │               │               │               │
        ▼               ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│build-windows│ │build-linux- │ │build-linux- │ │ build-darwin-    │
│             │ │    x64      │ │   arm64     │ │   universal2     │
└─────────────┘ └─────────────┘ └─────────────┘ └──────────────────┘
```

### Jobs

| Job | Plataforma | Executor | Notas |
|-----|------------|----------|-------|
| `test` | — | docker `cimg/python:3.13` | `pytest tests/` (puerta previa) |
| `build-windows` | Windows x64 | `win/server-2022` (orb `circleci/windows`) | Nuitka onefile nativo |
| `build-linux-x64` | Linux x64 | docker `cimg/python:3.13` | Nuitka onefile |
| `build-linux-arm64` | Linux ARM64 | machine `arm.medium` | Nuitka onefile nativo (ARM real) |
| `build-darwin-universal2` | macOS universal2 | macos `m4pro.medium` (Xcode 26.4.0) | Nuitka onefile (x86_64 + arm64) |

> **Nota de plataforma**: CircleCI retiró los runners macOS Intel (jun-2024) y los M1/M2
> (EOL feb-2026), por lo que macOS se compila en Apple Silicon (`m4pro.medium`) como un único
> binario `universal2`. Las builds ARM64 de Linux requieren el **machine executor**
> (`arm.medium`); el Docker executor no soporta resource classes ARM.

### Workflow

```yaml
workflows:
  build-all:
    jobs:
      - test
      - build-windows:
          requires:
            - test
      - build-linux-x64:
          requires:
            - test
      - build-linux-arm64:
          requires:
            - test
      - build-darwin-universal2:
          requires:
            - test
```

El archivo de configuración completo está en `.circleci/config.yml`.

---

## 5. Distribución de Binarios

Los binarios compilados se almacenan en `dist/`:

```bash
dist/
├── tts-sidecar.exe                  # Windows x64
├── tts-sidecar-linux-x86_64         # Linux x64
├── tts-sidecar-linux-aarch64        # Linux ARM64
└── tts-sidecar-macos-universal2     # macOS (x86_64 + arm64)
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
