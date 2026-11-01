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
from luau_contract_v106 import validate_source
from feature_quality_v106 import assess

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
            self.assertEqual(result["features"], 3)
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
                         "LycolesFunctionalObserver.client.lua", "quality-report.json", "inspection-diagnostics.json", "manifest.json"):
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
        self.assertEqual(len(features["features"]), 3)
        self.assertEqual(len(features["unsupported"]), 0)
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

    def test_static_contract_detects_missing_refresh_wiring(self):
        script = emit_luau(plan(build(fixture(), PLACE)))
        self.assertTrue(validate_source(script, 3)["ok"])
        broken = script.replace("status.Activated:Connect(refreshAll)", "-- disconnected")
        self.assertFalse(validate_source(broken, 3)["ok"])

    def test_static_contract_rejects_remote_invocation(self):
        script = emit_luau(plan(build(fixture(), PLACE)))
        self.assertFalse(validate_source(script + "\\nremote:FireServer()\\n", 3)["ok"])

    def test_invalid_generated_path_rejected(self):
        feature_plan = plan(build(fixture(), PLACE))
        feature_plan["features"][0]["path"][0] = "ServerStorage"
        with self.assertRaises(ValueError):
            emit_luau(feature_plan)

    def test_feature_plan_preserves_class_identity(self):
        features = plan(build(fixture(), PLACE))["features"]
        self.assertEqual([feature["className"] for feature in features],
                         ["TextLabel", "IntValue", "ProximityPrompt"])

    def test_generated_resolver_requires_terminal_class_match(self):
        script = emit_luau(plan(build(fixture(), PLACE)))
        self.assertIn("child.Name == terminalName and child.ClassName == feature.className", script)
        self.assertIn("for _, child in ipairs(node:GetChildren()) do", script)

    def test_invalid_generated_class_rejected(self):
        feature_plan = plan(build(fixture(), PLACE))
        feature_plan["features"][0]["className"] = "RemoteEvent"
        with self.assertRaises(ValueError):
            emit_luau(feature_plan)

    def test_static_contract_detects_missing_class_match(self):
        script = emit_luau(plan(build(fixture(), PLACE)))
        broken = script.replace("child.ClassName == feature.className", "true")
        self.assertFalse(validate_source(broken, 3)["ok"])

    def test_quality_accounting_and_coverage(self):
        report = build(fixture(), PLACE)
        result = assess(report, plan(report))
        self.assertEqual(result["observations"], 3)
        self.assertEqual(result["implementedObservationControls"], 3)
        self.assertEqual(result["unsupportedObservations"], 0)
        self.assertEqual(result["coverage"], 1.0)

    def test_quality_threshold(self):
        report = build(fixture(), PLACE)
        result = assess(report, plan(report), minimum_features=4)
        self.assertFalse(result["ok"])
        self.assertIn("insufficient_features", result["issues"])

    def test_quality_artifact_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "quality-report.json"
            data = json.loads(path.read_text())
            data["implementedObservationControls"] = 999
            path.write_text(json.dumps(data))
            self.assertFalse(verify(tmp)["ok"])

    def test_generated_dashboard_controls(self):
        script = emit_luau(plan(build(fixture(), PLACE)))
        self.assertIn("search:GetPropertyChangedSignal('Text'):Connect(applyFilter)", script)
        self.assertIn("autoButton = button('Auto refresh: OFF'", script)
        self.assertIn("if autoRefresh then refreshAll() end", script)
        self.assertIn("while gui.Parent do", script)

    def test_manifest_control_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(fixture(), PLACE, tmp)
            self.assertTrue(result["ok"], result)
            manifest = json.loads((Path(tmp) / "manifest.json").read_text())
            self.assertEqual(manifest["functionalControlsGenerated"], 6)

    def test_integrated_inspection_diagnostics(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(fixture(), PLACE, tmp)
            self.assertTrue(result["ok"], result)
            data = json.loads((Path(tmp) / "inspection-diagnostics.json").read_text())
            self.assertEqual(data["supportedControls"], 3)
            self.assertEqual(data["coverage"], 1.0)

    def test_missing_artifact_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            (Path(tmp) / "feature-plan.json").unlink()
            self.assertFalse(verify(tmp)["ok"])

if __name__ == "__main__":
    unittest.main()
