from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from pipeline.preview import render_switch_review


def segments(count):
    return [{"start": index * 2.0, "duration": 2.0, "camera": index % 2 + 1}
            for index in range(count)]


class ReviewBatchTests(unittest.TestCase):
    def test_default_includes_all_101_cuts_in_bounded_batches(self):
        seen = []
        def render(*args):
            seen.extend(args[-1])
            self.assertLessEqual(len(args[-1]), 8)
            Path(args[5]).write_bytes(b"fixture")
            return args[5]
        def assemble(command, **kwargs):
            Path(command[-1]).write_bytes(b"complete")
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            output = Path(temporary) / "review.mp4"
            with patch("pipeline.preview._render_switch_review_batch", side_effect=render), \
                    patch("pipeline.preview.subprocess.run", side_effect=assemble):
                render_switch_review(segments(102), "one", "two", "audio", 0, str(output))
            self.assertEqual(output.read_bytes(), b"complete")
            self.assertEqual(list(Path(temporary).iterdir()), [output])
        self.assertEqual(seen, list(range(1, 102)))

    def test_batch_failure_preserves_existing_output_and_cleans_temporary_media(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            output = Path(temporary) / "review.mp4"
            output.write_bytes(b"existing")
            with patch("pipeline.preview._render_switch_review_batch", return_value=None):
                self.assertIsNone(render_switch_review(
                    segments(3), "one", "two", "audio", 0, str(output)))
            self.assertEqual(output.read_bytes(), b"existing")
            self.assertEqual(list(Path(temporary).iterdir()), [output])

    def test_explicit_single_cut_limit_avoids_division_by_zero(self):
        seen = []
        def render(*args):
            seen.extend(args[-1])
            Path(args[5]).write_bytes(b"fixture")
            return args[5]
        def assemble(command, **kwargs):
            Path(command[-1]).write_bytes(b"complete")
            return subprocess.CompletedProcess(command, 0)
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            with patch("pipeline.preview._render_switch_review_batch", side_effect=render), \
                    patch("pipeline.preview.subprocess.run", side_effect=assemble):
                render_switch_review(segments(10), "one", "two", "audio", 0,
                                     str(Path(temporary) / "review.mp4"), max_cuts=1)
        self.assertEqual(seen, [1])

    def test_unknown_cut_number_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown cut"):
            render_switch_review(segments(3), "one", "two", "audio", 0,
                                 "unused.mp4", cut_numbers=[99])
