"""Record the exact source identity immediately before freezing a release bundle."""

from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.source_identity import fingerprint_sources


def main() -> None:
    output = ROOT / "packaging" / "build" / "source-fingerprint.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = fingerprint_sources(ROOT)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Source fingerprint: {payload['identity_sha256']} ({payload['file_count']} files)")


if __name__ == "__main__":
    main()
