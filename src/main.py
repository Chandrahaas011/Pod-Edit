# main.py
# Orchestrates the full podcast auto-edit pipeline:
# 1) Audio extraction
# 2) Sync estimation
# 3) Silence detection + keep segments
# 4) Speaker activity (camera choice)
# 5) Merge timelines
# 6) EDL generation

import os
import json
import time

# Import our modules
import audio_processor
import sync_engine
import silence_detector
import speaker_detector
import timeline_merger
import edl_generator  # uses its own main(), we’ll call helper functions

BASE_DIR = r"C:\podcast-research"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def run_pipeline():
    print("=" * 60)
    print("AUTOMATIC PODCAST EDITOR - FULL PIPELINE")
    print("=" * 60)

    # ----------------------------
    # 0) Basic configuration
    # ----------------------------
    datasets_dir = os.path.join(BASE_DIR, "datasets", "test_set_1")
    results_dir = os.path.join(BASE_DIR, "results")
    ensure_dir(results_dir)

    # You can hardcode or prompt; for now we assume:
    cam1_path = os.path.join(datasets_dir, "camera1_short.mp4")
    cam2_path = os.path.join(datasets_dir, "camera2_short.mp4")

    if not os.path.exists(cam1_path) or not os.path.exists(cam2_path):
        print("❌ camera1_short.mp4 or camera2_short.mp4 not found in datasets/test_set_1")
        print("   Please place your test clips there.")
        return

    fps = 25.0  # change if your project uses 30/29.97
    print(f"Using FPS = {fps}")

    # You could optionally prompt:
    # fps_input = input(f"Enter FPS (default {fps}): ").strip()
    # if fps_input:
    #     fps = float(fps_input)

    # ----------------------------
    # 1) Audio extraction
    # ----------------------------
    print("\n[1/6] Audio extraction")
    ap = audio_processor.AudioProcessor(sample_rate=44100, log_metrics=True)

    cam1_audio_path = os.path.join(results_dir, "camera1_audio.wav")
    cam2_audio_path = os.path.join(results_dir, "camera2_audio.wav")

    cam1_audio_path = ap.extract_audio(cam1_path, cam1_audio_path)
    cam2_audio_path = ap.extract_audio(cam2_path, cam2_audio_path)

    # Optionally save metrics
    ap.save_metrics(os.path.join(results_dir, "audio_processing_metrics.json"))

    # Load audio for later steps
    import librosa
    audio1, sr1 = librosa.load(cam1_audio_path, sr=44100, mono=True)
    audio2, sr2 = librosa.load(cam2_audio_path, sr=44100, mono=True)

    # ----------------------------
    # 2) Sync estimation
    # ----------------------------
    print("\n[2/6] Sync estimation")
    se = sync_engine.SyncEngine(sample_rate=44100, max_offset_seconds=5.0)
    offset_seconds = se.estimate_offset(audio1, audio2, downsample_factor=4, plot_debug=True)
    se.save_metrics(os.path.join(results_dir, "sync_metrics.json"))

    # ----------------------------
    # 3) Silence detection (on camera1 audio for now)
    # ----------------------------
    print("\n[3/6] Silence detection")
    sd = silence_detector.SilenceDetector(
        sample_rate=sr1,
        db_threshold=-40.0,        # tune this later
        min_silence_duration=1.5,
        padding=0.2
    )
    silence_segments = sd.detect_silence(audio1)
    keep_segments = sd.get_keep_segments(audio_duration=len(audio1) / sr1)
    sd.save_results(results_dir, keep_segments=keep_segments)
    sd.plot_rms_debug(audio1, max_time=60)

    # ----------------------------
    # 4) Speaker activity (camera choice)
    # ----------------------------
    print("\n[4/6] Speaker activity analysis")
    # For now we assume you have mic1.wav and mic2.wav exported already
    mic1_path = os.path.join(results_dir, "mic1.wav")
    mic2_path = os.path.join(results_dir, "mic2.wav")

    if not (os.path.exists(mic1_path) and os.path.exists(mic2_path)):
        print("⚠️  mic1.wav and/or mic2.wav not found in results/.")
        print("    Please export them from Premiere (one mono file per speaker) for best camera switching.")
        print("    Skipping speaker analysis and defaulting all segments to camera 1.")
        # Fallback: create speaker_timeline with active_speaker=0 and camera=1
        speaker_timeline = [{
            "start": 0.0,
            "end": len(audio1) / sr1,
            "active_speaker": 0
        }]
        with open(os.path.join(results_dir, "speaker_timeline.json"), "w") as f:
            json.dump(speaker_timeline, f, indent=2)
    else:
        a1, _ = librosa.load(mic1_path, sr=44100, mono=True)
        a2, _ = librosa.load(mic2_path, sr=44100, mono=True)

        analyzer = speaker_detector.SpeakerActivityAnalyzer(
            sample_rate=44100,
            frame_length_ms=50,
            hop_length_ms=25,
            db_floor=-60.0,
            min_db_diff=3.0,
            min_activation_db=-45.0,
            min_switch_interval=1.5
        )
        speaker_segments = analyzer.analyze(a1, a2, plot_debug=True)
        analyzer.save_results(results_dir)

    # ----------------------------
    # 5) Merge timelines (keep + speaker → edit segments)
    # ----------------------------
    print("\n[5/6] Merging silence and speaker timelines")
    from timeline_merger import merge_keep_and_speaker

    # Reload from disk to be sure we’re using saved JSON
    with open(os.path.join(results_dir, "keep_segments.json"), "r") as f:
        keep_segments = json.load(f)
    with open(os.path.join(results_dir, "speaker_timeline.json"), "r") as f:
        speaker_timeline = json.load(f)

    edit_segments = merge_keep_and_speaker(
        keep_segments=keep_segments,
        speaker_segments=speaker_timeline,
        default_camera=1
    )

    with open(os.path.join(results_dir, "edit_segments.json"), "w") as f:
        json.dump(edit_segments, f, indent=2)

    print("Saved edit_segments.json with", len(edit_segments), "segments")

    # ----------------------------
    # 6) EDL generation
    # ----------------------------
    print("\n[6/6] EDL generation")
    # We’ll use edl_generator.generate_edl() and save_edl() directly
    from edl_generator import generate_edl, save_edl, probe_duration

    # Reload sync offset just to be safe
    with open(os.path.join(results_dir, "sync_metrics.json"), "r") as f:
        sync_metrics = json.load(f)
    sync_offset_seconds = sync_metrics.get("estimated_offset_seconds", 0.0)

    print(f"Using sync offset: {sync_offset_seconds:.4f} s")

    # Optional duration check
    d1 = probe_duration(cam1_path)
    d2 = probe_duration(cam2_path)
    print(f"Camera1 duration: {d1}")
    print(f"Camera2 duration: {d2}")

    lines = generate_edl(
        edit_segments=edit_segments,
        sync_offset_seconds=sync_offset_seconds,
        fps=fps,
        camera1_reel="CAM1",
        camera2_reel="CAM2",
        camera1_start_time=0.0,
        camera2_start_time=0.0
    )

    edl_path = os.path.join(results_dir, "podcast_edit.edl")
    save_edl(lines, edl_path)

    print("\n✅ Pipeline complete.")
    print(f"Import {edl_path} into Premiere Pro to view the auto-edited sequence.")

if __name__ == "__main__":
    start = time.time()
    run_pipeline()
    print(f"\nTotal pipeline time: {time.time() - start:.2f} seconds")
