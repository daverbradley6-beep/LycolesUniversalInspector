"""Versioned public Roblox API compatibility tests for v107 generation."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from feature_planner_v106 import SUPPORTED
from feature_planner_v107 import plan
from integrated_pipeline_v107 import emit_luau, generate, verify
from path_identity_v107 import build
from roblox_api_contract_v107 import (
    assess_compatibility,
    load_snapshot,
    validate_emitted_source_members,
    validate_snapshot,
)

PLACE = 85896571713843
SNAPSHOT = ROOT / "api-definitions" / "roblox-api-version-d0e8cfcd943d4ae2-v107.json"
SOURCE_SHA256 = "02276f872886a6bc29e2e05a2e551a8c92c0e1745276520f4203d52a15679856"


def fixture():
    return {"placeId": PLACE, "observations": [{
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Coins", "className": "IntValue", "ordinal": 1},
        ],
        "className": "IntValue",
    }]}


class RobloxApiContractV107Tests(unittest.TestCase):
    def setUp(self):
        self.snapshot = load_snapshot(SNAPSHOT)
        self.feature_plan = plan(build(fixture(), PLACE))

    def test_snapshot_has_official_version_and_full_dump_digest(self):
        self.assertIs(validate_snapshot(self.snapshot), self.snapshot)
        source = self.snapshot["source"]
        self.assertEqual(source["channel"], "QTStudio")
        self.assertEqual(source["version"], "version-d0e8cfcd943d4ae2")
        self.assertEqual(source["sha256"], SOURCE_SHA256)
        self.assertEqual(source["url"], f"https://setup.rbxcdn.com/{source['version']}-API-Dump.json")

    def test_runtime_and_supported_feature_apis_are_compatible(self):
        result = assess_compatibility(self.snapshot, self.feature_plan)
        self.assertTrue(result["compatible"])
        self.assertEqual(result["issues"], [])
        self.assertFalse(result["runtimeVerified"])
        self.assertIn("Instance.new", result["globalAssumptions"])
        self.assertIn("RBXScriptSignal.Connect", result["globalAssumptions"])
        covered = {(item["targetClass"], item["member"]) for item in result["featureRequirements"]}
        self.assertEqual(covered, set(SUPPORTED.items()))

    def test_emitted_source_members_are_fully_accounted(self):
        source = emit_luau(self.feature_plan)
        result = validate_emitted_source_members(source)
        self.assertIn("GetService", result["members"])
        self.assertIn("Connect", result["globalMembers"])

    def test_unaccounted_emitted_member_is_rejected(self):
        source = emit_luau(self.feature_plan).replace(
            "local Players =", "game:UnaccountedApi()\nlocal Players =", 1,
        )
        with self.assertRaises(ValueError):
            validate_emitted_source_members(source)

    def test_snapshot_records_inherited_member_owners(self):
        records = {(item["targetClass"], item["member"]): item for item in self.snapshot["members"]}
        self.assertEqual(records[("ScreenGui", "Name")]["ownerClass"], "Instance")
        self.assertEqual(records[("TextButton", "Size")]["ownerClass"], "GuiObject")
        self.assertEqual(records[("DataModel", "GetService")]["ownerClass"], "ServiceProvider")

    def test_missing_api_member_fails_compatibility(self):
        broken = copy.deepcopy(self.snapshot)
        broken["members"] = [
            item for item in broken["members"]
            if (item["targetClass"], item["member"]) != ("IntValue", "Value")
        ]
        result = assess_compatibility(broken, self.feature_plan)
        self.assertFalse(result["compatible"])
        self.assertIn("missing:feature:read:IntValue.Value", result["issues"])

    def test_inaccessible_property_fails_compatibility(self):
        broken = copy.deepcopy(self.snapshot)
        target = next(item for item in broken["members"] if item["targetClass"] == "IntValue" and item["member"] == "Value")
        target["readSecurity"] = "RobloxScriptSecurity"
        result = assess_compatibility(broken, self.feature_plan)
        self.assertFalse(result["compatible"])
        self.assertIn("inaccessible:feature:read:IntValue.Value", result["issues"])

    def test_malformed_source_digest_is_rejected(self):
        broken = copy.deepcopy(self.snapshot)
        broken["source"]["sha256"] = "bad"
        with self.assertRaises(ValueError):
            validate_snapshot(broken)

    def test_integrated_pipeline_emits_api_compatibility_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = generate(fixture(), PLACE, tmp)
            self.assertTrue(result["ok"])
            artifact = json.loads((Path(tmp) / "api-compatibility.json").read_text())
            self.assertTrue(artifact["compatible"])
            self.assertEqual(artifact["snapshotVersion"], self.snapshot["source"]["version"])
            self.assertIn("GetService", artifact["emittedSourceMembers"]["members"])

    def test_integrated_verifier_rejects_api_artifact_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "api-compatibility.json"
            artifact = json.loads(path.read_text())
            artifact["compatible"] = False
            path.write_text(json.dumps(artifact, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertFalse(verify(tmp)["ok"])


if __name__ == "__main__":
    unittest.main()
