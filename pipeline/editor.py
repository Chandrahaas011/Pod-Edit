"""Editorial decision policy for converting diarization into camera shots."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class EditorialProfile:
    name: str
    bridge_gap: float
    min_takeover: float
    min_shot: float
    cut_lead: float


PROFILES = {
    # Conservative is suitable for interviews with long answers.
    "conservative": EditorialProfile("conservative", 0.45, 1.80, 3.00, 0.08),
    # Balanced suppresses acknowledgements but follows genuine exchanges.
    "balanced": EditorialProfile("balanced", 0.35, 1.10, 2.00, 0.10),
    # Responsive keeps faster debate-style turns while still rejecting blips.
    "responsive": EditorialProfile("responsive", 0.25, 0.65, 1.20, 0.08),
}


def _merge_speaker_turns(turns: list, bridge_gap: float, total_duration: float) -> list:
    cleaned = []
    for turn in sorted(turns, key=lambda item: (item["speaker"], item["start"], item["end"])):
        start = max(0.0, min(float(turn["start"]), total_duration))
        end = max(start, min(float(turn["end"]), total_duration))
        if end <= start:
            continue
        item = {"speaker": str(turn["speaker"]), "start": start, "end": end}
        if (cleaned and cleaned[-1]["speaker"] == item["speaker"]
                and item["start"] - cleaned[-1]["end"] <= bridge_gap):
            cleaned[-1]["end"] = max(cleaned[-1]["end"], item["end"])
        else:
            cleaned.append(item)
    return sorted(cleaned, key=lambda item: (item["start"], item["end"], item["speaker"]))


def _floor_intervals(turns: list, default_speaker: str, total_duration: float) -> list:
    """Resolve overlap by holding the current floor while that speaker remains active.

    A short interrupter no longer steals the shot merely because their start event is
    later.  When the current speaker stops, the longest remaining active turn wins.
    """
    boundaries = {0.0, total_duration}
    for turn in turns:
        boundaries.add(turn["start"])
        boundaries.add(turn["end"])
    points = sorted(boundaries)
    current = default_speaker
    intervals = []
    for start, end in zip(points, points[1:]):
        if end <= start:
            continue
        active = [turn for turn in turns if turn["start"] < end and turn["end"] > start]
        active_speakers = {turn["speaker"] for turn in active}
        if current not in active_speakers and active:
            winner = max(active, key=lambda turn: (turn["end"] - start, -turn["start"]))
            current = winner["speaker"]
        if intervals and intervals[-1]["speaker"] == current:
            intervals[-1]["end"] = end
        else:
            intervals.append({"start": start, "end": end, "speaker": current})
    return intervals


def _suppress_short_takeovers(intervals: list, min_takeover: float, min_shot: float) -> tuple[list, int]:
    if not intervals:
        return [], 0
    working = [dict(item) for item in intervals]
    suppressed = 0
    changed = True
    while changed and len(working) > 1:
        changed = False
        for index, item in enumerate(working):
            duration = item["end"] - item["start"]
            previous = working[index - 1] if index > 0 else None
            threshold = min_takeover
            if previous is not None:
                previous_duration = previous["end"] - previous["start"]
                if previous_duration < min_shot:
                    threshold = max(threshold, min_shot - previous_duration)
            if index > 0 and duration < threshold:
                item["speaker"] = previous["speaker"]
                suppressed += 1
                changed = True
        fused = []
        for item in working:
            if fused and fused[-1]["speaker"] == item["speaker"]:
                fused[-1]["end"] = item["end"]
            else:
                fused.append(item)
        working = fused
    return working, suppressed


def build_editorial_segments(
    turns: list,
    speaker_to_camera: dict,
    total_duration: float,
    profile_name: str = "balanced",
) -> tuple[list, dict]:
    if profile_name not in PROFILES:
        raise ValueError(f"Unknown editorial profile: {profile_name}")
    if total_duration <= 0:
        raise ValueError("total_duration must be positive")
    profile = PROFILES[profile_name]
    totals = {}
    for turn in turns:
        totals[turn["speaker"]] = totals.get(turn["speaker"], 0.0) + max(0.0, turn["end"] - turn["start"])
    default_speaker = max(totals, key=totals.get) if totals else next(iter(speaker_to_camera), "SPEAKER_00")

    merged_turns = _merge_speaker_turns(turns, profile.bridge_gap, total_duration)
    floor = _floor_intervals(merged_turns, default_speaker, total_duration)
    smoothed, suppressed = _suppress_short_takeovers(floor, profile.min_takeover, profile.min_shot)

    # Move a cut slightly before the detected onset.  This visual lead lets the
    # viewer see the new speaker form the first syllable, a common dialogue-editing
    # convention, while never violating the preceding minimum shot.
    for index in range(1, len(smoothed)):
        boundary = smoothed[index]["start"]
        earliest = smoothed[index - 1]["start"] + profile.min_shot
        shifted = max(earliest, boundary - profile.cut_lead)
        smoothed[index - 1]["end"] = shifted
        smoothed[index]["start"] = shifted

    segments = []
    for item in smoothed:
        camera = int(speaker_to_camera.get(item["speaker"], 1))
        start = item["start"]
        end = item["end"]
        if segments and segments[-1]["camera"] == camera:
            segments[-1]["duration"] = end - segments[-1]["start"]
        else:
            segments.append({"start": start, "duration": end - start, "camera": camera})

    # Rebuild from a frame-independent continuous cursor and remove float noise.
    cursor = 0.0
    final = []
    for segment in segments:
        duration = max(0.0, segment["duration"])
        if duration == 0:
            continue
        final.append({"start": round(cursor, 6), "duration": round(duration, 6),
                      "camera": segment["camera"]})
        cursor += duration
    if final:
        final[-1]["duration"] = round(total_duration - final[-1]["start"], 6)

    diagnostics = {
        "profile": asdict(profile),
        "input_turns": len(turns),
        "bridged_turns": len(merged_turns),
        "raw_floor_intervals": len(floor),
        "suppressed_takeovers": suppressed,
        "final_segments": len(final),
    }
    return final, diagnostics
