"""Publication-oriented timeline visualization."""

from __future__ import annotations

import argparse
import json
import os


def plot_camera_timeline(predicted: list, output_path: str, reference: list | None = None):
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    rows = [("PodEdit", predicted)]
    if reference is not None:
        rows.append(("Human reference", reference))
    fig, axis = plt.subplots(figsize=(10, 1.25 + 0.55 * len(rows)))
    colors = {1: "#285f8f", 2: "#d17b32"}
    for row, (label, segments) in enumerate(rows):
        for segment in segments:
            axis.broken_barh([(segment["start"], segment["duration"])],
                             (row - 0.32, 0.64), facecolors=colors[segment["camera"]])
        axis.text(-5, row, label, ha="right", va="center", fontsize=8)
    axis.set_yticks([])
    axis.set_xlabel("Timeline time (s)")
    axis.set_ylim(-0.6, len(rows) - 0.4)
    axis.grid(axis="x", alpha=0.2)
    axis.legend(handles=[Patch(color=colors[1], label="Camera 1"),
                         Patch(color=colors[2], label="Camera 2")],
                loc="upper right", frameon=False, ncol=2, fontsize=7)
    fig.tight_layout()
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Render a publication camera timeline")
    parser.add_argument("--predicted", required=True, help="PodEdit segment JSON")
    parser.add_argument("--output", required=True, help="PNG output path")
    parser.add_argument("--reference", help="Optional human-reference segment JSON")
    args = parser.parse_args()
    with open(args.predicted, "r", encoding="utf-8") as handle:
        predicted = json.load(handle)
    reference = None
    if args.reference:
        with open(args.reference, "r", encoding="utf-8") as handle:
            reference = json.load(handle)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    print(plot_camera_timeline(predicted, args.output, reference))


if __name__ == "__main__":
    main()
