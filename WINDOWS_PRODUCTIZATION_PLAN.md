# PodEdit Windows Productization Plan

Updated: 2026-08-12

## Assumptions

Estimates assume one experienced developer working full-time, the current
two-speaker/two-camera scope, CPU-first Windows 11 support, and no redesign of
the core research objective. Human-reference data collection is a separate
calendar dependency.

## Architecture

The Windows GUI should be a thin client for a separate headless worker. The GUI
submits a versioned job specification, receives JSON-lines progress events, and
can request cancellation. The worker owns source fingerprints, checkpoints,
inference, editorial policy, validation, and output manifests.

Stable interfaces are required for synchronization, diarization, camera
mapping, editorial policy, timeline export, and preview rendering. The current
`pipeline/` modules are useful starting boundaries, but orchestration,
configuration, filesystem layout, and console presentation must be extracted
from `main.py` before GUI work.

### Milestone 1 status

The foundation is implemented. `pipeline/job_contract.py` defines the finite,
versioned job schema; `worker.py` translates that schema to the maintained CLI
and streams JSON Lines events; and `pipeline/job_control.py` adds cooperative
cancellation before stages and before each diarization window. Existing atomic
window checkpoints provide resume behavior when the same job is run after the
cancel sentinel is removed. The interface has tests and does not alter the
timeline algorithm or canonical v1.5 result.

Validation on 2026-08-12: the 33-test suite passed, command compilation and
help checks passed, and a real cancelled worker job returned exit code 130 with
a resumable `job_cancelled` JSONL event before source probing. Job files accept
UTF-8 with an optional byte-order mark, including PowerShell-authored JSON.

## Schedule estimate

| Milestone | Full-time estimate | Result |
|---|---:|---|
| Worker/job API, structured progress, cancellation and resume | completed foundation; 1–2 additional days for GUI integration hardening | GUI-independent engine |
| GUI MVP: input selection, settings, cockpit log, progress and outputs | 1.5–2.5 weeks | internal desktop application |
| Production-only dependency environment and inspectable one-folder build | 0.5–1.5 weeks | clean portable beta |
| Reuse neural features instead of repeating the front end for confirmation | 2–4 weeks | primary CPU optimization |
| Installer, versioning, uninstall, signing and update design | 1–2 weeks | distributable beta |
| Clean-machine, interruption, Unicode-path, Defender and regression QA | 1.5–3 weeks | release candidate |

With overlapping work, a basic internal beta using the current PyTorch backend
is approximately **4–6 full-time weeks**. An optimized, signed public beta is
approximately **8–12 weeks total**. Exporting and validating an ONNX backend is
research work and would likely extend the total to **12–20 weeks**. Part-time
work should be scaled by available hours, not calendar optimism.

Multi-episode annotation by at least two independent editors can add 2–6 or
more calendar weeks depending on access to recordings and editors. It should
run alongside application engineering because it is the acceptance test for
any optimization that changes cuts.

## Execution roadmap after Milestone 1

The critical path is Milestone 2 -> 3 -> 4 -> 5 -> 6 -> 7. Academic validation
runs in parallel and gates accuracy claims. Milestone 8 is optional and begins
only after the PyTorch release is stable.

### Milestone 2 - Engine contract hardening — COMPLETE

**Estimate:** 2–4 workdays. **Additional workspace:** under 25 MiB.

**Progress (2026-08-12):** the preflight portion is implemented. The worker now
uses a separate event schema version, resolves relative paths from its own
installation root, validates input/output/disk/FFmpeg/offline-model
prerequisites before launch, records malformed jobs as structured events, and
offers `--preflight` without starting the engine. `pipeline/cli_contract.py`
now owns the shared CLI parser and cheap validation, with a contract test that
ensures all typed worker options are accepted by the engine. The remaining
Milestone 2 work is lifecycle integration testing against a real
completed/resumed job and completing extraction of the larger `main.py`
orchestration surface into a dedicated service. `RunRequest` and `RunLayout`
are now the typed configuration and output boundaries used by the CLI.
Successful workers now forward the validated run manifest's artifact paths in
an `artifacts_available` event, so the future GUI does not reconstruct output
names. A missing/corrupt manifest produces a warning but does not rewrite the
engine's successful exit status.
Manifest construction is now a separate tested module, completing another
large `main.py` responsibility without changing the v1.5 manifest schema.

Lifecycle probe (2026-08-12): the canonical offline job passed preflight, then
an active cancellation sentinel caused exit code 130 before source probing. The
event stream contained `job_started`, `preflight_started`,
`preflight_completed`, and resumable `job_cancelled`, with no probe output
retained.

