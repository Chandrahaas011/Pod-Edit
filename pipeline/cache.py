"""Small, deterministic cache helpers used by the pipeline.

The project processes multi-gigabyte media, so hashing an entire source on every
run would be wasteful.  A signature combines the resolved path, file metadata,
and hashes of blocks from the beginning and end of the file.  This is strong
enough to prevent the historical failure mode where a different camera file was
silently paired with audio or diarization from an earlier run.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path


SIGNATURE_VERSION = 1
BLOCK_SIZE = 1024 * 1024


def file_signature(path: str) -> dict:
    source = Path(path).resolve()
    stat = source.stat()
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        digest.update(handle.read(BLOCK_SIZE))
        if stat.st_size > BLOCK_SIZE:
            handle.seek(max(0, stat.st_size - BLOCK_SIZE))
            digest.update(handle.read(BLOCK_SIZE))
    return {
        "version": SIGNATURE_VERSION,
        "path": str(source),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "edge_sha256": digest.hexdigest(),
    }


def signatures_match(left: dict | None, right: dict | None) -> bool:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    keys = ("version", "path", "size", "mtime_ns", "edge_sha256")
    return all(left.get(key) == right.get(key) for key in keys)


def load_json(path: str) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            value = json.load(handle)
        return value if isinstance(value, dict) else None
    except (OSError, ValueError):
        return None


def atomic_write_json(path: str, payload: dict) -> None:
    """Write JSON without leaving a half-written cache after interruption."""
    target = os.path.abspath(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    temporary = target + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(temporary, target)
