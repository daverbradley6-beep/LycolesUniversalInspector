import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "universal_architecture_milestone.py"
spec = importlib.util.spec_from_file_location("universal_architecture_milestone", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def minimal_plan():
    return {
        "schemaVersion": "20.0",
        "integrity": {
            "scanId": "scan-phantom",
            "placeId": 292439477,
            "parts": 2,
            "objects": 100,
            "interactionEvents": 3,
            "scanComplete": True,
        },
        "features": [
            {"feature": "combat", "interactionEvents": 3, "observableOutcomeCandidates": 0, "status": "interaction-observed"},
            {"feature": "inventory", "interactionEvents": 1, "observableOutcomeCandidates": 0, "status": "interaction-observed"},
        ],
        "classCounts": {"Part": 20, "Tool": 5, "TextButton": 12, "Humanoid": 1},
        "observedInteractionHistory": [
            {"controlType": "InputBegan.MouseButton1", "path": "LocalPlayer.Input.MouseButton1",
             "featureCandidate": "combat", "stateChanges": [{"key": "HUD.Ammo", "before": 30, "after": 29}]},
            {"controlType": "InputBegan.MouseButton2", "path": "LocalPlayer.Input.MouseButton2",
             "featureCandidate": "combat", "stateChanges": []},
            {"controlType": "InputBegan.Keyboard", "path": "LocalPlayer.Input.Keyboard.R",
             "featureCandidate": "inventory", "stateChanges": [{"key": "HUD.Reload", "before": 0, "after": 1}]},
        ],
        "universalDiscovery": {
            "regions": [{"id": "region_a", "path": "Workspace.Map", "positionedObjectCount": 10, "totalObjectCount": 20}],
            "interactables": [{"id": "i1", "path": "Workspace.Crate.Prompt", "mechanism": "proximity_prompt", "observedInteractions": 0}],
            "interactionPatterns": [],
            "economySignals": [],
            "stateChangeSignals": [],
            "summary": {},
            "claims": {"sourceAuthenticityVerified": False},
            "schemaVersion": "89.universal-discovery.1",
        },
    }


def minimal_gameplay():
    return {
        "systems": [
            {"id": "combat", "label": "Combat", "evidenceTier": "interaction_observed", "observedInteractions": 3,
             "observableOutcomeCandidates": 0}
        ]
    }


def minimal_intelligence():
    return {"summary": {"actionRecords": 3, "workflowCandidates": 1}}


class UniversalArchitectureMilestoneTests(unittest.TestCase):
    def test_validate_evidence_inventory_preserves_uploaded_vs_extracted_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            manifest = {
                "scanId": "scan-a",
                "placeId": 292439477,
                "version": "30.6.60",
                "uploadedParts": 543,
                "partCount": 914,
                "diagnostics": {"scanMode": "client-visible-read-only"},
            }
            (root / "Lycoles_292439477_scan-a_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            for index in range(1, 5):
                payload = {"scanId": "scan-a", "placeId": 292439477, "partCount": 4, "partIndex": index, "objects": []}
                (root / f"Lycoles_292439477_scan-a_part-{index:04d}.json").write_text(json.dumps(payload), encoding="utf-8")

            observation = {
                "scanId": "scan-a",
                "placeId": 292439477,
                "integrity": {"scanId": "scan-a", "placeId": 292439477, "scanComplete": True},
                "sourceDiagnostics": {"scanMode": "dynamic-observations"},
                "features": [],
            }
            obs_path = root / "observation.json"
            obs_path.write_text(json.dumps(observation), encoding="utf-8")

            inventory = module.validate_evidence_inventory(root, obs_path)
            self.assertEqual(inventory["extractedPartCount"], 4)
            self.assertEqual(inventory["manifestUploadedParts"], 543)
            self.assertEqual(inventory["manifestExpectedParts"], 914)
            self.assertTrue(inventory["partIndexContiguous"])
            self.assertTrue(inventory["observationIdentityMatchesManifest"])

    def test_build_game_model_marks_direct_and_inferred_layers(self):
        observation = {
            "gameName": "Phantom Forces",
            "cameraOrientationSamples": [{"yaw": 1}],
            "inputGestureObservations": [{"id": "g1"}],
            "clickTargetObservations": [{"id": "c1"}],
        }
        model = module.build_game_model(minimal_plan(), minimal_gameplay(), minimal_intelligence(), observation)
        self.assertEqual(model["schemaVersion"], "120.universal-game-model.1")
        self.assertEqual(model["directObservations"]["scanIdentity"]["placeId"], 292439477)
        self.assertTrue(any(item["evidenceLevel"] == "supported-inference"
                            for item in model["inferenceModel"]["genreCandidates"]))
        self.assertGreaterEqual(len(model["challenges"]), 1)

    def test_discovery_supports_non_fps_fixture_without_hardcoding(self):
        model = {
            "scanId": "scan-farm",
            "placeId": 123,
            "directObservations": {
                "scanIdentity": {"interactionEvents": 6},
                "cameraSamples": 0,
                "clickTargetSamples": 2,
                "featureSummary": [{"feature": "progression", "interactionEvents": 4}],
                "combatSignals": {"mousePrimaryInputs": 0, "stateSignals": []},
                "inputControlTypes": [{"controlType": "InputBegan.Keyboard", "count": 6}],
                "classDistributionTop": [{"class": "Part", "count": 40}],
                "worldRegions": 3,
            },
            "inferenceModel": {
                "genreCandidates": [{"genre": "tycoon", "evidenceLevel": "supported-inference", "confidence": "medium"}]
            },
            "challenges": [{"id": "challenge-resource"}],
        }
        discovery = module.discover_universal_tools(model)
        statuses = {item["id"]: item["status"] for item in discovery["proposals"]}
        self.assertEqual(discovery["schemaVersion"], "120.universal-tool-discovery.1")
        self.assertEqual(statuses["combat_target_assist"], "Proposed")
        self.assertIn(statuses["profile_and_keybind_manager"], {"Feasible", "Evidence required", "Proposed"})

    def test_configuration_and_gui_blueprint_are_generated(self):
        discovery = module.discover_universal_tools({
            "scanId": "scan-x",
            "placeId": 1,
            "directObservations": {
                "scanIdentity": {"interactionEvents": 8},
                "cameraSamples": 10,
                "clickTargetSamples": 5,
                "featureSummary": [{"feature": "combat", "interactionEvents": 8}],
                "combatSignals": {"mousePrimaryInputs": 4, "stateSignals": [{"key": "HUD.Ammo", "count": 4}]},
                "inputControlTypes": [{"controlType": "InputBegan.MouseButton1", "count": 4}],
                "classDistributionTop": [{"class": "Humanoid", "count": 12}],
                "worldRegions": 5,
            },
            "inferenceModel": {"genreCandidates": [{"genre": "fps-combat", "evidenceLevel": "supported-inference"}]},
            "challenges": [{"id": "challenge-a"}],
        })
        catalog = module.build_feature_configuration_catalog(discovery)
        feasibility = module.build_feasibility_records(discovery, catalog)
        gui = module.build_unified_gui_blueprint(discovery, catalog)

        self.assertEqual(catalog["schemaVersion"], "120.feature-config-catalog.1")
        self.assertGreater(catalog["summary"]["settingsCount"], 0)
        for schema in catalog["featureSchemas"].values():
            for setting in schema["settings"]:
                self.assertIn("id", setting)
                self.assertIn("type", setting)
                self.assertIn("runtimeBinding", setting)
                self.assertIn("persistence", setting)
        self.assertEqual(feasibility["schemaVersion"], "120.feature-feasibility.1")
        self.assertEqual(gui["schemaVersion"], "120.unified-gui-architecture.1")
        self.assertTrue(gui["window"]["singleWindow"])
        self.assertFalse(gui["diagnostics"]["separateAdminGuiAllowed"])


if __name__ == "__main__":
    unittest.main()
