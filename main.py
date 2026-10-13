import hashlib
import json
import os
import sys
import time

from dotenv import load_dotenv
from pipeline.cli_contract import build_parser, validate_args
from pipeline.job_control import JobCancelled, check_cancel


def application_root() -> str:
    """Return stable mutable-runtime root in scripts and one-folder builds."""
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
    return os.path.abspath(base)


def load_hf_token():
    load_dotenv(os.path.join(application_root(), ".env"))
    token = os.environ.get("HF_TOKEN")
    if not token and os.environ.get("HF_HUB_OFFLINE") == "1":
        # A provisioned offline release already contains accepted model assets;
        # inference does not need to retain or package a personal access token.
        return None
    if not token:
        print("\n" + "=" * 62)
        print("ERROR: HuggingFace token not found")
        print("=" * 62)
        print("PodEdit uses pyannote for neural speaker diarization.")
        print("1. Accept terms: https://huggingface.co/pyannote/speaker-diarization-community-1")
        print("2. Create a token: https://huggingface.co/settings/tokens")
        print("3. Put HF_TOKEN=<token> in a .env file next to main.py")
        print("=" * 62)
        sys.exit(1)
    return token


def stage_banner(index, total, title):
    print("\n" + "═" * 62)
    print(f"  STAGE {index}/{total} — {title}")
    print("═" * 62)


