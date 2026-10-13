import time

import numpy as np
from scipy import signal
from pipeline.audio_io import load_mono


def estimate_offset(
    wav1_path: str,
    wav2_path: str,
    max_offset_seconds: float = 10.0,
    analysis_window_seconds: float = 300.0,
    sample_rate: int = 11025,
) -> dict:
    """Estimates the recording-start offset between two cameras' audio tracks
    by cross-correlating the first `analysis_window_seconds` of each file.

    Both microphones sit in the same room and pick up the same acoustic
    events, so the correlation peak marks the true clock offset.

    Sign convention (single source of truth for the whole pipeline):
      NEGATIVE offset -> camera 2 started rolling BEFORE camera 1.
        Downstream: cam2_source_seconds = T - offset = T + |offset|  (later footage)
      POSITIVE offset -> camera 2 started rolling AFTER camera 1.
        Downstream: cam2_source_seconds = T - offset                 (earlier footage)

    Returns {"offset_seconds": float, "peak_correlation": float, "confidence": float}.
    """
    print("  ┌─ SYNC ENGINE — audio cross-correlation")
    print(f"  │ analysis window : first {analysis_window_seconds:.0f}s of each track")
    print(f"  │ search range    : ±{max_offset_seconds:.1f}s")
    print(f"  │ working rate    : {sample_rate} Hz mono")

    start_t = time.time()
    audio1, sr = load_mono(wav1_path, sample_rate, duration=analysis_window_seconds)
    audio2, _ = load_mono(wav2_path, sample_rate, duration=analysis_window_seconds)
    print(f"  │ loaded          : cam1 {len(audio1)} samples, cam2 {len(audio2)} samples "
          f"({time.time() - start_t:.1f}s)")

    # Normalize amplitudes so one hot mic doesn't dominate the correlation.
    for arr, name in ((audio1, "cam1"), (audio2, "cam2")):
        peak = np.max(np.abs(arr))
        if peak > 0:
            arr /= peak
        print(f"  │ normalization   : {name} peak {peak:.4f} -> 1.0")

    corr = signal.correlate(audio1, audio2, mode="full", method="fft")
    lags = signal.correlation_lags(len(audio1), len(audio2), mode="full")

    max_lag = int(max_offset_seconds * sr)
    mask = (lags >= -max_lag) & (lags <= max_lag)
    corr_win = corr[mask]
    lags_win = lags[mask]

    best_index = int(np.argmax(corr_win))
    best_lag = int(lags_win[best_index])
    peak_value = float(corr_win[best_index])

    # scipy convention: correlate(a, b) — a positive lag means b must be shifted
    # RIGHT (delayed) to align with a, i.e. cam2's audio arrived LATER, i.e.
    # cam2 started recording AFTER cam1. Direct mapping, no sign flip:
    offset_seconds = best_lag / sr

    # Confidence: how much the peak stands out above the correlation noise floor.
    noise_floor = float(np.median(np.abs(corr_win)))
    confidence = peak_value / noise_floor if noise_floor > 0 else float("inf")

    direction = "cam2 started BEFORE cam1" if offset_seconds < 0 else "cam2 started AFTER cam1"
    print(f"  │ best lag        : {best_lag} samples")
    print(f"  │ peak corr       : {peak_value:.2f} (noise floor {noise_floor:.2f}, ratio {confidence:.1f}x)")
    print(f"  │ OFFSET          : {offset_seconds:+.4f}s — {direction} by {abs(offset_seconds):.4f}s")
    print(f"  └─ done in {time.time() - start_t:.2f}s")

    if confidence < 5.0:
        print("  ⚠ WARNING: weak correlation peak — offset estimate may be unreliable.")
        print("    Consider verifying with the preview render or --sync-offset override.")

    return {
        "offset_seconds": float(offset_seconds),
        "peak_correlation": peak_value,
        "confidence": float(confidence),
    }
