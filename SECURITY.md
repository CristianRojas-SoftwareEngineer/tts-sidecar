# Política de seguridad

## Versiones soportadas

TTS Sidecar está en desarrollo activo pre-1.0. Solo la última versión publicada
recibe correcciones de seguridad.

| Versión | Soportada |
|---------|-----------|
| 0.1.x   | ✅ |
| < 0.1.0 | ❌ |

## Cómo reportar una vulnerabilidad

**No** reportes vulnerabilidades de seguridad en Issues públicos.

Usa el canal privado de
[**GitHub Security Advisories**](https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/security/advisories/new)
para reportarlas de forma confidencial. Incluye:

- Una descripción de la vulnerabilidad y su impacto.
- Pasos para reproducirla (versión, SO, comando o entrada).
- Cualquier mitigación conocida.

Recibirás una respuesta inicial en un plazo razonable. Te pedimos no divulgar
públicamente el problema hasta que exista una corrección disponible.

## Modelo de amenaza

TTS Sidecar es una herramienta **local y offline**. Su superficie de ataque es
limitada, pero conviene explicitar sus supuestos:

### Daemon local (modo daemon)

- El daemon escucha **únicamente en loopback** (`127.0.0.1:8765`); no se expone a la
  red. **No implementa autenticación**: delega el control de acceso en el sistema
  operativo (cualquier proceso local del mismo usuario puede invocarlo).
- **No ejecutes el daemon en un host multiusuario no confiable** esperando
  aislamiento entre usuarios locales: no lo provee.
- El endpoint de síntesis valida la entrada (`text` acotado a 5000 caracteres; las
  rutas de audio deben existir y ser `.wav`) antes de procesarla.
- No reenvíes ni expongas el puerto 8765 a interfaces de red externas.

### Modelo y provisión

- El modelo se descarga desde HuggingFace con `tts-sidecar setup` a la caché local,
  con la **revisión fijada por release** (commit hash auditado, declarado en
  `src/tts_sidecar/model_cache.py`): un push posterior al repo del modelo —
  malicioso o accidental — no se propaga a los usuarios, y la detección de caché
  solo valida el snapshot de esa revisión en ambos repos (language pack y repo
  base). El alcance del pin es ese: protege contra cambios posteriores a la
  revisión auditada; no es una verificación criptográfica por archivo de los
  pesos descargados (el transporte y el direccionamiento por hash de commit
  corren a cargo de HuggingFace Hub).
- Los builds se producen desde un **lockfile con hashes** (`--require-hashes`), lo
  que protege la cadena de dependencias frente a paquetes alterados en PyPI.

### Contenido generado

- El audio sintetizado **no lleva marca de agua** (el watermark de PerthNet está
  desactivado). Esto es una decisión de diseño con implicaciones de uso responsable,
  no una vulnerabilidad; ver «Uso ético y responsable» en
  [README.md](README.md)/[USAGE.md](USAGE.md).

### Nota sobre el instalador de una línea de Linux

`install.sh` (raíz del repo) se sirve por `raw.githubusercontent.com` y se
ejecuta con `curl | sh`, el patrón habitual de instalación de una línea. La
mitigación de ese patrón —ejecutar contenido remoto sin inspeccionarlo antes—
es que **el propio script verifica el checksum SHA-256** del `.AppImage`
descargado contra `SHA256SUMS.txt` (publicado junto al Release, ver
«Artefactos sin firmar» abajo) **antes** de darle permisos de ejecución o de
invocarlo; un checksum que no coincide aborta la instalación sin ejecutar
nada. El propio `install.sh` no requiere privilegios elevados: instala en
`~/.local/opt/tts-sidecar/`, sin `sudo`.

### Nota sobre el instalador de una línea de Windows

`install.ps1` (raíz del repo) se sirve por `raw.githubusercontent.com` y se
ejecuta con `irm | iex`, el equivalente PowerShell del patrón anterior. La
mitigación es la misma: **el propio script verifica el checksum SHA-256** del
instalador descargado contra `SHA256SUMS.txt` **antes** de ejecutarlo; un
checksum que no coincide aborta la instalación sin ejecutar nada. El script no
requiere privilegios elevados: la instalación es per-user
(`%LOCALAPPDATA%\Programs\tts-sidecar`, PATH en `HKCU\Environment`), sin UAC.
La descarga por CLI (`Invoke-WebRequest`) no aplica el Mark-of-the-Web, por lo
que el instalador descargado por el script no dispara SmartScreen; Microsoft
Defender **Antivirus** es independiente del MOTW y puede marcar el binario sin
firma — en ese caso aplica el runbook WDSI de más abajo. Como `irm | iex` no
escribe un `.ps1` en disco, no pasa por la Execution Policy; la alternativa
inspeccionable es `iwr <url> -OutFile install.ps1; .\install.ps1`.

