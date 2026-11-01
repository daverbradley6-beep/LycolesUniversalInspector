"""End-to-end v108 system-plan and runtime-comparison artifact tests."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from feature_planner_v107 import plan
from integrated_pipeline_v108 import ARTIFACTS, generate, verify
from path_identity_v107 import build
from release_pipeline_v104 import build as build_v104, canonical

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


def source_fixture(reverse=False):
    observations = [
        observation(
            ["PlayerGui", "HUD", "Buy"],
            ["PlayerGui", "ScreenGui", "TextButton"],
            "TextButton",
        ),
        observation(
            ["PlayerGui", "HUD", "Status"],
            ["PlayerGui", "ScreenGui", "TextLabel"],
            "TextLabel",
        ),
        observation(
            ["Workspace", "Stats", "Coins"],
            ["Workspace", "Folder", "IntValue"],
            "IntValue",
        ),
    ]
    if reverse:
        observations.reverse()
    return {"placeId": PLACE, "observations": observations}


def relationship_evidence(feature_plan):
    return {
        "schemaVersion": "108.relationship-evidence.1",
        "placeId": PLACE,
        "sourceFeaturePlanSha256": hashlib.sha256(canonical(feature_plan)).hexdigest(),
        "relationships": [{
            "kind": "interaction_followed_by_state_change",
            "sourceFeatureId": "observe_0000",
            "targetFeatureId": "observe_0002",
            "observations": 4,
            "independentCaptures": 2,
            "attributionStatus": "unambiguous",
            "overlappingCandidates": 0,
            "evidenceArtifact": "relationship-capture.json",
            "evidenceDigest": "b" * 64,
        }],
        "runtimeVerified": False,
        "causalityProven": False,
        "gameplayVerified": False,
    }


def runtime_observation(feature_plan, *, failure=False):
    features = [
        {"featureId": "observe_0000", "status": "resolved", "value": "Buy"},
        {"featureId": "observe_0001", "status": "resolved", "value": "Ready"},
        {
            "featureId": "observe_0002",
            "status": "property_unavailable" if failure else "resolved",
            "value": "property unavailable" if failure else 42,
        },
    ]
    return {
        "schemaVersion": "108.runtime-observation.1",
        "placeId": PLACE,
        "sourceFeaturePlanSha256": hashlib.sha256(canonical(feature_plan)).hexdigest(),
        "environment": {
            "kind": "permitted_client_observation",
            "captureId": "capture-0001",
            "sourceArtifact": "permitted-runtime-capture.json",
            "sourceDigest": "c" * 64,
        },
        "features": features,
        "unsupportedApiUsages": [],
        "observationComplete": True,
        "readOnly": True,
        "sourceAuthenticityVerified": False,
        "runtimeVerified": False,
        "liveGameVerified": False,
        "serverAuthorityVerified": False,
        "gameplayVerified": False,
    }


class IntegratedPipelineV108Tests(unittest.TestCase):
    def setUp(self):
        self.report = build(source_fixture(), PLACE)
        self.feature_plan = plan(self.report)

    def test_generation_without_runtime_observation_is_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate(source_fixture(), PLACE, directory)
            self.assertTrue(result["ok"], result)
            self.assertEqual(result["features"], 3)
            self.assertEqual(result["systems"], 3)
            self.assertFalse(result["observationSupplied"])
            self.assertFalse(result["comparisonComplete"])
            self.assertIsNone(result["comparisonPassed"])
            self.assertFalse(result["driftDetected"])
            root = Path(directory)
            self.assertEqual(
                {path.name for path in root.iterdir()},
                set((*ARTIFACTS, "manifest.json")),
            )
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(manifest["schemaVersion"], "108.integrated-manifest.1")
            self.assertFalse(manifest["runtimeObservationSupplied"])
            self.assertFalse(manifest["runtimeVerified"])
            comparison = json.loads((root / "runtime-comparison.json").read_text())
            self.assertEqual(comparison["summary"]["notObservedFeatures"], 3)
            verification = json.loads((root / "feature-verification.json").read_text())
            self.assertTrue(all(
                item["runtimeOutcome"] == "not_observed"
                and item["staticArtifactsVerified"]
                and not item["runtimeVerified"]
                for item in verification["features"]
            ))
            unsupported = json.loads((root / "unsupported-report.json").read_text())
            self.assertTrue(unsupported["reportingComplete"])
            self.assertIn("automatic_gameplay_action", unsupported["systemCapabilities"])

    def test_runtime_observation_and_relationships_integrate_deterministically(self):
        relationships = relationship_evidence(self.feature_plan)
        observed = runtime_observation(self.feature_plan)
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            result = generate(
                source_fixture(), PLACE, first,
                relationship_evidence=relationships,
                runtime_observation=observed,
            )
            generate(
                source_fixture(reverse=True), PLACE, second,
                relationship_evidence=copy.deepcopy(relationships),
                runtime_observation=copy.deepcopy(observed),
            )
            self.assertTrue(result["observationSupplied"])
            self.assertTrue(result["comparisonComplete"])
            self.assertTrue(result["comparisonPassed"])
            self.assertFalse(result["driftDetected"])
            self.assertEqual(result["systems"], 2)
            for name in (*ARTIFACTS, "relationship-evidence.json", "runtime-observation.json", "manifest.json"):
                self.assertEqual(
                    (Path(first) / name).read_bytes(),
                    (Path(second) / name).read_bytes(),
                    name,
                )
            system_plan = json.loads((Path(first) / "system-plan.json").read_text())
            linked = next(item for item in system_plan["systems"] if len(item["featureIds"]) == 2)
            self.assertEqual(linked["type"], "interaction_state_candidate")
            self.assertEqual(linked["runtimeOutcome"], "matched")
            self.assertFalse(linked["systemVerified"])

    def test_v104_and_canonical_v107_inputs_remain_supported(self):
        legacy_source = {"placeId": PLACE, "objects": [{
            "path": ["PlayerGui", "HUD", "Status"],
            "className": "TextLabel",
        }]}
        legacy_report = build_v104(legacy_source, PLACE)
        canonical_report = build(source_fixture(), PLACE)
        for source, expected_legacy in (
            (legacy_report, 1),
            (canonical_report, 0),
        ):
            with self.subTest(schema=source["schemaVersion"]), tempfile.TemporaryDirectory() as directory:
                result = generate(source, PLACE, directory)
                self.assertTrue(result["ok"], result)
                plan_artifact = json.loads(
                    (Path(directory) / "feature-plan.json").read_text()
                )
                self.assertEqual(
                    sum(
                        feature["pathResolution"] == "legacy_terminal_identity"
                        for feature in plan_artifact["features"]
                    ),
                    expected_legacy,
                )
                self.assertTrue(verify(directory)["ok"])

    def test_runtime_drift_flows_into_feature_and_system_verification(self):
        observed = runtime_observation(self.feature_plan, failure=True)
        with tempfile.TemporaryDirectory() as directory:
            result = generate(
                self.report, PLACE, directory, runtime_observation=observed
            )
            self.assertTrue(result["driftDetected"])
            self.assertFalse(result["comparisonPassed"])
            verification = json.loads(
                (Path(directory) / "feature-verification.json").read_text()
            )
            by_id = {item["featureId"]: item for item in verification["features"]}
            self.assertEqual(by_id["observe_0002"]["runtimeOutcome"], "drifted")
            self.assertEqual(
                by_id["observe_0002"]["failedRuntimeChecks"],
                ["property_read_succeeds"],
            )
            self.assertFalse(by_id["observe_0002"]["runtimeVerified"])

    def test_every_derived_v108_artifact_tamper_is_detected(self):
        names = (
            "system-interpretation.json", "system-plan.json",
            "runtime-check-plan.json", "runtime-comparison.json",
            "feature-verification.json", "unsupported-report.json",
        )
        for name in names:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                generate(source_fixture(), PLACE, directory)
                path = Path(directory) / name
                value = json.loads(path.read_text())
                value["tampered"] = True
                path.write_text(json.dumps(value))
                self.assertFalse(verify(directory)["ok"])

    def test_extra_missing_and_source_artifact_tampering_are_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(source_fixture(), PLACE, directory)
            extra = Path(directory) / "extra.json"
            extra.write_text("{}")
            self.assertFalse(verify(directory)["ok"])
            extra.unlink()
            (Path(directory) / "system-plan.json").unlink()
            self.assertFalse(verify(directory)["ok"])
        with tempfile.TemporaryDirectory() as directory:
            relationships = relationship_evidence(self.feature_plan)
            observed = runtime_observation(self.feature_plan)
            generate(
                source_fixture(), PLACE, directory,
                relationship_evidence=relationships,
                runtime_observation=observed,
            )
            path = Path(directory) / "runtime-observation.json"
            value = json.loads(path.read_text())
            value["features"][0]["value"] = "tampered"
            path.write_bytes(canonical(value))
            self.assertFalse(verify(directory)["ok"])

    def test_runtime_observation_must_match_generated_feature_plan(self):
        observed = runtime_observation(self.feature_plan)
        observed["sourceFeaturePlanSha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "plan digest"):
                generate(
                    source_fixture(), PLACE, directory,
                    runtime_observation=observed,
                )

    def test_manifest_comparison_pass_tampering_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            generate(source_fixture(), PLACE, directory)
            path = Path(directory) / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["comparisonPassed"] = True
            path.write_bytes(canonical(manifest))
            self.assertFalse(verify(directory)["ok"])

    def test_generation_rejects_nonempty_and_symlink_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "output"
            root.mkdir()
            (root / "existing").write_text("keep")
            with self.assertRaisesRegex(ValueError, "output"):
                generate(source_fixture(), PLACE, root)
            self.assertEqual((root / "existing").read_text(), "keep")
            link = Path(directory) / "link"
            link.symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "output"):
                generate(source_fixture(), PLACE, link)

    def test_cli_generates_and_verifies_optional_evidence_bundle(self):
        relationships = relationship_evidence(self.feature_plan)
        observed = runtime_observation(self.feature_plan)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            relation_path = root / "relationships.json"
            observation_path = root / "runtime.json"
            output = root / "output"
            source.write_bytes(canonical(source_fixture()))
            relation_path.write_bytes(canonical(relationships))
            observation_path.write_bytes(canonical(observed))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "integrated_pipeline_v108.py"),
                    "--source", str(source),
                    "--place-id", str(PLACE),
                    "--relationship-evidence", str(relation_path),
                    "--runtime-observation", str(observation_path),
                    "--output", str(output),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads(completed.stdout)
            self.assertTrue(summary["ok"])
            self.assertTrue(summary["observationSupplied"])
            self.assertTrue(summary["comparisonComplete"])
            self.assertTrue(summary["comparisonPassed"])
            self.assertFalse(summary["runtimeVerified"])
            self.assertTrue(verify(output)["ok"])

    def test_cli_exits_nonzero_for_complete_drift_after_writing_bundle(self):
        observed = runtime_observation(self.feature_plan, failure=True)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            observation_path = root / "runtime.json"
            output = root / "output"
            source.write_bytes(canonical(source_fixture()))
            observation_path.write_bytes(canonical(observed))
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "integrated_pipeline_v108.py"),
                    "--source", str(source),
                    "--place-id", str(PLACE),
                    "--runtime-observation", str(observation_path),
                    "--output", str(output),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 1, completed.stderr)
            summary = json.loads(completed.stdout)
            self.assertTrue(summary["ok"])
            self.assertTrue(summary["comparisonComplete"])
            self.assertFalse(summary["comparisonPassed"])
            self.assertTrue(summary["driftDetected"])
            self.assertFalse(summary["runtimeVerified"])
            self.assertTrue(verify(output)["ok"])


if __name__ == "__main__":
    unittest.main()
