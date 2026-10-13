import os
import subprocess
import time
from pathlib import Path
import tempfile
import math


def _pick_window(segments, window_seconds):
    """Picks the preview window: centered on the first substantial camera-2
    segment so the render exercises BOTH cameras' sync math and at least two
    cuts. Falls back to the timeline start."""
    for seg in segments:
        if seg["camera"] == 2 and seg["duration"] >= 3.0:
            start = max(0.0, seg["start"] - window_seconds / 3)
            return start
    return 0.0


def render_preview(segments, cam1_path, cam2_path, audio_path, sync_offset_seconds,
                   output_path, window_start=None, window_seconds=60.0):
    """Renders a short MP4 of the actual edit using ffmpeg — same segment
    list, same sync math as the XML, but zero dependence on how an NLE
    interprets the XML.

    If this preview has correct lip-sync and sensible cuts, the edit decisions
    and sync offset are right; any remaining problem in DaVinci Resolve is an
    XML-interpretation issue. This is the isolation test the project lacked.
    """
    print("  ┌─ PREVIEW RENDER — ffmpeg ground-truth check")

    if window_start is None:
        window_start = _pick_window(segments, window_seconds)
    window_end = window_start + window_seconds
    print(f"  │ window          : {window_start:.1f}s -> {window_end:.1f}s on the edited timeline")

    # Clamp segments to the preview window.
    parts = []
    for seg in segments:
        seg_end = seg["start"] + seg["duration"]
        if seg_end <= window_start or seg["start"] >= window_end:
            continue
        clip_start = max(seg["start"], window_start)
        clip_end = min(seg_end, window_end)
        parts.append({"timeline_start": clip_start,
                      "duration": clip_end - clip_start,
                      "camera": seg["camera"]})
    if not parts:
        print("  └─ nothing to render in this window — skipping preview.")
        return None

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    filters = []
    for i, part in enumerate(parts):
        if part["camera"] == 1:
            source_seconds = part["timeline_start"]
            src = cam1_path
        else:
            source_seconds = max(0.0, part["timeline_start"] - sync_offset_seconds)
            src = cam2_path
        cmd += ["-ss", f"{source_seconds:.3f}", "-t", f"{part['duration']:.3f}", "-i", src]
        # Normalize every part to a common format so concat is legal.
        filters.append(f"[{i}:v]fps=30,scale=854:480,setsar=1,format=yuv420p[v{i}]")
        print(f"  │ part {i:2d}         : cam{part['camera']}  timeline {part['timeline_start']:8.2f}s  "
              f"source {source_seconds:8.2f}s  dur {part['duration']:6.2f}s")

    # Master audio: continuous camera-1 audio for the window.
    audio_index = len(parts)
    cmd += ["-ss", f"{window_start:.3f}", "-t", f"{window_seconds:.3f}", "-i", audio_path]

    concat_inputs = "".join(f"[v{i}]" for i in range(len(parts)))
    filters.append(f"{concat_inputs}concat=n={len(parts)}:v=1:a=0[vout]")
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", f"{audio_index}:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "128k",
        "-shortest",
        output_path,
    ]

    print(f"  │ rendering       : {len(parts)} parts -> {output_path}")
    start_t = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  └─ FFMPEG ERROR:\n{result.stderr}")
        return None

    size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"  └─ preview ready in {time.time() - start_t:.1f}s ({size_mb:.1f} MB) — "
          "check lip-sync on both cameras and that cuts land on speaker changes.")
    return output_path


