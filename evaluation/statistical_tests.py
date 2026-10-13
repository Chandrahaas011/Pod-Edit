"""Deterministic bootstrap utilities for human-reference edit evaluation."""

from __future__ import annotations

import random

from evaluation.metrics import _camera_at


def bootstrap_accuracy_interval(predicted: list, reference: list, duration: float,
                                bin_seconds: float = 1.0, samples: int = 10000,
                                confidence: float = 0.95, seed: int = 20260809) -> dict:
    """Percentile bootstrap CI over fixed-duration timeline bins."""
    if duration <= 0 or bin_seconds <= 0 or samples <= 0:
        raise ValueError("duration, bin_seconds, and samples must be positive")
    observations = []
    timestamp = bin_seconds / 2.0
    while timestamp < duration:
        observations.append(int(_camera_at(predicted, timestamp) ==
                                _camera_at(reference, timestamp)))
        timestamp += bin_seconds
    if not observations:
        raise ValueError("no timeline bins available")
    rng = random.Random(seed)
    distribution = []
    for _ in range(samples):
        total = sum(observations[rng.randrange(len(observations))]
                    for _ in observations)
        distribution.append(total / len(observations))
    distribution.sort()
    alpha = (1.0 - confidence) / 2.0
    lower = distribution[int(alpha * (samples - 1))]
    upper = distribution[int((1.0 - alpha) * (samples - 1))]
    return {"estimate": sum(observations) / len(observations),
            "lower": lower, "upper": upper, "confidence": confidence,
            "bin_seconds": bin_seconds, "bootstrap_samples": samples, "seed": seed}
