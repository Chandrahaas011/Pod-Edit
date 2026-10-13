from pathlib import Path
import tempfile
import unittest

from pipeline.diarization_cache import load_completed_turns, save_completed_turns
from pipeline.run_request import RunRequest


def _request(*, duration=60, cosine=0.7) -> RunRequest:
    return RunRequest(
        camera1="one.mp4", camera2="two.mp4", output="out", mode="hybrid",
        num_speakers=2, max_duration=duration, swap=False, force=False,
        diarization_strategy="windowed", diarization_window=60,
        diarization_overlap=15, second_speaker_max_cosine=cosine,
        sync_offset=None, no_preview=True, preview_start=None,
        editorial_profile="balanced", no_reactions=False, max_primary_shot=60,
        timeline_fps=30, offline=True, cancel_file=None,
    )


class DiarizationCacheTests(unittest.TestCase):
    def test_round_trip_requires_exact_inference_identity(self):
        signature = {"path": "one.mp4", "size": 10, "mtime_ns": 20, "edge_sha256": "abc"}
        turns = [{"start": 0, "end": 1, "speaker": "A"}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw_turns.json"
            save_completed_turns(path, _request(), signature, turns, {"ok": True},
                                 model="model", stitching_version=6)
            loaded = load_completed_turns(path, _request(), signature,
                                          model="model", stitching_version=6)
            changed = load_completed_turns(path, _request(cosine=0.6), signature,
                                           model="model", stitching_version=6)
        self.assertEqual(loaded, (turns, {"ok": True}))
        self.assertIsNone(changed)

    def test_corrupt_cache_is_a_safe_miss(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "raw_turns.json"
            path.write_text("not json", encoding="utf-8")
            self.assertIsNone(load_completed_turns(
                path, _request(), {}, model="model", stitching_version=6))
