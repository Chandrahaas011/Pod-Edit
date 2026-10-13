"""Apply completed PodEdit cut-review decisions to a copy of the timeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone

from pipeline.cache import atomic_write_json, file_signature
from pipeline.review import apply_cut_reviews


def main():
    parser = argparse.ArgumentParser(description="Apply numbered human cut-review decisions")
    parser.add_argument("--manifest", help="Run manifest; supplies source, media, sync, and FPS paths")
    parser.add_argument("--export-dir", help="Write a complete reviewed bundle to this new directory")
    parser.add_argument("--segments", help="Original podedit_segments.json")
    parser.add_argument("--review", help="Completed podedit_cut_report.csv")
    parser.add_argument("--output", help="New corrected segment JSON")
    parser.add_argument("--audit-output", help="Optional JSON summary of applied decisions")
    parser.add_argument("--xml-output", help="Optional validated Resolve XML output")
    parser.add_argument("--preview-output", help="Optional 60-second corrected preview")
    parser.add_argument("--cam1", help="Camera 1 video, required for XML/preview export")
    parser.add_argument("--cam2", help="Camera 2 video, required for XML/preview export")
    parser.add_argument("--audio", help="Master Camera 1 WAV, required for XML/preview export")
    parser.add_argument("--sync-offset", type=float,
                        help="Verified Camera 2 sync offset, required for XML/preview export")
    parser.add_argument("--timeline-fps", type=float)
    args = parser.parse_args()

    manifest = None
    if args.manifest:
        if not os.path.isfile(args.manifest):
            parser.error(f"--manifest does not exist: {args.manifest}")
        with open(args.manifest, encoding="utf-8") as handle:
            manifest = json.load(handle)
        outputs = manifest.get("outputs", {})
        inputs = manifest.get("inputs", {})
        args.segments = args.segments or outputs.get("segments")
        args.review = args.review or outputs.get("cut_report_csv")
        args.cam1 = args.cam1 or inputs.get("camera1", {}).get("path")
        args.cam2 = args.cam2 or inputs.get("camera2", {}).get("path")
        args.audio = (args.audio or outputs.get("camera1_audio") or
                      os.path.join(os.path.dirname(os.path.abspath(args.manifest)),
                                   "camera1_audio.wav"))
        if args.sync_offset is None:
            args.sync_offset = manifest.get("sync", {}).get("offset_seconds")
        if args.timeline_fps is None:
            args.timeline_fps = manifest.get("configuration", {}).get("timeline_fps")
    if args.export_dir:
        export_dir = os.path.abspath(args.export_dir)
        args.output = args.output or os.path.join(export_dir, "reviewed_segments.json")
        args.audit_output = args.audit_output or os.path.join(export_dir, "review_audit.json")
        args.xml_output = args.xml_output or os.path.join(export_dir, "reviewed_timeline.xml")
        args.preview_output = args.preview_output or os.path.join(export_dir, "reviewed_preview.mp4")
    missing_core = [name for name in ("segments", "review", "output")
                    if getattr(args, name) is None]
    if missing_core:
        parser.error("required directly or via --manifest/--export-dir: " +
                     ", ".join(f"--{name}" for name in missing_core))
    if not os.path.isfile(args.segments):
        parser.error(f"--segments does not exist: {args.segments}")
    if not os.path.isfile(args.review):
        parser.error(f"--review does not exist: {args.review}")
    if os.path.abspath(args.output) == os.path.abspath(args.segments):
        parser.error("--output must differ from --segments; source timelines are never overwritten")

    media_requested = args.xml_output or args.preview_output
    args.timeline_fps = 30.0 if args.timeline_fps is None else args.timeline_fps
    if args.timeline_fps <= 0:
        parser.error("--timeline-fps must be greater than zero")
    if media_requested:
        missing = [name for name in ("cam1", "cam2", "audio", "sync_offset")
                   if getattr(args, name) is None]
        if missing:
            parser.error("XML/preview export requires: " + ", ".join(f"--{name.replace('_', '-')}"
                                                                       for name in missing))
        for label, path in (("--cam1", args.cam1), ("--cam2", args.cam2), ("--audio", args.audio)):
            if not os.path.isfile(path):
                parser.error(f"{label} does not exist: {path}")
    with open(args.segments, encoding="utf-8") as handle:
        segments = json.load(handle)
    with open(args.review, newline="", encoding="utf-8-sig") as handle:
        review_rows = list(csv.DictReader(handle))
    total_duration = max(segment["start"] + segment["duration"] for segment in segments)
    corrected, audit = apply_cut_reviews(segments, review_rows, total_duration)
    atomic_write_json(args.output, corrected)
    audit["created_utc"] = datetime.now(timezone.utc).isoformat()
    audit["provenance"] = {
        "source_manifest": None if args.manifest is None else os.path.abspath(args.manifest),
        "source_segments": file_signature(args.segments),
        "completed_review": file_signature(args.review),
    }
    audit["outputs"] = {"segments": os.path.abspath(args.output)}
    if args.xml_output:
        from pipeline.validator import validate_xml
        from pipeline.xml_builder import generate_resolve_xml
        os.makedirs(os.path.dirname(os.path.abspath(args.xml_output)), exist_ok=True)
        generate_resolve_xml(corrected, args.cam1, args.cam2, args.audio, args.sync_offset,
                             args.xml_output, timeline_fps=args.timeline_fps)
        xml_validation = validate_xml(args.xml_output)
        if not xml_validation["valid"]:
            raise RuntimeError("Reviewed XML validation failed: "
                               + "; ".join(xml_validation["errors"]))
        audit["xml_validation"] = xml_validation
        audit["outputs"]["xml"] = os.path.abspath(args.xml_output)
    if args.preview_output:
        from pipeline.preview import render_preview
        os.makedirs(os.path.dirname(os.path.abspath(args.preview_output)), exist_ok=True)
        rendered = render_preview(corrected, args.cam1, args.cam2, args.audio,
                                  args.sync_offset, args.preview_output)
        if rendered is None:
            raise RuntimeError("Reviewed preview render failed")
        audit["outputs"]["preview"] = os.path.abspath(rendered)
    if args.audit_output:
        atomic_write_json(args.audit_output, audit)
    print(f"Applied {len(audit['applied'])} decisions; {len(segments)} -> "
          f"{len(corrected)} segments; validation PASS")
    print(f"Corrected segments: {os.path.abspath(args.output)}")
    if args.xml_output:
        print(f"Validated XML: {os.path.abspath(args.xml_output)}")
    if args.preview_output:
        print(f"Preview: {os.path.abspath(args.preview_output)}")


if __name__ == "__main__":
    main()
