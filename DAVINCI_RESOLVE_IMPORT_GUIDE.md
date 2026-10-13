# DaVinci Resolve Import Guide — PodEdit 1.5

Updated: 2026-08-11

The maintained entry point is `main.py`, and the canonical validated timeline
is `results/variable_speaker_25min/podedit_timeline.xml`. Historical v9 scripts,
MediaPipe instructions, and `xml_outputs/v9_timeline.xml` are obsolete.

## Generate the timeline

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

Before importing, watch `podedit_preview.mp4` for lip sync and inspect every
transition in `podedit_switch_review.mp4`.

## Import

1. Open or create a Resolve project.
2. Choose **File > Import > Timeline** and select the AAF/EDL/XML option if
   Resolve presents a format submenu.
3. Select
   `results/variable_speaker_25min/podedit_timeline.xml`.
4. Keep the imported 30-fps sequence settings unless Resolve reports a genuine
   project conflict.
5. If media is offline, relink Camera 1, Camera 2, and the master WAV to the
   exact source files recorded in `run_manifest.json`.

## Expected structure

```text
V2: Camera 2 clips with gaps
V1: Camera 1 clips with gaps
A1: Continuous Camera 1 master audio
```

PodEdit 1.5 places timeline events on a 30-fps integer grid while preserving
the cameras' native 25- and 30-fps metadata. Camera 2 source positions receive
the signed synchronization offset. The canonical XML has 45,000 timeline
frames and passed complete video/audio coverage and media-reference checks.

## Troubleshooting

- **Media offline:** Relink against the absolute input paths in
  `run_manifest.json`; do not substitute similarly named transcodes silently.
- **Immediate lip-sync error:** Compare Resolve with `podedit_preview.mp4`. If
  the preview is correct but Resolve is not, inspect Resolve's interpretation
  or relinking rather than changing the measured offset.
- **Cumulative drift:** Confirm the imported sequence is 30 fps and that Resolve
  retained each source's native-rate metadata.
- **Unexpected camera identity:** Confirm the visual mapping diagnostics in the
  manifest. Use `--swap` only for a documented fallback or verified reversal.

Import success and visual lip sync must still be confirmed by a human; XML
structural validation cannot certify an NLE application's interpretation.
