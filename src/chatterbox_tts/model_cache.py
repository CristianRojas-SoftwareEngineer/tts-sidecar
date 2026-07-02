"""
Detección de modelos en la caché de HuggingFace, libre de dependencias de ML.

Este módulo NO importa torch ni chatterbox: los comandos que solo necesitan
saber si el modelo está descargado (speak vía daemon, doctor, setup) lo usan
sin pagar los segundos de arranque en frío de engine.py.
"""

import os
from pathlib import Path
from typing import Optional

# Alias de modelo expuestos por el CLI → repo de HuggingFace
MODELS = {
    "multilingual": "ResembleAI/chatterbox-multilingual",
    "es-mx-latam": "ResembleAI/Chatterbox-Multilingual-es-mx-latam",
}

# Mapa único de alias/repos al nombre de carpeta en la caché de HuggingFace
CACHE_NAMES = {
    "es-mx-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "multilingual": "models--ResembleAI--chatterbox-multilingual",
    "ResembleAI/Chatterbox-Multilingual-es-mx-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "ResembleAI/chatterbox-multilingual": "models--ResembleAI--chatterbox-multilingual",
}


def hub_cache_path() -> Path:
    """Raíz de la caché de HuggingFace usada por el proyecto."""
    return Path(os.path.expanduser("~/.cache/huggingface/hub"))


def cache_folder_for(model_name: str) -> str:
    """Nombre de la carpeta de caché para un alias o repo de modelo."""
    return CACHE_NAMES.get(model_name, f"models--{model_name.replace('/', '--')}")


def _resolve_cached_snapshot(model_cache_dir: Path) -> Optional[Path]:
    """
    Resuelve el snapshot vigente de un modelo en la caché de HuggingFace.

    Prefiere la revisión apuntada por refs/main (la que huggingface_hub considera
    actual); si el ref no existe o apunta a un snapshot ausente, cae al snapshot
    más reciente por mtime. Devuelve None si no hay ninguno.
    """
    snap_path = model_cache_dir / "snapshots"
    if not snap_path.exists():
        return None

    ref_main = model_cache_dir / "refs" / "main"
    if ref_main.exists():
        revision = ref_main.read_text(encoding="utf-8").strip()
        candidate = snap_path / revision
        if candidate.is_dir():
            return candidate

    snapshots = [d for d in snap_path.iterdir() if d.is_dir()]
    if not snapshots:
        return None
    return max(snapshots, key=lambda d: d.stat().st_mtime)


def is_model_cached(model: str = "es-mx-latam") -> bool:
    """
    Verifica si el modelo dado ya está en la caché de HuggingFace.

    Pura inspección de sistema de archivos: no dispara descargas ni carga
    el modelo en memoria.
    """
    model_name = MODELS.get(model, model)

    cached = _resolve_cached_snapshot(hub_cache_path() / cache_folder_for(model_name))

    if cached is None:
        return False

    # es-mx-latam exige que el checkpoint del language-pack esté presente
    if model == "es-mx-latam" or "es-mx-latam" in model_name:
        return (cached / "t3_es_mx_latam.safetensors").exists()

    return True
