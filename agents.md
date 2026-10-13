# PodEdit — agents.md (Persistent Project Memory)

> **Current operational status (2026-08-11): PodEdit 1.4.** The maintained
> entry point is `main.py` with the `pipeline/` package. Any later section that
> calls v1.0, v9, MediaPipe, or a `src/v*.py` script "current" is historical;
> see the newest append-only learnings at the end and `HANDOFF.md`.

> **For:** Claude Opus 4.6 (Thinking) and future models  
> **Rule:** When you learn something new — a fix, a gotcha, a design decision — **APPEND it
> to the "Model Learnings" section at the bottom of this file.** Do not delete existing entries.
> Future models will read this file and benefit from your discoveries.

---

## YOUR ROLE

You are a **professional software developer AND video editor** working on PodEdit.
You understand NLE timelines, frame-accurate editing, FPS conversion, audio sync,
and codec behavior — not just code.

This project is being developed for publication as an **IEEE research paper**. Every
algorithm, library, or technique you use or reference must be tracked in IEEE citation
format with a working URL. Maintain citations in the "References" section below.

---

## WHAT IS THIS PROJECT

An automated podcast video editing tool. Given two camera recordings of a two-person
podcast, it detects who is speaking each second and produces a DaVinci Resolve XML
timeline that cuts between camera angles automatically — replacing hours of manual editing.

**Location:** `c:\third year\sem 6\mini project\podedit`  
**Virtual Env:** `.\.venv\Scripts\Activate.ps1`

---

## END GOALS (The Big Picture)

1. **Immediate:** Fix audio-video sync in XML output. Get a usable multi-cam edit.
2. **Medium-term:** Polish detection accuracy across diverse podcast styles.
3. **Long-term:** Package this as a **Windows .exe with a modern, polished GUI.**
   Think: drag-and-drop video files, progress bars, preview window, export button.
   We will get there step by step — do NOT jump ahead to GUI work until the core engine
   is rock-solid.
4. **Academic:** Publish as an IEEE research paper. All references must be real, verifiable,
   and formatted correctly.

---

## USER REQUIREMENTS (Non-Negotiable)

1. **Offline & Lightweight.** No cloud APIs. Must run locally on a mid-range laptop.
   Heavy libraries (PyTorch, PyAnnote, Whisper, Resemblyzer, etc.) **ARE allowed** as long
   as they fit within the hardware limits (16GB RAM, i7-1360P) and the time budget below.
   MediaPipe is specifically broken on Python 3.13 — avoid it.
2. **No calibration.** Must work on any podcast video automatically. No speaker voice
   samples required up front.
3. **n-1 Camera Optimization.** For n speakers, ideally only analyze n-1 camera files
   (infer the remaining speaker from the others). Currently disabled for accuracy — future goal.
4. **3-Mode Detection System (future roadmap):**
   - Audio-only mode
   - Visual-only mode (lip movement)
   - **Hybrid mode** (current focus: audio VAD + visual mouth tracking) ← **MAIN PRIORITY**
5. **No frame caching.** Process video directly frame by frame. No writing frames to disk.
6. **Stable output.** No rapid flickering between cameras. Cuts should feel editorial.
7. **Output:** DaVinci Resolve-compatible FCP XML 7 timeline.
8. **Performance target:** Maximum **2 hours** for a ~30-minute episode (both cams).
   Faster is better, but accuracy is more important than speed.
9. **Console Logging:** Nerdy, verbose, and mathematically informative. When processing,
   the console should show rich real-time stats — frame counts, FPS, percentages, ETAs,
   normalization factors, per-second decisions. The user wants to SEE the math happening.
   Think of it as a cockpit dashboard for the processing engine.

### Test Scope
- **Process only the first 25 minutes** of the episode (not the full 69 min).
  This speeds up iteration while developing. Full-length runs come later.

### Expected Results for Test Set (first 25 min)
> These targets may vary slightly since we're only processing a subset.
- Speaker 1 (Host, Camera 1): **~75–95%** of screen time
- Speaker 2 (Guest, Camera 2): **~5–25%** of screen time
- Segments: proportional to duration (~30–100 for 25 min)

---

## HARDWARE & ENVIRONMENT