## Artefactos sin firmar

Los binarios distribuidos **no están firmados ni notarizados**: Gatekeeper (macOS) y
SmartScreen (Windows) advierten en el primer arranque, y cada release —al ser
un archivo nuevo sin reputación acumulada— vuelve a disparar la advertencia.
Sin firma de código, la única verificación de integridad disponible es cotejar
el SHA-256 del artefacto descargado contra el archivo `SHA256SUMS.txt`
publicado junto a cada
[Release](https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/releases)
— esos hashes, a su vez, deben coincidir con los emitidos en el log del
pipeline de CI que construyó el artefacto. Ver el flujo completo de
publicación y verificación en [docs/RELEASING.md](docs/RELEASING.md), y la
guía de usuario para los diálogos de bloqueo en
[USAGE.md](USAGE.md#el-sistema-bloquea-el-primer-arranque-binarios-sin-firmar).

**Ruta prevista**: incorporar firma de código vía
[SignPath Foundation](https://signpath.org/), que ofrece firma gratuita a
proyectos open source con licencia OSI (el certificado se emite a nombre de la
fundación y la clave privada reside en su HSM; requiere builds verificables
desde el repositorio, MFA de los mantenedores y una política de firma
publicada). La firma OV no suprime la advertencia de SmartScreen de inmediato
—la reputación se acumula por volumen de descargas— pero reemplaza «editor
desconocido» por un editor verificable.

Mientras tanto, el build aplica dos mitigaciones baratas sin firma de código:
todos los artefactos de PyInstaller se empaquetan con `--noupx` (sin
compresión UPX, una de las señales que la heurística antivirus asocia con
malware), y el `.exe` de Windows lleva metadata PE de identidad (empresa,
producto y versión vía `--version-file`), ambas cubiertas por test en
`tests/test_build_utils.py` y `tests/test_build_windows.py`.

### Runbook: reportar un falso positivo de Defender Antivirus (WDSI)

Si un release de Windows es marcado por **Microsoft Defender Antivirus** (por
ejemplo con una firma como `Trojan:Win32/Wacatac`), reporta el falso positivo
al portal de Microsoft (*Windows Defender Security Intelligence*):

1. Entra a [microsoft.com/wdsi](https://www.microsoft.com/en-us/wdsi/filesubmission)
   y elige **"Submit a file for malware analysis"**.
2. Sube el artefacto marcado (el `.exe` o el instalador Inno Setup) tal cual se
   descargó del [Release](https://github.com/CristianRojas-SoftwareEngineer/TTS-Sidecar/releases);
   el reporte funciona con el binario **sin firmar**, no hace falta esperar a
   tener firma de código.
3. Clasifica la muestra como **"Incorrectly detected as malware / False
   Positive"** e indica la detección exacta que reportó Defender.
4. En el campo de comentarios, aclara que es un ejecutable PyInstaller de
   código abierto (enlaza este repositorio y el commit/tag del que se
   construyó el artefacto, verificable contra `SHA256SUMS.txt` — ver
   [docs/RELEASING.md](docs/RELEASING.md)).
5. Microsoft revisa la muestra con un analista y, si confirma el falso
   positivo, **borra la detección globalmente** para todos los usuarios de
   Defender (no solo para quien reportó).

Alcance de este runbook: cubre **únicamente** la detección de Defender
Antivirus. **No** desactiva ni acelera el paso de SmartScreen — SmartScreen es
reputación de archivo/editor, y solo la resuelve la firma de código (ver la
ruta prevista arriba), no un reporte a WDSI. Firmar el binario tampoco borra
retroactivamente una detección de Defender ya existente: solo el reporte a
WDSI lo hace. Sin firma de código, la reputación se acumula por archivo
individual, así que **cada versión nueva puede requerir un reporte propio**;
con firma de código, la reputación se hereda entre versiones y esa
recurrencia disminuye considerablemente. Ver también la guía de usuario para
los diálogos de bloqueo en
[USAGE.md](USAGE.md#el-sistema-bloquea-el-primer-arranque-binarios-sin-firmar).
