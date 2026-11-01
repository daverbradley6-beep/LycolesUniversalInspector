"""Evidence provenance and implementation-contract tests for v107 feature plans."""
import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from feature_planner_v107 import (
    LEGACY_PLAN_SCHEMA_VERSION,
    migrate_feature_plan_v1,
    plan,
    validate_feature_plan,
)
from feature_quality_v107 import assess
from inspection_diagnostics_v107 import analyze
from integrated_pipeline_v107 import emit_luau, generate, verify
from path_identity_v107 import build
from release_pipeline_v104 import canonical

PLACE = 85896571713843


def fixture():
    return {"placeId": PLACE, "observations": [{
        "path": ["Workspace", "Stats", "Coins"],
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Stats", "className": "Folder", "ordinal": 1},
            {"name": "Coins", "className": "IntValue", "ordinal": 2},
        ],
        "className": "IntValue",
    }]}


def legacy_plan(feature_plan):
    value = copy.deepcopy(feature_plan)
    value["schemaVersion"] = LEGACY_PLAN_SCHEMA_VERSION
    for feature in value["features"]:
        for field in (
            "evidence", "implementationStrategy", "runtimeChecks",
            "successCondition", "failureConditions", "unknowns",
        ):
            feature.pop(field)
    return value


class FeatureProvenanceV107Tests(unittest.TestCase):
    def setUp(self):
        self.report = build(fixture(), PLACE)
        self.feature_plan = plan(self.report)
        self.feature = self.feature_plan["features"][0]

    def test_feature_links_to_canonical_observation_digest(self):
        evidence = self.feature["evidence"]
        self.assertEqual(evidence["classification"], "observed_client_object")
        self.assertEqual(evidence["sourceArtifact"], "inspection-report.json")
        self.assertEqual(evidence["sourceObjectIndex"], 0)
        self.assertEqual(
            evidence["sourceDigest"],
            hashlib.sha256(canonical(self.report["objects"][0])).hexdigest(),
        )
        self.assertIn("client_visible_object_path", evidence["observedFacts"])
        self.assertIn("supported_class_property_mapping", evidence["inferences"])

    def test_feature_defines_strategy_checks_and_outcomes(self):
        self.assertEqual(self.feature["implementationStrategy"], "resolve_client_identity_then_read_property")
        self.assertIn("place_id_matches", self.feature["runtimeChecks"])
        self.assertIn("each_segment_name_class_ordinal_matches", self.feature["runtimeChecks"])
        self.assertEqual(self.feature["successCondition"], "target_resolved_and_property_read_succeeded")
        self.assertIn("identity_mismatch", self.feature["failureConditions"])
        self.assertIn("property_unavailable", self.feature["failureConditions"])

    def test_feature_explicitly_preserves_unknown_boundaries(self):
        self.assertEqual(self.feature["status"], "implemented_not_runtime_verified")
        self.assertIn("server_authority", self.feature["unknowns"])
        self.assertIn("gameplay_causality", self.feature["unknowns"])
        self.assertIn("runtime_property_value", self.feature["unknowns"])

    def test_provenance_digest_shape_is_strictly_validated(self):
        broken = copy.deepcopy(self.feature_plan)
        broken["features"][0]["evidence"]["sourceDigest"] = "not-a-sha256"
        with self.assertRaises(ValueError):
            validate_feature_plan(broken)

    def test_runtime_checks_are_resolution_specific(self):
        legacy_report = build({"placeId": PLACE, "objects": [{
            "path": ["Workspace", "Stats", "Coins"],
            "className": "IntValue",
        }]}, PLACE)
        feature = plan(legacy_report)["features"][0]
        self.assertIn("each_legacy_name_is_unique", feature["runtimeChecks"])
        self.assertIn("terminal_name_class_is_unique", feature["runtimeChecks"])
        self.assertNotIn("each_segment_name_class_ordinal_matches", feature["runtimeChecks"])

    def test_v1_plan_remains_valid_and_emits_identical_luau(self):
        old = legacy_plan(self.feature_plan)
        self.assertIs(validate_feature_plan(old), old)
        self.assertEqual(emit_luau(old), emit_luau(self.feature_plan))

    def test_v1_plan_migrates_deterministically_with_report_evidence(self):
        old = legacy_plan(self.feature_plan)
        self.assertEqual(migrate_feature_plan_v1(old, self.report), self.feature_plan)

    def test_migration_rejects_plan_not_derived_from_report(self):
        old = legacy_plan(self.feature_plan)
        old["features"][0]["property"] = "Text"
        with self.assertRaises(ValueError):
            migrate_feature_plan_v1(old, self.report)

    def test_integrated_verifier_rejects_provenance_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            generate(fixture(), PLACE, tmp)
            path = Path(tmp) / "feature-plan.json"
            value = json.loads(path.read_text())
            value["features"][0]["evidence"]["sourceObjectIndex"] = 999
            path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertFalse(verify(tmp)["ok"])

    def test_quality_and_diagnostics_account_for_evidence_contracts(self):
        quality = assess(self.report, self.feature_plan)
        diagnostics = analyze(self.report, self.feature_plan)
        for result in (quality, diagnostics):
            self.assertEqual(result["evidenceClassifications"], {"observed_client_object": 1})
            self.assertEqual(result["verificationStatuses"], {"implemented_not_runtime_verified": 1})
            self.assertEqual(result["featuresWithExplicitContracts"], 1)
            self.assertEqual(result["unknownBoundaries"]["server_authority"], 1)
            self.assertEqual(result["unknownBoundaries"]["gameplay_causality"], 1)


if __name__ == "__main__":
    unittest.main()
