# Goal: Sistema TTS con Chatterbox Multilingual V3

---

## Objetivo

Obtener un sistema TTS **100% local** con audio nativo por sistema operativo, para transformar texto a audio en **español latino** de la mejor calidad disponible, con **licencia MIT**.

Motor TTS: **Chatterbox Multilingual V3** (ResembleAI) — 23+ idiomas, clonación de voz, licencia MIT.

**El sistema debe ser consumible via línea de comandos** para que cualquier aplicación en cualquier lenguaje de programación pueda invocarlo (Python, JavaScript/Node, Rust, Go, Java, C#, etc.)

---

## Requisitos del instalador

- **Un solo instalador por SO**: Windows (.exe), Linux (.AppImage/.bin), macOS (.app)
- **Cero dependencias externas**: El usuario final no instala Python, Node, Rust ni nada más
- **Descarga + instalación + configuración** en un solo paso
- **Audio nativo**: playback usando APIs nativas de cada SO

---

## Alcance

Implementar y validar la síntesis en español latinoamericano con voz propia del usuario usando Chatterbox Multilingual V3.

---

## Estructura del proyecto migrado

```
tts-sidecar/
├── src/
│   └── chatterbox_tts/       # Python package
│       ├── __init__.py
│       ├── engine.py         # Wrapper de Chatterbox
│       ├── audio.py          # Audio playback nativo
│       ├── cli.py            # Interfaz CLI
│       ├── timing.py         # Instrumentation y timing
│       └── daemon/           # Daemon mode (FastAPI + IPC)
│           ├── daemon.py    # Lifecycle manager
│           ├── server.py    # FastAPI endpoints
│           ├── ipc.py       # HTTP client
│           ├── protocol.py  # Pydantic models
│           └── run.py       # Entry point
├── bin/
│   └── tts-sidecar          # Entry point script
├── scripts/                  # Build scripts por SO
├── models/                   # Modelos Chatterbox
└── docs/
```

---

## Comandos CLI objetivo (invocable desde cualquier lenguaje)

```bash
# 1. Instalación (primera vez - descarga el modelo)
./tts-sidecar install

# 2. Verificación (diagnóstico del sistema)
./tts-sidecar doctor
./tts-sidecar version
./tts-sidecar devices

# 3. Clonación de voz (requiere dos archivos de audio)
./tts-sidecar voice-add --name mi_voz --reference timbre.wav --speech condicion.wav

# 4. Listar voces registradas
./tts-sidecar voices

# 5. Síntesis y reproducción (usar voz clonada)
./tts-sidecar speak --text "Hola mundo" -v mi_voz

# 6. Síntesis a archivo (exportar WAV)
./tts-sidecar synthesize --text "Hola mundo" -v mi_voz --output audio.wav

# 7. Síntesis básica (sin clonación)
./tts-sidecar speak --text "Hola mundo"
./tts-sidecar synthesize --text "Hola mundo" --output audio.wav

# 8. Daemon mode (mantiene modelo en memoria para respuestas más rápidas)
./tts-sidecar daemon start
./tts-sidecar daemon status
./tts-sidecar daemon stop

# 9. Eliminar voz clonada
./tts-sidecar voice-remove --name mi_voz
```

---

## Restricciones

- **100% local**: Sin APIs externas ni conexiones a internet para síntesis
- **Instalador único por SO**: Un archivo ejecutable por plataforma
- **Sin dependencias externas**: El usuario final no necesita instalar nada más
- **Licencia MIT**: Todo el código y modelos usados deben ser MIT

---

## Criterios de Aceptación

1. [x] El instalador de Windows (.exe) funciona en Windows 10/11 sin dependencias
2. [x] El instalador de Linux funciona en distribuciones principales
3. [x] El instalador de macOS funciona en macOS 12+
4. [x] `tts-sidecar speak --text "Hola mundo"` reproduce audio en español
5. [x] `tts-sidecar voice-add --name test --reference ref.wav --speech speech.wav` clona la voz
6. [x] El audio generado suena en español con las características de la voz de referencia
7. [x] El español latinoamericano suena natural y con buena prosodia
8. [x] La síntesis funciona sin conexión a internet (modelo en local)
9. [x] El instalador incluye todo lo necesario (no requiere instalaciones adicionales)

---

## Condición de Finalización

La implementación está completa únicamente cuando:

- [x] El motor Chatterbox Multilingual V3 está implementado y funcional
- [x] La clonación de voz funciona con una muestra de ~10 segundos
- [x] El audio generado preserva las características de la voz original
- [x] El español latinoamericano suena natural
- [x] Hay un instalador standalone por cada SO (Windows, Linux, macOS)
- [x] Los instaladores funcionan sin ninguna dependencia externa
- [x] **README.md** refleja la nueva arquitectura con Chatterbox
- [x] **docs/DESIGN.md** corresponde al estado implementado
- [x] No queda documentación que haga referencia a XTTS, Kokoro o Rust como motor activo
- [x] El daemon mode está implementado y funciona correctamente
- [x] Los logs están normalizados con estructura consistente
- [x] Los tests pytest pasan (31/31)

---

## Estado Actual

**Completado (100%):**
- Motor Chatterbox Multilingual V3 implementado (Python)
- Sistema de audio playback nativo por SO (pycaw/winsound/sounddevice/afplay)
- Daemon mode con IPC HTTP (FastAPI, puerto 8765)
- torch.compile con optimizaciones (reduce-overhead, n_cfm=4, max_new_tokens=500)
- Watermark bypass para mayor velocidad
- Scripts de build Nuitka por SO (Windows/Linux/macOS)
- Descarga automática del modelo Chatterbox desde HuggingFace
- CLI completa con todos los comandos
- Tests pytest (31 tests)
- Documentación sincronizada