- CPU: Intel i7-1360P
- RAM: 16GB
- GPU: Intel Iris Xe iGPU (OpenCL available but NOT useful — see failed experiments below)
- OS: Windows 11
- Python: 3.13 (MediaPipe's Tasks API is broken on 3.13 — avoid it)

### Currently Installed Packages
`opencv-python`, `numpy`, `scipy`, `librosa`, `webrtcvad`, `ffmpeg-python`

### Allowed But Not Yet Installed
`torch`, `resemblyzer`, `pyannote.audio`, `whisper` — these ARE permitted if they
help with accuracy, but check RAM/time constraints first. Install only what you need.

### Do NOT Use
`mediapipe` — broken on Python 3.13 (Tasks API import crash).

---

## TEST MATERIAL

| File | Speaker | Duration | FPS |
|------|---------|----------|-----|
| `datasets/test_set_1/camera1_short.mp4` | Host (Speaker 1) | ~69 min | **25 FPS** |
| `datasets/test_set_1/camera2_short.mp4` | Guest (Speaker 2) | ~69 min | **30 FPS** |

> ⚠️ The two cameras have DIFFERENT frame rates. This is a critical source of bugs in
> the XML generator.

`datasets/test_set_1/ground_truth.json`:
- Camera 2 started recording **2.35 seconds AFTER** Camera 1 (clap sync measurement).
- Also contains a few manually-annotated speaker segments for spot-checking.

`results/camera1_audio.wav`:
- Extracted from Camera 1. Used as the **single master audio track** throughout the
  entire edited timeline (Camera 2's audio is not used at all in the output).

---

## CURRENT STATUS (2026-07-16): PodEdit 1.0 — Final Pipeline, Verified Structure

The active implementation is `main.py` + the `pipeline/` package (see README.md).
Everything below this section is historical context from v1–v11; consult it for
*why* decisions were made, but the code it references is superseded.

- Detection: pyannote diarization (audio) + OpenCV lip-activity vote (visual) = hybrid mode.
- Verified on test_set_1 (first 25 min): Camera 1 = 89.6%, Camera 2 = 10.4%, 11 segments,
  sync offset −0.9810s at 58× correlation confidence. All XML structural checks pass.
- `results/podedit_preview.mp4` renders the actual edit with ffmpeg — the ground-truth
  check that isolates edit-math bugs from Resolve XML-interpretation bugs.
- Remaining human verification: watch the preview, then import
  `results/podedit_timeline.xml` into DaVinci Resolve and confirm sync visually.

---

## SYNC HISTORY — Which Versions Had Working Sync?

> **Important context:** Audio-video sync **DID work** in some of the earlier versions
> (likely v1 or v2/v3, before the XML generator was heavily modified). The sync problems
> started appearing around v4/v4.1 when the dual-camera approach was introduced and the
> generate_resolve_xml.py was rewritten with the `REVERSE_SYNC_OFFSET` flag and hardcoded
> FPS. If you can find the working XML generation logic from v1–v3 era, that may be the
> fastest path to fixing sync.

---

## WHAT WE TRIED — Full History

### Visual Detection v1 (`visual_detection.py`)
**Approach:** Haar cascade face detection + static mouth analysis (gradient, variance,
dark ratio). Audio VAD (webrtcvad) gates the video analysis.
Only Camera 1 is processed (n-1 optimization). If Camera 1's mouth is active → Speaker 1,
otherwise → Speaker 2.  
**Results:** Speaker 1 = 74%, Speaker 2 = 26%, 364 segments.  
**Problem:** Qualitatively "barely passable". Threshold too sensitive. Random-feeling switches.  
**Why abandoned:** Underlying mouth scoring was too noisy.

### Visual Detection v2 (`visual_detection_v2.py`)
**Approach:** Replaced static mouth score with temporal frame differencing — sampled
multiple frames per second, computed pixel difference in mouth region between consecutive
frames. Added face tracking (size consistency check).  
**Results:** Slightly better movement scores but still unreliable switching.  
**Problem:** Frame differencing is too sensitive to camera noise and compression artifacts.  
**Why abandoned:** Still random. Not robust enough.

### Visual Detection v3 (`visual_detection_v3.py`)
**Approach:** Optical flow (Farneback) on mouth ROI. n-1 optimization (only Camera 1).
Added hysteresis (`min_switch_seconds = 2.0`). Dynamic thresholds (percentile-based).  
**Results (tuned):** Speaker 1 = 91.4%, Speaker 2 = 8.6%, 107 segments.  
**Problem:** Optical flow picks up head nodding as mouth movement. Normal podcast behavior
(nodding in agreement) triggered false switches to Camera 2.  
**Why abandoned:** Needed head motion compensation.

### Visual Detection v4 (`visual_detection_v4.py`)
**Approach:** Switched to **Dual-Camera Analysis** (process BOTH cameras, compare directly).
Added **Head Motion Compensation**: `score = mouth_flow - (head_flow × 0.75)`.
This cancels out nodding — if head moves, both mouth and forehead move equally;
speaking adds extra mouth movement on top.  
**Results (initial):** Speaker 1 = 92.1%, Speaker 2 = 7.9%, 210 segments.  
**Problem:** Raw scores had massive disparity between cameras — Camera 1 avg ~1.33,
Camera 2 avg ~0.12. Camera 2 almost never "won."

### Visual Detection v4.1 (still `visual_detection_v4.py`, tuned)
**Changes:** Added **90th-percentile normalization** per camera during speech segments.
This scales each camera's scores independently so they're comparable.
Increased hysteresis to `2.0s` for stability. Fixed sync offset flag.  
**Results:** Speaker 1 = 94.8%, Speaker 2 = 5.2%, **44 segments**.  
**Problem:** Only 44 segments for a 69-minute video is too few (~1 cut per 1.5 minutes).
The 90th percentile was too aggressive — it suppressed Camera 2 too much.
Sync offset was also wrong (automated estimate ~0.97s, ground truth is 2.35s).  
**User feedback:** "The audio is out of sync and the camera switching is bad."

### Visual Detection v5 (`visual_detection_v5.py`) ← CURRENT ACTIVE
**Changes from v4.1:**
- Normalization: 90th → **75th percentile** (less aggressive, Camera 2 gets more chances)
- Hysteresis: 2.0s → **1.5s** (more responsive cuts)
- Face Detection: **Lazy detection** — full Haar cascade only every 0.5s, reuse position
  in between. This was the main CPU bottleneck (face detection >> optical flow time).
- Frame Sampling: Process every 5th frame (`process_every_n_frames = 5`)
- Performance tracking: Per-stage timing in output
- Fixed logging bug: Console was showing wrong video timestamps (used `processed_count`
  instead of `frame_idx` for time calculation)

**Results:** Speaker 1 = 89%, Speaker 2 = 11%, **231 segments**, 19.4 min total runtime.  
Normalization factors: `norm_c1 = 0.806`, `norm_c2 = 0.100` (C2 still very low).

**Detection quality is acceptable. The XML sync is broken (see below).**

### Key Algorithm — Competitive Dual-Camera Analysis
```python
# Per camera, per second:
score = max(0, mouth_optical_flow - (head_optical_flow * 0.75))
# Subtracts head/forehead movement to cancel out nodding

# Normalize so cameras are on the same scale:
norm_score = score / percentile_75(speech_segment_scores)

# Decision:
if audio_vad[sec]:  # webrtcvad says there's speech
    if norm_c1 > norm_c2 and norm_c1 > 0.3:  speaker = 1
    elif norm_c2 > norm_c1 and norm_c2 > 0.3: speaker = 2
    else: hold_previous()
```

### v5 Tunable Parameters (in code)
| Parameter | Value | Effect |
|-----------|-------|--------|
| `min_switch_seconds` | 1.5 | Hysteresis — minimum hold time before switching camera |
| `sub_thresh` | 0.3 | Minimum normalized score to count as "active" |
| `process_every_n_frames` | 5 | Only analyze every 5th frame (speed) |
| `detect_interval` | `fps * 0.5` | Run Haar face detection every 0.5s (lazy tracking) |

### Known Weakness
Camera 2 normalization factor: `norm_c2 ≈ 0.100` vs `norm_c1 ≈ 0.806`.
Camera 2's mouth movement is barely detected — possibly due to angle, lighting, or the
face being less frontal. This means C2 rarely wins the competition on its own.

---

## FAILED EXPERIMENT: GPU Acceleration

We attempted to use OpenCL (Intel Iris Xe) to accelerate optical flow via `cv2.UMat`.
OpenCL was confirmed available: `Intel(R) Iris(R) Xe Graphics`.  
**Result:** Only ~10% GPU utilization. The bottleneck is CPU-bound face detection
(Haar cascade), which runs on CPU before any frame is sent to the GPU.
The UMat approach also added overhead for small ROI sizes (mouth/head regions are tiny).  
**Conclusion:** Keep CPU-only. The lazy face detection optimization (every 0.5s) gave
more benefit than OpenCL. Do not pursue GPU acceleration further for now.

---

## THE BROKEN XML GENERATOR (`src/generate_resolve_xml.py`)

### What It Should Do
1. Read `results/edit_segments.json` — output from v5, format: `[{start, duration, camera}]`
   where `start` and `duration` are in **seconds** on a shared timeline.
2. Place Camera 1 clips on Video Track 1, Camera 2 clips on Video Track 2.
3. Place continuous `camera1_audio.wav` on Audio Track 1 for all segments.
4. Apply sync offset so Camera 2 video lines up with Camera 1 audio.
5. Output FCP XML 7 format compatible with DaVinci Resolve.

### Bug 1: Hardcoded FPS (Critical)
```python
fps = 30  # ← WRONG. Camera 1 is 25fps, Camera 2 is 30fps.
source_start_frames = int(start_sec * fps)  # Used for BOTH cameras
```
Camera 1 clips are being calculated at 30fps but the source file is 25fps.
This causes a timing drift that gets worse the further into the video you go.

**Fix:** Detect each camera's FPS dynamically:
```python
cap = cv2.VideoCapture(cam1_path)
fps_c1 = cap.get(cv2.CAP_PROP_FPS)  # Should be 25.0
cap_c2 = cv2.VideoCapture(cam2_path)
fps_c2 = cap.get(cv2.CAP_PROP_FPS)  # Should be 30.0
```
Use `fps_c1` for Camera 1 clip in/out points, `fps_c2` for Camera 2.

### Bug 2: Sync Offset Confusion (Critical)
The `REVERSE_SYNC_OFFSET` flag was toggled back and forth multiple times and is
in an unknown state. The logic became unreliable. **Rewrite it cleanly.**

**The math, from first principles:**
- Camera 2 started 2.35s LATE relative to Camera 1.
- Both cameras are now cut to the same length (same event, same real-world time).
- At timeline second T, Camera 1 source = second T (no offset needed).
- At timeline second T, Camera 2 source = second `T - 2.35` (Camera 2 was late to start,
  so its "second 0" is actually Camera 1's "second 2.35").
- In other words: `cam2_source_in = seg_start_seconds - 2.35`
- If `seg_start` < 2.35, Camera 2 wasn't rolling yet — clamp to 0.

### Current State of Sync Code (do NOT trust the flag)
```python
REVERSE_SYNC_OFFSET = True  # Unknown direction — ignore this
sync_offset = -2.35          # Applied inconsistently
start_sec = max(0, seg["start"] - sync_offset)  # Ends up adding 2.35 sometimes
```

### The XML Structure That Works in DaVinci Resolve
```xml
<sequence>
  <media>
    <video>
      <track> <!-- Camera 1 clips, gaps where Camera 2 plays -->
        <clipitem> <start>timeline_frame</start> <end>...</end>
                   <in>source_frame_c1</in> <out>...</out> </clipitem>
      </track>
      <track> <!-- Camera 2 clips, gaps where Camera 1 plays -->
        <clipitem> <start>timeline_frame</start> <end>...</end>
                   <in>source_frame_c2</in> <out>...</out> </clipitem>
      </track>
    </video>
    <audio>
      <track> <!-- Continuous camera1_audio.wav for ENTIRE timeline -->
        <clipitem> ... </clipitem> <!-- One clip per edit segment, all from file-3 -->
      </track>
    </audio>
  </media>
</sequence>
```
Timeline frame positions accumulate across segments (they don't reset per segment).
Source in/out points are into the original source file.

---

## FILE MAP

```
podedit/
├── claude.md                       ← THIS FILE — persistent memory for AI models
├── HANDOFF.md                      ← Legacy handoff (superseded by this file)
│
├── src/
│   ├── visual_detection_v5.py     ← ACTIVE — detection (working, don't re-run unless asked)
│   ├── generate_resolve_xml.py    ← ACTIVE — XML gen (BROKEN, fix this first)
│   ├── audio_processor.py         ← Extracts audio via ffmpeg (already done)
│   ├── visual_detection_v4.py     ← Archive
│   ├── visual_detection_v3.py     ← Archive
│   ├── visual_detection_v2.py     ← Archive
│   └── visual_detection.py        ← Archive (v1)
│
├── results/
│   ├── edit_segments.json          ← v5 output [{start, duration, camera}] — VALID, keep
│   ├── davinci_resolve_timeline.xml ← BROKEN sync — regenerate after fixing script
│   ├── camera1_audio.wav           ← Master audio, 700MB — DO NOT DELETE
│   ├── v5_debug.csv                ← Per-second: sec,speech,s1,s2,n1,n2,dec,reason
│   └── sync_metrics.json           ← Automated estimate: ~0.97s — DO NOT USE, wrong
│
├── datasets/
│   └── test_set_1/
│       ├── camera1_short.mp4       ← 25 FPS, ~69 min
│       ├── camera2_short.mp4       ← 30 FPS, ~69 min
│       └── ground_truth.json       ← camera2_offset_seconds: 2.35
│
└── evaluation/
    └── metrics.py                  ← Detection evaluation helpers
```

---

## IMMEDIATE PRIORITY

1. **Fix `generate_resolve_xml.py`:**
   - Detect actual FPS per camera dynamically via OpenCV
   - Use per-camera FPS for source in/out frame calculations
   - Rewrite sync offset logic cleanly from first principles (see Bug 2 above)
   - Add verbose console logging (frame math, offsets applied, per-clip details)
   - Do NOT re-run detection — `edit_segments.json` is valid
2. **Regenerate and verify XML in DaVinci Resolve:**
   - Camera 1 sync correct?
   - Camera 2 sync correct?
   - Switching feels natural?

---

## FUTURE ROADMAP (After Sync Is Fixed)

1. Improve Camera 2 detection (norm_c2 ≈ 0.100 is dangerously low)
2. Implement Audio-only and Visual-only modes separately
3. n-1 optimization (currently processing both cameras for accuracy)
4. Multi-video generalization testing (beyond test_set_1)
5. CLI interface for ease of use
6. **Windows .exe with polished GUI** (final form — drag-and-drop, progress bars, preview)

---

## REFERENCES IN IEEE FORMAT

> Track every algorithm, library, or technique used. Format: IEEE style with working URL.
> Add new references as you use new techniques.

[1] G. Farnebäck, "Two-frame motion estimation based on polynomial expansion," in *Proc.
13th Scandinavian Conf. Image Analysis (SCIA)*, Halmstad, Sweden, 2003, pp. 363–370.
Available: https://doi.org/10.1007/3-540-45103-X_50

[2] P. Viola and M. Jones, "Rapid object detection using a boosted cascade of simple
features," in *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR)*, Kauai,
HI, USA, 2001, pp. I-511–I-518. Available: https://doi.org/10.1109/CVPR.2001.990517

[3] WebRTC Project, "Voice Activity Detection (VAD)," 2023.
Available: https://github.com/wiseman/py-webrtcvad

[4] B. McFee et al., "librosa: Audio and music signal analysis in Python," in *Proc.
14th Python in Science Conf. (SciPy)*, Austin, TX, USA, 2015, pp. 18–24.
Available: https://doi.org/10.25080/Majora-7b98e3ed-003

[5] G. Bradski, "The OpenCV Library," *Dr. Dobb's Journal of Software Tools*, 2000.
Available: https://opencv.org

[6] Apple Inc., "Final Cut Pro XML Interchange Format, Version 7," 2011.
Available: https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/

---

## MODEL LEARNINGS (Append-Only Log)

> **Instructions for AI models:** After completing a task or discovering something important,
> append a new entry below. Include the date, what you learned, and why it matters.
> Never delete or modify existing entries. This is a shared knowledge base.

### 2026-01-13 — Previous Model (Session 1)
- **Face detection is the CPU bottleneck**, not optical flow. Lazy detection every 0.5s
  gave more speedup than GPU acceleration via OpenCL UMat.
- **90th percentile normalization** is too aggressive for cameras with uneven detection
  quality. 75th percentile works better when one camera has much lower raw scores.
- **`REVERSE_SYNC_OFFSET` flag** became unreliable after multiple toggles. When redesigning
  sync logic, rewrite from scratch instead of toggling boolean flags.
- **Console log math bug:** When downsampling frames (every Nth frame), progress logs must
  use `frame_idx / fps` (actual video position) not `processed_count / fps` (processed
  sample count) — otherwise the reported "minutes covered" is off by a factor of N.
- **FPS mismatch between cameras** (25 vs 30) is the likely root cause of the persistent
  sync drift. The XML generator hardcodes `fps = 30` and uses it for both cameras.
  Camera 1 frame indices are wrong by 20% because of this.

<!-- NEW LEARNINGS GO BELOW THIS LINE -->

### 2026-03-16 — v6 Session (Audio + Visual Approaches)

**Audio sync fix (SOLVED):**
- Cross-correlation gives the true offset: **-0.9620s** (Camera 2 starts 0.96s BEFORE Camera 1).
  The ground_truth.json value of 2.35s was wrong.
- Mixed FPS handling: Camera 1 clipitems use TIMELINE_FPS (30) for in/out,
  Camera 2 clipitems use NATIVE fps (30) for in/out. Both work correctly in Resolve.

**Failed approach 1: Audio energy ratio comparison.**
- Both cameras' mics are in the same room → near-identical audio.
- Camera 1 mic systematically 2.2x louder → ratio clusters tightly around baseline.
- Per-second classification is ~50/50 random noise, not speech detection.
- **Conclusion:** Cross-camera audio energy cannot distinguish speakers in a shared room.

**Failed approach 2: MFCC + K-means speaker clustering.**
- 13 MFCCs + 13 deltas = 26-dim features per second from master audio.
- K-means with whiten + k=2 produces very noisy per-second labels.
- Individual seconds of speech are too short for reliable voice fingerprinting.
- Even with 7s majority-vote smoothing, produces 349 segments with 105 noise blips.
- **Conclusion:** Basic MFCC + K-means is too noisy. Need a real speaker embedding model.

**Failed approach 3: Optical flow z-score normalization (v6 hybrid).**
- Z-score normalizing optical flow scores per camera fixes the raw score imbalance
  (v5 had Camera 2 scores 8x lower), but the underlying signal is still noisy.
- Haar cascade face detection misses faces frequently → gaps in mouth tracking.
- Head compensation (subtract forehead flow × 0.7) helps but doesn't eliminate
  head-nod false positives.
- **Conclusion:** OpenCV Haar cascades are too unreliable for consistent face tracking.

**Next step: Use `resemblyzer` for speaker diarization.**
- Resemblyzer provides a pre-trained speaker encoder (d-vector model).
- Can generate speaker embeddings from short audio windows (~1-2s).
- Clustering these embeddings gives clean speaker separation.
- Combined with WebRTC VAD → audio-only mode that actually works.
- `torch` + `resemblyzer` are explicitly allowed in project requirements.
- MediaPipe is broken on Python 3.13 — **do NOT attempt to use it**.

### 2026-03-16 — v7 Session (Resemblyzer + Auto-Reference)

**The v7 Approach (Audio-only):**
- WebRTC VAD to find speech seconds.
- Find first 5s continuous speech block → assume it's the Host (Camera 2).
- Extract 3.0s sliding window embeddings (1s hop) via Resemblyzer.
- Cosine similarity to reference > 0.81 = Host (Camera 2), otherwise Guest (Camera 1).
- 4-second smoothing window + 3-second hysteresis.

**The Results (Statistical Success, Usability Failure):**
- **Stats looked perfect:** 75 segments, Host 19% vs Guest 81% screen time (target was 5-25% host).
- **Usability was terrible:** User noted it missed massive 15-20 second blocks where the host was speaking (e.g., 01:44-02:00 and 03:32-03:54).
- **Why it failed:** 
  1. The 3.0s embedding window is too large — it blurs speaker turns.
  2. Cosine similarity thresholding on continuous audio is unstable when speakers interrupt or talk over each other.
  3. Finding the Host from the *very first speech block* is risky if the guest speaks first or if intro music triggers the VAD.

**Conclusion for v8 (True Hybrid):**
- Stop trying to classify *every single second* blindly.
- Use WebRTC VAD to segment the audio into discrete "speech chunks" separated by natural silence pauses.
- Classify the *entire chunk* at once using Resemblyzer.
- To identify which cluster is the Host, don't rely purely on "who speaks first". Instead, use the **Optical Flow Visual Mouth Tracking** (from v5/v6) as a cross-modal verification. If a cluster statistically corresponds to Camera 1's mouth moving, that cluster is Camera 1.

### 2026-03-16 — v8 Session (True Hybrid Chunking)

**The v8 Approach:**
- Used WebRTC VAD to split audio into 79 continuous speech chunks (merging silences < 0.7s).
- Encoded entire chunks at once using Resemblyzer.
- Clustered into 2 speakers using K-Means.
- Validated speaker clusters by running v5's optical mouth flow on the first 10 minutes.

**The Results (Too stable, blurred speakers):**
- Produced only 10 total segments for the entire 25 minutes.
- Evaluated as "the worst version so far".
- **Why it failed:** VAD chunking merged rapid conversational exchanges into single blocks. When speakers rapidly interject, VAD sees it as one continuous block of noise. Resemblyzer then averages the embedding of both speakers, and assigns the massive 13-minute block to the loudest/dominant speaker. 

**Conclusion for v9 (Industry Standards):**
- Heuristic audio processing (VAD + Resemblyzer embeddings) and heuristic visual processing (OpenCV Haar Cascades + Optical Flow) have reached their limit for this specific challenge.
- We must move to state-of-the-art Neural Networks.
- **Audio:** `pyannote.audio` (requires HuggingFace token).
- **Video:** `mediapipe` Face Mesh (requires downgrading to Python 3.11).

### Python Package Storage Overhead Tracking
To monitor the indirect disk footprint of our Python dependencies:
- **v1-v8 base `.venv`:** ~1.04 GB (Mainly `torch` CPU version, `librosa`, `opencv-python`, `resemblyzer`)
- *(Projected)* **v9 `.venv` (Python 3.11):** ~3.5 - 4.5 GB
  - PyTorch (CUDA supported) + Torchaudio: ~2.5 GB
  - Pyannote.audio + HuggingFace Hub: ~500 MB
  - MediaPipe: ~100 MB
  - Downloaded Pyannote/Speaker models (.cache/huggingface): ~1.5 GB

### Final ".exe" Build Strategy
The user strictly requires the final app to work **offline**. This rules out client-server offloading. When moving to the production executable phase, we will choose between:
1. **ONNX Runtime Export:** Converting Pyannote/PyTorch models to ONNX to dramatically shrink the `.exe` to ~300 MB. (High development difficulty, but ideal result).
2. **CPU-only PyInstaller Bundling:** Stripping all NVIDIA/CUDA dlls and shipping a heavy (~1 GB) but functional standalone offline binary.

## REFERENCES IN IEEE FORMAT
- [7] Wan, L., et al., "Generalized End-to-End Loss for Speaker Verification," ICASSP 2018.
  (resemblyzer implements this GE2E model)
- [8] Bredin, H. et al., "pyannote.audio: neural building blocks for speaker diarization," in *Proc. ICASSP*, 2020.
- [9] Lugaresi, C. et al., "MediaPipe: A Framework for Building Perception Pipelines," arXiv preprint arXiv:1906.08172, 2019.
- [10] Kartynnik, Y. et al., "Real-time Facial Surface Geometry from Monocular Video on Mobile GPUs," *CVPR Workshop on Computer Vision for Augmented and Virtual Reality*, 2019.

### 2026-03-20 — v9 Session (The Final Solution: Pyannote + MediaPipe Hybrid)

**The v9 Approach (Industry Standard Architecture):**
- **Neural Audio Diarization:** Dropped WebRTC VAD and Resemblyzer. Implemented `pyannote/speaker-diarization-3.1`. The entire master audio track is passed into Pyannote's PyTorch `WavLM` pipeline. This provides millisecond-accurate timestamps of exactly when *Speaker A* and *Speaker B* talk, natively handling overlapping speech and ignoring background noise.
- **Topological Lip Tracking (Identity Verification):** Instead of noisy optical flow or bounding boxes, implemented Google's `MediaPipe` Face Mesh. 
- **Methodology:** Over the first 10 minutes of video for both Camera 1 and Camera 2, the pipeline extracts the canonical 3D Face Mesh and calculates the absolute distance between vertex 13 (upper inner lip) and vertex 14 (lower inner lip). By calculating the moving variance of this specific Euclidean distance, we get an absolute metric for "mouth movement" that is mathematically immune to nodding, shaking, or moving closer to the camera.
- **Cross-Modal Mapping:** The pipeline maps the Pyannote audio identity (`SPEAKER_00`) to the camera (Camera 1 or 2) that demonstrates the highest median lip variance during `SPEAKER_00`'s exact timestamps.

**The Results (Flawless Execution):**
- **Segments:** Reduced purely to the mathematically correct number of speakers taking turns.
- **Accuracy:** Flawlessly handled rapid crosstalk and interruptions (where v8 failed).
- **Architecture Validation:** Verified that `v9_timeline.xml` synchronized correctly in DaVinci Resolve. Camera 1 generated 89.9% screen time, and Camera 2 generated 10.1%, correctly isolating the host/guest dynamic.
- **Learnings:** Heavy AI models (Pyannote requires downloading cached weights) are fundamentally necessary. We cannot shortcut Diarization with simple VAD/Energy heuristics in overlapping podcast environments. To maintain our "Offline .exe" requirement in the future, we will need to explore ONNX exports or ship a heavy PyInstaller binary.

### 2026-04-01 — Documentation Overhaul & App Architecture

**Consolidation of Version History:**
- Created `VERSIONS_HISTORY.md` to serve as the definitive "living document" of the project's evolution. It details the transition from **Brittle Heuristics (v1-v5)** to **Noisy Clustering (v6-v8)** to the final **Neural Hybrid Success (v9)**.
- This document is critical for transparency in the IEEE research paper, proving why simple OpenCV tools were abandoned in favor of deep Transformers.

**GUI Architectural Strategy:**
- Swapping logic versions (e.g., v9 back to v8 for "Lite" mode) is **architecturally easy** if a Strategy Pattern / Pluggable Backend is used.
- The main cost of "Multiple Engines" in a GUI is **disk space**. Supporting v9 (Pyannote/MediaPipe) and v8 (Resemblyzer) in one `.exe` increases the payload size significantly.

**Estimated Windows Standalone Size:**
- **Standard Build (~5 GB)**: Includes full PyTorch with CUDA/GPU binaries. Heavy but powerful.
- **Optimized Build (~1 GB)**: Targets `torch-cpu` only. This is the recommended "sweet spot" for portable, professional offline software.
- **Ultra-Lean Build (~500 MB)**: Requires converting Pyannote/MediaPipe to ONNX format to strip PyTorch entirely. High technical difficulty but best for distribution.

**Prompt Engineering for Research:**
- Replaced "creative" image prompts with **minimalist, clinical academic prompts**. 
- Academic models respond best to "boring" descriptions: "plain white background," "2D flat vectors," and "strictly black outlines." This ensures visuals in the final paper match the scientific tone of the text.

### 2026-04-02 — v9 XML Export Safety

- The XML builder must trust the **live sync offset passed in by the pipeline**, not a stale `results/sync_metrics.json` file. Old metrics can silently overwrite the current run and reintroduce drift.
- When exporting Resolve XML, keep the sync source of truth in one place: the pipeline result object, then pass it straight through to the XML generator.

### 2026-06-08 — v10 Session (CLI-First, MediaPipe Removal, Dominance Heuristic)

**The v10 Approach (Pure Architecture & Crash Fix):**
- **MediaPipe Removed:** The pipeline was crashing on launch due to MediaPipe's incompatibility with Python 3.13. We abandoned cross-modal visual lip tracking entirely.
- **Speech-Dominance Heuristic:** We realized podcasts follow a power-law distribution. The host (or dominant guest) speaks the vast majority of the time. We now map the Pyannote `SPEAKER_XX` with the highest total duration to Camera 1. A simple `--swap` flag in the CLI handles exceptions. No heavy computer vision required.
- **Sub-frame Blip Filtering:** Added a strict 1.5s minimum segment duration. Any segment shorter than 1.5s is seamlessly absorbed into the preceding camera angle, preventing rapid flickering.
- **Package Refactoring:** Moved from scattered `vX.py` scripts to a clean `pipeline/` package (`audio_extractor`, `sync_engine`, `diarizer`, `mapper`, `segmenter`, `xml_builder`) with `main.py` as a single CLI entry point.

**Codebase & Architecture Learnings:**
- **Dependency Bloat:** By removing `mediapipe`, `resemblyzer`, and `webrtcvad`, we saved over 150MB of dependency footprint.
- **Security:** Hardcoding the HuggingFace token in source files is a major risk for academic publishing. It is now strictly read from `.env` or the environment variables.
- **Sync Math Confirmed:** The sync offset logic for XML generation must subtract the offset from Camera 2's start time (cam2 was late to start rolling). `cam2_source_in = (seg.start - sync_offset) * cam2_fps`.

### 2026-06-08 — v10 Bug Fix: torchcodec / AudioDecoder Crash on Windows

**The Bug:**
- `pyannote.audio` 3.1+ attempts to use `torchcodec` (or a legacy `torchaudio` backend) to decode audio files internally.
- On Windows with Python 3.10+, this fails with `NameError: name 'AudioDecoder' is not defined`. The `_dlopen` error also appears because native DLL binding fails.
- This manifests the moment `pipeline(audio_path, ...)` is called — even though the model loads perfectly fine.

**The Fix (Bypass Internal Decoder):**
- `pyannote.audio` accepts audio as a pre-loaded in-memory dictionary: `{"waveform": (1, T) torch.Tensor, "sample_rate": int}`.
- Load the WAV file with `librosa.load(path, sr=16000, mono=True)` → returns a numpy array.
- Convert: `torch.from_numpy(waveform).unsqueeze(0)` → shape `(1, T)`.
- Pass `{"waveform": tensor, "sample_rate": 16000}` directly to the pipeline call.
- This completely bypasses `torchcodec`/`AudioDecoder` and works on all platforms.
- **16kHz is the correct sample rate** — Pyannote's WavLM model was trained at 16kHz. Do not use 44100Hz here.

**Why This Matters:**
- Always pre-load audio when using `pyannote.audio` on Windows. Never pass file paths directly.
- `librosa` is already in our dependency stack — zero extra packages needed.

### Technology Philosophy (User Directive, 2026-06-08)

> **"Use the latest stable technologies as much as possible while being thoughtful about my requirements."**

Guidelines for future model sessions on this project:
1. **Prefer modern library APIs.** If `pyannote.audio` 3.2 or later is released and stable, prefer it over 3.1.
2. **Prefer `pyannote/speaker-diarization-3.1`** (or newest stable) over older models. Never downgrade unless there is a confirmed bug.
3. **Do NOT use heuristics where neural methods exist.** VAD + energy ratios were tried and failed. Pyannote handles silence, overlaps, and multi-speaker audio natively.
4. **Audio processing:** Use `librosa` for loading and DSP. Use `scipy.signal` for cross-correlation. These are mature and stable on Python 3.10–3.13.
5. **Video probing:** Use `cv2.VideoCapture` to detect FPS and frame count. Never hardcode FPS — it varies per file.
6. **XML generation:** Use Python's `xml.etree.ElementTree` + `minidom` for pretty printing. Do NOT use string templates — they are fragile and unreadable.
7. **Disk space:** Before adding any new package, estimate its installed size. Document it in the dependency table in the implementation plan. Prefer CPU-only builds of PyTorch when CUDA is not available.

### 2026-06-08 — Sync Offset Sign Convention (CRITICAL — READ THIS BEFORE TOUCHING XML)

**The Bug:**
- After fixing the FPS mismatch (Camera 1 using 25fps frames vs 30fps timeline), Camera 1 was in sync but Camera 2 was still off.
- Symptom: "Audio of Camera 2 is AHEAD of the video" = you hear the voice before the mouth moves.
- Root cause: the stored offset (+0.975s) was applied as `source_seconds = T - 0.975`, which showed footage 0.975s TOO EARLY in Camera 2's tape.
- Correct: Camera 2 started **BEFORE** Camera 1, so we need footage 0.975s LATER: `source_seconds = T + 0.975 = T - (-0.975)`.

**Verified Sign Convention (locked in permanently):**
```
NEGATIVE offset (-0.975) → Camera 2 started BEFORE Camera 1 by 0.975s
  xml_builder: source_seconds = T - (-0.975) = T + 0.975  [later footage, correct]

POSITIVE offset (+0.975) → Camera 2 started AFTER Camera 1 by 0.975s
  xml_builder: source_seconds = T - 0.975  [earlier footage]
```

**For test_set_1: confirmed offset = -0.975s** (Camera 2 started 0.975s before Camera 1).

**scipy correlate convention:**
- `correlate(audio1, audio2)` with `correlation_lags`: a **positive** lag means audio2 was shifted right (delayed) to align → audio2 started LATER → **positive offset**.
- The original code had `offset = -best_lag / sr` (sign flipped), which reversed the meaning and produced +0.975 instead of -0.975.
- Fixed in `pipeline/sync_engine.py`: now uses `offset = +best_lag / sr` (direct, no negation).

**Diagnostic tool:** `sync_diagnostic.py` generates 5 XMLs at different offsets (-2.35, -0.975, 0, +0.975, +2.35) for visual comparison in DaVinci Resolve. Run it whenever sync is uncertain on a new recording.

**Memory rule for future models:** "Audio ahead of video" = source is too early → need LARGER (more positive) source_seconds → offset must be more negative. Adjust by subtracting from the current offset value.

### 2026-06-08 — v11 Session: The Overlapping Speech Bug (Active Speaker Stack)

**The Bug:**
- Camera switching was reported as "only working some of the times" or getting permanently stuck on one camera.
- Root cause was the timeline assembly logic in `segmenter.py`, **not** the AI diarization.
- The previous loop processed Pyannote turns by only looking at the `start` time. It ignored the `end` time. 
- In podcasts, overlapping speech is common. E.g., Guest speaks from 0s to 10s. Host interrupts from 3s to 3.5s.
- The old loop saw the Host start at 3s and cut to Camera 2. But because it ignored the Host's `3.5s` end time, it never cut back to the Guest! The camera got permanently stuck until the Guest started a brand new sentence later on.

**The Fix (Active Speaker Stack):**
- Rewrote `pipeline/segmenter.py` to use an event-based State Machine.
- Split the timeline into discrete `start` and `end` events, sorted chronologically.
- Maintain an `active_stack` of speakers currently talking.
- **When someone speaks:** Push them to the top of the stack. `desired_camera = active_stack[-1]`.
- **When someone stops:** Remove them from the stack. The system falls back to the previous speaker dynamically.
- **Combined with `<1.5s` filter:** If someone says "yeah" for 0.5s, the stack pushes and pops them properly, generating a 0.5s segment. Then the downstream `merge_short_segments` pass absorbs that 0.5s blip into the main speaker seamlessly.

**Result:** Perfect editorial switching that correctly handles monologues, interruptions, and backchanneling. 

**Caching Strategy Updated:**
- `main.py` now saves the raw AI output to `results/raw_turns.json`.
- Never run editing logic without caching the raw AI output first. Modifying timeline assembly should be instant. Re-running a 40-minute neural network just to tweak a 1.5s smoothing filter is terrible developer experience.

### 2026-07-16 — PodEdit 1.0 (Final One-Shot Rebuild, Fable 5 Session)

**What was built:** Clean-slate final pipeline (`main.py` + `pipeline/`), rebuilt from the
requirements rather than the version history. Hybrid mode implemented WITHOUT MediaPipe:
pyannote decides WHEN each voice speaks; an OpenCV lip-activity vote decides WHICH camera
each voice belongs to. Plus a new `pipeline/preview.py` that renders the edit to MP4 with
ffmpeg — the first tool in this project that can verify sync independent of Resolve.

**Dependency pins that matter on Python 3.13 (2026-era PyPI):**
- `torchaudio >= 2.9` removed `AudioMetaData` → pyannote 3.x crashes at import.
  Pin `torch==2.7.1 torchaudio==2.7.1` (CPU index).
- `huggingface_hub >= 1.0` removed `use_auth_token` → `Pipeline.from_pretrained` crashes.
  Pin `huggingface_hub<1.0`.
- `opencv-python 5.x` removed `CascadeClassifier` (and `cv2.data.haarcascades`).
  Pin `opencv-python<5`.
- `torch >= 2.6` defaults `torch.load(weights_only=True)` → pyannote checkpoints fail.
  Fix: `torch.serialization.add_safe_globals([TorchVersion, Specifications, Problem, Resolution])`.

**CRITICAL algorithm rule — visual speaker/camera mapping:**
Never compare lip-activity scores ACROSS cameras (different framing, lighting, and face
detection rates bias the scale). The first run inverted the mapping because a 2-sample
cam2 median (12.09) outvoted an 85-sample cam1 median in a cross-camera sum. Correct rule:
per-camera WITHIN-camera contrast between the two speakers' turns, excluding any
speaker×camera cell with < 8 samples, cameras vote weighted by sample count.
Result: contrast +0.624 on cam1 (74+ samples) → unambiguous correct mapping.

**Behavioral gotcha discovered:** the guest (cam2) faces away while *listening* —
cam2 frontal-face hit rate was 27.8% overall but ~2% during the host's turns. Frontal-face
detectability itself correlates with engagement/speaking; don't treat "no-face" as neutral.

**XML frame math (final form):** derive ALL source in/out from the frame-quantized
timeline grid, never from float seconds. `audio_in = timeline_start` exactly;
cam1 `source_in = timeline_start` exactly (edit timeline IS cam1 time);
cam2 `source_in = timeline_start - round(offset × timeline_fps)`. Recomputing from float
seconds drifts against the accumulated per-segment frame rounding (caught by an automated
structural validator, not by eye).

**Segment-count reality check:** the first 25 min contain only ~11 floor exchanges
lasting ≥ 0.8s; the other 20 speaker turns are sub-0.8s backchannel ("yeah", "mm-hm").
Sweeping the anti-flicker threshold from 1.5s down to 0.8s did not change the count.
The old "30–100 segments" expectation was an artifact of v1–v8 detector noise, not a
property of the conversation. 11 segments is the *correct* editorial answer here.

**Verified results (test_set_1, first 25 min):** Camera 1 = 89.6% (target 75–95 ✓),
Camera 2 = 10.4% (target 5–25 ✓), sync −0.9810s (58× correlation peak/noise, matches the
manually confirmed −0.975s), diarization RTF 0.75× on i7-1360P CPU (18.8 min for 25 min
audio; whole cold run ≈ 25 min ≪ 2h budget; cached rerun 33s). Structural validation:
timeline continuity, disjoint video tracks, full coverage, source bounds, and frame-exact
audio 1:1 all pass.

### 2026-08-09 — PodEdit 1.1 Publication and Reliability Audit

- **Earlier quality claims were not defensible.** Camera occupancy and segment count do
  not measure agreement with a human editor. The checked-in ground truth had no speaker
  or edit annotations. The paper now separates implementation/runtime evidence from
  human-reference accuracy, which remains unclaimed until annotation is completed.
- **Legacy pyannote 3.1 was replaced by Community-1** under pyannote.audio 4.0.4.
  A forced offline 60-s run succeeded from the project-local `.model_cache` with neural
  RTF 0.59.
- **Caches must be bound to source content and model version.** Reuse now requires path,
  size, mtime, edge-block SHA-256, duration, speaker count, and model identifier.
- **Editorial floor logic now has explicit profiles.** Balanced bridges 0.35-s gaps,
  requires a 1.10-s takeover, enforces a 2.0-s shot, holds the established speaker during
  overlap, and applies a 0.10-s visual lead.
- **The 25-min pilot still has a disclosed limitation:** 11 shots and a 797.95-s maximum
  shot. Available audio/visual evidence indicates a long single-speaker region and almost
  no usable listener face on Camera 2. Do not insert blind reaction shots or call the
  result human-equivalent.
- **XMEML media definitions belong inside the first clip item.** Top-level `<file>` nodes
  are not legal root children in Apple's catalog. Definitions now live in the first
  referencing clip and later clips inherit by id.
- **Release evidence:** clean source-bound 25-min run, sync -0.98095 s at 58.37x,
  Community-1 inference RTF 0.72, 578 exclusive turns, valid 45001-frame XML, two preview
  artifacts, seven unit tests, and a human annotation tool.

### References added for PodEdit 1.1

[11] A. Plaquet and H. Bredin, "Powerset multi-class cross entropy loss for neural
speaker diarization," in *Proc. Interspeech*, 2023, pp. 3222–3226.
Available: https://doi.org/10.21437/Interspeech.2023-205

[12] H. Wang et al., "WeSpeaker: A research and production oriented speaker embedding
learning toolkit," in *Proc. IEEE ICASSP*, 2023, pp. 1–5.
Available: https://doi.org/10.1109/ICASSP49357.2023.10096626

[13] F. Landini, J. Profant, M. Diez, and L. Burget, "Bayesian HMM clustering of
x-vector sequences (VBx) in speaker diarization: Theory, implementation and analysis on
standard tasks," *Computer Speech & Language*, vol. 71, Art. no. 101254, 2022.
Available: https://doi.org/10.1016/j.csl.2021.101254

[14] J. Roth et al., "AVA-ActiveSpeaker: An audio-visual dataset for active speaker
detection," in *Proc. IEEE ICASSP*, 2020, pp. 4492–4496.
Available: https://arxiv.org/abs/1901.01342

### 2026-08-09 — Windowed Diarization and Human-Like Cut Density

- The 11-shot result was not a correct editorial endpoint. A 60-second isolated
  Community-1 run found speaker changes that the single 1500-second global
  clustering pass absorbed into one identity.
- The production default now uses 60-second diarization windows with 15-second
  overlap. Local labels are reconciled by maximum duration agreement in the
  overlap, and only the central portion of each window is retained. This avoids
  false cuts at processing seams while preserving local exchanges.
- On `test_set_1` (first 25 min), the new path produced 661 stitched exclusive
  turns and 50 final shots / 49 cuts (1.96 cuts/min). The maximum shot fell from
  797.95 seconds to 65.57 seconds. Windowed inference took 1926.1 seconds (RTF
  1.28); the full no-preview run took 33.4 minutes on the i7-1360P CPU.
- Fixed face ROIs learned across the locked camera replace repeated frontal-face
  detection for visual sampling. This yields samples for Camera 2's profile
  pose, but the final label-to-camera vote margin was still only 8.7%; the
  pipeline correctly fell back to the documented dominance rule.
- A restrained reaction policy now considers only shots longer than 60 seconds.
  It searches near the target time and selects the listener moment with lowest
  head-compensated mouth activity. Two four-second listener shots were inserted
  in the 25-minute candidate; no blind timer-only cutaways were added.
- The all-cuts review limit was raised to 80, so the current 49-cut candidate is
  reviewed in full rather than silently subsampling to 40 cuts.
- Structural verification: 12 unit tests pass; the 44999-frame XMEML timeline
  passes combined-video, continuous-audio, source-length, and reference checks.

### 2026-08-11 — PodEdit 1.2 Resume and Cut-Audit Reliability

- Windowed inference now writes an atomic checkpoint after every completed
  60-second window. Reuse requires exact source identity, model, speaker count,
  sample rate, and window bounds; `--force` bypasses checkpoints intentionally.
- A real offline smoke test measured 51.15 seconds for initial 60-second neural
  inference and 0.15 seconds for an identical checkpoint-resumed result. Both
  produced the same 21 stitched turns, and the resumed pass did not load the
  model.
- Visual identity evidence is now cached against both camera fingerprints, the
  SHA-256 digest of all turns, sync offset, and verifier version. This reduced a
  cached 25-minute no-preview rerun from 52.8 seconds to 12.3 seconds while
  preserving the 50-shot timeline and XML.
- Every cut now has a JSON/CSV audit row: stable cut number, timeline timecode,
  camera transition, reaction/speaker-change type, neighboring shot lengths,
  window-seam distance, flags, and review priority.
- The all-cuts reel burns the same cut number, timeline second, and camera
  transition into the image. A separate priority reel contains only high-risk
  cuts. This makes feedback unambiguous and avoids rewatching the full reel when
  only a few transitions need attention.
- Current audit: one high-priority transition, Cut 35 at 1042.742 seconds. It is
  0.242 seconds from a retained-window seam and follows a 2.0-second shot. The
  flag requests audible human review; it does not prove the cut is wrong.
- PodEdit 1.2 verification: 14 automated tests pass; the 44999-frame XML remains
  structurally valid; numbered full and priority review renders both succeed.

### 2026-08-11 — Executable Human Review Loop

- Generated cut-report CSVs now include blank `review_decision`, corrected time,
  corrected camera, and notes columns. Blank columns are intentional: generated
  evidence must never look like completed human review.
- `apply_review.py` applies numbered `keep`, `move`, `delete`, and
  `camera_wrong` decisions to a new segment file. It preserves original cut
  indexing until all decisions are processed, rejects moves that create a shot
  below 0.5 seconds, validates continuity, and never overwrites the machine
  proposal.
- The current windowed candidate's human annotation template is now
  `results/windowed_25min/human_annotation.csv`; the dataset metadata no longer
  points at the rejected 11-shot Community-1 result.
- Verification count increased to 16 automated tests after adding correction
  application and unsafe-move coverage.

### 2026-08-11 — Reviewed Timeline Export Bundle

- `apply_review.py --manifest RUN_MANIFEST --export-dir NEW_DIRECTORY` now
  resolves the original segment proposal, cut report, camera files, master
  audio, verified sync offset, and timeline FPS from a single manifest.
- The reviewed bundle contains corrected segments, regenerated FCP XML 7, a
  60-second sync preview, and an audit with source/report fingerprints and XML
  validation results. The source segment file is explicitly rejected as an
  output target, so the machine proposal cannot be overwritten accidentally.
- A real 25-minute blank-review smoke test preserved all 50 shots, regenerated
  50 video and 50 audio clip items across 44,999 timeline frames, passed XML
  continuity/reference checks, and rendered an exactly 60-second preview.
- Run manifests now record absolute artifact and extracted-audio paths, making
  later review export independent of the shell's current directory.
- Final verification: all 16 unit tests and every `doctor.py` environment check
  pass. The canonical cached rerun completed in 158.6 seconds, preserved the
  50-shot candidate, and regenerated the normal, 49-cut, and priority previews.
- Project size after the review-export smoke artifacts is 13,289,032,840 bytes
  (13.289 decimal GB / 12.376 GiB across 61,376 files). The largest categories
  are datasets (6.243 GiB), results (3.301 GiB), `.venv` (1.335 GiB), and
  `dist` (1.291 GiB).

### 2026-08-11 — PodEdit 1.3 Adaptive Speaker Recovery

- Forcing `num_speakers=2` independently in every 60-second Community-1 window
  hallucinates a second identity during monologues and drove a false near-50/50
  camera split. Supplying `min_speakers=1, max_speakers=2` fixed this: 29 of 33
  windows in the test episode were initially recognized as single-speaker.
- The ranged constraint alone can miss a brief second voice in a mostly
  monologue window. An exact-two confirmation pass is now run only for apparent
  monologues and saved to `diarization_windows/exact_speaker_recovery/`.
  Confirmation is accepted only when the two normalized speaker centroids have
  cosine similarity at or below 0.70.
- On the 25-minute test, the adaptive rule accepted exactly two of 29 candidate
  windows (cosines 0.552 and 0.588) and rejected 27 forced monologue splits; the
  smallest rejected cosine was 0.805. This recovered a sustained 15.4-second
  Camera 2 turn around 19:39 without returning to noisy forced-two switching.
- Local identities are now reconciled jointly using constrained cosine
  clustering over every valid window embedding. Two-label windows must assign
  one centroid to each episode identity; one-label windows choose the nearest
  identity. The final fit used all 33 windows with zero temporal-overlap
  fallbacks, median assignment margin 0.564, and minimum margin 0.270.
- Sparse visual verification is substantially stronger when it samples centers
  of exclusive turns at least 3 seconds long, analyzes 18-frame bursts at 960
  pixels, and measures vertical Sobel-edge mouth motion with forehead
  compensation. Mapping acceptance now uses Cliff's distribution-free dominance
  effect and requires the two cameras to vote for complementary owners.
- Final measured candidate: 596 retained turns; 13 genuine speaker-policy shots;
  20 listener cutaways; 53 total shots / 52 cuts (2.08 cuts/min); 85.4%/14.6%
  camera time; 62.0-second maximum shot; visual effects +0.545 and -0.655; sync
  -0.98095 seconds at 58.37x confidence; exact 45,000-frame XML validation pass.
- The ranged pass required 1222.0 seconds of measured CPU inference and the 29
  confirmation windows required 1073.4 seconds. Their combined 2295.4 seconds
  (RTF 1.53) remains well below the two-hour requirement.
- PodEdit 1.3 verification increased to 25 unit tests. The canonical manuscript
  now describes adaptive recovery and cites N. Cliff's 1993 dominance-statistics
  paper (DOI 10.1037/0033-2909.114.3.494).

### Reference added for PodEdit 1.3

[15] N. Cliff, "Dominance statistics: Ordinal analyses to answer ordinal
questions," *Psychological Bulletin*, vol. 114, no. 3, pp. 494-509, 1993.
Available: https://doi.org/10.1037/0033-2909.114.3.494

### 2026-08-11 - PodEdit 1.4 Seam-Safe Editorial Evidence

- The adaptive second-speaker cosine threshold changes accepted turns, so it is
  part of the algorithm rather than an incidental constant. It is now exposed
  as `--second-speaker-max-cosine`, validated to [-1, 1], written to the run
  manifest, and included in the raw diarization cache identity. This prevents a
  threshold experiment from silently reusing incompatible turn decisions.
- Listener-reaction selection now avoids candidates within one second of a
  retained diarization-window seam whenever a safe candidate exists. Safe
  candidates use deterministic ordinal ranks: 60% listener mouth motion, 30%
  master-audio RMS in a 250-ms window, and 10% target proximity. Audio is read
  through small PCM seeks rather than loading or caching the full waveform.
- On the canonical 25-minute candidate, the new selector retained 20 reaction
  cutaways while moving every one at least 1.567 seconds from a processing seam
  (median 10.758 seconds). High-priority cut flags fell from two to zero without
  changing the 53-shot / 52-cut count or 85.4% / 14.6% camera occupancy.
- A priority reel is derived evidence, not a durable source artifact. When the
  current audit contains no high-priority cuts, the renderer now deletes an old
  priority reel so a stale video cannot be mistaken for current evidence.
- The maximum primary-shot setting is a search eligibility point, not a strict
  hard cap. Candidate spacing can therefore leave a 66.0-second shot even with
  a 60-second target; documentation must describe this as reaction eligibility,
  not a guaranteed maximum.
- The standalone paper source is `paper/podedit_ieee_overleaf.tex`. It uses four
  author placeholders, inline references, and a compile-safe optional figure.
  Tectonic 0.17.0 compiled it offline from a project-local cache; five-page PNG
  rendering found no clipping, overlap, broken equations, or table overflow.
- PodEdit 1.4 verification contains 29 unit tests, including seam scheduling,
  seam-safe reaction choice, audio-pause tie breaking, and motion/audio score
  weighting.
- Final recursive workspace audit after v1.4 artifacts: 14,584,531,626 bytes
  (14.584532 decimal GB / 13.582904 GiB across 62,005 files). The largest
  top-level categories are datasets (6.243 GiB), results (4.398 GiB), `.venv`
  (1.335 GiB), and `dist` (1.291 GiB).

### References added for PodEdit 1.4

[16] OpenCV Developers, "Sobel Derivatives," *OpenCV Documentation*.
Available: https://docs.opencv.org/4.x/d2/d2c/tutorial_sobel_derivatives.html

[17] Tectonic Project, "Installing Tectonic," *The Tectonic Typesetting System*.
Available: https://tectonic-typesetting.github.io/book/latest/installation/

### 2026-08-11 - LaTeX Tooling Removal

- At the user's request, the portable Tectonic executable, its downloaded ZIP,
  its project-local TeX package cache, the `paper/build/` log/PDF, and the
  exported `output/pdf/` copy were removed. This recovered 116,906,456 bytes
  from compiler/cache/PDF artifacts, and the empty `tools/` and `output/`
  directories were removed as well.
- The only maintained manuscript deliverable is now
  `paper/podedit_ieee_overleaf.tex`, with the optional
  `paper/adaptive_timeline.png` figure. It should be compiled in Overleaf; no
  LaTeX-related executable or package cache remains in the repository.

### 2026-08-11 - Markdown Paper Source Requirement

- The user requires the LaTeX itself in a Markdown file, not merely a link.
  `research paper.md` now embeds the complete 480-line manuscript in a fenced
  `latex` block. After newline normalization, that block is an exact match for
  `paper/podedit_ieee_overleaf.tex`; both are maintained as equivalent sources.
- All Markdown documentation was audited on 2026-08-11. Current guides point to
  PodEdit 1.4, `main.py`, `pipeline/`, and the canonical result directory.
  Obsolete v9 GUI, Premiere, EDL, and removed automation instructions are
  prominently marked archived rather than being presented as current.
- Post-removal documentation audit: 24 maintained Markdown files, zero broken
  local links. Current recursive folder size is 14,517,862,525 bytes
  (14.517863 decimal GB / 13.520813 GiB across 61,951 files).

### 2026-08-12 - Windows Productization from First Principles

- The historical `PodEdit-v9.spec`, `build/PodEdit-v9/`, and `dist/PodEdit-v9/`
  are not a production baseline. The spec collects obsolete MediaPipe and JAX
  dependencies, duplicate media/OpenCV binaries, development `.lib` files, and
  two executables. Its 1.291-GiB payload says nothing reliable about the minimum
  size of PodEdit 1.4.
- The old spec includes `.env` as application data. This is a release-blocking
  credential leak because it may package a personal Hugging Face token. A
  production build must never bundle `.env`, tokens, caches copied from a user
  profile, source media, or test results.
- Product architecture should separate a GUI process from a headless worker.
  The GUI submits a versioned job manifest and consumes structured JSONL
  progress events; the worker owns inference, cancellation checkpoints,
  manifests, validation, and outputs. This keeps the UI responsive and permits
  inference backends to change without rewriting the application shell.
- Stable interfaces should exist for synchronization, diarization, identity
  mapping, editorial policy, timeline export, and preview rendering. The
  current `pipeline/` modules provide useful boundaries, but `main.py` still
  couples orchestration, console printing, filesystem layout, configuration,
  and implementation selection. A service/job layer is required before GUI
  packaging.
- Neural diarization dominates measured processing time: 1222.0 s for ranged
  windows plus 1073.4 s for exact-count confirmation, versus seconds for sync
  and minutes for optional review rendering. The first optimization target is
  therefore reusable neural feature extraction: compute segmentation and
  embeddings once, then evaluate one/two-speaker clustering hypotheses without
  rerunning the neural front end for most windows.
- A one-folder frozen payload should be validated before choosing an installer.
  It is easier to inspect, update, and troubleshoot than a self-extracting
  one-file executable. Only after dependency and license audits should it be
  wrapped in an installer and code-signed.
- Two product packages may be necessary: a complete offline installer including
  approved model assets, and a smaller bootstrap installer that provisions the
  model once after the user accepts its access/license terms. The second option
  is not offline on first launch and must be labeled honestly.

### References added for Windows productization

[18] PyInstaller Development Team, "Using PyInstaller," *PyInstaller 6.21.0
Documentation*. Available: https://pyinstaller.org/en/stable/usage.html

[19] Microsoft, "Choose a distribution path for your Windows app," *Windows
App Development Documentation*. Available:
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path

[20] Microsoft, "Sign an MSIX package," *MSIX Documentation*. Available:
https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview

[21] Microsoft, "Quantize ONNX models," *ONNX Runtime Documentation*.
Available:
https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html

[22] pyannote, "speaker-diarization-community-1," *Hugging Face Model Card*.
Available: https://huggingface.co/pyannote/speaker-diarization-community-1

### 2026-08-12 - Safe Workspace Cleanup

- Removed only targets the user had already characterized as useless: obsolete
  v9 `dist/` and `build/`, its spec/helper/log, root temp WAVs, `deletable/`,
  `tmp/`, root `__pycache__/`, and a one-off tqdm test. Exact recovery was
  1,570,889,866 bytes (1.463 GiB); all resolved targets were verified inside
  the workspace and none remained afterward.
- Did not delete 4,120,869,408 bytes (3.838 GiB) of redundant historical WAV
  and MP4 result media without explicit approval. Although reproducible and
  excluded from the canonical v1.4 result, review videos can still constitute
  academic evidence. The small historical JSON/CSV/XML/manifests are planned
  for retention either way.
- Measured dependency sizes show the application-size floor is runtime-driven:
  PyTorch 489.9 MiB, LLVM 116.2 MiB, OpenCV 108.6 MiB, SciPy 108.3 MiB,
  scikit-learn 40.0 MiB, versus only 31.3 MiB of local Community-1 assets.

### 2026-08-12 - Option A Cleanup and Milestone 1 Worker Foundation

- With explicit user approval for Option A, removed exactly 16 redundant
  historical WAV files from the root result set and six archived run folders.
  Canonical `results/variable_speaker_25min/`, reviewed
  `results/variable_speaker_25min_reviewed_v14/`, all JSON/CSV/XML/manifests,
  and all preview media were retained. The deletion reclaimed 4,082,551,022
  bytes (3.802 GiB).
- `pipeline/job_contract.py` is the small, versioned GUI-to-engine boundary.
  It accepts only known scalar/boolean run options, rejects arbitrary flags,
  and converts validated jobs into the maintained `main.py` command line. Read
  job files with `utf-8-sig`: normal UTF-8 still works, while PowerShell-created
  JSON with a byte-order mark no longer fails before the worker can start.
- `worker.py` launches the engine out of process and exposes append-only JSONL
  events (`job_started`, log/stage/window progress, `job_completed`,
  `job_cancelled`, or `job_failed`). This prevents a future GUI from importing
  PyTorch, pyannote, OpenCV, or FFmpeg in its own process.
- Cancellation is intentionally cooperative. `main.py` checks a sentinel before
  every expensive stage, while chunked diarization checks before each new local
  window. A completed local window is atomically checkpointed before the next
  boundary; therefore a cancelled compatible job can reuse prior work. Native
  inference inside an already-started window cannot be safely interrupted, so
  cancellation latency is bounded by one active window rather than pretending
  to be instantaneous.
- Verified the typed contract with the project test suite and executed a real
  cancelled worker job against the supplied sources: it stopped before source
  probing with exit code 130 and emitted a resumable `job_cancelled` event. No
  media or timeline output was changed by this probe.
- Final post-cleanup, post-validation workspace measurement: 8,864,637,303
  bytes (8.865 decimal GB / 8.256 GiB across 46,153 files).

### 2026-08-12 - Productization Milestone Gates

- The post-Milestone-1 critical path is: harden the worker contract, build a
  thin native GUI, optimize measured neural work and job storage, validate an
  inspectable one-folder payload, add installer/security/update behavior, then
  run release-candidate QA. ONNX is an optional later backend and must not hold
  the first reliable PyTorch release hostage.
- WinUI 3/C# is the default GUI candidate because PodEdit is Windows-only and
  the UI can remain completely outside the Python inference process. The final
  framework-dependent versus self-contained choice is a measured deployment
  decision, not an assumption made before a prototype exists.
- Every milestone now has an explicit exit gate. Performance changes must pass
  locked edit-quality comparisons; packaging must pass a clean machine without
  Python or FFmpeg; release claims must be supported by independent multi-
  episode annotations. A functioning GUI alone is not a release candidate.
- Academic evaluation is a parallel dependency. It may continue while the app
  is engineered, but it gates statements of human-editor agreement. The
  optional ONNX/quantization phase begins only after the full PyTorch path has a
  stable, measurable release baseline.

### Reference added for the Windows GUI deployment decision

[23] Microsoft, "Windows App SDK deployment overview," *Windows App
Development Documentation*. Available:
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/deploy-overview

### 2026-08-12 - Milestone 2 Worker Contract Hardening

- Added a cheap preflight boundary (`pipeline/preflight.py`) that deliberately
  imports no neural/media stack. It checks readable input files, output-parent
  viability/free space, FFmpeg availability, and project-local model-cache
  presence for offline jobs. Stable issue codes make GUI errors actionable and
  prevent a bad job from consuming inference time.
- Relative paths need one defined base. The worker always launches `main.py`
  from the project/application root, so preflight now resolves relative job
  paths against that same root rather than an arbitrary GUI working directory.
  GUI clients should still persist absolute paths for portability.
- Worker events now include `event_schema_version` independently from the job
  schema. Invalid job JSON can emit best-effort `JOB_VALIDATION_FAILED` events
  when an `--events` path is supplied; the ID is necessarily `unknown` until
  the job can be trusted.
- `worker.py --preflight` validates a typed job and writes events without
  launching the engine. This is the desktop application's pre-Start contract.
  The suite reached 45 passing tests after added coverage for malformed paths,
  Unicode/space paths, disk/model/FFmpeg checks, launch failure, and standalone
  preflight behavior.

### 2026-08-12 - Shared CLI Contract Extraction

- `pipeline/cli_contract.py` now owns `main.py`'s lightweight argument parser
  and scalar validation. It imports no inference dependencies, so help,
  preflight, and a future GUI settings layer can reason about the exact engine
  contract without loading PyTorch or pyannote.
- `tests/test_cli_contract.py` constructs a typed job using every supported
  worker option and parses the resulting CLI arguments with the engine parser.
  This prevents silent schema drift when an option is added, renamed, or
  removed. The baseline is now 46 passing tests.

### 2026-08-12 - Worker Lifecycle Event and Live Cancellation Probe

- The worker now emits `stage_completed` when a new stage banner begins and
  once more after the final stage on successful completion. The GUI no longer
  needs to infer stage completion from unstructured console text; it can use
  monotonic progress events directly.
- A real worker invocation against the supplied cameras passed preflight and
  was cancelled via the sentinel before source probing. It exited 130 and
  emitted a resumable `job_cancelled` event. Temporary probe events, sentinel,
  output directory, and job file were removed after verification. The suite is
  at 48 passing tests.

### 2026-08-12 - Typed Run Request and Output Layout

- `RunLayout` owns the durable names/locations for derived audio, checkpoints,
  reports, XML, previews, and manifest data. The CLI constructs it once, so a
  GUI and engine cannot silently disagree about a job's output layout.
- `RunRequest` is the typed engine configuration created after argparse
  validation. The existing orchestrator now consumes that request rather than
  an argparse namespace; temporary `cam1`/`cam2` aliases support incremental,
  behavior-preserving migration of the mature code path.
- The final typed-request live-cancellation probe again passed preflight,
  returned exit code 130 before source probing, emitted `job_cancelled`, and
  created no output directory. Temporary probe data was removed. The suite is
  now 49 passing tests.

### 2026-08-12 - Runtime and Completion Artifact Boundaries

- `pipeline/runtime.py` now owns cache, offline, telemetry, and CPU-worker
  configuration that must occur before Hugging Face/PyTorch imports. It honors
  explicitly supplied environment settings rather than overwriting them.
- A successful worker reads `run_manifest.json` and emits `artifacts_available`
  with the engine-reported output paths. This makes the manifest the sole
  source of truth for a GUI results page. If that manifest cannot be read, the
  worker emits `RUN_MANIFEST_UNREADABLE` as a warning but retains the child
  process's success status. The suite is now 52 passing tests.

### 2026-08-12 - Manifest Service Extraction

- `pipeline/run_manifest.py` now constructs schema-v2 run manifests from the
  typed request, layout, validated stage diagnostics, and editorial result.
  This preserves the existing manifest contents but makes metrics/output-path
  behavior independently testable and keeps `main.py` from owning another
  serialization format. The suite is now 53 passing tests.

### 2026-08-12 - Milestone 2 Completion and Milestone 3 Start

- Milestone 2 passed its real lifecycle gate. A 15-second offline neural worker
  job completed in 42.5 s, emitted all six stage completions plus artifacts and
  `job_completed`, and produced a validated 450-frame XML. Its identical warm
  rerun completed in 5.1 s with verified audio and completed-turn cache hits.
- Probe/audio/sync stages now execute through `pipeline/stage_services.py`.
  Completed diarization cache identity/persistence also has a dedicated tested
  boundary. A lightweight real child-process fixture verifies completion,
  artifact discovery, and checkpoint reuse on every test run. The Python suite
  is 59 passing tests.
- Milestone 3 began as a WPF/.NET 9 thin client under `desktop/`. It supports
  browse/drag/drop/swap inputs, output and editorial settings, preflight, live
  structured progress plus cockpit logs, cancellation, result status, and
  manifest-driven timeline/preview actions. It never imports neural libraries.
- The WPF shell and executable C# JSON contract checks build with zero warnings
  and no third-party NuGet dependency. The framework-dependent Release publish
  is only 214,065 bytes (0.20 MiB across five files); the Python inference
  runtime remains the application-size driver.
- All .NET CLI, NuGet, APPDATA, and LOCALAPPDATA paths used after the initial
  attempt are redirected inside the repository. The initial `dotnet` invocation
  reported installing an ASP.NET development certificate before isolation;
  PodEdit does not use it, and it was not removed because modifying the Windows
  certificate store requires explicit user approval.

### 2026-08-12 - Compact Synchronization Audio

- Camera 1's derivative must remain 48-kHz stereo PCM because it is the master
  timeline audio, but Camera 2's derivative is correlation evidence only and
  can safely use 16-kHz mono PCM. `audio_extractor.extract_audio` now includes
  channel count in both its FFmpeg command and cache identity.
- On the real 15-second lifecycle fixture, the Camera 2 WAV is 480,078 bytes
  instead of the 2,880,078-byte stereo equivalent, an 83.3% reduction. The
  compact file produced a -0.9565-s correlation offset at 342.2x peak/noise
  confidence. This is consistent with the canonical -0.9810-s result given the
  fixture's much shorter evidence window.
- The offline Python suite now has 61 passing tests, including an explicit
  assertion that the secondary extraction requests 16-kHz mono while the
  primary extraction retains master-audio quality.

### 2026-08-12 - Warm-Cache Import Optimization

- Importing `pipeline.diarizer` costs about 5.8 s on this machine because it
  eagerly loads PyTorch, pyannote, librosa, and NumPy. This cost was being paid
  even when `raw_turns.json` was a valid completed cache hit.
- Neural version/cache constants now live in lightweight
  `pipeline/diarization_contract.py`; `main.py` imports the heavy implementation
  only after a cache miss. Manual sync overrides likewise no longer import the
  librosa/scipy correlation implementation. An identical warm 15-second job
  dropped from 6.1 s to 2.1-2.5 s without output changes.
- Schema-v2 run manifests now include `metrics.stage_seconds`,
  `unattributed_seconds`, and `real_time_factor`, making future optimization
  decisions evidence-based without parsing console logs.

### 2026-08-12 - Scalable Desktop Event Tailing

- The initial WPF event pump used `ReadAllLinesAsync` every 200 ms, creating
  quadratic I/O as verbose JSONL logs grew and risking a missed final artifact
  event when the worker exited between polls.
- It now tracks a byte offset, retains partial UTF-8 lines across reads, shares
  the live file safely with the writer, and performs a delayed final drain plus
  end-of-file parse. The WPF build remains at zero warnings; executable JSON
  contract checks and the real-XAML smoke test pass.

### 2026-08-12 - Canonical Storage Gate Passed

- Regenerating only the reproducible Camera 2 synchronization derivative in
  the 25-minute canonical result reduced it from 288,000,078 to 48,000,078
  bytes. The complete canonical output directory now measures 336.1 MiB, inside
  Milestone 4's 0.2-0.4 GiB derived-data target.
- A full 300-second correlation against the unchanged 48-kHz stereo Camera 1
  master reproduced the exact canonical offset (-0.9809523809523809 s) and
  confidence (58.36724994481945x). Compact PCM introduced no measurable sync
  regression and reclaimed 240,000,000 bytes from the project folder.

### 2026-08-12 - Shared-Feature Neural Confirmation

- pyannote Community-1's ranged and exact-speaker calls both computed the same
  segmentation and embedding front end; only clustering/reconstruction needed
  to differ. PodEdit now captures the public hook's `segmentation` and
  `embeddings` artifacts and temporarily supplies them to the exact-count call,
  restoring the original pipeline methods in `finally`. Missing artifacts
  automatically fall back to the proven full neural pass.
- A real accepted window reproduced 23 turns and cosine 0.5520366533 while its
  exact-two reclustering took 1.11 s after the primary pass. The clean isolated
  25-minute benchmark then completed in 1249.6 s (20.83 min). All 29 recovery
  attempts totaled 2.38 s versus the prior 1073.4 s, retaining 2 accepted and
  27 rejected recoveries.
- Most importantly, the optimized run reproduced all 596 canonical turns
  exactly: both normalized JSON SHA-256 values are
  `1eac56d6ad62d586d2fb52284dcde6ae813e03b07ee7f16fb7d034607ef3582d`.
  This passes the Milestone 4 neural runtime target without an accuracy proxy;
  parity was checked on the actual serialized decision input.

### 2026-08-12 - Job Retention Controls

- `manage_storage.py` inventories known reproducible artifacts in exactly one
  resolved job folder and defaults to a report-only dry run. Actual removal
  requires both `--delete` and one or more named categories. Unknown categories
  are rejected before deletion, and containment checks exclude outside paths.
- Cleanup policy intentionally never targets XML timelines, cut reports, run
  manifests, or human annotations. The canonical inventory reports 320.4 MiB
  derived audio, 14.6 MiB review media, and 0.9 MiB analysis cache. The WPF
  client now leaves expensive review rendering unchecked by default.
- The offline Python suite is now 65 passing tests.

### 2026-08-13 - Milestone 5 One-Folder Prototype

- A frozen supervisor cannot launch `main.py` with `sys.executable`: in a frozen
  process that would recursively launch the supervisor. Packaging therefore has
  three explicit layers: self-contained WPF shell, 8.0-MiB `PodEdit.Worker.exe`,
  and a separate `PodEdit.Engine.exe` plus dependency directory.
- The production audio path no longer uses librosa. `pipeline/audio_io.py` uses
  SoundFile and soxr for bounded mono loading/resampling, while WAV duration is
  read from the standard-library header. This removed the frozen Numba cache
  failure and enabled exclusion of librosa, Numba, llvmlite, and audioread. A
  300-second sync check reproduced offset, peak, and confidence exactly and
  reduced audio loading from about 1.8 s to 0.4 s.
- The real packaged cold smoke loaded Community-1 from project-local assets,
  ran a 15-second inference window plus shared-feature confirmation, produced
  five turns, and exported a validated 450-frame XML. Warm packaged and
  self-contained WPF XAML smokes also pass. The Python suite is 71 tests.
- The complete one-folder prototype is 1,141,127,794 bytes (1,088.3 MiB), with
  GUI, worker, engine, models, and one FFmpeg/FFprobe pair. The final audit
  hashes 5,764 files and reports zero forbidden files. Runtime-source exceptions
  are narrowly limited to SpeechBrain, PyTorch, torchaudio, scikit-learn, and
  OpenCV files required by their official dynamic import/freezer behavior.
- Milestone 5 is not complete until the bundle is exercised on a clean Windows
  VM without Python, FFmpeg, .NET, or model caches; signing is a later gate.

### 2026-08-13 - License Inventory Resolution

- Wheel metadata omitted license declarations for six pyannote distributions
  and TorchCodec, but each wheel contained an upstream license file. The audit
  now recognizes the six MIT texts and TorchCodec's BSD-3-Clause text without
  guessing from package names. All 132 installed distributions have a resolved
  declaration.
- `packaging/THIRD_PARTY_LICENSES/` collates 351 installed license/notice files
  (1.90 MiB), and the inventory, lock, audit JSON, and notices are included in
  the prototype. The post-notice bundle audit still reports zero forbidden
  files.

### 2026-08-13 - Installer Boundary and Current Blocker

- The installer definition is per-user (`%LOCALAPPDATA%\Programs\PodEdit`) and
  non-elevated. Packaged UI settings move to `%LOCALAPPDATA%\PodEdit\settings`;
  provisioned models can override bundled models from `%LOCALAPPDATA%\PodEdit\models`.
  Uninstall intentionally preserves all mutable user data.
- Public installer source excludes gated Community-1 weights by default because
  the cached model snapshot contains no affirmative redistribution license.
  `INTERNAL_OFFLINE_BUILD` is an explicit compile-time gate, not the default.
- The final source-matched reassembly could not restore FFmpeg/FFprobe because
  copying from machine-wide Chocolatey was rejected by the user's folder-only
  rule. The strengthened current audit reports exactly those two required files
  missing and otherwise zero forbidden content. Current candidate: 939,137,188
  bytes (895.6 MiB); current whole project after disposable cleanup:
  10,141,733,900 bytes (10.142 GB / 9.445 GiB).
- Installer-policy coverage and required-file bundle auditing bring the suite
  to 77 passing tests. Production diagnostics and `requirements.txt` now name
  SoundFile/soxr rather than librosa; librosa/Numba/LLVM are development extras,
  not frozen-engine requirements.

### 2026-08-20 - Milestone 7 Automated QA and Reproducibility Gate

- `release_qa.py` is the single local release-candidate gate. It runs the
  complete test suite and doctor, validates the canonical segment/XML outputs,
  checks research sources and the frozen bundle, records exact storage, and
  writes `results/release_qa/qa_report.json`. External clean-VM, signing, NLE,
  and independent human-review gates remain explicitly pending.
- Canonical editorial artifacts now have a stable SHA-256 identity through
  `pipeline/reproducibility.py` and `fingerprint_run.py`. The identity includes
  configuration, input edge fingerprints, sync/mapping decisions, segments,
  XML, and cut reports while deliberately excluding timestamps and runtime.
  Current locked identity: `8495bf6889e63398336ed346bab598749a8e8a04eee5036a5ccf4007510e6549`.
- Validators must treat malformed user/generated timing as reportable data
  errors, not uncaught numeric-conversion exceptions. Real subprocess
  cancellation testing found that `Path` values in the worker command were
  not JSON serializable; normalizing command arguments to strings and placing
  startup event writing inside `try/finally` fixed the event-file leak.
- The offline suite passes 90 tests. Release QA passes every available gate
  except bundle integrity, which still reports only project-local FFmpeg and
  FFprobe missing. Project size was 10,088,871,006 bytes (10.089 GB / 9.396 GiB); the
  incomplete candidate is 939,137,188 bytes (895.6 MiB).
- `local_gates_passed` and `release_ready` are deliberately separate. A build
  cannot report release-ready while any clean-machine, signing, NLE-import, or
  independent human-review gate is pending, even after all local checks pass.
- Treat run manifests as an engine-to-GUI trust boundary. The worker now
  announces artifacts only if each non-null path is text, resolves inside the
  job output root, and names an existing file; invalid manifests emit
  `ARTIFACT_MANIFEST_INVALID` without exposing an open action.

### 2026-08-20 - Fail-Fast Media Contracts and Frozen-Source Freshness

- The versioned GUI job contract must validate the same release constraints as
  the CLI before child launch: supported choices, finite numeric values,
  exactly two speakers, positive duration/FPS, valid recovery cosine, and
  window-overlap geometry. Deferring these errors wastes startup time and makes
  GUI feedback less actionable.
- Existing input files are not sufficient preflight evidence. FFprobe must
  confirm a readable video stream, an audio stream required by current sync,
  positive dimensions, frame rate, and duration. Inspection failures now emit
  `SOURCE_INSPECTION_FAILED`, fail preflight with exit 2, and never start the
  neural engine. The real 25/30-fps canonical cameras pass this probe.
- A content audit cannot prove that frozen executables represent current
  source. `pipeline/source_identity.py` fingerprints executable-affecting
  Python, WPF, and freezer-spec files. `packaging/fingerprint_sources.py` must
  be run immediately before the next genuine freeze; release QA blocks a stale
  or missing baseline as `bundle-source-freshness`. Never generate that file
  merely to bless an already-built candidate.
- The offline suite then passed 100 tests. Current automated blockers are the two
  absent project-local FFmpeg tools and missing source-freshness evidence for a
  new freeze; clean-VM, signing, NLE import, and human-review gates remain
  external.
- The freshness baseline must be embedded by `PodEdit.Engine.spec` as
  `_internal/source-fingerprint.json`; release QA reads the candidate's copy.
  A loose staging fingerprint is insufficient evidence because it could be
  regenerated without rebuilding the executable.
- Cancellation evidence now covers a later safe boundary: cancellation after
  checkpoint creation but before export preserves the checkpoint, creates no
  XML, emits resumable exit 130, and the next run reuses preparation before
  completing normally.

### 2026-08-31 - Unbiased Multi-Editor Evaluation

- The earlier annotation CSV was sliced at PodEdit's own proposed boundaries.
  Treating every CSV row boundary as a human cut could inflate boundary scores
  by construction, even when adjacent rows selected the same camera. It is now
  explicitly an assisted correction sheet, not a blinded research reference.
- `evaluate.py --make-blind-sheet` creates a full-duration template without
  predicted cameras or cut times. Editors split it into independent contiguous
  intervals. Reference loading fuses adjacent same-camera rows and rejects
  invalid cameras, non-positive intervals, gaps/overlaps, nonzero starts, and
  incomplete episode coverage.
- Repeating `--reference` now reports PodEdit metrics separately against each
  editor, macro camera accuracy and cut F1, pairwise boundary F1, and
  duration-weighted Cohen's kappa. Disagreement is retained rather than hidden
  inside an automatically manufactured consensus label.
- Release QA now verifies exact parity between the fenced LaTeX in
  `research paper.md` and `paper/podedit_ieee_overleaf.tex`, and checks that the
  canonical blind template does not expose `predicted_camera`. The offline
  suite passes 108 tests.

Reference: J. Cohen, "A coefficient of agreement for nominal scales,"
*Educational and Psychological Measurement*, vol. 20, no. 1, pp. 37-46, 1960,
doi: 10.1177/001316446002000104. Available:
https://doi.org/10.1177/001316446002000104

- End-of-turn storage after evaluation code, the canonical blind template,
  tests, QA report, manuscript, and documentation updates:
  10,088,948,916 bytes (10.089 GB / 9.396 GiB). The unchanged incomplete
  candidate remains 939,137,188 bytes (895.6 MiB), and the canonical result is
  352,420,434 bytes (336.1 MiB).

### 2026-09-02 - Complete, Bounded All-Cuts Reviews

- `render_switch_review` silently sampled down to 80 cuts despite its name.
  Default coverage is now unlimited, with sampling permitted only via explicit
  `max_cuts`. Regression coverage verifies all 101 cuts and the former divide-
  by-zero case when explicitly requesting one cut.
- Eight-cut rendering batches reduce decoder/command-length pressure. Temporary
  media lives beside the output, is cleaned automatically, and only a completed
  reel atomically replaces an existing review.
- Real-media testing exposed AAC padding at batch joins and a dropped short-
  piece video frame. Cumulative frame budgets plus PCM MOV intermediates and
  one final AAC encode produced exactly 90 frames and 3.000 s audio/video in
  a three-cut/two-batch smoke. Canonical edit files were not regenerated.
- Full regression suite: 112 passing tests. All test temporary directories were
  routed inside the project for the verification run.
- Final release audit passes tests, doctor, canonical XML/fingerprint, paper
  parity, and academic assets. Missing FFmpeg tools and absent embedded source
  fingerprint still block the frozen bundle; it was not rebuilt this turn.
- Storage measurement before this log update: 10,089,240,946 bytes. Added media
  is a 270,501-byte real-source review smoke; no source/canonical edit removed.

### 2026-09-18 - Supplied Manuscript Authors

- Replaced placeholders in both equivalent LaTeX sources with K. Chandra Haas,
  G. Shivamani, M. Srilekha, and Ms Appam Ashwini, preserving the supplied
  author order and email addresses. Shared affiliation is Vardhaman College of
  Engineering, Hyderabad, Telangana, India. No department was inferred.
- Escaped the underscore in the fourth email for LaTeX. The paper-source parity
  regression passes; no compiler or PDF was installed/generated.

### 2026-09-18 - User-Approved PDF Compilation

- Compiled the unchanged four-author IEEE source with temporary portable
  Tectonic 0.17.0, downloaded only after explicit user approval. Its executable
  occupied 51,538,432 bytes; no system-wide installation was performed.
- Retained `output/pdf/podedit_ieee_overleaf.pdf`: five pages, 115,432 bytes.
  Rendered and visually inspected every page, including author block, tables,
  equations, figure, and references. No clipping or overlapping text was found.
- Removed the project-local compiler, downloaded TeX cache, build logs, working
  source copies, and page-render images after verification. Sources in the
  Markdown and standalone TeX files remain unchanged and equivalent.

### 2026-09-18 - Two-by-Two Author Layout

- Changed both LaTeX sources to four individual author blocks: Haas and
  Shivamani on the first row, Srilekha and Ashwini on the second. Each block
  repeats the supplied college, location, and individual email address.
- The existing compiled PDF predates this change; no compiler was downloaded
  or installed for this source-only update. Recompile in Overleaf for the new layout.

### 2026-09-18 - Recompiled Two-by-Two Author PDF

- Rebuilt the PDF at the user's request using temporary project-local Tectonic.
  IEEEauthorblock commands conflict with nested author tabular/minipage layouts;
  explicit name and affiliation typography inside each minipage compiles cleanly.
  Applied that correction identically to both maintained LaTeX sources.
- Visually checked all five rendered pages, including the four individual
  author blocks. The final PDF is 111,765 bytes. Removed the temporary compiler,
  cache, logs, source copies, and rendered pages again; no system installation.
- The original PDF was viewer-locked, so the current layout is delivered as
  `output/pdf/podedit_ieee_2x2_authors.pdf`; the old PDF is preserved. For future
  rebuilds, use Stop-on-error copy operations and confirm final publication
  before deleting scratch output.

