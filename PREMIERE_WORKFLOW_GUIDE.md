# Adobe Premiere Pro Workflow Status

Updated: 2026-08-11

PodEdit 1.4 has not been validated as a native Premiere Pro workflow. The old
v9 XML and JSX instructions referenced files that no longer exist and have been
removed from this guide.

The supported release-candidate workflow is DaVinci Resolve FCP XML 7. Generate
the timeline with `main.py` and follow `DAVINCI_RESOLVE_IMPORT_GUIDE.md`. If
Premiere compatibility becomes a requirement, test the current XML on a copy
of the project, document the exact Premiere version and import behavior, and do
not call it supported until media relinking, mixed-frame-rate timing, continuous
audio, and all 52 canonical cuts have been verified.
