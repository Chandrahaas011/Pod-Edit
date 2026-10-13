# PodEdit packaging workspace

Milestone 5 begins with measurement, not a legacy freezer specification.
`audit_runtime.py` records the current environment's exact versions, installed
sizes, and declared license metadata. Its lock is a reproducibility baseline,
not yet the production closure: the development environment contains packages
that a clean worker build may prove unnecessary.

Run with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe packaging\audit_runtime.py
```

Immediately before freezing a candidate, lock the exact executable-affecting
source set:

```powershell
.\.venv\Scripts\python.exe packaging\fingerprint_sources.py
```

Do not run that command merely to make an old candidate pass. The resulting
`build/source-fingerprint.json` certifies only a bundle frozen from that exact
source state. The engine spec embeds it as `_internal/source-fingerprint.json`;
`release_qa.py` compares that embedded copy with live source and blocks stale
or unproven candidates.

Release rules:

- freeze the Python worker separately from the framework-dependent WPF shell;
- bundle one real FFmpeg distribution, not the current Chocolatey shim;
- keep models and mutable job data outside immutable application files;
- exclude datasets, results, tokens, research material, tests, and developer caches;
- resolve every `REVIEW REQUIRED` license entry and include upstream license text;
- test on a clean Windows VM with no Python, FFmpeg, or pre-existing model cache.

## Current measured prototype

The last complete assembled prototype measured 1,141,127,794 bytes (1,088.3
MiB) across 5,764 files and passed the local gates below. The current rebuilt
candidate is 895.6 MiB and intentionally fails `bundle-audit-current.json`
because FFmpeg and FFprobe are missing: the workspace-only rule prevented
recopying them from the machine-wide Chocolatey installation. Place approved
binaries at `build/engine/PodEdit.Engine/tools/ffmpeg/bin/` before calling the
current candidate complete.
It also predates the source-fingerprint gate and therefore fails
`bundle-source-freshness`; refreeze from current source after recording the
fingerprint rather than blessing the old executables.

- self-contained WPF real-XAML smoke;
- frozen worker launching the separate frozen engine;
- warm completed-turn cache lifecycle;
- real 15-second offline Community-1 cache miss and 450-frame XML validation;
- SHA-256 inventory with zero forbidden application source, tokens, datasets,
  results, tests, or developer caches (historical completed audit; current
  audit additionally enforces required binaries).
- 132-package metadata inventory with zero unresolved license declarations and
  351 collated upstream license/notice files included in the folder.

It is still unsigned and not clean-VM certified. Do not distribute it as a
release until licensing, signing, clean-machine testing, and installer gates
are complete.
