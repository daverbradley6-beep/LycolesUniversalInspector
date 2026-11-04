import copy
import importlib.util
import json
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"
TRANSPORT_FIXTURE = ROOT / "tests" / "fixtures" / "report_transport_v301_cases.json"
SOURCE = ROOT / "tools" / "manifest_readiness_v109.py"
SPEC = importlib.util.spec_from_file_location("manifest_readiness_v109", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def transport_snapshot(case, expected_parts):
    transport = copy.deepcopy(case["reportTransport"])
    acknowledged = transport["acknowledgedParts"]
    if acknowledged == "ALL":
        acknowledged = expected_parts
    elif acknowledged == "ALL_BUT_ONE":
        acknowledged = expected_parts - 1
    elif acknowledged == "PARTIAL":
        acknowledged = max(1, expected_parts // 2)
    transport["acknowledgedParts"] = acknowledged
    transport["expectedParts"] = expected_parts
    return transport


class ManifestReadinessTests(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(FIXTURE.read_text(encoding="utf-8"))
        matrix = json.loads(TRANSPORT_FIXTURE.read_text(encoding="utf-8"))
        self.transport_scan_id = matrix["scanId"]
        self.transport_cases = matrix["cases"]

    def test_real_manifest_explains_evidence_and_generation_blockers(self):
        result = MODULE.analyze(self.manifest)
        self.assertEqual(result["schemaVersion"], "109.manifest-readiness.2")
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
        self.assertIsNone(result["scanId"])
        self.assertFalse(result["transport"]["receiverIntegrityLookupAvailable"])
        self.assertIn(
            "full_multipart_report_unavailable",
            result["generationReadiness"]["blockers"],
        )
        self.assertIn(
            "receiver_scan_id_unavailable",
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
        self.assertTrue(transport["reportGenerated"])
        self.assertEqual(transport["manifestSnapshotPhase"], "legacy-unspecified")
        self.assertEqual(transport["uploadAttemptStatus"], "unknown-legacy")
        self.assertEqual(transport["receiverReportStatus"], "unknown-legacy")
        self.assertEqual(transport["downstreamAvailabilityStatus"], "not-validated")
        self.assertFalse(transport["receiverIntegrityVerified"])
        self.assertFalse(transport["downstreamReportAvailable"])

    def test_missing_local_export_has_actionable_recovery(self):
        result = MODULE.analyze(self.manifest)
        export = result["transport"]["localExport"]
        self.assertFalse(export["attempted"])
        self.assertEqual(export["status"], "not-attempted")
        self.assertFalse(export["completeNumberedPartsClaimed"])
        self.assertEqual(result["generationReadiness"]["recommendedRecovery"],
                         "save_numbered_parts_or_upload")

    def test_complete_local_export_is_recoverable_but_not_manifest_only_ready(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["localExport"] = {
            "attempted": True, "status": "complete",
            "exportedParts": manifest["expectedParts"],
            "expectedParts": manifest["expectedParts"],
            "filenamePrefix": "Lycoles_85896571713843_scan-123",
            "manifestSaved": True, "manifestWriteAttempts": 2,
            "localPartContentDigestsComputed": False,
        }
        result = MODULE.analyze(manifest)
        export = result["transport"]["localExport"]
        self.assertTrue(export["completeNumberedPartsClaimed"])
        self.assertTrue(export["manifestSaved"])
        self.assertEqual(result["generationReadiness"]["recommendedRecovery"],
                         "provide_complete_local_numbered_parts")
        self.assertFalse(result["generationReadiness"]["scriptGenerationReady"])
        self.assertIn("full_multipart_report_unavailable",
                      result["generationReadiness"]["blockers"])

    def test_local_export_part_accounting_mismatch_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["localExport"] = {
            "attempted": True, "status": "complete",
            "exportedParts": manifest["expectedParts"],
            "expectedParts": manifest["expectedParts"] + 1,
            "filenamePrefix": "Lycoles_scan",
            "manifestSaved": True, "manifestWriteAttempts": 2,
            "localPartContentDigestsComputed": False,
        }
        with self.assertRaisesRegex(ValueError, "local export part accounting"):
            MODULE.analyze(manifest)

    def test_explicit_transport_status_is_preserved(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["reportTransport"] = {
            "reportGenerated": True,
            "manifestSnapshotPhase": "post-upload",
            "uploadAttempted": True,
            "uploadAttemptStatus": "attempted",
            "uploadStatus": "acknowledged",
            "receiverReportStatus": "acknowledged-awaiting-integrity",
            "downstreamAvailabilityStatus": "not-validated",
            "acknowledgedParts": manifest["expectedParts"],
            "expectedParts": manifest["expectedParts"],
            "lastError": None,
            "receiverIntegrityVerified": False,
            "downstreamReportAvailable": False,
        }
        result = MODULE.analyze(manifest)
        self.assertTrue(result["transport"]["uploadAttempted"])
        self.assertEqual(result["transport"]["uploadStatus"], "acknowledged")
        self.assertEqual(result["transport"]["uploadAttemptStatus"],"attempted")
        self.assertEqual(result["transport"]["receiverReportStatus"],
                         "acknowledged-awaiting-integrity")
        self.assertEqual(result["transport"]["downstreamAvailabilityStatus"],
                         "not-validated")

        self.assertFalse(result["transport"]["uploadFailed"])
        self.assertFalse(result["transport"]["downstreamReportAvailable"])
    def test_configuration_block_after_complete_ack_preserves_receiver_progress(self):
        manifest=copy.deepcopy(self.manifest);expected=manifest["expectedParts"]
        manifest["reportTransport"]={"reportGenerated":True,
            "manifestSnapshotPhase":"upload-blocked","uploadAttempted":True,
            "uploadAttemptStatus":"attempted-previously-currently-blocked",
            "uploadStatus":"configuration-error",
            "receiverReportStatus":"acknowledged-awaiting-integrity",
            "downstreamAvailabilityStatus":"not-validated",
            "acknowledgedParts":expected,"expectedParts":expected,
            "lastError":"invalid receiver endpoint","receiverIntegrityVerified":False,
            "downstreamReportAvailable":False}
        result=MODULE.analyze(manifest);transport=result["transport"]
        self.assertEqual(transport["receiverReportStatus"],
                         "acknowledged-awaiting-integrity")
        self.assertTrue(transport["lifecycleStages"]["uploadAcknowledged"])
        self.assertEqual(result["generationReadiness"]["recommendedRecovery"],
                         "verify_receiver_integrity_or_save_numbered_parts")

    def test_inconsistent_explicit_lifecycle_stage_is_rejected(self):
        manifest=copy.deepcopy(self.manifest);expected=manifest["expectedParts"]
        manifest["reportTransport"]={"reportGenerated":True,
            "manifestSnapshotPhase":"pre-upload","uploadAttempted":False,
            "uploadAttemptStatus":"attempted","uploadStatus":"not-attempted",
            "receiverReportStatus":"unavailable",
            "downstreamAvailabilityStatus":"not-validated",
            "acknowledgedParts":0,"expectedParts":expected,"lastError":None,
            "receiverIntegrityVerified":False,"downstreamReportAvailable":False}
        with self.assertRaisesRegex(ValueError,"inconsistent uploadAttemptStatus"):
            MODULE.analyze(manifest)



    def test_v301_transport_lifecycle_matrix(self):
        for case in self.transport_cases:
            with self.subTest(case=case["name"]):
                manifest = copy.deepcopy(self.manifest)
                manifest["scanId"] = self.transport_scan_id
                manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
                result = MODULE.analyze(manifest)
                transport = result["transport"]
                expected = case["reportTransport"]
                self.assertEqual(result["scanId"], self.transport_scan_id)
                self.assertEqual(transport["uploadStatus"], expected["uploadStatus"])
                self.assertIs(transport["reportGenerated"], expected["reportGenerated"])
                self.assertEqual(transport["manifestSnapshotPhase"], expected["manifestSnapshotPhase"])
                self.assertIs(transport["uploadAttempted"], expected["uploadAttempted"])
                self.assertIs(transport["uploadFailed"], case["expectedUploadFailed"])
                self.assertFalse(transport["receiverIntegrityVerified"])
                self.assertFalse(transport["downstreamReportAvailable"])
                self.assertTrue(transport["receiverIntegrityLookupAvailable"])
                expected_stages=MODULE._transport_stage_labels(
                    transport["uploadStatus"],transport["uploadAttempted"],
                    transport["acknowledgedParts"],transport["expectedParts"],False,False)
                self.assertEqual((transport["uploadAttemptStatus"],
                    transport["receiverReportStatus"],transport["downstreamAvailabilityStatus"]),
                    expected_stages)

                self.assertEqual(
                    transport["receiverIntegrityPath"],
                    f"/reports/READ_KEY/{self.transport_scan_id}/integrity",
                )
                stages = transport["lifecycleStages"]
                self.assertTrue(stages["scanComplete"])
                self.assertTrue(stages["reportGenerated"])
                self.assertFalse(stages["localExportAttempted"])
                self.assertIs(stages["uploadAttempted"], expected["uploadAttempted"])
                self.assertIs(stages["uploadAcknowledged"],
                              expected["uploadStatus"] == "acknowledged")
                self.assertFalse(stages["receiverIntegrityVerified"])
                self.assertFalse(stages["downstreamReportAvailable"])

    def test_v302_acknowledgement_digest_coverage_is_diagnostic_only(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["scanId"] = self.transport_scan_id
        case = next(item for item in self.transport_cases
                    if item["name"] == "post-acknowledgement")
        manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
        manifest["reportTransport"]["acknowledgedPartDigests"] = [
            {"partIndex": index, "sha256": f"{index:064x}"}
            for index in range(1, manifest["expectedParts"] + 1)
        ]
        manifest["reportTransport"]["acknowledgedDigestParts"] = manifest["expectedParts"]
        result = MODULE.analyze(manifest)
        self.assertEqual(result["transport"]["acknowledgedDigestParts"],
                         manifest["expectedParts"])
        self.assertTrue(result["transport"]["acknowledgementDigestCoverageComplete"])
        self.assertFalse(result["generationReadiness"]["scriptGenerationReady"])

    def test_duplicate_acknowledgement_digest_index_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        case = next(item for item in self.transport_cases
                    if item["name"] == "post-acknowledgement")
        manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
        manifest["reportTransport"]["acknowledgedPartDigests"] = [
            {"partIndex": 1, "sha256": "1" * 64},
            {"partIndex": 1, "sha256": "2" * 64},
        ]
        manifest["reportTransport"]["acknowledgedDigestParts"] = 2
        with self.assertRaisesRegex(ValueError, "duplicate acknowledged digest"):
            MODULE.analyze(manifest)

    def test_invalid_receiver_scan_id_is_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["scanId"] = "bad/id"
        with self.assertRaisesRegex(ValueError, "receiver scan ID"):
            MODULE.analyze(manifest)

    def test_transport_rejects_generation_contradiction(self):
        manifest = copy.deepcopy(self.manifest)
        case = next(item for item in self.transport_cases
                    if item["name"] == "post-acknowledgement")
        manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
        manifest["reportTransport"]["reportGenerated"] = False
        with self.assertRaisesRegex(ValueError, "report generation status"):
            MODULE.analyze(manifest)

    def test_transport_rejects_invalid_snapshot_phase(self):
        manifest = copy.deepcopy(self.manifest)
        case = next(item for item in self.transport_cases if item["name"] == "pre-upload")
        manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
        manifest["reportTransport"]["manifestSnapshotPhase"] = {"invalid": True}
        with self.assertRaisesRegex(ValueError, "snapshot phase"):
            MODULE.analyze(manifest)

    def test_transport_rejects_phase_status_contradiction(self):
        manifest = copy.deepcopy(self.manifest)
        case = next(item for item in self.transport_cases
                    if item["name"] == "post-acknowledgement")
        manifest["reportTransport"] = transport_snapshot(case, manifest["expectedParts"])
        manifest["reportTransport"]["manifestSnapshotPhase"] = "pre-upload"
        with self.assertRaisesRegex(ValueError, "phase is inconsistent"):
            MODULE.analyze(manifest)

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
