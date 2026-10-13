"""Small engine services extracted from CLI orchestration one stage at a time."""

from __future__ import annotations

from typing import Callable

from pipeline.run_layout import RunLayout
from pipeline.run_request import RunRequest


CancelCheck = Callable[[str], None]


def probe_sources(request: RunRequest) -> tuple[dict, dict]:
    """Probe both cameras while preserving their native-rate metadata."""
    from pipeline.probe import probe_video

    camera1 = probe_video(request.camera1)
    camera2 = probe_video(request.camera2)
    return camera1, camera2


def extract_source_audio(request: RunRequest, layout: RunLayout, cancel_check: CancelCheck) -> None:
    """Build/reuse both source-bound audio tracks at the request duration cap."""
    from pipeline.audio_extractor import extract_audio

    cancel_check("before audio extraction")
    extract_audio(request.camera1, str(layout.camera1_audio), max_duration=request.max_duration)
    # Camera 1 remains 48-kHz stereo because it is the exported master track.
    # Camera 2 is synchronization evidence only; 16-kHz mono preserves the
    # speech-band correlation signal at one sixth of the PCM storage.
    extract_audio(request.camera2, str(layout.camera2_audio), sample_rate=16000,
                  max_duration=request.max_duration, channels=1)


def resolve_sync(request: RunRequest, layout: RunLayout, cancel_check: CancelCheck) -> dict:
    """Return one live/manual offset and persist it as the run's source of truth."""
    from pipeline.cache import atomic_write_json

    cancel_check("before synchronization")
    if request.sync_offset is not None:
        result = {"offset_seconds": request.sync_offset, "source": "manual-override"}
    else:
        # soundfile/soxr/scipy are unnecessary when the user supplied a verified
        # offset, so keep their import off that fast path.
        from pipeline.sync_engine import estimate_offset
        result = estimate_offset(str(layout.camera1_audio), str(layout.camera2_audio))
    atomic_write_json(str(layout.sync_metrics), result)
    return result
