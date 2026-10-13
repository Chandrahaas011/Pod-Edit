import unittest

from evaluation.metrics import (cut_boundary_metrics, duration_weighted_cohen_kappa,
                                evaluate_edit, evaluate_multiple_references)


class MetricTests(unittest.TestCase):
    def test_perfect_edit(self):
        segments = [
            {"start": 0.0, "duration": 5.0, "camera": 1},
            {"start": 5.0, "duration": 5.0, "camera": 2},
        ]
        result = evaluate_edit(segments, segments, 10.0)
        self.assertEqual(result["camera_time"]["accuracy"], 1.0)
        self.assertEqual(result["cut_boundaries"]["f1"], 1.0)

    def test_boundary_tolerance(self):
        predicted = [{"start": 0, "duration": 5.2, "camera": 1},
                     {"start": 5.2, "duration": 4.8, "camera": 2}]
        reference = [{"start": 0, "duration": 5.0, "camera": 1},
                     {"start": 5.0, "duration": 5.0, "camera": 2}]
        result = evaluate_edit(predicted, reference, 10.0, 0.5)
        self.assertEqual(result["cut_boundaries"]["f1"], 1.0)
        self.assertAlmostEqual(result["camera_time"]["accuracy"], 0.98)

    def test_same_camera_row_boundaries_are_not_counted_as_cuts(self):
        rows = [{"start": 0, "duration": 3, "camera": 1},
                {"start": 3, "duration": 2, "camera": 1},
                {"start": 5, "duration": 5, "camera": 2}]
        result = cut_boundary_metrics(rows, rows)
        self.assertEqual(result["predicted_cuts"], 1)
        self.assertEqual(result["reference_cuts"], 1)

    def test_duration_weighted_kappa(self):
        first = [{"start": 0, "duration": 5, "camera": 1},
                 {"start": 5, "duration": 5, "camera": 2}]
        second = [{"start": 0, "duration": 5, "camera": 1},
                  {"start": 5, "duration": 5, "camera": 2}]
        self.assertEqual(duration_weighted_cohen_kappa(first, second, 10)["kappa"], 1.0)

    def test_multiple_references_report_pairwise_and_macro_metrics(self):
        predicted = [{"start": 0, "duration": 5, "camera": 1},
                     {"start": 5, "duration": 5, "camera": 2}]
        alternate = [{"start": 0, "duration": 6, "camera": 1},
                     {"start": 6, "duration": 4, "camera": 2}]
        result = evaluate_multiple_references(predicted, [predicted, alternate], 10, 1.0)
        self.assertEqual(result["editors"], 2)
        self.assertEqual(len(result["pairwise_agreement"]), 1)
        self.assertAlmostEqual(result["macro_camera_accuracy"], 0.95)


if __name__ == "__main__":
    unittest.main()
