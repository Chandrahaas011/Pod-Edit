# audio_processor.py
# Purpose: Extract and load audio from video files
# This is like exporting audio tracks in Premiere Pro

import ffmpeg  # Tool that handles video files
import numpy as np  # Math library for working with audio data
import librosa  # Audio analysis library
import os  # For file operations (checking if files exist, etc.)
import shutil  # For resolving system executables
import json  # For saving/loading our metrics
import time  # For measuring how long things take
from datetime import datetime  # For timestamps
import cv2  # For reliable video duration metadata without ffprobe

class AudioProcessor:
    """
    This class handles everything related to audio:
    - Extracting audio from video files
    - Loading audio into memory for analysis
    - Collecting metrics for our research paper
    
    Think of it as a specialized tool in your editing workflow
    """
    
    def __init__(self, sample_rate=44100, log_metrics=True):
        """
        Initialize the audio processor
        
        Parameters:
        - sample_rate: How many audio samples per second
          44100 is CD quality (standard for audio)
          Think of it like frame rate for audio
        
        - log_metrics: Should we track performance data?
          True = yes (we need this for the research paper)
        """
        self.sample_rate = sample_rate
        self.log_metrics = log_metrics
        
        # Dictionary to store all our measurements
        self.metrics = {
            'extraction_times': [],      # How long did audio extraction take?
            'file_sizes': [],             # How big are the audio files?
            'durations': [],              # How long is each video?
            'sample_rates': [],           # What sample rate did we use?
            'processing_timestamps': []   # When did we process this?
        }

    def _resolve_ffmpeg_cmd(self):
        """Find a usable ffmpeg binary from PATH or bundled Python package."""
        system_ffmpeg = shutil.which("ffmpeg")
        if system_ffmpeg:
            return system_ffmpeg

        try:
            import imageio_ffmpeg

            return imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            return None
    
    def extract_audio(self, video_path, output_path=None):
        """
        Extract audio from a video file
        
        This is like: Right-click video in Premiere > Extract Audio
        
        Parameters:
        - video_path: Full path to your video file (e.g., "C:/videos/camera1.mp4")
        - output_path: Where to save the audio (optional - auto-generates if not provided)
        
        Returns:
        - Path to the extracted audio file
        """
        
        # If user didn't specify output path, create one automatically
        # Example: "camera1.mp4" becomes "camera1_audio.wav"
        if output_path is None:
            base_name = os.path.splitext(video_path)[0]  # Remove .mp4 extension
            output_path = f"{base_name}_audio.wav"
        
        # Start timing (for research metrics)
        start_time = time.time()
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        try:
            print(f"🎵 Extracting audio from {os.path.basename(video_path)}...")

            ffmpeg_cmd = self._resolve_ffmpeg_cmd()
            if not ffmpeg_cmd:
                raise RuntimeError(
                    "No ffmpeg executable found. Install ffmpeg on PATH or install imageio-ffmpeg."
                )
            
            # Tell FFmpeg what to do:
            stream = ffmpeg.input(video_path)  # Open the video file
            stream = ffmpeg.output(
                stream,
                output_path,
                acodec='pcm_s16le',  # Audio codec (uncompressed WAV format)
                ac=2,                 # Audio channels (2 = stereo)
                ar=self.sample_rate   # Sample rate (44100 Hz)
            )
            
            # Actually run FFmpeg (overwrite if file exists, don't show verbose output)
            ffmpeg.run(stream, overwrite_output=True, quiet=True, cmd=ffmpeg_cmd)
            
            # Calculate how long extraction took
            extraction_time = time.time() - start_time
            
            # Collect metrics for our paper
            if self.log_metrics:
                # Get file size in megabytes
                file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
                
                # Get video duration
                duration = self.get_video_duration(video_path)
                
                # Store all measurements
                self.metrics['extraction_times'].append(extraction_time)
                self.metrics['file_sizes'].append(file_size_mb)
                self.metrics['durations'].append(duration)
                self.metrics['sample_rates'].append(self.sample_rate)
                self.metrics['processing_timestamps'].append(datetime.now().isoformat())
                
                # Show user what happened
                print(f"   ✅ Done in {extraction_time:.2f} seconds")
                print(f"   📦 File size: {file_size_mb:.2f} MB")
                print(f"   ⏱️  Duration: {duration:.2f} seconds")
            
            return output_path
            
        except ffmpeg.Error as e:
            # If something went wrong, show the error
            print(f"❌ Error extracting audio: {e.stderr.decode()}")
            raise  # Re-raise the error so program stops
    
    def load_audio(self, audio_path, duration=None):
        """
        Load audio file into memory for analysis
        
        This converts the audio file into a NumPy array (list of numbers)
        Each number represents the audio amplitude at that moment
        Think of it like loading a waveform view in Audacity
        
        Parameters:
        - audio_path: Path to audio file (.wav)
        - duration: Optional limit (in seconds) - useful for testing
        
        Returns:
        - audio_data: NumPy array of audio samples
        - sr: Sample rate used
        """
        start_time = time.time()
        print(f"📂 Loading audio from {os.path.basename(audio_path)}...")
        
        # Librosa loads the audio and converts to numpy array
        audio_data, sr = librosa.load(
            audio_path,
            sr=self.sample_rate,  # Resample to our target rate
            mono=True,             # Convert to mono (easier to analyze)
            duration=duration      # Limit duration if specified
        )
        
        load_time = time.time() - start_time
        audio_duration = len(audio_data) / sr
        
        print(f"   ✅ Loaded {audio_duration:.2f} seconds in {load_time:.2f} seconds")
        print(f"   📊 Array shape: {audio_data.shape} samples")
        
        return audio_data, sr
    
    def get_video_duration(self, video_path):
        """
        Get the duration of a video file
        Uses FFmpeg probe to read video metadata
        
        Returns: Duration in seconds (float)
        """
        try:
            capture = cv2.VideoCapture(video_path)
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
            frames = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
            capture.release()

            if fps <= 0.0:
                return None
            return frames / fps
        except Exception as e:
            print(f"⚠️  Warning: Could not get duration - {e}")
            return None
    
    def normalize_audio(self, audio_data):
        """
        Normalize audio to prevent clipping
        
        Makes the loudest point = 1.0, scales everything else proportionally
        Like using the "Normalize" effect in Audacity
        
        Why? Prevents distortion and makes comparison easier
        """
        max_val = np.abs(audio_data).max()
        if max_val > 0:
            return audio_data / max_val
        return audio_data
    
    def save_metrics(self, output_path="results/audio_processing_metrics.json"):
        """
        Save all collected metrics to a JSON file
        This data goes into our research paper tables
        """
        # Create the results folder if it doesn't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Write metrics to JSON file
        with open(output_path, 'w') as f:
            json.dump(self.metrics, f, indent=2)
        
        print(f"\n💾 Metrics saved to: {output_path}")
        print(f"   This file contains data for your research paper!")


