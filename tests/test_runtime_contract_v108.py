"""Versioned runtime observation and comparison contract tests for v108."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from feature_planner_v107 import plan
from path_identity_v107 import build
from release_pipeline_v104 import canonical
from runtime_contract_v108 import (
    build_check_plan,
    compare_runtime,
    validate_observation,
)
from system_interpreter_v108 import interpret

PLACE = 85896571713843


def observation(path, classes, class_name):
    return {
        "path": path,
        "pathIdentity": [
            {"name": name, "className": segment_class, "ordinal": 1}
            for name, segment_class in zip(path, classes)
        ],
        "className": class_name,
    }


def source_report():
    return build({"placeId": PLACE, "observations": [
        observation(
            ["PlayerGui", "HUD", "Buy"],
            ["PlayerGui", "ScreenGui", "TextButton"],
            "TextButton",
        ),
        observation(
            ["Workspace", "Stats", "Coins"],
            ["Workspace", "Folder", "IntValue"],
            "IntValue",
        ),
    ]}, PLACE)


def runtime_observation(feature_plan, features, *, complete=True, unsupported=None):
    return {
        "schemaVersion": "108.runtime-observation.1",
        "placeId": PLACE,
        "sourceFeaturePlanSha256": hashlib.sha256(canonical(feature_plan)).hexdigest(),
        "environment": {
            "kind": "permitted_client_observation",
            "captureId": "capture-0001",
            "sourceArtifact": "permitted-runtime-capture.json",
            "sourceDigest": "a" * 64,
        },
        "features": features,
        "unsupportedApiUsages": [] if unsupported is None else unsupported,
        "observationComplete": complete,
        "readOnly": True,
        "sourceAuthenticityVerified": False,
        "runtimeVerified": False,
        "liveGameVerified": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }


class RuntimeContractV108Tests(unittest.TestCase):
    def setUp(self):
        self.report = source_report()
        self.feature_plan = plan(self.report)
        self.interpretation = interpret(self.report, self.feature_plan)
        self.check_plan = build_check_plan(
            self.report, self.feature_plan, self.interpretation
        )

    def test_check_plan_is_deterministic_and_links_features_to_systems(self):
        self.assertEqual(self.check_plan["schemaVersion"], "108.runtime-check-plan.1")
        self.assertEqual(
            self.check_plan,
            build_check_plan(
                copy.deepcopy(self.report),
                copy.deepcopy(self.feature_plan),
                copy.deepcopy(self.interpretation),
            ),
        )
        self.assertEqual(
            [check["featureId"] for check in self.check_plan["featureChecks"]],
            ["observe_0000", "observe_0001"],
        )
        for check in self.check_plan["featureChecks"]:
            self.assertEqual(check["expectedStatus"], "resolved")
            self.assertIn("place_id_matches", check["runtimeChecks"])
            self.assertEqual(len(check["systemIds"]), 1)
            self.assertFalse(check["runtimeVerified"])
        self.assertEqual(
            [plan["systemId"] for plan in self.check_plan["systemPlans"]],
            ["system_0000", "system_0001"],
        )
        self.assertIn(
            "automatic_gameplay_action",
            self.check_plan["unsupportedCapabilities"],
        )
        self.assertFalse(self.check_plan["runtimeVerified"])
        self.assertFalse(self.check_plan["gameplayVerified"])
        first = self.check_plan["featureChecks"][0]
        self.assertEqual(first["path"], ["PlayerGui", "HUD", "Buy"])
        self.assertEqual(first["pathIdentity"][-1], {
            "name": "Buy", "className": "TextButton", "ordinal": 1,
        })
        self.assertEqual(first["className"], "TextButton")
        self.assertEqual(first["property"], "Text")
        self.assertEqual(first["expectedValueType"], "string")
        self.assertEqual(first["sourceObjectIndex"], 0)


    def test_no_observation_is_explicit_and_fail_closed(self):
        result = compare_runtime(self.check_plan, None)
        self.assertEqual(result["schemaVersion"], "108.runtime-comparison.1")
        self.assertIsNone(result["sourceRuntimeObservationSha256"])
        self.assertFalse(result["observationSupplied"])
        self.assertFalse(result["observationComplete"])
        self.assertFalse(result["comparisonComplete"])
        self.assertIsNone(result["comparisonPassed"])
        self.assertFalse(result["driftDetected"])
        self.assertEqual(result["summary"], {
            "expectedFeatures": 2,
            "matchedFeatures": 0,
            "driftedFeatures": 0,
            "notObservedFeatures": 2,
            "unsupportedApiUsages": 0,
        })
        self.assertTrue(all(
            feature["outcome"] == "not_observed"
            and feature["observedStatus"] is None
            for feature in result["features"]
        ))
        self.assertFalse(result["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])

    def test_complete_resolved_observation_matches_without_upgrading_claims(self):
        observed = runtime_observation(self.feature_plan, [
            {"featureId": "observe_0000", "status": "resolved", "value": "Buy"},
            {"featureId": "observe_0001", "status": "resolved", "value": 42},
        ])
        self.assertIs(validate_observation(observed, self.feature_plan), observed)
        result = compare_runtime(self.check_plan, observed)
        self.assertTrue(result["observationSupplied"])
        self.assertTrue(result["observationComplete"])
        self.assertTrue(result["comparisonComplete"])
        self.assertTrue(result["comparisonPassed"])
        self.assertFalse(result["driftDetected"])
        self.assertEqual(result["summary"]["matchedFeatures"], 2)
        self.assertTrue(all(
            feature["outcome"] == "matched"
            and feature["diagnosticCode"] is None
            and feature["failedRuntimeChecks"] == []
            for feature in result["features"]
        ))
        self.assertFalse(result["valueComparisonAvailable"])
        for field in (
            "sourceAuthenticityVerified", "runtimeVerified", "liveGameVerified",
            "serverAuthorityVerified", "causalityProven", "gameplayVerified",
        ):
            self.assertFalse(result[field])

    def test_check_plan_tampering_is_rejected_before_comparison(self):
        cases = []
        runtime_checks = copy.deepcopy(self.check_plan)
        runtime_checks["featureChecks"][0]["runtimeChecks"] = ["fabricated_check"]
        cases.append(runtime_checks)
        check_id = copy.deepcopy(self.check_plan)
        check_id["featureChecks"][0]["id"] = "runtime_check_wrong"
        cases.append(check_id)
        identity = copy.deepcopy(self.check_plan)
        identity["featureChecks"][0]["pathIdentity"][-1]["ordinal"] = 2
        cases.append(identity)
        value_type = copy.deepcopy(self.check_plan)
        value_type["featureChecks"][0]["expectedValueType"] = "boolean"
        cases.append(value_type)
        system_link = copy.deepcopy(self.check_plan)
        system_link["systemPlans"][0]["runtimeCheckIds"] = []
        cases.append(system_link)
        unsupported = copy.deepcopy(self.check_plan)
        unsupported["unsupportedObservations"] = [{"index": 0, "reason": "x"}]
        cases.append(unsupported)
        claim = copy.deepcopy(self.check_plan)
        claim["runtimeVerified"] = True
        cases.append(claim)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    compare_runtime(value, None)


    def test_status_drift_maps_to_specific_failed_runtime_checks(self):
        observed = runtime_observation(self.feature_plan, [
            {
                "featureId": "observe_0000",
                "status": "identity_mismatch",
                "value": "missing object or identity mismatch",
            },
            {
                "featureId": "observe_0001",
                "status": "property_unavailable",
                "value": "property unavailable",
            },
        ])
        result = compare_runtime(self.check_plan, observed)
        self.assertTrue(result["comparisonComplete"])
        self.assertFalse(result["comparisonPassed"])
        self.assertTrue(result["driftDetected"])
        by_id = {item["featureId"]: item for item in result["features"]}
        self.assertEqual(by_id["observe_0000"]["diagnosticCode"], "identity_drift")
        self.assertIn(
            "each_segment_name_class_ordinal_matches",
            by_id["observe_0000"]["failedRuntimeChecks"],
        )
        self.assertEqual(
            by_id["observe_0001"]["failedRuntimeChecks"],
            ["property_read_succeeds"],
        )
        self.assertEqual(result["summary"]["driftedFeatures"], 2)

    def test_partial_observation_retains_not_observed_features(self):
        observed = runtime_observation(
            self.feature_plan,
            [{"featureId": "observe_0000", "status": "resolved", "value": "ready"}],
            complete=False,
        )
        result = compare_runtime(self.check_plan, observed)
        self.assertFalse(result["comparisonComplete"])
        self.assertFalse(result["comparisonPassed"])
        self.assertEqual(result["summary"]["matchedFeatures"], 1)
        self.assertEqual(result["summary"]["notObservedFeatures"], 1)
        self.assertFalse(result["driftDetected"])

    def test_resolved_value_type_drift_fails_closed(self):
        observed = runtime_observation(self.feature_plan, [
            {"featureId": "observe_0000", "status": "resolved", "value": True},
            {"featureId": "observe_0001", "status": "resolved", "value": "ready"},
        ])
        result = compare_runtime(self.check_plan, observed)
        self.assertFalse(result["comparisonPassed"])
        self.assertTrue(result["driftDetected"])
        first = result["features"][0]
        self.assertEqual(first["expectedValueType"], "string")
        self.assertEqual(first["observedValueType"], "boolean")
        self.assertEqual(first["outcome"], "drifted")
        self.assertEqual(first["diagnosticCode"], "value_type_drift")
        self.assertEqual(first["failedRuntimeChecks"], [])

    def test_supplied_empty_plan_observation_cannot_pass_vacuously(self):
        report = build({"placeId": PLACE, "observations": []}, PLACE)
        feature_plan = plan(report)
        interpretation = interpret(report, feature_plan)
        check_plan = build_check_plan(report, feature_plan, interpretation)
        observed = runtime_observation(feature_plan, [])
        result = compare_runtime(check_plan, observed)
        self.assertFalse(result["comparisonComplete"])
        self.assertFalse(result["comparisonPassed"])
        self.assertTrue(result["driftDetected"])
        self.assertEqual(result["globalDiagnostics"], [{
            "code": "empty_runtime_check_plan",
            "count": 0,
            "classification": "runtime_contract_failure",
        }])

    def test_unsupported_api_usage_is_reported_as_global_drift(self):
        observed = runtime_observation(
            self.feature_plan,
            [
                {"featureId": "observe_0000", "status": "resolved", "value": "Buy"},
                {"featureId": "observe_0001", "status": "resolved", "value": 42},
            ],
            unsupported=["DataModel.GetService:HttpService"],
        )
        result = compare_runtime(self.check_plan, observed)
        self.assertTrue(result["comparisonComplete"])
        self.assertFalse(result["comparisonPassed"])
        self.assertTrue(result["driftDetected"])
        self.assertEqual(
            result["globalDiagnostics"],
            [{
                "code": "unsupported_api_usage",
                "count": 1,
                "classification": "runtime_contract_failure",
            }],
        )

    def test_observation_rejects_unknown_duplicate_missing_and_tampered_sources(self):
        valid = runtime_observation(self.feature_plan, [
            {"featureId": "observe_0000", "status": "resolved", "value": "Buy"},
            {"featureId": "observe_0001", "status": "resolved", "value": 42},
        ])
        cases = []
        unknown = copy.deepcopy(valid)
        unknown["features"][0]["featureId"] = "observe_9999"
        cases.append(unknown)
        duplicate = copy.deepcopy(valid)
        duplicate["features"][1]["featureId"] = "observe_0000"
        cases.append(duplicate)
        missing = copy.deepcopy(valid)
        missing["features"].pop()
        cases.append(missing)
        digest = copy.deepcopy(valid)
        digest["sourceFeaturePlanSha256"] = "0" * 64
        cases.append(digest)
        place = copy.deepcopy(valid)
        place["placeId"] = PLACE + 1
        cases.append(place)
        claim = copy.deepcopy(valid)
        claim["runtimeVerified"] = True
        cases.append(claim)
        extra = copy.deepcopy(valid)
        extra["unexpected"] = True
        cases.append(extra)
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_observation(value, self.feature_plan)

    def test_observation_rejects_noncanonical_order_and_unbounded_values(self):
        reversed_features = runtime_observation(self.feature_plan, [
            {"featureId": "observe_0001", "status": "resolved", "value": 42},
            {"featureId": "observe_0000", "status": "resolved", "value": "Buy"},
        ])
        with self.assertRaisesRegex(ValueError, "order"):
            validate_observation(reversed_features, self.feature_plan)
        oversized = runtime_observation(self.feature_plan, [
            {"featureId": "observe_0000", "status": "resolved", "value": "x" * 10001},
            {"featureId": "observe_0001", "status": "resolved", "value": 42},
        ])
        with self.assertRaisesRegex(ValueError, "value"):
            validate_observation(oversized, self.feature_plan)


if __name__ == "__main__":
    unittest.main()
