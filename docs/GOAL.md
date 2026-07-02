# Goal: Sistema TTS con Chatterbox Multilingual V3

---

## Objetivo

Obtener un sistema TTS **100% local** con audio nativo por sistema operativo, para transformar texto a audio en **español latino** de la mejor calidad disponible, distribuido bajo **licencia GPL-3.0-or-later** (con dependencias y modelo bajo licencias permisivas compatibles).

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
│   └── chatterbox_tts/       # Paquete Python
│       ├── __init__.py
│       ├── engine.py         # Wrapper de Chatterbox
│       ├── audio.py          # Reproducción de audio nativa
│       ├── cli.py            # Interfaz CLI
│       ├── timing.py         # Instrumentación y timing
│       └── daemon/           # Daemon mode (FastAPI + IPC)
│           ├── daemon.py    # Gestor del ciclo de vida
│           ├── server.py    # Endpoints FastAPI
│           ├── ipc.py       # Cliente HTTP
│           ├── protocol.py  # Modelos Pydantic
│           └── run.py       # Entry point
├── bin/
│   └── tts-sidecar          # Script de entry point
├── scripts/                  # Scripts de build por SO
├── tests/                    # Suite de tests pytest
└── docs/
```

> El modelo `es-mx-latam` no se almacena en el repo: reside en la caché de
> HuggingFace del usuario (`~/.cache/huggingface/hub`) tras `tts-sidecar setup`.

---

## Comandos CLI objetivo (invocable desde cualquier lenguaje)

Los comandos están ordenados en secuencia de dependencia: cada paso solo
requiere que los anteriores hayan funcionado. El daemon es el camino principal
de uso: carga el modelo una sola vez y lo mantiene en memoria, eliminando el
overhead de carga en cada invocación. Por eso su ciclo de vida envuelve toda la
sesión: se arranca antes de sintetizar y se detiene al final.

```bash
# 1. Provisión (primera vez - chequeos + descarga el modelo si falta)
./tts-sidecar setup

# 2. Diagnóstico del sistema (no depende de nada)
./tts-sidecar version              # Versión instalada
./tts-sidecar doctor               # Chequeo de entorno y modelo
./tts-sidecar devices              # Dispositivos de audio disponibles

# 3. Arrancar el daemon (camino principal: carga el modelo en memoria una vez)
./tts-sidecar daemon start         # Iniciar daemon
./tts-sidecar daemon status        # Verificar que está activo

# 4. Clonación de voz (requiere dos archivos de audio)
./tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav

# 5. Listar voces registradas (verifica que la voz quedó registrada)
./tts-sidecar voice list

# 6. Síntesis a través del daemon (añade -v mi_voz para usar la voz clonada)
./tts-sidecar speak --text "Hola mundo" [-v mi_voz]                    # Reproducir
./tts-sidecar speak --text "Hola mundo" [-v mi_voz] --output audio.wav  # Exportar WAV

# 7. Eliminar voz clonada (limpieza)
./tts-sidecar voice remove --name mi_voz

# 8. Detener el daemon (cierre de la sesión, libera el modelo de memoria)
./tts-sidecar daemon stop
```

---

## Restricciones

- **100% local**: Sin APIs externas ni conexiones a internet para síntesis
- **Instalador único por SO**: Un archivo ejecutable por plataforma
- **Sin dependencias externas**: El usuario final no necesita instalar nada más
- **Licencia**: El código propio se distribuye bajo GPL-3.0-or-later; todas las dependencias y el modelo usados deben tener licencias permisivas compatibles con GPLv3 (MIT/BSD/Apache/ISC/PSF)

---

## Criterios de Aceptación

<!-- Los criterios 1-3 son claims de ejecución por SO: el pipeline de build (CI +
scripts/build_*.py) produce los instaladores, pero la validación end-to-end sobre
cada SO no es verificable desde el repo, por eso quedan pendientes. -->

1. [ ] El instalador de Windows (.exe) funciona en Windows 10/11 sin dependencias (validación por SO pendiente)
2. [ ] El instalador de Linux funciona en distribuciones principales (validación por SO pendiente)
3. [ ] El instalador de macOS funciona en macOS 12+ (validación por SO pendiente)
4. [x] `tts-sidecar speak --text "Hola mundo"` reproduce audio en español
5. [x] `tts-sidecar voice add --name test --reference ref.wav --speech speech.wav` clona la voz
6. [x] El audio generado suena en español con las características de la voz de referencia
7. [x] El español latinoamericano suena natural y con buena prosodia
8. [x] La síntesis funciona sin conexión a internet (modelo en local)
9. [ ] El instalador incluye todo lo necesario (no requiere instalaciones adicionales) (validación por SO pendiente)

---

## Condición de Finalización

La implementación está completa únicamente cuando:

- [x] El motor Chatterbox Multilingual V3 está implementado y funcional
- [x] La clonación de voz funciona con una muestra de ~10 segundos
- [x] El audio generado preserva las características de la voz original
- [x] El español latinoamericano suena natural
- [x] Hay scripts de build e instalador por cada SO (Windows, Linux, macOS) en el pipeline de CI
- [ ] Los instaladores funcionan sin ninguna dependencia externa (validación end-to-end por SO pendiente)
- [x] **README.md** refleja la nueva arquitectura con Chatterbox
- [x] **docs/DESIGN.md** corresponde al estado implementado
- [x] El daemon mode está implementado y funciona correctamente
- [x] Los logs están normalizados con estructura consistente
- [x] Los tests pytest pasan (95/95)

---

## Estado Actual

**Implementado y verificable en el repo** (la validación end-to-end de los
instaladores por SO queda pendiente, ver Criterios de Aceptación):
- Motor Chatterbox Multilingual V3 implementado (Python)
- Sistema de audio playback nativo por SO (pycaw/winsound/sounddevice/afplay)
- Daemon mode con IPC HTTP (FastAPI, puerto 8765)
- Optimizaciones de síntesis (n_cfm=4, max_new_tokens=500, watermark bypass)
- Watermark bypass para mayor velocidad
- Scripts de build PyInstaller por SO (Windows/Linux/macOS)
- Descarga automática del modelo Chatterbox desde HuggingFace
- CLI completa con todos los comandos
- Tests pytest (95 tests: timing, protocolo, daemon, CLI, voces, caché de modelo, audio y utilidades de build)
- Documentación sincronizada
