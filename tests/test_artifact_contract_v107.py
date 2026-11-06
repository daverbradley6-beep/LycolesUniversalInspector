"""Semantic source and strict artifact-contract tests for v107 generation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from artifact_contract_v107 import parse_feature_table, validate_source_semantics
from feature_planner_v107 import plan
from integrated_pipeline_v107 import emit_luau, generate, verify
from path_identity_v107 import build

PLACE = 85896571713843


def row(ordinal=1):
    return {
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Coins", "className": "IntValue", "ordinal": ordinal},
        ],
        "className": "IntValue",
    }


def fixture():
    return {"placeId": PLACE, "observations": [row(2), row(1)]}


class ArtifactContractV107Tests(unittest.TestCase):
    def feature_plan_and_source(self):
        feature_plan = plan(build(fixture(), PLACE))
        return feature_plan, emit_luau(feature_plan)

    def test_semantic_parser_extracts_runtime_feature_table(self):
        feature_plan, source = self.feature_plan_and_source()
        parsed = parse_feature_table(source)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["pathIdentity"][-1]["ordinal"], 1)
        self.assertTrue(validate_source_semantics(source, feature_plan)["ok"])

    def test_semantics_reject_identity_ordinal_tamper(self):
        feature_plan, source = self.feature_plan_and_source()
        broken = source.replace("ordinal=1}", "ordinal=9}", 1)
        result = validate_source_semantics(broken, feature_plan)
        self.assertFalse(result["ok"])
        self.assertIn("feature_table_mismatch", result["issues"])

    def test_semantics_reject_property_tamper(self):
        feature_plan, source = self.feature_plan_and_source()
        broken = source.replace('property="Value"', 'property="Text"', 1)
        self.assertFalse(validate_source_semantics(broken, feature_plan)["ok"])

    def test_semantics_reject_place_guard_tamper(self):
        feature_plan, source = self.feature_plan_and_source()
        broken = source.replace(str(PLACE), str(PLACE + 1), 1)
        result = validate_source_semantics(broken, feature_plan)
        self.assertFalse(result["ok"])
        self.assertIn("place_guard_mismatch", result["issues"])

    def test_semantics_reject_duplicate_runtime_feature(self):
        feature_plan, source = self.feature_plan_and_source()
        entry = next(line for line in source.splitlines() if line.startswith("  {id="))
        broken = source.replace("}\nlocal status", entry + "\n}\nlocal status", 1)
        self.assertFalse(validate_source_semantics(broken, feature_plan)["ok"])

    def test_semantics_reject_unknown_feature_table_line(self):
        feature_plan, source = self.feature_plan_and_source()
        broken = source.replace("}\nlocal status", "   {id=\"hidden\"}\n}\nlocal status", 1)
        self.assertFalse(validate_source_semantics(broken, feature_plan)["ok"])

    def test_semantic_parser_supports_legacy_nil_identity(self):
        report = build({"placeId": PLACE, "objects": [
            {"path": ["Workspace", "Stats", "Coins"], "className": "IntValue"},
        ]}, PLACE)
        feature_plan = plan(report)
        parsed = parse_feature_table(emit_luau(feature_plan))
        self.assertIsNone(parsed[0]["pathIdentity"])

    def test_verify_rejects_unexpected_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            (Path(tmp) / "unexpected.txt").write_text("unexpected")
            self.assertFalse(verify(tmp)["ok"])

    def test_verify_rejects_extra_manifest_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["unverifiedClaim"] = True
            path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertFalse(verify(tmp)["ok"])

    def test_verify_rejects_malformed_manifest_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "manifest.json"
            manifest = json.loads(path.read_text())
            name = next(iter(manifest["files"]))
            manifest["files"][name] = "not-a-sha256"
            path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertFalse(verify(tmp)["ok"])


if __name__ == "__main__":
    unittest.main()