# ============================================
# TEST CODE - Run this script to test it
# ============================================
if __name__ == "__main__":
    """
    This section only runs when you execute this file directly
    It's for testing that everything works
    """
    
    print("=" * 60)
    print("AUDIO PROCESSOR TEST")
    print("=" * 60)
    
    # Create an AudioProcessor instance
    processor = AudioProcessor(sample_rate=44100, log_metrics=True)
    
    # Define paths to your test videos
    # CHANGE THESE to match your actual file names
    video1 = r"datasets\test_set_1\camera1_short.mp4"
    video2 = r"datasets\test_set_1\camera2_short.mp4"
    
    # Check if files exist
    if not os.path.exists(video1):
        print(f"❌ Error: Could not find {video1}")
        print("   Please check the file path and try again")
        exit()
    
    if not os.path.exists(video2):
        print(f"❌ Error: Could not find {video2}")
        print("   Please check the file path and try again")
        exit()
    
    print("\n--- Processing Camera 1 ---")
    # Extract audio from first camera
    audio1_path = processor.extract_audio(
        video1,
        "results/camera1_audio.wav"
    )
    
    # Load the extracted audio into memory
    audio1_data, sr1 = processor.load_audio(audio1_path)
    
    print("\n--- Processing Camera 2 ---")
    # Extract audio from second camera
    audio2_path = processor.extract_audio(
        video2,
        "results/camera2_audio.wav"
    )
    
    # Load the extracted audio into memory
    audio2_data, sr2 = processor.load_audio(audio2_path)
    
    # Display summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Camera 1:")
    print(f"  Duration: {len(audio1_data)/sr1:.2f} seconds")
    print(f"  Samples: {len(audio1_data):,}")
    print(f"  Sample rate: {sr1} Hz")
    
    print(f"\nCamera 2:")
    print(f"  Duration: {len(audio2_data)/sr2:.2f} seconds")
    print(f"  Samples: {len(audio2_data):,}")
    print(f"  Sample rate: {sr2} Hz")
    
    # Save metrics for research
    processor.save_metrics("results/audio_processing_metrics.json")
    
    print("\n✅ All tests passed! Audio processor is working correctly.")
    print("   You can now proceed to Phase 2 (Audio Sync)")
