import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from pipeline.job_contract import JobSpec
from pipeline.preflight import PreflightIssue, inspect_source, run_preflight


class PreflightTests(unittest.TestCase):
    def _spec(self, root: str, *, offline: bool = False) -> JobSpec:
        camera1 = os.path.join(root, "camera one.mp4")
        camera2 = os.path.join(root, "camera two.mp4")
        for path in (camera1, camera2):
            Path(path).touch()
        return JobSpec.from_dict({
            "schema_version": 1,
            "camera1": camera1,
            "camera2": camera2,
            "output": os.path.join(root, "output", "job"),
            "options": {"offline": offline},
        })

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    def test_reports_missing_output_parent_without_importing_engine(self, _which):
        with tempfile.TemporaryDirectory() as temporary:
            issues = run_preflight(self._spec(temporary), temporary)
        self.assertIn("OUTPUT_PARENT_NOT_FOUND", {issue.code for issue in issues})

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    def test_offline_mode_requires_project_local_model_cache(self, _which):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "output").mkdir()
            issues = run_preflight(self._spec(temporary, offline=True), temporary)
        self.assertIn("OFFLINE_MODEL_CACHE_MISSING", {issue.code for issue in issues})

    @patch("pipeline.preflight.shutil.which", return_value=None)
    def test_missing_ffmpeg_is_a_stable_error(self, _which):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "output").mkdir()
            issues = run_preflight(self._spec(temporary), temporary)
        self.assertIn("FFMPEG_NOT_FOUND", {issue.code for issue in issues})

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    @patch("pipeline.preflight.shutil.disk_usage")
    def test_low_space_is_an_error(self, disk_usage, _which):
        disk_usage.return_value = shutil._ntuple_diskusage(10, 9, 1)
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "output").mkdir()
            issues = run_preflight(self._spec(temporary), temporary)
        self.assertIn("OUTPUT_DISK_LOW", {issue.code for issue in issues})

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    @patch("pipeline.preflight.tempfile.NamedTemporaryFile",
           side_effect=PermissionError("read-only fixture"))
    def test_read_only_output_is_rejected_before_processing(self, _temporary, _which):
        with tempfile.TemporaryDirectory() as temporary:
            Path(temporary, "output").mkdir()
            issues = run_preflight(self._spec(temporary), temporary)
        self.assertIn("OUTPUT_NOT_WRITABLE", {issue.code for issue in issues})

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    def test_unicode_long_paths_survive_preflight(self, _which):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            nested = root / ("épisode_播客_" + "x" * 80)
            nested.mkdir()
            output_parent = root / ("résultats_結果_" + "y" * 80)
            output_parent.mkdir()
            camera1 = nested / "caméra un 🎙.mp4"
            camera2 = nested / "相机二.mp4"
            camera1.touch(); camera2.touch()
            spec = JobSpec.from_dict({
                "schema_version": 1, "camera1": str(camera1), "camera2": str(camera2),
                "output": str(output_parent / "job"), "options": {}})
            self.assertEqual(run_preflight(spec, root), [])

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    @patch.dict(os.environ, {}, clear=True)
    def test_offline_preflight_respects_provisioned_model_location(self, _which):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            root = Path(temporary)
            (root / "output").mkdir()
            models = root / "per-user-models"
            models.mkdir()
            (models / "weights.bin").write_bytes(b"weights")
            os.environ["PODEDIT_MODEL_CACHE"] = str(models)
            issues = run_preflight(self._spec(str(root), offline=True), root)
        self.assertNotIn("OFFLINE_MODEL_CACHE_MISSING", {issue.code for issue in issues})

    def test_issue_is_a_small_gui_safe_value(self):
        issue = PreflightIssue("EXAMPLE", "Example", "warning")
        self.assertEqual((issue.code, issue.severity), ("EXAMPLE", "warning"))

    @patch("pipeline.preflight.shutil.which", return_value="C:/tools/media-tool.exe")
    def test_relative_paths_resolve_from_worker_root(self, _which):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "media").mkdir()
            (root / "output").mkdir()
            (root / "media" / "one.mp4").touch()
            (root / "media" / "two.mp4").touch()
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": "media/one.mp4",
                "camera2": "media/two.mp4",
                "output": "output/job",
            })
            self.assertEqual(run_preflight(spec, root), [])

    @patch("pipeline.preflight.subprocess.run")
    def test_ffprobe_metadata_is_normalized_for_the_gui(self, run):
        run.return_value.stdout = (
            '{"streams":[{"codec_type":"video","width":1280,"height":720,'
            '"avg_frame_rate":"30000/1001"},{"codec_type":"audio"}],'
            '"format":{"duration":"15.5"}}')
        result = inspect_source("camera.mp4")
        self.assertEqual((result["width"], result["height"]), (1280, 720))
        self.assertAlmostEqual(result["fps"], 29.970, places=3)
        self.assertEqual(result["duration_seconds"], 15.5)

    @patch("pipeline.preflight.subprocess.run")
    def test_ffprobe_output_without_video_stream_is_rejected(self, run):
        run.return_value.stdout = '{"streams":[],"format":{"duration":"15.5"}}'
        with self.assertRaisesRegex(ValueError, "no readable video stream"):
            inspect_source("corrupt.mp4")

    @patch("pipeline.preflight.subprocess.run")
    def test_ffprobe_zero_duration_is_rejected(self, run):
        run.return_value.stdout = (
            '{"streams":[{"codec_type":"video","width":1280,"height":720,'
            '"avg_frame_rate":"30/1"},{"codec_type":"audio"}],'
            '"format":{"duration":"0"}}')
        with self.assertRaisesRegex(ValueError, "invalid video"):
            inspect_source("empty.mp4")

    @patch("pipeline.preflight.subprocess.run")
    def test_video_without_audio_is_rejected_before_sync(self, run):
        run.return_value.stdout = (
            '{"streams":[{"codec_type":"video","width":1280,"height":720,'
            '"avg_frame_rate":"30/1"}],"format":{"duration":"15"}}')
        with self.assertRaisesRegex(ValueError, "no audio stream"):
            inspect_source("silent.mp4")
