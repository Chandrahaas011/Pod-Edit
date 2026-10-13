import time

import cv2
import numpy as np

# Statistical mapping needs many independent samples, not perfect per-frame
# accuracy: even a noisy lip-activity signal that is right 60% of the time
# yields a near-certain majority vote across ~100 sampled seconds.
MAX_SAMPLES_PER_SPEAKER = 90
BURST_FRAMES = 18         # ~0.6-0.7 s captures a complete syllabic motion cycle
TARGET_WIDTH = 480        # face calibration width
ANALYSIS_WIDTH = 960      # mouth edges need more pixels than face localization
EDGE_MARGIN_SEC = 0.3     # avoid turn boundaries where diarization is fuzziest
MIN_PURE_TURN_SEC = 3.0   # long exclusive turns are cleaner cross-modal evidence
MIN_CELL_SAMPLES = 8      # a median from fewer samples than this is noise, not evidence
MIN_MARGIN = 0.15         # minimum absolute Cliff's delta on both cameras


def _calibrate_locked_face(capture, cascade, duration, samples=80):
    """Estimate one stable face box for a locked-off single-person camera."""
    boxes = []
    for timestamp in np.linspace(0.0, max(0.0, duration - 0.5), samples):
        capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp) * 1000.0)
        ok, frame = capture.read()
        if not ok:
            continue
        height, width = frame.shape[:2]
        gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                          (TARGET_WIDTH, round(height * TARGET_WIDTH / width)))
        faces = cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5,
                                         minSize=(48, 48))
        if len(faces):
            boxes.append(max(faces, key=lambda box: box[2] * box[3]))
    if not boxes:
        return None, 0
    fixed = np.median(np.asarray(boxes), axis=0).round().astype(int)
    return tuple(int(value) for value in fixed), len(boxes)


def _sample_lip_activity(capture, cascade, t_seconds):
    """Seeks to t_seconds and measures mouth-region motion across a short
    burst of consecutive frames. Returns (score, status)."""
    capture.set(cv2.CAP_PROP_POS_MSEC, t_seconds * 1000.0)
    frames = []
    for _ in range(BURST_FRAMES):
        ok, frame = capture.read()
        if not ok:
            break
        height, width = frame.shape[:2]
        scale = TARGET_WIDTH / width
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frames.append(cv2.resize(gray, (TARGET_WIDTH, int(height * scale))))
    if len(frames) < 2:
        return None, "read-fail"

    faces = cascade.detectMultiScale(frames[0], scaleFactor=1.15, minNeighbors=5,
                                     minSize=(48, 48))
    if len(faces) == 0:
        return None, "no-face"
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])  # largest face wins

    # Mouth ROI: central 60% width, lower 40% of the face box.
    mx0, mx1 = x + int(w * 0.20), x + int(w * 0.80)
    my0, my1 = y + int(h * 0.60), y + h

    diffs = []
    for a, b in zip(frames, frames[1:]):
        roi_a = a[my0:my1, mx0:mx1].astype(np.float32)
        roi_b = b[my0:my1, mx0:mx1].astype(np.float32)
        if roi_a.size == 0:
            return None, "roi-empty"
        # Normalize by mean brightness so lighting differences between
        # cameras don't bias the comparison.
        diffs.append(float(np.abs(roi_b - roi_a).mean() / max(roi_a.mean(), 1.0) * 100.0))
    return float(np.mean(diffs)), "ok"


