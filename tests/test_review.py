import unittest

from pipeline.review import apply_cut_reviews, build_cut_report


class CutReportTests(unittest.TestCase):
    def test_flags_reaction_boundaries_and_window_seam(self):
        segments = [
            {"start": 0.0, "duration": 52.5, "camera": 1},
            {"start": 52.5, "duration": 4.0, "camera": 2},
            {"start": 56.5, "duration": 43.5, "camera": 1},
        ]
        report = build_cut_report(
            segments, 100.0, 30.0, {"margin": 0.08},
            {"selections": [{"start": 52.5, "duration": 4.0}]}, 60.0, 15.0)
        self.assertEqual(report["summary"]["cuts"], 2)
        self.assertEqual(report["cuts"][0]["cut_type"], "listener_reaction_in")
        self.assertIn("near_window_seam", report["cuts"][0]["flags"])
        self.assertEqual(report["cuts"][1]["cut_type"], "listener_reaction_out")
        self.assertEqual(report["summary"]["mapping_status"], "fallback_low_visual_margin")

    def test_same_owner_camera_votes_are_not_called_visual_verified(self):
        report = build_cut_report(
            [{"start": 0.0, "duration": 5.0, "camera": 1},
             {"start": 5.0, "duration": 5.0, "camera": 2}],
            10.0, 30.0, {"margin": 0.8, "camera_votes_consistent": False,
                         "accepted": False}, {}, 60.0, 15.0)
        self.assertEqual(report["summary"]["mapping_status"],
                         "fallback_inconsistent_visual_votes")

    def test_applies_move_and_camera_correction_without_overwriting_input(self):
        segments = [
            {"start": 0.0, "duration": 5.0, "camera": 1},
            {"start": 5.0, "duration": 5.0, "camera": 2},
            {"start": 10.0, "duration": 5.0, "camera": 1},
        ]
        rows = [
            {"cut_number": "1", "review_decision": "move",
             "corrected_time_seconds": "6.0", "corrected_to_camera": ""},
            {"cut_number": "2", "review_decision": "camera_wrong",
             "corrected_time_seconds": "", "corrected_to_camera": "2"},
        ]
        corrected, audit = apply_cut_reviews(segments, rows, 15.0)
        self.assertEqual(segments[0]["duration"], 5.0)
        self.assertEqual(corrected, [
            {"start": 0.0, "duration": 6.0, "camera": 1},
            {"start": 6.0, "duration": 9.0, "camera": 2},
        ])
        self.assertEqual(len(audit["applied"]), 2)

    def test_rejects_move_that_creates_tiny_shot(self):
        segments = [
            {"start": 0.0, "duration": 5.0, "camera": 1},
            {"start": 5.0, "duration": 5.0, "camera": 2},
        ]
        with self.assertRaises(ValueError):
            apply_cut_reviews(segments, [{"cut_number": "1", "review_decision": "move",
                                          "corrected_time_seconds": "0.1",
                                          "corrected_to_camera": ""}], 10.0)


if __name__ == "__main__":
    unittest.main()
