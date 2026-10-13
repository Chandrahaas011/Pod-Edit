"""Inspect or explicitly remove reproducible artifacts from one completed job."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from pipeline.job_storage import CATEGORY_PATHS, inventory_job, remove_items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="One PodEdit job output folder")
    parser.add_argument("--category", action="append", choices=sorted(CATEGORY_PATHS),
                        help="Category to remove; repeat as needed")
    parser.add_argument("--delete", action="store_true",
                        help="Actually delete selected categories (default is report only)")
    args = parser.parse_args()
    root = Path(args.output).resolve()
    if not root.is_dir():
        parser.error(f"job output does not exist or is not a directory: {root}")

    items = inventory_job(root)
    totals = defaultdict(int)
    for item in items:
        totals[item.category] += item.bytes
    print(f"PodEdit job storage: {root}")
    for category in sorted(CATEGORY_PATHS):
        print(f"  {category:<16} {totals[category] / 1024 ** 2:9.1f} MiB")
    print(f"  {'known total':<16} {sum(totals.values()) / 1024 ** 2:9.1f} MiB")

    selected = set(args.category or [])
    if args.delete:
        if not selected:
            parser.error("--delete requires at least one --category")
        count, reclaimed = remove_items(root, selected)
        print(f"Removed {count} known artifacts; reclaimed {reclaimed / 1024 ** 2:.1f} MiB.")
    elif selected:
        planned = sum(item.bytes for item in items if item.category in selected)
        print(f"Dry run: selected categories would reclaim {planned / 1024 ** 2:.1f} MiB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
