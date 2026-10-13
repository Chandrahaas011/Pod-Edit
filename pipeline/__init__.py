"""PodEdit automated two-camera podcast editing pipeline."""

import sys

# The package emits mathematical and box-drawing diagnostics. Redirected
# Windows streams often default to CP-1252, so make library entry points as
# robust as the CLI entry point.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

__version__ = "1.1.0"
