import cv2


def probe_video(path: str) -> dict:
    """Probes a video file for FPS, frame count, resolution and duration.

    Never hardcode FPS — the two cameras in a shoot routinely differ
    (e.g. 25 vs 30 fps), and wrong FPS silently corrupts every frame
    calculation downstream.
    """
    capture = cv2.VideoCapture(path)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video file: {path}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()

    duration = frames / fps if fps > 0 else 0.0
    return {
        "path": path,
        "fps": float(fps),
        "frames": frames,
        "width": width,
        "height": height,
        "duration_seconds": float(duration),
    }
