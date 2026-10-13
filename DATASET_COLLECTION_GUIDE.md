# Dataset Collection Protocol — PodEdit 1.5

Updated: 2026-08-11

## Minimum study scope

- Collect at least 10–15 legally usable two-person podcast episodes.
- Record two locked single-person camera angles and preserve their native frame
  rates and original audio.
- Include studio, home, reverberant, and noisy environments.
- Include slow interviews, rapid exchanges, backchannels, interruptions, and
  overlapping speech.
- Keep development and held-out evaluation episodes separate.

## Source metadata

For every episode, record:

- stable episode and camera identifiers;
- source paths, byte sizes, modification timestamps, duration, resolution,
  native frame rate, audio sample rate, and codec;
- a manually verified signed camera-2 offset using the same convention as
  `pipeline/sync_engine.py`;
- participant-to-camera identity;
- consent, permitted research use, and any redistribution restrictions.

Do not use a manually estimated offset as hidden algorithm input during an
automated evaluation. Store it as reference evidence and compare it with the
pipeline estimate.

## Human editorial reference

At least two editors should independently annotate the desired camera over
continuous intervals without seeing PodEdit's output. They should also record
ambiguous intervals where more than one choice is defensible. Use
`evaluate.py --make-sheet` to create a compatible CSV and retain each editor's
file separately.

Report:

- duration-weighted camera agreement;
- cut precision, recall, and F1 with a predeclared boundary tolerance;
- absolute matched-boundary timing error;
- inter-editor agreement;
- subjective preference ratings and editing time;
- results per episode and per condition, not only pooled averages.

## Current pilot

`datasets/test_set_1/` is the engineering pilot. Only its first 1500 seconds
have been used for the PodEdit 1.5 release candidate. Its screen-time and cut
statistics must not be described as accuracy until
`results/variable_speaker_25min/human_annotation.csv` is completed by
independent editors.
