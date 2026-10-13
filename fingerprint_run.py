"""Create or compare a stable PodEdit editorial-output fingerprint."""

from pathlib import Path
import argparse
import json

from pipeline.reproducibility import compare_fingerprints, fingerprint_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--output", required=True)
    parser.add_argument("--compare")
    args = parser.parse_args()
    current = fingerprint_manifest(args.manifest)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if args.compare:
        expected = json.loads(Path(args.compare).read_text(encoding="utf-8"))
        result = compare_fingerprints(expected, current)
        print(json.dumps(result, sort_keys=True))
        return 0 if result["matches"] else 1
    print(current["identity_sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
