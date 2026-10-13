from pathlib import Path
import tempfile
import unittest

from pipeline.source_identity import compare_source_fingerprints, fingerprint_sources


class SourceIdentityTests(unittest.TestCase):
    def test_source_change_is_reported(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "pipeline").mkdir()
            source = root / "pipeline" / "engine.py"
            source.write_text("one\n", encoding="utf-8")
            first = fingerprint_sources(root)
            source.write_text("two\n", encoding="utf-8")
            second = fingerprint_sources(root)
        result = compare_source_fingerprints(first, second)
        self.assertFalse(result["matches"])
        self.assertEqual(result["changed"], ["pipeline/engine.py"])

    def test_non_runtime_document_does_not_change_identity(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "pipeline").mkdir()
            (root / "pipeline" / "engine.py").write_text("one\n", encoding="utf-8")
            first = fingerprint_sources(root)
            (root / "notes.md").write_text("documentation\n", encoding="utf-8")
            second = fingerprint_sources(root)
        self.assertTrue(compare_source_fingerprints(first, second)["matches"])
