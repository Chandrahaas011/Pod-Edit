"""Fast, dependency-light checks performed before PodEdit starts expensive work."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shutil
import json
import subprocess
import tempfile

from pipeline.job_contract import JobSpec


MIN_FREE_BYTES = 2 * 1024 ** 3
RECOMMENDED_FREE_BYTES = 4 * 1024 ** 3


@dataclass(frozen=True)
class PreflightIssue:
    """A GUI-safe preflight result with a stable machine-readable code."""

    code: str
    message: str
    severity: str = "error"


def _model_cache_has_files(project_root: Path) -> bool:
    cache_root = Path(os.environ.get("PODEDIT_MODEL_CACHE",
                                     project_root / ".model_cache"))
    try:
        return cache_root.is_dir() and any(path.is_file() for path in cache_root.rglob("*"))
    except OSError:
        return False


def _job_path(raw_path: str, project_root: Path) -> Path:
    """Resolve paths exactly as the worker's child process will resolve them."""
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else project_root / path


def run_preflight(spec: JobSpec, project_root: str | Path) -> list[PreflightIssue]:
    """Return deterministic checks without importing media or neural libraries.

    This intentionally verifies only prerequisites that can be known cheaply.
    Codec readability and model validity remain engine-stage checks, where their
    detailed diagnostics can be reported by the underlying library.
    """
    root = Path(project_root).resolve()
    output = _job_path(spec.output, root)
    issues: list[PreflightIssue] = []

    for label, raw_path in (("camera1", spec.camera1), ("camera2", spec.camera2)):
        path = _job_path(raw_path, root)
        if not path.is_file():
            issues.append(PreflightIssue(
                "INPUT_NOT_FOUND", f"{label} does not exist or is not a file: {path}"))
        elif not os.access(path, os.R_OK):
            issues.append(PreflightIssue(
                "INPUT_NOT_READABLE", f"{label} is not readable: {path}"))

    parent = output.parent
    if not parent.exists():
        issues.append(PreflightIssue(
            "OUTPUT_PARENT_NOT_FOUND", f"Output parent does not exist: {parent}"))
    elif not parent.is_dir():
        issues.append(PreflightIssue(
            "OUTPUT_PARENT_INVALID", f"Output parent is not a directory: {parent}"))
    else:
        try:
            with tempfile.NamedTemporaryFile(
                    prefix=".podedit-write-check-", dir=parent, delete=True):
                pass
        except OSError as exc:
            issues.append(PreflightIssue(
                "OUTPUT_NOT_WRITABLE", f"Output parent is not writable: {parent}: {exc}"))
        try:
            free = shutil.disk_usage(parent).free
        except OSError as exc:
            issues.append(PreflightIssue("OUTPUT_DISK_UNKNOWN",
                                         f"Could not inspect free space at {parent}: {exc}"))
        else:
            if free < MIN_FREE_BYTES:
                issues.append(PreflightIssue(
                    "OUTPUT_DISK_LOW",
                    f"Only {free / 1024 ** 3:.2f} GiB free at {parent}; PodEdit needs at least "
                    f"{MIN_FREE_BYTES / 1024 ** 3:.0f} GiB per active episode."))
            elif free < RECOMMENDED_FREE_BYTES:
                issues.append(PreflightIssue(
                    "OUTPUT_DISK_RECOMMENDED",
                    f"Only {free / 1024 ** 3:.2f} GiB free at {parent}; {RECOMMENDED_FREE_BYTES / 1024 ** 3:.0f} GiB "
                    "is recommended when review rendering is enabled.", "warning"))

    if shutil.which("ffmpeg") is None:
        issues.append(PreflightIssue("FFMPEG_NOT_FOUND", "ffmpeg was not found on PATH."))
    if shutil.which("ffprobe") is None:
        issues.append(PreflightIssue("FFPROBE_NOT_FOUND", "ffprobe was not found on PATH."))

    if spec.options.get("offline") and not _model_cache_has_files(root):
        issues.append(PreflightIssue(
            "OFFLINE_MODEL_CACHE_MISSING",
            "Offline mode was requested but the configured model cache has no model files."))
    return issues


def inspect_source(path: str) -> dict:
    """Read display metadata with ffprobe without importing OpenCV or PyTorch."""
    command = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,width,height,avg_frame_rate,duration:format=duration",
        "-of", "json", path,
    ]
    completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=20, check=True)
    payload = json.loads(completed.stdout)
    streams = payload.get("streams")
    if not isinstance(streams, list) or not streams:
        raise ValueError("ffprobe found no readable video stream")
    video_streams = [item for item in streams
                     if isinstance(item, dict) and item.get("codec_type") == "video"]
    audio_streams = [item for item in streams
                     if isinstance(item, dict) and item.get("codec_type") == "audio"]
    if not video_streams:
        raise ValueError("ffprobe found no readable video stream")
    if not audio_streams:
        raise ValueError("ffprobe found no audio stream required for synchronization")
    stream = video_streams[0]
    numerator, denominator = (stream.get("avg_frame_rate") or "0/1").split("/", 1)
    fps = float(numerator) / float(denominator) if float(denominator) else 0.0
    duration = stream.get("duration") or payload.get("format", {}).get("duration") or 0
    metadata = {
        "path": str(Path(path).resolve()), "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0), "fps": fps,
        "duration_seconds": float(duration), "has_audio": True,
    }
    if (metadata["width"] <= 0 or metadata["height"] <= 0 or metadata["fps"] <= 0
            or metadata["duration_seconds"] <= 0):
        raise ValueError("ffprobe returned invalid video dimensions, frame rate, or duration")
    return metadata
