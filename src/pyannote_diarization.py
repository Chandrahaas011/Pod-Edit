"""
State-of-the-Art Speaker Diarization using pyannote.audio
This replaces the resemblyzer approach with much more accurate detection.
"""

import os
import json
import torch
from pyannote.audio import Pipeline
from pyannote.audio.pipelines.utils.hook import ProgressHook


def run_pyannote_diarization(audio_path, output_dir, num_speakers=2, 
                              min_switch_interval=3.0):
    """
    Run speaker diarization using pyannote.audio.
    Automatically detects who is speaking when.
    """
    print("=" * 60)
    print("PYANNOTE.AUDIO SPEAKER DIARIZATION")
    print("=" * 60)
    print(f"Audio: {audio_path}")
    print(f"Expected speakers: {num_speakers}")
    print("=" * 60)
    
    # Initialize pipeline
    # Note: First run will download the model (~300MB)
    print("\nLoading diarization pipeline...")
    print("(First run downloads model, this may take a few minutes)")
    
    try:
        # Try to use the pipeline with HuggingFace token
        # For pyannote.audio v4.0+, use token= instead of use_auth_token=
        hf_token = os.environ.get("HF_TOKEN")
        if hf_token:
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1",
                token=hf_token
            )
        else:
            # Try without token (may work for some models)
            pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-3.1"
            )
    except Exception as e:
        print(f"Error loading pipeline: {e}")
        print("\nTo use pyannote.audio, you need to:")
        print("1. Create a HuggingFace account: https://huggingface.co/join")
        print("2. Accept the model terms: https://huggingface.co/pyannote/speaker-diarization-3.1")
        print("3. Get your token: https://huggingface.co/settings/tokens")
        print("4. Set environment variable: $env:HF_TOKEN='your_token'")
        return []
    
    # Move to GPU if available
    if torch.cuda.is_available():
        pipeline = pipeline.to(torch.device("cuda"))
        print("Using GPU for inference")
    else:
        print("Using CPU for inference (slower)")
    
    # Run diarization
    print("\nRunning speaker diarization...")
    with ProgressHook() as hook:
        diarization = pipeline(audio_path, num_speakers=num_speakers, hook=hook)
    
    # Convert to segments
    segments = []
    for turn, _, speaker in diarization.itertracks(yield_label=True):
        # Map speaker labels to 1 or 2
        speaker_num = 1 if speaker == "SPEAKER_00" else 2
        
        segments.append({
            "start": float(turn.start),
            "end": float(turn.end),
            "active_speaker": speaker_num
        })
    
    print(f"\nDetected {len(segments)} raw segments")
    
    # Merge short segments
    merged_segments = []
    for seg in segments:
        if merged_segments and seg["active_speaker"] == merged_segments[-1]["active_speaker"]:
            # Extend previous segment
            merged_segments[-1]["end"] = seg["end"]
        elif seg["end"] - seg["start"] < 1.0:
            # Skip very short segments (< 1s)
            continue
        else:
            merged_segments.append(seg)
    
    # Stats
    spk1_time = sum(s["end"] - s["start"] for s in merged_segments if s["active_speaker"] == 1)
    spk2_time = sum(s["end"] - s["start"] for s in merged_segments if s["active_speaker"] == 2)
    
    print(f"\nDiarization Results:")
    print(f"  Speaker 1: {spk1_time/60:.1f} min")
    print(f"  Speaker 2: {spk2_time/60:.1f} min")
    print(f"  Final segments: {len(merged_segments)}")
    
    # Save
    timeline_path = os.path.join(output_dir, "speaker_timeline.json")
    with open(timeline_path, "w") as f:
        json.dump(merged_segments, f, indent=2)
    print(f"\nSaved: {timeline_path}")
    
    metrics = {
        "method": "pyannote.audio speaker-diarization-3.1",
        "audio_source": "camera1_audio.wav only",
        "speaker1_time_seconds": float(spk1_time),
        "speaker2_time_seconds": float(spk2_time),
        "num_segments": len(merged_segments),
    }
    metrics_path = os.path.join(output_dir, "speaker_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    
    return merged_segments


def convert_to_edit_segments(speaker_timeline, output_dir):
    """Convert speaker timeline to edit segments."""
    edit_segments = []
    current_camera = 1
    
    cam1_time = 0
    cam2_time = 0
    
    for seg in speaker_timeline:
        if seg["active_speaker"] == 1:
            current_camera = 1
        elif seg["active_speaker"] == 2:
            current_camera = 2
        
        duration = seg["end"] - seg["start"]
        if current_camera == 1:
            cam1_time += duration
        else:
            cam2_time += duration
        
        edit_segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "duration": duration,
            "camera": current_camera
        })
    
    total = cam1_time + cam2_time
    print(f"\nCamera Distribution:")
    print(f"  Camera 1: {cam1_time/60:.1f} min ({100*cam1_time/total:.1f}%)")
    print(f"  Camera 2: {cam2_time/60:.1f} min ({100*cam2_time/total:.1f}%)")
    
    output_path = os.path.join(output_dir, "edit_segments.json")
    with open(output_path, "w") as f:
        json.dump(edit_segments, f, indent=2)
    print(f"\nSaved: {output_path} ({len(edit_segments)} segments)")
    
    return edit_segments


if __name__ == "__main__":
    project_dir = r"C:\third year\sem 6\mini project\podedit"
    results_dir = os.path.join(project_dir, "results")
    audio_path = os.path.join(results_dir, "camera1_audio.wav")
    
    # Run diarization (2 speakers for podcast)
    speaker_timeline = run_pyannote_diarization(
        audio_path=audio_path,
        output_dir=results_dir,
        num_speakers=2
    )
    
    # Convert to edit segments
    if speaker_timeline:
        convert_to_edit_segments(speaker_timeline, results_dir)
    
    print("\n" + "=" * 60)
    print("✅ Pyannote diarization complete!")
    print("=" * 60)
