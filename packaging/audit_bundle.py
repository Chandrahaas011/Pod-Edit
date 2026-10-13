"""Create a hash inventory and enforce release-folder exclusion policy."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline.bundle_audit import audit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(Path(args.root))
    Path(args.output).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                                 encoding="utf-8")
    print(f"{report['file_count']} files, {report['total_bytes'] / 1024 ** 2:.1f} MiB, "
          f"forbidden={len(report['forbidden'])}, missing={len(report['missing_required'])}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
