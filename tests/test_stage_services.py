from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.run_layout import RunLayout
from pipeline.run_request import RunRequest
from pipeline.stage_services import extract_source_audio, probe_sources, resolve_sync


def _request(root: str, *, sync_offset=None) -> RunRequest:
    return RunRequest(
        camera1="one.mp4", camera2="two.mp4", output=root, mode="hybrid",
        num_speakers=2, max_duration=10, swap=False, force=False,
        diarization_strategy="windowed", diarization_window=60, diarization_overlap=15,
        second_speaker_max_cosine=0.7, sync_offset=sync_offset, no_preview=True,
        preview_start=None, editorial_profile="balanced", no_reactions=False,
        max_primary_shot=60, timeline_fps=30, offline=True, cancel_file=None,
    )


class StageServiceTests(unittest.TestCase):
    @patch("pipeline.audio_extractor.extract_audio")
    def test_secondary_sync_audio_uses_compact_mono_format(self, extract):
        with tempfile.TemporaryDirectory() as temporary:
            layout = RunLayout.create(temporary)
            extract_source_audio(_request(temporary), layout, lambda _: None)
        self.assertEqual(extract.call_count, 2)
        self.assertEqual(extract.call_args_list[1].kwargs["sample_rate"], 16000)
        self.assertEqual(extract.call_args_list[1].kwargs["channels"], 1)

    @patch("pipeline.probe.probe_video")
    def test_probe_sources_keeps_two_distinct_camera_metadata(self, probe):
        probe.side_effect = [{"fps": 25}, {"fps": 30}]
        first, second = probe_sources(_request("output"))
        self.assertEqual((first["fps"], second["fps"]), (25, 30))

    @patch("pipeline.sync_engine.estimate_offset")
    def test_manual_sync_skips_estimator_and_writes_atomic_metrics(self, estimator):
        with tempfile.TemporaryDirectory() as temporary:
            layout = RunLayout.create(temporary)
            result = resolve_sync(_request(temporary, sync_offset=-0.98), layout, lambda _: None)
            self.assertTrue(layout.sync_metrics.is_file())
        estimator.assert_not_called()
        self.assertEqual(result["source"], "manual-override")

    def test_cancel_is_checked_before_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            layout = RunLayout.create(temporary)
            with self.assertRaisesRegex(RuntimeError, "stop"):
                resolve_sync(_request(temporary), layout, lambda _: (_ for _ in ()).throw(RuntimeError("stop")))
