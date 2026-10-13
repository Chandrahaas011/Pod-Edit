"""Build release and CycloneDX manifests from verified local audits."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


ROOT = Path(__file__).resolve().parent


def main() -> None:
    audit_path = ROOT / "build" / "bundle-audit-current.json"
    bundle = json.loads(audit_path.read_text(encoding="utf-8"))
    runtime = json.loads((ROOT / "runtime-audit.json").read_text(encoding="utf-8"))
    source_path = ROOT / "build" / "source-fingerprint.json"
    source = (json.loads(source_path.read_text(encoding="utf-8"))
              if source_path.is_file() else None)
    manifest = {
        "schema_version": 1,
        "product": "PodEdit",
        "version": "1.4.0",
        "platform": "windows-x64",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "bundle": {key: bundle[key] for key in (
            "file_count", "total_bytes", "passed", "missing_required")},
        "entry_points": ["PodEdit.Desktop.exe", "PodEdit.Worker.exe", "PodEdit.Engine.exe"],
        "media_tools": ["tools/ffmpeg/bin/ffmpeg.exe", "tools/ffmpeg/bin/ffprobe.exe"],
        "model_distribution_status": "internal-prototype-only-pending-redistribution-rights",
        "signed": False,
        "clean_vm_certified": False,
        "source_fingerprint": (None if source is None else {
            "identity_sha256": source.get("identity_sha256"),
            "file_count": source.get("file_count"),
        }),
    }
    (ROOT / "build" / "release-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    components = [{"type": "library", "name": item["name"], "version": item["version"],
                   "licenses": [{"license": {"name": item["license"]}}]}
                  for item in runtime["distributions"]]
    sbom = {"bomFormat": "CycloneDX", "specVersion": "1.6", "version": 1,
            "metadata": {"component": {"type": "application", "name": "PodEdit",
                                         "version": "1.4.0"}},
            "components": components}
    (ROOT / "build" / "podedit.cdx.json").write_text(
        json.dumps(sbom, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Release manifest and SBOM written for {len(components)} components.")


if __name__ == "__main__":
    main()
