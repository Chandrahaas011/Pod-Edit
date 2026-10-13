def merge_short_segments(segments: list, min_duration_sec: float) -> list:
    """Anti-flicker pass: any camera segment shorter than min_duration_sec is
    absorbed into the preceding segment, and adjacent same-camera segments
    are fused. Cuts should feel editorial, not twitchy."""
    if not segments:
        return []

    merged = [dict(segments[0])]
    absorbed = 0
    for segment in segments[1:]:
        candidate = dict(segment)
        if merged[-1]["camera"] == candidate["camera"]:
            merged[-1]["duration"] += candidate["duration"]
            continue
        if candidate["duration"] < min_duration_sec:
            merged[-1]["duration"] += candidate["duration"]
            absorbed += 1
            continue
        merged.append(candidate)

    # Absorption can make neighbours share a camera — fuse them.
    fused = [merged[0]]
    for segment in merged[1:]:
        if fused[-1]["camera"] == segment["camera"]:
            fused[-1]["duration"] += segment["duration"]
        else:
            fused.append(segment)

    print(f"  │ anti-flicker    : absorbed {absorbed} blips shorter than {min_duration_sec}s")
    return fused


def build_segments(turns: list, speaker_to_camera: dict, total_duration: float,
                   min_duration_sec: float = 1.5) -> list:
    """Converts diarized speaker turns into a continuous list of camera
    segments covering [0, total_duration].

    Uses an event-based active-speaker stack so overlapping speech is handled
    correctly: a 0.5s interjection pushes its speaker on top of the stack and
    pops off cleanly when it ends, falling back to whoever was already
    talking — the camera never gets 'stuck' after an interruption.
    """
    print("  ┌─ SEGMENT ASSEMBLY — active-speaker stack")

    if not turns:
        print("  └─ WARNING: no turns — defaulting to Camera 1 for the whole timeline.")
        return [{"start": 0.0, "duration": total_duration, "camera": 1}]

    events = []
    for turn in turns:
        cam = speaker_to_camera.get(turn["speaker"], 1)
        events.append({"time": turn["start"], "type": "start", "camera": cam})
        events.append({"time": turn["end"], "type": "end", "camera": cam})
    # Chronological; on ties process 'end' before 'start'.
    events.sort(key=lambda e: (e["time"], 0 if e["type"] == "end" else 1))
    print(f"  │ events          : {len(events)} (from {len(turns)} turns)")

    raw_segments = []
    active_stack = []
    current_camera = 1
    last_switch_time = 0.0
    switches = 0

    for event in events:
        t = event["time"]
        cam = event["camera"]
        if t > total_duration:
            break

        if event["type"] == "start":
            if cam in active_stack:
                active_stack.remove(cam)
            active_stack.append(cam)  # most recent speaker on top
        else:
            if cam in active_stack:
                active_stack.remove(cam)

        desired = active_stack[-1] if active_stack else current_camera  # hold during silence

        if desired != current_camera:
            duration = t - last_switch_time
            if duration > 0:
                raw_segments.append({"start": last_switch_time, "duration": duration,
                                     "camera": current_camera})
            switches += 1
            print(f"  │ switch #{switches:3d}     : {t:8.2f}s  cam{current_camera} -> cam{desired}  "
                  f"(held {duration:6.2f}s, stack={active_stack})")
            current_camera = desired
            last_switch_time = t

    if last_switch_time < total_duration:
        raw_segments.append({"start": last_switch_time,
                             "duration": total_duration - last_switch_time,
                             "camera": current_camera})

    print(f"  │ raw segments    : {len(raw_segments)} (overlap-aware)")

    merged = merge_short_segments(raw_segments, min_duration_sec)

    # Rebuild starts so the timeline is exactly continuous from 0.
    final_segments = []
    cursor = 0.0
    for seg in merged:
        final_segments.append({"start": round(cursor, 4),
                               "duration": round(seg["duration"], 4),
                               "camera": seg["camera"]})
        cursor += seg["duration"]

    cam_time = {1: 0.0, 2: 0.0}
    for seg in final_segments:
        cam_time[seg["camera"]] = cam_time.get(seg["camera"], 0.0) + seg["duration"]
    durations = [seg["duration"] for seg in final_segments]

    print(f"  │ final segments  : {len(final_segments)}")
    print(f"  │ screen time     : cam1 {cam_time[1]:7.1f}s ({cam_time[1] / total_duration * 100:5.1f}%)  "
          f"cam2 {cam_time[2]:7.1f}s ({cam_time[2] / total_duration * 100:5.1f}%)")
    print(f"  │ segment length  : min {min(durations):.1f}s / avg {sum(durations) / len(durations):.1f}s / "
          f"max {max(durations):.1f}s")
    print(f"  │ cut rate        : {(len(final_segments) - 1) / (total_duration / 60):.1f} cuts/min")
    print("  └─ timeline assembled")

    return final_segments
