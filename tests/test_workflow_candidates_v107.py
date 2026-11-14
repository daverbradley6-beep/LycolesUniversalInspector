import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))

from release_pipeline_v104 import build
from workflow_candidates_v107 import build as build_workflows, validate

PLACE = 85896571713843


def report_fixture():
    source = {
        "placeId": PLACE,
        "objects": [
            {"path": ["PlayerGui", "HUD", "Coins"], "className": "TextLabel"},
            {"path": ["Workspace", "Chest", "Prompt"], "className": "ProximityPrompt"},
        ],
        "observedInteractionHistory": [
            {
                "sequence": 10,
                "path": "PlayerGui.HUD.ShopButton",
                "transactionId": "txn-1",
                "featureCandidate": "shop",
                "actionCandidate": "open_shop",
                "stateChanges": [{"key": "Data.Bubbles", "before": 10, "after": 8}],
            },
            {
                "sequence": 11,
                "path": "PlayerGui.HUD.BuyButton",
                "transactionId": "txn-1",
                "featureCandidate": "shop",
                "actionCandidate": "buy_item",
                "stateChanges": [{"key": "Data.Inventory", "before": 2, "after": 3}],
            },
            {
                "sequence": 12,
                "path": "PlayerGui.HUD.CloseButton",
                "transactionId": "txn-2",
                "featureCandidate": "shop",
            },
            {"path": "PlayerGui.HUD.Bad", "sequence": 13, "transactionId": "txn-3", "stateChanges": ["bad"]},
            "invalid",
        ],
    }
    return build(source, PLACE)


class WorkflowCandidatesTests(unittest.TestCase):
    def test_build_and_validate(self):
        report = report_fixture()
        self.assertEqual(report["observedInteractionRejectedCount"], 1)
        document = build_workflows(report)
        validate(document)
        self.assertEqual(document["schemaVersion"], "107.workflow-candidates.1")
        self.assertEqual(document["summary"]["workflowCandidates"], 1)
        self.assertEqual(document["summary"]["completedCandidates"], 1)
        self.assertEqual(document["summary"]["reviewOnlyCandidates"], 0)
        self.assertEqual(document["summary"]["singletonTransactions"], 2)
        self.assertEqual(document["summary"]["rejectedEvents"], 0)
        candidate = document["workflowCandidates"][0]
        self.assertEqual(candidate["stepCount"], 2)
        self.assertEqual(candidate["observedStateChanges"], 2)
        self.assertTrue(candidate["completedCandidate"])

    def test_deterministic(self):
        self.assertEqual(build_workflows(report_fixture()), build_workflows(report_fixture()))

    def test_invalid_schema_rejected(self):
        document = build_workflows(report_fixture())
        document["summary"]["completedCandidates"] = 99
        with self.assertRaises(ValueError):
            validate(document)

    def test_invalid_report_rejected(self):
        with self.assertRaises(ValueError):
            build_workflows({"schemaVersion": "104.release", "placeId": True, "observedInteractionHistory": []})


if __name__ == "__main__":
    unittest.main()
