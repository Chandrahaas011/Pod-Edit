from pathlib import Path
import json
import tempfile
import unittest

from pipeline.reproducibility import compare_fingerprints, fingerprint_manifest


class ReproducibilityTests(unittest.TestCase):
    def _fixture(self, root: Path) -> Path:
        artifact = (root / "segments.json").resolve()
        artifact.write_text("[]\n", encoding="utf-8")
        manifest = (root / "run_manifest.json").resolve()
        manifest.write_text(json.dumps({
            "podedit_version": "1.5", "configuration": {"mode": "audio"},
            "inputs": {"camera1": {"size": 2, "edge_sha256": "abc"}},
            "sync": {"offset_seconds": -1, "source": "measured"},
            "speaker_to_camera": {"A": 1}, "outputs": {"segments": str(artifact)},
            "created_utc": "volatile", "metrics": {"runtime_seconds": 99}}), encoding="utf-8")
        return manifest

    def test_volatile_manifest_fields_do_not_change_identity(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = self._fixture(Path(temporary))
            first = fingerprint_manifest(path)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["created_utc"] = "different"; payload["metrics"]["runtime_seconds"] = 1
            path.write_text(json.dumps(payload), encoding="utf-8")
            second = fingerprint_manifest(path)
            self.assertTrue(compare_fingerprints(first, second)["matches"])

    def test_artifact_change_is_detected(self):
        with tempfile.TemporaryDirectory(dir=".") as temporary:
            path = self._fixture(Path(temporary))
            first = fingerprint_manifest(path)
            (Path(temporary) / "segments.json").write_text("[1]\n", encoding="utf-8")
            second = fingerprint_manifest(path)
            comparison = compare_fingerprints(first, second)
            self.assertFalse(comparison["matches"])
            self.assertIn("segments", comparison["changed_artifacts"])
