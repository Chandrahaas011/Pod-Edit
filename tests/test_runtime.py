import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pipeline.run_request import RunRequest
from pipeline.runtime import configure_runtime


def _request(*, offline: bool) -> RunRequest:
    return RunRequest(
        camera1="one.mp4", camera2="two.mp4", output="output", mode="hybrid",
        num_speakers=2, max_duration=1, swap=False, force=False,
        diarization_strategy="windowed", diarization_window=60,
        diarization_overlap=15, second_speaker_max_cosine=0.7,
        sync_offset=None, no_preview=True, preview_start=None,
        editorial_profile="balanced", no_reactions=False, max_primary_shot=60,
        timeline_fps=30, offline=offline, cancel_file=None,
    )


class RuntimeTests(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_offline_request_configures_project_local_cache_before_imports(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = configure_runtime(_request(offline=True), temporary)
            self.assertEqual(cache.name, ".model_cache")
            self.assertEqual(os.environ["HF_HOME"], os.path.join(temporary, ".model_cache", "huggingface"))
            self.assertEqual(os.environ["HF_HUB_OFFLINE"], "1")

    @patch.dict(os.environ, {"HF_HOME": "custom-cache"}, clear=True)
    def test_explicit_user_cache_setting_is_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            configure_runtime(_request(offline=False), temporary)
        self.assertEqual(os.environ["HF_HOME"], "custom-cache")

    @patch.dict(os.environ, {"PODEDIT_MODEL_CACHE": "custom-models"}, clear=True)
    def test_packaged_model_cache_location_is_respected(self):
        with tempfile.TemporaryDirectory() as temporary:
            cache = configure_runtime(_request(offline=True), temporary)
        self.assertEqual(cache, Path("custom-models").resolve())
