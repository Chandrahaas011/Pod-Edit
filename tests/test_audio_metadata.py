import tempfile
import unittest
import wave
from pathlib import Path

from pipeline.audio_metadata import wav_duration


class AudioMetadataTests(unittest.TestCase):
    def test_duration_comes_from_pcm_header_without_audio_dependencies(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = Path(temporary) / "duration.wav"
            with wave.open(str(path), "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(16000)
                output.writeframes(b"\0\0" * 24000)
            self.assertEqual(wav_duration(str(path)), 1.5)
