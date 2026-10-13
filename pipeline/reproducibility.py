"""Stable fingerprints for comparing editorial output across reruns/builds."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json


ARTIFACT_KEYS = ("segments", "xml", "cut_report_json", "cut_report_csv")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fingerprint_manifest(manifest_path: str | Path) -> dict:
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    outputs = manifest.get("outputs", {})
    artifacts = {}
    for key in ARTIFACT_KEYS:
        raw = outputs.get(key)
        if not raw:
            artifacts[key] = {"present": False}
            continue
        path = Path(raw)
        if not path.is_absolute():
            path = manifest_file.parent / path
        artifacts[key] = ({"present": True, "bytes": path.stat().st_size,
                           "sha256": _sha256(path)} if path.is_file()
                          else {"present": False})
    stable_identity = {
        "podedit_version": manifest.get("podedit_version"),
        "configuration": manifest.get("configuration"),
        "inputs": {name: {key: value.get(key) for key in ("size", "edge_sha256")}
                   for name, value in manifest.get("inputs", {}).items()},
        "sync": {key: manifest.get("sync", {}).get(key)
                 for key in ("offset_seconds", "source")},
        "speaker_to_camera": manifest.get("speaker_to_camera"),
        "artifacts": artifacts,
    }
    encoded = json.dumps(stable_identity, sort_keys=True, separators=(",", ":")).encode()
    return {"schema_version": 1, "manifest": str(manifest_file),
            "identity_sha256": hashlib.sha256(encoded).hexdigest(), **stable_identity}


def compare_fingerprints(expected: dict, actual: dict) -> dict:
    matches = expected.get("identity_sha256") == actual.get("identity_sha256")
    changed_artifacts = [key for key in ARTIFACT_KEYS
                         if expected.get("artifacts", {}).get(key) !=
                         actual.get("artifacts", {}).get(key)]
    return {"matches": matches, "changed_artifacts": changed_artifacts,
            "expected_sha256": expected.get("identity_sha256"),
            "actual_sha256": actual.get("identity_sha256")}
