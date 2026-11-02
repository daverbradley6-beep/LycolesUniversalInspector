import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"
SOURCE = ROOT / "tools" / "manifest_readiness_v109.py"
SPEC = importlib.util.spec_from_file_location("manifest_readiness_v109", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ManifestReadinessTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_real_manifest_explains_evidence_and_generation_blockers(self):
        result = MODULE.analyze(self.manifest)
        self.assertEqual(result["schemaVersion"], "109.manifest-readiness.1")
        self.assertEqual(result["placeId"], 85896571713843)
        self.assertTrue(result["scan"]["complete"])
        self.assertTrue(result["scan"]["objectAccountingValid"])
        self.assertEqual(result["evidence"]["interactions"], 153)
        self.assertEqual(result["evidence"]["attributedInteractions"], 89)
        self.assertEqual(result["evidence"]["stateTransitions"], 10)
        self.assertEqual(result["evidence"]["guiTransitions"], 88)
        self.assertEqual(result["evidence"]["completedWorkflowCandidates"], 0)
        self.assertTrue(result["evidence"]["historyIsSubset"])
        self.assertEqual(result["evidence"]["featureConsistentOutcomeCandidatesLowerBound"], 3)
        self.assertEqual(
            {item["feature"] for item in result["outcomeCandidates"]},
            {"pets", "rewards"},
        )
        self.assertFalse(result["generationReadiness"]["scriptGenerationReady"])
        self.assertFalse(result["generationReadiness"]["v108SourceCompatible"])
        self.assertIn(
            "full_multipart_report_unavailable",
            result["generationReadiness"]["blockers"],
        )
        self.assertFalse(result["claims"]["causalityProven"])
        self.assertFalse(result["claims"]["gameplayVerified"])

    def test_legacy_uploaded_parts_zero_is_unknown_not_failure(self):
        result = MODULE.analyze(self.manifest)
        transport = result["transport"]
        self.assertIsNone(transport["uploadAttempted"])
        self.assertEqual(transport["uploadStatus"], "unknown_legacy_manifest_snapshot")
        self.assertIsNone(transport["acknowledgedParts"])
        self.assertFalse(transport["uploadFailed"])
        self.assertFalse(transport["receiverIntegrityVerified"])
        self.assertFalse(transport["downstreamReportAvailable"])

    def test_explicit_transport_status_is_preserved(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["reportTransport"] = {
            "reportGenerated": True,
            "manifestSnapshotPhase": "post-upload",
            "uploadAttempted": True,
            "uploadStatus": "acknowledged",
            "acknowledgedParts": manifest["expectedParts"],
            "expectedParts": manifest["expectedParts"],
            "lastError": None,
            "receiverIntegrityVerified": False,
            "downstreamReportAvailable": False,
        }
        result = MODULE.analyze(manifest)
        self.assertTrue(result["transport"]["uploadAttempted"])
        self.assertEqual(result["transport"]["uploadStatus"], "acknowledged")
        self.assertFalse(result["transport"]["uploadFailed"])
        self.assertFalse(result["transport"]["downstreamReportAvailable"])

    def test_invalid_object_accounting_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["diagnostics"]["recordedObjects"] += 1
        with self.assertRaisesRegex(ValueError, "object accounting"):
            MODULE.analyze(manifest)

    def test_acknowledged_transport_requires_every_part(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["reportTransport"] = {
            "reportGenerated": True,
            "manifestSnapshotPhase": "post-upload",
            "uploadAttempted": True,
            "uploadStatus": "acknowledged",
            "acknowledgedParts": manifest["expectedParts"] - 1,
            "expectedParts": manifest["expectedParts"],
            "lastError": None,
            "receiverIntegrityVerified": False,
            "downstreamReportAvailable": False,
        }
        with self.assertRaisesRegex(ValueError, "acknowledged transport"):
            MODULE.analyze(manifest)

    def test_emit_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = pathlib.Path(directory) / "first.json"
            second = pathlib.Path(directory) / "second.json"
            a = MODULE.emit(self.manifest, first)
            b = MODULE.emit(self.manifest, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertEqual(a["sha256"], b["sha256"])
            self.assertFalse(a["scriptGenerationReady"])


if __name__ == "__main__":
    unittest.main()
