"""
Background bridge for the PodEdit GUI.

Runs the v9 pipeline on a worker thread and forwards stdout/stderr and
progress updates back to the GUI through a queue.
"""

from __future__ import annotations

import contextlib
import queue
import threading
import traceback


class _QueueWriter:
    def __init__(self, event_queue, event_type):
        self.event_queue = event_queue
        self.event_type = event_type
        self.buffer = ""

    def isatty(self):
        return True

    def write(self, text):
        if not text:
            return
        
        # Handle tqdm's \r behavior. We replace \r with a unique token and \n so it flushes immediately
        text = text.replace("\r", " __CR__\n")
        self.buffer += text
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            # Emit lines (we don't strictly strip so we keep spacing, but guard against completely empty if we want)
            if line.strip():
                # We prefix with a special marker or just emit
                self.event_queue.put((self.event_type, line.rstrip()))

    def flush(self):
        if self.buffer.strip():
            self.event_queue.put((self.event_type, self.buffer.rstrip()))
            self.buffer = ""


class PipelineBridge:
    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None

    @property
    def queue(self):
        return self._queue

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self, *, cam1_path, cam2_path, results_dir, force=False, progress_callback=None):
        if self.running:
            raise RuntimeError("The pipeline is already running.")

        def report_progress(stage, fraction, message):
            self._queue.put(("progress", {"stage": stage, "fraction": fraction, "message": message}))
            if progress_callback is not None:
                progress_callback(stage=stage, fraction=fraction, message=message)

        def worker():
            from src.v9_pipeline import run_v9

            stdout_writer = _QueueWriter(self._queue, "log")
            stderr_writer = _QueueWriter(self._queue, "log")
            try:
                with contextlib.redirect_stdout(stdout_writer), contextlib.redirect_stderr(stderr_writer):
                    result = run_v9(
                        cam1_path=cam1_path,
                        cam2_path=cam2_path,
                        results_dir=results_dir,
                        force=force,
                        progress_callback=report_progress,
                    )
                stdout_writer.flush()
                stderr_writer.flush()
                self._queue.put(("done", result))
            except Exception as exc:
                stdout_writer.flush()
                stderr_writer.flush()
                self._queue.put(("error", f"{exc}\n{traceback.format_exc()}"))

        self._thread = threading.Thread(target=worker, daemon=True)
        self._thread.start()

    def poll(self):
        events = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return events
