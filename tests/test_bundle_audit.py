from pathlib import Path
import tempfile
import unittest

from pipeline.bundle_audit import audit


class BundleAuditTests(unittest.TestCase):
    def test_forbidden_source_and_tokens_fail_audit(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "app.exe").write_bytes(b"app")
            (root / ".env").write_text("secret", encoding="utf-8")
            report = audit(root)
            self.assertFalse(report["passed"])
            self.assertIn(".env", report["forbidden"])

    def test_binary_only_folder_passes_with_hashes(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            from pipeline.bundle_audit import REQUIRED_FILES
            for relative in REQUIRED_FILES:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"app")
            report = audit(root)
            self.assertTrue(report["passed"])
            self.assertEqual(len(report["files"][0]["sha256"]), 64)

    def test_missing_media_tools_fail_release_gate(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            report = audit(Path(temporary))
            self.assertIn("tools/ffmpeg/bin/ffmpeg.exe", report["missing_required"])
