import unittest

from pipeline.cli_contract import build_parser
from pipeline.job_contract import JobSpec


class CliContractTests(unittest.TestCase):
    def test_every_worker_option_is_accepted_by_the_engine_parser(self):
        options = {
            "mode": "audio",
            "num_speakers": 2,
            "max_duration": 90,
            "diarization_strategy": "global",
            "diarization_window": 60,
            "diarization_overlap": 15,
            "second_speaker_max_cosine": 0.7,
            "sync_offset": -0.9,
            "preview_start": 10,
            "editorial_profile": "balanced",
            "max_primary_shot": 60,
            "timeline_fps": 30,
            "swap": True,
            "force": True,
            "no_preview": True,
            "no_reactions": True,
            "offline": True,
        }
        spec = JobSpec.from_dict({
            "schema_version": 1,
            "camera1": "one.mp4",
            "camera2": "two.mp4",
            "output": "output",
            "options": options,
        })
        parsed = build_parser().parse_args(spec.to_cli_args("cancel.flag"))
        self.assertEqual(parsed.cam1, "one.mp4")
        self.assertEqual(parsed.mode, "audio")
        self.assertTrue(parsed.no_preview)
        self.assertEqual(parsed.cancel_file, "cancel.flag")


if __name__ == "__main__":
    unittest.main()