Completion evidence (2026-08-12): a real 15-second offline neural worker job
completed in 42.5 seconds, produced a validated 450-frame XML and manifest, and
emitted six completed stages plus artifact/completion events. Re-running the
same job completed in 5.1 seconds with verified audio and completed-turn cache
hits. The automated suite reached 59 tests, including a true child-process
completion/reuse test.

Deliverables:

- extract orchestration from `main.py` behind an engine/service interface while
  keeping the existing CLI compatible;
- version the event schema and add stable progress, warning, error-code,
  completion, output-artifact, and resumability fields;
- add input, output, permissions, free-space, model-availability, and FFmpeg
  preflight checks before expensive processing starts;
- make cancellation-sentinel creation/removal and retry behavior deterministic;
- add worker integration tests for spaces and Unicode in paths, invalid jobs,
  missing media, child-process failure, cancellation, and checkpoint resume.

Exit gate: a short real-media job can be started, observed, cancelled, resumed,
and completed entirely through the worker contract, with no GUI imports and no
change to the canonical v1.5 edit.

### Milestone 3 - Native Windows GUI internal beta

**Estimate:** 7–12 workdays. **Installed-size addition:** provisionally
60–150 MiB; measure the prototype before locking the deployment model.

**Progress (2026-08-12):** implementation has started as a dependency-free
WPF/.NET 9 thin client. The first shell compiles with zero warnings and provides
camera/output selection, duration/editorial settings, standalone preflight,
worker launch, structured progress, cockpit logging, cooperative cancellation,
terminal status, drag-and-drop, camera swapping, optional review rendering, and
manifest-driven timeline/preview actions. WPF was selected for this first measured prototype because
the installed .NET SDK supplies it without downloading Windows App SDK/NuGet
packages; the worker protocol remains UI-framework independent.

The first framework-dependent Release publish is 214,065 bytes (0.20 MiB,
five files), excluding the .NET Desktop Runtime and Python worker. This confirms
that the inference runtime—not the native shell—is the product-size constraint.
Self-contained GUI size remains to be measured only when the required runtime
pack is locally available or its download is explicitly approved.

Use a thin native Windows client, with WinUI 3/C# as the default implementation
candidate. It communicates only through job JSON, JSONL events, and the worker
process. This keeps the neural Python environment replaceable. Microsoft
documents both framework-dependent and self-contained Windows App SDK
deployment; choose between them only after measuring the prototype.

Deliverables:

- two camera drop zones, output selection, duration and editorial presets;
- source metadata and free-space preflight summary;
- overall and per-stage progress, elapsed time, ETA, cockpit log, cancel,
  retry, and resume controls;
- clear states for ready, running, cancelling, cancelled, failed, and complete;
- results page with XML, preview, all-cuts review, cut report, manifest, and
  buttons to open the output folder and import documentation;
- accessible keyboard navigation, scalable layout, useful error messages, and
  Windows light/dark theme support;
- development-only model provisioning/settings without ever logging or
  packaging a token.

Exit gate: a non-developer can complete a short job without using PowerShell;
the UI remains responsive, survives worker failure, and can reopen the last
job state. This is the first internal beta, not yet a public installer.

### Milestone 4 - Processing and job-storage optimization

**Status (2026-08-12): IN PROGRESS.** The first storage optimization is
validated: Camera 2's synchronization-only derivative is now 16-kHz mono PCM,
while Camera 1 remains 48-kHz stereo because it is the edit's master audio.
On the 15-second lifecycle fixture this reduced Camera 2 audio from a
2,880,078-byte stereo equivalent to 480,078 bytes (83.3%). Cross-correlation
still found -0.9565 s at 342.2x peak/noise confidence; the small difference
from the canonical 25-minute -0.9810-s result is expected from the much shorter
analysis window, not from lossy compression (the derivative remains PCM).
Warm-cache startup was also profiled and optimized. The PyTorch/pyannote module
previously cost about 5.8 s to import even when completed turns were reused.
Moving neural imports behind the cache-miss boundary reduced an otherwise
identical measured warm lifecycle job from 6.1 s to 2.1-2.5 s (59-66%). Manual
sync overrides now similarly avoid importing the correlation stack. Manifests
record per-stage, unattributed-startup, and overall real-time-factor metrics.
The desktop event reader now tails appended bytes rather than rereading the
entire JSONL file on every poll, and performs a delayed final drain so the
artifact event cannot be lost in a worker-exit race.

**Estimate:** 10–20 workdays. **Temporary experimentation space:** 2–5 GiB.

Deliverables, in priority order:

