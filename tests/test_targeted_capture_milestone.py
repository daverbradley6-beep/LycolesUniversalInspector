import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "targeted_capture_milestone.py"
SPEC = importlib.util.spec_from_file_location("targeted_capture_milestone", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def capability_plan_fixture() -> dict:
    history = []
    for _ in range(8):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.MouseButton1.None",
            "controlType": "InputBegan.MouseButton1",
            "actionKind": "pointer-activate",
            "stateChanges": [],
            "workflow": {"action": "pointer-activate", "phase": "input-observed", "confidence": "bounded"},
            "outcomeVerified": False,
        })
    for _ in range(4):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.Keyboard.LeftShift",
            "controlType": "InputBegan.Keyboard",
            "actionKind": "sprint",
            "stateChanges": [],
            "workflow": {"action": "sprint", "phase": "input-observed", "confidence": "bounded"},
            "outcomeVerified": False,
        })
    for _ in range(2):
        history.append({
            "featureCandidate": "movement",
            "path": "LocalPlayer.Input.Keyboard.Space",
            "controlType": "InputBegan.Keyboard",
            "actionKind": "jump",
            "stateChanges": [],
            "workflow": {"action": "jump", "phase": "input-observed", "confidence": "bounded"},
            "outcomeVerified": False,
        })

    return {
        "schemaVersion": "20.0",
        "integrity": {
            "scanId": "scan-phantom",
            "placeId": 292439477,
            "parts": 14,
            "objects": 1200,
            "interactionEvents": len(history),
            "scanComplete": True,
        },
        "features": [
            {"feature": "movement", "interactionEvents": 8, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
            {"feature": "combat", "interactionEvents": 2, "observableOutcomeCandidates": 0, "featureStateCorrelations": 0, "featureGuiCorrelations": 0},
        ],
        "classCounts": {
            "Part": 300,
            "MeshPart": 120,
            "Humanoid": 1,
            "Backpack": 1,
            "ScreenGui": 4,
        },
        "observedInteractionHistory": history,
        "universalDiscovery": {
            "regions": [{"id": "r1", "path": "Workspace.Map"}],
            "interactables": [{"id": "i1", "path": "Workspace.Map.Prompt", "mechanism": "proximity_prompt"}],
            "interactionPatterns": [],
            "economySignals": [],
            "stateChangeSignals": [],
            "summary": {"regions": 1},
            "claims": {"sourceAuthenticityVerified": False},
            "schemaVersion": "89.universal-discovery.1",
        },
    }


def dynamic_observation_fixture() -> dict:
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
            "parts": 14,
            "interactionEvents": 15,
        },
        "inputGestureObservations": [],
        "cameraOrientationSamples": [],
        "playerPositionHistory": [{"x": 1, "y": 2, "z": 3}],
        "eventPositionSnapshots": [{"x": 3, "y": 2, "z": 1}],
        "clickTargetObservations": [],
        "clickOutcomeRelationships": [],
    }


def targeted_evidence_fixture() -> dict:
    return {
        "schemaVersion": "31.0.targeted-evidence-session.1",
        "exportKind": "targeted-evidence-session",
        "sessionId": "targeted-1",
        "placeId": 292439477,
        "baselineScanId": "scan-phantom",
        "requestIds": [
            "character-entity-observation",
            "combat-camera-weapon-correlation",
            "match-objective-state-observation",
            "loadout-runtime-observation",
        ],
        "requestProgress": {},
        "samples": {
            "characterEntities": [
                {"player": "Local", "isLocalPlayer": True, "team": "Blue"},
                {"player": "Enemy", "isLocalPlayer": False, "team": "Red"},
            ],
            "entityEvents": [{"eventType": "character-present"}],
            "cameraSamples": [{"lookVector": {"x": 0, "y": 0, "z": -1}}],
            "cameraCorrelations": [{"mousePrimaryInputDelta": 2, "lookDeltaMagnitude": 0.2}],
            "inputSamples": [{"mousePrimaryInputs": 3}],
            "weaponSnapshots": [{"equippedTools": ["Rifle"]}],
            "loadoutSnapshots": [{"equippedTools": ["Rifle"], "backpackTools": ["Knife"], "hudWeaponIndicators": [{"path": "HUD.Weapon", "text": "Rifle"}]}],
            "matchStateSamples": [{"signals": {"HUD.Score": "2-1", "HUD.Timer": "05:12"}}],
            "transitions": [{"path": "HUD.Score", "before": "1-1", "after": "2-1"}],
            "timelineEvents": [{"category": "camera-sample"}],
            "errors": [],
            "progressLogs": [],
        },
        "collectionLimitations": ["Client-visible observations only"],
        "errors": [],
    }


class TargetedCaptureMilestoneTests(unittest.TestCase):
    def test_run_milestone3_generates_required_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            cap_plan = root / "capability-plan.json"
            dynamic_obs = root / "dynamic-observation.json"
            targeted_obs = root / "targeted-session.json"
            m2_dir = root / "m2"
            out = root / "m3"
            m2_dir.mkdir(parents=True, exist_ok=True)

            cap_plan.write_text(json.dumps(capability_plan_fixture()), encoding="utf-8")
            dynamic_obs.write_text(json.dumps(dynamic_observation_fixture()), encoding="utf-8")
            targeted_obs.write_text(json.dumps(targeted_evidence_fixture()), encoding="utf-8")

            (m2_dir / "targeted-inspection-plan.json").write_text(json.dumps({
                "requests": [
                    {"requestId": "character-entity-observation", "missingEvidence": ["player_entity_set"]},
                    {"requestId": "combat-camera-weapon-correlation", "missingEvidence": ["camera_state_samples"]},
                    {"requestId": "match-objective-state-observation", "missingEvidence": ["objective_hud_signals"]},
                    {"requestId": "loadout-runtime-observation", "missingEvidence": ["hud_weapon_indicators"]},
                ]
            }), encoding="utf-8")
            (m2_dir / "reassessed-feature-feasibility.json").write_text(json.dumps({
                "summary": {
                    "stageCounts": {"Evidence partially available": 4},
                    "gameplayImplementationReadyCapabilities": []
                }
            }), encoding="utf-8")

            result = MODULE.run_milestone3(MODULE.MilestoneInputs(
                capability_plan_path=cap_plan,
                milestone2_dir=m2_dir,
                output_dir=out,
                dynamic_observation=dynamic_obs,
                targeted_evidence=targeted_obs,
            ))

            self.assertIsInstance(result, dict)
            expected = [
                "targeted-capture-architecture.json",
                "targeted-inspection-requests.json",
                "targeted-evidence-schema.json",
                "capture-validation-report.json",
                "movement-overlay-validation.json",
                "capability-readiness-update.json",
                "runtime-test-instructions.md",
                "milestone-3-summary.md",
            ]
            for name in expected:
                self.assertTrue((out / name).is_file(), name)

            capture = json.loads((out / "capture-validation-report.json").read_text(encoding="utf-8"))
            self.assertEqual(capture["schemaVersion"], "122.capture-validation-report.1")
            self.assertTrue(capture["identityChecks"]["placeIdMatches"])
            self.assertTrue(capture["identityChecks"]["baselineScanIdMatches"])

            overlay = json.loads((out / "movement-overlay-validation.json").read_text(encoding="utf-8"))
            stage5 = next(item for item in overlay["stages"] if item["stage"] == 5)
            self.assertEqual(stage5["status"], "passed")


if __name__ == "__main__":
    unittest.main()
