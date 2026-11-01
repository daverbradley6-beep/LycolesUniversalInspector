"""Controlled offline hierarchy tests for the v107 resolver model."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from feature_planner_v107 import plan
from path_identity_v107 import build
from resolver_harness_v107 import evaluate

PLACE = 85896571713843


def node(name, class_name, *, properties=None, children=None):
    return {
        "name": name,
        "className": class_name,
        "properties": properties or {},
        "children": children or [],
    }


def fixture(*roots):
    return {"schemaVersion": "107.hierarchy-fixture", "placeId": PLACE, "roots": list(roots)}


def rich_plan(ordinal=2, class_name="IntValue"):
    source = {"placeId": PLACE, "observations": [{
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Coins", "className": class_name, "ordinal": ordinal},
        ],
        "className": class_name,
    }]}
    return plan(build(source, PLACE))


def legacy_plan():
    source = {"placeId": PLACE, "objects": [
        {"path": ["Workspace", "Stats", "Coins"], "className": "IntValue"},
    ]}
    return plan(build(source, PLACE))


def workspace_with_coins(*coins, stats=None):
    stats_node = stats or node("Stats", "Folder", children=list(coins))
    return node("Workspace", "Workspace", children=[stats_node])


class ResolverHarnessV107Tests(unittest.TestCase):
    def test_full_identity_selects_class_qualified_ordinal(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 10}),
            node("Coins", "StringValue", properties={"Value": "ignored"}),
            node("Coins", "IntValue", properties={"Value": 20}),
        ))
        result = evaluate(rich_plan(2), hierarchy, PLACE)
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(result["features"][0]["value"], 20)
        self.assertTrue(result["modelVerified"])
        self.assertTrue(result["readOnly"])
        self.assertEqual(result["source"], "synthetic_hierarchy_fixture")
        self.assertFalse(result["luauExecuted"])
        self.assertFalse(result["robloxRuntimeVerified"])

    def test_full_identity_missing_ordinal_fails_closed(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 10}),
        ))
        result = evaluate(rich_plan(2), hierarchy, PLACE)
        self.assertEqual(result["features"][0]["status"], "identity_mismatch")

    def test_full_identity_class_mismatch_fails_closed(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "NumberValue", properties={"Value": 10}),
        ))
        result = evaluate(rich_plan(1), hierarchy, PLACE)
        self.assertEqual(result["failed"], 1)

    def test_legacy_unique_path_resolves(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 15}),
        ))
        result = evaluate(legacy_plan(), hierarchy, PLACE)
        self.assertEqual(result["features"][0]["status"], "resolved")
        self.assertEqual(result["features"][0]["value"], 15)

    def test_legacy_ambiguous_intermediate_fails_closed(self):
        hierarchy = fixture(node("Workspace", "Workspace", children=[
            node("Stats", "Folder", children=[node("Coins", "IntValue", properties={"Value": 1})]),
            node("Stats", "Configuration", children=[node("Coins", "IntValue", properties={"Value": 2})]),
        ]))
        result = evaluate(legacy_plan(), hierarchy, PLACE)
        self.assertEqual(result["features"][0]["status"], "legacy_ambiguity")

    def test_legacy_ambiguous_terminal_fails_closed(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
            node("Coins", "IntValue", properties={"Value": 2}),
        ))
        result = evaluate(legacy_plan(), hierarchy, PLACE)
        self.assertEqual(result["features"][0]["status"], "legacy_ambiguity")

    def test_missing_property_is_not_resolved(self):
        hierarchy = fixture(workspace_with_coins(node("Coins", "IntValue")))
        result = evaluate(rich_plan(1), hierarchy, PLACE)
        self.assertEqual(result["features"][0]["status"], "property_unavailable")

    def test_place_mismatch_blocks_model_evaluation(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
        ))
        result = evaluate(rich_plan(1), hierarchy, PLACE + 1)
        self.assertEqual(result["features"][0]["status"], "place_mismatch")
        self.assertEqual(result["resolved"], 0)

    def test_duplicate_service_roots_are_rejected(self):
        hierarchy = fixture(
            node("Workspace", "Workspace"),
            node("Workspace", "Workspace"),
        )
        with self.assertRaises(ValueError):
            evaluate(rich_plan(1), hierarchy, PLACE)

    def test_results_are_deterministic(self):
        hierarchy = fixture(workspace_with_coins(
            node("Coins", "IntValue", properties={"Value": 1}),
            node("Coins", "IntValue", properties={"Value": 2}),
        ))
        self.assertEqual(evaluate(rich_plan(2), hierarchy, PLACE), evaluate(rich_plan(2), hierarchy, PLACE))


if __name__ == "__main__":
    unittest.main()
