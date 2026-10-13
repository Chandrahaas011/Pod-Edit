# PodEdit 1.5

Review rendering update (2026-09-02): the all-cuts reel no longer silently
samples episodes above 80 cuts. It renders every cut in eight-cut batches,
uses temporary PCM audio to avoid repeated AAC encoder padding, and publishes
the assembled MP4 only on success. Scratch media stays beside the requested
output and is automatically removed. Python callers can explicitly request
sampling with `max_cuts`; the default is unlimited. Allow temporary disk space
for the batches plus the final reel. The canonical 52-cut edit is unchanged.

PodEdit is an offline, two-camera podcast rough-cut generator. It synchronizes
independent recordings, diarizes two voices, maps acoustic identities to camera
angles using sampled lip activity, applies an editorial pacing policy, and
exports a DaVinci Resolve-compatible FCP XML 7 timeline.

The current Windows packaging prototype is inspectable under `packaging/build/`
and is not yet a signed public installer. See `packaging/README.md` and
`WINDOWS_PRODUCTIZATION_PLAN.md` for measured gates and remaining work.

The project no longer claims that screen-time percentages prove editing
accuracy. Release candidates include structural validation, a reproducibility
manifest, a representative preview, an every-cut review reel, and a human
annotation workflow.

## Pipeline

1. Probe both sources at their native frame rates.
2. Extract bounded 48 kHz PCM audio with source-bound cache fingerprints.
3. estimate camera offset by FFT cross-correlation.
4. diarize overlapping local windows with `pyannote/speaker-diarization-community-1`;
   checkpoint every completed window and reconcile identities globally by voice
   embedding. A ranged one-to-two-speaker pass avoids monologue hallucinations;
   an exact-count confirmation recovers a brief second voice only when the two
   embedding centroids have cosine similarity at or below 0.70.
5. map the two speaker labels to cameras using long-turn-center, vertical-edge
   lip motion and require complementary Cliff-effect votes from both cameras.
6. apply a conservative, balanced, or responsive editorial policy and
   seam-safe, pause-aware listener cutaways in overlong shots. Candidate
   moments are ranked by listener mouth stillness, local master-audio RMS, and
   distance from the target while avoiding retained-window seams.
7. export and structurally validate FCP XML 7.
8. write numbered JSON/CSV cut audits and render normal, all-cut, and priority previews.

## Supported scope

- Windows 11, Python 3.13, CPU execution
- exactly two speakers and two single-person cameras
- mixed camera frame rates (the test pair is 25 fps and 30 fps)
- offline inference after the model has been downloaded once

PodEdit supports restrained listener cutaways for overlong close-up shots. It
does not yet detect wide shots, topic changes, or semantic/emotional reactions.

## Installation

Install FFmpeg 8 or another recent FFmpeg release and ensure `ffmpeg` and
`ffprobe` are on `PATH`.

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

Accept the terms for
`pyannote/speaker-diarization-community-1`, create a Hugging Face read token,
and place `HF_TOKEN=...` in `.env`. The first run stores weights under
`.model_cache/` inside this project. Later runs can use `--offline`.

## Run

```powershell
python main.py `
  --cam1 datasets\test_set_1\camera1_short.mp4 `
  --cam2 datasets\test_set_1\camera2_short.mp4 `
  --output results\my_run `
  --max-duration 1500 `
  --editorial-profile balanced
```

After the first model download, add `--offline`. Use `--swap` only when visual
mapping is unavailable and the two camera assignments are reversed.
Windowed diarization is the default because the legacy global pass erased local
speaker exchanges. Use `--no-reactions` to disable listener cutaways or
`--max-primary-shot` to change their 60-second eligibility threshold.
`--second-speaker-max-cosine` exposes the adaptive confirmation threshold
(default 0.70); it is recorded in cache identities and the run manifest so a
threshold change cannot silently reuse an incompatible result.

Completed neural windows are stored under `diarization_windows/`. If processing
is interrupted, the next compatible run resumes from those checkpoints. A
checkpoint is rejected when the source fingerprint, model, speaker count,
sample rate, or window boundaries differ. `--force` deliberately bypasses both
the final diarization cache and the window checkpoints.
Exact-count confirmation evidence is stored separately under
`diarization_windows/exact_speaker_recovery/`; it is never substituted merely
because forcing two labels produced two clusters.

## Headless worker contract (Windows app foundation)

`worker.py` is the GUI-facing wrapper around the maintained CLI. It receives a
versioned JSON job, launches the same `main.py` engine, mirrors the cockpit log,
and appends structured events to JSON Lines. The GUI does not need to import
PyTorch, pyannote, OpenCV, or FFmpeg directly.

Relative camera and output paths resolve from the PodEdit worker directory,
regardless of the GUI's own working directory. A desktop client should still
write absolute paths for portable job records.

Before launching inference, the worker emits `preflight_started` and performs
lightweight checks for readable video and audio streams, positive duration and
frame rate, a valid output parent, free disk space, FFmpeg/FFprobe, and the
local model cache when offline mode is requested. Typed job options are also
range/choice checked before launch. A failed
preflight emits one or more `job_rejected` events with stable codes and ends
with `job_failed` / exit code `2`; it never begins media processing.

Events include the independent `event_schema_version` field (currently `1`),
in addition to the job schema version. Event types are: `job_preflight_requested`, `job_started`,
`preflight_started`, `job_warning`, `preflight_completed`, `source_inspected`, `stage_started`,
`stage_completed`, `diarization_window_complete`, `job_completed`, `job_cancelled`,
`artifacts_available`, `job_rejected`, and `job_failed`. On success,
`artifacts_available` forwards the manifest's output paths to the GUI only
after every non-null artifact exists inside that job's output directory. The GUI
must treat unknown future event types
as displayable log/status information, rather than crashing. Supplying
`--events` also records malformed-job rejection events, whose `job_id` is
`"unknown"` because a valid ID cannot yet be trusted.

```json
{
  "schema_version": 1,
  "job_id": "example-001",
  "camera1": "C:\\media\\camera1.mp4",
  "camera2": "C:\\media\\camera2.mp4",
  "output": "C:\\media\\podedit-output",
  "options": {
    "max_duration": 1500,
    "editorial_profile": "balanced",
    "offline": true
  }
}
```

Run it with:

```powershell
python worker.py --job C:\media\podedit-job.json `
  --events C:\media\podedit-output\worker_events.jsonl `
  --cancel-file C:\media\podedit-output\cancel.flag
