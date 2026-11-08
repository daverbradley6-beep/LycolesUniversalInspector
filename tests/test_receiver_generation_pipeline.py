import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "receiver_generation_pipeline.py"
SPEC = importlib.util.spec_from_file_location("receiver_generation_pipeline", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def make_parts(directory, event=None, request=None, scan_id="receiver_pipeline_scan"):
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
        "stateChanges": [{"key": "leaderstats.🥚 Hatches", "before": 1, "after": 2}],
    }
    two = dict(
        scan,
        partIndex=2,
        objects=[{"path": "Workspace.B", "class": "Part", "scanOrdinal": 2}],
        interactionHistoryChunk=[interaction],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")





def make_workflow_ready_parts(directory, request="Complete observed shop flow", scan_id="receiver_pipeline_scan"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
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
        scanStats={"recorded": 2, "complete": True},
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



def make_automatic_workflow_ready_parts(directory, request="Automatically train and open shop prompt", scan_id="receiver_pipeline_auto_scan"):
    scan = {
        "scanId": scan_id,
        "placeId": 3623096087,
        "partCount": 2,
        "version": "10.0",
        "objects": [],
    }
    one = dict(
        scan,
        partIndex=1,
        scanStats={"recorded": 3, "complete": True},
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
        objects=[{"path": "Workspace.Shop.Door", "class": "Part", "scanOrdinal": 3}],
        interactionHistoryChunk=[tool_step, prompt_step],
    )
    (directory / "1.json").write_text(json.dumps(one), encoding="utf-8")
    (directory / "2.json").write_text(json.dumps(two), encoding="utf-8")

def make_live_observation_export(path, baseline_scan_id="receiver_pipeline_scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": baseline_scan_id,
        "baselineScanId": baseline_scan_id,
        "integrity": {
            "scanComplete": True,
            "placeId": 3623096087,
            "scanId": "live-observation-receiver-1",
            "baselineScanId": baseline_scan_id,
            "parts": 2,
            "interactionEvents": 7,
        },
        "sourceDiagnostics": {
            "scanMode": "dynamic-observations",
            "requiresFullObjectRescan": False,
            "baselineScanId": baseline_scan_id,
        },
        "sourceProvenance": {
            "schemaVersion": "30.2.source-provenance.1",
            "inputMode": "local-multipart",
            "scanId": "live-observation-receiver-1",
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
                "observationCoverage": 1.0,
                "timingDistribution": {"before": 2, "during": 2, "after": 3},
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")



def make_live_observation_tool_export(path, baseline_scan_id="receiver_pipeline_scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": baseline_scan_id,
        "baselineScanId": baseline_scan_id,
        "placeId": 3623096087,
        "gameName": "🎃Muscle Legends",
        "runtimeVerified": False,
        "gameplayVerified": False,
        "causalityProven": False,
        "serverAuthorityVerified": False,
        "sourceAuthenticityVerified": False,
        "integrity": {
            "scanComplete": True,
            "placeId": 3623096087,
            "scanId": "live-observation-recovery-1",
            "baselineScanId": baseline_scan_id,
            "parts": 2,
            "interactionEvents": 42,
        },
        "sourceDiagnostics": {
            "scanMode": "dynamic-observations",
            "requiresFullObjectRescan": False,
            "baselineScanId": baseline_scan_id,
        },
        "interactionDiagnostics": {
            "stateDeltaEvents": 317,
            "recentInteractions": [
                {
                    "controlType": "Tool.Activated",
                    "path": "LocalPlayer.Backpack.Weight",
                    "controlMetadata": {
                        "enabled": True,
                        "requiresHandle": True,
                        "canBeDropped": False,
                        "manualActivationOnly": False,
                    },
                    "stateChanges": [
                        {"key": "LocalPlayer.leaderstats.Strength", "before": 1033, "after": 1045},
                        {"key": "LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress", "before": 6, "after": 7},
                        {"key": "LocalPlayer.Quests.Daily Quests.Devoted Gains.requirements.Minutes.progress", "before": 1.5, "after": 1.6},
                        {"key": "Character.Humanoid.Health", "before": 95, "after": 100},
                    ],
                    "observationWindows": [{"seconds": 0.3}],
                },
                {
                    "controlType": "Tool.Activated",
                    "path": "LocalPlayer.Backpack.Weight",
                    "controlMetadata": {
                        "enabled": True,
                        "requiresHandle": True,
                        "canBeDropped": False,
                        "manualActivationOnly": False,
                    },
                    "stateChanges": [
                        {"key": "LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress", "before": 7, "after": 8},
                        {"key": "Character.Humanoid.ActiveAnimationCount", "before": 4, "after": 5},
                    ],
                    "observationWindows": [{"seconds": 0.4}],
                },
                {
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "rewards",
                    "path": "LocalPlayer.PlayerGui.gameGui.GroupRewardPrompt.ClaimButton",
                    "stateChanges": [
                        {"key": "LocalPlayer.leaderstats.Strength", "before": 1045, "after": 1050},
                    ],
                    "observationWindows": [{"seconds": 0.7}],
                },
                {
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "rewards",
                    "path": "LocalPlayer.PlayerGui.fortuneWheelMenuGui.fortuneMenu.buttonsFrame.spinButton",
                    "stateChanges": [],
                    "observationWindows": [{"seconds": 0.9}],
                },
                {
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "rebirth",
                    "path": "LocalPlayer.PlayerGui.gameGui.hudNewMenu.MiddleLeft.BTNList.Rebirth",
                    "stateChanges": [],
                    "observationWindows": [{"seconds": 0.8}],
                },
                {
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": None,
                    "path": "LocalPlayer.PlayerGui.gameGui.baseChoiceMenu.Content.Buttons.yesButton",
                    "stateChanges": [],
                    "observationWindows": [{"seconds": 0.8}],
                },
                {
                    "controlType": "InputBegan.Keyboard",
                    "actionKind": "interact",
                    "path": "LocalPlayer.Input.Keyboard.E",
                    "stateChanges": [],
                    "observationWindows": [{"seconds": 0.5}],
                },

            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


class ReceiverGenerationPipelineTests(unittest.TestCase):
    def test_generate_from_parts_runs_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Automatically hatch the selected egg",
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertIn(
                result["generationStatus"],
                ("generated", "generated-with-blockers", "observational-only-request-unmet"),
            )
            generated_result = pathlib.Path(result["delivery"]["generatedResultPath"])
            self.assertTrue(generated_result.is_file())

            readiness = json.loads(pathlib.Path(result["evidence"]["generationReadinessPath"]).read_text(encoding="utf-8"))
            self.assertEqual(readiness["request"]["request"],
                             "Automatically hatch the selected egg")
            self.assertNotEqual(readiness["request"]["status"], "no-capability-requested")


    def test_generate_from_parts_accepts_live_observation_overlay_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Track observed reload behavior")
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay)

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Track observed reload behavior",
                observation_paths=[overlay],
            )
            self.assertEqual(result["status"], "succeeded")
            release_manifest = json.loads(
                pathlib.Path(result["evidence"]["releaseManifestPath"]).read_text(encoding="utf-8")
            )
            self.assertEqual(release_manifest["evidenceOverlayProvenance"]["overlayCount"], 1)
            overlay_provenance = json.loads(
                (pathlib.Path(result["outputDir"]) / "evidence-overlay-provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(overlay_provenance["overlays"][0]["scanId"], "live-observation-receiver-1")

    def test_generate_from_parts_require_executable_blocks_manual_guided_subset_for_automatic_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_workflow_ready_parts(parts, request="Automatically complete observed shop flow")

            with self.assertRaisesRegex(ValueError, "Executable workflow required but unavailable"):
                MODULE.generate_from_parts(
                    parts_dir=parts,
                    output_root=root / "output",
                    requested_capability="Automatically complete observed shop flow",
                    require_executable=True,
                )

    def test_generate_from_parts_require_executable_succeeds_for_automatic_workflow_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_automatic_workflow_ready_parts(parts)

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Automatically train and open shop prompt",
                require_executable=True,
            )
            summary = MODULE.summarize_generation_result(result)
            self.assertEqual(summary["executableLogic"]["requestExecutableStatus"], "request-executable-ready")
            self.assertTrue(summary["executableLogic"]["automaticExecutionRequired"])
            self.assertGreaterEqual(summary["executableLogic"]["requestAlignedAutomaticExecutionReadyWorkflows"], 1)
            self.assertGreaterEqual(summary["executableLogic"]["automaticExecutionReadyWorkflowCandidates"], 1)
            self.assertEqual(summary["observationalOnly"], [])

    def test_summarize_generation_result_flags_observational_only_when_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically shoot and reload")

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Automatically shoot and reload",
            )
            summary = MODULE.summarize_generation_result(result)
            self.assertTrue(summary["generatedResultAvailable"])
            self.assertIsInstance(summary["implementedCapabilities"], list)
            self.assertIn("requested capability is not implementation-ready", summary["observationalOnly"])
            self.assertIn("no request-aligned execution-ready workflow candidates", summary["observationalOnly"])

    def test_resolve_parts_dir_for_scan_id_prefers_exact_manifest_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            extracted = root / "extracted"
            scan_dir = extracted / "arsenal_case"
            scan_dir.mkdir(parents=True)
            manifest = {
                "scanId": "DBFC72C6-749B-4F95-BBA2-433B8B61745C",
                "placeId": 286090429,
                "partCount": 2,
                "gameName": "Arsenal",
            }
            (scan_dir / "sample_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            resolved = MODULE._resolve_parts_dir_for_scan_id(
                extracted, "DBFC72C6-749B-4F95-BBA2-433B8B61745C")
            self.assertEqual(resolved, scan_dir.resolve())


    def test_summarize_generation_result_marks_request_executable_ready_when_workflow_generated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_workflow_ready_parts(parts)

            result = MODULE.generate_from_parts(
                parts_dir=parts,
                output_root=root / "output",
                requested_capability="Complete observed shop flow",
            )
            summary = MODULE.summarize_generation_result(result)
            self.assertTrue(summary["generatedResultAvailable"])
            self.assertEqual(summary["executableLogic"]["requestExecutableStatus"], "request-executable-ready")
            self.assertGreaterEqual(summary["executableLogic"]["executionReadyWorkflowCandidates"], 1)
            self.assertTrue(pathlib.Path(summary["generatedScriptPath"]).is_file())
            self.assertEqual(summary["generatedScriptKind"], "combined-utility")
            self.assertEqual(summary["observationalOnly"], [])

    def test_generate_from_parts_require_executable_raises_when_request_unmet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically shoot and reload")

            with self.assertRaisesRegex(ValueError, "Executable workflow required but unavailable"):
                MODULE.generate_from_parts(
                    parts_dir=parts,
                    output_root=root / "output",
                    requested_capability="Automatically shoot and reload",
                    require_executable=True,
                )

    def test_exercise_live_reports_requested_baseline_when_parts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            result = MODULE.run_live_evidence_exercise(
                output_root=root / "out",
                requested_capability_arsenal="Automatically shoot and reload in Arsenal",
                requested_capability_phantom="Automatically shoot and reload in Phantom Forces",
                observation_paths=[],
                extracted_root=root / "missing-extracted",
                arsenal_baseline_scan_id="DBFC72C6-749B-4F95-BBA2-433B8B61745C",
                phantom_baseline_scan_id="6D3741EF-9569-4F40-B38A-E4FD2AE0A063",
            )
            scenarios = {item["name"]: item for item in result["scenarios"]}
            self.assertEqual(scenarios["arsenal"]["status"], "blocked")
            self.assertEqual(scenarios["arsenal"]["requestedBaselineScanId"],
                             "DBFC72C6-749B-4F95-BBA2-433B8B61745C")
            self.assertEqual(scenarios["phantom-forces"]["status"], "blocked")
            self.assertEqual(scenarios["phantom-forces"]["requestedBaselineScanId"],
                             "6D3741EF-9569-4F40-B38A-E4FD2AE0A063")


    def test_exercise_live_marks_observational_only_when_request_not_executable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            extracted = root / "extracted"
            arsenal_dir = extracted / "arsenal_case"
            arsenal_dir.mkdir(parents=True)
            make_parts(arsenal_dir, request="Automatically shoot and reload", scan_id="arsenal-scan")
            (arsenal_dir / "1.json").replace(arsenal_dir / "part-1.json")
            (arsenal_dir / "2.json").replace(arsenal_dir / "part-2.json")

            result = MODULE.run_live_evidence_exercise(
                output_root=root / "out",
                requested_capability_arsenal="Automatically shoot and reload",
                requested_capability_phantom="Automatically shoot and reload",
                observation_paths=[],
                extracted_root=extracted,
                arsenal_baseline_scan_id="arsenal-scan",
                phantom_baseline_scan_id="phantom-missing",
            )
            scenarios = {item["name"]: item for item in result["scenarios"]}
            self.assertEqual(scenarios["arsenal"]["status"], "observational-only-request-unmet")
            self.assertEqual(
                scenarios["arsenal"]["summary"]["executableLogic"]["requestExecutableStatus"],
                "request-executable-unavailable",
            )
            self.assertEqual(scenarios["phantom-forces"]["status"], "blocked")

    def test_exercise_live_marks_success_when_request_executable_workflow_is_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            extracted = root / "extracted"
            arsenal_dir = extracted / "arsenal_case"
            arsenal_dir.mkdir(parents=True)
            make_workflow_ready_parts(arsenal_dir, request="Complete observed shop flow", scan_id="arsenal-ready")
            (arsenal_dir / "1.json").replace(arsenal_dir / "part-1.json")
            (arsenal_dir / "2.json").replace(arsenal_dir / "part-2.json")

            result = MODULE.run_live_evidence_exercise(
                output_root=root / "out",
                requested_capability_arsenal="Complete observed shop flow",
                requested_capability_phantom="Automatically shoot and reload",
                observation_paths=[],
                extracted_root=extracted,
                arsenal_baseline_scan_id="arsenal-ready",
                phantom_baseline_scan_id="phantom-missing",
            )
            scenarios = {item["name"]: item for item in result["scenarios"]}
            self.assertEqual(scenarios["arsenal"]["status"], "succeeded")
            self.assertEqual(
                scenarios["arsenal"]["summary"]["executableLogic"]["requestExecutableStatus"],
                "request-executable-ready",
            )
            self.assertTrue(pathlib.Path(scenarios["arsenal"]["summary"]["generatedScriptPath"]).is_file())


    def test_run_live_observation_scenario_blocks_when_baseline_parts_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "live-observation.json"
            make_live_observation_export(overlay, baseline_scan_id="missing-baseline")

            result = MODULE.run_live_observation_scenario(
                output_root=root / "out",
                observation_path=overlay,
                requested_capability="Automatically train and open shop prompt",
                extracted_root=root / "missing-extracted",
            )
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "baseline parts evidence unavailable")
            self.assertEqual(result["baselineScanId"], "missing-baseline")
            self.assertEqual(result["overlayCount"], 1)

    def test_run_live_observation_scenario_succeeds_for_matching_automatic_workflow(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            extracted = root / "extracted"
            baseline = extracted / "muscle_case"
            baseline.mkdir(parents=True)
            make_automatic_workflow_ready_parts(
                baseline,
                request="Automatically train and open shop prompt",
                scan_id="baseline-auto-123",
            )
            (baseline / "1.json").replace(baseline / "part-1.json")
            (baseline / "2.json").replace(baseline / "part-2.json")

            overlay = root / "live-observation.json"
            make_live_observation_export(overlay, baseline_scan_id="baseline-auto-123")

            result = MODULE.run_live_observation_scenario(
                output_root=root / "out",
                observation_path=overlay,
                requested_capability="Automatically train and open shop prompt",
                extracted_root=extracted,
                require_executable=True,
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(
                result["summary"]["executableLogic"]["requestExecutableStatus"],
                "request-executable-ready",
            )
            self.assertTrue(pathlib.Path(result["summary"]["generatedScriptPath"]).is_file())

    def test_run_live_observation_scenario_recovers_auto_train_without_baseline_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "live-observation.json"
            make_live_observation_tool_export(overlay, baseline_scan_id="missing-baseline")

            result = MODULE.run_live_observation_scenario(
                output_root=root / "out",
                observation_path=overlay,
                requested_capability="Automatically train with Weight tool",
                extracted_root=root / "missing-extracted",
                require_executable=True,
            )
            self.assertEqual(result["status"], "recovered-observation-contract")
            summary = result["summary"]
            self.assertEqual(summary["executableLogic"]["requestExecutableStatus"], "request-executable-ready")
            self.assertTrue(pathlib.Path(summary["generatedScriptPath"]).is_file())
            self.assertTrue(pathlib.Path(summary["contractPath"]).is_file())
            self.assertTrue(pathlib.Path(summary["loaderTemplatePath"]).is_file())

            contract = json.loads(pathlib.Path(summary["contractPath"]).read_text(encoding="utf-8"))
            self.assertEqual(contract["schemaVersion"], "117.observation-tool-contract.3")
            outcome_model = contract["outcomeModel"]
            self.assertEqual(outcome_model["kind"], "delayed-cumulative")
            self.assertEqual(outcome_model["primaryStatePath"], "LocalPlayer.leaderstats.Strength")
            self.assertIn(
                "LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress",
                outcome_model["questRepetitionStatePaths"],
            )
            self.assertNotIn(
                "LocalPlayer.Quests.Daily Quests.Devoted Gains.requirements.Minutes.progress",
                outcome_model["questRepetitionStatePaths"],
            )
            self.assertIn("auto_train", contract["generatedFeatureIds"])
            self.assertIn("auto_rewards", contract["generatedFeatureIds"])
            self.assertIn("auto_rebirth", contract["generatedFeatureIds"])
            feature_map = {item["id"]: item for item in contract["featureContracts"]}
            self.assertEqual(feature_map["auto_rewards"]["action"]["kind"], "auto_rewards_discovery")
            self.assertGreaterEqual(len(feature_map["auto_rewards"]["action"].get("rewardContainerPaths") or []), 1)
            self.assertEqual(feature_map["quest_automation"]["action"]["kind"], "quest_train_workflow")


            self.assertEqual(summary["generatedScriptKind"], "observation-multi-feature-batch")
            self.assertIn("quest_automation", summary["implementedFeatures"])
            self.assertIn("proximity_interactions", summary["excludedFeatures"])

            script_text = pathlib.Path(summary["generatedScriptPath"]).read_text(encoding="utf-8")
            self.assertIn("START ALL", script_text)
            self.assertIn("STOP ALL", script_text)
            self.assertIn("COPY REPORT", script_text)
            self.assertIn("MIN", script_text)
            self.assertIn("title.InputBegan", script_text)
            self.assertIn("runtimeCapabilities", script_text)
            self.assertIn("firesignal", script_text)
            self.assertIn("unsupportedFeatures", script_text)

    def test_generate_from_receiver_requires_read_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            previous = MODULE.os.environ.get("LYCOLES_READ_KEY")
            try:
                if "LYCOLES_READ_KEY" in MODULE.os.environ:
                    del MODULE.os.environ["LYCOLES_READ_KEY"]
                with self.assertRaisesRegex(ValueError, "LYCOLES_READ_KEY"):
                    MODULE.generate_from_receiver(
                        receiver_endpoint="https://example.com",
                        scan_id="scan123456",
                        output_root=root,
                    )
            finally:
                if previous is not None:
                    MODULE.os.environ["LYCOLES_READ_KEY"] = previous


    def test_generate_from_receiver_forwards_legacy_page_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            previous = MODULE.os.environ.get("LYCOLES_READ_KEY")
            original_fetch = MODULE.FETCH.fetch_scan
            original_generate = MODULE.generate_from_parts
            captured = {}

            def fake_fetch(endpoint, read_key, scan_id, output, **kwargs):
                output_path = pathlib.Path(output)
                output_path.mkdir(parents=True, exist_ok=True)
                captured["kwargs"] = kwargs
                return {
                    "schemaVersion": "30.2.receiver-import-legacy-reports.1",
                    "scanId": scan_id,
                    "placeId": 3623096087,
                    "partCount": 2,
                    "objectCount": 2,
                    "featureCount": 0,
                    "output": str(output_path),
                }

            def fake_generate_from_parts(**_kwargs):
                return {"status": "succeeded", "claims": {"runtimeVerified": False}}

            try:
                MODULE.os.environ["LYCOLES_READ_KEY"] = "read-secret"
                MODULE.FETCH.fetch_scan = fake_fetch
                MODULE.generate_from_parts = fake_generate_from_parts
                result = MODULE.generate_from_receiver(
                    receiver_endpoint="https://example.com",
                    scan_id="scan123456",
                    output_root=root,
                    allow_legacy_report_index=True,
                    max_legacy_report_pages=1234,
                )
                self.assertEqual(result["fetch"]["scanId"], "scan123456")
                self.assertEqual(captured["kwargs"]["max_legacy_report_pages"], 1234)
                self.assertTrue(captured["kwargs"]["allow_legacy_report_index"])
            finally:
                MODULE.FETCH.fetch_scan = original_fetch
                MODULE.generate_from_parts = original_generate
                if previous is None:
                    MODULE.os.environ.pop("LYCOLES_READ_KEY", None)
                else:
                    MODULE.os.environ["LYCOLES_READ_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
