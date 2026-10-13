"""
Sync diagnostic: generates three test XMLs with different Camera 2 offset values.
Used to determine the correct offset direction and magnitude.
Run after the main pipeline has produced v10_edit_segments.json.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pipeline.xml_builder import generate_resolve_xml

SEGMENTS_PATH = "results/v10_edit_segments.json"
CAM1 = "datasets/test_set_1/camera1_short.mp4"
CAM2 = "datasets/test_set_1/camera2_short.mp4"
AUDIO = "results/camera1_audio.wav"

if not os.path.exists(SEGMENTS_PATH):
    print(f"ERROR: {SEGMENTS_PATH} not found. Run main.py first.")
    sys.exit(1)

with open(SEGMENTS_PATH, "r") as f:
    segments = json.load(f)

offsets = {
    "offset_neg0975": -0.975,   # Camera 2 started 0.975s BEFORE Camera 1
    "offset_zero":      0.000,  # No offset
    "offset_pos0975":  +0.975,  # Camera 2 started 0.975s AFTER Camera 1 (current)
    "offset_pos2350":  +2.350,  # Ground truth from clap sync
    "offset_neg2350":  -2.350,  # Ground truth flipped
}

for label, offset in offsets.items():
    out = f"results/diag_{label}.xml"
    print(f"\nGenerating {out}  (offset={offset:+.3f}s) ...")
    generate_resolve_xml(segments, CAM1, CAM2, AUDIO, offset, out)
    print(f"  -> Done: {out}")

print("\n--- Diagnostic XMLs created ---")
print("Import each into DaVinci Resolve and find the one where Camera 2 mouth matches audio.")
print("Look for a segment where the host says a clearly identifiable word (e.g. 'hello', 'yeah').")
print("The correct offset is whichever XML shows Camera 2 lip-sync on that segment.")
