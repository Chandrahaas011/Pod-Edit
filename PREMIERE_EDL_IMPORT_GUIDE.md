# Adobe Premiere EDL Workflow Status

Updated: 2026-08-11

EDL export is not part of PodEdit 1.4. The historical generator and its expected
`podcast_edit.edl` artifact were removed during pipeline consolidation, so no
current EDL import instructions are provided.

Use `main.py` and the maintained FCP XML workflow in
`DAVINCI_RESOLVE_IMPORT_GUIDE.md`. Reintroducing EDL would require a new exporter
and independent verification of track limitations, source timecode, reel names,
mixed frame rates, master audio continuity, and relinking behavior.
