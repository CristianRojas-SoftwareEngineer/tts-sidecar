"""Crea AGENTS.md como hardlink de CLAUDE.md en la raíz del repo."""

import os
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
source = repo_root / "CLAUDE.md"
target = repo_root / "AGENTS.md"


def main() -> int:
    if not source.exists():
        print("Error: CLAUDE.md no se encontró en la raíz del proyecto.", file=sys.stderr)
        return 1

    print("=== Crear referencia multi-agente ===")
    print(f"Origen:    {source}")
    print(f"Destino:   {target}")
    print()

    if target.exists():
        os.unlink(target)
        print("  AVISO: existía un archivo AGENTS.md previo. Se sobrescribirá.")

    os.link(source, target)
    print("  OK: hardlink AGENTS.md -> CLAUDE.md creado.")

    print()
    print("Listo. AGENTS.md apunta a CLAUDE.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
