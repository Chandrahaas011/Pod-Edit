"""Typed, single-source output layout for one PodEdit processing run."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunLayout:
    """All durable outputs and checkpoints for a job, rooted in one directory."""

    root: Path
    camera1_audio: Path
    camera2_audio: Path
    raw_turns: Path
    segments: Path
    sync_metrics: Path
    visual_mapping_cache: Path
    timeline_xml: Path
    preview: Path
    switch_review: Path
    priority_review: Path
    cut_report_json: Path
    cut_report_csv: Path
    manifest: Path
    diarization_windows: Path

    @classmethod
    def create(cls, output: str | Path) -> "RunLayout":
        root = Path(output).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        return cls(
            root=root,
            camera1_audio=root / "camera1_audio.wav",
            camera2_audio=root / "camera2_audio.wav",
            raw_turns=root / "raw_turns.json",
            segments=root / "podedit_segments.json",
            sync_metrics=root / "sync_metrics.json",
            visual_mapping_cache=root / "visual_mapping_cache.json",
            timeline_xml=root / "podedit_timeline.xml",
            preview=root / "podedit_preview.mp4",
            switch_review=root / "podedit_switch_review.mp4",
            priority_review=root / "podedit_priority_review.mp4",
            cut_report_json=root / "podedit_cut_report.json",
            cut_report_csv=root / "podedit_cut_report.csv",
            manifest=root / "run_manifest.json",
            diarization_windows=root / "diarization_windows",
        )
