#!/usr/bin/env python3
"""Verificador de sincronía entre `requirements-lock.txt` y `THIRD-PARTY-LICENSES.md`.

`THIRD-PARTY-LICENSES.md` es un documento con peso legal (GPLv3 exige
atribuciones correctas de lo redistribuido) que se regenera a mano con
`pip-licenses`: nada garantizaba que reflejara el lockfile, y cada alta o baja
de dependencias podía desincronizarlo en silencio. Este script deriva
el conjunto de paquetes del lock universal, lo compara con la tabla de
dependencias del inventario (nombres normalizados PEP 503) y reporta faltantes
y sobrantes. Generar sigue siendo humano (ver §Regeneración del inventario);
verificar es automático: `tests/test_third_party_licenses.py` corre `check()`
en cada pytest, así que la desincronización rompe la suite en local y en los
3 jobs de test de CI sin tocar el pipeline (que solo corre en tags).
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
LOCKFILE = PROJECT_ROOT / "requirements-lock.txt"
LICENSES_DOC = PROJECT_ROOT / "THIRD-PARTY-LICENSES.md"

# Header exacto de la tabla de inventario: ancla el parser para no confundirse
# con las otras tablas del documento (modelos, MPL, LGPL, GPL).
_INVENTORY_HEADER = "| Paquete | Versión |"

# Línea de paquete del lock de uv: `nombre==versión` al inicio de línea,
# opcionalmente seguida de un marcador de entorno (`; sys_platform == ...`).
_LOCK_LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==\S+", re.MULTILINE)

# Fila de la tabla de inventario: `| `nombre` | versión | ... |`.
_DOC_ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def normalize(name: str) -> str:
    """Normalización PEP 503 del nombre de paquete (guiones/puntos/mayúsculas)."""
    return re.sub(r"[-_.]+", "-", name).lower()


def lockfile_packages(text: str) -> set:
    """Conjunto de nombres normalizados de los paquetes de un lockfile de uv.

    Ignora comentarios, líneas de hash/continuación y deduplica los paquetes
    que aparecen varias veces con marcadores de entorno distintos (p. ej.
    torch para python < 3.14 y >= 3.14).
    """
    return {normalize(m) for m in _LOCK_LINE.findall(text)}


def licenses_doc_packages(text: str) -> set:
    """Conjunto de nombres normalizados de la tabla de inventario del doc.

    Ancla en el header `| Paquete | Versión |` (las demás tablas del documento
    tienen otros headers) y lee filas hasta la primera línea que no es fila.
    """
    lines = text.splitlines()
    try:
        start = next(
            i for i, line in enumerate(lines) if line.startswith(_INVENTORY_HEADER)
        )
    except StopIteration:
        raise ValueError(
            f"No se encontró la tabla de inventario (header {_INVENTORY_HEADER!r}) "
            "en THIRD-PARTY-LICENSES.md"
        )

    packages = set()
    for line in lines[start + 2:]:  # salta header y separador
        m = _DOC_ROW.match(line)
        if not m:
            break
        packages.add(normalize(m.group(1)))
    return packages


def check() -> tuple:
    """Compara lock e inventario actuales; devuelve (missing, extra) ordenados.

    `missing`: paquetes del lock ausentes del inventario (atribución faltante).
    `extra`: paquetes del inventario que ya no están en el lock (fila obsoleta).
    """
    lock = lockfile_packages(LOCKFILE.read_text(encoding="utf-8"))
    doc = licenses_doc_packages(LICENSES_DOC.read_text(encoding="utf-8"))
    return sorted(lock - doc), sorted(doc - lock)


if __name__ == "__main__":
    missing, extra = check()
    if not missing and not extra:
        print("THIRD-PARTY-LICENSES.md está en sincronía con requirements-lock.txt")
        sys.exit(0)
    if missing:
        print("Paquetes del lock SIN fila en THIRD-PARTY-LICENSES.md (atribución faltante):")
        for name in missing:
            print(f"  + {name}")
    if extra:
        print("Filas de THIRD-PARTY-LICENSES.md sin paquete en el lock (obsoletas):")
        for name in extra:
            print(f"  - {name}")
    print("\nRegenera el inventario (ver §Regeneración de THIRD-PARTY-LICENSES.md).")
    sys.exit(1)
