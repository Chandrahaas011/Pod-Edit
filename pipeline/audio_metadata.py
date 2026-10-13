"""Dependency-free metadata helpers for PodEdit's PCM WAV derivatives."""

from __future__ import annotations

import wave


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as handle:
        rate = handle.getframerate()
        if rate <= 0:
            raise ValueError(f"WAV has invalid sample rate: {path}")
        return handle.getnframes() / rate
