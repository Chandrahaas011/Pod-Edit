import json
from pathlib import Path
import tempfile
import unittest
import sys
from unittest.mock import patch

from pipeline.job_contract import JobSpec
from worker import _engine_command, run_preflight_job, run_worker
from pipeline.preflight import PreflightIssue


class WorkerTests(unittest.TestCase):
    def test_development_engine_command_uses_current_python_and_explicit_script(self):
        command = _engine_command(Path("fixture_engine.py"))
        self.assertEqual(command, [sys.executable, "fixture_engine.py"])

    def test_preflight_rejects_missing_media_before_process_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            output.mkdir()
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": str(root / "missing one.mp4"),
                "camera2": str(root / "missing two.mp4"),
                "output": str(output),
                "options": {},
            })
            self.assertEqual(run_worker(spec, events), 2)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[0]["type"], "job_started")
        self.assertIn("preflight_started", [record["type"] for record in records])
        rejected = [record for record in records if record["type"] == "job_rejected"]
        self.assertIn("INPUT_NOT_FOUND", {record["code"] for record in rejected})
        self.assertEqual(records[-1]["code"], "PREFLIGHT_FAILED")

    @patch("worker.subprocess.Popen")
    @patch("worker.inspect_source", side_effect=ValueError("corrupt fixture"))
    @patch("worker.run_preflight", return_value=[])
    def test_corrupt_existing_media_is_rejected_before_launch(self, _preflight, _inspect, popen):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            camera1 = root / "one.mp4"; camera1.touch()
            camera2 = root / "two.mp4"; camera2.touch()
            output = root / "output"; output.mkdir()
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1, "camera1": str(camera1), "camera2": str(camera2),
                "output": str(output),
            })
            self.assertEqual(run_worker(spec, events), 2)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        popen.assert_not_called()
        self.assertNotIn("preflight_completed", [item["type"] for item in records])
        self.assertEqual(records[-1]["code"], "PREFLIGHT_FAILED")
        self.assertEqual(sum(item.get("code") == "SOURCE_INSPECTION_FAILED"
                             for item in records), 2)

    @patch("worker.subprocess.Popen", side_effect=OSError("simulated launch failure"))
    @patch("worker.run_preflight", return_value=[])
    def test_worker_reports_child_launch_failure(self, _preflight, _popen):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": str(root / "one.mp4"),
                "camera2": str(root / "two.mp4"),
                "output": str(root / "output"),
            })
            self.assertEqual(run_worker(spec, events), 1)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[-1]["type"], "job_failed")
        self.assertEqual(records[-1]["error"], "simulated launch failure")

    def test_standalone_preflight_never_launches_the_engine(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": str(root / "missing one.mp4"),
                "camera2": str(root / "missing two.mp4"),
                "output": str(root / "output"),
            })
            self.assertEqual(run_preflight_job(spec, events), 2)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(records[0]["type"], "job_preflight_requested")
        self.assertNotIn("job_started", [record["type"] for record in records])

    @patch("worker.run_preflight", return_value=[])
    @patch("worker.subprocess.Popen")
    def test_worker_emits_completed_stages_in_order(self, popen, _preflight):
        class FakeProcess:
            stdout = iter([
                "  STAGE 1/2 - PROBING SOURCE VIDEOS\n",
                "  STAGE 2/2 - SEGMENT ASSEMBLY\n",
            ])

            @staticmethod
            def wait():
                return 0

        popen.return_value = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": str(root / "one.mp4"),
                "camera2": str(root / "two.mp4"),
                "output": str(root / "output"),
            })
            output = root / "output"
            output.mkdir()
            timeline = output / "timeline.xml"
            timeline.write_text("<xmeml/>\n", encoding="utf-8")
            (output / "run_manifest.json").write_text(
                json.dumps({"outputs": {"xml": str(timeline)}}), encoding="utf-8")
            self.assertEqual(run_worker(spec, events), 0)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        completed = [record for record in records if record["type"] == "stage_completed"]
        self.assertEqual([(item["stage"], item["progress"]) for item in completed],
                         [(1, 0.5), (2, 1.0)])
        artifacts = [record for record in records if record["type"] == "artifacts_available"]
        self.assertTrue(artifacts[0]["outputs"]["xml"].endswith("timeline.xml"))

    @patch("worker.run_preflight", return_value=[])
    @patch("worker.subprocess.Popen")
    def test_success_rejects_artifact_paths_outside_job_output(self, popen, _preflight):
        class FakeProcess:
            stdout = iter([])

            @staticmethod
            def wait():
                return 0

        popen.return_value = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            output.mkdir()
            outside = root / "outside.xml"
            outside.write_text("<xmeml/>\n", encoding="utf-8")
            (output / "run_manifest.json").write_text(
                json.dumps({"outputs": {"xml": str(outside)}}), encoding="utf-8")
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1, "camera1": "one.mp4", "camera2": "two.mp4",
                "output": str(output),
            })
            self.assertEqual(run_worker(spec, events), 0)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertNotIn("artifacts_available", [item["type"] for item in records])
        warnings = [item for item in records if item.get("code") == "ARTIFACT_MANIFEST_INVALID"]
        self.assertEqual(len(warnings), 1)

    @patch("worker.run_preflight", return_value=[])
    @patch("worker.subprocess.Popen")
    def test_success_without_manifest_warns_but_preserves_completion(self, popen, _preflight):
        class FakeProcess:
            stdout = iter([])

            @staticmethod
            def wait():
                return 0

        popen.return_value = FakeProcess()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            events = root / "events.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1,
                "camera1": str(root / "one.mp4"),
                "camera2": str(root / "two.mp4"),
                "output": str(root / "output"),
            })
            self.assertEqual(run_worker(spec, events), 0)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertIn("RUN_MANIFEST_UNREADABLE", [item.get("code") for item in records])
        self.assertEqual(records[-1]["type"], "job_completed")

    @patch("worker.run_preflight", return_value=[])
    def test_real_child_process_completes_then_reuses_checkpoint(self, _preflight):
        fixture = Path(__file__).parent / "fixtures" / "lifecycle_engine.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            spec = JobSpec.from_dict({
                "schema_version": 1, "job_id": "lifecycle-test",
                "camera1": "one.mp4", "camera2": "two.mp4",
                "output": str(output), "options": {"no_preview": True},
            })
            first_events = root / "first.jsonl"
            second_events = root / "second.jsonl"
            self.assertEqual(run_worker(spec, first_events, engine_path=fixture), 0)
            self.assertEqual(run_worker(spec, second_events, engine_path=fixture), 0)
            first = [json.loads(line) for line in first_events.read_text(encoding="utf-8").splitlines()]
            second = [json.loads(line) for line in second_events.read_text(encoding="utf-8").splitlines()]
        self.assertIn("fixture checkpoint: created",
                      [item.get("message", "").strip() for item in first])
        self.assertIn("fixture checkpoint: resumed",
                      [item.get("message", "").strip() for item in second])
        self.assertIn("artifacts_available", [item["type"] for item in second])
        self.assertEqual(second[-1]["type"], "job_completed")

    @patch("worker.run_preflight", return_value=[])
    def test_real_child_cancellation_is_resumable_and_emits_no_artifacts(self, _preflight):
        fixture = Path(__file__).parent / "fixtures" / "lifecycle_engine.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            cancel = root / "cancel.flag"
            cancel.write_text("cancel\n", encoding="utf-8")
            events = root / "cancelled.jsonl"
            spec = JobSpec.from_dict({
                "schema_version": 1, "job_id": "cancel-test",
                "camera1": "one.mp4", "camera2": "two.mp4",
                "output": str(output), "options": {"no_preview": True},
            })
            self.assertEqual(run_worker(spec, events, cancel, fixture), 130)
            records = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines()]
        self.assertNotIn("artifacts_available", [item["type"] for item in records])
        self.assertEqual(records[-1]["type"], "job_cancelled")
        self.assertTrue(records[-1]["resumable"])

    @patch("worker.run_preflight", return_value=[])
    def test_cancellation_after_checkpoint_resumes_without_repeating_prepare(self, _preflight):
        fixture = Path(__file__).parent / "fixtures" / "lifecycle_engine.py"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output"
            cancel = root / "cancel.flag"
            cancel.write_text("before-export\n", encoding="utf-8")
            spec = JobSpec.from_dict({
                "schema_version": 1, "job_id": "late-cancel-test",
                "camera1": "one.mp4", "camera2": "two.mp4",
                "output": str(output), "options": {"no_preview": True},
            })
            cancelled_events = root / "cancelled.jsonl"
            self.assertEqual(run_worker(spec, cancelled_events, cancel, fixture), 130)
            self.assertTrue((output / "fixture.checkpoint").is_file())
            self.assertFalse((output / "podedit_timeline.xml").exists())
            cancel.unlink()
            resumed_events = root / "resumed.jsonl"
            self.assertEqual(run_worker(spec, resumed_events, cancel, fixture), 0)
            resumed = [json.loads(line) for line in
                       resumed_events.read_text(encoding="utf-8").splitlines()]
        messages = [item.get("message", "").strip() for item in resumed]
        self.assertIn("fixture checkpoint: resumed", messages)
        self.assertEqual(resumed[-1]["type"], "job_completed")


if __name__ == "__main__":
    unittest.main()
