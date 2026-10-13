from pathlib import Path
import tempfile
import unittest

from evaluate import create_blind_annotation_sheet, load_reference_csv


class EvaluationWorkflowTests(unittest.TestCase):
    def test_reference_loader_fuses_same_camera_rows(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = Path(temporary) / "editor.csv"
            path.write_text("start_seconds,end_seconds,reference_camera,notes\n"
                            "0,3,1,\n3,5,1,\n5,10,2,\n", encoding="utf-8")
            segments = load_reference_csv(str(path))
        self.assertEqual(segments, [{"start": 0.0, "duration": 5.0, "camera": 1},
                                    {"start": 5.0, "duration": 5.0, "camera": 2}])

    def test_blind_sheet_does_not_expose_predicted_camera_or_cuts(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = Path(temporary) / "blind.csv"
            create_blind_annotation_sheet(10.0, str(path))
            text = path.read_text(encoding="utf-8-sig")
        self.assertNotIn("predicted_camera", text)
        self.assertIn("0.000,10.000", text)

    def test_incomplete_reference_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = Path(temporary) / "incomplete.csv"
            path.write_text("start_seconds,end_seconds,reference_camera,notes\n"
                            "0,8,1,\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ends at"):
                load_reference_csv(str(path), expected_duration=10.0)