def render_switch_review(segments, cam1_path, cam2_path, audio_path,
                         sync_offset_seconds, output_path, radius_seconds=3.0,
                         max_cuts=None, cut_numbers=None, batch_size=8):
    """Render all selected cuts in bounded batches; publish only a complete reel.

    Sampling is opt-in through max_cuts. Temporary media stays beside the output
    and is removed on success or failure; an existing review survives failure.
    """
    if not math.isfinite(radius_seconds) or radius_seconds <= 0:
        raise ValueError("radius_seconds must be finite and positive")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size < 1:
        raise ValueError("batch_size must be a positive integer")
    if max_cuts is not None and (isinstance(max_cuts, bool)
                                or not isinstance(max_cuts, int) or max_cuts < 1):
        raise ValueError("max_cuts must be a positive integer or None")
    numbers = list(range(1, len(segments)))
    if cut_numbers is not None:
        selected = {int(number) for number in cut_numbers}
        invalid = selected - set(numbers)
        if invalid:
            raise ValueError(f"Unknown cut numbers: {sorted(invalid)}")
        numbers = [number for number in numbers if number in selected]
    if max_cuts is not None and len(numbers) > max_cuts:
        print(f"  Sampled review explicitly requested: {max_cuts} of {len(numbers)} cuts")
        numbers = ([numbers[0]] if max_cuts == 1 else
                   [numbers[round(index * (len(numbers) - 1) / (max_cuts - 1))]
                    for index in range(max_cuts)])
    if not numbers:
        return None
    destination = Path(output_path).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Source paths must stay valid when the assembly subprocess changes cwd.
    sources = [str(Path(path).resolve()) for path in (cam1_path, cam2_path, audio_path)]
    with tempfile.TemporaryDirectory(prefix=".podedit-review-", dir=destination.parent) as temporary:
        root = Path(temporary)
        batches = []
        for offset in range(0, len(numbers), batch_size):
            path = root / f"batch-{len(batches):05d}.mov"
            result = _render_switch_review_batch(
                segments, *sources, sync_offset_seconds, str(path),
                radius_seconds, numbers[offset:offset + batch_size])
            if result is None:
                return None
            batches.append(path)
        assembled = root / "complete.mp4"
        listing = root / "concat.txt"
        listing.write_text("".join(f"file '{path.name}'\n" for path in batches), encoding="utf-8")
        result = subprocess.run([
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-f", "concat", "-safe", "1", "-i", str(listing),
            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart", str(assembled)],
            cwd=root, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  FFMPEG review assembly error:\n{result.stderr}")
            return None
        os.replace(assembled, destination)
    print(f"  Review complete: {len(numbers)} of {len(segments) - 1} cuts -> {destination}")
    return output_path


def _render_switch_review_batch(segments, cam1_path, cam2_path, audio_path,
                                sync_offset_seconds, output_path, radius_seconds,
                                cut_numbers):
    """Render one bounded group, retaining original cut numbering."""
    cut_records = [
        {"number": index, "time": segment["start"],
         "from_camera": segments[index - 1]["camera"], "to_camera": segment["camera"]}
        for index, segment in enumerate(segments[1:], start=1)
    ]
    if cut_numbers is not None:
        selected = {int(number) for number in cut_numbers}
        cut_records = [cut for cut in cut_records if cut["number"] in selected]
    if not cut_records:
        return None
    timeline_end = max(segment["start"] + segment["duration"] for segment in segments)
    windows = [(max(0.0, cut["time"] - radius_seconds),
                min(timeline_end, cut["time"] + radius_seconds)) for cut in cut_records]
    parts = []
    for window_index, (window_start, window_end) in enumerate(windows):
        for segment in segments:
            seg_end = segment["start"] + segment["duration"]
            if seg_end <= window_start or segment["start"] >= window_end:
                continue
            start = max(segment["start"], window_start)
            end = min(seg_end, window_end)
            parts.append({"window": window_index, "timeline_start": start,
                          "duration": end - start, "camera": segment["camera"]})

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    filters = []
    elapsed = 0.0
    for index, part in enumerate(parts):
        frames = round((elapsed + part["duration"]) * 30) - round(elapsed * 30)
        elapsed += part["duration"]
        source_start = (part["timeline_start"] if part["camera"] == 1
                        else max(0.0, part["timeline_start"] - sync_offset_seconds))
        source = cam1_path if part["camera"] == 1 else cam2_path
        cmd += ["-ss", f"{source_start:.3f}", "-t", f"{part['duration']:.3f}", "-i", source]
        cut = cut_records[part["window"]]
        label = (f"CUT {cut['number']:02d} of {len(segments) - 1:02d}   "
                 f"T {cut['time']:.3f}s   C{cut['from_camera']} to C{cut['to_camera']}")
        filters.append(
            f"[{index}:v]fps=30,scale=854:480,setsar=1,format=yuv420p,"
            f"tpad=stop_mode=clone:stop_duration=1,trim=end_frame={frames},setpts=N/(30*TB),"
            f"drawtext=text='{label}':fontcolor=white:fontsize=22:box=1:"
            f"boxcolor=black@0.68:boxborderw=8:x=18:y=18[v{index}]")
    audio_index = len(parts)
    cmd += ["-i", audio_path]
    for index, (start, end) in enumerate(windows):
        filters.append(f"[{audio_index}:a]atrim=start={start:.3f}:end={end:.3f},"
                       f"asetpts=PTS-STARTPTS[a{index}]")
    video_inputs = "".join(f"[v{index}]" for index in range(len(parts)))
    audio_inputs = "".join(f"[a{index}]" for index in range(len(windows)))
    filters.append(f"{video_inputs}concat=n={len(parts)}:v=1:a=0[vout]")
    filters.append(f"{audio_inputs}concat=n={len(windows)}:v=0:a=1[aout]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-c:a", "pcm_s16le", "-shortest", output_path]
    print(f"  Rendering switch reel: {len(cut_records)} numbered cuts, {len(parts)} video pieces")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  FFMPEG switch-reel error:\n{result.stderr}")
        return None
    print(f"  Switch review ready: {output_path}")
    return output_path
