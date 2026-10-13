from pathlib import Path
import tempfile
import unittest

from pipeline.run_layout import RunLayout


class RunLayoutTests(unittest.TestCase):
    def test_create_makes_only_root_and_keeps_artifact_names_under_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "export with spaces"
            layout = RunLayout.create(root)
            self.assertTrue(root.is_dir())
            self.assertEqual(layout.root, root)
            self.assertEqual(layout.camera1_audio.parent, root)
            self.assertEqual(layout.timeline_xml.parent, root)
            self.assertEqual(layout.diarization_windows.parent, root)
            self.assertFalse(layout.camera1_audio.exists())
            self.assertFalse(layout.diarization_windows.exists())
