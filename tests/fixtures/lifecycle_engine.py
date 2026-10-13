"""Tiny subprocess fixture that behaves like a successful resumable engine."""

import argparse
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument("--cam1")
parser.add_argument("--cam2")
parser.add_argument("--output", required=True)
parser.add_argument("--cancel-file")
args, _ = parser.parse_known_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)
checkpoint = output / "fixture.checkpoint"
print("  STAGE 1/2 - FIXTURE PREPARE", flush=True)
cancel_mode = (Path(args.cancel_file).read_text(encoding="utf-8").strip()
               if args.cancel_file and Path(args.cancel_file).is_file() else None)
if cancel_mode and cancel_mode != "before-export":
    print("  CANCELLED: fixture safe boundary before preparation", flush=True)
    raise SystemExit(130)
if checkpoint.exists():
    print("  fixture checkpoint: resumed", flush=True)
else:
    checkpoint.write_text("complete\n", encoding="utf-8")
    print("  fixture checkpoint: created", flush=True)
print("  STAGE 2/2 - FIXTURE EXPORT", flush=True)
if cancel_mode:
    print("  CANCELLED: fixture safe boundary before export", flush=True)
    raise SystemExit(130)
xml = output / "podedit_timeline.xml"
xml.write_text("<xmeml/>\n", encoding="utf-8")
(output / "run_manifest.json").write_text(json.dumps({
    "schema_version": 2,
    "outputs": {"xml": str(xml.resolve())},
}), encoding="utf-8")
