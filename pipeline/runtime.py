"""Process-local runtime configuration for a PodEdit engine invocation."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from pipeline.run_request import RunRequest


def configure_runtime(request: RunRequest, project_root: str | Path) -> Path:
    """Set only missing runtime variables and return the project model cache.

    Call this before importing Hugging Face/PyTorch modules: those libraries read
    cache/offline settings during import. Existing explicit user environment
    settings are respected rather than overwritten.
    """
    root = Path(project_root).resolve()
    model_cache = Path(os.environ.get("PODEDIT_MODEL_CACHE", root / ".model_cache")).resolve()
    os.environ.setdefault("HF_HOME", str(model_cache / "huggingface"))
    os.environ.setdefault("TORCH_HOME", str(model_cache / "torch"))
    os.environ.setdefault("PODEDIT_MODEL_CACHE", str(model_cache))
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if getattr(sys, "frozen", False):
        # Numba cannot locate source files inside PyInstaller's archive for its
        # on-disk decorator cache. Production no longer imports librosa, but
        # keep this guard for optional third-party lazy paths.
        os.environ.setdefault("NUMBA_DISABLE_JIT", "1")
    try:
        configured_cores = int(os.environ.get("LOKY_MAX_CPU_COUNT", "0"))
    except ValueError:
        configured_cores = 0
    if configured_cores < 1:
        os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, os.cpu_count() or 1))
    if request.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    return model_cache
