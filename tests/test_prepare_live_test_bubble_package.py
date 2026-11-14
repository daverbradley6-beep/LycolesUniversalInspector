import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "prepare_live_test_bubble_package.py"
MANIFEST_FIXTURE = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"

spec = importlib.util.spec_from_file_location("prepare_live_test_bubble", SOURCE)
prep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prep)


class PrepareLiveTestBubblePackageTests(unittest.TestCase):
    def test_prepare_package_writes_expected_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = pathlib.Path(temp)
            artifact_dir = base / "e2e"
            output_dir = base / "live"
            result = prep.prepare_package(
                MANIFEST_FIXTURE,
                artifact_dir,
                output_dir,
                85896571713843,
            )
            self.assertEqual(result["targetCount"], 8)
            self.assertTrue((output_dir / "README.md").is_file())
            self.assertTrue((output_dir / "operator-checklist.md").is_file())
            self.assertTrue((output_dir / "targets-18-analysis.md").is_file())
            self.assertTrue((output_dir / "targets-18-analysis.json").is_file())
            self.assertTrue((output_dir / "LycolesManifestAssistedWorkflow.lua").is_file())
            self.assertTrue((output_dir / "manifest-assisted-workflow.json").is_file())
            self.assertTrue((output_dir / "manifest-readiness-v109.json").is_file())
            targets = json.loads((output_dir / "targets-18-analysis.json").read_text(encoding="utf-8"))
            self.assertEqual(len(targets), 8)
            self.assertIsNotNone(result["primaryPath"])


if __name__ == "__main__":
    unittest.main()
