from pathlib import Path
import tempfile
import unittest

import numpy as np
import soundfile as sf

from pipeline.audio_io import load_mono


class AudioIoTests(unittest.TestCase):
    def test_bounded_stereo_input_is_mixed_and_resampled(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = Path(temporary) / "stereo.wav"
            samples = np.column_stack((np.ones(8000, dtype=np.float32),
                                       np.zeros(8000, dtype=np.float32)))
            sf.write(path, samples, 8000, subtype="PCM_16")
            mono, rate = load_mono(str(path), 16000, duration=0.5)
            self.assertEqual((rate, len(mono)), (16000, 8000))
            self.assertAlmostEqual(float(np.median(mono)), 0.5, places=3)

    def test_invalid_bounds_are_rejected(self):
        with self.assertRaises(ValueError):
            load_mono("unused.wav", 0)
