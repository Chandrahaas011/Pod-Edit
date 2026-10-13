import os
import tempfile
import unittest
import json

from pipeline.job_contract import EVENT_SCHEMA_VERSION, JobSpec, JobValidationError, event
from pipeline.job_control import JobCancelled, check_cancel


class JobContractTests(unittest.TestCase):
    def test_typed_job_maps_only_supported_options_to_cli(self):
        spec = JobSpec.from_dict({
            "schema_version": 1,
            "job_id": "job-123",
            "camera1": "C:/media/camera one.mp4",
            "camera2": "C:/media/camera two.mp4",
            "output": "C:/output/podedit",
            "options": {
                "offline": True,
                "no_preview": True,
                "max_duration": 90,
                "editorial_profile": "balanced",
            },
        })
        self.assertEqual(spec.job_id, "job-123")
        self.assertEqual(spec.to_cli_args("C:/output/cancel.flag"), [
            "--cam1", "C:/media/camera one.mp4",
            "--cam2", "C:/media/camera two.mp4",
            "--output", "C:/output/podedit",
            "--max-duration", "90",
            "--editorial-profile", "balanced",
            "--no-preview", "--offline",
            "--cancel-file", "C:/output/cancel.flag",
        ])

    def test_job_rejects_unknown_and_non_scalar_options(self):
        payload = {
            "schema_version": 1,
            "camera1": "a.mp4",
            "camera2": "b.mp4",
            "output": "out",
            "options": {"unsafe_flag": True},
        }
        with self.assertRaises(JobValidationError):
            JobSpec.from_dict(payload)
        payload["options"] = {"max_duration": [1500]}
        with self.assertRaises(JobValidationError):
            JobSpec.from_dict(payload)

    def test_job_rejects_non_string_paths_and_boolean_value_options(self):
        payload = {
            "schema_version": 1,
            "camera1": ["a.mp4"],
            "camera2": "b.mp4",
            "output": "out",
        }
        with self.assertRaisesRegex(JobValidationError, "camera1.*string path"):
            JobSpec.from_dict(payload)
        payload["camera1"] = "a.mp4"
        payload["options"] = {"max_duration": True}
        with self.assertRaisesRegex(JobValidationError, "must not be boolean"):
            JobSpec.from_dict(payload)

    def test_job_rejects_invalid_choices_and_numeric_ranges_before_launch(self):
        base = {"schema_version": 1, "camera1": "a.mp4", "camera2": "b.mp4",
                "output": "out"}
        invalid = [
            ("mode", "visual"), ("max_duration", "banana"),
            ("max_duration", 0), ("num_speakers", 3),
            ("num_speakers", 2.0),
            ("timeline_fps", float("nan")), ("preview_start", -1),
            ("max_primary_shot", 19), ("second_speaker_max_cosine", 1.1),
        ]
        for name, value in invalid:
            with self.subTest(name=name, value=value):
                with self.assertRaises(JobValidationError):
                    JobSpec.from_dict({**base, "options": {name: value}})

    def test_job_rejects_invalid_window_overlap_geometry(self):
        with self.assertRaisesRegex(JobValidationError, "must exceed"):
            JobSpec.from_dict({
                "schema_version": 1, "camera1": "a.mp4", "camera2": "b.mp4",
                "output": "out", "options": {
                    "diarization_window": 15, "diarization_overlap": 15,
                }})

    def test_job_preserves_unicode_and_space_paths(self):
        spec = JobSpec.from_dict({
            "schema_version": 1,
            "camera1": "C:/podcasts/Guest Interview 01/\u0915\u0948\u092e\u0930\u093e one.mp4",
            "camera2": "C:/podcasts/Guest Interview 01/c\u00e1mara two.mp4",
            "output": "C:/exports/\u00c9pisode final",
        })
        self.assertIn("C:/podcasts/Guest Interview 01/\u0915\u0948\u092e\u0930\u093e one.mp4", spec.to_cli_args())
        self.assertIn("C:/exports/\u00c9pisode final", spec.to_cli_args())

    def test_cancel_file_is_only_observed_at_cooperative_boundary(self):
        with tempfile.TemporaryDirectory() as temporary:
            cancel_file = os.path.join(temporary, "cancel.flag")
            check_cancel(cancel_file, "test")
            with open(cancel_file, "w", encoding="utf-8") as handle:
                handle.write("cancel\n")
            with self.assertRaisesRegex(JobCancelled, "safe boundary: test"):
                check_cancel(cancel_file, "test")

    def test_job_loader_accepts_utf8_bom_from_powershell(self):
        payload = {
            "schema_version": 1,
            "camera1": "a.mp4",
            "camera2": "b.mp4",
            "output": "out",
        }
        with tempfile.NamedTemporaryFile("w", encoding="utf-8-sig", delete=False) as handle:
            json.dump(payload, handle)
            job_file = handle.name
        self.addCleanup(lambda: os.path.exists(job_file) and os.unlink(job_file))
        self.assertEqual(JobSpec.load(job_file).output, "out")

    def test_event_has_an_independent_versioned_contract(self):
        self.assertEqual(event("job_started", "test")["event_schema_version"], EVENT_SCHEMA_VERSION)


if __name__ == "__main__":
    unittest.main()
