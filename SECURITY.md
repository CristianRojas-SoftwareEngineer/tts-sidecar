# Política de seguridad

## Versiones soportadas

`tts-sidecar` está en desarrollo activo pre-1.0. Solo la última versión publicada
recibe correcciones de seguridad.

| Versión | Soportada |
|---------|-----------|
| 0.1.x   | ✅ |
| < 0.1.0 | ❌ |

## Cómo reportar una vulnerabilidad

**No** reportes vulnerabilidades de seguridad en Issues públicos.

Usa el canal privado de
[**GitHub Security Advisories**](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/security/advisories/new)
para reportarlas de forma confidencial. Incluye:

- Una descripción de la vulnerabilidad y su impacto.
- Pasos para reproducirla (versión, SO, comando o entrada).
- Cualquier mitigación conocida.

Recibirás una respuesta inicial en un plazo razonable. Te pedimos no divulgar
públicamente el problema hasta que exista una corrección disponible.

## Modelo de amenaza

`tts-sidecar` es una herramienta **local y offline**. Su superficie de ataque es
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

- El modelo se descarga desde HuggingFace con `tts-sidecar setup` a la caché local.
  La integridad de los pesos depende de HuggingFace Hub.
- Los builds se producen desde un **lockfile con hashes** (`--require-hashes`), lo
  que protege la cadena de dependencias frente a paquetes alterados en PyPI.

### Contenido generado

- El audio sintetizado **no lleva marca de agua** (el watermark de PerthNet está
  desactivado). Esto es una decisión de diseño con implicaciones de uso responsable,
  no una vulnerabilidad; ver «Uso ético y responsable» en
  [README.md](README.md)/[USAGE.md](USAGE.md).

## Artefactos sin firmar

Los binarios distribuidos **no están firmados ni notarizados**: Gatekeeper (macOS) y
SmartScreen (Windows) advierten en el primer arranque. Verifica que descargas los
artefactos desde el repositorio oficial de Releases.
