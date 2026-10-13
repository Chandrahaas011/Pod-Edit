import unittest

from pipeline.editor import build_editorial_segments


class EditorialPolicyTests(unittest.TestCase):
    def test_backchannel_does_not_steal_camera(self):
        turns = [
            {"speaker": "A", "start": 0.0, "end": 10.0},
            {"speaker": "B", "start": 3.0, "end": 3.4},
        ]
        segments, diagnostics = build_editorial_segments(turns, {"A": 1, "B": 2}, 10.0)
        self.assertEqual(segments, [{"start": 0.0, "duration": 10.0, "camera": 1}])
        self.assertGreaterEqual(diagnostics["final_segments"], 1)

    def test_sustained_takeover_switches(self):
        turns = [
            {"speaker": "A", "start": 0.0, "end": 5.0},
            {"speaker": "B", "start": 5.2, "end": 10.0},
        ]
        segments, _ = build_editorial_segments(turns, {"A": 1, "B": 2}, 10.0)
        self.assertEqual([item["camera"] for item in segments], [1, 2])
        self.assertAlmostEqual(sum(item["duration"] for item in segments), 10.0)
        self.assertLess(segments[1]["start"], 5.2)

    def test_overlap_holds_current_floor(self):
        turns = [
            {"speaker": "A", "start": 0.0, "end": 6.0},
            {"speaker": "B", "start": 4.0, "end": 9.0},
        ]
        segments, _ = build_editorial_segments(turns, {"A": 1, "B": 2}, 9.0)
        self.assertEqual([item["camera"] for item in segments], [1, 2])
        self.assertGreaterEqual(segments[1]["start"], 5.8)


if __name__ == "__main__":
    unittest.main()