def _sample_fixed_lip_activity(capture, face_box, t_seconds):
    """Head-compensated vertical-edge motion in a calibrated mouth ROI."""
    capture.set(cv2.CAP_PROP_POS_MSEC, t_seconds * 1000.0)
    frames = []
    for _ in range(BURST_FRAMES + 2):
        ok, frame = capture.read()
        if not ok:
            break
        height, width = frame.shape[:2]
        gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY),
                          (ANALYSIS_WIDTH, round(height * ANALYSIS_WIDTH / width)))
        frames.append(gray)
    if len(frames) < 2:
        return None, "read-fail"
    scale = ANALYSIS_WIDTH / TARGET_WIDTH
    x, y, w, h = (round(value * scale) for value in face_box)
    mx0, mx1 = x + round(w * 0.18), x + round(w * 0.82)
    my0, my1 = y + round(h * 0.58), y + h
    hx0, hx1 = x, x + w
    hy0, hy1 = y + round(h * 0.10), y + round(h * 0.40)
    mouth_diffs, head_diffs = [], []
    for first, second in zip(frames, frames[1:]):
        mouth_a = first[my0:my1, mx0:mx1].astype(np.float32)
        mouth_b = second[my0:my1, mx0:mx1].astype(np.float32)
        head_a = first[hy0:hy1, hx0:hx1].astype(np.float32)
        head_b = second[hy0:hy1, hx0:hx1].astype(np.float32)
        if not mouth_a.size or not head_a.size:
            return None, "roi-empty"
        # Vertical Sobel edges emphasize lip opening/closing while rejecting
        # much of the shared illumination and compression variation.
        mouth_edge_a = cv2.Sobel(mouth_a, cv2.CV_32F, 0, 1)
        mouth_edge_b = cv2.Sobel(mouth_b, cv2.CV_32F, 0, 1)
        head_edge_a = cv2.Sobel(head_a, cv2.CV_32F, 0, 1)
        head_edge_b = cv2.Sobel(head_b, cv2.CV_32F, 0, 1)
        mouth_diffs.append(float(np.mean(np.abs(mouth_edge_b - mouth_edge_a)) /
                                 max(np.mean(np.abs(mouth_edge_a)), 1.0) * 100.0))
        head_diffs.append(float(np.mean(np.abs(head_edge_b - head_edge_a)) /
                                max(np.mean(np.abs(head_edge_a)), 1.0) * 100.0))
    return max(0.0, float(np.mean(mouth_diffs)) - 0.70 * float(np.mean(head_diffs))), "ok"


def _pick_sample_times(speaker_turns):
    """Spreads sample timestamps across a speaker's turns, skipping the fuzzy
    turn edges, then uniformly subsamples down to MAX_SAMPLES_PER_SPEAKER."""
    # One center sample from each long exclusive turn is more independent and
    # avoids the identity uncertainty concentrated near rapid turn boundaries.
    pure = [(turn["start"] + turn["end"]) / 2.0 for turn in speaker_turns
            if turn["end"] - turn["start"] >= MIN_PURE_TURN_SEC]
    if len(pure) >= MIN_CELL_SAMPLES:
        if len(pure) <= MAX_SAMPLES_PER_SPEAKER:
            return pure
        indices = np.linspace(0, len(pure) - 1, MAX_SAMPLES_PER_SPEAKER).astype(int)
        return [pure[index] for index in indices]
    candidates = []
    for turn in speaker_turns:
        t = turn["start"] + EDGE_MARGIN_SEC
        while t < turn["end"] - EDGE_MARGIN_SEC:
            candidates.append(t)
            t += 1.0
    if len(candidates) <= MAX_SAMPLES_PER_SPEAKER:
        return candidates
    indices = np.linspace(0, len(candidates) - 1, MAX_SAMPLES_PER_SPEAKER).astype(int)
    return [candidates[i] for i in indices]


def _cliffs_delta(first, second):
    """Distribution-free effect: P(first>second) - P(first<second)."""
    left = np.asarray(first, dtype=np.float64)[:, None]
    right = np.asarray(second, dtype=np.float64)[None, :]
    return float((np.sum(left > right) - np.sum(left < right)) /
                 max(1, left.size * right.size))


