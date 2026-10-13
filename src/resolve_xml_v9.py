"""
PodEdit 1.5 Resolve XML generator.

This builder is parameterized for arbitrary camera paths and detects each
source FPS independently so Camera 1 and Camera 2 can come from different
recording frame rates.
"""

from __future__ import annotations

import json
import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

import cv2
import librosa


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _rate(parent, fps):
    rate = SubElement(parent, "rate")
    SubElement(rate, "timebase").text = str(int(round(fps)))
    SubElement(rate, "ntsc").text = "FALSE"
    return rate


def _probe_video(path):
    capture = cv2.VideoCapture(path)
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    capture.release()
    duration_seconds = frame_count / fps if fps else 0.0
    return {"fps": float(fps), "frames": int(frame_count), "duration_seconds": float(duration_seconds)}


def _audio_duration_frames(path, timeline_fps):
    if not os.path.exists(path):
        return 0

    try:
        audio, sr = librosa.load(path, sr=None, mono=True)
        return int(round((len(audio) / float(sr)) * timeline_fps))
    except Exception:
        return 0


def _file_element(parent, file_id, name, pathurl, duration_frames, fps, with_video=True):
    file_elem = SubElement(parent, "file", id=file_id)
    SubElement(file_elem, "name").text = name
    SubElement(file_elem, "pathurl").text = pathurl
    _rate(file_elem, fps)
    SubElement(file_elem, "duration").text = str(int(duration_frames))

    media = SubElement(file_elem, "media")
    if with_video:
        video = SubElement(media, "video")
        sc = SubElement(video, "samplecharacteristics")
        _rate(sc, fps)
        SubElement(sc, "width").text = "1920"
        SubElement(sc, "height").text = "1080"
        SubElement(sc, "anamorphic").text = "FALSE"
        SubElement(sc, "pixelaspectratio").text = "square"
        SubElement(sc, "fielddominance").text = "none"
    else:
        audio = SubElement(media, "audio")
        sc = SubElement(audio, "samplecharacteristics")
        SubElement(sc, "depth").text = "16"
        SubElement(sc, "samplerate").text = "48000"
        SubElement(audio, "channelcount").text = "2"
    return file_elem


def _clip(parent, clip_id, name, file_ref, start, end, source_in, source_out, fps):
    clip = SubElement(parent, "clipitem", id=clip_id)
    SubElement(clip, "name").text = name
    SubElement(clip, "enabled").text = "TRUE"
    SubElement(clip, "duration").text = str(int(end - start))
    _rate(clip, fps)
    SubElement(clip, "start").text = str(int(start))
    SubElement(clip, "end").text = str(int(end))
    SubElement(clip, "in").text = str(int(source_in))
    SubElement(clip, "out").text = str(int(source_out))
    SubElement(clip, "file", id=file_ref)
    return clip


