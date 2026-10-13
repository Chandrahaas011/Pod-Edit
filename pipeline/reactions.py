"""Evidence-selected listener cutaways for overlong single-speaker shots."""

from __future__ import annotations

import wave

import cv2
import numpy as np

from pipeline.visual_verifier import (
    TARGET_WIDTH,
    _calibrate_locked_face,
    _sample_fixed_lip_activity,
)


def _fuse_adjacent(segments):
    fused = []
    for segment in segments:
        if segment["duration"] <= 0:
            continue
        if (fused and fused[-1]["camera"] == segment["camera"]
                and abs(fused[-1]["start"] + fused[-1]["duration"] - segment["start"]) < 1e-4):
            fused[-1]["duration"] += segment["duration"]
        else:
            fused.append(dict(segment))
    return fused


def _processing_seams(total_duration, window_seconds, overlap_seconds):
    """Mirror the retained-window seams used by the cut audit."""
    stride = window_seconds - overlap_seconds
    if stride <= 0:
        return []
    seams = []
    seam = window_seconds - overlap_seconds / 2.0
    while seam < total_duration:
        seams.append(seam)
        seam += stride
    return seams


def _nearest_seam_distance(timeline_time, seams):
    return min((abs(timeline_time - seam) for seam in seams), default=float("inf"))


def _ordinal_ranks(values):
    """Return deterministic 0..1 ranks while preserving exact ties."""
    unique = sorted(set(values))
    if len(unique) <= 1:
        return [0.0 for _ in values]
    positions = {value: index / (len(unique) - 1) for index, value in enumerate(unique)}
    return [positions[value] for value in values]


def _select_reaction_candidate(candidates, desired, search_radius, seams,
                               seam_guard_seconds=1.0):
    """Rank safe listener moments by motion, audio pause, then proximity.

    A candidate outside processing-seam guards is always preferred when one is
    available. Within that safe set, ordinal ranks prevent camera-specific
    motion and audio scales from dominating each other. Lower is better.
    """
    if not candidates:
        return None
    prepared = []
    for candidate in candidates:
        item = dict(candidate)
        item["nearest_window_seam_seconds"] = _nearest_seam_distance(
            float(item["time"]), seams)
        prepared.append(item)
    safe = [item for item in prepared
            if item["nearest_window_seam_seconds"] >= seam_guard_seconds]
    pool = safe or prepared
    motion_ranks = _ordinal_ranks([float(item["motion"]) for item in pool])
    finite_audio = [float(item["audio_rms"]) for item in pool
                    if item.get("audio_rms") is not None]
    missing_audio = max(finite_audio, default=0.0)
    audio_values = [float(item["audio_rms"]) if item.get("audio_rms") is not None
                    else missing_audio for item in pool]
    audio_ranks = _ordinal_ranks(audio_values)
    radius = max(float(search_radius), 1e-6)
    for item, motion_rank, audio_rank in zip(pool, motion_ranks, audio_ranks):
        proximity = min(1.0, abs(float(item["time"]) - desired) / radius)
        item["selection_score"] = (
            0.60 * motion_rank + 0.30 * audio_rank + 0.10 * proximity)
    return min(pool, key=lambda item: (item["selection_score"],
                                       abs(float(item["time"]) - desired),
                                       float(item["time"])))


def _pcm_rms_at(reader, timeline_time, window_seconds=0.25):
    """Read a small PCM window without loading or caching the full WAV."""
    if reader is None or reader.getsampwidth() != 2:
        return None
    frame_rate = reader.getframerate()
    channels = reader.getnchannels()
    frame_count = max(1, round(window_seconds * frame_rate))
    first_frame = max(0, round((timeline_time - window_seconds / 2.0) * frame_rate))
    try:
        reader.setpos(min(first_frame, reader.getnframes()))
        raw = reader.readframes(frame_count)
    except (EOFError, wave.Error):
        return None
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64)
    if samples.size < channels:
        return None
    if channels > 1:
        samples = samples[:samples.size - samples.size % channels]
        samples = samples.reshape(-1, channels).mean(axis=1)
    return float(np.sqrt(np.mean(np.square(samples))) / 32768.0)


