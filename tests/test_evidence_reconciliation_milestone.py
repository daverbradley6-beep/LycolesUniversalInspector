import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "evidence_reconciliation_milestone.py"
SPEC = importlib.util.spec_from_file_location("evidence_reconciliation_milestone", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def phantom_like_plan():
    history = []
    for _ in range(11):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.MouseButton1.None",
            "controlType": "InputBegan.MouseButton1",
            "actionKind": "pointer-activate",
            "outcomeVerified": False,
            "workflow": {"action": "pointer-activate", "phase": "input-observed", "confidence": "bounded"},
            "stateChanges": [],
        })
    for _ in range(8):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.MouseButton2.None",
            "controlType": "InputBegan.MouseButton2",
            "actionKind": "pointer-activate",
            "outcomeVerified": False,
            "workflow": {"action": "pointer-activate", "phase": "input-observed", "confidence": "bounded"},
            "stateChanges": [],
        })
    for _ in range(39):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.Keyboard.LeftShift",
            "controlType": "InputBegan.Keyboard",
            "actionKind": "sprint",
            "outcomeVerified": False,
            "workflow": {"action": "sprint", "phase": "input-observed", "confidence": "bounded"},
            "stateChanges": [],
        })
    for _ in range(9):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.Keyboard.Space",
            "controlType": "InputBegan.Keyboard",
            "actionKind": "jump",
            "outcomeVerified": False,
            "workflow": {"action": "jump", "phase": "input-observed", "confidence": "bounded"},
            "stateChanges": [],
        })

    features = [
        {"feature": "combat", "interactionEvents": 0, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        {"feature": "movement", "interactionEvents": 48, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        {"feature": "inventory", "interactionEvents": 3, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        {"feature": "shops", "interactionEvents": 0, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        {"feature": "progression", "interactionEvents": 0, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
    ]

    return {
        "schemaVersion": "20.0",
        "integrity": {
            "scanId": "scan-phantom",
            "placeId": 292439477,
            "parts": 914,
            "objects": 92466,
            "interactionEvents": len(history),
            "scanComplete": True,
        },
        "features": features,
        "classCounts": {
            "Part": 24000,
            "MeshPart": 20000,
            "UnionOperation": 2200,
            "Humanoid": 1,
            "Camera": 20,
            "ScreenGui": 15,
            "Backpack": 1,
            "Tool": 0,
            "Team": 0,
            "Player": 0,
        },
        "observedInteractionHistory": history,
        "universalDiscovery": {
            "regions": [{"id": "region_1", "path": "Workspace.Map"}],
            "interactables": [{"id": "i_1", "path": "Workspace.Object.Prompt", "mechanism": "proximity_prompt"}],
            "interactionPatterns": [{"id": "pattern_1", "key": "input:keyboard", "memberCount": 48, "observedInteractions": 48}],
            "economySignals": [],
            "stateChangeSignals": [],
            "summary": {"regions": 1},
            "claims": {"sourceAuthenticityVerified": False},
            "schemaVersion": "89.universal-discovery.1",
        },
    }


def phantom_like_observation():
    gestures = [
        {
            "id": "gesture_1",
            "intent": {
                "likelyCameraMovement": True,
                "inputContextSignals": {"rightButtonInput": True, "mouseButton": "MouseButton2"},
                "physicalGesture": {"cameraTurnDegrees": 24.5, "kind": "drag", "durationSeconds": 0.8},
            },
        },
        {
            "id": "gesture_2",
            "intent": {
                "likelyCameraMovement": True,
                "inputContextSignals": {"rightButtonInput": False, "mouseButton": "MouseButton1"},
                "physicalGesture": {"cameraTurnDegrees": 6.2, "kind": "click", "durationSeconds": 0.1},
            },
        },
    ]
    return {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": "scan-phantom",
        "baselineScanId": "scan-phantom",
        "sourceDiagnostics": {"scanMode": "dynamic-observations"},
        "integrity": {
            "scanComplete": True,
            "placeId": 292439477,
            "scanId": "live-observation-scan",
            "baselineScanId": "scan-phantom",
            "parts": 914,
            "interactionEvents": 105,
        },
        "inputGestureObservations": gestures,
        "cameraOrientationSamples": [],
        "playerPositionHistory": [{"x": 1, "y": 2, "z": 3}, {"x": 2, "y": 2, "z": 4}],
        "eventPositionSnapshots": [{"x": 10, "y": 3, "z": 7}],
        "clickTargetObservations": [
            {
                "id": "click_1",
                "guiCandidates": [
                    {"path": "LocalPlayer.PlayerGui.MenuScreenGui.Pages.PageLoadoutMenu.DisplayWeaponSelection"},
                    {"path": "LocalPlayer.PlayerGui.HUD.WeaponFrame"},
                ],
            }
        ],
        "clickOutcomeRelationships": [
            {
                "id": "co_1",
                "outcomeCorroborated": False,
                "provenance": {"targetScope": "world"},
            }
        ],
    }


def targeted_session_payload():
    return {
        "schemaVersion": "31.0.targeted-evidence-session.1",
        "exportKind": "targeted-evidence-session",
        "sessionId": "targeted-session-1",
        "baselineScanId": "scan-phantom",
        "placeId": 292439477,
        "samples": {
            "characterEntities": [
                {"player": "Local", "isLocalPlayer": True, "team": "Blue"},
                {"player": "Opponent", "isLocalPlayer": False, "team": "Red"},
            ],
            "cameraSamples": [
                {"timestamp": "2026-11-13T19:00:00Z"},
                {"timestamp": "2026-11-13T19:00:01Z"},
            ],
            "cameraCorrelations": [
                {"mousePrimaryInputs": 3, "cameraDeltaMagnitude": 2.1},
            ],
            "inputSamples": [
                {"mousePrimaryInputs": 5},
                {"mousePrimaryInputs": 2},
            ],
            "loadoutSnapshots": [
                {
                    "equippedTools": ["Rifle"],
                    "backpackTools": ["Knife"],
                    "hudWeaponIndicatorPaths": ["LocalPlayer.PlayerGui.HUD.WeaponLabel"],
                    "hudWeaponIndicators": ["Rifle"],
                }
            ],
            "weaponSnapshots": [{"tool": "Rifle"}],
            "matchStateSamples": [
                {"signals": {"LocalPlayer.PlayerGui.HUD.ScoreLabel": "3-2", "LocalPlayer.PlayerGui.HUD.Timer": "12:10"}},
            ],
            "transitions": [
                {"path": "LocalPlayer.PlayerGui.HUD.ScoreLabel", "before": "2-2", "after": "3-2"},
            ],
        },
    }


def non_fps_plan():
    return {
        "schemaVersion": "20.0",
        "integrity": {
            "scanId": "scan-nonfps",
            "placeId": 123456,
            "parts": 4,
            "objects": 1200,
            "interactionEvents": 8,
            "scanComplete": True,
        },
        "features": [
            {"feature": "progression", "interactionEvents": 8, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
            {"feature": "inventory", "interactionEvents": 2, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        ],
        "classCounts": {"Part": 900, "MeshPart": 80, "Humanoid": 1, "ScreenGui": 4, "Backpack": 1},
        "observedInteractionHistory": [
            {
                "featureCandidate": "progression",
                "path": "LocalPlayer.Input.Keyboard.E",
                "controlType": "InputBegan.Keyboard",
                "actionKind": "interact",
                "outcomeVerified": False,
                "workflow": {"action": "interact", "phase": "input-observed", "confidence": "bounded"},
                "stateChanges": [],
            }
            for _ in range(8)
        ],
        "universalDiscovery": {
            "regions": [{"id": "region_farm", "path": "Workspace.Farm"}],
            "interactables": [{"id": "crop_1", "path": "Workspace.Farm.Crop", "mechanism": "click_detector"}],
            "interactionPatterns": [],
            "economySignals": [],
            "stateChangeSignals": [],
            "summary": {"regions": 1},
            "claims": {"sourceAuthenticityVerified": False},
            "schemaVersion": "89.universal-discovery.1",
        },
    }


class EvidenceReconciliationMilestoneTests(unittest.TestCase):
    def test_camera_gesture_vs_state_discrepancy_is_classified(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            result = MODULE._run_with_plan(
                plan=phantom_like_plan(),
                observation=phantom_like_observation(),
                output_dir=out,
                integration_context={"source": "test"},
            )
            recon = json.loads((out / "evidence-reconciliation-report.json").read_text(encoding="utf-8"))
            contracts = json.loads((out / "capability-evidence-contracts.json").read_text(encoding="utf-8"))

            self.assertEqual(recon["schemaVersion"], "121.evidence-reconciliation-report.1")
            self.assertGreater(recon["cameraEvidenceBreakdown"]["cameraRotationObservations"], 0)
            self.assertEqual(recon["cameraEvidenceBreakdown"]["cameraStateSamples"], 0)

            reqs = {item["requirementId"]: item for item in contracts["requirements"]}
            self.assertEqual(reqs["camera_state_samples"]["status"], "captured-not-extracted")
            self.assertEqual(reqs["camera_rotation_gesture"]["status"], "available")
            self.assertEqual(result["scanId"], "scan-phantom")

    def test_partial_feature_feasibility_uses_capability_level_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            MODULE._run_with_plan(plan=phantom_like_plan(), observation=phantom_like_observation(), output_dir=out)
            feasibility = json.loads((out / "reassessed-feature-feasibility.json").read_text(encoding="utf-8"))

            movement = next(item for item in feasibility["records"] if item["featureId"] == "movement_navigation_assist")
            capability_stages = {cap["capabilityId"]: cap["stage"] for cap in movement["capabilities"]}
            self.assertEqual(capability_stages["movement_navigation_assist.movement_telemetry_overlay"], "Implementation ready")
            self.assertIn(capability_stages["movement_navigation_assist.path_hinting"], {"Evidence sufficient for a bounded implementation", "Evidence partially available"})
            self.assertTrue((out / "MovementTelemetryOverlay.lua").is_file())

    def test_infrastructure_feature_not_counted_as_gameplay_progress(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            MODULE._run_with_plan(plan=phantom_like_plan(), observation=phantom_like_observation(), output_dir=out)
            feasibility = json.loads((out / "reassessed-feature-feasibility.json").read_text(encoding="utf-8"))
            ready = feasibility["summary"]["gameplayImplementationReadyCapabilities"]
            self.assertTrue(any(item["featureId"] == "movement_navigation_assist" for item in ready))
            self.assertFalse(any(item["featureId"] == "profile_and_keybind_manager" for item in ready))

    def test_targeted_inspection_requests_are_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            MODULE._run_with_plan(plan=phantom_like_plan(), observation=phantom_like_observation(), output_dir=out)
            plan = json.loads((out / "targeted-inspection-plan.json").read_text(encoding="utf-8"))

            self.assertEqual(plan["schemaVersion"], "121.targeted-inspection-plan.1")
            request_ids = {item["requestId"] for item in plan["requests"]}
            self.assertIn("character-entity-observation", request_ids)
            self.assertIn("combat-camera-weapon-correlation", request_ids)
            self.assertGreaterEqual(plan["summary"]["requestCount"], 2)

    def test_non_fps_fixture_still_uses_same_contract_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            MODULE._run_with_plan(plan=non_fps_plan(), observation=None, output_dir=out)
            contracts = json.loads((out / "capability-evidence-contracts.json").read_text(encoding="utf-8"))
            feasibility = json.loads((out / "reassessed-feature-feasibility.json").read_text(encoding="utf-8"))

            self.assertEqual(contracts["schemaVersion"], "121.capability-evidence-contracts.1")
            self.assertTrue(any(item["featureId"] == "combat_recoil_assist" for item in contracts["features"]))
            self.assertGreater(feasibility["summary"]["gameplayFeatureCount"], 0)

    def test_run_from_artifacts_supports_existing_capability_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            plan_path = root / "capability-plan.json"
            plan_path.write_text(json.dumps(phantom_like_plan()), encoding="utf-8")
            out = root / "out"

            result = MODULE.run_from_artifacts(capability_plan_path=plan_path, output_dir=out, observation_files=())
            self.assertIsInstance(result, dict)
            self.assertTrue((out / "evidence-reconciliation-report.json").is_file())
            self.assertTrue((out / "generation-integration-report.json").is_file())
            summary = json.loads((out / "generation-integration-report.json").read_text(encoding="utf-8"))
            self.assertFalse(summary["claims"]["gameplayVerified"])


    def test_targeted_session_payload_updates_signals_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            plan_path = root / "capability-plan.json"
            observation_path = root / "live-observation.json"
            targeted_path = root / "targeted-session.json"
            out = root / "out"

            plan_path.write_text(json.dumps(phantom_like_plan()), encoding="utf-8")
            observation_path.write_text(json.dumps(phantom_like_observation()), encoding="utf-8")
            targeted_path.write_text(json.dumps(targeted_session_payload()), encoding="utf-8")

            result = MODULE.run_from_artifacts(
                capability_plan_path=plan_path,
                output_dir=out,
                observation_files=(observation_path, targeted_path),
            )

            self.assertIsInstance(result, dict)
            self.assertEqual(result["summary"]["targetedSessionsConsumed"], 1)

            contracts = json.loads((out / "capability-evidence-contracts.json").read_text(encoding="utf-8"))
            reqs = {item["requirementId"]: item for item in contracts["requirements"]}
            self.assertEqual(reqs["camera_state_samples"]["status"], "available")
            self.assertEqual(reqs["weapon_equipped_signal"]["status"], "available")
            self.assertEqual(reqs["loadout_gui_structures"]["status"], "available")
            self.assertEqual(reqs["hud_weapon_indicators"]["status"], "available")
            self.assertIn(reqs["objective_hud_signals"]["status"], {"available", "captured-not-classified"})

            loadout_feature = next(item for item in contracts["features"] if item["featureId"] == "loadout_information_suite")
            loadout_stages = {cap["capabilityId"]: cap["stage"] for cap in loadout_feature["capabilities"]}
            self.assertEqual(loadout_stages["loadout_information_suite.loadout_gui_reader"], "Implementation ready")
            self.assertEqual(loadout_stages["loadout_information_suite.runtime_weapon_state"], "Implementation ready")

    def test_movement_overlay_module_exposes_runtime_contract_methods(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp)
            MODULE._run_with_plan(plan=phantom_like_plan(), observation=phantom_like_observation(), output_dir=out)
            code = (out / "MovementTelemetryOverlay.lua").read_text(encoding="utf-8")

            self.assertIn("function MovementTelemetry.new", code)
            self.assertIn("function MovementTelemetry:Start", code)
            self.assertIn("function MovementTelemetry:Stop", code)
            self.assertIn("function MovementTelemetry:UpdateConfig", code)
            self.assertIn("function MovementTelemetry:GetStatus", code)
            self.assertIn("UpdateInterval", code)
            self.assertIn("DisplayPosition", code)
            self.assertIn("VisibleFields", code)



if __name__ == "__main__":
    unittest.main()
