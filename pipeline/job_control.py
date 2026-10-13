"""Cooperative cancellation primitives shared by the CLI and worker process."""

from __future__ import annotations

import os


class JobCancelled(RuntimeError):
    """Raised only at a known-safe worker boundary after prior outputs persist."""


def is_cancel_requested(cancel_file: str | None) -> bool:
    """A GUI requests cancellation by atomically creating this sentinel file."""
    return bool(cancel_file and os.path.isfile(cancel_file))


def check_cancel(cancel_file: str | None, boundary: str) -> None:
    """Stop before beginning new work; completed checkpoints remain reusable."""
    if is_cancel_requested(cancel_file):
        raise JobCancelled(f"Cancellation requested at safe boundary: {boundary}")
