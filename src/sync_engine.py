# sync_engine.py
# Purpose: Find time offset between two audio tracks (camera1 & camera2)
# This is the "auto sync" core, similar to Premiere's Merge Clips

import numpy as np
from scipy import signal
import json
import os
import time
from datetime import datetime
import matplotlib.pyplot as plt

class SyncEngine:
    """
    Uses cross-correlation to estimate delay between two audio signals.
    Intuition: Slide one waveform over the other until similarity is highest.
    """

    def __init__(self, sample_rate=44100, max_offset_seconds=5.0):
        """
        sample_rate: must match AudioProcessor sample_rate
        max_offset_seconds: search window (e.g. +/- 5 seconds is enough if you clapped near the start)
        """
        self.sample_rate = sample_rate
        self.max_offset_seconds = max_offset_seconds
        self.metrics = {}

    def estimate_offset(self, audio1, audio2, downsample_factor=4, plot_debug=False):
        """
        Estimate offset between audio2 relative to audio1.

        Returns:
            offset_seconds (float): positive => audio2 starts LATER than audio1
        """
        start_time = time.time()

        # Optional downsampling for speed (we don't need sample-level precision initially)
        if downsample_factor > 1:
            audio1_ds = audio1[::downsample_factor]
            audio2_ds = audio2[::downsample_factor]
            sr_eff = self.sample_rate // downsample_factor
        else:
            audio1_ds = audio1
            audio2_ds = audio2
            sr_eff = self.sample_rate

        # Normalize both signals to avoid scale issues
        audio1_ds = self._normalize(audio1_ds)
        audio2_ds = self._normalize(audio2_ds)

        # Limit search window in samples
        max_lag_samples = int(self.max_offset_seconds * sr_eff)

        # Compute cross-correlation using FFT method (fast)[web:171][web:169]
        # We correlate full signals, then look only near center (±max_lag_samples)
        corr = signal.correlate(audio1_ds, audio2_ds, mode='full', method='fft')
        lags = signal.correlation_lags(len(audio1_ds), len(audio2_ds), mode='full')

        # Focus on lags within [-max_lag_samples, max_lag_samples]
        mask = (lags >= -max_lag_samples) & (lags <= max_lag_samples)
        corr_window = corr[mask]
        lags_window = lags[mask]

        # Find lag with maximum correlation (best alignment)
        best_index = np.argmax(corr_window)
        best_lag = lags_window[best_index]

        # Convert lag to time (seconds)
        offset_seconds = -best_lag / sr_eff  # minus sign so "positive = audio2 later than audio1"

        elapsed = time.time() - start_time

        # Store metrics for paper
        self.metrics = {
            "sample_rate": self.sample_rate,
            "effective_sample_rate": sr_eff,
            "downsample_factor": downsample_factor,
            "max_offset_seconds": self.max_offset_seconds,
            "estimated_offset_seconds": float(offset_seconds),
            "max_correlation_value": float(corr_window[best_index]),
            "processing_time_seconds": float(elapsed),
            "timestamp": datetime.now().isoformat()
        }

        print("\n=== SYNC ESTIMATION ===")
        print(f"Estimated offset (audio2 relative to audio1): {offset_seconds:.4f} s")
        print(f"Search window: ±{self.max_offset_seconds:.1f} s")
        print(f"Computation time: {elapsed:.3f} s")

        if plot_debug:
            self._plot_debug(corr_window, lags_window, best_index, sr_eff)

        return offset_seconds

    def _normalize(self, x):
        max_val = np.max(np.abs(x))
        if max_val > 0:
            return x / max_val
        return x

    def _plot_debug(self, corr_window, lags_window, best_index, sr_eff):
        """
        Plot correlation vs lag for understanding (helpful for your paper figures).
        """
        import matplotlib.pyplot as plt

        lag_times = lags_window / sr_eff

        plt.figure(figsize=(10, 4))
        plt.plot(lag_times, corr_window)
        plt.scatter([lag_times[best_index]], [corr_window[best_index]], color='red', label='Best lag')
        plt.axvline(lag_times[best_index], color='red', linestyle='--')
        plt.title("Cross-correlation vs Lag (seconds)")
        plt.xlabel("Lag (s)")
        plt.ylabel("Correlation")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        os.makedirs("paper/figures", exist_ok=True)
        plt.savefig("paper/figures/sync_correlation_plot.png", dpi=200)
        plt.close()
        print("Saved debug plot to paper/figures/sync_correlation_plot.png")

    def save_metrics(self, output_path="results/sync_metrics.json"):
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(self.metrics, f, indent=2)
        print(f"Sync metrics saved to {output_path}")


# Simple test harness (run this file directly)
if __name__ == "__main__":
    import librosa

    audio1_path = "results/camera1_audio.wav"
    audio2_path = "results/camera2_audio.wav"

    if not (os.path.exists(audio1_path) and os.path.exists(audio2_path)):
        print("❌ Please run audio_processor.py first to generate camera1_audio.wav and camera2_audio.wav")
        exit()

    print("Loading audio files for sync test...")
    audio1, sr1 = librosa.load(audio1_path, sr=44100, mono=True)
    audio2, sr2 = librosa.load(audio2_path, sr=44100, mono=True)

    engine = SyncEngine(sample_rate=44100, max_offset_seconds=5.0)
    offset = engine.estimate_offset(audio1, audio2, downsample_factor=4, plot_debug=True)
    engine.save_metrics("results/sync_metrics.json")
