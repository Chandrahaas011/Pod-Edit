"""Audit missed speaker changes with continuous audio and fixed-ROI video cues.

This diagnostic reads frames directly from both cameras and never caches frames.
It is intentionally independent of the production decision policy.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os

import cv2
import librosa
import numpy as np


def robust_z(values):
    array = np.asarray(values, dtype=np.float64)
    median = np.nanmedian(array)
    mad = np.nanmedian(np.abs(array - median))
    scale = max(1.4826 * mad, 1e-6)
    return (array - median) / scale, float(median), float(scale)


def calibrate_face(video_path, start, end, step=10.0, target_width=480):
    capture = cv2.VideoCapture(video_path)
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    boxes = []
    timestamp = start
    while timestamp < end:
        capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
        ok, frame = capture.read()
        if ok:
            height, width = frame.shape[:2]
            gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                              (target_width, round(height * target_width / width)))
            faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(48, 48))
            if len(faces):
                boxes.append(max(faces, key=lambda box: box[2] * box[3]))
        timestamp += step
    capture.release()
    if not boxes:
        raise RuntimeError(f"No calibration face found in {video_path}")
    box = np.median(np.asarray(boxes), axis=0).round().astype(int)
    return tuple(int(value) for value in box), len(boxes)


def motion_at(capture, timestamp, face_box, target_width=480, burst_frames=7):
    capture.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000.0)
    frames = []
    for _ in range(burst_frames):
        ok, frame = capture.read()
        if not ok:
            break
        height, width = frame.shape[:2]
        gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                          (target_width, round(height * target_width / width)))
        frames.append(gray)
    if len(frames) < 2:
        return math.nan, math.nan, math.nan
    x, y, width, height = face_box
    frame_height, frame_width = frames[0].shape
    x0, x1 = max(0, x), min(frame_width, x + width)
    mouth_y0, mouth_y1 = max(0, y + round(0.58 * height)), min(frame_height, y + height)
    head_y0, head_y1 = max(0, y + round(0.10 * height)), min(frame_height, y + round(0.40 * height))
    inner_x0, inner_x1 = max(0, x + round(0.18 * width)), min(frame_width, x + round(0.82 * width))

    mouth, head = [], []
    for first, second in zip(frames, frames[1:]):
        mouth_a = first[mouth_y0:mouth_y1, inner_x0:inner_x1].astype(np.float32)
        mouth_b = second[mouth_y0:mouth_y1, inner_x0:inner_x1].astype(np.float32)
        head_a = first[head_y0:head_y1, x0:x1].astype(np.float32)
        head_b = second[head_y0:head_y1, x0:x1].astype(np.float32)
        if not mouth_a.size or not head_a.size:
            return math.nan, math.nan, math.nan
        mouth.append(float(np.mean(np.abs(mouth_b - mouth_a)) / max(np.mean(mouth_a), 1.0)))
        head.append(float(np.mean(np.abs(head_b - head_a)) / max(np.mean(head_a), 1.0)))
    mouth_score = float(np.mean(mouth))
    head_score = float(np.mean(head))
    compensated = max(0.0, mouth_score - 0.70 * head_score)
    return mouth_score, head_score, compensated


def speaker_at(turns, timestamp):
    active = [turn for turn in turns if turn["start"] <= timestamp < turn["end"]]
    return active[-1]["speaker"] if active else "SILENCE"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cam1", required=True)
    parser.add_argument("--cam2", required=True)
    parser.add_argument("--wav1", required=True)
    parser.add_argument("--wav2", required=True)
    parser.add_argument("--turns", required=True)
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=1500.0)
    parser.add_argument("--step", type=float, default=1.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    with open(args.turns, encoding="utf-8") as handle:
        turns = json.load(handle)["turns"]
    audio1, rate = librosa.load(args.wav1, sr=8000, mono=True, duration=args.end)
    audio2, _ = librosa.load(args.wav2, sr=8000, mono=True, duration=args.end)

    # Learn each locked-off camera's subject location from the whole analyzed
    # episode, then keep using that ROI even when a profile pose defeats the
    # frontal-face detector in the interval being audited.
    box1, hits1 = calibrate_face(args.cam1, 0.0, args.end)
    box2, hits2 = calibrate_face(args.cam2, 0.0, args.end)
    print(f"Fixed face boxes: cam1={box1} ({hits1} hits), cam2={box2} ({hits2} hits)")
    captures = [cv2.VideoCapture(args.cam1), cv2.VideoCapture(args.cam2)]
    rows = []
    timestamps = np.arange(args.start, args.end, args.step)
    for index, timestamp in enumerate(timestamps):
        sample_start = round(timestamp * rate)
        sample_end = min(len(audio1), round((timestamp + args.step) * rate))
        rms1 = float(np.sqrt(np.mean(np.square(audio1[sample_start:sample_end])) + 1e-12))
        rms2 = float(np.sqrt(np.mean(np.square(audio2[sample_start:sample_end])) + 1e-12))
        m1, h1, c1 = motion_at(captures[0], float(timestamp), box1)
        # Convert master time to camera-2 tape time with the verified -0.98095-s offset.
        m2, h2, c2 = motion_at(captures[1], float(timestamp + 0.98095238), box2)
        rows.append({"time": float(timestamp), "speaker": speaker_at(turns, float(timestamp)),
                     "rms1": rms1, "rms2": rms2, "log_rms_ratio": math.log((rms1 + 1e-8)/(rms2 + 1e-8)),
                     "mouth1": m1, "head1": h1, "visual1": c1,
                     "mouth2": m2, "head2": h2, "visual2": c2})
        if (index + 1) % 100 == 0:
            print(f"Audited {index + 1}/{len(timestamps)} timestamps")
    for capture in captures:
        capture.release()

    for key in ("log_rms_ratio", "visual1", "visual2"):
        z, median, scale = robust_z([row[key] for row in rows])
        for row, value in zip(rows, z):
            row[key + "_z"] = float(value)
        print(f"{key}: median={median:.6g}, robust_scale={scale:.6g}")
    for row in rows:
        row["visual_dominance"] = row["visual2_z"] - row["visual1_z"]

    csv_path = os.path.join(args.output, "multimodal_seconds.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    grouped = {}
    for label in sorted({row["speaker"] for row in rows}):
        group = [row for row in rows if row["speaker"] == label]
        grouped[label] = {key: float(np.nanmedian([row[key] for row in group]))
                          for key in ("log_rms_ratio_z", "visual1_z", "visual2_z", "visual_dominance")}
        grouped[label]["seconds"] = len(group) * args.step
    summary = {"face_boxes": {"camera1": box1, "camera2": box2},
               "calibration_hits": {"camera1": hits1, "camera2": hits2},
               "group_medians": grouped}
    with open(os.path.join(args.output, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