```

Validate a job before starting work:

```powershell
python worker.py --job C:\media\podedit-job.json `
  --events C:\media\podedit-output\preflight.jsonl `
  --preflight
```

This emits `job_preflight_requested` and the usual preflight events, but never
launches the processing engine.

Create `cancel.flag` to request cooperative cancellation. The worker stops
before a new pipeline stage or a new diarization window, after completed window
checkpoints have been atomically saved. Run the same job again without the
sentinel to resume compatible work. Do not use `--force` when resuming.

Editorial profiles:

| Profile | Minimum takeover | Minimum shot | Intended style |
|---|---:|---:|---|
| conservative | 1.80 s | 3.00 s | long-form interview |
| balanced | 1.10 s | 2.00 s | general conversation |
| responsive | 0.65 s | 1.20 s | fast debate |

## Outputs

Derived audio is deliberately asymmetric: `camera1_audio.wav` is 48-kHz
stereo PCM and remains the edit/master track; `camera2_audio.wav` is 16-kHz
mono PCM used only for synchronization. The compact secondary derivative cuts
that artifact's storage by 83.3% without changing the exported program audio.
The production PCM loader uses SoundFile plus soxr; librosa/Numba/LLVM are not
part of the maintained engine or frozen release dependency path.

- `podedit_timeline.xml`: validated FCP XML 7 timeline
- `podedit_preview.mp4`: representative 60-second preview
- `podedit_switch_review.mp4`: six seconds around every cut
- `podedit_priority_review.mp4`: ten seconds around high-priority flagged cuts;
  absent when the current audit has no high-priority cuts, with stale reels
  removed automatically
- `podedit_cut_report.csv`: sortable numbered cut queue for editors
- `podedit_cut_report.json`: cut queue plus machine-readable summary
- `podedit_segments.json`: exact camera decision list
- `raw_turns.json`: source- and model-bound diarization cache
- `diarization_windows/`: ranged-pass and adaptive confirmation checkpoints
- `visual_mapping_cache.json`: content-bound visual identity evidence
- `run_manifest.json`: inputs, configuration, metrics, diagnostics, validation,
  per-stage time, startup overhead, and overall real-time factor
- `sync_metrics.json`: offset, peak correlation, and peak/noise confidence
- `worker_events.jsonl`: optional structured headless-worker event stream

Watch the switch review before importing the XML into Resolve.
The "all-cuts review" is a compact reel containing six seconds around every
transition (52 in the current candidate); it is not a claim that ten cuts are
enough and it is not a substitute for the 25-minute edit. The reel burns in the
cut number, timeline second, and camera transition. If a priority reel exists,
start there; otherwise use the CSV and full switch reel. A `near_window_seam`
flag is a request for human inspection, not an automatic assertion that the cut
is wrong.

Inspect reclaimable derivatives for one completed job without deleting them:

```powershell
python manage_storage.py --output results\my_run --category review-media
```

Deletion requires both an explicit category and `--delete`. The manager only
recognizes scoped reproducible artifacts inside that job; timelines, reports,
manifests, and human annotations are never cleanup targets. Derived audio can
be rebuilt, but removing Camera 1 audio makes the exported XML's audio reference
unavailable until the job is rerun.

In the CSV, set `review_decision` to `keep`, `move`, `delete`, or
`camera_wrong`. For a move or camera correction, fill the corresponding
`corrected_*` field. These columns are deliberately blank in generated reports
so reruns never masquerade as completed human review.

Apply completed decisions as a self-contained reviewed bundle. The run manifest
supplies the original segments, cameras, master audio, verified sync offset, and
timeline FPS; the machine proposal is never overwritten:

```powershell
python apply_review.py `
  --manifest results\my_run\run_manifest.json `
  --export-dir results\my_run_reviewed