def generate_resolve_xml(
    edit_segments,
    cam1_path,
    cam2_path,
    audio_path,
    sync_offset_seconds,
    results_dir,
    output_path,
    timeline_fps=30,
):
    os.makedirs(results_dir, exist_ok=True)

    cam1_meta = _probe_video(cam1_path)
    cam2_meta = _probe_video(cam2_path)
    cam1_url = os.path.abspath(cam1_path).replace("\\", "/")
    cam2_url = os.path.abspath(cam2_path).replace("\\", "/")
    audio_url = os.path.abspath(audio_path).replace("\\", "/")

    total_duration_frames = sum(int(round(seg["duration"] * timeline_fps)) for seg in edit_segments)
    cam1_duration_frames = cam1_meta["frames"]
    cam2_duration_frames = cam2_meta["frames"]
    audio_duration_frames = _audio_duration_frames(audio_path, timeline_fps)
    if audio_duration_frames <= 0:
        audio_duration_frames = total_duration_frames

    print("=" * 60)
    print("DaVinci Resolve XML Generator")
    print("=" * 60)
    print(f"Loaded {len(edit_segments)} edit segments")
    print(f"Timeline FPS: {timeline_fps}")
    print(f"Camera 1 FPS: {cam1_meta['fps']:.3f}")
    print(f"Camera 2 FPS: {cam2_meta['fps']:.3f}")
    print(f"Sync offset: {sync_offset_seconds:.4f}s")
    print(f"Timeline duration: {total_duration_frames / timeline_fps:.2f}s")

    xmeml = Element("xmeml", version="5")
    project = SubElement(xmeml, "project")
    SubElement(project, "name").text = "PodEdit 1.5"
    SubElement(project, "children")

    sequence = SubElement(xmeml, "sequence", id="sequence-1")
    SubElement(sequence, "name").text = "PodEdit 1.5 Multi-Cam"
    SubElement(sequence, "duration").text = str(total_duration_frames)
    _rate(sequence, timeline_fps)
    timecode = SubElement(sequence, "timecode")
    _rate(timecode, timeline_fps)
    SubElement(timecode, "string").text = "00:00:00:00"
    SubElement(timecode, "frame").text = "0"
    SubElement(timecode, "displayformat").text = "NDF"

    media = SubElement(sequence, "media")
    video = SubElement(media, "video")
    format_elem = SubElement(video, "format")
    sc = SubElement(format_elem, "samplecharacteristics")
    _rate(sc, timeline_fps)
    SubElement(sc, "width").text = "1920"
    SubElement(sc, "height").text = "1080"
    SubElement(sc, "anamorphic").text = "FALSE"
    SubElement(sc, "pixelaspectratio").text = "square"
    SubElement(sc, "fielddominance").text = "none"

    track1 = SubElement(video, "track")
    track2 = SubElement(video, "track")
    audio_parent = SubElement(media, "audio")
    audio_format = SubElement(audio_parent, "format")
    audio_sc = SubElement(audio_format, "samplecharacteristics")
    SubElement(audio_sc, "depth").text = "16"
    SubElement(audio_sc, "samplerate").text = "48000"
    audio_track = SubElement(audio_parent, "track")

    cam1_count = 0
    cam2_count = 0
    audio_count = 0
    timeline_pos = 0
    cam1_added = False
    cam2_added = False
    audio_added = False

    for index, segment in enumerate(edit_segments):
        segment_duration_frames = int(round(segment["duration"] * timeline_fps))
        timeline_start = timeline_pos
        timeline_end = timeline_start + segment_duration_frames

        if segment["camera"] == 1:
            source_in = int(round(segment["start"] * cam1_meta["fps"]))
            source_out = min(cam1_meta["frames"], source_in + int(round(segment["duration"] * cam1_meta["fps"])))
            _clip(
                track1,
                f"clip-cam1-{cam1_count}",
                os.path.basename(cam1_path),
                "file-1",
                timeline_start,
                timeline_end,
                source_in,
                source_out,
                cam1_meta["fps"],
            )
            cam1_count += 1
            if not cam1_added:
                _file_element(xmeml, "file-1", os.path.basename(cam1_path), cam1_url, cam1_duration_frames, cam1_meta["fps"], True)
                cam1_added = True

        if segment["camera"] == 2:
            source_seconds = max(0.0, segment["start"] - sync_offset_seconds)
            source_in = int(round(source_seconds * cam2_meta["fps"]))
            source_out = min(cam2_meta["frames"], source_in + int(round(segment["duration"] * cam2_meta["fps"])))
            _clip(
                track2,
                f"clip-cam2-{cam2_count}",
                os.path.basename(cam2_path),
                "file-2",
                timeline_start,
                timeline_end,
                source_in,
                source_out,
                cam2_meta["fps"],
            )
            cam2_count += 1
            if not cam2_added:
                _file_element(xmeml, "file-2", os.path.basename(cam2_path), cam2_url, cam2_duration_frames, cam2_meta["fps"], True)
                cam2_added = True

        audio_in = int(round(segment["start"] * timeline_fps))
        audio_out = audio_in + segment_duration_frames
        audio_clip = SubElement(audio_track, "clipitem", id=f"audio-{audio_count}")
        SubElement(audio_clip, "name").text = os.path.basename(audio_path)
        SubElement(audio_clip, "enabled").text = "TRUE"
        SubElement(audio_clip, "duration").text = str(audio_duration_frames)
        _rate(audio_clip, timeline_fps)
        SubElement(audio_clip, "start").text = str(timeline_start)
        SubElement(audio_clip, "end").text = str(timeline_end)
        SubElement(audio_clip, "in").text = str(audio_in)
        SubElement(audio_clip, "out").text = str(audio_out)
        SubElement(audio_clip, "file", id="file-3")
        audio_count += 1
        if not audio_added:
            _file_element(xmeml, "file-3", os.path.basename(audio_path), audio_url, audio_duration_frames, timeline_fps, False)
            audio_added = True

        timeline_pos = timeline_end

    xml_str = minidom.parseString(tostring(xmeml)).toprettyxml(indent="  ")
    final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    final_xml += '<!DOCTYPE xmeml>\n'
    final_xml += "\n".join(xml_str.split("\n")[1:])

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print("\n" + "=" * 60)
    print("✅ DaVinci Resolve XML Generated Successfully!")
    print("=" * 60)
    print(f"File: {output_path}")
    print(f"Track 1 clips: {cam1_count}")
    print(f"Track 2 clips: {cam2_count}")
    print(f"Audio clips: {audio_count}")
    print(f"Total duration: {total_duration_frames / timeline_fps:.2f}s")
    print(f"Frame rate: {timeline_fps} fps")

    return output_path


if __name__ == "__main__":
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    segments = _load_json(os.path.join(project_dir, "results", "edit_segments.json"))
    sync_metrics_path = os.path.join(project_dir, "results", "sync_metrics.json")
    sync_offset = 0.0
    if os.path.exists(sync_metrics_path):
        try:
            sync_offset = float(_load_json(sync_metrics_path).get("estimated_offset_seconds", 0.0))
        except Exception:
            sync_offset = 0.0

    generate_resolve_xml(
        edit_segments=segments,
        cam1_path=os.path.join(project_dir, "datasets", "test_set_1", "camera1_short.mp4"),
        cam2_path=os.path.join(project_dir, "datasets", "test_set_1", "camera2_short.mp4"),
        audio_path=os.path.join(project_dir, "results", "camera1_audio.wav"),
        sync_offset_seconds=sync_offset,
        results_dir=os.path.join(project_dir, "results"),
        output_path=os.path.join(project_dir, "results", "davinci_resolve_timeline.xml"),
        timeline_fps=30,
    )
