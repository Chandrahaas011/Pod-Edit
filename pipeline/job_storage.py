"""Conservative inventory and cleanup planning for one PodEdit job folder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


CATEGORY_PATHS = {
    "review-media": (
        "podedit_preview.mp4", "podedit_switch_review.mp4", "podedit_priority_review.mp4"),
    "analysis-cache": ("diarization_windows", "raw_turns.json", "visual_mapping_cache.json"),
    "derived-audio": (
        "camera1_audio.wav", "camera1_audio.wav.meta.json",
        "camera2_audio.wav", "camera2_audio.wav.meta.json"),
    "control-logs": (".podedit-control",),
}


@dataclass(frozen=True)
class StorageItem:
    category: str
    path: Path
    bytes: int


def _tree_size(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def inventory_job(output: str | Path) -> list[StorageItem]:
    """List only known reproducible artifacts contained by one job root."""
    root = Path(output).resolve()
    items: list[StorageItem] = []
    for category, relative_paths in CATEGORY_PATHS.items():
        for relative in relative_paths:
            path = (root / relative).resolve()
            if root not in path.parents or not path.exists():
                continue
            items.append(StorageItem(category, path, _tree_size(path)))
    return items


def remove_items(output: str | Path, categories: set[str]) -> tuple[int, int]:
    """Delete selected known derivatives; returns (items, bytes reclaimed)."""
    unknown = categories - CATEGORY_PATHS.keys()
    if unknown:
        raise ValueError(f"Unknown storage categories: {', '.join(sorted(unknown))}")
    selected = [item for item in inventory_job(output) if item.category in categories]
    for item in selected:
        if item.path.is_dir():
            shutil.rmtree(item.path)
        else:
            item.path.unlink()
    return len(selected), sum(item.bytes for item in selected)
