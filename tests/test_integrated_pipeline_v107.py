"""End-to-end tests for identity-aware v107 client observation generation."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from feature_planner_v107 import plan
from integrated_pipeline_v107 import emit_luau, generate, verify
from luau_contract_v107 import validate_source
from path_identity_v107 import build, migrate_v104_report
from release_pipeline_v104 import build as build_v104

PLACE = 85896571713843


def segment(name, class_name, ordinal=1):
    return {"name": name, "className": class_name, "ordinal": ordinal}


def rich_row(ordinal):
    return {
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            segment("Workspace", "Workspace"),
            segment("Stats", "Folder"),
            segment("Coins", "IntValue", ordinal),
        ],
        "className": "IntValue",
    }


def rich_fixture():
    return {"placeId": PLACE, "observations": [rich_row(2), rich_row(1)]}


def legacy_fixture():
    return {"placeId": PLACE, "objects": [
        {"path": ["PlayerGui", "HUD", "Coins"], "className": "TextLabel"},
        {"path": ["Workspace", "Chest", "Prompt"], "className": "ProximityPrompt"},
    ]}


class IntegratedPipelineV107Tests(unittest.TestCase):
    def test_end_to_end_full_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(rich_fixture(), PLACE, tmp)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["features"], 2)
            self.assertEqual(result["fullIdentityFeatures"], 2)
            self.assertEqual(result["legacyFeatures"], 0)
            report = json.loads((Path(tmp) / "inspection-report.json").read_text())
            self.assertEqual(report["schemaVersion"], "107.release")
            self.assertTrue(verify(tmp)["ok"])

    def test_duplicate_names_with_distinct_ordinals_are_emitted(self):
        features = plan(build(rich_fixture(), PLACE))["features"]
        self.assertEqual(len(features), 2)
        self.assertEqual(
            [feature["pathIdentity"][-1]["ordinal"] for feature in features],
            [1, 2],
        )

    def test_full_identity_resolver_checks_every_segment(self):
        script = emit_luau(plan(build(rich_fixture(), PLACE)))
        self.assertIn("child.Name == step.name and child.ClassName == step.className", script)
        self.assertIn("if count == step.ordinal then chosen = child", script)
        self.assertIn("for i=2,#feature.pathIdentity do", script)
        self.assertIn("if feature.pathResolution == 'full_identity' then", script)

    def test_legacy_input_rejects_ambiguous_siblings(self):
        script = emit_luau(plan(build(legacy_fixture(), PLACE)))
        self.assertIn("feature.pathResolution == 'legacy_terminal_identity'", script)
        self.assertIn("local function legacyChild(parent,name,className)", script)
        self.assertIn("if count ~= 1 then return nil end", script)
        self.assertIn("node = legacyChild(node,feature.path[i],nil)", script)
        self.assertIn("node = legacyChild(node,feature.path[#feature.path],feature.className)", script)
        self.assertNotIn("FindFirstChild(feature.path[i])", script)
        self.assertIn("pathIdentity=nil", script)

    def test_v104_report_migrates_without_fabricated_identity(self):
        old = build_v104(legacy_fixture(), PLACE)
        report = migrate_v104_report(old)
        feature_plan = plan(report)
        self.assertTrue(all(feature["pathIdentity"] is None for feature in feature_plan["features"]))
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(old, PLACE, tmp)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["legacyFeatures"], 2)

    def test_plan_rejects_identity_name_tampering(self):
        report = build(rich_fixture(), PLACE)
        report["objects"][0]["pathIdentity"][1]["name"] = "Other"
        with self.assertRaises(ValueError):
            plan(report)

    def test_emitter_rejects_ordinal_tampering(self):
        feature_plan = plan(build(rich_fixture(), PLACE))
        feature_plan["features"][0]["pathIdentity"][-1]["ordinal"] = 0
        with self.assertRaises(ValueError):
            emit_luau(feature_plan)

    def test_emitter_rejects_resolution_identity_mismatch(self):
        feature_plan = plan(build(rich_fixture(), PLACE))
        feature_plan["features"][0]["pathResolution"] = "legacy_terminal_identity"
        with self.assertRaises(ValueError):
            emit_luau(feature_plan)

    def test_deterministic_artifacts_across_input_order(self):
        reversed_fixture = copy.deepcopy(rich_fixture())
        reversed_fixture["observations"].reverse()
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            generate(rich_fixture(), PLACE, a)
            generate(reversed_fixture, PLACE, b)
            for name in (
                "inspection-report.json", "feature-plan.json", "quality-report.json",
                "inspection-diagnostics.json", "LycolesFunctionalObserver.client.lua", "manifest.json",
            ):
                self.assertEqual((Path(a) / name).read_bytes(), (Path(b) / name).read_bytes())

    def test_script_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(rich_fixture(), PLACE, tmp)
            script = Path(tmp) / "LycolesFunctionalObserver.client.lua"
            script.write_text(script.read_text() + "-- tampered\n")
            self.assertFalse(verify(tmp)["ok"])

    def test_plan_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(rich_fixture(), PLACE, tmp)
            path = Path(tmp) / "feature-plan.json"
            data = json.loads(path.read_text())
            data["features"][0]["pathIdentity"][-1]["ordinal"] = 99
            path.write_text(json.dumps(data))
            self.assertFalse(verify(tmp)["ok"])

    def test_static_contract_requires_full_identity_resolution(self):
        script = emit_luau(plan(build(rich_fixture(), PLACE)))
        self.assertTrue(validate_source(script, 2)["ok"])
        broken = script.replace("if count == step.ordinal then chosen = child", "if count == 1 then chosen = child")
        self.assertFalse(validate_source(broken, 2)["ok"])

    def test_static_contract_rejects_remote_invocation(self):
        script = emit_luau(plan(build(rich_fixture(), PLACE)))
        self.assertFalse(validate_source(script + "\nremote:FireServer()\n", 2)["ok"])

    def test_diagnostics_count_resolution_modes(self):
        source = {"placeId": PLACE, "objects": [rich_row(1), *legacy_fixture()["objects"]]}
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(source, PLACE, tmp)
            self.assertTrue(result["ok"], result)
            diagnostics = json.loads((Path(tmp) / "inspection-diagnostics.json").read_text())
            self.assertEqual(diagnostics["resolutionModes"], {
                "full_identity": 1,
                "legacy_terminal_identity": 2,
            })

    def test_manifest_identity_claim_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(rich_fixture(), PLACE, tmp)
            path = Path(tmp) / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["pathIdentityVersion"] = "tampered"
            path.write_text(json.dumps(manifest))
            self.assertFalse(verify(tmp)["ok"])


if __name__ == "__main__":
    unittest.main()
