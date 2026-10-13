# Timeline Automation Status

Updated: 2026-08-11

The former Premiere JSX and Resolve Python-API builders were removed and are
not part of PodEdit 1.4. The sole maintained timeline builder is
`pipeline/xml_builder.py`, invoked through `main.py` and validated by
`pipeline/validator.py`.

The canonical output is
`results/variable_speaker_25min/podedit_timeline.xml`. Import it using
`DAVINCI_RESOLVE_IMPORT_GUIDE.md`. Any future platform-specific automation must
consume the source-bound run manifest, preserve the signed synchronization
offset and 30-fps timeline grid, and pass the same complete video/audio coverage
checks before it is documented as supported.
