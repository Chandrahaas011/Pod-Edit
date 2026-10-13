"""Cut-level audit records for fast, accountable human review."""

from __future__ import annotations

import csv
import math

from pipeline.cache import atomic_write_json
from pipeline.validator import validate_segments


def _timecode(seconds: float, fps: float) -> str:
    total_frames = max(0, round(seconds * fps))
    frames = total_frames % round(fps)
    total_seconds = total_frames // round(fps)
    minutes, secs = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}:{frames:02d}"


def _reaction_type(cut_time, selections, tolerance=0.02):
    for selection in selections:
        start = float(selection["start"])
        end = start + float(selection["duration"])
        if abs(cut_time - start) <= tolerance:
            return "listener_reaction_in"
        if abs(cut_time - end) <= tolerance:
            return "listener_reaction_out"
    return "speaker_change"


def build_cut_report(segments, total_duration, timeline_fps,
                     mapping_diagnostics=None, reaction_diagnostics=None,
                     window_seconds=60.0, overlap_seconds=15.0):
    """Describe every cut and flag transitions that deserve first review."""
    mapping_diagnostics = mapping_diagnostics or {}
    reaction_diagnostics = reaction_diagnostics or {}
    selections = reaction_diagnostics.get("selections", [])
    margin = mapping_diagnostics.get("margin")
    if mapping_diagnostics.get("accepted") is True:
        mapping_status = "visual_verified"
    elif mapping_diagnostics.get("camera_votes_consistent") is False:
        mapping_status = "fallback_inconsistent_visual_votes"
    else:
        mapping_status = "fallback_low_visual_margin"
    stride = window_seconds - overlap_seconds
    seams = []
    seam = window_seconds - overlap_seconds / 2.0
    while seam < total_duration:
        seams.append(seam)
        seam += stride

    cuts = []
    for index in range(1, len(segments)):
        before, after = segments[index - 1], segments[index]
        cut_time = float(after["start"])
        before_duration = float(before["duration"])
        after_duration = float(after["duration"])
        distance_to_seam = min((abs(cut_time - seam) for seam in seams), default=math.inf)
        cut_type = _reaction_type(cut_time, selections)
        flags = []
        if distance_to_seam <= 0.5:
            flags.append("near_window_seam")
        if before_duration < 3.0:
            flags.append("short_preceding_shot")
        if after_duration < 3.0:
            flags.append("short_following_shot")
        if cut_type != "speaker_change":
            flags.append("intentional_listener_reaction")
        if "near_window_seam" in flags or len([f for f in flags if f.startswith("short_")]) >= 2:
            priority = "high"
        elif flags:
            priority = "medium"
        else:
            priority = "standard"
        cuts.append({
            "cut_number": index,
            "time_seconds": round(cut_time, 6),
            "timecode": _timecode(cut_time, timeline_fps),
            "from_camera": int(before["camera"]),
            "to_camera": int(after["camera"]),
            "cut_type": cut_type,
            "preceding_shot_seconds": round(before_duration, 6),
            "following_shot_seconds": round(after_duration, 6),
            "nearest_window_seam_seconds": (None if not seams else
                                             round(distance_to_seam, 6)),
            "mapping_status": mapping_status,
            "review_priority": priority,
            "flags": flags,
        })
    return {
        "summary": {
            "cuts": len(cuts),
            "high_priority": sum(cut["review_priority"] == "high" for cut in cuts),
            "medium_priority": sum(cut["review_priority"] == "medium" for cut in cuts),
            "listener_reaction_boundaries": sum(
                cut["cut_type"] != "speaker_change" for cut in cuts),
            "mapping_status": mapping_status,
            "visual_mapping_margin": margin,
        },
        "cuts": cuts,
    }


def write_cut_report(report, json_path, csv_path):
    atomic_write_json(json_path, report)
    fields = ["cut_number", "time_seconds", "timecode", "from_camera", "to_camera",
              "cut_type", "preceding_shot_seconds", "following_shot_seconds",
              "nearest_window_seam_seconds", "mapping_status", "review_priority", "flags",
              "review_decision", "corrected_time_seconds", "corrected_to_camera",
              "reviewer_notes"]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for cut in report["cuts"]:
            row = dict(cut)
            row["flags"] = ";".join(row["flags"])
            row.update({"review_decision": "", "corrected_time_seconds": "",
                        "corrected_to_camera": "", "reviewer_notes": ""})
            writer.writerow(row)
    return json_path, csv_path


def apply_cut_reviews(segments, review_rows, total_duration, minimum_shot=0.5):
    """Apply numbered human decisions while preserving original cut indexing."""
    working = [{"start": float(segment["start"]),
                "end": float(segment["start"] + segment["duration"]),
                "camera": int(segment["camera"])} for segment in segments]
    applied = []
    valid_decisions = {"", "keep", "move", "delete", "camera_wrong"}
    rows = {int(row["cut_number"]): row for row in review_rows}
    for cut_number in range(1, len(working)):
        row = rows.get(cut_number, {})
        decision = row.get("review_decision", "").strip().lower()
        if decision not in valid_decisions:
            raise ValueError(f"Cut {cut_number}: unknown review_decision {decision!r}")
        if decision in ("", "keep"):
            continue
        before, after = working[cut_number - 1], working[cut_number]
        if decision == "move":
            raw_time = row.get("corrected_time_seconds", "").strip()
            if not raw_time:
                raise ValueError(f"Cut {cut_number}: move requires corrected_time_seconds")
            corrected = float(raw_time)
            earliest = before["start"] + minimum_shot
            latest = after["end"] - minimum_shot
            if not earliest <= corrected <= latest:
                raise ValueError(
                    f"Cut {cut_number}: corrected time {corrected} outside "
                    f"safe range {earliest:.3f}-{latest:.3f}")
            before["end"] = corrected
            after["start"] = corrected
        elif decision == "delete":
            after["camera"] = before["camera"]
        elif decision == "camera_wrong":
            raw_camera = row.get("corrected_to_camera", "").strip()
            if raw_camera not in ("1", "2"):
                raise ValueError(f"Cut {cut_number}: camera_wrong requires corrected_to_camera 1 or 2")
            after["camera"] = int(raw_camera)
        optional_camera = row.get("corrected_to_camera", "").strip()
        if decision == "move" and optional_camera:
            if optional_camera not in ("1", "2"):
                raise ValueError(f"Cut {cut_number}: corrected_to_camera must be 1 or 2")
            after["camera"] = int(optional_camera)
        applied.append({"cut_number": cut_number, "decision": decision})

    corrected = []
    for item in working:
        if item["end"] <= item["start"]:
            continue
        if corrected and corrected[-1]["camera"] == item["camera"]:
            corrected[-1]["duration"] = item["end"] - corrected[-1]["start"]
        else:
            corrected.append({"start": item["start"],
                              "duration": item["end"] - item["start"],
                              "camera": item["camera"]})
    cursor = 0.0
    final = []
    for item in corrected:
        final.append({"start": round(cursor, 6), "duration": round(item["duration"], 6),
                      "camera": int(item["camera"])})
        cursor += item["duration"]
    if final:
        final[-1]["duration"] = round(total_duration - final[-1]["start"], 6)
    validation = validate_segments(final, total_duration)
    if not validation["valid"]:
        raise ValueError("Corrected timeline is invalid: " + "; ".join(validation["errors"]))
    return final, {"applied": applied, "result_segments": len(final),
                   "validation": validation}
