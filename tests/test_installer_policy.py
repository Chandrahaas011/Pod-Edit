from pathlib import Path
import unittest


class InstallerPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = Path("packaging/PodEdit.iss").read_text(encoding="utf-8")

    def test_installer_is_per_user_and_does_not_require_elevation(self):
        self.assertIn("DefaultDirName={localappdata}\\Programs\\PodEdit", self.text)
        self.assertIn("PrivilegesRequired=lowest", self.text)

    def test_public_default_excludes_gated_models(self):
        self.assertIn('Excludes: ".model_cache\\*"', self.text)
        self.assertIn("#ifdef INTERNAL_OFFLINE_BUILD", self.text)

    def test_uninstall_does_not_delete_user_data(self):
        section = self.text.split("[UninstallDelete]", 1)[1]
        self.assertNotIn("Type:", section)
        self.assertNotIn("Name:", section)

    def test_installer_has_stable_app_id(self):
        self.assertIn("AppId={{A01A78B2-36DD-4BF5-82D1-9AD26F0850D4}", self.text)

    def test_engine_freeze_requires_and_embeds_source_fingerprint(self):
        spec = Path("packaging/PodEdit.Engine.spec").read_text(encoding="utf-8")
        self.assertIn("source-fingerprint.json", spec)
        self.assertIn("if not source_fingerprint.is_file()", spec)
        self.assertIn("datas = [(str(source_fingerprint), '.')]", spec)
