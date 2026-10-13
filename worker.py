"""Headless worker bridge for a future Windows desktop client.

It launches the maintained CLI in a child process, mirrors its human-readable
console output, and writes a structured JSONL event stream for a GUI. Keeping
the worker separate means a future GUI never imports Torch or pyannote itself.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

from pipeline.job_contract import JobValidationError, JobSpec, event
from pipeline.preflight import inspect_source, run_preflight


STAGE_RE = re.compile(r"\bSTAGE\s+(\d+)/(\d+)\s+[—-]\s+(.+)$")
WINDOW_RE = re.compile(r"\bwindow\s+(\d+)/(\d+)\b", re.IGNORECASE)


def _application_root() -> Path:
    return Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).parent


def _configure_packaged_tools() -> None:
    """Prefer the release's audited media binaries over machine-global tools."""
    if not getattr(sys, "frozen", False):
        return
    media_bin = _application_root() / "tools" / "ffmpeg" / "bin"
    if media_bin.is_dir():
        os.environ["PATH"] = str(media_bin) + os.pathsep + os.environ.get("PATH", "")
    local_data = Path(os.environ.get("LOCALAPPDATA", _application_root())) / "PodEdit"
    os.environ.setdefault("PODEDIT_DATA_ROOT", str(local_data))
    provisioned_models = local_data / "models"
    bundled_models = _application_root() / ".model_cache"
    os.environ.setdefault(
        "PODEDIT_MODEL_CACHE",
        str(provisioned_models if provisioned_models.is_dir() else bundled_models))


def _engine_command(engine_path: Path | None = None) -> list[str]:
    """Resolve development script or packaged sibling without recursion."""
    if engine_path is not None:
        return [sys.executable, str(engine_path)]
    if getattr(sys, "frozen", False):
        engine = Path(sys.executable).with_name("PodEdit.Engine.exe")
        if not engine.is_file():
            raise FileNotFoundError(f"Packaged engine is missing: {engine}")
        return [str(engine)]
    return [sys.executable, str(Path(__file__).with_name("main.py"))]


class JsonlEventWriter:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(path, "a", encoding="utf-8", buffering=1)

    def write(self, payload: dict) -> None:
        payload.setdefault("timestamp_utc", datetime.now(timezone.utc).isoformat())
        self._handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")

    def close(self) -> None:
        self._handle.close()


def _default_event_path(spec: JobSpec) -> Path:
    return Path(spec.output) / "worker_events.jsonl"


def _emit_result_artifacts(writer: JsonlEventWriter, spec: JobSpec) -> None:
    """Forward validated manifest output paths to the GUI after a successful run."""
    manifest_path = Path(spec.output) / "run_manifest.json"
    try:
        with open(manifest_path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
        outputs = manifest.get("outputs")
        if not isinstance(outputs, dict):
            raise ValueError("missing outputs object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        writer.write(event("job_warning", spec.job_id, code="RUN_MANIFEST_UNREADABLE",
                           message=f"Run succeeded but result manifest could not be read: {exc}"))
        return
    output_root = Path(spec.output).resolve()
    invalid = []
    for name, raw_path in outputs.items():
        if raw_path is None:
            continue
        if not isinstance(raw_path, str):
            invalid.append(f"{name}: path is not text")
            continue
        candidate = Path(raw_path)
        artifact = (candidate if candidate.is_absolute()
                    else output_root / candidate).resolve()
        try:
            artifact.relative_to(output_root)
        except ValueError:
            invalid.append(f"{name}: path escapes job output")
            continue
        if not artifact.is_file():
            invalid.append(f"{name}: file does not exist")
    if invalid:
        writer.write(event("job_warning", spec.job_id, code="ARTIFACT_MANIFEST_INVALID",
                           message="Run completed but artifacts were not announced: "
                                   + "; ".join(invalid)))
        return
    writer.write(event("artifacts_available", spec.job_id,
                       manifest=str(manifest_path.resolve()), outputs=outputs))


def _write_rejection_event(event_path: str | None, message: str) -> None:
    """Best-effort structured feedback when the job cannot be parsed at all."""
    if not event_path:
        return
    writer = JsonlEventWriter(Path(event_path))
    try:
        writer.write(event("job_rejected", "unknown", code="JOB_VALIDATION_FAILED",
                           message=message))
        writer.write(event("job_failed", "unknown", exit_code=2,
                           code="JOB_VALIDATION_FAILED", resumable=False))
    finally:
        writer.close()


