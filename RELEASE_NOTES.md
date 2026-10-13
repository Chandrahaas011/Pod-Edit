# PodEdit 1.5 Seam-Safe Editorial Candidate

## Review completeness fix (2026-09-02)

The default all-cuts review now includes every cut, including episodes above
the former silent 80-cut cap. Bounded rendering batches reduce Windows command
length and decoder pressure. Frame-budgeted pieces and PCM intermediates avoid
frame loss and repeated AAC padding at batch joins. Output replacement is atomic
and failed renders preserve the old review. Canonical decisions are unchanged.

Date: 2026-08-11

## Post-candidate validation hardening (2026-08-31)

- corrected the academic evaluator so same-camera CSV row splits are not
  miscounted as human cuts;
- added free-boundary blinded annotation templates that reveal neither
  PodEdit's camera choices nor its proposed cut times;
- added continuous full-duration reference validation, repeated multi-editor
  inputs, per-editor and macro system metrics, pairwise boundary F1, and
  duration-weighted Cohen's kappa;
- added `ANNOTATION_PROTOCOL.md` and a canonical blind template while retaining
  the old prediction-aligned sheet strictly for assisted correction;
- release QA now proves exact parity between the Markdown and standalone LaTeX
  sources and validates the blind evaluation assets;
- 108 automated tests pass. Human results remain pending; these changes improve
  protocol validity but do not invent agreement measurements.

## What changed in 1.4

- exposed the adaptive second-speaker centroid threshold as
  `--second-speaker-max-cosine` and bound it to the raw cache identity and run
  manifest, preventing incompatible threshold experiments from reusing stale
  diarization decisions
- replaced proximity-only listener-cutaway selection with a deterministic
  ordinal rank over listener mouth stillness (60%), 250-ms master-audio RMS
  (30%), and target proximity (10%)
- added a one-second retained-window seam guard whenever a safe reaction
  candidate exists; the canonical pilot's minimum reaction-to-seam distance is
  now 1.567 s and its two prior high-priority flags are gone
- delete an old priority-review video when the current cut audit contains no
  high-priority cuts, preventing stale evidence from being mistaken for a new
  result
- added four unit tests for seam generation, guarded candidate selection,
  pause ranking, and score weighting
- delivered the complete four-author `IEEEtran` code inside
  `research paper.md`, mirrored exactly by `paper/podedit_ieee_overleaf.tex`,
  with an inline bibliography and compile-safe optional figure; it was
  compile-checked before the temporary local compiler and PDF artifacts were
  removed at the user's request

## Verified 1.4 candidate

- 596 retained turns; adaptive confirmation accepted 2 of 29 candidates and
  rejected 27 monologue splits, using the manifest-bound 0.70 threshold
- 53 shots / 52 cuts (2.08 cuts/min), 85.4% / 14.6% camera occupancy, and a
  66.0-second maximum shot
- all 20 listener cutaways are at least 1.567 s from a processing seam; zero
  high-priority cut flags remain
- sync remains -0.98095 s at 58.37x peak/noise confidence; visual mapping
  remains complementary at +0.545 / -0.655 Cliff effects
- FCP XML validation passes at exactly 45,000 frames with 53 video and 53 audio
  clip items
- the representative preview is exactly 60 s and the every-cut reel exactly
  312 s; independent probes find H.264 video plus AAC audio in both
- blank human-review export preserves 53 shots and produces a valid
  45,000-frame reviewed timeline plus a 60-s preview
- 29 automated tests, source compilation, CLI help, and environment diagnostics
  pass

## Remaining acceptance gate

Watch `results/variable_speaker_25min/podedit_preview.mp4` for lip sync, then
review all 52 transitions in `podedit_switch_review.mp4`. Complete
`human_annotation.csv`, score it with `evaluate.py`, and import the XML into
Resolve. The paper intentionally reports engineering validity and pilot edit
statistics until independent human annotations exist.

---

# PodEdit 1.3 Adaptive Speaker Recovery Candidate (Archived)

Date: 2026-08-11

## What changed in 1.3

- stopped forcing two speakers into every 60-second window; the primary
  Community-1 pass now permits one or two speakers, preventing synthetic
  identities during monologues
- added a separately cached exact-count confirmation pass for apparent
  monologues; a recovered second voice is retained only when its two speaker
  embeddings have cosine similarity no greater than 0.70
- replaced sequential/overlap-only identity stitching with a joint constrained
  cosine fit over all window embeddings, while retaining temporal overlap as an
  explicit fallback
- upgraded visual mapping to 960-pixel long-turn-center vertical-edge motion
  with head compensation and complementary, distribution-free Cliff-effect
  votes from both cameras
- made inconsistent same-owner camera votes fail closed instead of being
  reported as visually verified
