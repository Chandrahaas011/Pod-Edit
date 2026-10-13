# PodEdit: Evidence-Based Version History

Updated: 2026-08-11

This file records why the active architecture exists. Historical numerical
results are diagnostic, not accuracy claims unless they were compared with a
completed human reference.

| Era | Main idea | Observed failure or result | Status |
|---|---|---|---|
| v1-v5 | Haar face detection and mouth optical flow | noisy head-motion responses and excessive switching | archived |
| v6-v7 | MFCC/Resemblyzer embeddings and local thresholds | unstable labels and missed long turns | archived |
| v8 | VAD speech chunks with whole-chunk embeddings | continuous speech merged exchanges; roughly 10 shots | archived |
| v9 | neural diarization plus visual identity binding | established the neural direction, but depended on MediaPipe/Python downgrade | superseded |
| v10 | Python-3.13 CLI and dominant-speaker mapping | removed crash-prone MediaPipe; mapping heuristic remained weak | superseded |
| v11-v1.2 | synchronized, cached local windows and review artifacts | forced-two windows created false identities and near-balanced occupancy | superseded |
| v1.3 | adaptive one/two-speaker windows and constrained global reconciliation | 53-shot candidate; two listener cuts remained near window seams | superseded |
| v1.5 | cache-bound recovery threshold and seam-safe pause-aware reactions | 53 shots, 52 cuts, zero high-priority structural flags | current candidate |

## Why adaptive local diarization replaced the earlier passes

A single 1500-second clustering pass produced a plausible 89.8%/10.2% camera
distribution but only 11 shots, including one 797.95-second hold. Splitting the
episode into overlapping windows while forcing two identities raised the result
to 60 shots and capped the maximum at 62 seconds, but shifted occupancy to
58.2%/41.8% because monologue windows were artificially divided.

The v1.3 primary pass therefore permits one or two speakers per window. If it
returns one, a separately cached exact-two pass is inspected. Across the pilot,
true two-voice candidates had centroid cosines from 0.338 to 0.588, while the
smallest rejected forced monologue split was 0.805. The operating threshold is
0.70 and is explicitly recorded in the raw cache identity and manifest. This
procedure recovered two brief two-voice windows and rejected 27 synthetic
splits.

## Why v1.5 changed listener reaction selection

The v1.3 cutaway selector favored mouth motion and target proximity but did not
explicitly consider audio pauses or retained-window seams. Two resulting cuts
were correctly elevated for human inspection. v1.5 excludes candidates inside
a one-second seam guard whenever a safe alternative exists and ranks the
remainder using listener mouth stillness, 250-ms master-audio RMS, and temporal
proximity. All 20 cutaways remain evidence-selected; their minimum seam distance
is now 1.567 seconds and the high-priority count is zero.

## Current measured pilot

- 1500 seconds analyzed from 69.3-minute, 1280x720 sources at 25 and 30 fps;
- signed camera-2 offset -0.98095 seconds at 58.37 peak/noise ratio;
- 596 exclusive diarization turns and no global identity fallback;
- complementary visual effects +0.545 and -0.655;
- 13 speaker-policy shots plus 20 four-second listener views: 53 shots and 52
  cuts, or 2.08 cuts/min;
- Camera 1/2 occupancy 85.4%/14.6%, maximum shot 66.0 seconds;
- exact 45,000-frame XMEML validation pass;
- representative preview 60 seconds, all-cuts reel 312 seconds;
- 108 automated tests, including blinded multi-editor evaluation integrity.

These figures establish implementation behavior, runtime feasibility, and
structural correctness. Human-edit agreement is intentionally pending the
supplied multi-editor annotation protocol.

The 2026-08-31 evaluator hardening distinguishes assisted correction from
research annotation. Publication references now use independent free-boundary
intervals; adjacent same-camera rows are fused before boundary scoring, full
coverage is mandatory, and repeated editor inputs produce pairwise
duration-weighted Cohen's kappa and boundary F1 without manufacturing a
consensus label.
