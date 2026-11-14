import importlib.util
import json
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE_MANIFEST = ROOT / "tests" / "fixtures" / "bubble_gum_infinity_manifest_v30_sanitized.json"
SOURCE = ROOT / "tools" / "lycoles_generation_service.py"
SPEC = importlib.util.spec_from_file_location("lycoles_generation_service", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


REPLAY_SOURCE = ROOT / "tools" / "evidence_replay_import.py"
REPLAY_SPEC = importlib.util.spec_from_file_location("evidence_replay_import", REPLAY_SOURCE)
REPLAY_MODULE = importlib.util.module_from_spec(REPLAY_SPEC)
REPLAY_SPEC.loader.exec_module(REPLAY_MODULE)


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



def make_automatic_workflow_ready_parts(directory, request="Automatically train and open shop prompt", scan_id="workflow_auto_scan"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
    scan_stats = {"recorded": 3, "complete": True}
    one = dict(
        scan,
        partIndex=1,
        scanStats=scan_stats,
        featureEvidence={"training": {}, "shops": {}},
        featureRequest=request,
        objects=[
            {
                "path": "LocalPlayer.Backpack.Sword",
                "class": "Tool",
                "scanOrdinal": 1,
                "interaction": {
                    "toolTip": "Train",
                    "requiresHandle": True,
                    "canBeDropped": False,
                    "enabled": True,
                    "manualActivationOnly": False,
                },
            },
            {
                "path": "Workspace.Shop.Door.Prompt",
                "class": "ProximityPrompt",
                "scanOrdinal": 2,
                "interaction": {
                    "actionText": "Open",
                    "objectText": "Shop Door",
                    "holdDuration": 0,
                    "maxActivationDistance": 10,
                },
            },
        ],
    )

    tool_step = {
        "featureCandidate": "training",
        "path": "LocalPlayer.Backpack.Sword",
        "pathIdentity": [
            {"name": "LocalPlayer", "className": "Player", "ordinal": 1},
            {"name": "Backpack", "className": "Backpack", "ordinal": 1},
            {"name": "Sword", "className": "Tool", "ordinal": 1},
        ],
        "controlType": "Tool.Activated",
        "transactionId": "auto-shop-training",
        "sequence": 1,
        "controlMetadata": {
            "tooltip": "Train",
            "requiresHandle": True,
            "canBeDropped": False,
            "enabled": True,
            "manualActivationOnly": False,
        },
        "stateChanges": [{
            "key": "Data.TrainingProgress",
            "before": 1,
            "after": 2,
            "stateIdentityStatus": "component-resolved",
            "stateIdentity": [
                {"name": "Data", "className": "Folder", "ordinal": 1},
                {"name": "TrainingProgress", "className": "IntValue", "ordinal": 1},
            ],
        }],
    }
    prompt_step = {
        "featureCandidate": "shops",
        "path": "Workspace.Shop.Door.Prompt",
        "pathIdentity": [
            {"name": "Workspace", "className": "Workspace", "ordinal": 1},
            {"name": "Shop", "className": "Model", "ordinal": 1},
            {"name": "Door", "className": "Part", "ordinal": 1},
            {"name": "Prompt", "className": "ProximityPrompt", "ordinal": 1},
        ],
        "controlType": "ProximityPrompt.Triggered",
        "transactionId": "auto-shop-training",
        "sequence": 2,
        "controlMetadata": {
            "actionText": "Open",
            "objectText": "Shop Door",
            "enabled": True,
            "holdDuration": 0,
            "maxActivationDistance": 10,
            "anchorPath": "Workspace.Shop.Door",
            "anchorPosition": {"x": 1, "y": 2, "z": 3},
        },
        "stateChanges": [{
            "key": "Data.ShopOpened",
            "before": 0,
            "after": 1,
            "stateIdentityStatus": "component-resolved",
            "stateIdentity": [
                {"name": "Data", "className": "Folder", "ordinal": 1},
                {"name": "ShopOpened", "className": "IntValue", "ordinal": 1},
            ],
        }],
    }

    two = dict(
        scan,
        partIndex=2,
        objects=[
            {"path": "Workspace.Shop.Door", "class": "Part", "scanOrdinal": 3},
        ],
        interactionHistoryChunk=[tool_step, prompt_step],
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





def make_targeted_evidence_export(path):
    payload = {
        "schemaVersion": "31.0.targeted-evidence-session.1",
        "exportKind": "targeted-evidence-session",
        "sessionId": "targeted-service-1",
        "placeId": 3623096087,
        "baselineScanId": "service_scan_001",
        "requestIds": [
            "character-entity-observation",
            "combat-camera-weapon-correlation",
            "match-objective-state-observation",
            "loadout-runtime-observation",
        ],
        "requestProgress": {},
        "samples": {
            "characterEntities": [
                {"player": "Local", "isLocalPlayer": True, "team": "Blue"},
                {"player": "Enemy", "isLocalPlayer": False, "team": "Red"},
            ],
            "entityEvents": [{"eventType": "character-present"}],
            "cameraSamples": [{"lookVector": {"x": 0, "y": 0, "z": -1}}],
            "cameraCorrelations": [{"mousePrimaryInputDelta": 2, "lookDeltaMagnitude": 0.13}],
            "inputSamples": [{"mousePrimaryInputs": 4}],
            "weaponSnapshots": [{"equippedTools": ["Rifle"]}],
            "loadoutSnapshots": [{"equippedTools": ["Rifle"], "backpackTools": ["Knife"], "hudWeaponIndicators": [{"path": "HUD.Weapon", "text": "Rifle"}]}],
            "matchStateSamples": [{"signals": {"HUD.Score": "1-0"}}],
            "transitions": [{"path": "HUD.Score", "before": "0-0", "after": "1-0"}],
            "timelineEvents": [{"category": "camera-sample"}],
            "errors": [],
            "progressLogs": [],
        },
        "collectionLimitations": ["Client-visible observations only"],
        "errors": [],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

class CountingProvider(MODULE.BaseLLMProvider):
    def __init__(self):
        self.analysis_calls = 0
        self._info = MODULE.ProviderInfo(provider="counting-test", enabled=True, reason="test counting provider")

    def info(self):
        return self._info

    def analyze(self, bundle, model):
        self.analysis_calls += 1
        return {
            "provider": "counting-test",
            "model": model,
            "summary": {
                "mode": bundle.mode,
                "placeId": bundle.place_id,
                "scanId": bundle.scan_id,
            },
            "recommendedFeatures": [],
            "explicitBlockers": [],
            "analysisFallbackErrors": [],
        }, {
            "tokens": 256,
            "costGbp": 0.00256,
            "attempts": 1,
            "retriesUsed": 0,
        }

    def generate(self, _bundle, _analysis, model):
        return None, {
            "tokens": 64,
            "costGbp": 0.00064,
            "attempts": 1,
            "retriesUsed": 0,
            "model": model,
        }

    def repair(self, code, _analysis, model):
        return code, {
            "tokens": 48,
            "costGbp": 0.00048,
            "attempts": 1,
            "retriesUsed": 0,
            "model": model,
        }


def make_split_live_observation_parts(part_one, part_two, scan_id="live-observation-split-1"):
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
            "interactionEvents": 0,
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
        "features": [],
        "targetedCaptureSession": {
            "schemaVersion": "31.0.targeted-evidence-session.1",
            "requestProgress": {
                "loadout-runtime-observation": {
                    "status": "satisfied",
                    "missingEvidence": [],
                }
            },
            "samples": {
                "loadoutSnapshots": [
                    {
                        "equippedTools": ["Rifle"],
                        "backpackTools": ["Knife"],
                        "hudWeaponIndicatorPaths": ["LocalPlayer.PlayerGui.HUD.WeaponLabel"],
                        "hudWeaponIndicators": ["Rifle"],
                    }
                ],
                "weaponSnapshots": [{"equippedTools": ["Rifle"], "hasCombatTool": True}],
                "inputSamples": [{"mousePrimaryInputs": 3}],
            },
        },
    }
    serialized = json.dumps(payload, ensure_ascii=False)
    midpoint = len(serialized) // 2
    part_one.write_text(serialized[:midpoint], encoding="utf-8")
    part_two.write_text(serialized[midpoint:], encoding="utf-8")


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

    def test_manifest_assisted_workflow_uses_source_manifest_for_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            source_manifest = root / "raw-manifest.json"
            source_manifest.write_text(FIXTURE_MANIFEST.read_text(encoding="utf-8"), encoding="utf-8")
            assisted = root / "manifest-assisted-workflow.json"
            assisted.write_text(
                json.dumps(
                    {
                        "schemaVersion": "30.6.manifest-assisted-workflow.5",
                        "sourceManifest": source_manifest.name,
                        "placeId": 85896571713843,
                        "scriptGenerationReady": False,
                        "targets": [],
                    }
                ),
                encoding="utf-8",
            )

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="manifest",
                evidence_path=assisted,
                requested_capability="Automatically hatch eggs",
            )
            result = service.run_sync(request)
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["analysis"]["mode"], "manifest-only")
            self.assertEqual(result["generationStatus"], "blocked")

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

    def test_require_executable_blocks_manual_guided_subset_for_automatic_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_workflow_ready_parts(parts, request="Automatically complete observed shop flow")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically complete observed shop flow",
                require_executable=True,
            )
            with self.assertRaisesRegex(ValueError, "Executable workflow required but unavailable"):
                service.run_sync(request)

    def test_automatic_workflow_parts_satisfy_require_executable_without_manual_activation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_automatic_workflow_ready_parts(parts)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically train and open shop prompt",
                require_executable=True,
            )
            result = service.run_sync(request)
            self.assertEqual(result["status"], "succeeded")

            workflow = result["delivery"]["executableWorkflow"]
            self.assertTrue(workflow["automaticExecutionRequired"])
            self.assertTrue(workflow["requestAlignedExecutableWorkflowAvailable"])
            self.assertGreaterEqual(workflow["automaticExecutionReadyWorkflowCandidates"], 1)
            self.assertGreaterEqual(workflow["requestAlignedAutomaticExecutionReadyWorkflowCandidates"], 1)
            self.assertFalse(workflow["manualGuiActivationRequired"])
            self.assertTrue(workflow["automaticActivationSupported"])

            guided_path = pathlib.Path(result["delivery"]["scriptArtifacts"]["guidedWorkflow"])
            self.assertTrue(guided_path.is_file())
            guided = guided_path.read_text(encoding="utf-8")
            self.assertIn("tool:Activate()", guided)
            self.assertIn("fireproximityprompt(prompt)", guided)
            self.assertIn("startButton.Activated:Connect(function() task.spawn(runWorkflow) end)", guided)
            self.assertIn("stopButton.Activated:Connect(function()", guided)


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

    def test_parts_job_accepts_split_live_observation_parts_and_builds_loadout_module(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track loadout observations")

            part_one = root / "PhantomForces_v30.6.68_Observation_Part_1_of_2.txt"
            part_two = root / "PhantomForces_v30.6.68_Observation_Part_2_of_2.txt"
            make_split_live_observation_parts(part_one, part_two)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Track loadout observations",
                observation_paths=(part_one, part_two),
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            warnings = result.get("analysis", {}).get("evidenceWarnings") or []
            self.assertTrue(any("Combined split observation parts" in item for item in warnings))
            self.assertTrue(any("Synthesized" in item for item in warnings))

            script_path = pathlib.Path(result["delivery"]["generatedScriptPath"])
            script = script_path.read_text(encoding="utf-8")
            self.assertIn('button("Loadout"', script)
            self.assertIn('button("Movement"', script)
            self.assertIn("LOADOUT_SNAPSHOT_COUNT = ", script)

            fulfillment = result.get("requestFulfillment") or {}
            self.assertIn("requiredBehaviors", fulfillment)
            self.assertFalse(fulfillment.get("runtimeVerified"))

            reconciliation = result.get("evidenceReconciliation") or {}
            self.assertTrue(reconciliation.get("generated"))
            summary = reconciliation.get("summary") or {}
            self.assertGreaterEqual(int(summary.get("targetedSessionsConsumed") or 0), 1)

    def test_request_fulfillment_marks_offline_complete_for_loadout_movement_contract(self):
        behavior_ids = ["ui.unified_categories"] + list(MODULE._LOADOUT_REQUIRED_BEHAVIORS) + list(MODULE._MOVEMENT_REQUIRED_BEHAVIORS)
        module_contract = {
            "behaviorCoverage": {
                behavior: {"generated": True, "evidenceSupported": True, "offlineValidated": True}
                for behavior in behavior_ids
            }
        }
        fulfillment = MODULE._assess_request_fulfillment(
            "Provide loadout and movement telemetry",
            module_contract,
            {"guidedWorkflowScriptGenerated": False,
             "requestAlignedExecutionReadyWorkflowCandidates": 0,
             "requestAlignedExecutableWorkflowAvailable": False},
            {"summary": {"gameplayImplementationReadyCapabilities": [{"capabilityId": "loadout_information_suite.loadout_gui_reader"}]}}
        )
        self.assertTrue(fulfillment["offlineImplementationComplete"])
        self.assertEqual(fulfillment["status"], "offline-implementation-complete-runtime-unverified")
        self.assertFalse(fulfillment["runtimeVerified"])
        self.assertIn("loadout_information_suite.loadout_gui_reader", fulfillment["implementationReadyCapabilities"])

    def test_request_fulfillment_keeps_automatic_request_unmet_without_executable_workflow(self):
        module_contract = {
            "behaviorCoverage": {
                "ui.unified_categories": {"generated": True, "evidenceSupported": True, "offlineValidated": True}
            }
        }
        fulfillment = MODULE._assess_request_fulfillment(
            "Automatically complete observed shop flow",
            module_contract,
            {"guidedWorkflowScriptGenerated": False,
             "requestAlignedExecutionReadyWorkflowCandidates": 0,
             "requestAlignedExecutableWorkflowAvailable": False},
            None,
        )
        self.assertFalse(fulfillment["offlineImplementationComplete"])
        self.assertIn("workflow.request_aligned_executable", fulfillment["missingBehaviors"])
        self.assertEqual(fulfillment["status"], "request-unmet-implementation-gap")

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

    def test_replay_package_import_runs_generation_job(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track combat observations")
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay)

            replay_dir = root / "replay"
            replay = REPLAY_MODULE.import_replay_package(
                baseline_inputs=[parts],
                observation_inputs=[overlay],
                output_dir=replay_dir,
                expected_place_id=3623096087,
                expected_baseline_scan_id="service_scan_001",
                expected_observation_scan_ids=["live-observation-service-1"],
            )

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="replay_package",
                evidence_path=pathlib.Path(replay["replayPackagePath"]),
                requested_capability="Track combat observations",
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["evidence"]["evidenceKind"], "replay_package")
            release_manifest_path = pathlib.Path(result["evidence"]["releaseManifestPath"])
            release_manifest = json.loads(release_manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(release_manifest["evidenceOverlayProvenance"]["overlayCount"], 1)

    def test_replay_package_preserves_legacy_timing_compatibility(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            legacy_event = {
                "featureCandidate": "rewards",
                "path": "LocalPlayer.Input.MouseButton1.None",
                "controlType": "Input.MouseButton1",
                "baselineSource": "input-event-callback",
                "baselineTiming": "activation-callback",
                "preActivationBaselineAvailable": False,
                "stateChanges": [{"key": "leaderstats.Coins", "before": 1, "after": 2}],
            }
            make_parts(parts, event=legacy_event, request="Collect rewards")

            replay_dir = root / "replay"
            replay = REPLAY_MODULE.import_replay_package(
                baseline_inputs=[parts],
                observation_inputs=[],
                output_dir=replay_dir,
                expected_place_id=3623096087,
                expected_baseline_scan_id="service_scan_001",
            )

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="replay_package",
                evidence_path=pathlib.Path(replay["replayPackagePath"]),
                requested_capability="Collect rewards",
            )
            result = service.run_sync(request)
            self.assertEqual(result["status"], "succeeded")
            self.assertIn(result["generationStatus"], {"generated", "generated-with-blockers", "observational-only-request-unmet", "blocked"})

    def test_autonomous_planner_fallback_selects_feasible_non_top_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            matched_id = MODULE._safe_feature_id("matched", "quests", "discovered")
            bundle = MODULE.EvidenceBundle(
                mode="multipart",
                place_id=85896571713843,
                scan_id="scan-fallback",
                output_dir=root,
                generation_readiness={
                    "generatedCapabilities": [
                        {
                            "id": "cap-infeasible",
                            "kind": "world-interaction",
                            "targetFeature": "rewards",
                            "targetPath": None,
                        }
                    ],
                    "requestFeatureReadiness": {
                        "featureEvidence": {
                            "matchedFeatures": [
                                {
                                    "feature": "quests",
                                    "status": "discovered",
                                    "evidenceClassification": "discovered-no-interaction-evidence",
                                }
                            ]
                        }
                    },
                },
            )
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=root,
                requested_capability="Collect rewards",
            )

            def fake_candidates(feature, _category, **_kwargs):
                if feature.get("id") == "cap-infeasible":
                    return [{
                        "id": "strategy-a-bring-pickups-to-player",
                        "label": "Strategy A",
                        "summary": "infeasible",
                        "feasible": False,
                        "score": 0.95,
                        "evidenceSignals": [],
                        "assumptions": ["missing anchors"],
                        "missingDependencies": ["workspace target path"],
                        "rejectionReasons": ["insufficient-evidence"],
                        "feasibilityClass": "insufficient-evidence",
                        "priorFailureCount": 0,
                    }]
                if feature.get("id") == matched_id:
                    return [{
                        "id": "strategy-c-direct-interaction",
                        "label": "Strategy C",
                        "summary": "feasible",
                        "feasible": True,
                        "score": 0.4,
                        "evidenceSignals": ["direct-control-signal-observed"],
                        "assumptions": [],
                        "missingDependencies": [],
                        "rejectionReasons": [],
                        "feasibilityClass": "supported",
                        "priorFailureCount": 0,
                    }]
                return []

            planner = MODULE.AutonomousPlanningEngine()
            with mock.patch.object(MODULE.AutonomousPlanningEngine, "_strategy_candidates", side_effect=fake_candidates):
                plan = planner.build_plan(bundle, request, analysis={}, feedback_penalties={})

            self.assertEqual(plan["selectionDiagnostics"]["highestRankedFeatureId"], "cap-infeasible")
            self.assertEqual(plan["selectedFeature"]["featureId"], matched_id)
            self.assertTrue(plan["selectionDiagnostics"]["fallbackUsed"])
            self.assertEqual(plan["selectedStrategy"]["id"], "strategy-c-direct-interaction")


    def test_matched_feature_semantic_mismatch_clears_path_and_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            bundle = MODULE.EvidenceBundle(
                mode="multipart",
                place_id=85896571713843,
                scan_id="scan-semantic-mismatch",
                output_dir=root,
                generation_readiness={
                    "requestFeatureReadiness": {
                        "featureEvidence": {
                            "matchedFeatures": [
                                {
                                    "feature": "rewards",
                                    "status": "discovered",
                                    "evidenceClassification": "interaction-observed-no-outcome-contract",
                                    "representativeTargetPath": "LocalPlayer.PlayerGui.ScreenGui.DailyRewards.Frame.Playtime.Top.Close.Button",
                                    "observedControlTypes": ["GuiButton.Activated"],
                                    "requestActionSemanticsAligned": False,
                                }
                            ]
                        }
                    }
                },
            )
            features = MODULE.AutonomousPlanningEngine._extract_features(bundle, analysis={})
            matched = [item for item in features if item.get("source") == "matched-feature"]
            self.assertEqual(len(matched), 1)
            self.assertIsNone(matched[0].get("targetPath"))
            self.assertEqual(matched[0].get("commands"), [])


    def test_malformed_overlay_timing_falls_back_to_baseline_without_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Collect rewards")
            overlay = root / "overlay.json"
            overlay.write_text("{}", encoding="utf-8")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            original_build = service.evidence_processor._build_release.build

            def patched_build(*args, **kwargs):
                if kwargs.get("observation_files"):
                    raise ValueError("Malformed interaction baseline timing")
                return original_build(*args, **kwargs)

            service.evidence_processor._build_release.build = patched_build
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Collect rewards",
                observation_paths=(overlay,),
            )
            result = service.run_sync(request)
            warnings = result["evidence"].get("warnings") or []
            self.assertTrue(any("falling back to baseline-only generation" in item for item in warnings))
            self.assertEqual(result["status"], "succeeded")

    def test_identical_jobs_reuse_analysis_cache_signature(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            provider = CountingProvider()
            service = MODULE.LycolesGenerationService(
                output_root=root / "jobs",
                llm_provider=provider,
                provider_info=provider.info(),
            )
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )

            first = service.run_sync(request)
            second = service.run_sync(request)

            self.assertEqual(provider.analysis_calls, 1)
            self.assertTrue(first["provider"]["analysisCacheEnabled"])
            self.assertFalse(first["provider"]["analysisCacheHit"])
            self.assertTrue(second["provider"]["analysisCacheHit"])
            self.assertEqual(first["provider"]["analysisCacheKey"], second["provider"]["analysisCacheKey"])
            self.assertGreater(first["usage"]["analysis"]["tokens"], 0)
            self.assertEqual(second["usage"]["analysis"]["tokens"], 0)

    def test_analysis_cache_persists_across_service_restarts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            first_provider = CountingProvider()
            first_service = MODULE.LycolesGenerationService(
                output_root=root / "jobs",
                llm_provider=first_provider,
                provider_info=first_provider.info(),
            )
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically hatch the selected egg",
            )
            first = first_service.run_sync(request)

            cache_path = root / "jobs" / "analysis-cache.json"
            self.assertTrue(cache_path.is_file())

            second_provider = CountingProvider()
            second_service = MODULE.LycolesGenerationService(
                output_root=root / "jobs",
                llm_provider=second_provider,
                provider_info=second_provider.info(),
            )
            second = second_service.run_sync(request)

            self.assertEqual(first_provider.analysis_calls, 1)
            self.assertEqual(second_provider.analysis_calls, 0)
            self.assertFalse(first["provider"]["analysisCacheHit"])
            self.assertTrue(second["provider"]["analysisCacheHit"])
            self.assertEqual(first["provider"]["analysisCacheKey"], second["provider"]["analysisCacheKey"])

            persisted = json.loads(cache_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted.get("schemaVersion"), "30.6.analysis-cache.1")
            self.assertGreaterEqual(len(persisted.get("entries") or []), 1)


    def test_parts_job_emits_autonomous_plan_artifact_and_verification_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Collect rewards and farm currency")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Collect rewards and farm currency",
            )
            result = service.run_sync(request)

            plan = result.get("autonomousGeneration") or {}
            self.assertEqual(plan.get("schemaVersion"), "30.6.autonomous-generation-plan.1")
            self.assertIn("featureDiscovery", plan)
            self.assertIn("verificationStates", plan)
            self.assertIn("selectedStrategy", plan)

            lifecycle = (result.get("validation") or {}).get("verificationLifecycle") or {}
            self.assertIn("states", lifecycle)
            self.assertIn("currentState", lifecycle)
            self.assertIn(lifecycle.get("currentState"), MODULE._VERIFICATION_STATE_ORDER)

            plan_path = pathlib.Path(result["delivery"]["autonomousGenerationPath"])
            self.assertTrue(plan_path.is_file())
            persisted = json.loads(plan_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted.get("schemaVersion"), "30.6.autonomous-generation-plan.1")

    def test_repeated_failed_strategy_is_demoted_in_next_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically collect rewards")

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Automatically collect rewards",
            )
            first = service.run_sync(request)
            selected_feature = ((first.get("autonomousGeneration") or {}).get("selectedFeature") or {})
            selected_strategy = ((first.get("autonomousGeneration") or {}).get("selectedStrategy") or {})
            self.assertTrue(selected_feature.get("featureId"))
            self.assertTrue(selected_strategy.get("id"))

            feedback_payload = {
                "placeId": first["evidence"]["placeId"],
                "scanId": first["evidence"]["scanId"],
                "featureId": selected_feature.get("featureId"),
                "strategyId": selected_strategy.get("id"),
                "status": "failed",
                "runtimeErrors": ["attempt failed"],
                "failedInteractions": ["activation timeout"],
            }
            service.record_feedback(feedback_payload)
            service.record_feedback(feedback_payload)

            second = service.run_sync(request)
            ranked = ((second.get("autonomousGeneration") or {}).get("featureDiscovery") or {}).get("ranked") or []
            self.assertGreaterEqual(len(ranked), 1)
            same_feature = next((item for item in ranked if item.get("featureId") == selected_feature.get("featureId")), None)
            self.assertIsNotNone(same_feature)
            same_strategy = next((item for item in (same_feature.get("strategies") or []) if item.get("id") == selected_strategy.get("id")), None)
            self.assertIsNotNone(same_strategy)
            self.assertGreaterEqual(same_strategy.get("priorFailureCount", 0), 2)
            self.assertFalse(same_strategy.get("feasible"))

    def test_record_feedback_roundtrip_and_listing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            payload = {
                "placeId": 85896571713843,
                "scanId": "scan-feedback-1",
                "featureId": "feature-abc",
                "strategyId": "strategy-c-direct-interaction",
                "status": "partial",
                "runtimeErrors": ["nil value"],
                "missingObjects": ["PlayerGui.ScreenGui.Shop.Button"],
                "successfulInteractions": ["Shop tab opened"],
                "observedChanges": ["leaderstats.Coins: 10 -> 11"],
                "notes": "Observed partial success.",
            }
            recorded = service.record_feedback(payload)
            self.assertEqual(recorded.get("status"), "recorded")
            listed = service.list_feedback()
            self.assertEqual(len(listed), 1)
            self.assertEqual(listed[0].get("scanId"), "scan-feedback-1")
            self.assertEqual(listed[0].get("status"), "partial")
            self.assertTrue((root / "jobs" / "feedback-log.jsonl").is_file())

    def test_job_result_includes_evidence_reconciliation_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track movement and combat observations")
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Track movement and combat observations",
                observation_paths=(overlay,),
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            reconciliation = result.get("evidenceReconciliation") or {}
            self.assertTrue(reconciliation.get("generated"))
            self.assertIsNone(reconciliation.get("error"))
            files = reconciliation.get("files") or {}
            self.assertIn("capabilityEvidenceContracts", files)
            self.assertTrue(pathlib.Path(files["capabilityEvidenceContracts"]).is_file())
            evidence_payload = result.get("evidence") or {}
            self.assertIn("evidenceReconciliationOutputDir", evidence_payload)
            self.assertTrue(pathlib.Path(evidence_payload["evidenceReconciliationOutputDir"]).is_dir())





    def test_job_result_consumes_targeted_evidence_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track movement and combat observations")
            overlay = root / "live-observation.json"
            targeted = root / "targeted-evidence.json"
            make_live_observation_export(overlay)
            make_targeted_evidence_export(targeted)

            service = MODULE.LycolesGenerationService(output_root=root / "jobs")
            request = MODULE.GenerationRequest(
                evidence_kind="parts_dir",
                evidence_path=parts,
                requested_capability="Track movement and combat observations",
                observation_paths=(overlay, targeted),
            )
            result = service.run_sync(request)

            self.assertEqual(result["status"], "succeeded")
            reconciliation = result.get("evidenceReconciliation") or {}
            self.assertTrue(reconciliation.get("generated"))
            summary = reconciliation.get("summary") or {}
            self.assertEqual(summary.get("targetedSessionsConsumed"), 1)

if __name__ == "__main__":
    unittest.main()