- added direct tests for adaptive recovery, global single-speaker assignment,
  visual effect direction, and contradictory mapping evidence
- added a command-line entry point for regenerating publication timeline plots

## Verified 1.3 candidate

- 33/33 ranged window checkpoints and 29/29 confirmation checkpoints are
  source-, model-, constraint-, and boundary-bound
- adaptive recovery accepted 2 candidate windows (pair cosines 0.552 and
  0.588) and rejected 27 forced monologue splits (next observed cosine 0.805)
- 596 retained exclusive turns; global identity fit used all 33 windows with
  zero overlap fallbacks, 0.564 median and 0.270 minimum assignment margin
- visual mapping passed without dominance fallback: Camera 1 Cliff effect
  +0.545 and Camera 2 effect -0.655, with complementary owners
- 13 speaker-policy shots plus 20 listener cutaways produced 53 shots / 52 cuts
  (2.08 cuts/min), a 62.0-second maximum, and 85.4% / 14.6% camera occupancy
- sync remained -0.98095 s at 58.37x correlation confidence
- FCP XML validation passed at exactly 45,000 frames with 53 video and 53 audio
  clip items
- final 60-second preview, 312-second every-cut reel, and 20-second two-cut
  priority reel contain H.264 video plus AAC audio
- 25 automated tests, compilation, and every environment diagnostic pass
- blank human-review export preserves 53 shots and regenerates valid XML and a
  60-second preview without modifying the machine proposal

## Remaining acceptance gate

The code, caches, media, and XML are release-candidate quality, but no algorithm
can honestly certify "human edited" from cut count or screen-time balance. Watch
`results/variable_speaker_25min/podedit_priority_review.mp4`, then the every-cut
reel, fill `human_annotation.csv`, and score it with `evaluate.py`. Import the
45,000-frame XML into Resolve for the final NLE interpretation check. Until a
human reference is completed, the paper reports engineering validity and pilot
edit statistics rather than human-equivalent accuracy.

---

# PodEdit 1.2 Reliability and Review Candidate (Archived)

Date: 2026-08-11

## What changed

- upgraded legacy speaker-diarization 3.1 to offline Community-1
- added overlapping local diarization with duration-based identity stitching
- added atomic, source-bound checkpoints for every neural window; interrupted
  runs now resume without discarding completed inference
- added three human-editor pacing profiles, overlap/backchannel handling, and
  evidence-selected listener cutaways for overlong shots
- bound audio and diarization caches to source fingerprints and model version
- moved all model artifacts into project-local `.model_cache/`
- corrected XMEML media-definition placement and added structural validation
- added a run manifest, every-cut review reel, annotation CSV, objective metrics,
  bootstrap confidence intervals, timeline plotting, and environment diagnostics
- added numbered cut overlays, JSON/CSV cut audits, and a short priority reel
- added `apply_review.py` to safely apply numbered keep/move/delete/camera
  corrections without overwriting the original; one manifest-based command now
  exports corrected segments, validated Resolve XML, a sync preview, and a
  source-fingerprinted audit
- cached visual mapping evidence using camera fingerprints, turn hashes, sync
  offset, and verifier version
- replaced the unsupported paper claims with an original IEEE LaTeX pilot paper

## Verified

- sixteen automated tests pass
- all environment diagnostics pass
- a forced 60-second neural run succeeds with `--offline`
- clean 25-minute Community-1 run completes under the two-hour constraint
- sync: -0.98095 s, correlation peak/noise ratio 58.37
- windowed neural inference: 1926.1 s, RTF 1.28 on the i7-1360P CPU
- generated 44999-frame XML passes video/audio coverage and clip-length checks
- 60-second representative preview and 49-cut review reel render successfully
- checkpoint smoke: 51.15-s inference, then identical 0.15-s resumed result
- visual-mapping cache: cached no-preview rerun reduced from 52.8 s to 12.3 s
- cut audit: 49 numbered cuts, one high-priority seam/short-shot transition
- reviewed-bundle smoke: 50 shots preserved from a blank report, 44,999-frame
  XML validation pass, and an exactly 60-second preview render

## Not yet defensible as a final release

The 25-minute candidate has 50 shots, 49 cuts (1.96/min), and a 65.57-second
maximum shot. This fixes the global clustering pass that erased local exchanges.
The visual identity margin remains below threshold and no completed human
reference edit exists. Watch `podedit_switch_review.mp4`, fill
`human_annotation.csv`, run `evaluate.py`, and import the XML into Resolve before
calling the camera decisions or NLE behavior release-ready. The paper deliberately
does not claim human-equivalent accuracy until those steps produce evidence.

Review `podedit_priority_review.mp4` first. It currently contains Cut 35 at
1042.742 s; the flag means the transition is close to a window seam and follows
a 2.0-s shot, not that it is automatically incorrect.
