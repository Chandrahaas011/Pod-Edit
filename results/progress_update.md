# PodEdit 1.5 Progress Update

Updated: 2026-08-11

The maintained 25-minute candidate is
`results/variable_speaker_25min/`. It contains 53 shots and 52 cuts, an
85.4%/14.6% camera split, a -0.98095-s synchronization offset at 58.37
peak/noise confidence, zero high-priority structural cut flags, and a validated
45,000-frame FCP XML timeline.

Review in this order:

1. watch `podedit_preview.mp4` for lip sync;
2. inspect all 52 transitions in `podedit_switch_review.mp4`;
3. import `podedit_timeline.xml` into DaVinci Resolve;
4. complete `human_annotation.csv` independently and score it with
   `evaluate.py`.

The implementation and file structure are verified, but human-editor agreement
remains pending. See the root `README.md`, `RELEASE_NOTES.md`, and `HANDOFF.md`
for the current architecture and acceptance boundary.
