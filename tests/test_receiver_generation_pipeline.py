import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest
import zipfile

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


def make_parts_archive(parts_dir, archive_path, scan_id="receiver_pipeline_scan", place_id=3623096087):
    part_files = []
    for source_name, index in (("1.json", 1), ("2.json", 2)):
        payload = json.loads((parts_dir / source_name).read_text(encoding="utf-8"))
        payload["scanId"] = scan_id
        payload["placeId"] = place_id
        payload["partCount"] = 2
        payload["partIndex"] = index
        archive_name = f"Lycoles_{place_id}_{scan_id}_part-{index:04d}.json"
        part_files.append((archive_name, json.dumps(payload).encode("utf-8")))

    manifest = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "expectedParts": 2,
        "objectCount": 2,
        "uploadedParts": 0,
        "version": "10.0",
    }

    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name, raw in part_files:
            bundle.writestr(name, raw)
        bundle.writestr(
            f"Lycoles_{place_id}_{scan_id}_manifest.json",
            json.dumps(manifest).encode("utf-8"),
        )




def make_split_parts_archives(
    parts_dir,
    archive_one,
    archive_two,
    scan_id="receiver_pipeline_scan",
    place_id=3623096087,
    uploaded_parts=1,
):
    payload_one = json.loads((parts_dir / "1.json").read_text(encoding="utf-8"))
    payload_two = json.loads((parts_dir / "2.json").read_text(encoding="utf-8"))
    payload_one.update({"scanId": scan_id, "placeId": place_id, "partCount": 2, "partIndex": 1})
    payload_two.update({"scanId": scan_id, "placeId": place_id, "partCount": 2, "partIndex": 2})

    manifest = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "expectedParts": 2,
        "uploadedParts": uploaded_parts,
        "version": "10.0",
    }

    with zipfile.ZipFile(archive_one, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_manifest.json", json.dumps(manifest).encode("utf-8"))
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0001.json", json.dumps(payload_one).encode("utf-8"))

    with zipfile.ZipFile(archive_two, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0002.json", json.dumps(payload_two).encode("utf-8"))


def make_broken_parts_archive_missing_part(archive_path, scan_id="receiver_pipeline_scan", place_id=3623096087):
    part = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "partIndex": 1,
        "version": "10.0",
        "objects": [],
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0001.json", json.dumps(part).encode("utf-8"))


def make_broken_parts_archive_duplicate_conflict(archive_path, scan_id="receiver_pipeline_scan", place_id=3623096087):
    first = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "partIndex": 1,
        "version": "10.0",
        "objects": [{"path": "Workspace.A", "class": "Part"}],
    }
    conflicting = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "partIndex": 1,
        "version": "10.0",
        "objects": [{"path": "Workspace.B", "class": "Part"}],
    }
    second = {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": 2,
        "partIndex": 2,
        "version": "10.0",
        "objects": [{"path": "Workspace.C", "class": "Part"}],
    }
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0001.json", json.dumps(first).encode("utf-8"))
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0001-duplicate.json", json.dumps(conflicting).encode("utf-8"))
        bundle.writestr(f"Lycoles_{place_id}_{scan_id}_part-0002.json", json.dumps(second).encode("utf-8"))






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
                    "beforePositionSample": {
                        "sessionElapsedSeconds": 12.2,
                        "characterGeneration": 1,
                        "positionValid": True,
                        "position": {"x": 35.2, "y": 4.1, "z": -12.8},
                        "sampled": True,
                        "interpolated": False,
                    },
                    "actionPositionSample": {
                        "sessionElapsedSeconds": 12.3,
                        "characterGeneration": 1,
                        "positionValid": True,
                        "position": {"x": 35.9, "y": 4.1, "z": -12.1},
                        "sampled": True,
                        "interpolated": False,
                    },
                    "nearbyWorldObjects": [
                        {
                            "path": "Workspace.Decoration.Rock01",
                            "class": "Part",
                            "sourceScope": "workspace-active",
                            "distanceStuds": 4.5,
                            "position": {"x": 37.0, "y": 4.0, "z": -10.0},
                            "interactionMechanisms": ["touch"],
                        }
                    ],
                    "inferredLocationPurpose": "training-or-progression",
                    "eventPositionSnapshots": [
                        {
                            "interactionSequence": 1,
                            "transactionId": "tx-1",
                            "phase": "at-action",
                            "sampled": True,
                            "interpolated": False,
                            "sessionElapsedSeconds": 12.3,
                            "characterGeneration": 1,
                            "position": {"x": 35.9, "y": 4.1, "z": -12.1},
                        }
                    ],
                    "observationWindows": [
                        {
                            "seconds": 0.3,
                            "positionSample": {
                                "sessionElapsedSeconds": 12.6,
                                "characterGeneration": 1,
                                "positionValid": True,
                                "position": {"x": 36.6, "y": 4.2, "z": -11.3},
                                "sampled": True,
                                "interpolated": False,
                            },
                        }
                    ],
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
            "playerPositionHistory": [
                {
                    "snapshotSequence": 1,
                    "sampledAt": "2026-11-06T12:30:00Z",
                    "sessionElapsedSeconds": 12.2,
                    "reason": "pre-activation",
                    "characterGeneration": 1,
                    "positionValid": True,
                    "position": {"x": 35.2, "y": 4.1, "z": -12.8},
                    "sampled": True,
                    "interpolated": False,
                },
                {
                    "snapshotSequence": 2,
                    "sampledAt": "2026-11-06T12:30:01Z",
                    "sessionElapsedSeconds": 12.6,
                    "reason": "observation-window-0.3",
                    "characterGeneration": 1,
                    "positionValid": True,
                    "position": {"x": 36.6, "y": 4.2, "z": -11.3},
                    "sampled": True,
                    "interpolated": False,
                },
            ],
            "eventPositionSnapshots": [
                {
                    "interactionSequence": 1,
                    "transactionId": "tx-1",
                    "phase": "at-action",
                    "sampled": True,
                    "interpolated": False,
                    "sessionElapsedSeconds": 12.3,
                    "characterGeneration": 1,
                    "position": {"x": 35.9, "y": 4.1, "z": -12.1},
                }
            ],
            "spatialLocationHistory": [
                {
                    "interactionSequence": 1,
                    "transactionId": "tx-1",
                    "featureCandidate": "training",
                    "actionKind": "fire",
                    "controlType": "Tool.Activated",
                    "path": "LocalPlayer.Backpack.Weight",
                    "purpose": "training-or-progression",
                    "sessionElapsedSeconds": 12.3,
                    "characterGeneration": 1,
                    "position": {"x": 35.9, "y": 4.1, "z": -12.1},
                    "nearbyWorldObjects": [
                        {
                            "path": "Workspace.Decoration.Rock01",
                            "class": "Part",
                            "distanceStuds": 4.5,
                            "position": {"x": 37.0, "y": 4.0, "z": -10.0},
                        }
                    ],
                    "sampled": True,
                    "interpolated": False,
                }
            ],
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")




