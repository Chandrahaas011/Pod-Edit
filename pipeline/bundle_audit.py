"""Hash inventory and exclusion policy for a release folder."""

from __future__ import annotations

from pathlib import Path
import hashlib


FORBIDDEN_ROOTS = {
    "datasets", "results", "tests", ".git", ".nuget", ".dotnet_cli", ".desktop_state",
}
FORBIDDEN_SUFFIXES = {".py", ".pyc", ".pyx", ".pdb", ".spec", ".tex"}
REQUIRED_FILES = {
    "PodEdit.Desktop.exe", "PodEdit.Worker.exe", "PodEdit.Engine.exe",
    "tools/ffmpeg/bin/ffmpeg.exe", "tools/ffmpeg/bin/ffprobe.exe",
    "THIRD_PARTY_INVENTORY.md", "runtime-audit.json", "requirements-lock.txt",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def audit(root: Path) -> dict:
    root = root.resolve()
    files = []
    forbidden = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root)
        parts = {part.lower() for part in relative.parts}
        runtime_source_packages = {"speechbrain", "torch", "torchaudio", "sklearn", "cv2"}
        runtime_source_exception = (
            len(relative.parts) >= 2 and relative.parts[0].lower() == "_internal"
            and relative.parts[1].lower() in runtime_source_packages
            and path.suffix.lower() in {".py", ".pyx"})
        if (relative.parts[0].lower() in FORBIDDEN_ROOTS or ".env" in parts or
                "__pycache__" in parts or
                (path.suffix.lower() in FORBIDDEN_SUFFIXES and not runtime_source_exception)):
            forbidden.append(str(relative))
        files.append({"path": str(relative).replace("\\", "/"),
                      "bytes": path.stat().st_size, "sha256": _sha256(path)})
    present = {item["path"] for item in files}
    missing = sorted(REQUIRED_FILES - present)
    return {"schema_version": 1, "root": str(root), "files": files,
            "file_count": len(files), "total_bytes": sum(item["bytes"] for item in files),
            "forbidden": forbidden, "missing_required": missing,
            "passed": not forbidden and not missing}
