import os
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from pipeline.probe import probe_video


def _rate(parent, fps):
    rate = SubElement(parent, "rate")
    SubElement(rate, "timebase").text = str(int(round(fps)))
    SubElement(rate, "ntsc").text = "FALSE"
    return rate


def _pathurl(path):
    return "file://localhost/" + os.path.abspath(path).replace("\\", "/")


def _file_element(parent, file_id, name, pathurl, duration_frames, fps, with_video=True,
                  audio_sample_rate=48000, element=None):
    file_elem = element if element is not None else SubElement(parent, "file", id=file_id)
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
        SubElement(sc, "samplerate").text = str(int(audio_sample_rate))
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


def generate_resolve_xml(segments, cam1_path, cam2_path, audio_path,
                         sync_offset_seconds, output_path, timeline_fps=30.0):
    """Builds a DaVinci Resolve-compatible FCP XML 7 timeline.

    Frame-math conventions (verified against Resolve's importer):
    - clipitem <in>/<out> are expressed in TIMELINE-fps frames for every clip,
      regardless of the source's native rate. Resolve conforms the source to
      the timeline internally. Using native fps here causes proportional
      drift (25fps source on a 30fps timeline drifts 20%).
    - <file> <rate> carries each source's true native fps so Resolve knows
      what it is conforming from.
    - Sync: camera 2's tape position at timeline second T is (T - offset).
      With the sync engine's convention a NEGATIVE offset (cam2 started
      early) yields T + |offset| — later footage — which is correct.
    """
    print("  ┌─ FCP XML 7 BUILDER")
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    cam1_meta = probe_video(cam1_path)
    cam2_meta = probe_video(cam2_path)

    total_duration_frames = sum(int(round(seg["duration"] * timeline_fps)) for seg in segments)
    # <file> durations are given in timeline-fps units (what Resolve uses to
    # bound the source in timeline-time).
    cam1_duration_frames = int(round(cam1_meta["duration_seconds"] * timeline_fps))
    cam2_duration_frames = int(round(cam2_meta["duration_seconds"] * timeline_fps))
    audio_duration_frames = total_duration_frames

    print(f"  │ timeline fps    : {timeline_fps}")
    print(f"  │ camera 1        : {cam1_meta['fps']:.3f} fps, {cam1_meta['frames']} frames, "
          f"{cam1_meta['duration_seconds']:.1f}s")
    print(f"  │ camera 2        : {cam2_meta['fps']:.3f} fps, {cam2_meta['frames']} frames, "
          f"{cam2_meta['duration_seconds']:.1f}s")
    print(f"  │ sync offset     : {sync_offset_seconds:+.4f}s "
          f"(cam2 source = T {'+' if sync_offset_seconds < 0 else '-'} {abs(sync_offset_seconds):.4f}s)")
    print(f"  │ timeline frames : {total_duration_frames}")

    xmeml = Element("xmeml", version="5")
    project = SubElement(xmeml, "project")
    SubElement(project, "name").text = "PodEdit"
    SubElement(project, "children")

    sequence = SubElement(xmeml, "sequence", id="sequence-1")
    SubElement(sequence, "name").text = "PodEdit Auto Edit"
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

    cam1_count = cam2_count = audio_count = 0
    timeline_pos = 0
    files_added = set()

    print("  │")
    print("  │  # │  start │    dur │ cam │  source in │ source out │ note")
    print("  │ ───┼────────┼────────┼─────┼────────────┼────────────┼──────────────")

    for index, segment in enumerate(segments):
        segment_frames = int(round(segment["duration"] * timeline_fps))
        timeline_start = timeline_pos
        timeline_end = timeline_start + segment_frames

        # All source positions derive from the frame-quantized timeline grid,
        # never from float seconds — recomputing from floats drifts against
        # the accumulated frame position and shifts sync by a frame or more.
        if segment["camera"] == 1:
            # The edit timeline IS camera-1 time, so source == timeline exactly.
            source_in = timeline_start
            source_out = min(cam1_duration_frames, timeline_end)
            clip = _clip(track1, f"clip-cam1-{cam1_count}", os.path.basename(cam1_path), "file-1",
                         timeline_start, timeline_end, source_in, source_out, timeline_fps)
            cam1_count += 1
            if "file-1" not in files_added:
                _file_element(None, "file-1", os.path.basename(cam1_path), _pathurl(cam1_path),
                              cam1_duration_frames, cam1_meta["fps"], True,
                              element=clip.find("file"))
                files_added.add("file-1")
            note = f"TL@{timeline_fps:.0f}fps"
        else:
            offset_frames = int(round(sync_offset_seconds * timeline_fps))
            source_in = max(0, timeline_start - offset_frames)
            source_out = min(cam2_duration_frames, source_in + segment_frames)
            clip = _clip(track2, f"clip-cam2-{cam2_count}", os.path.basename(cam2_path), "file-2",
                         timeline_start, timeline_end, source_in, source_out, timeline_fps)
            cam2_count += 1
            if "file-2" not in files_added:
                _file_element(None, "file-2", os.path.basename(cam2_path), _pathurl(cam2_path),
                              cam2_duration_frames, cam2_meta["fps"], True,
                              element=clip.find("file"))
                files_added.add("file-2")
            note = f"offset {-offset_frames} frames"

        print(f"  │ {index:3d}│ {segment['start']:6.1f} │ {segment['duration']:6.1f} │  {segment['camera']}  │ "
              f"{source_in:10d} │ {source_out:10d} │ {note}")

        # Master audio: continuous camera1 audio, source == timeline exactly.
        audio_in = timeline_start
        audio_out = timeline_end
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
        if "file-3" not in files_added:
            _file_element(None, "file-3", os.path.basename(audio_path), _pathurl(audio_path),
                          audio_duration_frames, timeline_fps, False,
                          element=audio_clip.find("file"))
            files_added.add("file-3")

        timeline_pos = timeline_end

    xml_str = minidom.parseString(tostring(xmeml)).toprettyxml(indent="  ")
    final_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'
    final_xml += "\n".join(xml_str.split("\n")[1:])

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"  │ clips           : cam1 {cam1_count}, cam2 {cam2_count}, audio {audio_count}")
    print(f"  └─ XML written to {output_path}")
    return output_path
