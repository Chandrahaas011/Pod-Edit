"""The stable command-line surface shared by the CLI and headless worker."""

from __future__ import annotations

import argparse
import os


def build_parser() -> argparse.ArgumentParser:
    """Create the lightweight parser without importing inference dependencies."""
    parser = argparse.ArgumentParser(
        description="PodEdit — automated multi-cam podcast editor "
                    "(neural diarization + hybrid visual verification)")
    parser.add_argument("--cam1", required=True, help="Camera 1 video (host / master audio source)")
    parser.add_argument("--cam2", required=True, help="Camera 2 video (guest)")
    parser.add_argument("--output", default="results", help="Output directory (default: results)")
    parser.add_argument("--mode", choices=["hybrid", "audio"], default="hybrid",
                        help="hybrid: diarization + visual lip-activity mapping (default). "
                             "audio: diarization + speech-dominance mapping only.")
    parser.add_argument("--num-speakers", type=int, default=2, help="Number of speakers (default: 2)")
    parser.add_argument("--max-duration", type=float, default=1500.0,
                        help="Seconds of the episode to process (default: 1500 = 25 min)")
    parser.add_argument("--swap", action="store_true", help="Reverse the final speaker->camera mapping")
    parser.add_argument("--force", action="store_true", help="Ignore the diarization cache and re-run")
    parser.add_argument("--diarization-strategy", choices=["windowed", "global"],
                        default="windowed",
                        help="windowed preserves local exchanges (default); global is legacy")
    parser.add_argument("--diarization-window", type=float, default=60.0,
                        help="Local diarization window in seconds (default: 60)")
    parser.add_argument("--diarization-overlap", type=float, default=15.0,
                        help="Window overlap used for identity stitching (default: 15)")
    parser.add_argument("--second-speaker-max-cosine", type=float, default=0.70,
                        help="Maximum forced-pair cosine accepted as a recovered "
                             "second voice (default: 0.70)")
    parser.add_argument("--sync-offset", type=float, default=None,
                        help="Manual sync offset override in seconds (skips cross-correlation)")
    parser.add_argument("--no-preview", action="store_true", help="Skip the ffmpeg preview render")
    parser.add_argument("--preview-start", type=float, default=None,
                        help="Timeline second where the preview window starts (default: auto)")
    parser.add_argument("--editorial-profile", choices=["conservative", "balanced", "responsive"],
                        default="balanced", help="Camera-cut pacing policy (default: balanced)")
    parser.add_argument("--no-reactions", action="store_true",
                        help="Disable evidence-selected listener cutaways in overlong shots")
    parser.add_argument("--max-primary-shot", type=float, default=60.0,
                        help="Seconds before considering a listener cutaway (default: 60)")
    parser.add_argument("--timeline-fps", type=float, default=30.0,
                        help="FCP timeline frame rate (default: 30)")
    parser.add_argument("--offline", action="store_true",
                        help="Forbid model-network checks; requires a downloaded model")
    parser.add_argument("--cancel-file",
                        help="Optional sentinel file checked at safe stage/window boundaries")
    return parser


def validate_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    """Apply cheap release-scope validation before the engine is imported."""
    for label, path in (("--cam1", args.cam1), ("--cam2", args.cam2)):
        if not os.path.isfile(path):
            parser.error(f"{label} does not exist or is not a file: {path}")
    if os.path.abspath(args.cam1) == os.path.abspath(args.cam2):
        parser.error("--cam1 and --cam2 must be different files")
    if args.num_speakers != 2:
        parser.error("this release supports exactly two speakers/cameras")
    if args.max_duration <= 0:
        parser.error("--max-duration must be positive")
    if args.timeline_fps <= 0:
        parser.error("--timeline-fps must be positive")
    if args.max_primary_shot < 20:
        parser.error("--max-primary-shot must be at least 20 seconds")
    if (args.diarization_window <= args.diarization_overlap
            or args.diarization_overlap <= 0):
        parser.error("--diarization-window must exceed a positive --diarization-overlap")
    if not -1.0 <= args.second_speaker_max_cosine <= 1.0:
        parser.error("--second-speaker-max-cosine must be between -1 and 1")
