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

# Repo base de Chatterbox: fuente de ve.safetensors (Voice Encoder), que el
# language pack es-mx-latam no incluye.
BASE_MODEL_REPO = "ResembleAI/chatterbox"

# Mapa único de alias/repos al nombre de carpeta en la caché de HuggingFace
CACHE_NAMES = {
    "es-mx-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "multilingual": "models--ResembleAI--chatterbox-multilingual",
    "ResembleAI/Chatterbox-Multilingual-es-mx-latam": "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "ResembleAI/chatterbox-multilingual": "models--ResembleAI--chatterbox-multilingual",
}


def hub_cache_path() -> Path:
    """Raíz de la caché de HuggingFace usada por el proyecto.

    Delega en huggingface_hub.constants.HF_HUB_CACHE: la misma fuente que
    consulta snapshot_download, de modo que respeta HF_HUB_CACHE/HF_HOME y
    no puede divergir de donde 'setup' descarga realmente el modelo.
    """
    # Import local: huggingface_hub es liviano pero se difiere igualmente
    # para no encarecer los comandos que nunca tocan la caché.
    from huggingface_hub import constants
    return Path(constants.HF_HUB_CACHE)


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


def is_ve_cached(lang_snapshot: Optional[Path] = None) -> bool:
    """
    Verifica si ve.safetensors (Voice Encoder) está resoluble localmente.

    El engine lo busca primero en el snapshot del language pack y, si no está,
    en el snapshot cacheado del modelo base (BASE_MODEL_REPO): este chequeo
    replica exactamente esa resolución sin disparar descargas.
    """
    if lang_snapshot is not None and (lang_snapshot / "ve.safetensors").exists():
        return True
    base = _resolve_cached_snapshot(hub_cache_path() / cache_folder_for(BASE_MODEL_REPO))
    return base is not None and (base / "ve.safetensors").exists()


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

    # es-mx-latam exige el checkpoint del language-pack más el Voice Encoder
    # (ve.safetensors, compartido con el modelo base): sin él, el primer speak
    # dispararía una descarga, rompiendo la promesa «100 % offline tras setup».
    if model == "es-mx-latam" or "es-mx-latam" in model_name:
        if not (cached / "t3_es_mx_latam.safetensors").exists():
            return False
        return is_ve_cached(cached)

    return True


def model_cache_dirs() -> list[Path]:
    """Carpetas de caché de HuggingFace propias del proyecto (existan o no).

    Solo las de los dos repos que el proyecto usa: el language pack es-mx-latam
    y el modelo base (fuente de ve.safetensors). `cleanup` borra exactamente
    estas rutas, nunca la caché completa.
    """
    root = hub_cache_path()
    return [
        root / cache_folder_for("es-mx-latam"),
        root / cache_folder_for(BASE_MODEL_REPO),
    ]
