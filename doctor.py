"""Read-only environment diagnostic for PodEdit."""

import importlib
import os
import shutil
import sys
import warnings

warnings.filterwarnings("ignore", message=r"(?s).*torchcodec is not installed correctly.*")


def main():
    checks = []
    checks.append(("Python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0]))
    for executable in ("ffmpeg", "ffprobe"):
        location = shutil.which(executable)
        checks.append((executable, bool(location), location or "not on PATH"))
    for package in ("torch", "pyannote.audio", "cv2", "soundfile", "soxr", "scipy"):
        try:
            module = importlib.import_module(package)
            detail = getattr(module, "__version__", "imported")
            checks.append((package, True, str(detail)))
        except Exception as exc:
            checks.append((package, False, str(exc)))
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".model_cache")
    checks.append(("project-local model cache", os.path.isdir(cache), cache))
    width = max(len(name) for name, _, _ in checks)
    for name, passed, detail in checks:
        print(f"{'PASS' if passed else 'FAIL'}  {name:<{width}}  {detail}")
    return 0 if all(passed for _, passed, _ in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