1. profile one cold and one warm canonical run using stage/window timings;
2. reuse neural segmentation/embedding features when testing one-speaker and
   two-speaker hypotheses instead of rerunning the neural front end;
3. test compact mono analysis audio and remove duplicate derived audio where
   source media can safely remain the master; **compact Camera 2 derivative
   complete, master-audio removal still pending evidence**;
4. replace dependency-heavy audio paths where an equivalent small routine is
   validated, and control CPU thread oversubscription;
5. make long review rendering explicitly on-demand and add cache retention and
   cleanup controls. **Complete:** desktop review rendering is opt-in by
   default, and `manage_storage.py` provides dry-run-first, category-scoped
   cleanup that never targets timelines, reports, manifests, or annotations.

Exit gate: target a 20–28 minute cold run for a 25-minute episode and 0.2–0.4
GiB of derived data for a 30-minute job. Every optimization must pass timeline,
sync, cut-report, XML, and held-out human-review comparisons. A speedup is
rejected if it materially worsens edit decisions.

### Milestone 5 - Reproducible one-folder Windows build

**Status (2026-08-13): IN PROGRESS; first inspectable build passes local
gates.** The audited one-folder prototype is 1,141,127,794 bytes (1,088.3 MiB)
across 5,764 files. It contains a self-contained WPF shell, 8.0-MiB supervisor,
separate neural engine, project-local offline model assets, and one FFmpeg plus
FFprobe pair. A real packaged cache-miss job loaded Community-1 offline, ran
neural inference, wrote reports/XML, and passed 450-frame validation. The
self-contained GUI real-XAML smoke and a warm cached worker-to-engine job also
pass. `bundle-audit-final.json` records every file's SHA-256 and reports zero
forbidden files.

The current prototype is not a public release: code signing, complete license
text resolution, clean-VM execution, and installer work remain. SpeechBrain,
PyTorch, torchaudio, scikit-learn, and OpenCV retain narrowly allowed runtime
source/Cython files required by their freezer hooks; PodEdit application source,
tokens, datasets, results, tests, and developer caches are absent.

After the latest worker/engine/settings rebuild, the candidate is 895.6 MiB and
the strengthened audit correctly fails on two missing required files: FFmpeg
and FFprobe. Recopying them from machine-wide Chocolatey was rejected by the
workspace-only rule. The last complete measured assembly remains the 1,088.3-
MiB figure above; the current build must not be called complete until approved
media binaries are placed inside the project and the audit is rerun.

**Estimate:** 3–7 workdays. **Build workspace:** 2–4 GiB. **Expected installed
payload:** first 0.8–1.2 GiB, then 0.6–0.9 GiB after pruning.

Deliverables:

- create a clean production-only dependency lock/environment; **audit/lock
  baseline complete, clean environment refinement pending**;
- freeze one worker executable and include exactly one FFmpeg/FFprobe runtime;
  **prototype complete using separate worker and neural-engine executables**;
- use explicit inclusions/exclusions and audit every file in the payload;
- keep models, caches, settings, jobs, and outputs outside immutable app files;
- generate a dependency/license inventory and third-party notices; **complete:
  132-package metadata audit, zero unresolved declarations, and 351 collated
  license/notice files included in the prototype**;
- verify that `.env`, tokens, datasets, historical results, source code,
  development libraries, and user-profile caches are absent;
- run the unpacked build on a clean Windows machine with no Python, FFmpeg, or
  pre-existing model cache.

Exit gate: the inspectable one-folder build completes the same smoke job and
produces equivalent validated output. Its measured contents become the only
source for installer sizing; no historical v9 build configuration is reused.

### Milestone 6 - Installer, security, licensing, and updates

**Status (2026-08-13): STARTED.** `packaging/PodEdit.iss` defines a per-user,
non-elevated conventional installer with stable upgrade identity, preserved
user data, optional desktop shortcut, and gated internal-only model inclusion.
`SECURITY_AND_UPDATE_POLICY.md` defines signing, integrity, stable/beta,
rollback, and no-update-during-job rules. Release and CycloneDX manifests are
generated. No installer compiler or signing tool is installed, so compilation,
Authenticode signing, upgrade/repair/uninstall tests, and clean-VM validation
remain open.

**Estimate:** 5–10 workdays. **Expected compressed installer:** 0.35–0.75 GiB
for the PyTorch edition, subject to Milestone 5 measurements.

Deliverables:

- decide full-offline versus first-run model provisioning after verifying model
  redistribution conditions; label network requirements honestly;
- select per-user or per-machine installation, writable-data locations,
  shortcuts, file associations if useful, repair, upgrade, and uninstall;
