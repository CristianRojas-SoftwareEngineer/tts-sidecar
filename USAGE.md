# Guía de Uso de TTS Sidecar

`tts-sidecar` es un sintetizador de voz (TTS) 100 % local con clonación de voz en
español latinoamericano. Esta guía recorre cada caso de uso desde la perspectiva
del usuario: qué comando ejecutar, qué ocurre y qué salida esperar.

Todos los comandos funcionan **de forma idéntica en Windows, Linux y macOS**: la
misma sintaxis, la misma salida y los mismos códigos de retorno. Las diferencias
internas por plataforma (backend de reproducción, ubicación de datos) se detallan
en [Experiencia unificada entre sistemas operativos](#experiencia-unificada-entre-sistemas-operativos).

## Instalación

Hay dos flujos según la audiencia: el del **usuario del binario** (instala el
ejecutable distribuido por SO) y el del **desarrollador** (ejecuta desde el código
fuente con dependencias Python).

### Usuario del binario

Instala el ejecutable de tu plataforma desde Releases y déjalo accesible en el
PATH (en Windows el instalador lo agrega automáticamente). Luego invoca:

```bash
tts-sidecar <comando>
```

### Desarrollador (desde el código fuente)

```bash
# 1. Instalar dependencias (runtime + herramientas de build)
pip install -r requirements.txt

# 2. Ejecutar desde el código fuente
python bin/tts-sidecar <comando>
```

A partir de aquí, todos los ejemplos usan `tts-sidecar <comando>`; si trabajas
desde el código fuente, sustituye por `python bin/tts-sidecar <comando>`. El
comportamiento es el mismo.

## Primer uso: provisionar el modelo (`setup`)

El modelo de voz `es-mx-latam` (varios cientos de MB) no viene incluido: se
descarga una sola vez a la caché de HuggingFace (`~/.cache/huggingface/hub` por
defecto; si defines `HF_HOME` o `HF_HUB_CACHE`, se respeta esa ubicación)
mediante el comando `setup`.

```bash
tts-sidecar setup
```

**Qué esperar:** `setup` integra primero el comando en el PATH (solo en Linux,
ejecutado desde el AppImage; en Windows y macOS ese paso lo cubren el instalador
y el script del `.dmg`), después corre los chequeos de entorno (los mismos que
`doctor`) y por último descarga el modelo solo si falta. Un fallo del chequeo de
audio **no detiene la provisión**: `setup` lo degrada a `[WARN]` y continúa,
porque la síntesis a archivo (`speak --output`) funciona sin subsistema de
sonido (p. ej. en hosts headless o sesiones SSH); `doctor`, en cambio, lo sigue
reportando como `[FAIL]` con salida 1, como señal diagnóstica. En la primera
ejecución verás algo como:

```
=== Chatterbox TTS Setup ===

[PASS] Chatterbox TTS: 0.3.x
[PASS] Audio library: ... — N dispositivo(s)

Descargando el modelo es-mx-latam...
(Puede tardar varios minutos en la primera ejecución)

[PASS] ¡Modelo descargado correctamente!
  Ubicación: ~/.cache/huggingface/hub
```

Si lo vuelves a ejecutar con el modelo ya descargado, termina de inmediato sin
descargar nada (es idempotente):

```
[PASS] El modelo 'es-mx-latam' ya está en caché en: ~/.cache/huggingface/hub
Provisión completa. No hay nada que descargar.
```

**Provisión por SO** (experiencia homóloga):

- **Windows**: el instalador agrega `tts-sidecar` al PATH y ofrece una casilla
  post-instalación que ejecuta `setup` en tu contexto de usuario.
- **Linux**: `setup` es el punto único de provisión. Ejecutado desde el AppImage,
  además de descargar el modelo crea el symlink `~/.local/bin/tts-sidecar`
  apuntando al AppImage, dejando el comando invocable por nombre:

  ```bash
  # Primer uso con el AppImage descargado
  chmod +x tts-sidecar-0.1.0-x86_64.AppImage
  ./tts-sidecar-0.1.0-x86_64.AppImage setup
  # → symlink en ~/.local/bin + chequeos + descarga del modelo

  # Desde entonces, en una terminal nueva:
  tts-sidecar speak --text "Hola"

  # Reversión del symlink (desinstalación limpia):
  tts-sidecar setup --remove-path
  ```

  Si `~/.local/bin` no está en tu PATH, `setup` te lo advierte con la línea a
  añadir al shell profile.
- **macOS**: el `.dmg` incluye `Instalar (PATH + modelo).command`, que enlaza
  `tts-sidecar` en `/usr/local/bin` (pide sudo) y a continuación ofrece ejecutar
  `setup` como tu usuario. Para desinstalar, el mismo `.dmg` trae
  `Desinstalar (quitar del PATH).command`, que elimina el symlink; el `.app` se
  borra arrastrándolo a la Papelera.

> **Importante**: hasta que el modelo esté provisionado, `speak` y `daemon start`
> **abortan de inmediato** con un mensaje que remite a `tts-sidecar setup`. Nunca
> disparan una descarga silenciosa.

## Comandos

Los comandos de lectura (`version`, `doctor`, `devices`, `voice list`,
`daemon status`) aceptan `--json` para salida legible por máquina, útil al
invocar `tts-sidecar` desde otro programa.

---

### `version`

Muestra la versión del programa.

```bash
tts-sidecar version
tts-sidecar version --json
```

**Qué esperar:**

```
tts-sidecar 0.1.0
```

---

### `doctor`

Verifica que todos los componentes estén disponibles: la librería TTS, el
subsistema de audio, el modelo descargado y las voces.

```bash
tts-sidecar doctor
tts-sidecar doctor --json
```

**Qué esperar** (entorno sano):

```
=== Chatterbox TTS Doctor ===

Python: 3.11.x ...
Plataforma: Windows 11 / Linux 6.x / Darwin 24.x

[PASS] Chatterbox TTS: 0.3.x
[PASS] Audio library: pycaw (Windows) — 2 dispositivo(s)
[PASS] Chatterbox model: es-mx-latam presente en la caché
[PASS] Voices directory: 1 voz(voces) disponible(s)

Chequeos: 4 exitosos, 0 fallidos
```

Termina con código de salida 0 si todo pasa, y 1 si algún chequeo falla (cada
`[FAIL]` indica cómo corregirlo, p. ej. `ejecuta: tts-sidecar setup`).

---

### `devices`

Lista los dispositivos de salida de audio disponibles.

```bash
tts-sidecar devices
tts-sidecar devices --json
```

**Qué esperar:**

```
Dispositivos de salida de audio:
  [0] Altavoces (Realtek High Definition Audio) (latency: 10.0ms)
  [1] Auriculares (latency: 8.0ms)
```

---

### `speak`

Sintetiza texto. Sin `--output` reproduce el audio inmediatamente por los
altavoces; con `--output` lo guarda en un archivo WAV sin reproducirlo.

Sin `--voice` ni audios explícitos, `speak` usa la voz de fábrica **`default`**
(empaquetada, de solo lectura), por lo que el ejemplo mínimo funciona recién
instalado, sin registrar nada:

```bash
# Reproducir con la voz de fábrica 'default'
tts-sidecar speak --text "Hola mundo"

# Usar una voz registrada
tts-sidecar speak --text "Hola mundo" --voice mi_voz

# Guardar a archivo WAV
tts-sidecar speak --text "Hola mundo" --output output.wav
```

**Qué esperar:** el comando reporta su progreso por etapas con timestamps. En
modo directo (sin daemon), la primera etapa es la carga del modelo (~15–30 s) y
luego la síntesis; al final, el audio suena por los altavoces (o se anuncia el
archivo guardado):

```
Starting speak...
[10:00:01] Using cached model: es-mx-latam (...)...
[10:00:20] Model loaded: es-MX-Latam (vocab=2454, compute_backend=cpu, builtin_voice=yes)...
[10:00:20] [1-Speak] Stage 1/4: Loading conditionals...
[10:00:21] [1-Speak] -> Done (1.0s)
[10:00:21] [2-Speak] Stage 2/4: Generating audio (TTS)...
[10:00:39]    [Stage 2a] T3 autoregresivo: 12.0s...
[10:00:39]    [Stage 2b] S3Gen vocoder:   6.0s...
[10:00:39] [2-Speak] -> Done (18.2s)
[10:00:39] [3-Speak] Stage 3/4: Converting to WAV...
[10:00:39] [3-Speak] -> Done (0.1s)
[10:00:39] [Playback] Reproduciendo audio...
[10:00:42] [Playback] Reproducción finalizada
Finished in 41.5s
```

Con `--output`, en lugar de las líneas de `[Playback]` verás
`[I/O] Audio guardado: output.wav` y el archivo quedará en la ruta indicada.

**Orígenes de voz (resolución usuario→fábrica):**
- **Fábrica**: voces empaquetadas en el ejecutable, de solo lectura (incluye
  `default`). Idénticas en desarrollo y en cualquier instalación.
- **Usuario**: voces registradas con `voice add`, escribibles, guardadas en el
  directorio de datos de usuario por SO (estables entre ejecuciones). Una voz de
  usuario con el mismo nombre que una de fábrica la sobrescribe.

**Opciones:**
- `--text, -t` (requerido): Texto a sintetizar
- `--output, -o`: Ruta del archivo WAV de salida; si se omite, el audio se reproduce
- `--voice, -v`: Nombre de la voz clonada a usar (auto-carga sus dos audios)
- `--voice-audio`: Ruta a archivo de audio para timbre (usa `--speech-audio` si no se especifica)
- `--speech-audio`: Ruta a archivo de audio para conditioning (usa `--voice-audio` si no se especifica)
- `--daemon`: Usar el daemon sin sondeo previo; si falla, el error se reporta (sin fallback a directo)
- `--no-daemon`: Forzar modo directo, sin sondear el daemon
- `--compute-backend, -cb`: Backend de cómputo para la inferencia (`auto`, `cpu`, `cuda`, `mps`; default: `auto`)

Sin valor, `tts-sidecar` detecta automáticamente el mejor backend disponible
(CUDA → MPS → CPU) y lo usa durante toda la sesión. El backend elegido se
muestra en el log de arranque del motor (`Model loaded: …,
compute_backend=…`). Si quieres forzar uno concreto (p. ej. CPU para
reproducibilidad), pasa el valor explícito.

No hay opción de modelo: `tts-sidecar` está especializado en español
latinoamericano y usa siempre el modelo `es-mx-latam` provisionado por `setup`.
Tú solo gestionas las voces.

**Ejemplos:**
```bash
# Usando voz registrada
tts-sidecar speak --text "Hola mundo" --voice mi_voz

# Usando archivos de audio directamente (sin registrar voz)
tts-sidecar speak --text "Hola" --voice-audio timbre.wav --speech-audio condicion.wav

# Guardar a archivo con voz registrada
tts-sidecar speak --text "Hola mundo" --voice mi_voz --output audio.wav

# Forzar modo directo
tts-sidecar speak --text "Hola" --voice mi_voz --no-daemon
```

---

### `voice add`

Registra una nueva voz clonada a partir de dos archivos de audio.

```bash
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav
```

**Qué esperar:** el comando valida que ambos audios sean cargables, copia los
archivos al directorio de voces de usuario y confirma:

```
Starting voice_add...
Voz 'mi_voz' registrada:
  timbre (reference): <ruta>/voices/mi_voz/reference.wav
  habla (conditioning): <ruta>/voices/mi_voz/speech.wav
Finished in 0.4s
```

A partir de ese momento la voz aparece en `voice list` y puede usarse con
`speak --voice mi_voz`.

El registro es **casi instantáneo** (< 1 s): no carga el motor de inferencia,
solo valida y copia los audios. La preparación de la voz (cómputo de
conditionals) la absorbe la primera síntesis con `speak --voice mi_voz`, que
por eso puede tardar unos segundos más que las siguientes. Como el resto de
comandos de escritura, `voice add` requiere el modelo provisionado
(`tts-sidecar setup`).

**Opciones:**
- `--name, -n` (requerido): Nombre para la voz
- `--reference, -r` (requerido): Audio para timbre (cualquier largo — el audio completo se usa para el embedding)
- `--speech, -s` (requerido): Audio para conditioning (10+ segundos de habla limpia)
- `--compute-backend, -cb`: Backend de cómputo para la inferencia (`auto`, `cpu`, `cuda`, `mps`; default: `auto`); ver detalle en `speak`
- `--force, -f`: Sobrescribir la voz si ya existe (incluida una de fábrica homónima)

**¿Por qué dos archivos?**
- `--reference` captura el **timbre** de la voz (cómo suena)
- `--speech` provee el **patrón de habla** (ritmo, entonación)

Pueden ser el mismo archivo si solo tienes una grabación, pero separar ambos da
mejores resultados.

**Requisitos del audio:**
- Duración: 10+ segundos recomendados para `--speech`; `--reference` puede ser de cualquier largo
- Idioma: Español latinoamericano
- Calidad: Sin ruido de fondo, habla clara
- Formato: WAV 16-bit

---

### `voice list`

Lista las voces disponibles, tanto las de fábrica como las registradas por ti.

```bash
tts-sidecar voice list
tts-sidecar voice list --json
```

**Qué esperar:**

```
Voces registradas:
  - default
  - mi_voz
```

La voz `default` siempre está presente (viene de fábrica).

---

### `voice remove`

Elimina una voz registrada por el usuario.

```bash
tts-sidecar voice remove --name mi_voz
```

**Qué esperar:**

```
Voz 'mi_voz' eliminada.
```

Las voces de fábrica (como `default`) son de solo lectura y no pueden
eliminarse; el comando lo indica y termina con error si lo intentas.

---

### `cleanup`

Desaprovisiona los datos del proyecto: el modelo descargado y/o las voces de
usuario. Es la contraparte de `setup` y completa el ciclo de vida
instalación→desinstalación.

```bash
tts-sidecar cleanup --model      # elimina el modelo descargado
tts-sidecar cleanup --voices     # elimina las voces de usuario
tts-sidecar cleanup --all        # ambos
tts-sidecar cleanup --all --dry-run   # lista lo que se borraría, sin borrar
```

**Qué esperar:** el comando lista las rutas exactas a eliminar y pide
confirmación (`s/n`) antes de borrar; con `--dry-run` solo lista. Sin flags
muestra la ayuda y no borra nada.

El borrado es **quirúrgico**: dentro de la caché de HuggingFace solo se
eliminan las carpetas de los dos repos que usa el proyecto
(`Chatterbox-Multilingual-es-mx-latam` y `chatterbox` de ResembleAI), nunca
modelos de otros proyectos; `--voices` elimina únicamente el directorio de
voces de usuario. Todo es recuperable: `setup` reprovisiona el modelo y
`voice add` vuelve a registrar voces.

---

## Desinstalación completa

1. Ejecuta `tts-sidecar cleanup --all` para eliminar el modelo y las voces de
   usuario (los datos que la desinstalación del binario no toca).
2. Desinstala el binario según tu SO:
   - **Windows**: desinstalador de Inno Setup (Panel de control → Aplicaciones);
     revierte PATH y registro.
   - **Linux**: `tts-sidecar setup --remove-path` (quita el symlink) y borra el
     `.AppImage`.
   - **macOS**: `Desinstalar (quitar del PATH).command` del `.dmg` y arrastra el
     `.app` a la Papelera.

---

## Modo Daemon

El daemon mantiene el modelo cargado en memoria, evitando el tiempo de carga en
cada invocación (~15–30 s de overhead). Es el modo recomendado cuando vas a
sintetizar varias veces seguidas.

### Gestión del daemon

```bash
# Iniciar daemon (background; puerto fijo: 8765 en loopback, no configurable)
tts-sidecar daemon start

# Ver estado
tts-sidecar daemon status
tts-sidecar daemon status --json

# Reiniciar
tts-sidecar daemon restart

# Detener
tts-sidecar daemon stop

# Auto-reinicio en caso de crash
tts-sidecar daemon start --autorestart --max-retries 3
```

**Qué esperar:** `daemon start` verifica que el modelo esté descargado, lanza el
servidor en segundo plano y confirma con `Daemon iniciado correctamente`. Luego
`daemon status` muestra:

```
Daemon en ejecución:
  Estado: ready
  Modelo cargado: True
  Tiempo activo: 42.3s
```

`daemon stop` responde `Daemon detenido` y `daemon restart`, `Daemon reiniciado`.

### Uso con daemon

`speak` despacha según tres ramas:

- **Sin flags**: sondea el daemon con un health check corto y lo usa si responde;
  si no, cae al modo directo sin error.
- **`--daemon`**: asume el daemon disponible y le envía la síntesis sin sondeo
  previo; un fallo se reporta como error (sin fallback silencioso).
- **`--no-daemon`**: modo directo, sin ningún sondeo.

```bash
# El daemon se usa automáticamente si está disponible
tts-sidecar speak --text "Hola" --voice mi_voz

# Forzar modo daemon (falla si el daemon no responde)
tts-sidecar speak --text "Hola" --voice mi_voz --daemon

# Forzar modo directo (sin daemon)
tts-sidecar speak --text "Hola" --voice mi_voz --no-daemon
```

**Qué esperar** con el daemon activo: `speak` omite la etapa de carga del modelo
y la síntesis empieza de inmediato:

```
Starting speak...
[10:05:01] [Daemon] Enviando solicitud de síntesis...
   [Stage 2a] T3 autoregresivo: 12.0s
   [Stage 2b] S3Gen vocoder:   6.0s
[10:05:19] [Daemon] Síntesis completada (18.0s)...
[10:05:19] [Playback] Reproduciendo audio...
[10:05:22] [Playback] Reproducción finalizada
Finished in 21.3s
```

Los tiempos de `[Stage 2a]` (generación de tokens) y `[Stage 2b]` (vocoder) se
muestran en ambos modos, para que puedas comparar el rendimiento.

---

## Clonación de voz: recorrido completo

De principio a fin, desde grabar tu voz hasta escucharla sintetizada:

```bash
# 1. Graba dos audios en español (WAV 16-bit, sin ruido de fondo):
#    timbre.wav  - cualquier largo, captura tu timbre
#    habla.wav   - 10+ segundos de habla limpia y continua

# 2. Registra la voz
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech habla.wav
# → Voz 'mi_voz' registrada: (rutas de los dos archivos copiados)

# 3. Verifica que aparece
tts-sidecar voice list
# → Voces registradas: default, mi_voz

# 4. Escúchala
tts-sidecar speak --text "Hola, esto es una prueba" --voice mi_voz
# → etapas de síntesis + reproducción por los altavoces

# 5. O genera un archivo
tts-sidecar speak --text "Hola, esto es una prueba" --voice mi_voz --output mi_voz.wav
# → [I/O] Audio guardado: mi_voz.wav
```

La voz queda guardada de forma permanente: en futuras sesiones basta con
`--voice mi_voz`, sin volver a registrar nada.

---

## Experiencia unificada entre sistemas operativos

Todos los casos de uso de esta guía se ejecutan **con los mismos comandos, la
misma salida y los mismos códigos de retorno** en Windows, Linux y macOS, tanto
desde el binario como desde el código fuente. En concreto:

- **Sintaxis idéntica**: no hay flags ni subcomandos exclusivos de una plataforma.
- **Contrato de salida estable**: los datos van a stdout y los diagnósticos y
  errores a stderr, siempre en UTF-8. Esto hace a `tts-sidecar` consumible por
  scripts de forma idéntica en los tres SO.
- **Códigos de salida (contrato público congelado)**: un orquestador distingue la
  causa del fallo sin parsear texto en español. Los valores son estables entre SO
  y versiones:

  | Código | Significado | Ejemplo |
  |--------|-------------|---------|
  | `0` | Éxito | Síntesis o comando completado |
  | `1` | Error genérico | Fallo inesperado; `doctor` con algún chequeo fallido |
  | `2` | Modelo no provisionado | `speak`/`daemon start` sin ejecutar `setup` |
  | `3` | Voz o audio no encontrado | `--voice inexistente`; `voice remove` de una voz ausente |
  | `4` | Entrada inválida | `--text` vacío; nombre de voz ilegal; colisión en `voice add` sin `--force` |
  | `5` | Daemon inalcanzable | `speak --daemon` sin daemon; `daemon start/stop/restart` fallido |
  | `130` | Interrupción del usuario | Ctrl+C (128 + SIGINT) durante cualquier comando |
- **La voz `default` y el modelo** son los mismos en todas las plataformas: el
  audio generado para un mismo texto y voz es equivalente en cualquier SO.
- **El motor auto-detecta el mejor backend de cómputo disponible** (CUDA en
  NVIDIA, MPS en Apple Silicon, CPU en otro caso); se puede forzar uno
  concreto con `--compute-backend` (`auto` por default). La detección corre
  una sola vez al cargar el motor (en cada `speak` sin daemon, y una vez por
  arranque del daemon).

Las únicas diferencias son internas y no cambian la forma de usar la aplicación:

| Aspecto | Windows | Linux | macOS |
|---------|---------|-------|-------|
| Reproducción de audio | winsound (integrado) | sounddevice (PortAudio) | afplay (integrado) |
| Enumeración de dispositivos | pycaw | sounddevice | sounddevice |
| Voces de usuario (binario) | `%LOCALAPPDATA%\tts-sidecar\voices` | `~/.local/share/tts-sidecar/voices` | `~/Library/Application Support/tts-sidecar/voices` |
| Caché del modelo | `~/.cache/huggingface/hub` | `~/.cache/huggingface/hub` | `~/.cache/huggingface/hub` |

> La caché del modelo respeta las variables de entorno `HF_HUB_CACHE` y `HF_HOME`
> si están definidas (misma resolución que usa HuggingFace Hub); la ruta de la
> tabla es el valor por defecto.

---

## Formato de Audio

- **Generación**: 24000 Hz, Mono
- **Exportación WAV**: 16-bit PCM, 24000 Hz, Mono

## Solución de Problemas

### "el modelo 'es-mx-latam' no está descargado"

`speak` y `daemon start` requieren el modelo provisionado y nunca lo descargan
por sí mismos. Ejecuta la provisión una vez:

```bash
tts-sidecar setup
```

### "Voice 'x' not found"

Verifica que la voz existe:

```bash
tts-sidecar voice list
```

### "La voz 'x' ya existe"

`voice add` no sobrescribe voces por accidente. Si quieres reemplazarla:

```bash
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech habla.wav --force
```

### "reference.wav/speech.wav not found"

La voz no tiene los archivos necesarios. Puede que se registró con el formato
antiguo. Vuelve a registrar:

```bash
tts-sidecar voice add --name mi_voz --reference timbre.wav --speech condicion.wav --force
```

### "Voz 'x' es una voz de fábrica (solo lectura)"

Las voces empaquetadas (como `default`) no pueden eliminarse con `voice remove`.
Si quieres reemplazar su sonido, registra una voz de usuario con el mismo nombre
usando `voice add --force`: la tuya toma precedencia.

### Error al eliminar una voz: "uno de sus archivos parece estar en uso"

Otro proceso (el daemon, un reproductor de audio) tiene abierto alguno de los
archivos de la voz. Ciérralo (p. ej. `tts-sidecar daemon stop`) y reintenta.

### Sin audio de salida

1. Verifica que `tts-sidecar devices` detecta tu dispositivo
2. Comprueba que el volumen del sistema no está en mute
3. Verifica que el dispositivo de audio predeterminado es correcto
4. Ejecuta `tts-sidecar doctor`: el chequeo "Audio library" falla si el host no
   tiene un subsistema de audio funcional (p. ej. sesiones remotas o headless)

En un host sin audio puedes seguir usando la síntesis a archivo
(`tts-sidecar speak --text "Hola" --output audio.wav`); `setup` también funciona
allí (degrada el chequeo de audio a `[WARN]` y provisiona igual).

### El sistema bloquea el primer arranque (binarios sin firmar)

Los binarios distribuidos no están firmados ni notarizados, así que la primera
apertura puede ser bloqueada por el sistema:

- **macOS (Gatekeeper)**: al abrir el `.app`/`.dmg` por primera vez, haz clic
  derecho sobre él → **Abrir** y confirma; o quita la cuarentena desde una
  terminal:

  ```bash
  xattr -d com.apple.quarantine /Applications/tts-sidecar-arm64.app
  ```

- **Windows (SmartScreen)**: si aparece «Windows protegió tu PC» al ejecutar el
  instalador, pulsa **Más información** → **Ejecutar de todas formas**.

Esto solo ocurre en el primer arranque; las ejecuciones posteriores no vuelven a
pedir confirmación.

## Uso ético y responsable

`tts-sidecar` permite clonar voces arbitrarias a partir de unos segundos de audio.
Por diseño, **el audio generado no contiene marca de agua**: el watermark de
PerthNet está desactivado en el motor (tanto en modo directo como en el daemon),
de modo que la salida no es distinguible por medios técnicos de una grabación
real. Esta capacidad exige diligencia por parte de quien la usa:

- **Consentimiento explícito**: registra y clona únicamente voces para las que
  cuentes con el permiso de la persona titular. Clonar la voz de alguien sin su
  autorización puede ser ilegal en tu jurisdicción y es, en todo caso, una falta
  de respeto a su identidad.
- **Prohibición de suplantación**: no emplees la herramienta para hacerte pasar
  por otra persona, cometer fraude, eludir sistemas de verificación por voz,
  difamar, acosar ni generar desinformación.
- **Divulgación del contenido sintético**: cuando publiques o compartas audio
  generado, decláralo como sintético. Dado que **no lleva marca de agua**, la
  transparencia depende enteramente de ti; no existe un mecanismo automático que
  identifique la salida como generada por IA.
- **Canal de reporte**: si detectas un uso indebido de este proyecto o de
  material producido con él, abre un
  [Issue](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/issues)
  describiendo la situación.

`tts-sidecar` es software libre y no impone barreras técnicas al uso (serían
triviales de sortear); establece, en cambio, la diligencia debida esperada en la
comunidad de IA de código abierto. La responsabilidad del uso legítimo recae en
la persona que ejecuta la herramienta.

## Licencia

`tts-sidecar` se distribuye bajo **GPL-3.0-or-later** (ver [LICENSE](LICENSE)). El modelo
Chatterbox y las dependencias empaquetadas conservan sus licencias permisivas
(MIT/BSD/Apache), detalladas en [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md).
