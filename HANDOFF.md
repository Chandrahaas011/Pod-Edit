# PodEdit 1.5 - Maintainer Handoff

Manuscript authors updated 2026-09-18: K. Chandra Haas, G. Shivamani,
M. Srilekha, and Ms Appam Ashwini, all affiliated with Vardhaman College of
Engineering, Hyderabad, Telangana, India. Both LaTeX sources contain their
supplied emails and pass the source-parity regression.

Latest change (2026-09-02): `render_switch_review` now covers every cut by
default, batching eight cuts at a time instead of silently sampling down to
80. Cumulative frame rounding gives each piece its intended frame count;
PCM MOV intermediates avoid per-batch AAC padding, with one final AAC encode.
Failed renders preserve the existing output and clean their local scratch
directory. A real three-cut/two-batch smoke produced exactly 90 H.264 frames
and 3.000 s of AAC audio. Evidence: `results/release_qa/batched_review_smoke.mp4`.

Updated: 2026-08-20

## Current production path

Run `main.py`; the maintained engine is the `pipeline/` package. The historical
`src/v*.py` experiments explain earlier failures but are not production entry
points. Python 3.13 is supported, MediaPipe is not used, and the canonical test
processes only the first 1500 seconds of the two-camera episode.

The current pipeline:

1. probes each camera at its native frame rate;
2. extracts source-bound 48-kHz stereo Camera 1 master audio and a compact
   16-kHz mono Camera 2 synchronization derivative;
3. estimates a signed offset with FFT cross-correlation;
4. runs overlapping Community-1 diarization windows with one-to-two-speaker
   constraints, then selectively confirms apparent monologues with exact-two
   checkpoints;
5. jointly reconciles local voice identities and maps them to cameras using
   sparse, head-compensated vertical-edge lip motion;
6. applies a deterministic editorial policy plus seam-safe, pause-aware
   listener cutaways; and
7. exports and validates FCP XML 7, previews, cut reports, and a run manifest.

## Canonical command

```powershell
python main.py `
  --cam1 datasets\test_set_1\camera1_short.mp4 `
  --cam2 datasets\test_set_1\camera2_short.mp4 `
  --output results\variable_speaker_25min `
  --max-duration 1500 `
  --editorial-profile balanced `
  --second-speaker-max-cosine 0.70 `
  --offline
