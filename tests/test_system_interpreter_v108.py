"""Evidence-bounded gameplay-system interpretation tests for v108."""
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
from path_identity_v107 import build
from release_pipeline_v104 import canonical
from system_interpreter_v108 import interpret, validate_interpretation

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


def report():
    return build({"placeId": PLACE, "observations": [
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
    ]}, PLACE)


def relationship_evidence(feature_plan):
    relationships = [
        {
            "kind": "interaction_followed_by_state_change",
            "sourceFeatureId": "observe_0000",
            "targetFeatureId": "observe_0002",
            "observations": 6,
            "independentCaptures": 2,
            "attributionStatus": "unambiguous",
            "overlappingCandidates": 0,
            "evidenceArtifact": "relationship-capture.json",
            "evidenceDigest": "a" * 64,
        },
        {
            "kind": "state_and_feedback_changed_together",
            "sourceFeatureId": "observe_0002",
            "targetFeatureId": "observe_0001",
            "observations": 6,
            "independentCaptures": 2,
            "attributionStatus": "unambiguous",
            "overlappingCandidates": 0,
            "evidenceArtifact": "relationship-capture.json",
            "evidenceDigest": "a" * 64,
        },
    ]
    return {
        "schemaVersion": "108.relationship-evidence.1",
        "placeId": PLACE,
        "sourceFeaturePlanSha256": hashlib.sha256(canonical(feature_plan)).hexdigest(),
        "relationships": relationships,
        "runtimeVerified": False,
        "causalityProven": False,
        "gameplayVerified": False,
    }