def make_pointer_only_observation_export(path, scan_id="pointer-only-scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": scan_id,
        "baselineScanId": scan_id,
        "placeId": 111,
        "gameName": "Pointer Only Test",
        "interactionDiagnostics": {
            "recentInteractions": [
                {
                    "sequence": 1,
                    "transactionId": "tx-1",
                    "controlType": "InputBegan.MouseButton2",
                    "actionKind": "interact",
                    "path": "LocalPlayer.Input.MouseButton2.None",
                    "stateChanges": [
                        {"key": "Character.Humanoid.ActiveAnimations", "before": 1, "after": 2},
                    ],
                    "actionPositionSample": {
                        "interactionSequence": 1,
                        "transactionId": "tx-1",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 10, "y": 4, "z": 15},
                        "worldContext": {"path": "Workspace.World.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Foliage.TreeA", "class": "Part", "distanceStuds": 3.4}
                    ],
                }
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_gui_repeat_observation_export(path, scan_id="gui-repeat-scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": scan_id,
        "baselineScanId": scan_id,
        "placeId": 222,
        "gameName": "GUI Repeat Test",
        "interactionDiagnostics": {
            "recentInteractions": [
                {
                    "sequence": 1,
                    "transactionId": "tx-1",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.Shop.Frame.Items.A.Button",
                    "stateChanges": [{"key": "Character.Humanoid.ActiveAnimations", "before": 1, "after": 2}],
                    "actionPositionSample": {
                        "interactionSequence": 1,
                        "transactionId": "tx-1",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 30.1, "y": 9.0, "z": -102.4},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.ShopKeeper", "class": "Model", "distanceStuds": 5.0}
                    ],
                },
                {
                    "sequence": 2,
                    "transactionId": "tx-1",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.Shop.Frame.Items.B.Button",
                    "stateChanges": [{"key": "Character.Humanoid.ActiveAnimationCount", "before": 3, "after": 4}],
                    "actionPositionSample": {
                        "interactionSequence": 2,
                        "transactionId": "tx-1",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 30.2, "y": 9.0, "z": -102.2},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.ShopKeeper", "class": "Model", "distanceStuds": 5.2}
                    ],
                },
                {
                    "sequence": 3,
                    "transactionId": "tx-2",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.Shop.Frame.Close",
                    "stateChanges": [{"key": "Character.Humanoid.MoveDirectionMagnitude", "before": 0, "after": 1}],
                    "actionPositionSample": {
                        "interactionSequence": 3,
                        "transactionId": "tx-2",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 30.0, "y": 9.0, "z": -102.0},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.ShopKeeper", "class": "Model", "distanceStuds": 5.1}
                    ],
                },
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_multi_world_observation_export(path, scan_id="multi-world-scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": scan_id,
        "baselineScanId": scan_id,
        "placeId": 333,
        "gameName": "Multi World Test",
        "interactionDiagnostics": {
            "recentInteractions": [
                {
                    "sequence": 1,
                    "transactionId": "tx-a",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "travel",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.FastTravel.A.Button",
                    "stateChanges": [{"key": "leaderstats.Coins", "before": 10, "after": 11}],
                    "actionPositionSample": {
                        "interactionSequence": 1,
                        "transactionId": "tx-a",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 0, "y": 5, "z": 0},
                        "worldContext": {"path": "Workspace.Worlds.Alpha"},
                    },
                    "nearbyWorldObjects": [{"path": "Workspace.Worlds.Alpha.FastTravel", "class": "Model", "distanceStuds": 4.0}],
                },
                {
                    "sequence": 2,
                    "transactionId": "tx-b",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "travel",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.FastTravel.B.Button",
                    "stateChanges": [{"key": "leaderstats.Coins", "before": 11, "after": 12}],
                    "actionPositionSample": {
                        "interactionSequence": 2,
                        "transactionId": "tx-b",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 0, "y": 5, "z": 0},
                        "worldContext": {"path": "Workspace.Worlds.Beta"},
                    },
                    "nearbyWorldObjects": [{"path": "Workspace.Worlds.Beta.FastTravel", "class": "Model", "distanceStuds": 4.2}],
                },
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")



def make_overlapping_destination_observation_export(path, scan_id="overlapping-destination-scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": scan_id,
        "baselineScanId": scan_id,
        "placeId": 444,
        "gameName": "Overlapping Destination Test",
        "interactionDiagnostics": {
            "recentInteractions": [
                {
                    "sequence": 1,
                    "transactionId": "shop-a",
                    "characterGeneration": 1,
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Items.Lemon.Button",
                    "stateChanges": [{"key": "Character.Humanoid.ActiveAnimations", "before": 1, "after": 2}],
                    "actionPositionSample": {
                        "interactionSequence": 1,
                        "transactionId": "shop-a",
                        "characterGeneration": 1,
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 35.3212, "y": 9.16, "z": -113.0463},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.GumShop.Counter", "class": "Part", "distanceStuds": 4.1},
                        {"path": "Workspace.Worlds.Overworld.GumShop.NPC", "class": "Model", "distanceStuds": 4.3},
                    ],
                },
                {
                    "sequence": 2,
                    "transactionId": "shop-b",
                    "characterGeneration": 2,
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Selected.Action.Button",
                    "stateChanges": [{"key": "Character.Humanoid.ActiveAnimationCount", "before": 3, "after": 4}],
                    "actionPositionSample": {
                        "interactionSequence": 2,
                        "transactionId": "shop-b",
                        "characterGeneration": 2,
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 35.29, "y": 9.16, "z": -113.09},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.GumShop.Counter", "class": "Part", "distanceStuds": 4.2},
                        {"path": "Workspace.Worlds.Overworld.GumShop.NPC", "class": "Model", "distanceStuds": 4.4},
                    ],
                },
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def make_nearby_unrelated_observation_export(path, scan_id="nearby-unrelated-scan"):
    payload = {
        "schemaVersion": "30.6.live-observation-export.1",
        "exportKind": "dynamic-observations",
        "scanId": scan_id,
        "baselineScanId": scan_id,
        "placeId": 555,
        "gameName": "Nearby Unrelated Target Test",
        "interactionDiagnostics": {
            "recentInteractions": [
                {
                    "sequence": 1,
                    "transactionId": "shop-tx",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "shops",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.Shop.Frame.Buy.Button",
                    "stateChanges": [{"key": "Character.Humanoid.ActiveAnimations", "before": 1, "after": 2}],
                    "actionPositionSample": {
                        "interactionSequence": 1,
                        "transactionId": "shop-tx",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 12.0, "y": 6.0, "z": -8.0},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.ShopKeeper", "class": "Model", "distanceStuds": 3.2}
                    ],
                },
                {
                    "sequence": 2,
                    "transactionId": "reward-tx",
                    "controlType": "GuiButton.Activated",
                    "featureCandidate": "rewards",
                    "path": "LocalPlayer.PlayerGui.ScreenGui.Rewards.Frame.Claim.Button",
                    "stateChanges": [{"key": "leaderstats.Coins", "before": 100, "after": 110}],
                    "actionPositionSample": {
                        "interactionSequence": 2,
                        "transactionId": "reward-tx",
                        "phase": "at-action",
                        "sampled": True,
                        "position": {"x": 14.1, "y": 6.0, "z": -8.2},
                        "worldContext": {"path": "Workspace.Worlds.Overworld"},
                    },
                    "nearbyWorldObjects": [
                        {"path": "Workspace.Worlds.Overworld.DailyChest", "class": "Model", "distanceStuds": 3.0}
                    ],
                },
            ]
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

    def test_generate_from_parts_accepts_zip_archive_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts, request="Automatically hatch the selected egg")
            archive = root / "parts.zip"
            make_parts_archive(parts, archive)

            result = MODULE.generate_from_parts(
                parts_dir=archive,
                output_root=root / "output",
                requested_capability="Automatically hatch the selected egg",
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertIn("partsArchiveIngestion", result)
            ingestion = result["partsArchiveIngestion"]
            self.assertEqual(ingestion["partCount"], 2)
            self.assertEqual(ingestion["missingPartCount"], 0)
            self.assertTrue(pathlib.Path(ingestion["outputDir"]).is_dir())

    def test_ingest_parts_archives_accepts_split_archives_and_reports_receiver_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts)
            archive_one = root / "split-1.zip"
            archive_two = root / "split-2.zip"
            make_split_parts_archives(parts, archive_one, archive_two, uploaded_parts=1)

            ingestion = MODULE.ingest_parts_archives(
                [archive_one, archive_two],
                root / "extracted",
                expected_scan_id="receiver_pipeline_scan",
            )
            self.assertEqual(ingestion["partCount"], 2)
            self.assertEqual(ingestion["missingPartCount"], 0)
            self.assertEqual(ingestion["sourceArchiveCount"], 2)
            self.assertEqual(ingestion["manifestUploadedPartsObserved"], 1)
            self.assertEqual(ingestion["receiverAcknowledgementGap"], 1)
            self.assertFalse(ingestion["receiverAcknowledgementComplete"])
            self.assertTrue(pathlib.Path(ingestion["outputDir"]).is_dir())

    def test_ingest_parts_archive_rejects_missing_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            archive = root / "broken_missing.zip"
            make_broken_parts_archive_missing_part(archive)
            with self.assertRaisesRegex(ValueError, "missing parts"):
                MODULE.ingest_parts_archive(archive, root / "extracted")

    def test_ingest_parts_archive_rejects_conflicting_duplicate_parts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            archive = root / "broken_duplicate.zip"
            make_broken_parts_archive_duplicate_conflict(archive)
            with self.assertRaisesRegex(ValueError, "conflicting duplicate part content"):
                MODULE.ingest_parts_archive(archive, root / "extracted")

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
            self.assertEqual(result["status"], "discovery-only")
            self.assertEqual(result["baselineScanId"], "missing-baseline")
            self.assertEqual(result["overlayCount"], 1)
            self.assertIn("discovery", result)
            discovery = result["discovery"]
            self.assertTrue(pathlib.Path(discovery["reportPath"]).is_file())
            self.assertTrue(pathlib.Path(discovery["summaryPath"]).is_file())
            self.assertEqual(result["summary"]["status"], "generated-discovery-only")
            self.assertIsNone(result["summary"].get("generatedScriptPath"))


    def test_run_universal_discovery_export_outputs_schema_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            parts = root / "parts"
            parts.mkdir()
            make_parts(parts)
            archive_one = root / "split-1.zip"
            archive_two = root / "split-2.zip"
            make_split_parts_archives(parts, archive_one, archive_two, uploaded_parts=1)

            overlay = root / "live-observation.json"
            make_live_observation_tool_export(overlay, baseline_scan_id="receiver_pipeline_scan")
            payload = json.loads(overlay.read_text(encoding="utf-8"))
            recent = payload.get("interactionDiagnostics", {}).get("recentInteractions", [])
            if isinstance(recent, list) and recent and isinstance(recent[0], dict):
                nearby = recent[0].setdefault("nearbyWorldObjects", [])
                if isinstance(nearby, list):
                    nearby.append({"path": "Workspace.", "class": "Workspace"})
                    nearby.append({"path": "ReplicatedStorage.Assets.EggTemplate", "class": "Model"})
            overlay.write_text(json.dumps(payload), encoding="utf-8")

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Identify mechanics and progression systems",
                scenario_name="bubble-like-discovery",
                baseline_archives=[archive_one, archive_two],
            )
            self.assertEqual(result["status"], "succeeded")
            self.assertEqual(result["schemaVersion"], "live-observation-discovery.1")
            self.assertEqual(result["baselineArchiveValidation"]["sourceArchiveCount"], 2)
            self.assertEqual(result["baselineArchiveValidation"]["receiverAcknowledgementGap"], 1)

            discovery = result["discovery"]
            report_path = pathlib.Path(discovery["reportPath"])
            summary_path = pathlib.Path(discovery["summaryPath"])
            self.assertTrue(report_path.is_file())
            self.assertTrue(summary_path.is_file())

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["schemaVersion"], "30.8.universal-discovery-report.1")
            self.assertIn("gameIdentity", report)
            self.assertIn("scanMetadata", report)
            self.assertIn("objectAndInteractionInventory", report)
            self.assertIn("playerProgressionRegistry", report)
            self.assertIn("discoveredGameplaySystems", report)
            self.assertIn("candidateActionOutcomeRelationships", report)
            self.assertIn("playerPositionHistory", report)
            self.assertIn("eventPositionSnapshots", report)
            self.assertIn("functionalLocationRegistry", report)
            self.assertIn("physicalDestinationRegistry", report)
            self.assertIn("destinationWorkflows", report)
            self.assertIn("spatialActionOutcomeRelationships", report)
            self.assertIn("locationNavigationCandidates", report)
            self.assertIn("navigationCandidates", report)
            self.assertIn("spatialDiscovery", report)
            self.assertIn("spatialDiscoveryQualityMetrics", report)
            self.assertIn("guiWorkflowGraph", report)
            self.assertIn("knownExecutableInteractionMechanisms", report)
            self.assertIn("uncertaintiesAndValidation", report)
            self.assertIn("qualityMetrics", report)
            self.assertIn("crossGameIsolation", report)
            self.assertGreater(len(report.get("candidateActionOutcomeRelationships") or []), 0)
            self.assertGreater(len(report.get("functionalLocationRegistry") or []), 0)
            self.assertGreater(len(report.get("eventPositionSnapshots") or []), 0)

            metadata = report["scanMetadata"]
            self.assertEqual((metadata.get("baselineArchiveValidation") or {}).get("receiverAcknowledgementGap"), 1)
            self.assertGreaterEqual((metadata.get("baselineContext") or {}).get("objectCount", 0), 1)

            locations = report.get("functionalLocationRegistry") or []
            self.assertTrue(any("relevantWorkspaceObjectPaths" in item for item in locations if isinstance(item, dict)))
            self.assertTrue(all("Workspace" not in set(item.get("relevantWorkspaceObjectPaths") or []) for item in locations if isinstance(item, dict)))
            self.assertTrue(any("requiredActivationConditions" in item for item in locations if isinstance(item, dict)))
            self.assertTrue(any(isinstance(item.get("physicalDestinationId"), str) for item in locations if isinstance(item, dict)))

            destinations = report.get("physicalDestinationRegistry") or []
            self.assertGreaterEqual(len(destinations), 1)
            self.assertTrue(all(isinstance(item.get("destinationId"), str) for item in destinations if isinstance(item, dict)))
            self.assertTrue(any(len(item.get("sourceLocationIds") or []) >= 1 for item in destinations if isinstance(item, dict)))
            self.assertTrue(any("navigationReadiness" in item for item in destinations if isinstance(item, dict)))
            self.assertTrue(any("gameplayOutcomeVerification" in item for item in destinations if isinstance(item, dict)))

            navigation = report.get("navigationCandidates") or []
            self.assertTrue(any("evidenceStatus" in item for item in navigation if isinstance(item, dict)))
            self.assertTrue(any("validationStatus" in item for item in navigation if isinstance(item, dict)))
            self.assertTrue(any("associatedWorkflowIds" in item for item in navigation if isinstance(item, dict)))
            self.assertTrue(any("gameplayOutcomeVerification" in item for item in navigation if isinstance(item, dict)))

            quality = report["qualityMetrics"]
            self.assertIn("distinctMechanicsIdentified", quality)
            self.assertIn("interactionCoverage", quality)
            self.assertIn("actionOutcomeRelationships", quality)
            self.assertIn("workflowCompleteness", quality)
            self.assertIn("spatialDiscovery", quality)
            spatial_quality = report["spatialDiscoveryQualityMetrics"]
            self.assertGreaterEqual((spatial_quality.get("eventPositionSnapshots") or {}).get("withCoordinates", 0), 1)
            self.assertIn("nearbyObjectRelevance", spatial_quality)
            self.assertIn("coverage", spatial_quality)
            self.assertIn("missingLocationEvidence", spatial_quality)

            summary_text = summary_path.read_text(encoding="utf-8")
            self.assertIn("Lycoles Universal Discovery Summary", summary_text)
            self.assertIn("Top discovered systems", summary_text)
            self.assertIn("Baseline archive integrity", summary_text)


    def test_navigation_readiness_rejects_pointer_only_location_without_targets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "pointer-only.json"
            make_pointer_only_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Discover location purpose",
                scenario_name="pointer-only",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))
            navigation = report.get("navigationCandidates") or []
            self.assertGreaterEqual(len(navigation), 1)
            first = navigation[0]
            self.assertFalse((first.get("evidenceStatus") or {}).get("actionableNavigationCandidate"))
            self.assertIn(first.get("validationStatus"), {"interaction-position", "observed-position", "outcome-associated-position"})
            blockers = first.get("readinessBlockers") or []
            self.assertTrue(any("No actionable target path" in item for item in blockers))

            clustering = (report.get("spatialDiscoveryQualityMetrics") or {}).get("locationClustering") or {}
            self.assertEqual(clustering.get("actionableNavigationCandidates"), 0)
            self.assertEqual(clustering.get("navigationCandidatesReady"), 0)

    def test_navigation_readiness_promotes_repeat_gui_flow_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "gui-repeat.json"
            make_gui_repeat_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Discover interaction destinations",
                scenario_name="gui-repeat",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))
            clustering = (report.get("spatialDiscoveryQualityMetrics") or {}).get("locationClustering") or {}
            self.assertGreaterEqual(clustering.get("actionableNavigationCandidates", 0), 1)
            self.assertGreaterEqual(clustering.get("navigationCandidatesReady", 0), 1)

            actionable = [
                item
                for item in (report.get("navigationCandidates") or [])
                if (item.get("validationStatus") or "") in {"actionable-navigation-candidate", "navigation-ready", "live-validated-destination"}
            ]
            self.assertGreaterEqual(len(actionable), 1)
            self.assertTrue(any(len(item.get("targetGuiPaths") or []) > 0 for item in actionable))
            self.assertTrue(all((item.get("evidenceStatus") or {}).get("liveValidatedDestination") is False for item in actionable))

    def test_multi_world_contexts_remain_separate_for_same_coordinates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "multi-world.json"
            make_multi_world_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Discover travel destinations",
                scenario_name="multi-world",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))
            locations = report.get("functionalLocationRegistry") or []
            self.assertEqual(len(locations), 2)

            world_identities = set()
            for location in locations:
                worlds = location.get("worldContexts") or []
                self.assertGreaterEqual(len(worlds), 1)
                world_identities.add(worlds[0])
            self.assertEqual(len(world_identities), 2)
            self.assertTrue(any((location.get("candidatePurpose") or "") in {"movement-and-navigation", "travel-or-teleport"} for location in locations))
            destinations = report.get("physicalDestinationRegistry") or []
            self.assertEqual(len(destinations), 2)
            self.assertEqual(len({item.get("destinationId") for item in destinations}), 2)

    def test_overlapping_locations_consolidate_to_single_physical_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "overlapping.json"
            make_overlapping_destination_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Discover shop workflows",
                scenario_name="overlapping-destinations",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))

            locations = report.get("functionalLocationRegistry") or []
            destinations = report.get("physicalDestinationRegistry") or []
            workflows = report.get("destinationWorkflows") or []
            navigation = report.get("navigationCandidates") or []

            self.assertGreaterEqual(len(locations), 2)
            self.assertEqual(len(destinations), 1)
            self.assertEqual(len(navigation), 1)

            destination = destinations[0]
            self.assertGreaterEqual(len(destination.get("sourceLocationIds") or []), 2)
            self.assertGreaterEqual(len(destination.get("associatedWorkflows") or []), 2)

            matching_workflows = [
                item for item in workflows
                if item.get("destinationId") == destination.get("destinationId")
            ]
            self.assertGreaterEqual(len(matching_workflows), 2)

            candidate = navigation[0]
            self.assertEqual(candidate.get("destinationId"), destination.get("destinationId"))
            self.assertGreaterEqual(len(candidate.get("associatedWorkflowIds") or []), 2)
            self.assertEqual((candidate.get("gameplayOutcomeVerification") or {}).get("status"), "unverified")

            clustering = ((report.get("spatialDiscoveryQualityMetrics") or {}).get("locationClustering") or {})
            self.assertEqual(clustering.get("functionalLocationCount"), len(locations))
            self.assertEqual(clustering.get("physicalDestinationCount"), 1)
            self.assertGreaterEqual(clustering.get("destinationMerges", 0), 1)
            self.assertGreaterEqual(clustering.get("destinationWorkflowCount", 0), 2)

    def test_nearby_unrelated_targets_remain_separate_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "nearby-unrelated.json"
            make_nearby_unrelated_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Discover nearby interaction destinations",
                scenario_name="nearby-unrelated",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))

            destinations = report.get("physicalDestinationRegistry") or []
            navigation = report.get("navigationCandidates") or []
            self.assertEqual(len(destinations), 2)
            self.assertEqual(len(navigation), 2)
            self.assertEqual(len({item.get("destinationId") for item in destinations}), 2)

            clustering = ((report.get("spatialDiscoveryQualityMetrics") or {}).get("locationClustering") or {})
            self.assertEqual(clustering.get("physicalDestinationCount"), 2)
            self.assertEqual(clustering.get("destinationMerges"), 0)

    def test_passive_state_changes_do_not_count_as_verified_outcomes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            overlay = root / "passive-outcome.json"
            make_pointer_only_observation_export(overlay)

            result = MODULE.run_universal_discovery_export(
                observation_path=overlay,
                output_root=root / "out",
                requested_capability="Assess interaction outcomes",
                scenario_name="passive-outcome",
            )
            report = json.loads(pathlib.Path(result["discovery"]["reportPath"]).read_text(encoding="utf-8"))

            destinations = report.get("physicalDestinationRegistry") or []
            self.assertGreaterEqual(len(destinations), 1)
            verification = (destinations[0].get("gameplayOutcomeVerification") or {})
            self.assertEqual(verification.get("status"), "unverified")
            self.assertFalse(verification.get("temporallyAssociated"))
            self.assertFalse(verification.get("multiSignalCorroborated"))
            self.assertTrue(any("No gameplay-relevant outcome signal observed" in item for item in (verification.get("missingEvidence") or [])))



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
            self.assertIn("discovery", result)
            self.assertTrue(pathlib.Path(result["discovery"]["reportPath"]).is_file())
            self.assertTrue(pathlib.Path(result["discovery"]["summaryPath"]).is_file())
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
            self.assertEqual(contract["schemaVersion"], "117.observation-tool-contract.6")
            self.assertEqual(summary["schemaVersion"], "117.observation-recovery-summary.6")
            self.assertTrue(pathlib.Path(summary["discoveryReportPath"]).is_file())
            self.assertTrue(pathlib.Path(summary["discoverySummaryPath"]).is_file())
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
            self.assertNotIn("auto_equip", contract["generatedFeatureIds"])
            self.assertNotIn("alternate_tool_training", contract["generatedFeatureIds"])

            feature_map = {item["id"]: item for item in contract["featureContracts"]}
            self.assertEqual(feature_map["auto_train"]["action"]["kind"], "tool_activate_selectable")
            training_methods = feature_map["auto_train"]["action"].get("methods") or []
            self.assertGreaterEqual(len(training_methods), 1)
            self.assertGreaterEqual(len(feature_map["auto_train"]["action"].get("defaultSelectedMethodIds") or []), 1)
            for method in training_methods:
                if "punch" in str(method.get("name", "")).lower() or "punch" in str(method.get("path", "")).lower():
                    self.assertFalse(method.get("defaultSelected"))
                if str(method.get("path", "")).lower().startswith("localplayer.input."):
                    self.assertFalse(method.get("safeByDefault"))
                    self.assertFalse(method.get("defaultSelected"))
            self.assertEqual(feature_map["auto_rewards"]["action"]["kind"], "auto_rewards_discovery")
            self.assertGreaterEqual(len(feature_map["auto_rewards"]["action"].get("rewardContainerPaths") or []), 1)
            self.assertGreaterEqual(len(feature_map["auto_rewards"]["action"].get("claimPaths") or []), 1)
            self.assertTrue(all(".claimed" not in str(path).lower() for path in (feature_map["auto_rewards"]["action"].get("paths") or [])))
            self.assertEqual(feature_map["quest_monitor"]["action"]["kind"], "observe_only")
            self.assertIn("quest completion/claim state deltas", feature_map["quest_monitor"]["evidence"].get("missingEvidence") or [])
            self.assertEqual(contract.get("featureDependencies", {}), {})
            self.assertIn("trainingDiscovery", contract)
            self.assertIn("inventoryMethods", contract["trainingDiscovery"])
            self.assertIn("worldStations", contract["trainingDiscovery"])
            self.assertIn("statRegistry", contract["trainingDiscovery"])
            self.assertIn("statTrainingTargets", contract["trainingDiscovery"])
            self.assertIn("actionStatEvidence", contract["trainingDiscovery"])

            stat_registry = (contract["trainingDiscovery"]["statRegistry"] or {}).get("stats") or []
            categories = {item.get("category") for item in stat_registry}
            self.assertIn("primary-progression", categories)
            self.assertIn("quest-progress", categories)

            self.assertGreaterEqual(len((contract["trainingDiscovery"]["statRegistry"] or {}).get("stats") or []), 1)
            self.assertGreaterEqual(len(contract["trainingDiscovery"].get("statTrainingTargets") or []), 1)
            self.assertGreaterEqual(len((contract["trainingDiscovery"].get("actionStatEvidence") or {}).get("relationships") or []), 1)

            auto_train_action = feature_map["auto_train"]["action"]
            self.assertIn("statTargets", auto_train_action)
            self.assertIn("methodStatMap", auto_train_action)
            self.assertGreaterEqual(len(auto_train_action.get("statTargets") or []), 1)
            self.assertGreaterEqual(len(auto_train_action.get("defaultSelectedMethodIds") or []), 1)

            self.assertEqual(summary["generatedScriptKind"], "observation-multi-feature-batch")
            self.assertGreaterEqual(summary.get("statRegistryCount", 0), 1)
            self.assertIn("quest_monitor", summary["monitoredFeatures"])
            self.assertNotIn("quest_monitor", summary["implementedFeatures"])
            self.assertIn("proximity_interactions", summary["excludedFeatures"])
            self.assertIn("world_training_stations", summary["excludedFeatures"])

            script_text = pathlib.Path(summary["generatedScriptPath"]).read_text(encoding="utf-8")
            self.assertIn("START ALL", script_text)
            self.assertIn("STOP ALL", script_text)
            self.assertIn("COPY REPORT", script_text)
            self.assertIn("MIN", script_text)
            self.assertIn("ARM", script_text)
            self.assertIn("tool_activate_selectable", script_text)
            self.assertIn("Stat targets and training methods:", script_text)
            self.assertIn("title.InputBegan", script_text)
            self.assertIn("runtimeCapabilities", script_text)
            self.assertIn("action-verified-in-gameplay", script_text)
            self.assertIn("firesignal", script_text)
            self.assertIn("unsupportedFeatures", script_text)
            self.assertIn("CharacterRemoving", script_text)
            self.assertIn("beginLifecycleRecovery", script_text)
            self.assertIn("recoveryAttempts", script_text)
            self.assertIn("no executable reward claim control; monitor-only fallback", script_text)
            self.assertIn("quest actionable controls unresolved; monitor-only fallback", script_text)


    def test_observation_contract_prefers_leaderstats_strength_as_primary_progression(self):
        payload = {
            "schemaVersion": "30.6.live-observation-export.1",
            "scanId": "scan-strength-priority",
            "placeId": 3623096087,
            "gameName": "Muscle Legends",
            "interactionDiagnostics": {
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
                            {"key": "LocalPlayer.leaderstats.Strength", "before": 1000, "after": 1001},
                            {"key": "LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress", "before": 40, "after": 52},
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
                            {"key": "LocalPlayer.leaderstats.Strength", "before": 1001, "after": 1002},
                            {"key": "LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress", "before": 52, "after": 65},
                        ],
                        "observationWindows": [{"seconds": 0.4}],
                    },
                ]
            },
        }

        contract = MODULE._build_observation_tool_contract(payload, "Automatically train strength")
        self.assertIsNotNone(contract)
        self.assertEqual((contract.get("outcomeModel") or {}).get("primaryStatePath"), "LocalPlayer.leaderstats.Strength")

        targets = ((contract.get("featureContracts") or [])[0].get("action") or {}).get("statTargets") or []
        targets_by_path = {item.get("path"): item for item in targets}
        self.assertTrue(targets_by_path["LocalPlayer.leaderstats.Strength"].get("defaultActive"))
        self.assertFalse(targets_by_path["LocalPlayer.Quests.Weekly Quests.Rep Titan.requirements.Reps.progress"].get("defaultActive"))



    def test_observation_contract_filters_non_actionable_quest_buttonlabel_paths(self):
        payload = {
            "schemaVersion": "30.6.live-observation-export.1",
            "scanId": "scan-quest-filter",
            "placeId": 3623096087,
            "gameName": "Muscle Legends",
            "objects": [
                {"path": "PlayerGui.questsGui.questsNewMenu.QuestsDaily.MainBase.Content.List.ScrollingFrame.DailyQuests.CollectButton.ButtonLabel"},
                {"path": "PlayerGui.questsGui.questsNewMenu.QuestsDaily.MainBase.Content.List.ScrollingFrame.DailyQuests.CollectButton"},
            ],
            "interactionDiagnostics": {
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
                            {"key": "LocalPlayer.leaderstats.Strength", "before": 100, "after": 110},
                        ],
                        "observationWindows": [{"seconds": 0.3}],
                    }
                ]
            },
        }

        contract = MODULE._build_observation_tool_contract(payload, "Open quest interface")
        self.assertIsNotNone(contract)
        feature_map = {item["id"]: item for item in contract.get("featureContracts") or []}
        self.assertIn("quest_interface", feature_map)
        paths = (feature_map["quest_interface"]["action"] or {}).get("paths") or []
        self.assertTrue(any("collectbutton" in str(path).lower() for path in paths))
        self.assertTrue(all("buttonlabel" not in str(path).lower() for path in paths))


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
