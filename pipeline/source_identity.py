"""Deterministic identity for source inputs that affect frozen PodEdit binaries."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json


SOURCE_FILES = ("main.py", "worker.py")
SOURCE_GLOBS = ("pipeline/*.py", "desktop/**/*.cs", "desktop/**/*.xaml", "packaging/*.spec")


def fingerprint_sources(project_root: str | Path) -> dict:
    root = Path(project_root).resolve()
    paths = {root / name for name in SOURCE_FILES}
    for pattern in SOURCE_GLOBS:
        paths.update(root.glob(pattern))
    files = []
    for path in sorted((item for item in paths if item.is_file()),
                       key=lambda item: item.relative_to(root).as_posix()):
        content = path.read_bytes()
        files.append({"path": path.relative_to(root).as_posix(), "bytes": len(content),
                      "sha256": hashlib.sha256(content).hexdigest()})
    encoded = json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"schema_version": 1, "file_count": len(files),
            "identity_sha256": hashlib.sha256(encoded).hexdigest(), "files": files}


def compare_source_fingerprints(expected: dict, actual: dict) -> dict:
    expected_files = {item["path"]: item["sha256"] for item in expected.get("files", [])}
    actual_files = {item["path"]: item["sha256"] for item in actual.get("files", [])}
    return {
        "matches": expected.get("identity_sha256") == actual.get("identity_sha256"),
        "added": sorted(actual_files.keys() - expected_files.keys()),
        "removed": sorted(expected_files.keys() - actual_files.keys()),
        "changed": sorted(name for name in expected_files.keys() & actual_files.keys()
                          if expected_files[name] != actual_files[name]),
        "expected_sha256": expected.get("identity_sha256"),
        "actual_sha256": actual.get("identity_sha256"),
    }