class SystemInterpreterV108Tests(unittest.TestCase):
    def setUp(self):
        self.report = report()
        self.feature_plan = plan(self.report)

    def test_structural_interpretation_classifies_roles_without_inventing_links(self):
        result = interpret(self.report, self.feature_plan)
        self.assertEqual(result["schemaVersion"], "108.system-interpretation.1")
        self.assertEqual(len(result["systems"]), 3)
        by_feature = {
            system["featureIds"][0]: system for system in result["systems"]
        }
        self.assertEqual(
            by_feature["observe_0000"]["features"][0]["roles"],
            ["interface", "interaction_affordance"],
        )
        self.assertEqual(
            by_feature["observe_0001"]["features"][0]["roles"],
            ["feedback_surface_candidate", "interface"],
        )
        self.assertEqual(
            by_feature["observe_0002"]["features"][0]["roles"],
            ["observable_state"],
        )
        for system in result["systems"]:
            self.assertEqual(
                system["interpretationClassification"], "deterministic_inference"
            )
            self.assertEqual(
                system["features"][0]["rolesClassification"],
                "deterministic_inference",
            )
            self.assertEqual(
                system["features"][0]["sourceEvidenceClassification"],
                "observed_client_object",
            )
        self.assertTrue(all(
            system["confidence"]["level"] == "structural_only"
            for system in result["systems"]
        ))
        self.assertEqual(result["relationships"], [])
        self.assertEqual(result["summary"]["relationshipCount"], 0)

    def test_reported_repeated_correlations_form_one_system_candidate(self):
        evidence = relationship_evidence(self.feature_plan)
        result = interpret(self.report, self.feature_plan, evidence)
        self.assertEqual(len(result["systems"]), 1)
        system = result["systems"][0]
        self.assertEqual(system["featureIds"], [
            "observe_0000", "observe_0001", "observe_0002",
        ])
        self.assertEqual(system["type"], "interaction_feedback_candidate")
        self.assertEqual(
            system["confidence"]["level"], "reported_repeated_correlation"
        )
        self.assertEqual(system["confidence"]["relationshipCount"], 2)
        self.assertTrue(all(
            relationship["classification"] == "caller_supplied_correlation"
            for relationship in result["relationships"]
        ))
        self.assertIn("gameplay_causality", system["unknowns"])
        self.assertIn("relationship_evidence_authenticity", system["unknowns"])
        self.assertIn("relationship_persistence", system["unknowns"])
        self.assertIn("automatic_gameplay_action", system["unsupportedCapabilities"])
        self.assertEqual(result["summary"]["confidenceLevels"], {
            "reported_repeated_correlation": 1,
        })

    def test_interaction_state_edge_without_feedback_uses_state_candidate_type(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["relationships"] = [evidence["relationships"][0]]
        result = interpret(self.report, self.feature_plan, evidence)
        linked = next(system for system in result["systems"] if len(system["featureIds"]) == 2)
        self.assertEqual(linked["type"], "interaction_state_candidate")
        self.assertNotIn(
            "feedback_surface_candidate",
            {role for feature in linked["features"] for role in feature["roles"]},
        )

    def test_interpretation_never_upgrades_evidence_claims(self):
        result = interpret(
            self.report, self.feature_plan, relationship_evidence(self.feature_plan)
        )
        self.assertTrue(result["readOnly"])
        for field in (
            "runtimeVerified", "liveGameVerified", "causalityProven",
            "serverAuthorityVerified", "gameplayVerified",
        ):
            self.assertFalse(result[field])
        self.assertTrue(all(
            relationship["causalityProven"] is False
            for relationship in result["relationships"]
        ))

    def test_single_capture_relationship_remains_weak_correlation(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["relationships"] = [evidence["relationships"][1]]
        evidence["relationships"][0]["independentCaptures"] = 1
        result = interpret(self.report, self.feature_plan, evidence)
        linked = next(system for system in result["systems"] if len(system["featureIds"]) == 2)
        self.assertEqual(linked["confidence"]["level"], "reported_correlation")
        self.assertIn("insufficient_independent_captures", linked["unknowns"])

    def test_source_plan_and_report_must_match_exactly(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["sourceFeaturePlanSha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "feature plan digest"):
            interpret(self.report, self.feature_plan, evidence)
        broken_plan = copy.deepcopy(self.feature_plan)
        broken_plan["features"][0]["label"] = "Tampered"
        with self.assertRaisesRegex(ValueError, "feature plan mismatch"):
            interpret(self.report, broken_plan)

    def test_relationships_reject_unknown_self_duplicate_and_unsupported_edges(self):
        base = relationship_evidence(self.feature_plan)
        cases = []
        unknown = copy.deepcopy(base)
        unknown["relationships"][1]["targetFeatureId"] = "observe_9999"
        cases.append(unknown)
        self_edge = copy.deepcopy(base)
        self_edge["relationships"][1]["targetFeatureId"] = "observe_0002"
        cases.append(self_edge)
        duplicate = copy.deepcopy(base)
        duplicate["relationships"].append(copy.deepcopy(duplicate["relationships"][-1]))
        cases.append(duplicate)
        unsupported = copy.deepcopy(base)
        unsupported["relationships"][1]["kind"] = "causes_gameplay_reward"
        cases.append(unsupported)
        malformed_kind = copy.deepcopy(base)
        malformed_kind["relationships"][0]["kind"] = []
        cases.append(malformed_kind)
        malformed_feature = copy.deepcopy(base)
        malformed_feature["relationships"][0]["sourceFeatureId"] = {}
        cases.append(malformed_feature)
        for evidence in cases:
            with self.subTest(evidence=evidence["relationships"][-1]):
                with self.assertRaises(ValueError):
                    interpret(self.report, self.feature_plan, evidence)

    def test_relationship_role_semantics_fail_closed(self):
        evidence = relationship_evidence(self.feature_plan)
        relation = evidence["relationships"][0]
        relation["sourceFeatureId"] = "observe_0001"
        with self.assertRaisesRegex(ValueError, "relationship role"):
            interpret(self.report, self.feature_plan, evidence)

    def test_ambiguous_temporal_relationships_are_quarantined(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["relationships"][0]["attributionStatus"] = "ambiguous"
        evidence["relationships"][0]["overlappingCandidates"] = 2
        with self.assertRaisesRegex(ValueError, "ambiguous relationship"):
            interpret(self.report, self.feature_plan, evidence)

    def test_co_visible_relationship_requires_canonical_direction(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["relationships"] = [{
            "kind": "co_visible",
            "sourceFeatureId": "observe_0001",
            "targetFeatureId": "observe_0000",
            "observations": 2,
            "independentCaptures": 1,
            "attributionStatus": "not_temporal",
            "overlappingCandidates": 0,
            "evidenceArtifact": "relationship-capture.json",
            "evidenceDigest": "c" * 64,
        }]
        with self.assertRaisesRegex(ValueError, "co-visible direction"):
            interpret(self.report, self.feature_plan, evidence)
        evidence["relationships"][0]["sourceFeatureId"] = "observe_0000"
        evidence["relationships"][0]["targetFeatureId"] = "observe_0001"
        result = interpret(self.report, self.feature_plan, evidence)
        linked = next(system for system in result["systems"] if len(system["featureIds"]) == 2)
        self.assertEqual(linked["type"], "interface_cluster_candidate")

    def test_noncanonical_relationship_order_is_rejected(self):
        evidence = relationship_evidence(self.feature_plan)
        evidence["relationships"].reverse()
        with self.assertRaisesRegex(ValueError, "relationship order"):
            interpret(self.report, self.feature_plan, evidence)

    def test_relationship_provenance_and_claims_are_strict(self):
        bad_artifact = relationship_evidence(self.feature_plan)
        bad_artifact["relationships"][0]["evidenceArtifact"] = "../secret.json"
        with self.assertRaises(ValueError):
            interpret(self.report, self.feature_plan, bad_artifact)
        bad_digest = relationship_evidence(self.feature_plan)
        bad_digest["relationships"][0]["evidenceDigest"] = "not-a-digest"
        with self.assertRaises(ValueError):
            interpret(self.report, self.feature_plan, bad_digest)
        conflicting_digest = relationship_evidence(self.feature_plan)
        conflicting_digest["relationships"][1]["evidenceDigest"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "artifact digest conflict"):
            interpret(self.report, self.feature_plan, conflicting_digest)
        bad_claim = relationship_evidence(self.feature_plan)
        bad_claim["causalityProven"] = True
        with self.assertRaises(ValueError):
            interpret(self.report, self.feature_plan, bad_claim)
        bad_place = relationship_evidence(self.feature_plan)
        bad_place["placeId"] = True
        with self.assertRaisesRegex(ValueError, "evidence place"):
            interpret(self.report, self.feature_plan, bad_place)

    def test_interpretation_is_deterministic_and_revalidates_exactly(self):
        evidence = relationship_evidence(self.feature_plan)
        first = interpret(self.report, self.feature_plan, evidence)
        second = interpret(
            copy.deepcopy(self.report), copy.deepcopy(self.feature_plan),
            copy.deepcopy(evidence),
        )
        self.assertEqual(first, second)
        self.assertIs(validate_interpretation(
            first, self.report, self.feature_plan, evidence
        ), first)
        tampered = copy.deepcopy(first)
        tampered["systems"][0]["confidence"]["level"] = "causal"
        with self.assertRaisesRegex(ValueError, "interpretation mismatch"):
            validate_interpretation(
                tampered, self.report, self.feature_plan, evidence
            )

    def test_public_cli_writes_canonical_claim_safe_artifact(self):
        evidence = relationship_evidence(self.feature_plan)
        expected = interpret(self.report, self.feature_plan, evidence)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inputs = {
                "report.json": self.report,
                "feature-plan.json": self.feature_plan,
                "relationships.json": evidence,
            }
            for name, value in inputs.items():
                (root / name).write_bytes(canonical(value))
            output = root / "system-interpretation.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "system_interpreter_v108.py"),
                    "--report", str(root / "report.json"),
                    "--feature-plan", str(root / "feature-plan.json"),
                    "--relationship-evidence", str(root / "relationships.json"),
                    "--output", str(output),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(output.read_bytes(), canonical(expected))
            summary = json.loads(completed.stdout)
            self.assertEqual(summary["systems"], 1)
            self.assertEqual(summary["relationships"], 2)
            self.assertFalse(summary["causalityProven"])
            self.assertFalse(summary["gameplayVerified"])

    def test_public_cli_refuses_to_overwrite_source_evidence(self):
        evidence = relationship_evidence(self.feature_plan)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report_path = root / "report.json"
            plan_path = root / "feature-plan.json"
            evidence_path = root / "relationships.json"
            report_path.write_bytes(canonical(self.report))
            plan_path.write_bytes(canonical(self.feature_plan))
            evidence_bytes = canonical(evidence)
            evidence_path.write_bytes(evidence_bytes)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "system_interpreter_v108.py"),
                    "--report", str(report_path),
                    "--feature-plan", str(plan_path),
                    "--relationship-evidence", str(evidence_path),
                    "--output", str(evidence_path),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(evidence_path.read_bytes(), evidence_bytes)
            hard_link = root / "output-hard-link.json"
            os.link(evidence_path, hard_link)
            completed = subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve().parents[1] / "tools" / "system_interpreter_v108.py"),
                    "--report", str(report_path),
                    "--feature-plan", str(plan_path),
                    "--relationship-evidence", str(evidence_path),
                    "--output", str(hard_link),
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(evidence_path.read_bytes(), evidence_bytes)

    def test_empty_plan_produces_bounded_empty_interpretation(self):
        empty_report = build({"placeId": PLACE, "observations": []}, PLACE)
        empty_plan = plan(empty_report)
        result = interpret(empty_report, empty_plan)
        self.assertEqual(result["systems"], [])
        self.assertEqual(result["relationships"], [])
        self.assertEqual(result["summary"]["systemCount"], 0)
        self.assertFalse(result["gameplayVerified"])


if __name__ == "__main__":
    unittest.main()
