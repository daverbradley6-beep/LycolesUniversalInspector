import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "validate_live_capture.py"
MANIFEST_FIXTURE = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"

spec = importlib.util.spec_from_file_location("live_capture_validator", SOURCE)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class LiveCaptureValidatorTests(unittest.TestCase):
    def test_manifest_fixture_produces_blocked_readiness_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "out"
            summary = validator.build_summary(MANIFEST_FIXTURE, output, expected_place_id=85896571713843)
            self.assertEqual(summary["manifest"]["placeId"], 85896571713843)
            self.assertFalse(summary["generationReadiness"]["scriptGenerationReady"])
            self.assertIn(
                "legacy_manifest_missing_outcome_candidate_field",
                summary["generationReadiness"]["blockers"],
            )
            self.assertEqual(summary["interaction"]["events"], 8)
            self.assertEqual(summary["interaction"]["eventsReportedByInspector"], 153)
            self.assertTrue(summary["interaction"]["historyIsSubset"])
            self.assertEqual(summary["interaction"]["explicitOutcomeCandidateEvents"], 0)
            self.assertGreater(summary["interaction"]["transactionIdEvents"], 0)
            artifacts = summary["pipeline"]["artifacts"]
            self.assertTrue(artifacts["manifestAssistedLua"])
            self.assertTrue(artifacts["manifestReadiness"])
            self.assertFalse(artifacts["generatedUtilityLua"])

    def test_cli_writes_json_and_markdown_reports(self):
        with tempfile.TemporaryDirectory() as temp:
            output = pathlib.Path(temp) / "validation"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SOURCE),
                    "--manifest",
                    str(MANIFEST_FIXTURE),
                    "--output",
                    str(output),
                    "--place-id",
                    "85896571713843",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            payload = json.loads(completed.stdout.strip())
            self.assertTrue(payload["ok"])
            self.assertTrue((output / "live-capture-validation.json").is_file())
            self.assertTrue((output / "live-capture-validation.md").is_file())


if __name__ == "__main__":
    unittest.main()
