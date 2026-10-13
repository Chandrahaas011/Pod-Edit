"""Metrics for comparing an automatic camera edit with a human reference."""

from __future__ import annotations

from itertools import combinations


def _camera_at(segments: list, timestamp: float):
    for segment in segments:
        if segment["start"] <= timestamp < segment["start"] + segment["duration"]:
            return segment["camera"]
    return None


def _actual_cuts(segments: list) -> list[float]:
    """Return boundaries where the selected camera really changes."""
    cuts = []
    previous = None
    for segment in sorted(segments, key=lambda item: float(item["start"])):
        camera = int(segment["camera"])
        if previous is not None and camera != previous:
            cuts.append(float(segment["start"]))
        previous = camera
    return cuts


def camera_time_accuracy(predicted: list, reference: list, duration: float) -> dict:
    """Exact duration-weighted agreement, computed at every segment boundary."""
    boundaries = {0.0, duration}
    for collection in (predicted, reference):
        for segment in collection:
            boundaries.add(max(0.0, min(duration, float(segment["start"]))))
            boundaries.add(max(0.0, min(duration,
                                         float(segment["start"]) + float(segment["duration"]))))
    ordered = sorted(boundaries)
    correct = 0.0
    confusion = {"1->1": 0.0, "1->2": 0.0, "2->1": 0.0, "2->2": 0.0}
    for start, end in zip(ordered, ordered[1:]):
        if end <= start:
            continue
        middle = (start + end) / 2.0
        ref_cam = _camera_at(reference, middle)
        pred_cam = _camera_at(predicted, middle)
        span = end - start
        if ref_cam == pred_cam:
            correct += span
        if ref_cam in (1, 2) and pred_cam in (1, 2):
            confusion[f"{ref_cam}->{pred_cam}"] += span
    return {"accuracy": correct / duration if duration else 0.0,
            "correct_seconds": correct, "duration_seconds": duration,
            "confusion_seconds": confusion}


def cut_boundary_metrics(predicted: list, reference: list, tolerance_seconds: float = 0.5) -> dict:
    """One-to-one cut matching within a symmetric temporal tolerance."""
    pred_cuts = _actual_cuts(predicted)
    ref_cuts = _actual_cuts(reference)
    unused = set(range(len(ref_cuts)))
    errors = []
    for cut in pred_cuts:
        candidates = [(abs(cut - ref_cuts[index]), index) for index in unused
                      if abs(cut - ref_cuts[index]) <= tolerance_seconds]
        if candidates:
            error, match = min(candidates)
            unused.remove(match)
            errors.append(error)
    true_positive = len(errors)
    precision = true_positive / len(pred_cuts) if pred_cuts else (1.0 if not ref_cuts else 0.0)
    recall = true_positive / len(ref_cuts) if ref_cuts else (1.0 if not pred_cuts else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "tolerance_seconds": tolerance_seconds,
        "predicted_cuts": len(pred_cuts),
        "reference_cuts": len(ref_cuts),
        "matched_cuts": true_positive,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_absolute_timing_error_seconds": sum(errors) / len(errors) if errors else None,
    }


def evaluate_edit(predicted: list, reference: list, duration: float,
                  tolerance_seconds: float = 0.5) -> dict:
    return {
        "camera_time": camera_time_accuracy(predicted, reference, duration),
        "cut_boundaries": cut_boundary_metrics(predicted, reference, tolerance_seconds),
    }


def duration_weighted_cohen_kappa(first: list, second: list, duration: float) -> dict:
    """Cohen's kappa using continuous timeline duration as observation weight."""
    agreement = camera_time_accuracy(first, second, duration)
    confusion = agreement["confusion_seconds"]
    observed = agreement["accuracy"]
    if duration <= 0:
        return {"kappa": 0.0, "observed_agreement": 0.0,
                "expected_agreement": 0.0, "duration_seconds": duration}
    first_1 = (confusion["1->1"] + confusion["1->2"]) / duration
    first_2 = (confusion["2->1"] + confusion["2->2"]) / duration
    second_1 = (confusion["1->1"] + confusion["2->1"]) / duration
    second_2 = (confusion["1->2"] + confusion["2->2"]) / duration
    expected = first_1 * second_1 + first_2 * second_2
    kappa = ((observed - expected) / (1.0 - expected)
             if expected < 1.0 else (1.0 if observed == 1.0 else 0.0))
    return {"kappa": kappa, "observed_agreement": observed,
            "expected_agreement": expected, "duration_seconds": duration}


def evaluate_multiple_references(predicted: list, references: list[list],
                                 duration: float,
                                 tolerance_seconds: float = 0.5) -> dict:
    """Score each editor separately and report pairwise editorial agreement."""
    if len(references) < 2:
        raise ValueError("at least two human references are required")
    per_editor = [evaluate_edit(predicted, reference, duration, tolerance_seconds)
                  for reference in references]
    pairwise = []
    for first_index, second_index in combinations(range(len(references)), 2):
        first, second = references[first_index], references[second_index]
        pairwise.append({
            "editors": [first_index + 1, second_index + 1],
            "camera_time": duration_weighted_cohen_kappa(first, second, duration),
            "cut_boundaries": cut_boundary_metrics(first, second, tolerance_seconds),
        })
    return {
        "editors": len(references), "per_editor": per_editor,
        "pairwise_agreement": pairwise,
        "macro_camera_accuracy": sum(
            item["camera_time"]["accuracy"] for item in per_editor) / len(per_editor),
        "macro_cut_f1": sum(
            item["cut_boundaries"]["f1"] for item in per_editor) / len(per_editor),
        "mean_pairwise_kappa": sum(
            item["camera_time"]["kappa"] for item in pairwise) / len(pairwise),
    }
