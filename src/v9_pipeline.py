"""
PodEdit 1.5 pipeline.

This is the GUI-friendly orchestration layer for the final neural workflow:
audio extraction, sync estimation, pyannote diarization, visual identity mapping,
segment building, and Resolve XML generation.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

DEFAULT_CAM1_PATH = os.path.join(PROJECT_ROOT, "datasets", "test_set_1", "camera1_short.mp4")
DEFAULT_CAM2_PATH = os.path.join(PROJECT_ROOT, "datasets", "test_set_1", "camera2_short.mp4")
DEFAULT_RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
DEFAULT_MAX_DURATION_SECONDS = 1500
VISUAL_LIMIT_SECONDS = 600


@dataclass
class PipelineResult:
    cam1_audio_path: str
    cam2_audio_path: str
    sync_offset_seconds: float
    segments_path: str
    xml_path: str
    segments: list


def _log(message):
    print(message, flush=True)


def _emit_progress(progress_callback, stage, fraction, message):
    if progress_callback is not None:
        progress_callback(stage=stage, fraction=fraction, message=message)


def _merge_short_segments(segments, minimum_duration=2.0):
    if not segments:
        return []

    merged = [dict(segments[0])]
    for segment in segments[1:]:
        candidate = dict(segment)
        if merged[-1]["camera"] == candidate["camera"]:
            merged[-1]["duration"] += candidate["duration"]
            continue
        if candidate["duration"] < minimum_duration:
            merged[-1]["duration"] += candidate["duration"]
            continue
        merged.append(candidate)

    return merged


def _build_segments_from_diarization(raw_segments, speaker_to_camera, total_duration_seconds):
    final_segments = []
    current_camera = None
    segment_start = 0.0

    for chunk in raw_segments:
        camera = speaker_to_camera.get(chunk["speaker"], 1)
        start = float(chunk["start"])

        if current_camera is None:
            current_camera = camera
            segment_start = 0.0
            continue

        if camera != current_camera:
            duration = max(0.0, start - segment_start)
            if duration > 0:
                final_segments.append(
                    {
                        "start": round(segment_start, 4),
                        "duration": round(duration, 4),
                        "camera": current_camera,
                    }
                )
            current_camera = camera
            segment_start = start

    if current_camera is None:
        return [
            {
                "start": 0.0,
                "duration": round(total_duration_seconds, 4),
                "camera": 1,
            }
        ]

    if segment_start < total_duration_seconds:
        final_segments.append(
            {
                "start": round(segment_start, 4),
                "duration": round(total_duration_seconds - segment_start, 4),
                "camera": current_camera,
            }
        )

    return _merge_short_segments(final_segments)


def run_v9(
    cam1_path=None,
    cam2_path=None,
    results_dir=None,
    force=False,
    max_duration_seconds=DEFAULT_MAX_DURATION_SECONDS,
    output_filename="v9_timeline.xml",
    progress_callback=None,
):
    from src.audio_processor import AudioProcessor
    from src.resolve_xml_v9 import generate_resolve_xml
    from src.sync_engine import SyncEngine

    start_t = time.time()
    cam1_path = cam1_path or DEFAULT_CAM1_PATH
    cam2_path = cam2_path or DEFAULT_CAM2_PATH
    results_dir = results_dir or DEFAULT_RESULTS_DIR
    os.makedirs(results_dir, exist_ok=True)

    segments_path = os.path.join(results_dir, "v9_edit_segments.json")
    cam1_audio_path = os.path.join(results_dir, "camera1_audio.wav")
    cam2_audio_path = os.path.join(results_dir, "camera2_audio.wav")
    sync_metrics_path = os.path.join(results_dir, "sync_metrics.json")
    output_path = os.path.join(results_dir, output_filename)

    _log("\n" + "╔" + "═" * 58 + "╗")
    _log("║    PodEdit 1.5 — NEURAL HYBRID PIPELINE                  ║")
    _log("╚" + "═" * 58 + "╝")

    if os.path.exists(segments_path) and not force:
        _log("📂  Reusing existing v9 segments")
        with open(segments_path, "r", encoding="utf-8") as f:
            segments = json.load(f)
        sync_offset_seconds = 0.0
        if os.path.exists(sync_metrics_path):
            try:
                with open(sync_metrics_path, "r", encoding="utf-8") as f:
                    sync_metrics = json.load(f)
                sync_offset_seconds = float(sync_metrics.get("estimated_offset_seconds", 0.0))
            except Exception:
                sync_offset_seconds = 0.0

        _emit_progress(progress_callback, "xml", 0.9, "Regenerating XML from cached segments")
        xml_path = generate_resolve_xml(
            edit_segments=segments,
            cam1_path=cam1_path,
            cam2_path=cam2_path,
            audio_path=cam1_audio_path,
            results_dir=results_dir,
            output_path=output_path,
            sync_offset_seconds=sync_offset_seconds,
            timeline_fps=30,
        )
        _emit_progress(progress_callback, "done", 1.0, "Processing complete")
        _log(f"\n✅  v9 pipeline completed in {(time.time() - start_t) / 60.0:.1f} minutes")
        return PipelineResult(
            cam1_audio_path=cam1_audio_path,
            cam2_audio_path=cam2_audio_path,
            sync_offset_seconds=sync_offset_seconds,
            segments_path=segments_path,
            xml_path=xml_path,
            segments=segments,
        )

    _emit_progress(progress_callback, "audio", 0.05, "Extracting audio")
    processor = AudioProcessor(sample_rate=44100, log_metrics=True)
    cam1_audio_path = processor.extract_audio(cam1_path, cam1_audio_path)
    cam2_audio_path = processor.extract_audio(cam2_path, cam2_audio_path)
    processor.save_metrics(os.path.join(results_dir, "audio_processing_metrics.json"))

    _emit_progress(progress_callback, "sync", 0.18, "Estimating sync offset")
    audio1, sr1 = processor.load_audio(cam1_audio_path, duration=max_duration_seconds)
    audio2, _ = processor.load_audio(cam2_audio_path, duration=max_duration_seconds)
    sync_engine = SyncEngine(sample_rate=sr1, max_offset_seconds=5.0)
    sync_offset_seconds = sync_engine.estimate_offset(audio1, audio2, downsample_factor=4, plot_debug=False)
    sync_engine.save_metrics(sync_metrics_path)
    _log(f"  Sync offset (audio2 relative to audio1): {sync_offset_seconds:.4f}s")

    env_path = os.path.join(sys._MEIPASS, ".env") if getattr(sys, 'frozen', False) else os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(env_path):
        load_dotenv(env_path)
    
    token = os.environ.get("HF_TOKEN")

    _emit_progress(progress_callback, "diarization", 0.32, "Loading pyannote model")
    try:
        import torch
        from pyannote.audio import Pipeline
    except Exception as exc:
        raise RuntimeError(f"Pyannote or torch could not be imported: {exc}") from exc

    try:
        pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=token,
        )
    except Exception as exc:
        raise RuntimeError(f"Failed to load pyannote pipeline: {exc}") from exc

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    _log(f"  Pyannote ready on {device}")

    _emit_progress(progress_callback, "diarization", 0.45, "Running speech diarization")
    waveform = torch.tensor(audio1).unsqueeze(0)
    try:
        from pyannote.audio.pipelines.utils.hook import ProgressHook
        with ProgressHook() as hook:
            diarization = pipeline({"uri": "audio", "waveform": waveform, "sample_rate": sr1}, hook=hook)
    except ImportError:
        diarization = pipeline({"uri": "audio", "waveform": waveform, "sample_rate": sr1})
    annotation = diarization.speaker_diarization if hasattr(diarization, "speaker_diarization") else diarization

    raw_segments = []
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        if turn.start > max_duration_seconds:
            break
        raw_segments.append({"start": turn.start, "end": turn.end, "speaker": speaker})

    _log(f"  Pyannote detected {len(raw_segments)} speech turns")

    _emit_progress(progress_callback, "visual", 0.62, "Mapping speakers to cameras")
    try:
        from src.visual_mesh import extract_mesh_scores, verify_speaker_with_mesh
    except Exception as exc:
        raise RuntimeError(
            "MediaPipe visual mesh import failed. Verify that mediapipe works in this Python environment."
        ) from exc

    visual_limit = min(max_duration_seconds, VISUAL_LIMIT_SECONDS)
    scores_c1 = extract_mesh_scores(cam1_path, max_duration=visual_limit, camera_name="Camera 1")
    scores_c2 = extract_mesh_scores(cam2_path, max_duration=visual_limit, camera_name="Camera 2")
    speaker_to_camera = verify_speaker_with_mesh(raw_segments, scores_c1, scores_c2)

    total_duration_seconds = len(audio1) / float(sr1)
    segments = _build_segments_from_diarization(raw_segments, speaker_to_camera, total_duration_seconds)

    c1_duration = sum(item["duration"] for item in segments if item["camera"] == 1)
    c2_duration = sum(item["duration"] for item in segments if item["camera"] == 2)
    total = max(c1_duration + c2_duration, 1e-8)
    _log(f"\n  Final Output: {len(segments)} segments")
    _log(f"  Camera 1: {c1_duration:.0f}s ({(c1_duration / total) * 100:.1f}%)")
    _log(f"  Camera 2: {c2_duration:.0f}s ({(c2_duration / total) * 100:.1f}%)")

    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2)

    _log(f"  Saved segments to {segments_path}")
    _emit_progress(progress_callback, "xml", 0.84, "Building XML timeline")

    xml_path = generate_resolve_xml(
        edit_segments=segments,
        cam1_path=cam1_path,
        cam2_path=cam2_path,
        audio_path=cam1_audio_path,
        results_dir=results_dir,
        output_path=output_path,
        sync_offset_seconds=sync_offset_seconds,
        timeline_fps=30,
    )

    _emit_progress(progress_callback, "done", 1.0, "Processing complete")
    _log(f"\n✅  v9 pipeline completed in {(time.time() - start_t) / 60.0:.1f} minutes")

    return PipelineResult(
        cam1_audio_path=cam1_audio_path,
        cam2_audio_path=cam2_audio_path,
        sync_offset_seconds=sync_offset_seconds,
        segments_path=segments_path,
        xml_path=xml_path,
        segments=segments,
    )


def main():
    result = run_v9(force="--force-detect" in sys.argv)
    _log(f"\n{'═' * 60}")
    _log(f"🎬  ALL DONE! Import {os.path.basename(result.xml_path)} into DaVinci Resolve.")
    _log(f"{'═' * 60}")


if __name__ == "__main__":
    main()