def _perform_preflight(writer: JsonlEventWriter, spec: JobSpec) -> int:
    """Write the shared preflight event sequence and return a CLI-style status."""
    writer.write(event("preflight_started", spec.job_id))
    issues = run_preflight(spec, _application_root())
    for issue in issues:
        writer.write(event("job_warning" if issue.severity == "warning" else "job_rejected",
                           spec.job_id, code=issue.code, message=issue.message))
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        print("Worker preflight failed:", file=sys.stderr)
        for issue in errors:
            print(f"  [{issue.code}] {issue.message}", file=sys.stderr)
        writer.write(event("job_failed", spec.job_id, exit_code=2,
                           code="PREFLIGHT_FAILED", resumable=False))
        return 2
    inspection_failures = []
    for camera, path in ((1, spec.camera1), (2, spec.camera2)):
        if not Path(path).is_file():
            continue
        try:
            metadata = inspect_source(path)
            writer.write(event("source_inspected", spec.job_id, camera=camera, **metadata))
        except (OSError, ValueError, KeyError, IndexError, subprocess.SubprocessError) as exc:
            message = f"Camera {camera} is not a readable supported video: {exc}"
            inspection_failures.append(message)
            writer.write(event("job_rejected", spec.job_id, code="SOURCE_INSPECTION_FAILED",
                               message=message))
    if inspection_failures:
        writer.write(event("job_failed", spec.job_id, exit_code=2,
                           code="PREFLIGHT_FAILED", resumable=False))
        return 2
    writer.write(event("preflight_completed", spec.job_id,
                       warnings=sum(issue.severity == "warning" for issue in issues)))
    return 0


def run_preflight_job(spec: JobSpec, event_path: Path) -> int:
    """Validate a job for a GUI without launching inference or media processing."""
    writer = JsonlEventWriter(event_path)
    try:
        writer.write(event("job_preflight_requested", spec.job_id,
                           output=str(Path(spec.output).resolve())))
        return _perform_preflight(writer, spec)
    finally:
        writer.close()


def run_worker(spec: JobSpec, event_path: Path, cancel_file: str | None = None,
               engine_path: Path | None = None) -> int:
    """Run the current CLI with a typed job contract and JSONL observability."""
    writer = JsonlEventWriter(event_path)
    command = [str(part) for part in [*_engine_command(engine_path),
                                     *spec.to_cli_args(cancel_file)]]
    try:
        writer.write(event("job_started", spec.job_id, command=command,
                           output=str(Path(spec.output).resolve()),
                           cancel_file=str(cancel_file) if cancel_file is not None else None))
        if _perform_preflight(writer, spec):
            return 2
        process = subprocess.Popen(
            command,
            cwd=_application_root(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        active_stage: tuple[int, int, str] | None = None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if not line:
                continue
            print(line, flush=True)
            writer.write(event("log", spec.job_id, message=line))
            stage = STAGE_RE.search(line)
            if stage:
                index, total, name = stage.groups()
                next_stage = (int(index), int(total), name.strip())
                if active_stage is not None:
                    prior_index, prior_total, prior_name = active_stage
                    writer.write(event("stage_completed", spec.job_id, stage=prior_index,
                                       total_stages=prior_total, name=prior_name,
                                       progress=prior_index / prior_total))
                active_stage = next_stage
                writer.write(event("stage_started", spec.job_id, stage=int(index),
                                   total_stages=int(total), name=name.strip(),
                                   progress=(int(index) - 1) / int(total)))
            window = WINDOW_RE.search(line)
            if window:
                index, total = (int(value) for value in window.groups())
                writer.write(event("diarization_window_complete", spec.job_id,
                                   window=index, total_windows=total,
                                   progress=index / total))
        close_stdout = getattr(process.stdout, "close", None)
        if close_stdout is not None:
            close_stdout()
        return_code = process.wait()
        if return_code == 0 and active_stage is not None:
            index, total, name = active_stage
            writer.write(event("stage_completed", spec.job_id, stage=index,
                               total_stages=total, name=name, progress=index / total))
        if return_code == 0:
            _emit_result_artifacts(writer, spec)
            writer.write(event("job_completed", spec.job_id, exit_code=return_code))
        elif return_code == 130:
            writer.write(event("job_cancelled", spec.job_id, exit_code=return_code,
                               resumable=True))
        else:
            writer.write(event("job_failed", spec.job_id, exit_code=return_code))
        return return_code
    except OSError as exc:
        writer.write(event("job_failed", spec.job_id, exit_code=1, error=str(exc)))
        print(f"Worker launch failed: {exc}", file=sys.stderr)
        return 1
    finally:
        writer.close()


def main() -> int:
    _configure_packaged_tools()
    parser = argparse.ArgumentParser(description="PodEdit typed headless worker")
    parser.add_argument("--job", required=True, help="Versioned job JSON file")
    parser.add_argument("--events", help="JSONL event output (default: job output folder)")
    parser.add_argument("--cancel-file", help="Sentinel file checked at safe engine boundaries")
    parser.add_argument("--preflight", action="store_true",
                        help="Validate the job without launching the processing engine")
    args = parser.parse_args()
    try:
        spec = JobSpec.load(args.job)
    except JobValidationError as exc:
        _write_rejection_event(args.events, str(exc))
        print(f"Invalid job: {exc}", file=sys.stderr)
        return 2
    event_path = Path(args.events) if args.events else _default_event_path(spec)
    if args.preflight:
        return run_preflight_job(spec, event_path)
    return run_worker(spec, event_path, args.cancel_file)


if __name__ == "__main__":
    raise SystemExit(main())
