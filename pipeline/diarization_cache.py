"""Cache identity and persistence for completed episode diarization."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from pipeline.cache import atomic_write_json, signatures_match
from pipeline.run_request import RunRequest


def load_completed_turns(
    path: str | Path,
    request: RunRequest,
    source_signature: dict[str, Any],
    *,
    model: str,
    stitching_version: int,
) -> tuple[list[dict], dict] | None:
    """Load turns only when every inference-affecting identity field matches."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            cache = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    valid = (
        isinstance(cache, dict)
        and cache.get("max_duration") == request.max_duration
        and cache.get("num_speakers") == request.num_speakers
        and cache.get("model") == model
        and cache.get("strategy") == request.diarization_strategy
        and (request.diarization_strategy != "windowed"
             or cache.get("stitching_version") == stitching_version)
        and (request.diarization_strategy != "windowed"
             or cache.get("second_speaker_max_cosine") == request.second_speaker_max_cosine)
        and cache.get("window_seconds") == request.diarization_window
        and cache.get("overlap_seconds") == request.diarization_overlap
        and signatures_match(cache.get("source"), source_signature)
        and isinstance(cache.get("turns"), list)
    )
    if not valid:
        return None
    diagnostics = cache.get("stitching_diagnostics")
    return cache["turns"], (diagnostics if isinstance(diagnostics, dict)
                            else {"strategy": request.diarization_strategy})


def save_completed_turns(
    path: str | Path,
    request: RunRequest,
    source_signature: dict[str, Any],
    turns: list[dict],
    diagnostics: dict,
    *,
    model: str,
    stitching_version: int,
) -> None:
    atomic_write_json(str(path), {
        "source": source_signature,
        "max_duration": request.max_duration,
        "num_speakers": request.num_speakers,
        "model": model,
        "strategy": request.diarization_strategy,
        "stitching_version": (stitching_version
                               if request.diarization_strategy == "windowed" else None),
        "second_speaker_max_cosine": (
            request.second_speaker_max_cosine
            if request.diarization_strategy == "windowed" else None),
        "stitching_diagnostics": diagnostics,
        "window_seconds": request.diarization_window,
        "overlap_seconds": request.diarization_overlap,
        "turns": turns,
    })
