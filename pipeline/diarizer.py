import time
import warnings
import os
import json

import numpy as np
import torch
from itertools import permutations
warnings.filterwarnings("ignore", category=UserWarning, module=r"pyannote\.audio\.core\.io")
from pyannote.audio import Pipeline
from pipeline.cache import atomic_write_json
from pipeline.audio_io import load_mono
from pipeline.diarization_contract import (
    DIARIZATION_MODEL,
    SECOND_SPEAKER_MAX_COSINE,
    STITCHING_VERSION,
    WINDOW_CACHE_SCHEMA,
)


def _load_window_checkpoint(path, expected):
    """Return cached local turns only when every inference input matches."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != WINDOW_CACHE_SCHEMA:
        return None
    if any(payload.get(key) != value for key, value in expected.items()):
        return None
    turns = payload.get("turns")
    embeddings = payload.get("speaker_embeddings")
    if not isinstance(turns, list) or not isinstance(embeddings, dict):
        return None
    return {"turns": turns, "speaker_embeddings": embeddings}


def _load_pipeline(hf_token: str):
    """Load the gated model once so windowed inference does not reload weights."""
    from torch.torch_version import TorchVersion
    from pyannote.audio.core.task import Problem, Resolution, Specifications
    torch.serialization.add_safe_globals([TorchVersion, Specifications, Problem, Resolution])
    try:
        pipeline = Pipeline.from_pretrained(
            DIARIZATION_MODEL, token=hf_token,
            cache_dir=os.environ.get("PODEDIT_MODEL_CACHE"))
    except TypeError:
        pipeline = Pipeline.from_pretrained(
            DIARIZATION_MODEL, use_auth_token=hf_token,
            cache_dir=os.environ.get("PODEDIT_MODEL_CACHE"))
    if pipeline is None:
        raise RuntimeError(
            f"Failed to load {DIARIZATION_MODEL}. Accept the model terms on HuggingFace "
            "and make sure HF_TOKEN is valid."
        )
    pipeline.to(torch.device("cuda" if torch.cuda.is_available() else "cpu"))
    return pipeline


def _infer_output(pipeline, waveform, sample_rate, num_speakers, hook=None,
                  exact_speaker_count=False):
    audio = {"waveform": waveform, "sample_rate": sample_rate}
    kwargs = ({"num_speakers": num_speakers} if exact_speaker_count else
              {"min_speakers": 1, "max_speakers": num_speakers})
    return pipeline(audio, hook=hook, **kwargs) if hook else pipeline(audio, **kwargs)


def _infer_exact_from_shared_features(pipeline, waveform, sample_rate, num_speakers,
                                      shared_features):
    """Recluster one window without recomputing neural front-end features.

    pyannote's public progress hook exposes the segmentation and embedding
    artifacts. Its exact-speaker call differs only at clustering time, so we
    temporarily provide those already-computed artifacts to the same pipeline
    implementation. Restoring both methods in ``finally`` keeps later windows
    isolated. Returns ``None`` when the installed backend did not expose the
    required artifacts, allowing the caller to use the proven full-pass path.
    """
    segmentations = shared_features.get("segmentation")
    embeddings = shared_features.get("embeddings")
    if segmentations is None or embeddings is None:
        return None
    original_segmentations = pipeline.get_segmentations
    original_embeddings = pipeline.get_embeddings
    try:
        pipeline.get_segmentations = lambda file, hook=None: segmentations
        pipeline.get_embeddings = (
            lambda file, binarized_segmentations, exclude_overlap=False, hook=None: embeddings)
        return _infer_output(
            pipeline, waveform, sample_rate, num_speakers, exact_speaker_count=True)
    finally:
        pipeline.get_segmentations = original_segmentations
        pipeline.get_embeddings = original_embeddings


def _exclusive_annotation(result):
    annotation = getattr(result, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = getattr(result, "speaker_diarization", result)
    return annotation


def _speaker_embeddings(result):
    """Return JSON-safe embeddings keyed by the labels documented by pyannote.

    Community-1 orders `speaker_embeddings` exactly like
    `speaker_diarization.labels()`. Zero-padded or non-finite rows are excluded
    so a weak window cannot contaminate the episode prototypes.
    """
    annotation = getattr(result, "speaker_diarization", None)
    matrix = getattr(result, "speaker_embeddings", None)
    if annotation is None or matrix is None:
        return {}
    labels = [str(label) for label in annotation.labels()]
    matrix = np.asarray(matrix, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != len(labels):
        return {}
    embeddings = {}
    for label, vector in zip(labels, matrix):
        norm = float(np.linalg.norm(vector))
        if np.all(np.isfinite(vector)) and norm > 1e-8:
            embeddings[label] = (vector / norm).tolist()
    return embeddings


def _embedding_pair_cosine(embeddings):
    """Return cosine similarity for an exact two-label recovery result."""
    labels = sorted(embeddings)
    if len(labels) != 2:
        return None
    first = np.asarray(embeddings[labels[0]], dtype=np.float64)
    second = np.asarray(embeddings[labels[1]], dtype=np.float64)
    if (first.ndim != 1 or second.ndim != 1 or first.shape != second.shape or
            not np.all(np.isfinite(first)) or not np.all(np.isfinite(second))):
        return None
    denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
    if denominator <= 1e-8:
        return None
    return float(np.dot(first, second) / denominator)


def _accept_second_speaker_recovery(primary_embeddings, recovery_embeddings,
                                    max_cosine=SECOND_SPEAKER_MAX_COSINE):
    """Keep a forced second identity only when the voices are well separated.

    A ranged first pass avoids splitting a monologue into two identities. A
    confirmation pass can recover a brief interjection that the ranged pass
    missed, but is accepted only when its two embedding centroids are distinct.
    """
    if len(primary_embeddings) != 1:
        return False, None
    pair_cosine = _embedding_pair_cosine(recovery_embeddings)
    return (pair_cosine is not None and pair_cosine <= max_cosine), pair_cosine


def _overlap_seconds(first, second):
    return max(0.0, min(first["end"], second["end"]) - max(first["start"], second["start"]))


def _stitch_label_map(local_turns, reference_turns, canonical_labels):
    """Map arbitrary labels in one window onto stable episode labels.

    The overlap is scored by *duration*, not turn count. With two speakers we
    test both permutations and retain the one that agrees most with the prior
    window. This prevents each local diarization call's arbitrary SPEAKER_00/
    SPEAKER_01 naming from introducing a false camera cut.
    """
    local_labels = sorted({turn["speaker"] for turn in local_turns})
    if not canonical_labels:
        return {label: f"PODCAST_SPEAKER_{index:02d}"
                for index, label in enumerate(local_labels)}
    if len(local_labels) != len(canonical_labels):
        # A window may contain only one participant. Match it to the identity
        # with greatest temporal agreement in the overlap.
        mapping = {}
        available = list(canonical_labels)
        for label in local_labels:
            candidates = [turn for turn in local_turns if turn["speaker"] == label]
            scores = {canonical: sum(_overlap_seconds(a, b) for a in candidates
                                     for b in reference_turns if b["speaker"] == canonical)
                      for canonical in available}
            winner = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else available[0]
            mapping[label] = winner
            available.remove(winner)
        return mapping
    best_mapping, best_score = None, -1.0
    for assigned in permutations(canonical_labels, len(local_labels)):
        mapping = dict(zip(local_labels, assigned))
        score = sum(_overlap_seconds(local, prior)
                    for local in local_turns for prior in reference_turns
                    if mapping[local["speaker"]] == prior["speaker"])
        if score > best_score:
            best_mapping, best_score = mapping, score
    return best_mapping


def _embedding_label_map(local_embeddings, canonical_prototypes):
    """Assign local speaker labels to episode identities by cosine similarity.

    Returns `(mapping, diagnostics)`. The full permutation is scored so two
    locally arbitrary labels cannot both select the same canonical identity.
    """
    local_labels = sorted(local_embeddings)
    canonical_labels = sorted(canonical_prototypes)
    if not local_labels or len(local_labels) != len(canonical_labels):
        return None, {"reason": "embedding-label-count-mismatch"}
    local = {label: np.asarray(local_embeddings[label], dtype=np.float64)
             for label in local_labels}
    canonical = {label: np.asarray(canonical_prototypes[label], dtype=np.float64)
                 for label in canonical_labels}
    if any(vector.ndim != 1 or not np.all(np.isfinite(vector)) or
           np.linalg.norm(vector) <= 1e-8 for vector in [*local.values(), *canonical.values()]):
        return None, {"reason": "invalid-embedding"}
    for values in (local, canonical):
        for label, vector in values.items():
            values[label] = vector / np.linalg.norm(vector)
    candidates = []
    for assigned in permutations(canonical_labels, len(local_labels)):
        mapping = dict(zip(local_labels, assigned))
        similarities = [float(np.dot(local[label], canonical[mapping[label]]))
                        for label in local_labels]
        candidates.append((sum(similarities), mapping, similarities))
    candidates.sort(key=lambda item: item[0], reverse=True)
    best_score, best_mapping, similarities = candidates[0]
    second_score = candidates[1][0] if len(candidates) > 1 else best_score
    return best_mapping, {
        "best_mean_cosine": best_score / len(local_labels),
        "assignment_margin": (best_score - second_score) / len(local_labels),
        "pair_cosines": similarities,
    }


def _prototype_vectors(states):
    return {label: state["sum"] / max(state["weight"], 1e-8)
            for label, state in states.items()}


def _update_prototypes(states, local_embeddings, label_map, local_turns):
    durations = {}
    for turn in local_turns:
        durations[turn["speaker"]] = durations.get(turn["speaker"], 0.0) + max(
            0.0, turn["end"] - turn["start"])
    for local_label, canonical_label in label_map.items():
        if local_label not in local_embeddings:
            continue
        vector = np.asarray(local_embeddings[local_label], dtype=np.float64)
        norm = float(np.linalg.norm(vector))
        if not np.all(np.isfinite(vector)) or norm <= 1e-8:
            continue
        vector /= norm
        # Cap a window's influence so a long monologue cannot erase the
        # identity evidence accumulated across many other windows.
        weight = min(30.0, max(0.5, durations.get(local_label, 0.5)))
        if canonical_label not in states:
            states[canonical_label] = {"sum": vector * weight, "weight": weight}
        else:
            states[canonical_label]["sum"] += vector * weight
            states[canonical_label]["weight"] += weight


def _global_embedding_maps(window_records, num_speakers=2):
    """Jointly reconcile all local identities with constrained cosine k-means.

    A two-speaker window must assign one centroid to each episode identity; a
    genuine monologue contributes one centroid to its nearest episode identity.
    Fitting all windows together avoids both forced-speaker hallucinations and
    error propagation from an ambiguous early sequential prototype.
    """
    canonical = [f"PODCAST_SPEAKER_{index:02d}" for index in range(num_speakers)]
    valid = []
    for index, record in enumerate(window_records):
        embeddings = record["speaker_embeddings"]
        labels = sorted(embeddings)
        if not labels or len(labels) > num_speakers:
            continue
        vectors = np.asarray([embeddings[label] for label in labels], dtype=np.float64)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if vectors.ndim != 2 or not np.all(np.isfinite(vectors)) or np.any(norms <= 1e-8):
            continue
        vectors /= norms
        durations = {label: 0.0 for label in labels}
        for turn in record["turns"]:
            if turn["speaker"] in durations:
                durations[turn["speaker"]] += max(0.0, turn["end"] - turn["start"])
        weights = np.asarray([min(30.0, max(0.5, durations[label])) for label in labels])
        valid.append({"index": index, "labels": labels, "vectors": vectors,
                      "weights": weights})
    if not valid:
        return {}, {"reason": "no-valid-embedding-windows", "valid_windows": 0}

    seeds = [item for item in valid if len(item["labels"]) == num_speakers]
    if not seeds:
        return {}, {"reason": "no-multi-speaker-seed-window",
                    "valid_windows": len(valid)}
    best = None
    for seed in seeds:
        centroids = seed["vectors"].copy()
        previous_signature = None
        iterations = 0
        for iterations in range(1, 51):
            assignments = []
            sums = np.zeros_like(centroids)
            total_weights = np.zeros(num_speakers, dtype=np.float64)
            score = 0.0
            margins = []
            for item in valid:
                candidates = []
                for assigned in permutations(range(num_speakers), len(item["labels"])):
                    similarities = [float(np.dot(item["vectors"][local], centroids[episode]))
                                    for local, episode in enumerate(assigned)]
                    candidates.append((sum(similarities), assigned, similarities))
                candidates.sort(key=lambda value: value[0], reverse=True)
                selected_score, assigned, similarities = candidates[0]
                alternative = candidates[1][0] if len(candidates) > 1 else selected_score
                margins.append((selected_score - alternative) / len(item["labels"]))
                score += selected_score
                assignments.append(assigned)
                for local, episode in enumerate(assigned):
                    weight = item["weights"][local]
                    sums[episode] += item["vectors"][local] * weight
                    total_weights[episode] += weight
            signature = tuple(assignments)
            for episode in range(num_speakers):
                if total_weights[episode] > 0:
                    centroids[episode] = sums[episode] / total_weights[episode]
                    centroids[episode] /= max(np.linalg.norm(centroids[episode]), 1e-8)
            if signature == previous_signature:
                break
            previous_signature = signature
        candidate = {"score": score, "assignments": assignments, "margins": margins,
                     "iterations": iterations, "centroids": centroids}
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    maps = {}
    for item, assigned in zip(valid, best["assignments"]):
        maps[item["index"]] = {label: canonical[episode]
                               for label, episode in zip(item["labels"], assigned)}

    # Canonical names are arbitrary, but keeping the first valid window's
    # sorted first label as SPEAKER_00 makes reruns deterministic and preserves
    # the historical label convention.
    first = seeds[0]
    if num_speakers == 2 and maps[first["index"]][first["labels"][0]] != canonical[0]:
        swap = {canonical[0]: canonical[1], canonical[1]: canonical[0]}
        maps = {index: {local: swap[episode] for local, episode in mapping.items()}
                for index, mapping in maps.items()}

    margins = best["margins"]
    diagnostics = {
        "method": "global-constrained-cosine",
        "valid_windows": len(valid),
        "total_windows": len(window_records),
        "iterations": best["iterations"],
        "mean_pair_cosine": best["score"] /
                            sum(len(item["labels"]) for item in valid),
        "assignment_margin_median": float(np.median(margins)),
        "assignment_margin_minimum": float(np.min(margins)),
        "ambiguous_windows_below_0_05": sum(margin < 0.05 for margin in margins),
        "single_speaker_windows": sum(len(item["labels"]) == 1 for item in valid),
    }
    return maps, diagnostics


def run_diarization(audio_path: str, num_speakers: int, hf_token: str,
                    max_duration: float = None) -> list:
    """Runs neural speaker diarization (pyannote) on the master audio track.

    Returns turns: [{"speaker": "SPEAKER_00", "start": s, "end": e, "duration": d}, ...]

    Windows note: pyannote's internal decoder (torchcodec/torchaudio) crashes
    on Windows, so audio is pre-loaded with soundfile/soxr and handed over as an
    in-memory {"waveform", "sample_rate"} dict. 16 kHz is mandatory — the
    underlying WavLM model was trained at 16 kHz.
    """
    print("  ┌─ NEURAL DIARIZATION (pyannote)")
    print(f"  │ model           : {DIARIZATION_MODEL}")
    start_t = time.time()

    # torch >= 2.6 defaults torch.load to weights_only=True; pyannote's
    # official checkpoints embed these classes, so allowlist them
    # (the checkpoint comes from the gated, terms-accepted HF repo).
    from torch.torch_version import TorchVersion
    from pyannote.audio.core.task import Problem, Resolution, Specifications
    torch.serialization.add_safe_globals([TorchVersion, Specifications, Problem, Resolution])

    try:
        pipeline = Pipeline.from_pretrained(
            DIARIZATION_MODEL, token=hf_token,
            cache_dir=os.environ.get("PODEDIT_MODEL_CACHE"))
    except TypeError:
        pipeline = Pipeline.from_pretrained(
            DIARIZATION_MODEL, use_auth_token=hf_token,
            cache_dir=os.environ.get("PODEDIT_MODEL_CACHE"))
    if pipeline is None:
        raise RuntimeError(
            f"Failed to load {DIARIZATION_MODEL}. Accept the model terms on HuggingFace "
            "and make sure HF_TOKEN is valid."
        )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline.to(device)
    print(f"  │ device          : {device} (model load {time.time() - start_t:.1f}s)")

    load_t = time.time()
    waveform, sample_rate = load_mono(audio_path, 16000, duration=max_duration)
    audio_in_memory = {"waveform": torch.from_numpy(waveform).unsqueeze(0), "sample_rate": sample_rate}
    audio_seconds = len(waveform) / sample_rate
    print(f"  │ audio           : {audio_seconds:.1f}s @ {sample_rate} Hz "
          f"({len(waveform)} samples, load {time.time() - load_t:.1f}s)")
    print(f"  │ speakers        : forcing num_speakers={num_speakers}")

    infer_t = time.time()
    try:
        from pyannote.audio.pipelines.utils.hook import ProgressHook
        with ProgressHook() as hook:
            diarization = pipeline(audio_in_memory, num_speakers=num_speakers, hook=hook)
    except ImportError:
        diarization = pipeline(audio_in_memory, num_speakers=num_speakers)
    infer_elapsed = time.time() - infer_t

    annotation = getattr(diarization, "exclusive_speaker_diarization", None)
    if annotation is None:
        annotation = getattr(diarization, "speaker_diarization", diarization)

    turns = []
    speaker_totals = {}
    for turn, _, speaker in annotation.itertracks(yield_label=True):
        dur = turn.end - turn.start
        turns.append({
            "speaker": speaker,
            "start": float(turn.start),
            "end": float(turn.end),
            "duration": float(dur),
        })
        speaker_totals[speaker] = speaker_totals.get(speaker, 0.0) + dur

    rtf = infer_elapsed / audio_seconds if audio_seconds else 0.0
    print(f"  │ inference       : {infer_elapsed:.1f}s for {audio_seconds:.1f}s audio "
          f"(real-time factor {rtf:.2f}x)")
    print(f"  │ turns           : {len(turns)}")
    for spk in sorted(speaker_totals):
        tot = speaker_totals[spk]
        pct = tot / audio_seconds * 100 if audio_seconds else 0.0
        print(f"  │   {spk}      : {tot:8.1f}s speech ({pct:5.1f}% of audio)")
    print(f"  └─ done in {time.time() - start_t:.1f}s total")

    return turns


def run_chunked_diarization(audio_path: str, num_speakers: int, hf_token: str,
                            max_duration: float = None, window_seconds: float = 60.0,
                            overlap_seconds: float = 15.0,
                            window_cache_dir: str | None = None,
                            cache_identity: str | None = None,
                            use_window_cache: bool = True,
                            return_diagnostics: bool = False,
                            second_speaker_max_cosine: float =
                            SECOND_SPEAKER_MAX_COSINE,
                            cancel_check=None) -> list | tuple[list, dict]:
    """Diarize overlapping local windows and stitch their identities.

    Community-1's segmentation is strong on this test episode, but a single
    25-minute clustering pass collapsed short speaker exchanges into the
    dominant identity. Local windows retain those exchanges. Their overlaps
    provide enough shared speech to reconcile arbitrary local label names.
    """
    if window_seconds <= overlap_seconds or overlap_seconds <= 0:
        raise ValueError("window_seconds must exceed a positive overlap_seconds")
    if not -1.0 <= second_speaker_max_cosine <= 1.0:
        raise ValueError("second_speaker_max_cosine must be between -1 and 1")
    print("  ┌─ WINDOWED NEURAL DIARIZATION (local turns + overlap stitching)")
    print(f"  │ model           : {DIARIZATION_MODEL}")
    started = time.time()
    waveform_np, sample_rate = load_mono(audio_path, 16000, duration=max_duration)
    waveform = torch.from_numpy(waveform_np).unsqueeze(0)
    duration = waveform.shape[1] / sample_rate
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    pipeline = None
    stride = window_seconds - overlap_seconds
    starts = []
    position = 0.0
    while position < duration:
        starts.append(position)
        if position + window_seconds >= duration:
            break
        position += stride

    accepted = []
    previous_full = []
    canonical_labels = []
    prototype_states = {}
    infer_total = 0.0
    cache_hits = 0
    cache_misses = 0
    recovery_attempts = 0
    recovery_cache_hits = 0
    recovery_cache_misses = 0
    recovery_accepted = 0
    recovery_infer_total = 0.0
    recovery_shared_feature_runs = 0
    recovery_pair_cosines = []
    embedding_stitches = 0
    overlap_fallbacks = 0
    embedding_margins = []
    window_records = []
    if window_cache_dir:
        os.makedirs(window_cache_dir, exist_ok=True)
    for index, window_start in enumerate(starts):
        if cancel_check is not None:
            # Prior window checkpoints were atomically persisted before this
            # safe boundary, so a cancelled job can resume without guessing.
            cancel_check(f"before diarization window {index + 1}/{len(starts)}")
        window_end = min(duration, window_start + window_seconds)
        sample_start, sample_end = round(window_start * sample_rate), round(window_end * sample_rate)
        expected = {
            "model": DIARIZATION_MODEL,
            "cache_identity": cache_identity,
            "num_speakers": num_speakers,
            "speaker_constraint": "range-1-to-max",
            "sample_rate": sample_rate,
            "window_start": window_start,
            "window_end": window_end,
        }
        checkpoint_path = (os.path.join(window_cache_dir, f"window_{index:04d}.json")
                           if window_cache_dir else None)
        checkpoint = (_load_window_checkpoint(checkpoint_path, expected)
                      if checkpoint_path and use_window_cache else None)
        if checkpoint is not None:
            local = checkpoint["turns"]
            local_embeddings = checkpoint["speaker_embeddings"]
            elapsed = 0.0
            cache_hits += 1
            status = "checkpoint"
        else:
            if pipeline is None:
                load_started = time.time()
                pipeline = _load_pipeline(hf_token)
                print(f"  │ device          : {device} (model load {time.time() - load_started:.1f}s)")
            infer_started = time.time()
            shared_features = {}

            def capture_feature(step_name, artifact, **kwargs):
                if step_name in {"segmentation", "embeddings"}:
                    shared_features[step_name] = artifact

            result = _infer_output(
                pipeline, waveform[:, sample_start:sample_end], sample_rate, num_speakers,
                hook=capture_feature)
            elapsed = time.time() - infer_started
            infer_total += elapsed
            cache_misses += 1
            status = "inferred"
            annotation = _exclusive_annotation(result)
            local_embeddings = _speaker_embeddings(result)
            local = []
            for turn, _, speaker in annotation.itertracks(yield_label=True):
                local.append({"speaker": str(speaker),
                              "start": float(turn.start + window_start),
                              "end": float(turn.end + window_start)})
            if checkpoint_path:
                atomic_write_json(checkpoint_path, {
                    "schema_version": WINDOW_CACHE_SCHEMA,
                    **expected,
                    "inference_seconds": elapsed,
                    "turns": local,
                    "speaker_embeddings": local_embeddings,
                })

        recovery_note = None
        if num_speakers == 2 and len(local_embeddings) == 1:
            recovery_attempts += 1
            recovery_dir = (os.path.join(window_cache_dir, "exact_speaker_recovery")
                            if window_cache_dir else None)
            if recovery_dir:
                os.makedirs(recovery_dir, exist_ok=True)
            recovery_path = (os.path.join(recovery_dir, f"window_{index:04d}.json")
                             if recovery_dir else None)
            recovery_expected = {
                "model": DIARIZATION_MODEL,
                "cache_identity": cache_identity,
                "num_speakers": num_speakers,
                "speaker_constraint": "exact",
                "sample_rate": sample_rate,
                "window_start": window_start,
                "window_end": window_end,
            }
            recovery = (_load_window_checkpoint(recovery_path, recovery_expected)
                        if recovery_path and use_window_cache else None)
            if recovery is not None:
                recovered_local = recovery["turns"]
                recovered_embeddings = recovery["speaker_embeddings"]
                recovery_cache_hits += 1
            else:
                if pipeline is None:
                    load_started = time.time()
                    pipeline = _load_pipeline(hf_token)
                    print(f"  │ device          : {device} "
                          f"(model load {time.time() - load_started:.1f}s)")
                recovery_started = time.time()
                recovery_result = _infer_exact_from_shared_features(
                    pipeline, waveform[:, sample_start:sample_end], sample_rate,
                    num_speakers, shared_features if status == "inferred" else {})
                if recovery_result is None:
                    recovery_result = _infer_output(
                        pipeline, waveform[:, sample_start:sample_end], sample_rate,
                        num_speakers, exact_speaker_count=True)
                else:
                    recovery_shared_feature_runs += 1
                recovery_elapsed = time.time() - recovery_started
                infer_total += recovery_elapsed
                recovery_infer_total += recovery_elapsed
                recovery_cache_misses += 1
                recovery_annotation = _exclusive_annotation(recovery_result)
                recovered_embeddings = _speaker_embeddings(recovery_result)
                recovered_local = []
                for turn, _, speaker in recovery_annotation.itertracks(yield_label=True):
                    recovered_local.append({
                        "speaker": str(speaker),
                        "start": float(turn.start + window_start),
                        "end": float(turn.end + window_start),
                    })
                if recovery_path:
                    atomic_write_json(recovery_path, {
                        "schema_version": WINDOW_CACHE_SCHEMA,
                        **recovery_expected,
                        "inference_seconds": recovery_elapsed,
                        "turns": recovered_local,
                        "speaker_embeddings": recovered_embeddings,
                    })
            accept_recovery, pair_cosine = _accept_second_speaker_recovery(
                local_embeddings, recovered_embeddings,
                max_cosine=second_speaker_max_cosine)
            if pair_cosine is not None:
                recovery_pair_cosines.append(pair_cosine)
            if accept_recovery:
                local = recovered_local
                local_embeddings = recovered_embeddings
                recovery_accepted += 1
                recovery_note = f"recovered-second-speaker cos={pair_cosine:.3f}"
            else:
                cosine_text = "invalid" if pair_cosine is None else f"{pair_cosine:.3f}"
                recovery_note = f"confirmed-monologue cos={cosine_text}"
        window_records.append({"window_start": window_start, "window_end": window_end,
                               "turns": local, "speaker_embeddings": local_embeddings})

        if index == 0:
            seed_labels = sorted(set(local_embeddings) |
                                 {turn["speaker"] for turn in local})
            label_map = {label: f"PODCAST_SPEAKER_{position:02d}"
                         for position, label in enumerate(seed_labels)}
            canonical_labels = list(label_map.values())
            stitch_method = "embedding-seed"
        else:
            overlap_start = window_start
            overlap_end = min(previous_full[-1]["window_end"], window_end) if previous_full else window_start
            reference = [turn for turn in previous_full
                         if turn["start"] < overlap_end and turn["end"] > overlap_start]
            label_map, embedding_diagnostics = _embedding_label_map(
                local_embeddings, _prototype_vectors(prototype_states))
            if label_map is not None:
                embedding_stitches += 1
                embedding_margins.append(embedding_diagnostics["assignment_margin"])
                stitch_method = (f"voice-embedding cos={embedding_diagnostics['best_mean_cosine']:.3f} "
                                 f"margin={embedding_diagnostics['assignment_margin']:.3f}")
            else:
                # Temporal overlap remains a last-resort path for legacy or
                # invalid model outputs, and is explicitly counted.
                label_map = _stitch_label_map(local, reference, canonical_labels)
                overlap_fallbacks += 1
                stitch_method = f"overlap-fallback ({embedding_diagnostics['reason']})"
        _update_prototypes(prototype_states, local_embeddings, label_map, local)
        mapped_full = [{"speaker": label_map[turn["speaker"]], "start": turn["start"],
                        "end": turn["end"], "window_end": window_end} for turn in local]

        core_start = window_start if index == 0 else window_start + overlap_seconds / 2.0
        core_end = window_end if index == len(starts) - 1 else window_end - overlap_seconds / 2.0
        for turn in mapped_full:
            start, end = max(core_start, turn["start"]), min(core_end, turn["end"])
            if end > start:
                accepted.append({"speaker": turn["speaker"], "start": start,
                                 "end": end, "duration": end - start})
        previous_full = mapped_full
        print(f"  │ window {index + 1:02d}/{len(starts):02d}  {window_start:7.1f}-{window_end:7.1f}s  "
              f"{len(local):3d} turns  {elapsed:5.1f}s  {status:10s}  "
              + ", ".join(f"{a}->{b}" for a, b in sorted(label_map.items()))
              + f"  [{stitch_method}]"
              + (f" [{recovery_note}]" if recovery_note else ""))

    # The online assignments above are useful progress diagnostics only. The
    # authoritative identity reconciliation is fitted jointly across every
    # saved window so ambiguous early centroids cannot cause identity drift.
    global_maps, global_diagnostics = _global_embedding_maps(
        window_records, num_speakers=num_speakers)
    accepted = []
    previous_global_full = []
    global_fallbacks = 0
    for index, record in enumerate(window_records):
        label_map = global_maps.get(index)
        if label_map is None:
            reference = [turn for turn in previous_global_full
                         if turn["start"] < record["window_start"] + overlap_seconds and
                         turn["end"] > record["window_start"]]
            label_map = _stitch_label_map(record["turns"], reference, canonical_labels)
            global_fallbacks += 1
        mapped_full = [{"speaker": label_map[turn["speaker"]], "start": turn["start"],
                        "end": turn["end"], "window_end": record["window_end"]}
                       for turn in record["turns"]]
        core_start = (record["window_start"] if index == 0 else
                      record["window_start"] + overlap_seconds / 2.0)
        core_end = (record["window_end"] if index == len(window_records) - 1 else
                    record["window_end"] - overlap_seconds / 2.0)
        for turn in mapped_full:
            start, end = max(core_start, turn["start"]), min(core_end, turn["end"])
            if end > start:
                accepted.append({"speaker": turn["speaker"], "start": start,
                                 "end": end, "duration": end - start})
        previous_global_full = mapped_full
    overlap_fallbacks = global_fallbacks
    embedding_stitches = len(global_maps)
    embedding_margins = [global_diagnostics.get("assignment_margin_median")]
    embedding_margins = [value for value in embedding_margins if value is not None]
    accepted.sort(key=lambda turn: (turn["start"], turn["end"]))
    diagnostics = {
        "stitching_version": STITCHING_VERSION,
        "windows": len(starts),
        "embedding_stitches": embedding_stitches,
        "overlap_fallbacks": overlap_fallbacks,
        "embedding_assignment_margin_median": (
            float(np.median(embedding_margins)) if embedding_margins else None),
        "embedding_assignment_margin_minimum": (
            global_diagnostics.get("assignment_margin_minimum")),
        "global_embedding_clustering": global_diagnostics,
        "checkpoint_hits": cache_hits,
        "checkpoint_misses": cache_misses,
        "second_speaker_recovery": {
            "attempts": recovery_attempts,
            "accepted": recovery_accepted,
            "rejected_as_monologue": recovery_attempts - recovery_accepted,
            "max_pair_cosine": second_speaker_max_cosine,
            "checkpoint_hits": recovery_cache_hits,
            "checkpoint_misses": recovery_cache_misses,
            "inference_seconds": recovery_infer_total,
            "shared_feature_runs": recovery_shared_feature_runs,
            "pair_cosine_minimum": (float(np.min(recovery_pair_cosines))
                                    if recovery_pair_cosines else None),
            "pair_cosine_maximum": (float(np.max(recovery_pair_cosines))
                                    if recovery_pair_cosines else None),
        },
        "inference_seconds": infer_total,
        "real_time_factor": infer_total / duration if duration else 0.0,
    }
    print(f"  └─ {len(accepted)} stitched turns; checkpoints {cache_hits} hit/{cache_misses} miss; "
          f"inference {infer_total:.1f}s; RTF {infer_total / duration:.2f}x; "
          f"voice embeddings {embedding_stitches}/{len(starts)} windows; "
          f"second-speaker recovery {recovery_accepted}/{recovery_attempts}; "
          f"overlap fallbacks {overlap_fallbacks}; total {time.time() - started:.1f}s")
    return (accepted, diagnostics) if return_diagnostics else accepted