```

`--force` deliberately bypasses compatible final and window caches. Do not use
it for routine release verification. Model files live in `.model_cache/`; no
project artifact needs to be written outside this repository.

## Verified v1.4 evidence

- sync: -0.98095 s, peak/noise ratio 58.37;
- adaptive diarization: 596 exclusive turns, 2/29 exact confirmations accepted,
  27 forced monologue splits rejected;
- visual mapping: Camera 1 effect +0.545, Camera 2 effect -0.655, no fallback;
- edit: 53 shots, 52 cuts, 85.4%/14.6% occupancy, 66.0-s maximum shot;
- reactions: 20 listener cutaways, minimum processing-seam distance 1.567 s,
  zero high-priority cut flags;
- XML: 45,000 frames, 53 video clips, 53 audio clips, validation pass;
- media: 60-s preview and 312-s all-cuts reel, H.264 plus AAC;
- review workflow: blank report preserves 53 shots and produces a validated
  45,000-frame reviewed XML plus a 60-s preview;
- tests: 61 automated tests, including the typed worker job contract,
  PowerShell UTF-8-BOM compatibility, cooperative cancellation, extracted
  stage services, and compact synchronization-audio policy.

Milestone 4 has started. A real 15-second run verified that the Camera 2
sync-only WAV is 480,078 bytes instead of the 2,880,078-byte stereo equivalent
(83.3% smaller) while correlation remained decisive at -0.9565 s and 342.2x
peak/noise confidence. Camera 1 remains 48-kHz stereo because it supplies the
timeline's master audio.
The heavy PyTorch/pyannote implementation is now imported only on a completed-
turn cache miss. This reduced the measured 15-second warm lifecycle from 6.1 s
to 2.1-2.5 s; `run_manifest.json` now retains stage timings, unattributed
startup time, and overall real-time factor for future cold/warm comparisons.
The canonical `results/variable_speaker_25min/` Camera 2 derivative has also
been regenerated in the compact format. The complete directory is now 336.1
MiB, and full-window correlation exactly reproduced -0.980952 s at 58.367x.

The dominant cold-run optimization is validated in
`results/milestone4_shared_feature_benchmark/benchmark.json`. Exact-speaker
confirmation now reclusters pyannote's already-computed segmentation and
embedding artifacts rather than rerunning the neural front end. The clean
25-minute run took 1249.6 s (20.83 min), with all 29 confirmations totaling
2.38 s, and reproduced the canonical 596 turns exactly by normalized JSON hash.
The full-pass confirmation remains an automatic compatibility fallback.

Production audio loading now uses SoundFile/soxr instead of librosa. This keeps
Numba/LLVM out of the frozen engine and avoids source-locator cache failures in
PyInstaller while reproducing canonical sync correlation exactly.

Milestone 5 now has a locally validated one-folder prototype at
`packaging/build/engine/PodEdit.Engine/`. It measures 1,141,127,794 bytes
(1,088.3 MiB), includes the self-contained WPF GUI, separate frozen supervisor
and neural engine, offline models, and FFmpeg/FFprobe. Both cached and real
cache-miss packaged jobs pass; the latter loads Community-1 offline and emits a
validated 450-frame XML. `packaging/build/bundle-audit-final.json` hashes all
5,764 files and reports zero forbidden content. The dependency audit has zero
unresolved license declarations and 351 collated notice files. Clean-VM
testing, signing, and installer compilation are still open.

Important latest state: current source was refrozen after moving packaged
settings/models to per-user data locations. Its 895.6-MiB candidate passes 73
Python tests and GUI smoke but intentionally fails the strengthened bundle
audit because `tools/ffmpeg/bin/ffmpeg.exe` and `ffprobe.exe` are absent. An
attempt to recopy the system Chocolatey binaries was rejected by the user's
workspace-only restriction. Supply those two files inside the project, then
rerun `packaging/audit_bundle.py`; do not rely on the older complete-build hash.

The canonical artifacts are in `results/variable_speaker_25min/`. The absence
of `podedit_priority_review.mp4` is intentional: the current audit contains no
high-priority cuts, and stale priority reels are deleted.

## Acceptance boundary

The implementation and timeline structure are reproducible, but a publishable
claim of human-editor agreement still requires completed independent
annotations. Watch `podedit_preview.mp4`, inspect every transition in
`podedit_switch_review.mp4`, complete `human_annotation.csv`, run `evaluate.py`,
and import `podedit_timeline.xml` into Resolve before claiming editorial parity.

## Paper

The author layout was changed to four individual blocks in a 2x2 grid on
2026-09-18. The retained PDF was rebuilt and visually checked with this layout.

`research paper.md` contains the complete four-author IEEE source in a fenced
`latex` block. `paper/podedit_ieee_overleaf.tex` is an identical standalone
copy. `paper/adaptive_timeline.png` is optional but should be uploaded beside
`main.tex` in Overleaf. The five-page compiled PDF is retained at
`output/pdf/podedit_ieee_2x2_authors.pdf` (2026-09-18; 111,765 bytes). The older
single-block PDF is retained because an open viewer prevented replacement. All pages
were visually checked. The user-approved temporary portable compiler, package
cache, rendering images, and build log were removed after compilation.

## Next defensible improvements

1. complete blinded annotations from at least two editors across multiple
   episodes and report inter-editor agreement;
2. tune the recovery threshold only on a development set, then lock it before
   testing new episodes;
3. replace sparse Haar calibration if new poses or occlusions break the
   complementary camera vote;
4. generalize beyond exactly two participants only after the two-camera
   evaluation is complete.

For Windows application work, Milestone 1 is complete: `worker.py` accepts a
versioned job, emits JSONL progress, and supports resumable cooperative
cancellation at safe boundaries. Follow the gated Milestones 2–8 in
`WINDOWS_PRODUCTIZATION_PLAN.md`; do not revive the removed v9 GUI/build.

Milestone 2 subsequently completed its real cold/warm worker lifecycle gate.
Milestone 3 is active in `desktop/PodEdit.Desktop/`; the WPF shell is a thin
client only and the Python worker remains the source of truth for processing,
progress, cancellation, and artifacts.

Milestones 4–6 have since reached their local gates, and Milestone 7 automated
QA is active through `release_qa.py`. Its current report passes 112 tests,
doctor, canonical 45,000-frame XML validation, paper sources, and the locked
editorial-output fingerprint. It is locally blocked by the two missing FFmpeg
tools described above and by the absent pre-freeze source fingerprint: the
existing executables contain no embedded fingerprint proving parity with
current source. Validators
now report malformed segment and XML timing
as data errors rather than exceptions. A real subprocess test also verifies
exit 130 produces a resumable cancellation event and no artifact announcement;
this fixed Windows `Path` serialization and writer cleanup at worker startup.
Current project size is approximately 10.089 GB (9.396 GiB), including the new
270,501-byte review smoke. The incomplete
candidate remains 939,137,188 bytes (895.6 MiB). Passing local gates and true
release readiness are separate report fields, so pending external verification
can never be mistaken for an approved release.
The worker also validates every non-null manifest artifact before GUI handoff:
it must exist and remain contained by that job's output directory.
Typed GUI jobs now mirror the CLI's choices and numeric constraints before
launch. Source inspection requires valid video and audio streams, positive
dimensions/frame rate/duration, and rejects corrupt or silent containers before
model startup. Both canonical cameras pass the real enhanced probe.
Real-child lifecycle coverage now cancels both before preparation and after a
durable checkpoint but before export; the latter resumes successfully without
repeating completed preparation and emits artifacts only after completion.

Academic evaluation was corrected on 2026-08-31. The old assisted annotation
sheet exposes PodEdit boundaries and is suitable only for corrections. Use
`--make-blind-sheet` and `ANNOTATION_PROTOCOL.md` for independent references;
repeat `--reference` for multiple editors. The evaluator fuses same-camera row
splits, validates full continuous coverage, reports per-editor/macro scores,
pairwise boundary F1, and duration-weighted Cohen's kappa. The canonical blind
template is `results/variable_speaker_25min/human_annotation_blind_template.csv`.
Both LaTeX deliverables describe this protocol and are release-gated for exact
source parity. The suite now passes 108 tests.
