# PodEdit Release-Candidate QA Matrix

Updated: 2026-08-20

This is the human-readable companion to
`results/release_qa/qa_report.json`. A row is complete only when its evidence
exists; an assumption or successful developer-machine run is not a pass.

| Area | Current status | Evidence / remaining action |
|---|---|---|
| Python regression suite | Pass | 112 offline tests |
| Environment doctor | Pass | Executed by `release_qa.py` |
| Canonical segments and XML | Pass | 1500 s; exactly 45,000 timeline frames |
| Deterministic editorial artifacts | Pass | Locked SHA-256 identity `8495bf...6549` |
| All-cuts review completeness | Pass | 101-cut regression retains every cut; explicit sampling only |
| Batched review media smoke | Pass | Real sources: 90 frames, video/audio both 3.000 s across two batches |
| Paper source parity | Pass | Markdown LaTeX block equals standalone Overleaf source |
| Blind evaluation assets | Pass | Free-boundary template hides PodEdit cuts/cameras |
| Malformed segments/XML | Pass | Structured failures, no conversion crash |
| Corrupt/silent media | Pass | Video/audio streams, dimensions, fps, and duration checked before launch |
| Typed option validation | Pass | Choices, finite ranges, speaker count, and window geometry checked |
| Unicode, spaces, long paths | Pass | Preflight regression fixture |
| Read-only and low-disk outputs | Pass | Stable preflight errors/warnings |
| Corrupt diarization checkpoint | Pass | Safe cache miss |
| Cancellation and resume | Pass | Real child cancellation before preparation and after checkpoint; successful resume/reuse |
| Artifact handoff containment | Pass | Missing/outside paths are never announced to GUI |
| Bundle integrity | Blocked | Add project-local FFmpeg and FFprobe, then rerun audit |
| Bundle/source freshness | Blocked | Refreeze current source with its fingerprint embedded in the engine bundle |
| Clean Windows 11 standard-user VM | Pending | Install/run without Python, developer tools, or caches |
| Authenticode signing | Pending | Obtain certificate and sign binaries/installer |
| DaVinci Resolve import | Pending human | Import canonical XML and inspect sync/cuts |
| Premiere Pro import | Pending human | Import canonical XML and document supported workflow |
| Three independent all-cuts reviews | Pending study | Complete blinded annotation and agreement metrics |

## Commands

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe release_qa.py
```

`release_qa.py` distinguishes `local_gates_passed` from `release_ready`.
Release readiness remains false while any external gate above is pending.
