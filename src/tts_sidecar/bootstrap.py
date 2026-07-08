"""
Bootstrap pre-import de tts-sidecar.

Fuente única de la preparación que debe correr antes de importar cualquier
dependencia pesada (chatterbox, perth, transformers): supresión de warnings,
variables de entorno, niveles de logging y el mock de `pkg_resources` que
Python 3.13 necesita porque el módulo fue eliminado de la stdlib pero `perth`
(dependencia de chatterbox) lo importa en tiempo de import.

`apply()` es idempotente y debe invocarse al principio de cada vía de entrada
del proceso (entry point pip/uv, `bin/tts-sidecar`, `python -m tts_sidecar`,
subcomando congelado `daemon serve`), antes de cualquier otro import del
paquete que pueda arrastrar `chatterbox`/`perth` transitivamente.
"""

import importlib.machinery
import importlib.util
import logging
import os
import sys
import types
import warnings
from pathlib import Path

_applied = False


def _install_pkg_resources_mock() -> None:
    """Instala un mock mínimo de `pkg_resources` si no está disponible.

    El mock debe ser un módulo real con `__spec__`: un objeto bare haría que
    cualquier llamada posterior a `importlib.util.find_spec('pkg_resources')`
    lanzara "pkg_resources.__spec__ is not set" (p. ej. desde el subcomando
    congelado `daemon serve`, que corre en el mismo proceso que el entry point
    del CLI y reconsulta el spec).
    """
    if 'pkg_resources' in sys.modules:
        return
    if importlib.util.find_spec('pkg_resources') is not None:
        return

    def _resource_filename(package, resource):
        spec = importlib.util.find_spec(package)
        if spec and spec.submodule_search_locations:
            return str(Path(spec.submodule_search_locations[0]) / resource)
        return resource

    mock = types.ModuleType('pkg_resources')
    mock.resource_filename = _resource_filename
    mock.__spec__ = importlib.machinery.ModuleSpec('pkg_resources', None)
    sys.modules['pkg_resources'] = mock


def apply() -> None:
    """Aplica el bootstrap pre-import. Idempotente: una segunda invocación es no-op."""
    global _applied
    if _applied:
        return
    _applied = True

    warnings.filterwarnings("ignore")
    os.environ["PYTHONWARNINGS"] = "ignore"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["TRANSFORMERS_VERBOSITY"] = "error"
    os.environ["TRANSFORMERS_NO_ADVISORY_WARNINGS"] = "1"
    os.environ["TOKENIZERS_PARALLELISM"] = "false"

    logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
    logging.getLogger("chatterbox.models.tokenizers.tokenizer").setLevel(logging.ERROR)
    logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer").setLevel(logging.ERROR)

    _install_pkg_resources_mock()
