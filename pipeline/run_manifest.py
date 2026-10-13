"""Construction of a portable, auditable completed-run manifest."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.run_layout import RunLayout
from pipeline.run_request import RunRequest


def build_manifest(
    request: RunRequest,
    layout: RunLayout,
    *,
    inputs: dict[str, Any],
    sync: dict[str, Any],
    diarization_diagnostics: dict[str, Any],
    speaker_to_camera: dict[str, int],
    mapping_diagnostics: dict[str, Any],
    editorial_diagnostics: dict[str, Any],
    reaction_diagnostics: dict[str, Any],
    cut_report_summary: dict[str, Any],
    segment_validation: dict[str, Any],
    xml_validation: dict[str, Any],
    runtime_seconds: float,
    stage_seconds: dict[str, float],
    duration_seconds: float,
    segments: list[dict[str, Any]],
    camera_screen_time_seconds: dict[int, float],
) -> dict[str, Any]:
    """Return the schema-v2 manifest without writing or probing files."""
    durations = sorted(segment["duration"] for segment in segments)
    measured_stage_seconds = sum(float(seconds) for seconds in stage_seconds.values())
    return {
        "schema_version": 2,
        "podedit_version": "1.5",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": inputs,
        "configuration": {
            "mode": request.mode,
            "num_speakers": request.num_speakers,
            "diarization_strategy": request.diarization_strategy,
            "diarization_window": request.diarization_window,
            "diarization_overlap": request.diarization_overlap,
            "second_speaker_max_cosine": request.second_speaker_max_cosine,
            "max_duration": request.max_duration,
            "editorial_profile": request.editorial_profile,
            "reaction_cutaways": not request.no_reactions,
            "max_primary_shot": request.max_primary_shot,
            "timeline_fps": request.timeline_fps,
            "swap": request.swap,
            "offline": request.offline,
        },
        "sync": sync,
        "diarization_diagnostics": diarization_diagnostics,
        "speaker_to_camera": speaker_to_camera,
        "mapping_diagnostics": mapping_diagnostics,
        "editorial_diagnostics": editorial_diagnostics,
        "reaction_diagnostics": reaction_diagnostics,
        "cut_report_summary": cut_report_summary,
        "validation": {"segments": segment_validation, "xml": xml_validation},
        "metrics": {
            "runtime_seconds": runtime_seconds,
            "stage_seconds": {name: float(seconds)
                              for name, seconds in stage_seconds.items()},
            "unattributed_seconds": max(0.0, runtime_seconds - measured_stage_seconds),
            "real_time_factor": runtime_seconds / duration_seconds,
            "duration_seconds": duration_seconds,
            "segments": len(segments),
            "cuts_per_minute": max(0, len(segments) - 1) / (duration_seconds / 60.0),
            "maximum_shot_seconds": max(durations),
            "median_shot_seconds": durations[len(durations) // 2],
            "camera_screen_time_seconds": camera_screen_time_seconds,
        },
        "outputs": {
            "segments": str(layout.segments.resolve()),
            "xml": str(layout.timeline_xml.resolve()),
            "camera1_audio": str(layout.camera1_audio.resolve()),
            "camera2_audio": str(layout.camera2_audio.resolve()),
            "preview": None if request.no_preview else str(layout.preview.resolve()),
            "switch_review": None if request.no_preview else str(layout.switch_review.resolve()),
            "priority_review": (None if request.no_preview or not layout.priority_review.exists()
                                else str(layout.priority_review.resolve())),
            "cut_report_json": str(layout.cut_report_json.resolve()),
            "cut_report_csv": str(layout.cut_report_csv.resolve()),
        },
    }
