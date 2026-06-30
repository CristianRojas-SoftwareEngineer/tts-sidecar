# CI/CD Build Pipeline

Este documento describe el pipeline de CI/CD para compilar `tts-sidecar` en múltiples plataformas usando CircleCI y Nuitka.

## Arquitectura del Pipeline

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

## Plataformas Soportadas

| Job | Plataforma | Compilador | Executor | Notas |
|-----|------------|------------|----------|-------|
| `build-windows` | Windows x64 | Nuitka + MSVC | windows-server | Nuitka onefile |
| `build-linux-x64` | Linux x64 | Nuitka + GCC | ubuntu | Nuitka onefile |
| `build-linux-arm64` | Linux ARM64 | Nuitka + GCC | ubuntu | Cross-compile |
| `build-darwin-x64` | macOS Intel | Nuitka + Clang | macos | Nuitka onefile |
| `build-darwin-arm64` | macOS Apple Silicon | Nuitka + Clang | macos | Nuitka onefile |

## Configuración

### Requisitos del Proyecto

1. **Python 3.13+** con Nuitka instalado:
   ```bash
   pip install nuitka==4.1.3
   ```

2. **Visual Studio Build Tools 2022** (Windows) con:
   - "Desktop development with C++"
   - Windows 11 SDK

3. **macOS**: Command Line Tools for Xcode

4. **Linux**: GCC y dependencias de Python

## Estructura del Proyecto para Build

```
tts-sidecar/
├── .circleci/
│   └── config.yml           # Configuración CircleCI
├── bin/
│   └── tts-sidecar           # Entry point
├── src/
│   └── chatterbox_tts/       # Python package
├── scripts/
│   ├── build_windows.py
│   ├── build_linux.py
│   └── build_macos.py
├── nuitka/
│   └── tts-sidecar.spec      # Nuitka spec file
└── pyproject.toml
```

## Configuración de CircleCI

El archivo de configuración está en `.circleci/config.yml`.

### Jobs

#### build-windows
```yaml
build-windows:
  docker:
    - image: cimg/python:3.13
  steps:
    - checkout
    - python/install-packages:
        package-manager: pip
        pip-dependency-file: requirements.txt
    - run:
        name: Install Nuitka
        command: pip install nuitka==4.1.3
    - run:
        name: Build Windows
        command: python scripts/build_windows.py
    - store_artifacts:
        path: bin/win32-x64/tts-sidecar.exe
        destination: tts-sidecar-win32-x64.exe
```

#### build-linux-x64
```yaml
build-linux-x64:
  docker:
    - image: cimg/python:3.13
  steps:
    - checkout
    - python/install-packages:
        package-manager: pip
        pip-dependency-file: requirements.txt
    - run:
        name: Install Nuitka
        command: pip install nuitka==4.1.3
    - run:
        name: Install Linux dependencies
        command: |
          sudo apt-get update
          sudo apt-get install -y patchelf
    - run:
        name: Build Linux x64
        command: python scripts/build_linux.py --arch x86_64
    - store_artifacts:
        path: bin/linux-x64/tts-sidecar
        destination: tts-sidecar-linux-x64
```

#### build-linux-arm64
```yaml
build-linux-arm64:
  docker:
    - image: cimg/python:3.13
  steps:
    - checkout
    - python/install-packages:
        package-manager: pip
        pip-dependency-file: requirements.txt
    - run:
        name: Install Nuitka
        command: pip install nuitka==4.1.3
    - run:
        name: Install Linux dependencies
        command: |
          sudo apt-get update
          sudo apt-get install -y patchelf gcc-aarch64-linux-gnu g++-aarch64-linux-gnu
    - run:
        name: Build Linux ARM64
        command: python scripts/build_linux.py --arch arm64
    - store_artifacts:
        path: bin/linux-arm64/tts-sidecar
        destination: tts-sidecar-linux-arm64
```

#### build-darwin-x64
```yaml
build-darwin-x64:
  macos:
    xcode: "15.0"
  steps:
    - checkout
    - run:
        name: Set up Python
        command: |
          python3 --version
          python3 -m pip install --upgrade pip
          pip3 install -r requirements.txt
    - run:
        name: Install Nuitka
        command: pip3 install nuitka==4.1.3
    - run:
        name: Build macOS x64
        command: python3 scripts/build_macos.py --arch x86_64
    - store_artifacts:
        path: bin/darwin-x64/tts-sidecar
        destination: tts-sidecar-darwin-x64
```

#### build-darwin-arm64
```yaml
build-darwin-arm64:
  macos:
    xcode: "14.0"
  steps:
    - checkout
    - run:
        name: Set up Python
        command: |
          python3 --version
          python3 -m pip install --upgrade pip
          pip3 install -r requirements.txt
    - run:
        name: Install Nuitka
        command: pip3 install nuitka==4.1.3
    - run:
        name: Build macOS ARM64
        command: python3 scripts/build_macos.py --arch arm64
    - store_artifacts:
        path: bin/darwin-arm64/tts-sidecar
        destination: tts-sidecar-darwin-arm64
```

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

## Distribución de Binarios

Los binarios compilados se almacenan en `bin/<platform>/`:

```bash
# Estructura final
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

## Notas Importantes

- **Nuitka onefile**: El binario incluye el interpreter de Python embebido
- **Tamaño**: Los binarios Nuitka son más grandes (~100-200MB) pero no requieren Python instalado
- **macOS**: Los binarios deben ser firmados/notarized para distribución fuera de App Store
- **Windows**: El binario es autocontenido y no requiere Visual Studio
- **Linux**: Requiere GCC para compilar las extensiones C de Nuitka

## Troubleshooting

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
