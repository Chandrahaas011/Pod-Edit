from pathlib import Path
import tempfile
import unittest

from pipeline.run_layout import RunLayout
from pipeline.run_manifest import build_manifest
from pipeline.run_request import RunRequest


def _request(root: Path, *, no_preview: bool) -> RunRequest:
    return RunRequest(
        camera1="one.mp4", camera2="two.mp4", output=str(root), mode="hybrid",
        num_speakers=2, max_duration=120, swap=False, force=False,
        diarization_strategy="windowed", diarization_window=60,
        diarization_overlap=15, second_speaker_max_cosine=0.7,
        sync_offset=None, no_preview=no_preview, preview_start=None,
        editorial_profile="balanced", no_reactions=False, max_primary_shot=60,
        timeline_fps=30, offline=True, cancel_file=None,
    )


class RunManifestTests(unittest.TestCase):
    def test_manifest_derives_artifacts_from_layout_and_keeps_metrics_consistent(self):
        with tempfile.TemporaryDirectory() as temporary:
            layout = RunLayout.create(temporary)
            manifest = build_manifest(
                _request(layout.root, no_preview=True), layout,
                inputs={"camera1": {"size": 1}}, sync={"offset_seconds": 0},
                diarization_diagnostics={}, speaker_to_camera={"A": 1},
                mapping_diagnostics={}, editorial_diagnostics={}, reaction_diagnostics={},
                cut_report_summary={}, segment_validation={"valid": True},
                xml_validation={"valid": True}, runtime_seconds=3.0,
                stage_seconds={"probe": 0.25, "diarize": 2.0}, duration_seconds=120.0,
                segments=[{"duration": 20}, {"duration": 100}],
                camera_screen_time_seconds={1: 120.0, 2: 0.0},
            )
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["metrics"]["cuts_per_minute"], 0.5)
        self.assertEqual(manifest["metrics"]["maximum_shot_seconds"], 100)
        self.assertEqual(manifest["metrics"]["stage_seconds"]["diarize"], 2.0)
        self.assertAlmostEqual(manifest["metrics"]["unattributed_seconds"], 0.75)
        self.assertEqual(manifest["metrics"]["real_time_factor"], 0.025)
        self.assertIsNone(manifest["outputs"]["preview"])
        self.assertTrue(manifest["outputs"]["xml"].endswith("podedit_timeline.xml"))
