from pathlib import Path
import tempfile
import unittest

from pipeline.job_storage import inventory_job, remove_items


class JobStorageTests(unittest.TestCase):
    def test_inventory_ignores_unknown_files_and_reports_known_categories(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "podedit_preview.mp4").write_bytes(b"preview")
            (root / "podedit_timeline.xml").write_bytes(b"keep")
            items = inventory_job(root)
            self.assertEqual([(item.category, item.bytes) for item in items],
                             [("review-media", 7)])

    def test_removal_is_category_scoped_and_preserves_timeline(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "camera2_audio.wav").write_bytes(b"audio")
            (root / "podedit_timeline.xml").write_bytes(b"timeline")
            count, reclaimed = remove_items(root, {"derived-audio"})
            self.assertEqual((count, reclaimed), (1, 5))
            self.assertTrue((root / "podedit_timeline.xml").exists())

    def test_unknown_category_is_rejected_before_deletion(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            with self.assertRaises(ValueError):
                remove_items(temporary, {"everything"})