def resolve_mapping_visual(turns, cam1_path, cam2_path, sync_offset_seconds):
    """Hybrid cross-modal identity check: for each diarized speaker, measures
    which camera shows more lip movement during that speaker's turns.

    Audio (pyannote) decides WHEN someone talks with millisecond precision;
    this module decides WHO is on which camera — no calibration, no frame
    caching, all in-memory.

    Returns (mapping dict {speaker: camera} or None if not confident,
             diagnostics dict).
    """
    print("  ┌─ VISUAL VERIFIER — cross-modal lip-activity vote")
    start_t = time.time()

    speaker_totals = {}
    speaker_turns = {}
    for t in turns:
        speaker_totals[t["speaker"]] = speaker_totals.get(t["speaker"], 0.0) + t["duration"]
        speaker_turns.setdefault(t["speaker"], []).append(t)

    ranked = sorted(speaker_totals, key=speaker_totals.get, reverse=True)
    if len(ranked) < 2:
        print("  └─ fewer than 2 speakers found — visual vote not applicable.")
        return None, {"reason": "fewer-than-2-speakers"}
    top_two = ranked[:2]

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    captures = {1: cv2.VideoCapture(cam1_path), 2: cv2.VideoCapture(cam2_path)}
    if not captures[1].isOpened() or not captures[2].isOpened():
        for cap in captures.values():
            cap.release()
        print("  └─ could not open one of the cameras — skipping visual vote.")
        return None, {"reason": "video-open-failed"}

    duration = max(turn["end"] for turn in turns)
    fixed_boxes = {}
    for cam in (1, 2):
        fixed_boxes[cam], hits = _calibrate_locked_face(
            captures[cam], cascade, duration)
        print(f"  │ camera {cam} fixed ROI       : {fixed_boxes[cam]} ({hits} calibration hits)")

    # activity[speaker][camera] -> list of per-second lip scores
    activity = {spk: {1: [], 2: []} for spk in top_two}
    stats = {cam: {"ok": 0, "no-face": 0, "read-fail": 0, "roi-empty": 0} for cam in (1, 2)}

    for spk in top_two:
        times = _pick_sample_times(speaker_turns[spk])
        print(f"  │ {spk}: sampling {len(times)} seconds across "
              f"{len(speaker_turns[spk])} turns ({speaker_totals[spk]:.0f}s speech)")
        for i, t in enumerate(times):
            row = []
            for cam in (1, 2):
                # Timeline t is cam1-audio time; cam2's tape position honors
                # the sync offset (same formula as the XML builder).
                source_t = t if cam == 1 else t - sync_offset_seconds
                if source_t < 0:
                    row.append(f"cam{cam}: pre-roll")
                    continue
                if fixed_boxes[cam] is not None:
                    score, status = _sample_fixed_lip_activity(
                        captures[cam], fixed_boxes[cam], source_t)
                else:
                    score, status = _sample_lip_activity(captures[cam], cascade, source_t)
                stats[cam][status] += 1
                if score is not None:
                    activity[spk][cam].append(score)
                    row.append(f"cam{cam}: {score:6.2f}")
                else:
                    row.append(f"cam{cam}: {status:>7}")
            print(f"  │   [{spk} {i + 1:3d}/{len(times)}] t={t:8.2f}s  {'  '.join(row)}")

    for cap in captures.values():
        cap.release()

    total_attempts = {cam: sum(stats[cam].values()) for cam in (1, 2)}
    hit_rate = {cam: (stats[cam]["ok"] / total_attempts[cam] if total_attempts[cam] else 0.0)
                for cam in (1, 2)}
    print("  │")
    print(f"  │ face-detection hit rate : cam1 {hit_rate[1] * 100:5.1f}%  "
          f"cam2 {hit_rate[2] * 100:5.1f}%")

    median = {spk: {cam: (float(np.median(activity[spk][cam])) if activity[spk][cam] else 0.0)
                    for cam in (1, 2)}
              for spk in top_two}

    print("  │ lip-activity matrix (median motion while speaker talks):")
    print("  │            │   camera 1 │   camera 2 │ samples c1/c2")
    for spk in top_two:
        print(f"  │ {spk} │ {median[spk][1]:10.3f} │ {median[spk][2]:10.3f} │ "
              f"{len(activity[spk][1])}/{len(activity[spk][2])}")

    # Decision: WITHIN-camera contrast only. Comparing medians across cameras
    # is invalid — the cameras have different framing, lighting, and face
    # detection rates. Instead ask each camera separately: "whose turns make
    # this camera's mouth move more?" A camera only votes if both of its
    # cells have enough samples to mean anything.
    s0, s1 = top_two
    votes = []
    for cam in (1, 2):
        n0, n1 = len(activity[s0][cam]), len(activity[s1][cam])
        if n0 < MIN_CELL_SAMPLES or n1 < MIN_CELL_SAMPLES:
            print(f"  │ camera {cam} vote           : EXCLUDED "
                  f"(cells have {n0}/{n1} samples, need >= {MIN_CELL_SAMPLES})")
            continue
        m0, m1 = median[s0][cam], median[s1][cam]
        if m0 + m1 <= 0:
            print(f"  │ camera {cam} vote           : EXCLUDED (no lip activity measured)")
            continue
        contrast = (m0 - m1) / (m0 + m1)  # +1 -> s0 owns this camera, -1 -> s1
        effect = _cliffs_delta(activity[s0][cam], activity[s1][cam])
        if contrast * effect <= 0:
            print(f"  camera {cam} vote: EXCLUDED "
                  f"(median direction and Cliff's delta disagree)")
            continue
        weight = min(n0, n1)
        owner = s0 if effect > 0 else s1
        votes.append({"camera": cam, "contrast": contrast, "weight": weight,
                      "cliffs_delta": effect, "effect_size": abs(effect),
                      "owner": owner})
        print(f"  │ camera {cam} vote           : contrast {contrast:+.3f} "
              f"Cliff {effect:+.3f} (n={weight}) -> belongs to {owner}")

    # Positive total = hypothesis A (s0->cam1, s1->cam2). A camera-1 vote for
    # s0 and a camera-2 vote for s1 both support A.
    score = sum(v["weight"] * v["cliffs_delta"] *
                (1 if v["camera"] == 1 else -1) for v in votes)
    margin = min((v["effect_size"] for v in votes), default=0.0)
    camera_votes_consistent = (len(votes) == 2 and
                               len({vote["owner"] for vote in votes}) == 2)

    print(f"  │ hypothesis A ({s0}->cam1) : score {score:+.2f}, margin {margin * 100:.1f}%")

    diagnostics = {
        "hit_rate": hit_rate,
        "activity_matrix": median,
        "votes": votes,
        "margin": margin,
        "camera_votes_consistent": camera_votes_consistent,
        "accepted": False,
        "feature": "long-turn-center-vertical-edge-v1",
        "elapsed_seconds": time.time() - start_t,
        "fixed_face_boxes": fixed_boxes,
    }

    if not votes:
        print(f"  └─ NOT CONFIDENT: no camera produced enough samples to vote. "
              f"Falling back to speech-dominance heuristic. [{diagnostics['elapsed_seconds']:.1f}s]")
        return None, diagnostics
    if not camera_votes_consistent:
        print(f"  â””â”€ NOT CONFIDENT: both cameras vote for the same speaker. "
              f"A valid two-close-up mapping requires complementary camera owners. "
              f"Falling back to speech dominance. [{diagnostics['elapsed_seconds']:.1f}s]")
        return None, diagnostics
    if margin < MIN_MARGIN:
        print(f"  └─ NOT CONFIDENT: margin {margin * 100:.1f}% < {MIN_MARGIN * 100:.0f}% "
              f"(cameras disagree). Falling back to speech-dominance heuristic. "
              f"[{diagnostics['elapsed_seconds']:.1f}s]")
        return None, diagnostics

    if score > 0:
        mapping = {s0: 1, s1: 2}
    else:
        mapping = {s0: 2, s1: 1}
    # Any extra (3rd+) speakers inherit the camera of the dominant speaker.
    for spk in ranked[2:]:
        mapping[spk] = mapping[ranked[0]]
    diagnostics["accepted"] = True

    print(f"  └─ CONFIDENT visual mapping: "
          + ", ".join(f"{spk}->cam{cam}" for spk, cam in mapping.items())
          + f" [{diagnostics['elapsed_seconds']:.1f}s]")
    return mapping, diagnostics