- choose MSIX/Store or a signed conventional installer from the actual update
  and distribution requirements;
- sign executables and installer, verify hashes, and produce an SBOM/release
  manifest;
- ensure uninstall preserves user projects by default and clearly offers
  optional cache removal;
- define stable/beta update channels and rollback behavior.

Exit gate: install, upgrade, repair, and uninstall pass under a standard user;
no credential or personal media enters the package; an offline installation
works exactly as advertised.

### Milestone 7 - Release-candidate QA and public beta

2026-09-02 review-rendering improvement: unlimited default cut coverage with
eight-cut batches, atomic publication, and cleaned project-local scratch media.
The real two-batch smoke matches audio/video duration exactly at 3.000 s.

**Estimate:** 7–15 workdays plus access to test editors and machines.
**QA storage:** 4–10 GiB excluding source videos.

**Status (2026-08-20): in progress.** `release_qa.py` now executes the offline
test suite, environment doctor, canonical segment/XML validation, content-based
reference fingerprint comparison, bundle audit, paper-source check, and exact
storage measurement into `results/release_qa/qa_report.json`. The current run
passes 112 tests. The workspace candidate remains blocked because it lacks its
project-local FFmpeg and FFprobe binaries and predates the new source-freshness
fingerprint required to prove frozen executables match current source.
Malformed timeline data, read-only/Unicode/long output paths, provisioned model
locations, real child-process cancellation, checkpoint reuse, and deterministic
canonical artifacts now have automated regression coverage. Clean-machine,
NLE-import, signing, and independent all-cuts reviews remain external gates.
Existing-but-corrupt or silent media and invalid typed job options are now
rejected before the engine starts.

Test matrix:

- clean Windows 11 x64, standard-user permissions, Windows Defender enabled;
- Unicode, spaces, long paths, removable drives, low disk, read-only outputs,
  missing/corrupt inputs, and interrupted/corrupt checkpoints;
- cancellation during every stage, application restart, retry, and resume;
- mixed frame rates, variable frame rate where support is claimed, differing
  resolutions, long episodes, weak/noisy audio, overlap, and silence;
- DaVinci Resolve XML import and Premiere Pro compatibility on supported paths;
- cold/warm performance, peak RAM, disk use, deterministic manifests, and
  comparison with locked reference outputs.

Exit gate: no open release-blocking defects; automated, packaging, security,
and clean-machine tests pass; known limitations and recovery instructions are
documented; at least three independent episodes receive complete all-cuts
human review. This produces the signed public beta candidate.

### Milestone 8 - Optional ONNX lean edition

**Estimate:** 15–40 workdays after Milestone 7. **Experiment space:** 4–8 GiB.

Export supported neural components to ONNX, establish floating-point parity,
then test dynamic/static quantization. Compare diarization, identity stitching,
camera cuts, runtime, RAM, and CPU support against the locked PyTorch backend.
Ship it only if accuracy gates pass. The objective is a 0.3–0.55 GiB installed
application, not a smaller package obtained by weakening results.

### Parallel academic-validation track

**Calendar estimate:** 2–6+ weeks, largely dependent on people and datasets.

- freeze an evaluation protocol before tuning further;
- obtain at least two independent editor annotations on multiple episodes;
- calculate cut-boundary precision/recall with stated tolerance, camera-choice
  agreement, screen-time error, inter-editor agreement, and runtime/resource
  metrics;
- record failures and ablations, preserve raw observations, and regenerate all
  paper tables/figures from scripts;
- update the IEEE manuscript only with reproducible measurements and qualify
  claims where the dataset remains small.

The evaluator now supports this protocol directly. `--make-blind-sheet` hides
PodEdit's cameras and boundaries so editors define independent intervals;
repeated `--reference` arguments produce per-editor and macro system metrics,
pairwise boundary F1, and duration-weighted Cohen's kappa. Same-camera CSV row
splits are fused rather than counted as cuts, and incomplete/gapped timelines
are rejected. The former proposal-aligned sheet remains useful for correction
but is explicitly excluded from publication-grade agreement claims.

This track blocks claims such as “human-equivalent editing,” but it does not
block the internal desktop beta.

## Processing optimization

The 25-minute cold neural path is now optimized and measured. Previously it
spent 1222.0 s on ranged windows plus 1073.4 s recomputing the same neural
front end for exact-count confirmations. PodEdit now captures pyannote's public
segmentation/embedding hook artifacts and evaluates exact-two clustering from
those features, with an automatic full-pass fallback when artifacts are
unavailable. A clean isolated benchmark completed in 1249.6 s (20.83 min): all
29 confirmations together took 2.38 s, retained the same 2 accepted and 27
rejected decisions, and reproduced all 596 canonical turns exactly, including
their normalized JSON SHA-256. This passes the 20–28 minute neural-runtime
target; full worker time still includes visual mapping and optional renders.

