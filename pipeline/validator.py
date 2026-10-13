"""Structural validation for segment lists and generated FCP XML 7 files."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET


def validate_segments(segments: list, total_duration: float, tolerance: float = 1e-3) -> dict:
    errors = []
    cursor = 0.0
    if not isinstance(segments, list):
        return {"valid": False, "errors": ["segments must be a list"],
                "duration": cursor, "segments": 0}
    try:
        expected_duration = float(total_duration)
    except (TypeError, ValueError, OverflowError):
        return {"valid": False, "errors": ["total duration must be a finite number"],
                "duration": cursor, "segments": len(segments)}
    for index, segment in enumerate(segments):
        if not isinstance(segment, dict):
            errors.append(f"segment {index} must be an object")
            continue
        try:
            start = float(segment.get("start", -1))
            duration = float(segment.get("duration", 0))
        except (TypeError, ValueError, OverflowError):
            errors.append(f"segment {index} has non-numeric start or duration")
            continue
        camera = segment.get("camera")
        if abs(start - cursor) > tolerance:
            errors.append(f"segment {index} starts at {start:.6f}, expected {cursor:.6f}")
        if duration <= 0:
            errors.append(f"segment {index} has non-positive duration")
        if camera not in (1, 2):
            errors.append(f"segment {index} has invalid camera {camera!r}")
        cursor = start + duration
    if abs(cursor - expected_duration) > tolerance:
        errors.append(f"timeline ends at {cursor:.6f}, expected {expected_duration:.6f}")
    return {"valid": not errors, "errors": errors, "duration": cursor, "segments": len(segments)}


def validate_xml(path: str) -> dict:
    errors = []
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return {"valid": False, "errors": [str(exc)]}
    sequence = root.find("sequence")
    if sequence is None:
        return {"valid": False, "errors": ["missing sequence"]}
    try:
        duration = int(sequence.findtext("duration", "0"))
    except (TypeError, ValueError):
        return {"valid": False, "errors": ["sequence duration is not an integer"]}
    # A full media definition lives inside the first clipitem; later file
    # elements inherit it by id according to XMEML's id convention.
    file_ids = {node.attrib.get("id") for node in root.findall(".//file")
                if node.find("pathurl") is not None}
    video_clips = sequence.findall("./media/video/track/clipitem")
    audio_clips = sequence.findall("./media/audio/track/clipitem")

    def inspect(clips, label):
        spans = []
        for clip in clips:
            try:
                start = int(clip.findtext("start", "-1"))
                end = int(clip.findtext("end", "-1"))
                source_in = int(clip.findtext("in", "-1"))
                source_out = int(clip.findtext("out", "-1"))
            except (TypeError, ValueError):
                errors.append(f"{label} clip {clip.attrib.get('id')} has non-integer timing")
                continue
            reference = clip.find("file")
            if end <= start:
                errors.append(f"{label} clip {clip.attrib.get('id')} has invalid timeline span")
            if source_out - source_in != end - start:
                errors.append(f"{label} clip {clip.attrib.get('id')} source/timeline lengths differ")
            if reference is None or reference.attrib.get("id") not in file_ids:
                errors.append(f"{label} clip {clip.attrib.get('id')} has unresolved file reference")
            spans.append((start, end))
        return spans

    video_spans = sorted(inspect(video_clips, "video"))
    audio_spans = sorted(inspect(audio_clips, "audio"))
    for spans, label in ((video_spans, "video"), (audio_spans, "audio")):
        cursor = 0
        for start, end in spans:
            if start != cursor:
                errors.append(f"{label} coverage discontinuity at frame {cursor} (next {start})")
            cursor = max(cursor, end)
        if cursor != duration:
            errors.append(f"{label} coverage ends at {cursor}, sequence duration is {duration}")
    return {
        "valid": not errors,
        "errors": errors,
        "duration_frames": duration,
        "video_clips": len(video_clips),
        "audio_clips": len(audio_clips),
        "path": os.path.abspath(path),
    }