def _main():
    # Windows terminals and redirected build logs may default to CP-1252.
    # Keep rich status output from crashing the application before it starts.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = build_parser()
    args = parser.parse_args()
    validate_args(parser, args)
    from pipeline.run_request import RunRequest
    request = RunRequest.from_namespace(args)
    args = request  # Keep the mature orchestration below parser-independent.

    def ensure_not_cancelled(boundary: str) -> None:
        check_cancel(request.cancel_file, boundary)

    ensure_not_cancelled("before source probing")

    print("\n╔" + "═" * 60 + "╗")
    print("║  PodEdit 1.5 — NEURAL HYBRID MULTI-CAM PODCAST EDITOR     ║")
    print("║  audio: pyannote diarization   video: lip-activity vote   ║")
    print("╚" + "═" * 60 + "╝")

    from pipeline.run_layout import RunLayout
    paths = RunLayout.create(request.output)
    cam1_audio_path = str(paths.camera1_audio)
    cam2_audio_path = str(paths.camera2_audio)
    raw_turns_path = str(paths.raw_turns)
    segments_path = str(paths.segments)
    sync_metrics_path = str(paths.sync_metrics)
    mapping_cache_path = str(paths.visual_mapping_cache)
    xml_path = str(paths.timeline_xml)
    preview_path = str(paths.preview)
    switch_review_path = str(paths.switch_review)
    priority_review_path = str(paths.priority_review)
    cut_report_json_path = str(paths.cut_report_json)
    cut_report_csv_path = str(paths.cut_report_csv)

    total_stages = 6 if args.no_preview else 7
    stage_times = {}
    run_start = time.time()

    # Configure cache/offline settings before importing Hugging Face/PyTorch.
    from pipeline.runtime import configure_runtime
    configure_runtime(request, application_root())

    # Heavy imports after arg parsing so --help stays instant.
    from pipeline.cache import atomic_write_json, file_signature, signatures_match
    from pipeline.diarization_cache import load_completed_turns, save_completed_turns
    from pipeline.diarization_contract import DIARIZATION_MODEL, STITCHING_VERSION
    from pipeline.editor import build_editorial_segments
    from pipeline.mapper import map_speakers_dominance, apply_swap
    from pipeline.preview import render_preview, render_switch_review
    from pipeline.reactions import add_reaction_cutaways
    from pipeline.review import build_cut_report, write_cut_report
    from pipeline.stage_services import extract_source_audio, probe_sources, resolve_sync
    from pipeline.validator import validate_segments, validate_xml
    from pipeline.visual_verifier import resolve_mapping_visual
    from pipeline.xml_builder import generate_resolve_xml

    # ── Stage 1: Probe ──────────────────────────────────────────────
    stage_banner(1, total_stages, "PROBING SOURCE VIDEOS")
    t0 = time.time()
    for label, meta in zip(("camera 1", "camera 2"), probe_sources(request)):
        print(f"  {label}: {meta['width']}x{meta['height']} @ {meta['fps']:.3f} fps, "
              f"{meta['frames']} frames, {meta['duration_seconds'] / 60:.1f} min")
    stage_times["probe"] = time.time() - t0

    # ── Stage 2: Audio extraction ───────────────────────────────────
    stage_banner(2, total_stages, "AUDIO EXTRACTION")
    t0 = time.time()
    extract_source_audio(request, paths, ensure_not_cancelled)
    stage_times["extract"] = time.time() - t0

    # ── Stage 3: Sync offset ────────────────────────────────────────
    stage_banner(3, total_stages, "SYNC OFFSET ESTIMATION")
    t0 = time.time()
    if request.sync_offset is not None:
        sync_offset = request.sync_offset
        print(f"  Manual override: {sync_offset:+.4f}s (cross-correlation skipped)")
    sync_result = resolve_sync(request, paths, ensure_not_cancelled)
    sync_offset = sync_result["offset_seconds"]
    stage_times["sync"] = time.time() - t0

    # ── Stage 4: Neural diarization ─────────────────────────────────
    ensure_not_cancelled("before diarization")
    stage_banner(4, total_stages, "NEURAL SPEAKER DIARIZATION")
    t0 = time.time()
    source_signature = file_signature(args.cam1)
    cache_valid = False
    diarization_diagnostics = {"strategy": args.diarization_strategy}
    if not args.force:
        completed_cache = load_completed_turns(
            raw_turns_path, request, source_signature,
            model=DIARIZATION_MODEL, stitching_version=STITCHING_VERSION)
        if completed_cache is not None:
            turns, diarization_diagnostics = completed_cache
            cache_valid = True
            print(f"  Cache hit: {len(turns)} turns from {raw_turns_path} "
                  f"(max_duration={args.max_duration}, num_speakers={args.num_speakers})")
    # Transitional fallback preserves compatibility with pre-service caches;
    # remove after all released caches have the strict typed identity.
    if not args.force and not cache_valid and os.path.exists(raw_turns_path):
        with open(raw_turns_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        cache_valid = (isinstance(cache, dict)
                       and cache.get("max_duration") == args.max_duration
                       and cache.get("num_speakers") == args.num_speakers
                       and cache.get("model") == DIARIZATION_MODEL
                       and cache.get("strategy") == args.diarization_strategy
                       and (args.diarization_strategy != "windowed" or
                            cache.get("stitching_version") == STITCHING_VERSION)
                       and (args.diarization_strategy != "windowed" or
                            cache.get("second_speaker_max_cosine") ==
                            args.second_speaker_max_cosine)
                       and cache.get("window_seconds") == args.diarization_window
                       and cache.get("overlap_seconds") == args.diarization_overlap
                       and signatures_match(cache.get("source"), source_signature))
        if cache_valid:
            turns = cache["turns"]
            diarization_diagnostics = cache.get("stitching_diagnostics",
                                                diarization_diagnostics)
            print(f"  Cache hit: {len(turns)} turns from {raw_turns_path} "
                  f"(max_duration={args.max_duration}, num_speakers={args.num_speakers})")
        else:
            print("  Cache exists but parameters changed — re-running diarization.")
    if not cache_valid:
        # Importing PyTorch/pyannote takes several seconds. Keep it entirely
        # off the warm-cache path, where no neural inference is required.
        from pipeline.diarizer import run_chunked_diarization, run_diarization
        hf_token = load_hf_token()
        if args.diarization_strategy == "windowed":
            turns, diarization_diagnostics = run_chunked_diarization(
                cam1_audio_path, args.num_speakers, hf_token, args.max_duration,
                args.diarization_window, args.diarization_overlap,
                window_cache_dir=str(paths.diarization_windows),
                cache_identity=source_signature["edge_sha256"],
                use_window_cache=not args.force, return_diagnostics=True,
                second_speaker_max_cosine=args.second_speaker_max_cosine,
                cancel_check=ensure_not_cancelled)
        else:
            turns = run_diarization(
                cam1_audio_path, args.num_speakers, hf_token, args.max_duration)
        save_completed_turns(
            raw_turns_path, request, source_signature, turns, diarization_diagnostics,
            model=DIARIZATION_MODEL, stitching_version=STITCHING_VERSION)
        print(f"  Cached {len(turns)} raw turns -> {raw_turns_path}")
    stage_times["diarize"] = time.time() - t0

    # ── Stage 5: Speaker -> camera mapping ──────────────────────────
    ensure_not_cancelled("before speaker-to-camera mapping")
    stage_banner(5, total_stages, f"SPEAKER-TO-CAMERA MAPPING (mode: {args.mode})")
    t0 = time.time()
    mapping = None
    mapping_diagnostics = {"mode": args.mode}
    if args.mode == "hybrid":
        turns_digest = hashlib.sha256(
            json.dumps(turns, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        mapping_key = {
            "schema_version": 1,
            "camera1": source_signature,
            "camera2": file_signature(args.cam2),
            "turns_sha256": turns_digest,
            "sync_offset_seconds": sync_offset,
            "visual_verifier_version": 4,
        }
        mapping_cache = None
        if not args.force and os.path.exists(mapping_cache_path):
            try:
                with open(mapping_cache_path, "r", encoding="utf-8") as handle:
                    candidate = json.load(handle)
                if candidate.get("key") == mapping_key:
                    mapping_cache = candidate
            except (OSError, ValueError, AttributeError):
                mapping_cache = None
        if mapping_cache is not None:
            mapping = mapping_cache.get("visual_mapping")
            mapping_diagnostics = mapping_cache.get("diagnostics", {})
            print(f"  Verified visual-mapping cache hit: {mapping_cache_path}")
        else:
            mapping, mapping_diagnostics = resolve_mapping_visual(
                turns, args.cam1, args.cam2, sync_offset)
            atomic_write_json(mapping_cache_path, {
                "key": mapping_key,
                "visual_mapping": mapping,
                "diagnostics": mapping_diagnostics,
            })
            print(f"  Visual-mapping evidence cached -> {mapping_cache_path}")
    if mapping is None:
        mapping = map_speakers_dominance(turns)
    if args.swap:
        mapping = apply_swap(mapping)
    print("  Final mapping: " + ", ".join(f"{spk} -> Camera {cam}" for spk, cam in mapping.items()))
    stage_times["mapping"] = time.time() - t0

    # ── Stage 6: Segments + XML ─────────────────────────────────────
    ensure_not_cancelled("before segment assembly and XML export")
    stage_banner(6, total_stages, "SEGMENT ASSEMBLY & XML EXPORT")
    t0 = time.time()
    from pipeline.audio_metadata import wav_duration
    audio_duration = wav_duration(cam1_audio_path)
    total_duration = min(audio_duration, args.max_duration)
    print(f"  Edit length: {total_duration:.1f}s "
          f"(audio {audio_duration:.1f}s, cap {args.max_duration:.0f}s)\n")

    segments, editorial_diagnostics = build_editorial_segments(
        turns, mapping, total_duration, args.editorial_profile)
    print(f"  Editorial policy: {args.editorial_profile}; "
          f"suppressed {editorial_diagnostics['suppressed_takeovers']} short takeovers; "
          f"{editorial_diagnostics['final_segments']} final shots")
    reaction_diagnostics = {"enabled": False, "inserted": 0, "reason": "disabled"}
    if not args.no_reactions:
        segments, reaction_diagnostics = add_reaction_cutaways(
            segments, args.cam1, args.cam2, sync_offset, total_duration,
            max_primary_shot=args.max_primary_shot,
            master_audio_path=cam1_audio_path,
            diarization_window=args.diarization_window,
            diarization_overlap=args.diarization_overlap)
        print(f"  Reaction policy: inserted {reaction_diagnostics['inserted']} "
              f"evidence-selected listener shots; {len(segments)} total shots")
    segment_validation = validate_segments(segments, total_duration)
    if not segment_validation["valid"]:
        raise RuntimeError("Invalid segment timeline: " + "; ".join(segment_validation["errors"]))
    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2)
    print(f"\n  Segments saved -> {segments_path}\n")

    cut_report = build_cut_report(
        segments, total_duration, args.timeline_fps, mapping_diagnostics,
        reaction_diagnostics, args.diarization_window, args.diarization_overlap)
    write_cut_report(cut_report, cut_report_json_path, cut_report_csv_path)
    print(f"  Cut audit: {cut_report['summary']['cuts']} cuts; "
          f"{cut_report['summary']['high_priority']} high-priority review flags; "
          f"mapping={cut_report['summary']['mapping_status']}")
    print(f"  Cut report -> {cut_report_csv_path}\n")

    generate_resolve_xml(segments, args.cam1, args.cam2, cam1_audio_path, sync_offset,
                         xml_path, timeline_fps=args.timeline_fps)
    xml_validation = validate_xml(xml_path)
    if not xml_validation["valid"]:
        raise RuntimeError("Invalid XML export: " + "; ".join(xml_validation["errors"]))
    print(f"  XML validation: PASS ({xml_validation['duration_frames']} frames, "
          f"{xml_validation['video_clips']} video clips)")
    stage_times["segments+xml"] = time.time() - t0

    # ── Stage 7: Preview render ─────────────────────────────────────
    if not args.no_preview:
        ensure_not_cancelled("before preview rendering")
        stage_banner(7, total_stages, "PREVIEW RENDER (ground-truth sync check)")
        t0 = time.time()
        render_preview(segments, args.cam1, args.cam2, cam1_audio_path, sync_offset,
                       preview_path, window_start=args.preview_start)
        render_switch_review(segments, args.cam1, args.cam2, cam1_audio_path, sync_offset,
                             switch_review_path)
        priority_cut_numbers = [cut["cut_number"] for cut in cut_report["cuts"]
                                if cut["review_priority"] == "high"]
        if priority_cut_numbers:
            render_switch_review(
                segments, args.cam1, args.cam2, cam1_audio_path, sync_offset,
                priority_review_path, radius_seconds=5.0,
                cut_numbers=priority_cut_numbers)
        elif os.path.exists(priority_review_path):
            os.remove(priority_review_path)
            print(f"  Removed stale priority reel: {priority_review_path} "
                  "(current audit has no high-priority cuts)")
        stage_times["preview"] = time.time() - t0

    # ── Summary ─────────────────────────────────────────────────────
    total_runtime = time.time() - run_start
    cam_time = {1: 0.0, 2: 0.0}
    for seg in segments:
        cam_time[seg["camera"]] = cam_time.get(seg["camera"], 0.0) + seg["duration"]

    from pipeline.run_manifest import build_manifest
    manifest = build_manifest(
        request, paths,
        inputs={"camera1": file_signature(args.cam1), "camera2": file_signature(args.cam2)},
        sync=sync_result,
        diarization_diagnostics=diarization_diagnostics,
        speaker_to_camera=mapping,
        mapping_diagnostics=mapping_diagnostics,
        editorial_diagnostics=editorial_diagnostics,
        reaction_diagnostics=reaction_diagnostics,
        cut_report_summary=cut_report["summary"],
        segment_validation=segment_validation,
        xml_validation=xml_validation,
        runtime_seconds=total_runtime,
        stage_seconds=stage_times,
        duration_seconds=total_duration,
        segments=segments,
        camera_screen_time_seconds=cam_time,
    )
    manifest_path = str(paths.manifest)
    atomic_write_json(manifest_path, manifest)

    print("\n╔" + "═" * 60 + "╗")
    print("║  RUN SUMMARY                                               ║")
    print("╚" + "═" * 60 + "╝")
    for stage, elapsed in stage_times.items():
        print(f"  {stage:<14} {elapsed:8.1f}s")
    print(f"  {'TOTAL':<14} {total_runtime:8.1f}s ({total_runtime / 60:.1f} min "
          f"for {total_duration / 60:.1f} min of episode)")
    print(f"\n  Segments : {len(segments)}")
    print(f"  Camera 1 : {cam_time[1] / total_duration * 100:5.1f}% screen time")
    print(f"  Camera 2 : {cam_time[2] / total_duration * 100:5.1f}% screen time")
    print(f"\n  Timeline XML : {xml_path}")
    print(f"  Run manifest : {manifest_path}")
    if not args.no_preview and os.path.exists(preview_path):
        print(f"  Preview MP4  : {preview_path}  <- watch this first")
    if not args.no_preview and os.path.exists(switch_review_path):
        print(f"  Switch review: {switch_review_path}  <- every cut in one reel")
    if not args.no_preview and os.path.exists(priority_review_path):
        print(f"  Priority review: {priority_review_path}  <- inspect flagged cuts first")
    print("\n  Next: check the preview's lip-sync, then import the XML into")
    print("  DaVinci Resolve (File > Import > Timeline).")


def main():
    try:
        _main()
    except JobCancelled as exc:
        print(f"\n  CANCELLED: {exc}")
        print("  Completed source-bound checkpoints remain reusable on the next run.")
        return 130
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
