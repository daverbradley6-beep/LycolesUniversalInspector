"""Integration and regression tests for the v106 client observation pipeline."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from integrated_pipeline_v106 import generate, verify, emit_luau
from release_pipeline_v104 import build
from feature_planner_v106 import plan

PLACE = 85896571713843

def fixture():
    return {"placeId": PLACE, "objects": [
        {"path": ["PlayerGui", "HUD", "Coins"], "className": "TextLabel"},
        {"path": ["Players", "PlayerStats", "Wins"], "className": "IntValue"},
        {"path": ["Workspace", "Chest", "Prompt"], "className": "ProximityPrompt"},
    ]}

class IntegratedPipelineTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(fixture(), PLACE, tmp)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["features"], 2)
            self.assertTrue(verify(tmp)["ok"])
            script = (Path(tmp) / "LycolesFunctionalObserver.client.lua").read_text()
            self.assertIn("Activated:Connect", script)
            self.assertIn("readFeature(feature)", script)
            self.assertIn("gui:Destroy()", script)
            self.assertIn("game.PlaceId", script)

    def test_determinism(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate(fixture(), PLACE, a)
            generate(fixture(), PLACE, b)
            for name in ("inspection-report.json", "feature-plan.json",
                         "LycolesFunctionalObserver.client.lua", "manifest.json"):
                self.assertEqual((Path(a) / name).read_bytes(), (Path(b) / name).read_bytes())

    def test_tampering_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            script = Path(tmp) / "LycolesFunctionalObserver.client.lua"
            script.write_text(script.read_text() + "-- tampered\n")
            self.assertFalse(verify(tmp)["ok"])

    def test_unsupported_is_not_misrepresented(self):
        report = build(fixture(), PLACE)
        features = plan(report)
        self.assertEqual(len(features["features"]), 2)
        self.assertEqual(len(features["unsupported"]), 1)
        self.assertFalse(features["runtimeVerified"])
        self.assertFalse(features["gameplayVerified"])

    def test_place_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                generate(fixture(), PLACE + 1, tmp)

    def test_bad_feature_kind_rejected(self):
        feature_plan = plan(build(fixture(), PLACE))
        feature_plan["features"][0]["kind"] = "server_action"
        with self.assertRaises(ValueError):
            emit_luau(feature_plan)

    def test_manifest_claim_tamper_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["gameplayVerified"] = True
            path.write_text(json.dumps(manifest))
            self.assertFalse(verify(tmp)["ok"])

    def test_missing_artifact_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            (Path(tmp) / "feature-plan.json").unlink()
            self.assertFalse(verify(tmp)["ok"])

if __name__ == "__main__":
    unittest.main()
