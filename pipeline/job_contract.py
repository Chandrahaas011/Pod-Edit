"""Stable GUI-to-worker job schema for PodEdit's headless processing engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar
import json
import math
import uuid


JOB_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1


class JobValidationError(ValueError):
    """Raised when an untrusted job JSON cannot safely become CLI arguments."""


@dataclass(frozen=True)
class JobSpec:
    """Versioned, serializable request accepted by the future desktop client.

    The worker deliberately accepts a finite set of options. This prevents a
    GUI job file from smuggling arbitrary command-line flags into the engine.
    """

    camera1: str
    camera2: str
    output: str
    options: dict[str, Any] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: int = JOB_SCHEMA_VERSION

    _BOOLEAN_FLAGS: ClassVar[frozenset[str]] = frozenset(
        {"swap", "force", "no_preview", "no_reactions", "offline"})
    _VALUE_FLAGS: ClassVar[dict[str, str]] = {
        "mode": "--mode",
        "num_speakers": "--num-speakers",
        "max_duration": "--max-duration",
        "diarization_strategy": "--diarization-strategy",
        "diarization_window": "--diarization-window",
        "diarization_overlap": "--diarization-overlap",
        "second_speaker_max_cosine": "--second-speaker-max-cosine",
        "sync_offset": "--sync-offset",
        "preview_start": "--preview-start",
        "editorial_profile": "--editorial-profile",
        "max_primary_shot": "--max-primary-shot",
        "timeline_fps": "--timeline-fps",
    }
    _CHOICES: ClassVar[dict[str, frozenset[str]]] = {
        "mode": frozenset({"hybrid", "audio"}),
        "diarization_strategy": frozenset({"windowed", "global"}),
        "editorial_profile": frozenset({"conservative", "balanced", "responsive"}),
    }
    _NUMERIC_OPTIONS: ClassVar[frozenset[str]] = frozenset({
        "num_speakers", "max_duration", "diarization_window", "diarization_overlap",
        "second_speaker_max_cosine", "sync_offset", "preview_start",
        "max_primary_shot", "timeline_fps",
    })

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "JobSpec":
        if not isinstance(payload, dict):
            raise JobValidationError("Job JSON must be an object.")
        if payload.get("schema_version") != JOB_SCHEMA_VERSION:
            raise JobValidationError(
                f"Unsupported job schema {payload.get('schema_version')!r}; "
                f"expected {JOB_SCHEMA_VERSION}.")
        options = payload.get("options", {})
        if not isinstance(options, dict):
            raise JobValidationError("Job 'options' must be an object.")
        for field_name in ("camera1", "camera2", "output"):
            if not isinstance(payload.get(field_name), str):
                raise JobValidationError(f"Job '{field_name}' must be a string path.")
        if "job_id" in payload and payload["job_id"] is not None and not isinstance(payload["job_id"], str):
            raise JobValidationError("Job 'job_id' must be a string.")
        spec = cls(
            camera1=payload["camera1"],
            camera2=payload["camera2"],
            output=payload["output"],
            options=dict(options),
            job_id=str(payload.get("job_id") or uuid.uuid4()),
            schema_version=payload["schema_version"],
        )
        spec.validate()
        return spec

    @classmethod
    def load(cls, path: str | Path) -> "JobSpec":
        try:
            # ``utf-8-sig`` accepts normal UTF-8 and the BOM that PowerShell
            # commonly writes, without changing the job-file wire format.
            with open(path, "r", encoding="utf-8-sig") as handle:
                return cls.from_dict(json.load(handle))
        except (OSError, json.JSONDecodeError) as exc:
            raise JobValidationError(f"Cannot read job file {path}: {exc}") from exc

    def validate(self) -> None:
        for label, value in (("camera1", self.camera1), ("camera2", self.camera2),
                             ("output", self.output)):
            if not value.strip():
                raise JobValidationError(f"Job '{label}' is required.")
        if Path(self.camera1).resolve() == Path(self.camera2).resolve():
            raise JobValidationError("camera1 and camera2 must be different files.")
        unknown = set(self.options) - self._BOOLEAN_FLAGS - set(self._VALUE_FLAGS)
        if unknown:
            raise JobValidationError("Unsupported job option(s): " + ", ".join(sorted(unknown)))
        for flag in self._BOOLEAN_FLAGS:
            if flag in self.options and not isinstance(self.options[flag], bool):
                raise JobValidationError(f"Option '{flag}' must be boolean.")
        for name, value in self.options.items():
            if name in self._VALUE_FLAGS and isinstance(value, (dict, list, tuple, set)):
                raise JobValidationError(f"Option '{name}' must be a scalar value.")
            if name in self._VALUE_FLAGS and isinstance(value, bool):
                raise JobValidationError(f"Option '{name}' must not be boolean.")
        for name, choices in self._CHOICES.items():
            if name in self.options and self.options[name] not in choices:
                raise JobValidationError(
                    f"Option '{name}' must be one of: {', '.join(sorted(choices))}.")
        numbers: dict[str, float] = {}
        for name in self._NUMERIC_OPTIONS:
            if name not in self.options or self.options[name] is None:
                continue
            try:
                number = float(self.options[name])
            except (TypeError, ValueError, OverflowError) as exc:
                raise JobValidationError(f"Option '{name}' must be numeric.") from exc
            if not math.isfinite(number):
                raise JobValidationError(f"Option '{name}' must be finite.")
            numbers[name] = number
        if ("num_speakers" in self.options
                and not isinstance(self.options["num_speakers"], int)):
            raise JobValidationError("Option 'num_speakers' must be the integer 2.")
        if "num_speakers" in numbers and numbers["num_speakers"] != 2:
            raise JobValidationError("This release supports exactly two speakers/cameras.")
        for name in ("max_duration", "timeline_fps"):
            if name in numbers and numbers[name] <= 0:
                raise JobValidationError(f"Option '{name}' must be positive.")
        if "max_primary_shot" in numbers and numbers["max_primary_shot"] < 20:
            raise JobValidationError("Option 'max_primary_shot' must be at least 20 seconds.")
        if "preview_start" in numbers and numbers["preview_start"] < 0:
            raise JobValidationError("Option 'preview_start' must not be negative.")
        if ("second_speaker_max_cosine" in numbers
                and not -1 <= numbers["second_speaker_max_cosine"] <= 1):
            raise JobValidationError(
                "Option 'second_speaker_max_cosine' must be between -1 and 1.")
        window = numbers.get("diarization_window", 60.0)
        overlap = numbers.get("diarization_overlap", 15.0)
        if overlap <= 0 or window <= overlap:
            raise JobValidationError(
                "Option 'diarization_window' must exceed a positive overlap.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "camera1": self.camera1,
            "camera2": self.camera2,
            "output": self.output,
            "options": self.options,
        }

    def to_cli_args(self, cancel_file: str | None = None) -> list[str]:
        """Translate only validated fields to the stable legacy CLI contract."""
        self.validate()
        args = ["--cam1", self.camera1, "--cam2", self.camera2, "--output", self.output]
        for name, cli_flag in self._VALUE_FLAGS.items():
            if name in self.options and self.options[name] is not None:
                args.extend([cli_flag, str(self.options[name])])
        for name in sorted(self._BOOLEAN_FLAGS):
            if self.options.get(name, False):
                args.append("--" + name.replace("_", "-"))
        if cancel_file:
            args.extend(["--cancel-file", cancel_file])
        return args


def event(event_type: str, job_id: str, **fields: Any) -> dict[str, Any]:
    """Create a JSON-safe event record without importing heavy engine modules."""
    return {"schema_version": JOB_SCHEMA_VERSION, "event_schema_version": EVENT_SCHEMA_VERSION,
            "type": event_type, "job_id": job_id, **fields}
