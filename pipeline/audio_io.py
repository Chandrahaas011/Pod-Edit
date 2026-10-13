"""Small production audio loader without librosa/Numba runtime coupling."""

from __future__ import annotations

import math

import numpy as np
import soundfile as sf
import soxr


def load_mono(path: str, sample_rate: int, duration: float | None = None,
              offset: float = 0.0) -> tuple[np.ndarray, int]:
    """Read a bounded audio interval, mix channels, and resample with soxr."""
    if sample_rate <= 0 or offset < 0 or (duration is not None and duration < 0):
        raise ValueError("sample_rate must be positive; offset/duration cannot be negative")
    with sf.SoundFile(path) as source:
        source_rate = int(source.samplerate)
        source.seek(min(len(source), round(offset * source_rate)))
        frames = -1 if duration is None else math.ceil(duration * source_rate)
        data = source.read(frames=frames, dtype="float32", always_2d=True)
    mono = np.mean(data, axis=1, dtype=np.float32)
    if source_rate != sample_rate and len(mono):
        mono = soxr.resample(mono, source_rate, sample_rate, quality="HQ")
    if duration is not None:
        mono = mono[:round(duration * sample_rate)]
    return np.asarray(mono, dtype=np.float32), sample_rate
