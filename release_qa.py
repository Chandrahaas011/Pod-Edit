"""Run PodEdit's local release-candidate gates and write one auditable report."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

from pipeline.bundle_audit import audit as audit_bundle
from pipeline.reproducibility import compare_fingerprints, fingerprint_manifest
from pipeline.source_identity import compare_source_fingerprints, fingerprint_sources
from pipeline.validator import validate_segments, validate_xml


ROOT = Path(__file__).resolve().parent


def _tree_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _command(name: str, command: list[str]) -> dict:
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
    return {"name": name, "passed": completed.returncode == 0,
            "exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-4000:]}


def _pending_gates(statuses: dict[str, str]) -> list[str]:
    return [name for name, status in statuses.items() if status != "passed"]


def _paper_sources_match(markdown_path: Path, tex_path: Path) -> tuple[bool, str | None]:
    markdown = markdown_path.read_text(encoding="utf-8")
    match = re.search(r"```latex\s*\n(.*?)\n```", markdown, flags=re.DOTALL)
    if match is None:
        return False, "research paper.md has no fenced latex block"
    embedded = match.group(1).replace("\r\n", "\n").rstrip("\n")
    standalone = tex_path.read_text(encoding="utf-8").replace("\r\n", "\n").rstrip("\n")
    return (embedded == standalone,
            None if embedded == standalone else "Markdown and standalone LaTeX differ")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="results/release_qa/qa_report.json")
    parser.add_argument("--bundle", default="packaging/build/engine/PodEdit.Engine")
    parser.add_argument("--canonical", default="results/variable_speaker_25min")
    args = parser.parse_args()

    bundle = (ROOT / args.bundle).resolve()
    canonical = (ROOT / args.canonical).resolve()
    checks = [
        _command("python-tests", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"]),
        _command("environment-doctor", [sys.executable, "doctor.py"]),
    ]
    try:
        segments = json.loads((canonical / "podedit_segments.json").read_text(encoding="utf-8"))
        segment_result = validate_segments(segments, 1500.0)
        xml_result = validate_xml(str(canonical / "podedit_timeline.xml"))
        if xml_result.get("duration_frames") != 45000:
            xml_result.setdefault("errors", []).append(
                f"expected 45000 frames, found {xml_result.get('duration_frames')}")
            xml_result["valid"] = False
        checks.append({"name": "canonical-output", "passed": bool(
            segment_result.get("valid") and xml_result.get("valid")),
            "segments": segment_result, "xml": xml_result})
    except (OSError, ValueError, TypeError) as exc:
        checks.append({"name": "canonical-output", "passed": False, "error": str(exc)})

    try:
        baseline_path = canonical / "reproducibility_fingerprint.json"
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        current = fingerprint_manifest(canonical / "run_manifest.json")
        comparison = compare_fingerprints(baseline, current)
        checks.append({"name": "canonical-reproducibility",
                       "passed": comparison["matches"], **comparison,
                       "baseline": str(baseline_path)})
    except (OSError, ValueError, TypeError, KeyError) as exc:
        checks.append({"name": "canonical-reproducibility", "passed": False,
                       "error": str(exc)})

    bundle_result = audit_bundle(bundle) if bundle.is_dir() else {
        "passed": False, "error": f"bundle not found: {bundle}"}
    checks.append({"name": "bundle-integrity", **bundle_result})
    try:
        source_baseline_path = bundle / "_internal" / "source-fingerprint.json"
        source_baseline = json.loads(source_baseline_path.read_text(encoding="utf-8"))
        source_comparison = compare_source_fingerprints(
            source_baseline, fingerprint_sources(ROOT))
        checks.append({"name": "bundle-source-freshness",
                       "passed": source_comparison["matches"], **source_comparison,
                       "baseline": str(source_baseline_path)})
    except (OSError, ValueError, TypeError, KeyError) as exc:
        checks.append({"name": "bundle-source-freshness", "passed": False,
                       "error": "Freeze source fingerprint is missing or invalid: " + str(exc)})
    paper_files = [ROOT / "research paper.md", ROOT / "paper" / "podedit_ieee_overleaf.tex"]
    try:
        paper_match, paper_error = _paper_sources_match(*paper_files)
    except OSError as exc:
        paper_match, paper_error = False, str(exc)
    checks.append({"name": "paper-sources", "passed": paper_match,
                   "error": paper_error, "files": [str(path) for path in paper_files]})
    protocol = ROOT / "ANNOTATION_PROTOCOL.md"
    blind_template = canonical / "human_annotation_blind_template.csv"
    try:
        template_text = blind_template.read_text(encoding="utf-8-sig")
        academic_assets_pass = (protocol.is_file()
                                and "predicted_camera" not in template_text
                                and "reference_camera" in template_text)
    except OSError:
        academic_assets_pass = False
    checks.append({"name": "academic-evaluation-assets", "passed": academic_assets_pass,
                   "files": [str(protocol), str(blind_template)]})

    blockers = [check["name"] for check in checks if not check.get("passed")]
    external_gates = {
        "clean_windows_vm": "pending", "authenticode_signing": "pending",
        "resolve_and_premiere_import": "pending-human-verification",
        "three_episode_all_cuts_review": "pending-human-study",
    }
    external_blockers = _pending_gates(external_gates)
    report = {
        "schema_version": 2, "created_utc": datetime.now(timezone.utc).isoformat(),
        "local_gates_passed": not blockers,
        "release_ready": not blockers and not external_blockers,
        "blocking_checks": blockers,
        "external_blocking_gates": external_blockers,
        "checks": checks,
        "storage": {"project_bytes": _tree_size(ROOT),
                    "bundle_bytes": _tree_size(bundle) if bundle.is_dir() else None,
                    "canonical_result_bytes": _tree_size(canonical) if canonical.is_dir() else None},
        "external_gates": external_gates,
    }
    output = (ROOT / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Local release QA: {'PASS' if report['local_gates_passed'] else 'BLOCKED'}; "
          f"blocking checks: {', '.join(blockers) or 'none'}")
    print(f"Release readiness: {'PASS' if report['release_ready'] else 'BLOCKED'}; "
          f"external gates: {', '.join(external_blockers) or 'none'}")
    print(f"Report: {output}")
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
