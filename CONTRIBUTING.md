# Guía de contribución

Gracias por tu interés en contribuir a `tts-sidecar`. Este documento describe el
flujo de desarrollo, los estándares del proyecto y cómo proponer cambios.

## Requisitos

- **Python 3.13** (el proyecto fija esta versión en el build y en CI).
- Git.
- En Linux, las cabeceras de ALSA para el audio: `libasound2-dev`.

## Configuración del entorno de desarrollo

```bash
git clone https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar.git
cd tts-sidecar

# Instalar dependencias de desarrollo (límites >=; ver nota más abajo)
pip install -r requirements.txt
pip install pytest

# Ejecutar el CLI desde el código fuente
python bin/tts-sidecar version
python bin/tts-sidecar doctor
```

> Los **builds y el CI** no instalan desde `requirements.txt`, sino desde
> `requirements-lock.txt` (lock universal con hashes) con `--require-hashes`, para
> garantizar reproducibilidad. `requirements.txt` son los límites de desarrollo.

## Tests

La suite usa `pytest`. Antes de abrir un PR, ejecútala completa y asegúrate de que
pasa:

```bash
pytest tests/ -v
```

- Añade tests para todo comportamiento nuevo o corregido.
- La suite se ejecuta en CI tanto en **Linux** como en **Windows** nativo; evita
  supuestos específicos de un SO (rutas, permisos, señales) o márcalos con un
  `skip` justificado.
- Verificación rápida de sintaxis: `python -m compileall src/`.

## Dependencias y lockfile

La fuente de verdad de las dependencias de runtime es `pyproject.toml`. Tras
modificarla, **regenera el lockfile** de forma deliberada y revisa el diff:

```bash
pip install uv
uv pip compile --universal --generate-hashes --python-version 3.13 \
    pyproject.toml -o requirements-lock.txt
```

Si cambian las dependencias empaquetadas, actualiza también
`THIRD-PARTY-LICENSES.md` (ver la sección «Regeneración» de ese archivo).

## Compilación de binarios

Ver [docs/BUILD.md](docs/BUILD.md) para el detalle por plataforma. Resumen:

```bash
npm run build-windows          # o python scripts/build_windows.py
python scripts/build_linux.py --arch x86_64
python scripts/build_macos.py --arch arm64
```

## Estilo y convenciones

- **Idioma**: el código, los comentarios, los mensajes de commit y la documentación
  se escriben en **español**, con ortografía correcta (acentos y signos incluidos).
- **Comentarios**: explican el *porqué*, no el *qué*; sigue la densidad y el estilo
  del código circundante.
- **Commits**: mensajes descriptivos en español, con prefijo de tipo cuando aplique
  (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `build:`), en imperativo.

## Flujo de Pull Request

1. Crea una rama a partir de `main`.
2. Implementa el cambio con sus tests y la actualización documental correspondiente
   (código, CI y docs deben quedar sincronizados en el mismo cambio).
3. Verifica que `pytest tests/ -v` pasa en tu máquina.
4. Abre el PR describiendo el problema, la solución y cómo verificarla.
5. Enlaza el Issue relacionado si existe.

## Reporte de problemas

- **Bugs y solicitudes de función**: abre un
  [Issue](https://github.com/CristianRojas-SoftwareEngineer/tts-sidecar/issues).
- **Vulnerabilidades de seguridad**: sigue [SECURITY.md](SECURITY.md) (no las
  reportes en un Issue público).