```

The bundle contains `reviewed_segments.json`, `reviewed_timeline.xml`, a
60-second `reviewed_preview.mp4`, and `review_audit.json`. The audit fingerprints
the source segment and completed CSV, records every applied decision, and embeds
the XML validation result. `move` decisions are rejected if they would leave a
shot below the safe minimum. The corrected timeline must pass continuity
validation, and its XML must pass complete video/audio coverage checks.

## Human-reference evaluation

Create an annotation sheet:

```powershell
python evaluate.py --predicted results\my_run\podedit_segments.json `
  --make-sheet results\my_run\human_annotation.csv
```

That assisted sheet exposes PodEdit's proposed boundaries and is intended for
correction/review, not publication-grade agreement. For independent evaluation,
follow `ANNOTATION_PROTOCOL.md` and create a blind free-boundary sheet:

```powershell
python evaluate.py `
  --predicted results\my_run\podedit_segments.json `
  --make-blind-sheet results\my_run\editor_01.csv
```

Fill `reference_camera` with `1` or `2`, then score duration-weighted camera
agreement and one-to-one cut precision/recall:

```powershell
python evaluate.py --predicted results\my_run\podedit_segments.json `
  --reference results\my_run\human_annotation.csv
```

Repeat `--reference` for two or more editors to obtain per-editor metrics,
macro camera accuracy/cut F1, pairwise boundary F1, and duration-weighted
Cohen's kappa. Same-camera spreadsheet row boundaries are not counted as cuts,
and incomplete/gapped references are rejected.

## Verification status

On the first 25 minutes of `test_set_1`, PodEdit measured an offset of
-0.98095 s at a 58.37x peak/noise ratio. Thirty-three overlapping Community-1
windows produced 596 retained exclusive turns. The primary ranged pass required
1222.0 s of CPU inference; confirmation of 29 candidate monologue windows took
1073.4 s. The adaptive rule accepted two well-separated second voices and
rejected 27 forced monologue splits. These measured inference components total
2295.4 s (RTF 1.53), below the two-hour target.

The final edit has 53 shots and 52 cuts (2.08 cuts/min): 13 result from the
speaker-floor policy and 20 four-second listener cutaways add 40 boundaries.
Camera occupancy is 85.4% / 14.6%, the maximum shot is 66.0 s, and the visual
identity vote passed without fallback (minimum absolute Cliff effect 54.5%).
The XML validator passed complete video/audio coverage at exactly 45,000 frames.
The 60-s preview and 312-s every-cut reel both contain H.264 video and AAC
audio. The pause-aware selector moved every listener cutaway at least 1.567 s
from a retained-window seam (median 10.758 s), reducing the two prior
high-priority seam flags to zero. Consequently, no priority reel exists for the
current run. Twenty-nine automated tests pass. Human-editor agreement remains
unreported until `human_annotation.csv` is completed.

A blank-review bundle test preserves all 53 shots, regenerates the validated
45,000-frame XML, and renders an exactly 60-second review preview without
overwriting the machine proposal.

## Research manuscript

The complete Overleaf source is embedded in the `latex` code block in
`research paper.md`, with four individual author blocks in a 2x2 layout.
The retained PDF includes this layout and was visually checked on 2026-09-18.
The complete source is in
`research paper.md`. An identical standalone copy is maintained at
`paper/podedit_ieee_overleaf.tex`. It uses `IEEEtran`, contains four explicit
authors and their Vardhaman College of Engineering affiliation, an inline
bibliography, measured v1.4 results, and a
compile-safe figure fallback. Upload `paper/adaptive_timeline.png` beside
`main.tex` to include the timeline figure. The visually checked five-page PDF is
`output/pdf/podedit_ieee_2x2_authors.pdf` (compiled 2026-09-18). The older
`podedit_ieee_overleaf.pdf` has the single-block layout and was retained because
it was locked by an open viewer. No LaTeX compiler,
package cache, or build log is retained; the Markdown code remains usable in Overleaf.

Run tests with:

```powershell
python -m unittest discover -s tests -v
```

Run all local release-candidate gates and write the machine-readable report:

```powershell
python release_qa.py
```

The canonical edit is protected by
`results/variable_speaker_25min/reproducibility_fingerprint.json`. Recreate a
fingerprint for another completed run with `fingerprint_run.py`; use
`--compare <baseline.json>` to make artifact drift return a non-zero status.
The current release QA intentionally remains blocked until the audited bundle
contains `tools/ffmpeg/bin/ffmpeg.exe` and `ffprobe.exe`.
