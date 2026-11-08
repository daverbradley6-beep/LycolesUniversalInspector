import importlib.util
import json
import pathlib
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_MANIFEST = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"
SOURCE = ROOT / "tools" / "lycoles_generation_service.py"
SPEC = importlib.util.spec_from_file_location("lycoles_generation_service", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_parts(directory, event=None, request=None, scan_id="service_scan_001"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
    scan_stats = {"recorded": 2, "complete": True}
    one = dict(
        scan,
        partIndex=1,
        scanStats=scan_stats,
        featureEvidence={"pets": {}},
        featureRequest=request,
        objects=[
            {
                "path": "Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
                "class": "ProximityPrompt",
                "scanOrdinal": 1,
                "interaction": {
                    "actionText": "Hatch",
                    "objectText": "Rainbow Egg",
                    "holdDuration": 0,
                    "maxActivationDistance": 10,
                },
            }
        ],
    )
    interaction = event or {
        "featureCandidate": "pets",
        "path": "Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt",
        "controlType": "ProximityPrompt.Triggered",
        "evidenceLevel": "temporal-state-change-observed",
        "outcomeVerified": False,
        "stateChanges": [{"key": "leaderstats.🥚 Hatches", "before": 285, "after": 286}],
    }
    two = dict(
        scan,
        partIndex=2,
        objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 2}],
        interactionHistoryChunk=[interaction],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")



def make_workflow_ready_parts(directory, request="Complete observed shop flow", scan_id="workflow_ready_scan"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
    scan_stats = {"recorded": 2, "complete": True}
    shared_control = {
        "visible": True,
        "active": True,
        "selectable": True,
        "autoButtonColor": True,
        "interactable": True,
        "ancestorVisible": True,
        "screenEnabled": True,
        "withinScrollingBounds": True,
        "effectiveVisible": True,
    }
    one = dict(
        scan,
        partIndex=1,
        scanStats=scan_stats,
        featureEvidence={"shops": {}},
        featureRequest=request,
        objects=[{
            "path": "PlayerGui.HUD.Shop.Select",
            "class": "TextButton",
            "scanOrdinal": 1,
            "guiControl": dict({"text": "Select"}, **shared_control),
        }],
    )

    event_one = {
        "featureCandidate": "shops",
        "path": "PlayerGui.HUD.Shop.Select",
        "pathIdentity": [
            {"name": "PlayerGui", "className": "PlayerGui", "ordinal": 1},
            {"name": "HUD", "className": "ScreenGui", "ordinal": 1},
            {"name": "Shop", "className": "Frame", "ordinal": 1},
            {"name": "Select", "className": "TextButton", "ordinal": 1},
        ],
        "controlType": "GuiButton.Activated",
        "transactionId": "shop-flow",
        "sequence": 1,
        "controlMetadata": dict({"controlClass": "TextButton", "text": "Select"}, **shared_control),
        "stateChanges": [{
            "key": "Data.ShopStage",
            "before": 2,
            "after": 3,
            "stateIdentityStatus": "component-resolved",
            "stateIdentity": [
                {"name": "Data", "className": "Folder", "ordinal": 1},
                {"name": "ShopStage", "className": "IntValue", "ordinal": 1},
            ],
        }],
    }
    event_two = {
        "featureCandidate": "shops",
        "path": "PlayerGui.HUD.Shop.Confirm",
        "pathIdentity": [
            {"name": "PlayerGui", "className": "PlayerGui", "ordinal": 1},
            {"name": "HUD", "className": "ScreenGui", "ordinal": 1},
            {"name": "Shop", "className": "Frame", "ordinal": 1},
            {"name": "Confirm", "className": "TextButton", "ordinal": 1},
        ],
        "controlType": "GuiButton.Activated",
        "transactionId": "shop-flow",
        "sequence": 2,
        "controlMetadata": dict({"controlClass": "TextButton", "text": "Confirm"}, **shared_control),
        "stateChanges": [{
            "key": "Data.ShopStage",
            "before": 3,
            "after": 4,
            "stateIdentityStatus": "component-resolved",
            "stateIdentity": [
                {"name": "Data", "className": "Folder", "ordinal": 1},
                {"name": "ShopStage", "className": "IntValue", "ordinal": 1},
            ],
        }],
    }

    two = dict(
        scan,
        partIndex=2,
        objects=[{
            "path": "PlayerGui.HUD.Shop.Confirm",
            "class": "TextButton",
            "scanOrdinal": 2,
            "guiControl": dict({"text": "Confirm"}, **shared_control),
        }],
        interactionHistoryChunk=[event_one, event_two],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")




def make_live_observation_export(path, scan_id="live-observation-service-1"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": "service_scan_001",
        "baselineScanId": "service_scan_001",
        "integrity": {
            "scanComplete": True,
            "placeId": 3623096087,
            "scanId": scan_id,
            "baselineScanId": "service_scan_001",
            "parts": 2,
            "interactionEvents": 7,
        },
        "sourceDiagnostics": {
            "scanMode": "dynamic-observations",
            "requiresFullObjectRescan": False,
            "baselineScanId": "service_scan_001",
        },
        "sourceProvenance": {
            "schemaVersion": "30.2.source-provenance.1",
            "inputMode": "local-multipart",
            "scanId": scan_id,
            "placeId": 3623096087,
            "partCount": 2,
            "receiverStoredPayloadDigestsVerified": False,
            "receiverStoredPayloadDigestsRevalidatedThisRun": False,
            "receiverAcknowledgementDigestEquivalent": False,
            "receiverIntegrityVerified": False,
            "resumeCheckpointAuthenticated": False,
            "receiverResponseAuthenticityVerified": False,
            "localPayloadEquivalent": False,
            "sourceAuthenticityVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "replayable": False,
            "gameplayVerified": False,
            "actionOutcomesVerified": False,
        },
        "features": [
            {
                "feature": "combat",
                "interactionEvents": 7,
                "observedEvents": 7,
                "verifiedClientOutcomes": 0,
                "clientCorroboratedEvents": 2,
                "temporalTransitionEvents": 2,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

class LycolesGenerationServiceTests(unittest.TestCase):
    def test_manifest_only_job_is_blocked_but_structured(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = MODULE.LycolesGenerationService(output_root=pathlib.Path(tmp) / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="manifest",
                evidence_path=FIXTURE_MANIFEST,
                requested_capability="Auto hatch eggs",
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["generationStatus"], "blocked")
            self.assertEqual(result["analysis"]["mode"], "manifest-only")
            self.assertIn("full_multipart_report_unavailable", result["analysis"]["explicitBlockers"])
            self.assertIsNone(result["delivery"]["generatedResultPath"])
            self.assertFalse(result["claims"]["runtimeVerified"])

    def test_parts_job_generates_display_only_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            self.assertIn(
                result["generationStatus"],
                ("generated", "generated-with-blockers", "observational-only-request-unmet"),
            )
            generated_result_path = pathlib.Path(result["delivery"]["generatedResultPath"])
            self.assertTrue(generated_result_path.is_file())

            generated = json.loads(generated_result_path.read_text(encoding="utf-8"))
            self.assertEqual(generated["schemaVersion"], "113.generated-result.1")
            self.assertEqual(generated["placeId"], 3623096087)
            self.assertFalse(generated["runtimeVerified"])
            self.assertFalse(generated["gameplayVerified"])
            self.assertFalse(generated["executionAuthorized"])

            readiness_path = pathlib.Path(result["evidence"]["generationReadinessPath"])
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            self.assertEqual(readiness["request"]["request"],
                             "Automatically hatch the selected egg")
            self.assertNotEqual(readiness["request"]["status"], "no-capability-requested")
            self.assertGreater(len(readiness["requestFeatureReadiness"]["requestedTerms"]), 0)

    def test_parts_job_exposes_complexity_aware_model_routing_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            result = service.run_sync(request)
            provider = result["provider"]
            self.assertIn(provider["complexityClass"], ("low", "standard", "hard"))
            self.assertIsInstance(provider["analysisModelOrder"], list)
            self.assertIsInstance(provider["generationModelOrder"], list)
            self.assertIsInstance(provider["repairModelOrder"], list)
            self.assertIn("expectedCostScores", provider)
            usage = result["usage"]
            self.assertIn("attempts", usage["analysis"])
            self.assertIn("retries", usage["analysis"])
            self.assertIn("attempts", usage["generation"])
            self.assertIn("retries", usage["repair"])

    def test_workflow_ready_parts_generate_executable_script_with_gui_wiring(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_workflow_ready_parts(parts)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Complete observed shop flow",
            )
            result = service.run_sync(request)
            self.assertEqual(result["status"], "succeeded")
            self.assertIn(result["generationStatus"], ("generated", "generated-with-blockers"))

            delivery = result["delivery"]
            self.assertEqual(delivery["generatedScriptKind"], "combined-utility")
            generated_script_path = pathlib.Path(delivery["generatedScriptPath"])
            self.assertTrue(generated_script_path.is_file())
            workflow = delivery["executableWorkflow"]
            self.assertTrue(workflow["guidedWorkflowScriptGenerated"])
            self.assertGreaterEqual(workflow["executionReadyWorkflowCandidates"], 1)
            self.assertGreaterEqual(workflow["requestAlignedExecutionReadyWorkflowCandidates"], 1)
            self.assertTrue(workflow["requestAlignedExecutableWorkflowAvailable"])

            source = generated_script_path.read_text(encoding="utf-8")
            self.assertIn("StartGuidedWorkflow", source)
            self.assertIn("StopGuidedWorkflow", source)
            self.assertIn("startButton.Activated:Connect(function() task.spawn(runWorkflow) end)", source)
            self.assertIn("stopButton.Activated:Connect(function()", source)

    def test_require_executable_blocks_observational_only_requested_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically shoot and reload")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically shoot and reload",
                require_executable=True,
            )
            with self.assertRaisesRegex(ValueError, "Executable workflow required but unavailable"):
                service.run_sync(request)

    def test_hard_request_prioritizes_reasoning_generation_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automate combat recoil weapon tracking")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automate combat recoil weapon tracking",
            )
            result = service.run_sync(request)
            provider = result["provider"]
            self.assertEqual(provider["complexityClass"], "hard")
            self.assertEqual(provider["generationModelOrder"][0], provider["reasoningModel"])

    def test_parts_job_accepts_live_observation_overlay_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track combat observations")
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Track combat observations",
                observation_paths=(overlay,),
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            release_manifest_path = pathlib.Path(result["evidence"]["releaseManifestPath"])
            release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(release_manifest["evidenceOverlayProvenance"]["overlayCount"], 1)
            overlay_provenance_path = pathlib.Path(result["outputDir"]) / "evidence-overlay-provenance.json"
            overlay_provenance = json.loads(overlay_provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(overlay_provenance["overlays"][0]["scanId"], "live-observation-service-1")
            self.assertFalse(release_manifest["runtimeVerified"])

    def test_async_submission_exposes_job_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            job_id = service.submit(request)

            snapshot = None
            deadline = time.time() + 15
            while time.time() < deadline:
                snapshot = service.get_job(job_id)
                if snapshot and snapshot["status"] in ("succeeded", "failed"):
                    break
                time.sleep(0.05)

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["status"], "succeeded")
            self.assertIsInstance(snapshot["result"], dict)
            self.assertEqual(snapshot["result"]["jobId"], job_id)


if __name__ == "__main__":
    unittest.main()
