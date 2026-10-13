# PodEdit Independent Editor Annotation Protocol

Updated: 2026-08-31

Use this protocol for paper-grade evaluation. The older assisted sheet is useful
for correcting PodEdit's proposal, but it exposes predicted cuts and therefore
must not be treated as an independent human reference.

## Blinding and assignment

Use at least two editors per episode. Give each editor the synchronized source
views and master audio, but do not show PodEdit's timeline, cut report, camera
occupancy, or another editor's decisions. Keep the editorial brief identical:
produce the preferred two-camera program cut, prioritizing the visible active
speaker while allowing intentional listener reactions.

Create one free-boundary template per editor:

```powershell
python evaluate.py `
  --predicted results\my_run\podedit_segments.json `
  --make-blind-sheet results\my_run\editor_01.csv
```

The initial row covers the complete episode. Split it into consecutive shots
and enter `reference_camera` as `1` or `2`. Editors choose their own boundaries;
do not copy times from PodEdit. Rows must start at 0, have no gaps or overlaps,
and cover the exact evaluated duration. Notes are optional.

## Scoring

Repeat `--reference` for independently completed sheets:

```powershell
python evaluate.py `
  --predicted results\my_run\podedit_segments.json `
  --reference results\my_run\editor_01.csv `
  --reference results\my_run\editor_02.csv `
  --output results\my_run\multi_editor_metrics.json `
  --tolerance 0.5
```

PodEdit reports metrics against each editor separately, macro camera accuracy,
macro cut-boundary F1, and pairwise editor agreement. Duration-weighted Cohen's
kappa measures camera-choice agreement beyond chance; pairwise boundary F1
measures timing agreement. Same-camera row splits are fused before scoring and
are not counted as cuts. No consensus label is manufactured when editors
disagree.

The evaluator rejects missing labels, invalid cameras, non-positive intervals,
gaps, overlaps, nonzero starts, and incomplete final coverage. Preserve the raw
editor sheets unchanged alongside the generated metrics.

## Reporting boundary

Report every episode and editor, the predeclared boundary tolerance, macro
scores, pairwise agreement, and failure cases. Do not describe PodEdit as
human-equivalent when only one editor, one episode, or an assisted sheet was
used.

## Reference

J. Cohen, "A coefficient of agreement for nominal scales," *Educational and
Psychological Measurement*, vol. 20, no. 1, pp. 37–46, 1960,
doi: 10.1177/001316446002000104. Available:
https://doi.org/10.1177/001316446002000104
