#!/usr/bin/env python3
"""
Clean build script — removes dist/ and cached model cache.
Usage: python scripts/clean_build.py
       npm run build-clean
"""

import shutil
import time
from pathlib import Path

# Import shared logging utilities
import sys
sys.path.insert(0, str(Path(__file__).parent))
from build_utils import log

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / "dist"

# HuggingFace default cache location
HF_CACHE = Path.home() / ".cache" / "huggingface" / "hub"
MODEL_CACHE_NAMES = [
    "models--ResembleAI--Chatterbox-Multilingual-es-mx-latam",
    "models--ResembleAI--chatterbox",
    "chatterbox-multilingual",
]


def delete_folder(dir_path: Path):
    """Delete a folder if it exists, log the result."""
    if not dir_path.exists():
        log(f"Not found (skip): {dir_path}")
        return
    try:
        shutil.rmtree(dir_path)
        log(f"Deleted: {dir_path}")
    except Exception as e:
        log(f"Error deleting {dir_path}: {e}")


def main():
    start = time.time()
    print()
    log("=== CLEAN BUILD ===")

    log("Removing dist/...")
    delete_folder(DIST_DIR)

    log("Removing HuggingFace model cache...")
    for name in MODEL_CACHE_NAMES:
        delete_folder(HF_CACHE / name)

    log("=== CLEAN DONE ===", time.time() - start)
    print()


if __name__ == "__main__":
    main()
