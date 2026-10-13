"""Create a human annotation sheet or score PodEdit against completed labels."""

from __future__ import annotations

import argparse
import csv
import json
import os

from evaluation.metrics import evaluate_edit, evaluate_multiple_references


def load_segments(path: str) -> list:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON segment list: {path}")
    return data


def create_annotation_sheet(segments: list, output_path: str) -> None:
    with open(output_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "start_seconds", "end_seconds", "predicted_camera", "reference_camera", "notes"])
        writer.writeheader()
        for segment in segments:
            writer.writerow({
                "start_seconds": f"{segment['start']:.3f}",
                "end_seconds": f"{segment['start'] + segment['duration']:.3f}",
                "predicted_camera": segment["camera"],
                "reference_camera": "",
                "notes": "",
            })


def create_blind_annotation_sheet(duration: float, output_path: str) -> None:
    """Create an unbiased template in which editors define their own boundaries."""
    with open(output_path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "start_seconds", "end_seconds", "reference_camera", "notes"])
        writer.writeheader()
        writer.writerow({"start_seconds": "0.000", "end_seconds": f"{duration:.3f}",
                         "reference_camera": "", "notes": "split into independent shots"})


def load_reference_csv(path: str, expected_duration: float | None = None) -> list:
    segments = []
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            if not row.get("reference_camera", "").strip():
                raise ValueError(f"Missing reference_camera on CSV row {row_number}")
            start = float(row["start_seconds"])
            end = float(row["end_seconds"])
            camera = int(row["reference_camera"])
            if end <= start:
                raise ValueError(f"Non-positive interval on CSV row {row_number}")
            if camera not in (1, 2):
                raise ValueError(f"Invalid reference_camera on CSV row {row_number}")
            if segments and abs(start - (segments[-1]["start"] + segments[-1]["duration"])) > 1e-3:
                raise ValueError(f"Gap or overlap before CSV row {row_number}")
            if segments and segments[-1]["camera"] == camera:
                segments[-1]["duration"] = end - segments[-1]["start"]
            else:
                segments.append({"start": start, "duration": end - start,
                                 "camera": camera})
    if not segments:
        raise ValueError(f"Reference contains no intervals: {path}")
    if abs(segments[0]["start"]) > 1e-3:
        raise ValueError("Reference timeline must start at 0 seconds")
    if expected_duration is not None:
        actual_end = segments[-1]["start"] + segments[-1]["duration"]
        if abs(actual_end - expected_duration) > 1e-3:
            raise ValueError(
                f"Reference timeline ends at {actual_end:.3f}, expected {expected_duration:.3f}")
    return segments


def main():
    parser = argparse.ArgumentParser(description="PodEdit human-reference evaluation")
    parser.add_argument("--predicted", default="results/podedit_segments.json")
    parser.add_argument("--make-sheet", help="Write an annotation CSV and stop")
    parser.add_argument("--make-blind-sheet", help="Write a publication-grade free-boundary CSV")
    parser.add_argument("--reference", action="append", help="Completed annotation CSV; repeat for multiple editors")
    parser.add_argument("--output", default="results/evaluation_metrics.json")
    parser.add_argument("--tolerance", type=float, default=0.5)
    args = parser.parse_args()
    predicted = load_segments(args.predicted)
    duration = max(item["start"] + item["duration"] for item in predicted)
    if args.make_sheet:
        create_annotation_sheet(predicted, args.make_sheet)
        print(f"Annotation sheet written: {os.path.abspath(args.make_sheet)}")
        return
    if args.make_blind_sheet:
        create_blind_annotation_sheet(duration, args.make_blind_sheet)
        print(f"Blind annotation sheet written: {os.path.abspath(args.make_blind_sheet)}")
        return
    if not args.reference:
        parser.error("provide either --make-sheet or --reference")
    references = [load_reference_csv(path, duration) for path in args.reference]
    metrics = (evaluate_edit(predicted, references[0], duration, args.tolerance)
               if len(references) == 1 else
               evaluate_multiple_references(predicted, references, duration, args.tolerance))
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, indent=2)
        handle.write("\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
