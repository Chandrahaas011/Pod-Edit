import unittest

from pipeline.reactions import (_fuse_adjacent, _processing_seams,
                                _select_reaction_candidate)


class ReactionPolicyTests(unittest.TestCase):
    def test_fuses_only_contiguous_same_camera_parts(self):
        parts = [
            {"start": 0.0, "duration": 10.0, "camera": 1},
            {"start": 10.0, "duration": 5.0, "camera": 1},
            {"start": 15.0, "duration": 4.0, "camera": 2},
        ]
        self.assertEqual(_fuse_adjacent(parts), [
            {"start": 0.0, "duration": 15.0, "camera": 1},
            {"start": 15.0, "duration": 4.0, "camera": 2},
        ])

    def test_processing_seams_match_retained_window_boundaries(self):
        self.assertEqual(_processing_seams(150.0, 60.0, 15.0),
                         [52.5, 97.5, 142.5])

    def test_reaction_candidate_avoids_window_seam_when_safe_option_exists(self):
        selected = _select_reaction_candidate(
            [{"time": 52.4, "motion": 0.0, "audio_rms": 0.0},
             {"time": 50.0, "motion": 10.0, "audio_rms": 0.5}],
            desired=52.5, search_radius=6.0, seams=[52.5],
            seam_guard_seconds=1.0)
        self.assertEqual(selected["time"], 50.0)
        self.assertGreaterEqual(selected["nearest_window_seam_seconds"], 1.0)

    def test_audio_pause_breaks_equal_motion_tie(self):
        selected = _select_reaction_candidate(
            [{"time": 50.0, "motion": 0.0, "audio_rms": 0.2},
             {"time": 54.0, "motion": 0.0, "audio_rms": 0.01}],
            desired=52.0, search_radius=6.0, seams=[])
        self.assertEqual(selected["time"], 54.0)

    def test_motion_outweighs_audio_when_both_differ(self):
        selected = _select_reaction_candidate(
            [{"time": 50.0, "motion": 0.0, "audio_rms": 0.2},
             {"time": 54.0, "motion": 1.0, "audio_rms": 0.01}],
            desired=52.0, search_radius=6.0, seams=[])
        self.assertEqual(selected["time"], 50.0)


if __name__ == "__main__":
    unittest.main()
