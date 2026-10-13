import os
import shutil

project_root = r"c:\third year\sem 6\mini project\podedit"
deletable_src = os.path.join(project_root, "deletable", "src")
deletable_root = os.path.join(project_root, "deletable", "root")

os.makedirs(deletable_src, exist_ok=True)
os.makedirs(deletable_root, exist_ok=True)

files_to_move = [
    # src files
    "src/v6.py", "src/v7.py", "src/v8.py",
    "src/visual_detection.py", "src/visual_detection_v2.py", "src/visual_detection_v3.py", 
    "src/visual_detection_v4.py", "src/visual_detection_v5.py",
    "src/visual_mesh.py",
    "src/voice_detection.py", "src/voice_detection_fast.py",
    "src/visual_mouth.py", "src/audio_chunking.py",
    "src/prproj_generator.py", "src/generate_multitrack_edl.py",
    "src/edl_generator.py", "src/generate_csv_reference.py",
    "src/generate_xml_v3.py", "src/generate_xml_v4.py",
    "src/xml_generator.py", "src/generate_resolve_xml.py",
    "src/rerun_detection.py", "src/metrics_collector.py",
    "src/sample_based_detection.py", "src/speaker_detector.py",
    "src/speaker_diarization.py", "src/analyze_samples.py",
    "src/silence_detector.py", "src/timeline_merger.py",
    "src/test_xml.py", "src/sync_evaluation.py",
    
    # root files
    "premiere_com_builder.py", "premiere_timeline_builder.jsx",
    "resolve_timeline_builder.py", "podedit_gui.py"
]

for f in files_to_move:
    src_path = os.path.join(project_root, f)
    if os.path.exists(src_path):
        if f.startswith("src/"):
            dst_path = os.path.join(deletable_src, os.path.basename(f))
        else:
            dst_path = os.path.join(deletable_root, os.path.basename(f))
        shutil.move(src_path, dst_path)
        print(f"Moved {f} to {dst_path}")
    else:
        print(f"File {f} not found, skipping.")

print("Cleanup complete.")
