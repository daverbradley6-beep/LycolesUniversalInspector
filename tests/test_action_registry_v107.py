import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from action_registry_v107 import build_registry
from feature_planner_v107 import plan
from path_identity_v107 import build

PLACE = 85896571713843


def segment(name, class_name, ordinal=1):
    return {"name": name, "className": class_name, "ordinal": ordinal}


def feature_plan():
    source = {
        "placeId": PLACE,
        "observations": [
            {
                "path": ["PlayerGui", "HUD", "Coins"],
                "pathIdentity": [
                    segment("PlayerGui", "PlayerGui"),
                    segment("HUD", "Frame"),
                    segment("Coins", "TextLabel"),
                ],
                "className": "TextLabel",
            },
            {
                "path": ["Workspace", "Stats", "Wins"],
                "pathIdentity": [
                    segment("Workspace", "Workspace"),
                    segment("Stats", "Folder"),
                    segment("Wins", "IntValue"),
                ],
                "className": "IntValue",
            },
        ],
    }
    return plan(build(source, PLACE))


class TestActionRegistryV107(unittest.TestCase):
    def test_no_runtime_evidence(self):
        data = build_registry(feature_plan())
        self.assertEqual(data["summary"]["totalActions"], 2)
        self.assertEqual(data["summary"]["runtimeObservedActions"], 0)
        self.assertEqual(data["summary"]["workflowCorrelatedActions"], 0)
        self.assertEqual(data["summary"]["completedWorkflowCandidates"], 0)
        self.assertEqual(data["actions"][0]["runtimeStatus"], "not_runtime_verified")
        self.assertEqual(data["actions"][0]["runtimeEvidence"]["completedWorkflowHits"], 0)

    def test_completed_workflow_candidate(self):
        features = feature_plan()["features"]
        evidence = {
            "schemaVersion": "107.runtime-evidence",
            "placeId": PLACE,
            "records": [
                {"featureId": features[0]["id"], "status": "success", "timestamp": 10, "workflowId": "wf_rebirth", "stepIndex": 1, "stepCount": 2, "observedValue": "10"},
                {"featureId": features[1]["id"], "status": "success", "timestamp": 11, "workflowId": "wf_rebirth", "stepIndex": 2, "stepCount": 2, "observedValue": "11"},
                {"featureId": features[0]["id"], "status": "success", "timestamp": 12, "observedValue": "12"},
            ],
        }
        data = build_registry(feature_plan(), evidence)
        self.assertEqual(data["summary"]["completedWorkflowCandidates"], 1)
        self.assertEqual(data["summary"]["runtimeObservedActions"], 1)
        self.assertEqual(data["summary"]["workflowCorrelatedActions"], 2)
        self.assertEqual(data["actions"][0]["runtimeStatus"], "runtime_observed")
        self.assertEqual(data["actions"][0]["generationReadiness"], "high")
        self.assertEqual(data["actions"][0]["runtimeEvidence"]["completedWorkflowHits"], 1)
        self.assertEqual(data["actions"][1]["runtimeStatus"], "runtime_partially_observed")
        self.assertEqual(data["actions"][1]["generationReadiness"], "high")
        self.assertEqual(data["actions"][1]["runtimeEvidence"]["completedWorkflowHits"], 1)

    def test_unknown_feature_evidence_rejected(self):
        evidence = {
            "schemaVersion": "107.runtime-evidence",
            "placeId": PLACE,
            "records": [{"featureId": "missing_feature", "status": "success"}],
        }
        with self.assertRaisesRegex(ValueError, "unknown feature"):
            build_registry(feature_plan(), evidence)

    def test_runtime_evidence_place_mismatch_rejected(self):
        evidence = {"schemaVersion": "107.runtime-evidence", "placeId": 1, "records": []}
        with self.assertRaisesRegex(ValueError, "place mismatch"):
            build_registry(feature_plan(), evidence)

    def test_invalid_step_span_rejected(self):
        feature_id = feature_plan()["features"][0]["id"]
        evidence = {
            "schemaVersion": "107.runtime-evidence",
            "placeId": PLACE,
            "records": [{"featureId": feature_id, "status": "success", "workflowId": "wf", "stepIndex": 3, "stepCount": 2}],
        }
        with self.assertRaisesRegex(ValueError, "step index exceeds"):
            build_registry(feature_plan(), evidence)


if __name__ == "__main__":
    unittest.main()
