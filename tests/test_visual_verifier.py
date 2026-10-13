import unittest

from pipeline.visual_verifier import _cliffs_delta, _pick_sample_times


class VisualVerifierTests(unittest.TestCase):
    def test_cliffs_delta_has_expected_direction(self):
        self.assertEqual(_cliffs_delta([3, 4], [1, 2]), 1.0)
        self.assertEqual(_cliffs_delta([1, 2], [3, 4]), -1.0)
        self.assertEqual(_cliffs_delta([1, 2], [1, 2]), 0.0)

    def test_long_turn_centers_are_preferred(self):
        turns = [
            {"start": 0.0, "end": 4.0},
            {"start": 5.0, "end": 9.0},
            {"start": 10.0, "end": 14.0},
            {"start": 15.0, "end": 19.0},
            {"start": 20.0, "end": 24.0},
            {"start": 25.0, "end": 29.0},
            {"start": 30.0, "end": 34.0},
            {"start": 35.0, "end": 39.0},
            {"start": 40.0, "end": 40.8},
        ]
        self.assertEqual(_pick_sample_times(turns),
                         [2.0, 7.0, 12.0, 17.0, 22.0, 27.0, 32.0, 37.0])


if __name__ == "__main__":
    unittest.main()
