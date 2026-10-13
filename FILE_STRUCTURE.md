# PodEdit 1.5 Project Structure

Updated: 2026-09-18

```text
podedit/
|-- main.py                         production CLI
|-- worker.py                       typed job worker with JSONL progress events
|-- desktop/                        native Windows thin-client source
|   |-- PodEdit.Desktop/            WPF/.NET 9 application
|   `-- README.md                   isolated development-build instructions
|-- apply_review.py                 non-destructive human corrections
|-- evaluate.py                     annotation and metric workflow
|-- doctor.py                       environment diagnostics
|-- release_qa.py                   aggregated local release-candidate gates
|-- fingerprint_run.py              create/compare stable run fingerprints
|-- manage_storage.py               dry-run-first per-job retention controls
|-- packaging/                      reproducible Windows build/audit workspace
|   |-- PodEdit.Engine.spec         isolated neural-engine freezer definition
|   |-- PodEdit.Worker.spec         thin supervisor freezer definition
|   |-- audit_runtime.py            dependency/size/license metadata inventory
|   |-- audit_bundle.py             hash and forbidden-content release gate
|   |-- fingerprint_sources.py      pre-freeze runtime-source identity recorder
|   `-- build/engine/PodEdit.Engine/ inspectable one-folder prototype
|-- pipeline/                       maintained engine
|   |-- audio_io.py                 soundfile/soxr bounded mono loader
|   |-- audio_metadata.py           dependency-free PCM duration reader
|   |-- audio_extractor.py          bounded, fingerprinted configurable PCM extraction
|   |-- bundle_audit.py             tested release exclusion/hash policy
|   |-- cache.py                    signatures and atomic JSON caches
|   |-- cli_contract.py             shared CLI parser and cheap argument validation
|   |-- diarizer.py                 adaptive window diarization/reconciliation
|   |-- diarization_contract.py     lightweight neural cache/version identity
|   |-- diarization_cache.py        completed-turn cache identity and persistence
|   |-- stage_services.py           extracted probe/audio/sync engine stages
|   |-- editor.py                   deterministic camera-floor policy
|   |-- job_contract.py             versioned GUI-to-worker job schema
|   |-- job_storage.py              contained artifact inventory/removal policy
|   |-- job_control.py              cooperative cancellation boundaries
|   |-- mapper.py                   mapping orchestration/fallbacks
|   |-- reactions.py                seam-safe pause-aware listener cuts
|   |-- run_layout.py               typed output/checkpoint layout for one job
|   |-- run_manifest.py             auditable result-manifest construction
|   |-- run_request.py              typed engine request independent of argparse
|   |-- source_identity.py          frozen-build source freshness identity
|   |-- runtime.py                  cache, offline, and CPU runtime configuration
|   |-- preview.py                  preview and numbered review rendering
|                                   complete batched reels with atomic publication
|   |-- reproducibility.py          stable editorial artifact identity
|   |-- probe.py                    native source metadata
|   |-- review.py                   validated human-decision application
|   |-- segmenter.py                timeline segment normalization
|   |-- sync_engine.py              FFT audio cross-correlation
|   |-- validator.py                segment and XMEML invariants
|   |-- visual_verifier.py          sparse edge-motion identity evidence
|   `-- xml_builder.py              mixed-rate FCP XML 7 export
|-- tests/                          offline unit tests, including job-contract checks
|-- datasets/test_set_1/            primary 25/30-fps source pair
|-- results/variable_speaker_25min/ canonical v1.4 proposal and evidence
|   `-- reproducibility_fingerprint.json locked canonical artifact identity
|-- results/release_qa/             latest machine-readable QA report
|-- results/milestone4_shared_feature_benchmark/
|                                     cold optimization parity evidence
|-- results/variable_speaker_25min_reviewed_v14/
|                                     blank-review workflow smoke output
|-- output/pdf/podedit_ieee_2x2_authors.pdf current five-page, four-block manuscript
|-- output/pdf/podedit_ieee_overleaf.pdf older single-block PDF (viewer-locked)
|-- paper/
|   |-- podedit_ieee_overleaf.tex   standalone four-author IEEE source
|   |-- adaptive_timeline.png       optional same-directory Overleaf figure
|   `-- figures/                    publication figures and history
|-- README.md                       user and verification guide
|-- RELEASE_NOTES.md                release history and acceptance gates
|-- RELEASE_QA_MATRIX.md            local/external release evidence ledger
|-- ANNOTATION_PROTOCOL.md          blinded multi-editor evaluation procedure
|-- WINDOWS_PRODUCTIZATION_PLAN.md  Windows architecture, schedule and size plan
|-- HANDOFF.md                      current maintainer state
|-- VERSIONS_HISTORY.md             evidence-based architecture history
|-- research paper.md               complete fenced Overleaf LaTeX source
|-- research_paper.md               compatibility pointer to paper sources
`-- agents.md                       append-only technical learnings/references
```

The legacy `src/` scripts and old result directories are retained for research
traceability. They must not be mistaken for the production pipeline. Generated
media, model weights, the virtual environment, and historical experiments make
the repository large. No LaTeX compiler or TeX package cache is included.