def add_reaction_cutaways(segments, cam1_path, cam2_path, sync_offset_seconds,
                          total_duration, max_primary_shot=60.0,
                          reaction_duration=4.0, search_radius=6.0,
                          sample_step=2.0, master_audio_path=None,
                          diarization_window=60.0, diarization_overlap=15.0,
                          seam_guard_seconds=1.0):
    """Break only overlong shots with a short view of the listening camera.

    Candidate moments are compared within the *same* target camera. The moment
    with the lowest compensated lip activity is preferred, reducing the chance
    of showing a listener whose visible mouth contradicts the master audio.
    Frames are sought directly from the source files and are never cached.
    """
    if max_primary_shot <= reaction_duration * 2:
        raise ValueError("max_primary_shot must be much longer than reaction_duration")
    captures = {1: cv2.VideoCapture(cam1_path), 2: cv2.VideoCapture(cam2_path)}
    if not all(capture.isOpened() for capture in captures.values()):
        for capture in captures.values():
            capture.release()
        return segments, {"enabled": False, "reason": "video-open-failed", "inserted": 0}
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    boxes = {}
    for camera in (1, 2):
        boxes[camera], _ = _calibrate_locked_face(
            captures[camera], cascade, total_duration, samples=60)
    if any(box is None for box in boxes.values()):
        for capture in captures.values():
            capture.release()
        return segments, {"enabled": False, "reason": "face-calibration-failed", "inserted": 0}

    seams = _processing_seams(
        total_duration, diarization_window, diarization_overlap)
    audio_reader = None
    if master_audio_path:
        try:
            audio_reader = wave.open(master_audio_path, "rb")
        except (OSError, wave.Error):
            audio_reader = None

    output, selections = [], []
    for segment_index, segment in enumerate(segments):
        segment_start = float(segment["start"])
        segment_end = segment_start + float(segment["duration"])
        primary_camera = int(segment["camera"])
        listener_camera = 2 if primary_camera == 1 else 1
        cursor = segment_start
        while segment_end - cursor > max_primary_shot:
            desired = cursor + max_primary_shot
            earliest = cursor + max_primary_shot - search_radius
            latest = min(segment_end - reaction_duration - 8.0,
                         cursor + max_primary_shot + search_radius)
            if latest <= earliest:
                break
            candidates = np.arange(earliest, latest + 0.001, sample_step)
            candidates_with_evidence = []
            for timeline_time in candidates:
                source_time = (timeline_time if listener_camera == 1
                               else timeline_time - sync_offset_seconds)
                score, status = _sample_fixed_lip_activity(
                    captures[listener_camera], boxes[listener_camera], source_time)
                if status == "ok" and score is not None:
                    candidates_with_evidence.append({
                        "motion": float(score),
                        "audio_rms": _pcm_rms_at(audio_reader, float(timeline_time)),
                        "time": float(timeline_time),
                    })
            selected = _select_reaction_candidate(
                candidates_with_evidence, desired, search_radius, seams,
                seam_guard_seconds=seam_guard_seconds)
            if selected is None:
                break
            motion = selected["motion"]
            reaction_start = selected["time"]
            if reaction_start <= cursor or reaction_start + reaction_duration >= segment_end:
                break
            output.append({"start": cursor, "duration": reaction_start - cursor,
                           "camera": primary_camera})
            output.append({"start": reaction_start, "duration": reaction_duration,
                           "camera": listener_camera})
            selections.append({"source_segment": segment_index,
                               "start": reaction_start,
                               "duration": reaction_duration,
                               "camera": listener_camera,
                               "listener_lip_activity": motion,
                               "master_audio_rms": selected.get("audio_rms"),
                               "selection_score": selected["selection_score"],
                               "nearest_window_seam_seconds":
                                   selected["nearest_window_seam_seconds"]})
            cursor = reaction_start + reaction_duration
        output.append({"start": cursor, "duration": segment_end - cursor,
                       "camera": primary_camera})
    for capture in captures.values():
        capture.release()
    if audio_reader is not None:
        audio_reader.close()

    output = _fuse_adjacent(output)
    # Re-round against one continuous cursor to prevent tiny validation gaps.
    cursor = 0.0
    final = []
    for segment in output:
        duration = float(segment["duration"])
        final.append({"start": round(cursor, 6), "duration": round(duration, 6),
                      "camera": int(segment["camera"])})
        cursor += duration
    if final:
        final[-1]["duration"] = round(total_duration - final[-1]["start"], 6)
    diagnostics = {"enabled": True, "inserted": len(selections),
                   "max_primary_shot": max_primary_shot,
                   "reaction_duration": reaction_duration,
                   "selection_policy": "seam-safe-motion60-audio30-proximity10-v1",
                   "seam_guard_seconds": seam_guard_seconds,
                   "fixed_face_boxes": boxes, "selections": selections}
    return final, diagnostics
