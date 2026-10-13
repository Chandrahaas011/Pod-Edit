import unittest

from pipeline.cli_contract import build_parser
from pipeline.run_request import RunRequest


class RunRequestTests(unittest.TestCase):
    def test_request_preserves_all_cli_values_without_argparse_dependency_after_creation(self):
        namespace = build_parser().parse_args([
            "--cam1", "one.mp4", "--cam2", "two.mp4", "--output", "export",
            "--max-duration", "90", "--offline", "--no-preview",
            "--cancel-file", "cancel.flag",
        ])
        request = RunRequest.from_namespace(namespace)
        self.assertEqual(request.camera1, "one.mp4")
        self.assertEqual(request.output, "export")
        self.assertEqual(request.max_duration, 90.0)
        self.assertTrue(request.offline)
        self.assertEqual(request.cancel_file, "cancel.flag")
