import os
import time

import ffmpeg

from pipeline.cache import atomic_write_json, file_signature, load_json, signatures_match


def extract_audio(video_path: str, output_wav_path: str, sample_rate: int = 48000,
                  max_duration: float | None = None, channels: int = 2) -> str:
    """Extracts audio from a video file to WAV (pcm_s16le) using ffmpeg.

    Reuses an extraction only when its sidecar fingerprint matches the source.
    """
    print(f"  Extraction target: {output_wav_path}")
    metadata_path = output_wav_path + ".meta.json"
    source_signature = file_signature(video_path)
    metadata = load_json(metadata_path)
    cache_valid = (
        os.path.exists(output_wav_path)
        and isinstance(metadata, dict)
        and metadata.get("sample_rate") == sample_rate
        and metadata.get("channels") == channels
        and metadata.get("max_duration") == max_duration
        and signatures_match(metadata.get("source"), source_signature)
    )
    if cache_valid:
        size_mb = os.path.getsize(output_wav_path) / (1024 * 1024)
        print(f"    -> Verified cache hit ({size_mb:.1f} MB).")
        return output_wav_path
    if os.path.exists(output_wav_path):
        print("    -> Existing WAV has no matching source fingerprint; rebuilding safely.")

    os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)

    layout = "mono" if channels == 1 else f"{channels} channels"
    print(f"    -> ffmpeg: {os.path.basename(video_path)} -> pcm_s16le, {sample_rate} Hz, {layout}")
    start_t = time.time()
    try:
        input_options = {"t": max_duration} if max_duration is not None else {}
        (
            ffmpeg
            .input(video_path, **input_options)
            .output(output_wav_path, acodec="pcm_s16le", ac=channels, ar=sample_rate)
            .overwrite_output()
            .run(quiet=True)
        )
    except ffmpeg.Error as e:
        err_msg = e.stderr.decode("utf8") if e.stderr else str(e)
        print(f"    -> FFMPEG ERROR: {err_msg}")
        raise RuntimeError(f"Failed to extract audio from {video_path}") from e

    size_mb = os.path.getsize(output_wav_path) / (1024 * 1024)
    atomic_write_json(metadata_path, {
        "source": source_signature,
        "sample_rate": sample_rate,
        "max_duration": max_duration,
        "channels": channels,
        "codec": "pcm_s16le",
    })
    print(f"    -> Done in {time.time() - start_t:.1f}s ({size_mb:.1f} MB)")
    return output_wav_path
