"""Typed engine request independent of argparse and the desktop GUI."""

from __future__ import annotations

from dataclasses import dataclass
from argparse import Namespace


@dataclass(frozen=True)
class RunRequest:
    """All supported two-camera engine settings after CLI/job validation."""

    camera1: str
    camera2: str
    output: str
    mode: str
    num_speakers: int
    max_duration: float
    swap: bool
    force: bool
    diarization_strategy: str
    diarization_window: float
    diarization_overlap: float
    second_speaker_max_cosine: float
    sync_offset: float | None
    no_preview: bool
    preview_start: float | None
    editorial_profile: str
    no_reactions: bool
    max_primary_shot: float
    timeline_fps: float
    offline: bool
    cancel_file: str | None

    @classmethod
    def from_namespace(cls, args: Namespace) -> "RunRequest":
        return cls(
            camera1=args.cam1, camera2=args.cam2, output=args.output,
            mode=args.mode, num_speakers=args.num_speakers,
            max_duration=args.max_duration, swap=args.swap, force=args.force,
            diarization_strategy=args.diarization_strategy,
            diarization_window=args.diarization_window,
            diarization_overlap=args.diarization_overlap,
            second_speaker_max_cosine=args.second_speaker_max_cosine,
            sync_offset=args.sync_offset, no_preview=args.no_preview,
            preview_start=args.preview_start, editorial_profile=args.editorial_profile,
            no_reactions=args.no_reactions, max_primary_shot=args.max_primary_shot,
            timeline_fps=args.timeline_fps, offline=args.offline,
            cancel_file=args.cancel_file,
        )

    # Compatibility aliases let the orchestration migrate from argparse in
    # small reviewed steps while GUI callers use the explicit camera names.
    @property
    def cam1(self) -> str:
        return self.camera1

    @property
    def cam2(self) -> str:
        return self.camera2
