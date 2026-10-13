"""Generate a deterministic local Python runtime and license audit."""

from __future__ import annotations

from importlib import metadata
from pathlib import Path
import json
import shutil


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "packaging"
EXCLUDED = {"pip", "setuptools"}


def distribution_size(distribution: metadata.Distribution) -> int:
    total = 0
    for relative in distribution.files or ():
        path = distribution.locate_file(relative)
        try:
            if path.is_file():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def normalized_license(distribution: metadata.Distribution) -> str:
    value = (distribution.metadata.get("License-Expression") or
             distribution.metadata.get("License") or "").strip()
    if value and value.upper() != "UNKNOWN":
        return value.splitlines()[0][:200]
    classifiers = distribution.metadata.get_all("Classifier") or []
    matches = [item.rsplit("::", 1)[-1].strip()
               for item in classifiers if "License ::" in item]
    if matches:
        return ", ".join(matches)
    for relative in distribution.files or ():
        name = str(relative).lower()
        if "license" not in name and "copying" not in name:
            continue
        try:
            start = distribution.locate_file(relative).read_text(
                encoding="utf-8", errors="replace")[:200].lower()
        except OSError:
            continue
        if "mit license" in start or "the mit license" in start:
            return "MIT"
        if "bsd 3-clause license" in start:
            return "BSD-3-Clause"
    return "REVIEW REQUIRED"


def collect_license_files(distributions: list[metadata.Distribution]) -> int:
    destination = OUTPUT / "THIRD_PARTY_LICENSES"
    if destination.exists():
        shutil.rmtree(destination)
    copied = 0
    for distribution in distributions:
        package = distribution.metadata.get("Name") or "unknown"
        for relative in distribution.files or ():
            filename = Path(str(relative)).name.lower()
            if not any(marker in filename for marker in ("license", "copying", "notice")):
                continue
            source = distribution.locate_file(relative)
            if not source.is_file():
                continue
            target = destination / f"{package}-{distribution.version}" / Path(str(relative)).name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists():
                target = target.with_name(f"{target.stem}-{copied}{target.suffix}")
            shutil.copyfile(source, target)
            copied += 1
    return copied


def main() -> None:
    distributions = list(metadata.distributions())
    records = []
    for distribution in distributions:
        name = distribution.metadata.get("Name")
        if not name or name.lower() in EXCLUDED:
            continue
        records.append({
            "name": name,
            "version": distribution.version,
            "bytes": distribution_size(distribution),
            "license": normalized_license(distribution),
            "project_url": (distribution.metadata.get("Home-page") or
                            distribution.metadata.get("Project-URL") or ""),
        })
    records.sort(key=lambda item: item["name"].lower())
    audit = {
        "schema_version": 1,
        "note": "Installed development environment; prune against clean-build imports before release.",
        "total_bytes": sum(item["bytes"] for item in records),
        "distributions": records,
    }
    (OUTPUT / "runtime-audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (OUTPUT / "requirements-lock.txt").write_text(
        "# Audited development lock; not yet the pruned production closure.\n" +
        "".join(f"{item['name']}=={item['version']}\n" for item in records), encoding="utf-8")
    lines = ["# Third-party runtime inventory\n",
             "Generated from installed package metadata. `REVIEW REQUIRED` entries must be resolved before release.\n",
             "| Package | Version | License metadata | Installed MiB |\n",
             "|---|---:|---|---:|\n"]
    for item in records:
        license_text = item["license"].replace("|", "\\|")
        lines.append(f"| {item['name']} | {item['version']} | {license_text} | "
                     f"{item['bytes'] / 1024 ** 2:.1f} |\n")
    (OUTPUT / "THIRD_PARTY_INVENTORY.md").write_text("".join(lines), encoding="utf-8")
    license_files = collect_license_files(distributions)
    print(f"Audited {len(records)} distributions, {audit['total_bytes'] / 1024 ** 2:.1f} MiB installed; "
          f"collated {license_files} license/notice files.")


if __name__ == "__main__":
    main()