Next targets are replacing librosa paths that pull in Numba/LLVM, using
headless OpenCV, controlling PyTorch thread oversubscription, and rendering the
312-second all-cuts reel only on demand. ONNX/INT8 is a later backend, not a
packaging trick; quantization can change accuracy and requires held-out
validation.

## Disk-space estimate

Measured installed-development components currently include approximately
489.9 MiB of PyTorch, 116.2 MiB of LLVM, 108.6 MiB of OpenCV, 108.3 MiB of
SciPy, 40.0 MiB of scikit-learn, and only 31.3 MiB of project-local model
assets. The runtime, not the model download, is the principal size constraint.

| Product form | Estimated installed size | Estimated installer |
|---|---:|---:|
| Clean current PyTorch backend with polished GUI | 0.8–1.2 GiB | 0.45–0.75 GiB |
| Pruned PyTorch backend after audio/dependency cleanup | 0.6–0.9 GiB | 0.35–0.55 GiB |
| Validated ONNX/ORT backend | 0.3–0.55 GiB | 0.18–0.35 GiB |

These are engineering ranges, not promises. The unpacked one-folder payload
must be measured before selecting installer compression.

After compacting the synchronization-only track, the complete 25-minute
canonical job measures 336.1 MiB. Camera 2 audio fell from 288,000,078 to
48,000,078 bytes while a full 300-second correlation reproduced the exact
-0.980952-s offset and 58.367x confidence. The 0.2–0.4 GiB derived-data target
is therefore achieved for this fixture without removing the edit's 48-kHz
stereo master. The application should still check for at least 2 GiB free per
active episode and recommend 4 GiB when review rendering is enabled. Source
video storage is additional.

Packaging development needs roughly 2–4 GiB of temporary space for an unpacked
runtime, analysis output, compressed installer, and clean-machine artifacts.
ONNX experimentation should reserve 4–8 GiB because PyTorch and multiple model
variants must coexist until parity is proven.

## Distribution constraints

- Never package `.env`, personal tokens, user caches, datasets, test results, or
  development libraries.
- Bundle exactly one FFmpeg/FFprobe runtime and document its license.
- Start with an inspectable one-folder frozen build; do not begin with a
  self-extracting one-file executable.
- Verify Community-1 model access, CC-BY-4.0 attribution, and redistribution
  conditions before including weights in a public installer.
- Sign production installers. MSIX requires a trusted signature; Store
  distribution can provide signing and update infrastructure.
- Test without Python, FFmpeg, developer tools, or pre-existing model caches,
  and with Windows Defender and standard-user permissions enabled.

## Cleanup status

On 2026-08-12, the obsolete v9 frozen `dist/` and `build/`, its spec/helper/log,
and ordinary temp/cache debris were deleted. This removed 1,570,889,866 bytes
(1.463 GiB). Academic sources, paper files, documentation, datasets, current
model cache, virtual environment, canonical v1.5 result, and reviewed-v1.5
bundle were preserved.

With explicit approval for Option A, 16 redundant historical WAVs were then
deleted, reclaiming another 4,082,551,022 bytes (3.802 GiB). Canonical and
reviewed-v1.5 results, all small JSON/CSV/XML/manifest evidence, and all preview
media were retained. Approximately 38,318,386 bytes of superseded preview media
remain outside the canonical result; removing those videos still requires
separate approval because they may be useful as historical academic evidence.

## References

[1] PyInstaller Development Team, "Using PyInstaller," *PyInstaller 6.21.0
Documentation*. Available: https://pyinstaller.org/en/stable/usage.html

[2] Microsoft, "Choose a distribution path for your Windows app," *Windows App
Development Documentation*. Available:
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/choose-distribution-path

[3] Microsoft, "Sign an MSIX package," *MSIX Documentation*. Available:
https://learn.microsoft.com/en-us/windows/msix/package/signing-package-overview

[4] Microsoft, "Quantize ONNX models," *ONNX Runtime Documentation*. Available:
https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html

[5] pyannote, "speaker-diarization-community-1," *Hugging Face Model Card*.
Available: https://huggingface.co/pyannote/speaker-diarization-community-1

[6] Microsoft, "Windows App SDK deployment overview," *Windows App
Development Documentation*. Available:
https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/deploy-overview
