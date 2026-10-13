from pathlib import Path
import json
import tempfile
import unittest

from release_qa import ROOT, _paper_sources_match, _pending_gates, _tree_size
from pipeline.reproducibility import compare_fingerprints, fingerprint_manifest
from pipeline.validator import validate_xml


class ReleaseQaTests(unittest.TestCase):
    def test_tree_size_counts_nested_files_exactly(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "nested").mkdir()
            (root / "one.bin").write_bytes(b"123")
            (root / "nested" / "two.bin").write_bytes(b"4567")
            self.assertEqual(_tree_size(root), 7)

    def test_canonical_xml_validator_reports_locked_frame_count(self):
        result = validate_xml("results/variable_speaker_25min/podedit_timeline.xml")
        self.assertTrue(result["valid"], result["errors"])
        self.assertEqual(result["duration_frames"], 45000)

    def test_canonical_fingerprint_matches_current_artifacts(self):
        canonical = ROOT / "results" / "variable_speaker_25min"
        baseline = json.loads(
            (canonical / "reproducibility_fingerprint.json").read_text(encoding="utf-8"))
        current = fingerprint_manifest(canonical / "run_manifest.json")
        self.assertTrue(compare_fingerprints(baseline, current)["matches"])

    def test_pending_external_gates_are_not_release_ready(self):
        statuses = {"clean_vm": "passed", "human_review": "pending-human-study"}
        self.assertEqual(_pending_gates(statuses), ["human_review"])

    def test_markdown_and_standalone_paper_sources_match(self):
        matched, error = _paper_sources_match(
            ROOT / "research paper.md", ROOT / "paper" / "podedit_ieee_overleaf.tex")
        self.assertTrue(matched, error)

    def test_canonical_blind_template_hides_machine_decisions(self):
        text = (ROOT / "results" / "variable_speaker_25min" /
                "human_annotation_blind_template.csv").read_text(encoding="utf-8-sig")
        self.assertIn("reference_camera", text)
        self.assertNotIn("predicted_camera", text)
