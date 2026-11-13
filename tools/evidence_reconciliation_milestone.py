#!/usr/bin/env python3
"""Milestone 2 evidence reconciliation and capability feasibility pipeline.

Produces reusable, machine-readable outputs:
- evidence-reconciliation-report.json
- capability-evidence-contracts.json
- reassessed-feature-feasibility.json
- targeted-inspection-plan.json
- game-understanding-improvements.json
- generation-integration-report.json
- milestone-2-summary.md

The pipeline is read-only, evidence-bounded, and keeps verification claims false
until explicit runtime/gameplay evidence is provided.
"""

from __future__ import annotations

import argparse
import collections
import importlib.util
import json
import pathlib
import re
from dataclasses import dataclass
from typing import Any, Optional

SCHEMA_RECONCILIATION = "121.evidence-reconciliation-report.1"
SCHEMA_CONTRACTS = "121.capability-evidence-contracts.1"
SCHEMA_FEASIBILITY = "121.reassessed-feature-feasibility.1"
SCHEMA_INSPECTION_PLAN = "121.targeted-inspection-plan.1"
SCHEMA_UNDERSTANDING = "121.game-understanding-improvements.1"
SCHEMA_INTEGRATION = "121.generation-integration-report.1"

MAX_FILE_BYTES = 35_000_000

FALSE_CLAIMS = {
    "sourceAuthenticityVerified": False,
    "causalityProven": False,
    "serverAuthorityVerified": False,
    "runtimeVerified": False,
    "gameplayVerified": False,
    "actionOutcomesVerified": False,
}


def _load_local_module(name: str, filename: str):
    source = pathlib.Path(__file__).resolve().parent / filename
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COMPILE_SCAN = _load_local_module("compile_scan", "compile_scan.py")
UNDERSTAND_GAMEPLAY = _load_local_module("understand_gameplay", "understand_gameplay.py")
UNIVERSAL_INTELLIGENCE = _load_local_module("universal_gameplay_intelligence", "universal_gameplay_intelligence.py")


def _safe_json(path: pathlib.Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"JSON exceeds size limit: {path}")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _tokenize(text: str) -> set[str]:
    return {item.casefold() for item in re.findall(r"[^\W_]+", text, flags=re.UNICODE)}


@dataclass
class RequirementResult:
    requirement_id: str
    status: str
    available: bool
    rationale: str
    provenance: list[str]


def _counter_from_history(history: list[dict[str, Any]], key: str) -> collections.Counter[str]:
    counter: collections.Counter[str] = collections.Counter()
    for item in history:
        value = item.get(key)
        if isinstance(value, str) and value:
            counter[value] += 1
    return counter


def _extract_observation_paths(observation: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for item in observation.get("clickTargetObservations") or []:
        if not isinstance(item, dict):
            continue
        target_path = item.get("targetPath")
        if isinstance(target_path, str) and target_path:
            paths.append(target_path)
        for gui in item.get("guiCandidates") or []:
            if isinstance(gui, dict) and isinstance(gui.get("path"), str) and gui["path"]:
                paths.append(gui["path"])
    return paths


def _extract_targeted_sessions(observation_payloads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sessions: list[dict[str, Any]] = []
    for payload in observation_payloads:
        if not isinstance(payload, dict):
            continue
        if payload.get("schemaVersion") == "31.0.targeted-evidence-session.1" or payload.get("exportKind") == "targeted-evidence-session":
            sessions.append(payload)
            continue
        embedded = payload.get("targetedCaptureSession")
        if isinstance(embedded, dict):
            sessions.append(embedded)
        nested = payload.get("targetedCapture")
        if isinstance(nested, dict):
            sessions.append(nested)
    return sessions


def _aggregate_targeted_signals(targeted_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    aggregate = {
        "cameraSamples": 0,
        "cameraCorrelations": 0,
        "entitySnapshots": 0,
        "nonLocalEntities": 0,
        "teamSignals": 0,
        "weaponSnapshots": 0,
        "loadoutSnapshots": 0,
        "loadoutToolSignals": 0,
        "matchStateSamples": 0,
        "objectiveSignals": 0,
        "objectiveTransitions": 0,
        "stateTransitions": 0,
        "inputSamples": 0,
        "primaryInputEvents": 0,
        "hudWeaponIndicators": 0,
    }
    gui_paths: list[str] = []
    for session in targeted_sessions:
        samples = session.get("samples") if isinstance(session.get("samples"), dict) else {}
        aggregate["cameraSamples"] += len(samples.get("cameraSamples") or [])
        aggregate["cameraCorrelations"] += len(samples.get("cameraCorrelations") or [])
        entities = [item for item in (samples.get("characterEntities") or []) if isinstance(item, dict)]
        aggregate["entitySnapshots"] += len(entities)
        aggregate["nonLocalEntities"] += sum(1 for item in entities if item.get("isLocalPlayer") is False)
        aggregate["teamSignals"] += sum(1 for item in entities if isinstance(item.get("team"), str) and item.get("team"))
        loadout_samples = [item for item in (samples.get("loadoutSnapshots") or []) if isinstance(item, dict)]
        aggregate["loadoutSnapshots"] += len(loadout_samples)
        for item in loadout_samples:
            aggregate["loadoutToolSignals"] += len(item.get("equippedTools") or []) + len(item.get("backpackTools") or [])
            for path in item.get("hudWeaponIndicatorPaths") or []:
                if isinstance(path, str):
                    gui_paths.append(path)
        aggregate["weaponSnapshots"] += len(samples.get("weaponSnapshots") or [])
        match_samples = [item for item in (samples.get("matchStateSamples") or []) if isinstance(item, dict)]
        aggregate["matchStateSamples"] += len(match_samples)
        for item in match_samples:
            signals = item.get("signals") if isinstance(item.get("signals"), dict) else {}
            aggregate["objectiveSignals"] += len(signals)
            for path in signals.keys():
                if isinstance(path, str):
                    gui_paths.append(path)
        transitions = [item for item in (samples.get("transitions") or []) if isinstance(item, dict)]
        aggregate["objectiveTransitions"] += len(transitions)
        aggregate["stateTransitions"] += len(transitions)
        input_samples = [item for item in (samples.get("inputSamples") or []) if isinstance(item, dict)]
        aggregate["inputSamples"] += len(input_samples)
        aggregate["primaryInputEvents"] += sum(int(item.get("mousePrimaryInputs") or 0) for item in input_samples)
        aggregate["hudWeaponIndicators"] += sum(len(item.get("hudWeaponIndicators") or []) for item in loadout_samples)
    aggregate["guiPaths"] = gui_paths
    return aggregate


def _extract_evidence_signals(
    plan: dict[str, Any],
    observation: Optional[dict[str, Any]],
    targeted_sessions: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    history = [item for item in plan.get("observedInteractionHistory") or [] if isinstance(item, dict)]
    class_counts = plan.get("classCounts") if isinstance(plan.get("classCounts"), dict) else {}
    feature_summary = [item for item in plan.get("features") or [] if isinstance(item, dict)]
    discovery = plan.get("universalDiscovery") if isinstance(plan.get("universalDiscovery"), dict) else {}

    control_counts = _counter_from_history(history, "controlType")
    action_counts = _counter_from_history(history, "actionKind")
    feature_counts = _counter_from_history(history, "featureCandidate")

    state_keys: collections.Counter[str] = collections.Counter()
    path_tokens_counter: collections.Counter[str] = collections.Counter()
    history_paths: list[str] = []
    for event in history:
        path = event.get("path")
        if isinstance(path, str):
            history_paths.append(path)
            for token in _tokenize(path):
                path_tokens_counter[token] += 1
        for change in event.get("stateChanges") or []:
            if isinstance(change, dict) and isinstance(change.get("key"), str):
                state_keys[change["key"]] += 1

    observation_paths = []
    if isinstance(observation, dict):
        observation_paths = _extract_observation_paths(observation)
        for path in observation_paths:
            for token in _tokenize(path):
                path_tokens_counter[token] += 1

    targeted = _aggregate_targeted_signals(targeted_sessions or [])
    for path in targeted.get("guiPaths", []):
        if isinstance(path, str):
            for token in _tokenize(path):
                path_tokens_counter[token] += 1

    gesture_records = [item for item in (observation or {}).get("inputGestureObservations") or [] if isinstance(item, dict)]
    camera_turn_gestures = 0
    likely_camera_gestures = 0
    right_button_gestures = 0
    for gesture in gesture_records:
        intent = gesture.get("intent") if isinstance(gesture.get("intent"), dict) else {}
        physical = intent.get("physicalGesture") if isinstance(intent.get("physicalGesture"), dict) else {}
        signals = intent.get("inputContextSignals") if isinstance(intent.get("inputContextSignals"), dict) else {}
        turn = physical.get("cameraTurnDegrees")
        if isinstance(turn, (int, float)) and abs(turn) > 0:
            camera_turn_gestures += 1
        if intent.get("likelyCameraMovement") is True:
            likely_camera_gestures += 1
        if signals.get("rightButtonInput") is True:
            right_button_gestures += 1

    click_outcomes = [item for item in (observation or {}).get("clickOutcomeRelationships") or [] if isinstance(item, dict)]
    world_target_outcomes = sum(1 for item in click_outcomes if isinstance(item.get("provenance"), dict) and item["provenance"].get("targetScope") == "world")
    corroborated_click_outcomes = sum(1 for item in click_outcomes if item.get("outcomeCorroborated") is True)

    camera_state_samples = len((observation or {}).get("cameraOrientationSamples") or []) + int(targeted.get("cameraSamples") or 0)
    player_position_samples = len((observation or {}).get("playerPositionHistory") or []) + int(targeted.get("entitySnapshots") or 0)
    event_position_snapshots = len((observation or {}).get("eventPositionSnapshots") or []) + int(targeted.get("cameraCorrelations") or 0)

    ammo_signal_count = sum(count for key, count in state_keys.items() if any(token in key.casefold() for token in ("ammo", "mag", "bullet", "reload")))
    health_signal_count = sum(count for key, count in state_keys.items() if any(token in key.casefold() for token in ("health", "hp", "damage")))
    objective_signal_count = sum(count for key, count in state_keys.items() if any(token in key.casefold() for token in ("score", "objective", "timer", "round", "capture")))
    objective_signal_count += int(targeted.get("objectiveSignals") or 0)
    objective_signal_count += int(targeted.get("objectiveTransitions") or 0)

    return {
        "scan": {
            "scanId": (plan.get("integrity") or {}).get("scanId") if isinstance(plan.get("integrity"), dict) else None,
            "placeId": (plan.get("integrity") or {}).get("placeId") if isinstance(plan.get("integrity"), dict) else None,
            "interactionEvents": int((plan.get("integrity") or {}).get("interactionEvents") or len(history)) if isinstance(plan.get("integrity"), dict) else len(history),
            "objects": int((plan.get("integrity") or {}).get("objects") or 0) if isinstance(plan.get("integrity"), dict) else 0,
        },
        "classCounts": class_counts,
        "controlTypeCounts": dict(control_counts),
        "actionCounts": dict(action_counts),
        "featureCounts": dict(feature_counts),
        "featureSummary": feature_summary,
        "stateChangeKeys": dict(state_keys),
        "stateChangeTotal": sum(state_keys.values()),
        "pathTokenCounts": dict(path_tokens_counter),
        "historyPaths": history_paths,
        "observationPaths": observation_paths,
        "camera": {
            "inputGestureCount": len(gesture_records) + int(targeted.get("inputSamples") or 0),
            "rightButtonGestureCount": right_button_gestures,
            "cameraTurnGestureCount": camera_turn_gestures,
            "likelyCameraMovementGestureCount": likely_camera_gestures + int(targeted.get("cameraCorrelations") or 0),
            "cameraStateSampleCount": camera_state_samples,
            "worldTargetOutcomeCount": world_target_outcomes,
            "corroboratedOutcomeCount": corroborated_click_outcomes,
            "verifiedCameraResponseBehavior": False,
        },
        "movement": {
            "playerPositionSampleCount": player_position_samples,
            "eventPositionSnapshotCount": event_position_snapshots,
            "movementActionCount": int(action_counts.get("sprint", 0) + action_counts.get("jump", 0)),
        },
        "combat": {
            "mousePrimaryInputCount": int(control_counts.get("InputBegan.MouseButton1", 0)) + int(targeted.get("primaryInputEvents") or 0),
            "mouseSecondaryInputCount": int(control_counts.get("InputBegan.MouseButton2", 0)),
            "weaponToolClassCount": max(int(class_counts.get("Tool") or 0), 1 if int(targeted.get("loadoutToolSignals") or 0) > 0 else 0),
            "weaponStateSignalCount": int(ammo_signal_count) + int(targeted.get("stateTransitions") or 0),
            "healthSignalCount": int(health_signal_count),
        },
        "entities": {
            "humanoidCount": max(int(class_counts.get("Humanoid") or 0), 1 if int(targeted.get("entitySnapshots") or 0) > 0 else 0),
            "teamCount": max(int(class_counts.get("Team") or 0) + int(class_counts.get("Teams") or 0), int(targeted.get("teamSignals") or 0)),
            "playerCount": max(int(class_counts.get("Player") or 0) + int(class_counts.get("Players") or 0), int(targeted.get("nonLocalEntities") or 0) + 1),
        },
        "objectives": {
            "objectiveSignalCount": int(objective_signal_count),
        },
        "world": {
            "regionCount": len(discovery.get("regions") or []),
            "interactableCount": len(discovery.get("interactables") or []),
            "mapGeometryCount": int(class_counts.get("Part") or 0) + int(class_counts.get("MeshPart") or 0) + int(class_counts.get("UnionOperation") or 0),
        },
    }


def _requirement_definitions() -> dict[str, dict[str, Any]]:
    return {
        "mouse_primary_input": {"kind": "observation", "description": "Primary mouse input events observed"},
        "input_control_types": {"kind": "observation", "description": "Input/control type distribution available"},
        "camera_state_samples": {"kind": "observation", "description": "Raw camera orientation state samples"},
        "camera_rotation_gesture": {"kind": "observation", "description": "Camera-turn gestures observed from input intent metrics"},
        "camera_movement_correlation": {"kind": "temporal", "description": "Temporal relation between camera movement and combat-relevant events"},
        "weapon_equipped_signal": {"kind": "entity", "description": "Equipped weapon/tool evidence"},
        "weapon_state_signal": {"kind": "state", "description": "Weapon/ammo/reload state-change evidence"},
        "state_change_signals": {"kind": "state", "description": "General state change keys available"},
        "player_entity_set": {"kind": "entity", "description": "Non-local player entity set available"},
        "team_relationship_signal": {"kind": "entity", "description": "Team relationship evidence available"},
        "character_spatial_positions": {"kind": "observation", "description": "Character/player spatial samples"},
        "visibility_signal": {"kind": "observation", "description": "Occlusion/visibility evidence"},
        "world_regions": {"kind": "world", "description": "World region clustering available"},
        "map_geometry": {"kind": "world", "description": "Map geometry density available"},
        "loadout_gui_structures": {"kind": "gui", "description": "Loadout/weapon GUI structures observed"},
        "hud_weapon_indicators": {"kind": "gui", "description": "HUD weapon indicators observed"},
        "movement_position_samples": {"kind": "observation", "description": "Player position samples available"},
        "movement_actions": {"kind": "observation", "description": "Movement actions (sprint/jump) observed"},
        "objective_hud_signals": {"kind": "gui", "description": "Objective/timer/score HUD signals"},
        "feature_summary": {"kind": "summary", "description": "Feature summary evidence available"},
    }


def _evaluate_requirement(requirement_id: str, signals: dict[str, Any]) -> RequirementResult:
    camera = signals["camera"]
    combat = signals["combat"]
    entities = signals["entities"]
    movement = signals["movement"]
    world = signals["world"]
    tokens = signals["pathTokenCounts"]
    objective_signals = signals["objectives"]["objectiveSignalCount"]

    def available(reason: str, provenance: list[str]) -> RequirementResult:
        return RequirementResult(requirement_id, "available", True, reason, provenance)

    def captured_not_extracted(reason: str, provenance: list[str]) -> RequirementResult:
        return RequirementResult(requirement_id, "captured-not-extracted", False, reason, provenance)

    def captured_not_classified(reason: str, provenance: list[str]) -> RequirementResult:
        return RequirementResult(requirement_id, "captured-not-classified", False, reason, provenance)

    def missing(reason: str, provenance: list[str]) -> RequirementResult:
        return RequirementResult(requirement_id, "missing", False, reason, provenance)

    if requirement_id == "mouse_primary_input":
        count = combat["mousePrimaryInputCount"]
        if count > 0:
            return available(f"{count} primary mouse input events observed.", ["plan.observedInteractionHistory.controlType"])
        return missing("No primary mouse input events observed.", ["plan.observedInteractionHistory.controlType"])

    if requirement_id == "input_control_types":
        if signals["controlTypeCounts"]:
            return available("Control type distribution is present.", ["plan.observedInteractionHistory.controlType"])
        return missing("No control type distribution available.", ["plan.observedInteractionHistory.controlType"])

    if requirement_id == "camera_state_samples":
        count = camera["cameraStateSampleCount"]
        if count > 0:
            return available(f"{count} camera orientation samples captured.", ["observation.cameraOrientationSamples"])
        if camera["cameraTurnGestureCount"] > 0:
            return captured_not_extracted(
                "Camera turn evidence exists via gestures, but raw camera state sample stream is empty.",
                ["observation.inputGestureObservations.intent.physicalGesture.cameraTurnDegrees",
                 "observation.cameraOrientationSamples"],
            )
        return missing("No camera state samples available.", ["observation.cameraOrientationSamples"])

    if requirement_id == "camera_rotation_gesture":
        count = camera["cameraTurnGestureCount"]
        if count > 0:
            return available(f"{count} gestures include non-zero camera turn evidence.",
                             ["observation.inputGestureObservations.intent.physicalGesture.cameraTurnDegrees"])
        return missing("No gestures with camera-turn evidence.",
                       ["observation.inputGestureObservations.intent.physicalGesture.cameraTurnDegrees"])

    if requirement_id == "camera_movement_correlation":
        if camera["cameraTurnGestureCount"] > 0 and combat["mousePrimaryInputCount"] > 0:
            if combat["weaponStateSignalCount"] > 0 or signals["stateChangeTotal"] > 0:
                return available("Camera movement and combat inputs have temporal candidates with state support.", [
                    "observation.inputGestureObservations",
                    "plan.observedInteractionHistory",
                ])
            return captured_not_classified(
                "Camera movement and combat input are co-observed, but no validating state transitions were classified.",
                ["observation.inputGestureObservations", "plan.observedInteractionHistory", "plan.stateChanges"],
            )
        return missing("Insufficient camera/combat overlap for temporal correlation.", ["observation.inputGestureObservations"])

    if requirement_id == "weapon_equipped_signal":
        if combat["weaponToolClassCount"] > 0:
            return available("Tool class evidence indicates weapon/tool entities are present.", ["plan.classCounts.Tool"])
        if tokens.get("weapon", 0) > 0 or tokens.get("loadout", 0) > 0:
            return captured_not_classified(
                "Weapon/loadout GUI references captured but no direct tool entity evidence in baseline classes.",
                ["observation.clickTargetObservations.guiCandidates.path", "plan.classCounts.Tool"],
            )
        return missing("No direct weapon/tool entity evidence.", ["plan.classCounts.Tool"])

    if requirement_id == "weapon_state_signal":
        count = combat["weaponStateSignalCount"]
        if count > 0:
            return available(f"{count} weapon-related state changes observed.", ["plan.observedInteractionHistory.stateChanges"])
        if combat["mousePrimaryInputCount"] > 0:
            return captured_not_classified(
                "Primary firing-like input exists but no weapon-state transitions were captured/classified.",
                ["plan.observedInteractionHistory.controlType", "plan.observedInteractionHistory.stateChanges"],
            )
        return missing("No weapon-state signal evidence.", ["plan.observedInteractionHistory.stateChanges"])

    if requirement_id == "state_change_signals":
        count = signals["stateChangeTotal"]
        if count > 0:
            return available(f"{count} state changes captured.", ["plan.observedInteractionHistory.stateChanges"])
        return missing("No state-change signals were captured.", ["plan.observedInteractionHistory.stateChanges"])

    if requirement_id == "player_entity_set":
        player_count = entities["playerCount"]
        humanoids = entities["humanoidCount"]
        if player_count >= 2 or humanoids >= 2:
            return available("Multiple player/character entities observed.", ["plan.classCounts.Player", "plan.classCounts.Humanoid"])
        if player_count >= 1 or humanoids >= 1:
            return captured_not_classified(
                "Only local/single character entity observed; opponent set is unconfirmed.",
                ["plan.classCounts.Player", "plan.classCounts.Humanoid"],
            )
        return missing("No player/character entity set evidence.", ["plan.classCounts.Player", "plan.classCounts.Humanoid"])

    if requirement_id == "team_relationship_signal":
        count = entities["teamCount"]
        if count >= 2:
            return available("Team relationship entities observed.", ["plan.classCounts.Team", "plan.classCounts.Teams"])
        if count == 1:
            return captured_not_classified("Single team signal observed without relationship coverage.", ["plan.classCounts.Team"])
        return missing("No team relationship evidence.", ["plan.classCounts.Team", "plan.classCounts.Teams"])

    if requirement_id == "character_spatial_positions":
        if movement["playerPositionSampleCount"] > 0:
            return available(
                f"{movement['playerPositionSampleCount']} player position samples observed.",
                ["observation.playerPositionHistory"],
            )
        if movement["eventPositionSnapshotCount"] > 0:
            return captured_not_extracted(
                "Event position snapshots exist but continuous player-position stream is missing.",
                ["observation.eventPositionSnapshots", "observation.playerPositionHistory"],
            )
        return missing("No character spatial sampling evidence.", ["observation.playerPositionHistory"])

    if requirement_id == "visibility_signal":
        if camera["corroboratedOutcomeCount"] > 0:
            return captured_not_classified(
                "Corroborated click outcome exists, but explicit visibility/occlusion classification is absent.",
                ["observation.clickOutcomeRelationships.outcomeCorroborated"],
            )
        return missing("No visibility/occlusion signal evidence.", ["observation.clickOutcomeRelationships"])

    if requirement_id == "world_regions":
        count = world["regionCount"]
        if count > 0:
            return available(f"{count} world regions discovered.", ["plan.universalDiscovery.regions"])
        return missing("No world region evidence.", ["plan.universalDiscovery.regions"])

    if requirement_id == "map_geometry":
        count = world["mapGeometryCount"]
        if count > 500:
            return available("Dense map geometry evidence is available.", ["plan.classCounts.Part", "plan.classCounts.MeshPart", "plan.classCounts.UnionOperation"])
        if count > 0:
            return captured_not_classified("Map geometry exists but density is low for navigation helpers.", ["plan.classCounts"])
        return missing("No map geometry evidence.", ["plan.classCounts"])

    if requirement_id == "loadout_gui_structures":
        if tokens.get("loadout", 0) > 0 or tokens.get("weapon", 0) > 0:
            return available("Loadout/weapon GUI paths were observed.", ["observation.clickTargetObservations.guiCandidates.path"])
        return missing("No loadout/weapon GUI structures observed.", ["observation.clickTargetObservations.guiCandidates.path"])

    if requirement_id == "hud_weapon_indicators":
        if tokens.get("hud", 0) > 0 and tokens.get("weapon", 0) > 0:
            return available("HUD and weapon-related paths co-occur in observed GUI structures.", ["observation.clickTargetObservations.guiCandidates.path"])
        if tokens.get("hud", 0) > 0:
            return captured_not_classified("HUD paths observed but weapon indicators were not confidently classified.", ["observation.clickTargetObservations.guiCandidates.path"])
        return missing("No HUD weapon indicator evidence.", ["observation.clickTargetObservations.guiCandidates.path"])

    if requirement_id == "movement_position_samples":
        if movement["playerPositionSampleCount"] > 0:
            return available("Player position samples are available.", ["observation.playerPositionHistory"])
        return missing("No player position samples.", ["observation.playerPositionHistory"])

    if requirement_id == "movement_actions":
        if movement["movementActionCount"] > 0:
            return available("Movement actions (sprint/jump) were observed.", ["plan.observedInteractionHistory.actionKind"])
        return missing("No movement actions observed.", ["plan.observedInteractionHistory.actionKind"])

    if requirement_id == "objective_hud_signals":
        if objective_signals > 0:
            return available("Objective/timer/score state signals were observed.", ["plan.observedInteractionHistory.stateChanges"])
        if tokens.get("score", 0) > 0 or tokens.get("objective", 0) > 0 or tokens.get("timer", 0) > 0:
            return captured_not_classified(
                "GUI objective-like tokens exist but no dynamic objective state transitions were captured.",
                ["observation.clickTargetObservations.guiCandidates.path", "plan.observedInteractionHistory.stateChanges"],
            )
        return missing("No objective/timer/score evidence.", ["plan.observedInteractionHistory.stateChanges"])

    if requirement_id == "feature_summary":
        if signals["featureSummary"]:
            return available("Feature summary entries are present.", ["plan.features"])
        return missing("Feature summary is missing.", ["plan.features"])

    return missing("Unknown requirement.", ["internal"])


def _capability_specs() -> list[dict[str, Any]]:
    return [
        {
            "featureId": "combat_recoil_assist",
            "featureTitle": "Recoil Assistance",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "combat_recoil_assist.recoil_camera_compensation",
                    "name": "Camera recoil compensation",
                    "description": "Estimate recoil direction from firing cadence and camera deltas, then apply bounded camera compensation.",
                    "implementationMethod": "client camera delta sampler with fire-correlation guardrails",
                    "requiredRequirements": [
                        "mouse_primary_input",
                        "camera_state_samples",
                        "weapon_equipped_signal",
                        "weapon_state_signal",
                        "camera_movement_correlation",
                    ],
                    "optionalRequirements": ["camera_rotation_gesture"],
                    "requiredTemporalRelationships": [
                        "camera movement must co-occur with firing windows",
                        "non-firing camera movement must be separable",
                    ],
                    "implementationDependencies": ["camera-control runtime adapter", "weapon-state classifier"],
                    "verificationRequirements": ["reduced recoil drift in controlled burst test"],
                }
            ],
        },
        {
            "featureId": "combat_target_assist",
            "featureTitle": "Target Assistance",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "combat_target_assist.target_candidate_selection",
                    "name": "Target candidate selection",
                    "description": "Select candidate entities for aim assist using character positions and team relationships.",
                    "implementationMethod": "entity tracker + team filter + camera projection",
                    "requiredRequirements": [
                        "player_entity_set",
                        "character_spatial_positions",
                        "team_relationship_signal",
                        "input_control_types",
                    ],
                    "optionalRequirements": ["visibility_signal"],
                    "requiredTemporalRelationships": ["candidate updates synchronized with render step"],
                    "implementationDependencies": ["entity-index adapter", "projection adapter"],
                    "verificationRequirements": ["stable candidate lock under movement"],
                }
            ],
        },
        {
            "featureId": "combat_trigger_assist",
            "featureTitle": "Trigger Assistance",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "combat_trigger_assist.crosshair_fire_condition",
                    "name": "Crosshair fire condition",
                    "description": "Trigger fire condition only when validated target criteria are met.",
                    "implementationMethod": "crosshair overlap predicate with cooldown and team checks",
                    "requiredRequirements": [
                        "mouse_primary_input",
                        "player_entity_set",
                        "weapon_equipped_signal",
                        "weapon_state_signal",
                        "state_change_signals",
                    ],
                    "optionalRequirements": ["visibility_signal"],
                    "requiredTemporalRelationships": ["trigger decisions aligned with frame updates"],
                    "implementationDependencies": ["fire-control adapter", "target classifier"],
                    "verificationRequirements": ["validated trigger condition logs without false positives"],
                }
            ],
        },
        {
            "featureId": "esp_player_overlay",
            "featureTitle": "Player Awareness Overlay",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "esp_player_overlay.basic_entity_boxes",
                    "name": "Basic player boxes",
                    "description": "Render player box overlays for visible character entities.",
                    "implementationMethod": "runtime character enumeration + camera projection + box rendering",
                    "requiredRequirements": ["player_entity_set", "character_spatial_positions"],
                    "optionalRequirements": ["team_relationship_signal", "visibility_signal"],
                    "requiredTemporalRelationships": ["entity projection updates each render frame"],
                    "implementationDependencies": ["drawing adapter", "projection adapter"],
                    "verificationRequirements": ["overlay tracks moving entities in live match"],
                },
                {
                    "capabilityId": "esp_player_overlay.team_and_health_enhancements",
                    "name": "Team/health enhancements",
                    "description": "Add team coloring and health bars when team/health data is available.",
                    "implementationMethod": "entity metadata layering over basic overlay",
                    "requiredRequirements": ["player_entity_set", "team_relationship_signal", "state_change_signals"],
                    "optionalRequirements": ["visibility_signal"],
                    "requiredTemporalRelationships": ["metadata refresh under player updates"],
                    "implementationDependencies": ["health value resolver", "team-color map"],
                    "verificationRequirements": ["correct team coloring and health updates"],
                },
            ],
        },
        {
            "featureId": "loadout_information_suite",
            "featureTitle": "Loadout and Weapon Intelligence",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "loadout_information_suite.loadout_gui_reader",
                    "name": "Loadout GUI reader",
                    "description": "Extract current loadout/menu weapon selection signals from observed GUI structures.",
                    "implementationMethod": "GUI path resolver and normalized value presenter",
                    "requiredRequirements": ["loadout_gui_structures", "feature_summary"],
                    "optionalRequirements": ["hud_weapon_indicators"],
                    "requiredTemporalRelationships": ["refresh on GUI visibility/state changes"],
                    "implementationDependencies": ["gui-snapshot parser", "schema normalizer"],
                    "verificationRequirements": ["menu selection changes reflected in overlay"],
                },
                {
                    "capabilityId": "loadout_information_suite.runtime_weapon_state",
                    "name": "Runtime weapon state indicators",
                    "description": "Display equipped weapon and dynamic weapon-state indicators in gameplay HUD.",
                    "implementationMethod": "runtime tool/HUD state merger",
                    "requiredRequirements": ["weapon_equipped_signal", "hud_weapon_indicators"],
                    "optionalRequirements": ["weapon_state_signal"],
                    "requiredTemporalRelationships": ["weapon switch updates propagated to display"],
                    "implementationDependencies": ["tool identity resolver"],
                    "verificationRequirements": ["equipped weapon updates during switching"],
                },
            ],
        },
        {
            "featureId": "movement_navigation_assist",
            "featureTitle": "Navigation Assistance",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "movement_navigation_assist.movement_telemetry_overlay",
                    "name": "Movement telemetry overlay",
                    "description": "Track local movement vectors, jump/sprint activity, and trajectory hints.",
                    "implementationMethod": "local position history sampling + movement action markers",
                    "requiredRequirements": ["movement_position_samples", "movement_actions"],
                    "optionalRequirements": ["camera_rotation_gesture"],
                    "requiredTemporalRelationships": ["position sampling must be time-ordered"],
                    "implementationDependencies": ["local-character position sampler", "lightweight drawing adapter"],
                    "verificationRequirements": ["trajectory and movement state update during traversal"],
                },
                {
                    "capabilityId": "movement_navigation_assist.path_hinting",
                    "name": "Path hinting",
                    "description": "Suggest path hints based on world regions and map geometry.",
                    "implementationMethod": "region graph approximation with obstacle-aware hints",
                    "requiredRequirements": ["world_regions", "map_geometry", "character_spatial_positions"],
                    "optionalRequirements": ["camera_state_samples"],
                    "requiredTemporalRelationships": ["hints update with location changes"],
                    "implementationDependencies": ["region graph builder"],
                    "verificationRequirements": ["hints remain stable across movement"],
                },
            ],
        },
        {
            "featureId": "objective_status_dashboard",
            "featureTitle": "Objective and Match Status Dashboard",
            "featureType": "gameplay",
            "capabilities": [
                {
                    "capabilityId": "objective_status_dashboard.reactive_match_reader",
                    "name": "Reactive match reader",
                    "description": "Track objective/timer/score transitions and surface match-state changes.",
                    "implementationMethod": "HUD/state watcher with transition timeline",
                    "requiredRequirements": ["objective_hud_signals", "feature_summary"],
                    "optionalRequirements": ["state_change_signals"],
                    "requiredTemporalRelationships": ["objective values must change over time"],
                    "implementationDependencies": ["objective field mapper"],
                    "verificationRequirements": ["state transitions detected across match phases"],
                }
            ],
        },
        {
            "featureId": "profile_and_keybind_manager",
            "featureTitle": "Profiles and Keybinds",
            "featureType": "infrastructure",
            "capabilities": [
                {
                    "capabilityId": "profile_and_keybind_manager.profile_persistence",
                    "name": "Profile persistence",
                    "description": "Persist keybind/settings profiles for enabled gameplay features.",
                    "implementationMethod": "schema-validated config persistence",
                    "requiredRequirements": ["feature_summary"],
                    "optionalRequirements": [],
                    "requiredTemporalRelationships": [],
                    "implementationDependencies": ["config persistence backend"],
                    "verificationRequirements": ["profile save/load consistency"],
                }
            ],
        },
    ]


def _stage_from_requirements(requirements: list[RequirementResult], dependencies_missing: list[str]) -> str:
    if all(item.available for item in requirements):
        if dependencies_missing:
            return "Evidence sufficient for a bounded implementation"
        return "Implementation dependencies satisfied"
    if any(item.available for item in requirements):
        return "Evidence partially available"
    return "Concept proposed"


def _lifecycle_flags(stage: str) -> dict[str, bool]:
    ordered = [
        "Concept proposed",
        "Evidence partially available",
        "Evidence sufficient for a bounded implementation",
        "Implementation dependencies satisfied",
        "Implementation ready",
        "Implemented",
        "Static validation passed",
        "Runtime tested",
        "Gameplay verified",
    ]
    reached = set()
    for item in ordered:
        reached.add(item)
        if item == stage:
            break
    return {name: (name in reached) for name in ordered}


def _build_capability_contracts(signals: dict[str, Any]) -> dict[str, Any]:
    definitions = _requirement_definitions()
    features = []
    req_index: dict[str, RequirementResult] = {}

    for spec in _capability_specs():
        capability_entries = []
        feature_stage_rank = -1
        stage_order = [
            "Concept proposed",
            "Evidence partially available",
            "Evidence sufficient for a bounded implementation",
            "Implementation dependencies satisfied",
            "Implementation ready",
            "Implemented",
            "Static validation passed",
            "Runtime tested",
            "Gameplay verified",
        ]

        for capability in spec["capabilities"]:
            required = [_evaluate_requirement(req_id, signals) for req_id in capability["requiredRequirements"]]
            optional = [_evaluate_requirement(req_id, signals) for req_id in capability.get("optionalRequirements", [])]

            for item in required + optional:
                req_index[item.requirement_id] = item

            dependency_missing = []
            for dep in capability.get("implementationDependencies", []):
                if dep in {"config persistence backend"}:
                    continue
                if dep == "local-character position sampler" and signals["movement"]["playerPositionSampleCount"] > 0:
                    continue
                if dep == "lightweight drawing adapter" and signals["scan"]["objects"] > 0:
                    continue
                if dep == "gui-snapshot parser" and _evaluate_requirement("loadout_gui_structures", signals).available:
                    continue
                if dep == "schema normalizer" and _evaluate_requirement("feature_summary", signals).available:
                    continue
                dependency_missing.append(dep)

            stage = _stage_from_requirements(required, dependency_missing)
            if (
                stage == "Implementation dependencies satisfied"
                and capability["capabilityId"] == "movement_navigation_assist.movement_telemetry_overlay"
                and signals["movement"]["playerPositionSampleCount"] > 0
                and signals["movement"]["movementActionCount"] > 0
            ):
                stage = "Implementation ready"
            feature_stage_rank = max(feature_stage_rank, stage_order.index(stage))

            capability_entries.append({
                "capabilityId": capability["capabilityId"],
                "name": capability["name"],
                "description": capability["description"],
                "implementationMethod": capability["implementationMethod"],
                "requiredEntities": [item.requirement_id for item in required if definitions[item.requirement_id]["kind"] == "entity"],
                "requiredProperties": [item.requirement_id for item in required if definitions[item.requirement_id]["kind"] == "state"],
                "requiredObservations": [item.requirement_id for item in required if definitions[item.requirement_id]["kind"] in {"observation", "gui", "world", "summary"}],
                "optionalSupportingSignals": [item.requirement_id for item in optional],
                "requiredTemporalRelationships": capability.get("requiredTemporalRelationships", []),
                "implementationDependencies": capability.get("implementationDependencies", []),
                "verificationRequirements": capability.get("verificationRequirements", []),
                "missingEvidence": [item.requirement_id for item in required if not item.available],
                "missingDependencies": dependency_missing,
                "requirementResults": [
                    {
                        "requirementId": item.requirement_id,
                        "description": definitions[item.requirement_id]["description"],
                        "status": item.status,
                        "available": item.available,
                        "rationale": item.rationale,
                        "provenance": item.provenance,
                    }
                    for item in required + optional
                ],
                "confidence": "medium" if stage in {"Implementation dependencies satisfied", "Implementation ready"}
                    else "low" if stage == "Evidence sufficient for a bounded implementation"
                    else "very-low",
                "limitations": [
                    "Read-only client-visible evidence only",
                    "No server-authoritative verification",
                ],
                "stage": stage,
                "lifecycle": _lifecycle_flags(stage),
                "claims": dict(FALSE_CLAIMS),
            })

        feature_stage = stage_order[feature_stage_rank] if feature_stage_rank >= 0 else "Concept proposed"
        features.append({
            "featureId": spec["featureId"],
            "featureTitle": spec["featureTitle"],
            "featureType": spec["featureType"],
            "capabilities": capability_entries,
            "featureStage": feature_stage,
            "claims": dict(FALSE_CLAIMS),
        })

    return {
        "schemaVersion": SCHEMA_CONTRACTS,
        "requirements": [
            {
                "requirementId": key,
                "kind": value["kind"],
                "description": value["description"],
                "status": req_index[key].status if key in req_index else "unassessed",
                "available": req_index[key].available if key in req_index else False,
                "rationale": req_index[key].rationale if key in req_index else "",
                "provenance": req_index[key].provenance if key in req_index else [],
            }
            for key, value in sorted(definitions.items())
        ],
        "features": features,
        "claims": dict(FALSE_CLAIMS),
    }


def _build_reconciliation_report(
    signals: dict[str, Any],
    contracts: dict[str, Any],
) -> dict[str, Any]:
    requirement_trace = []
    for feature in contracts.get("features", []):
        for capability in feature.get("capabilities", []):
            for item in capability.get("requirementResults", []):
                requirement_trace.append({
                    "featureId": feature.get("featureId"),
                    "capabilityId": capability.get("capabilityId"),
                    "requirementId": item.get("requirementId"),
                    "status": item.get("status"),
                    "available": item.get("available"),
                    "provenance": item.get("provenance"),
                })

    status_counter = collections.Counter(item["status"] for item in requirement_trace if isinstance(item.get("status"), str))

    camera = signals["camera"]
    camera_discrepancy = {
        "cameraInputGestures": camera["inputGestureCount"],
        "cameraRotationObservations": camera["cameraTurnGestureCount"],
        "cameraStateSamples": camera["cameraStateSampleCount"],
        "cameraMovementCorrelations": camera["likelyCameraMovementGestureCount"],
        "verifiedCameraResponseBehavior": camera["verifiedCameraResponseBehavior"],
        "analysis": [
            "Camera state sample stream is empty in this observation export.",
            "Camera-turn evidence exists in gesture intent metrics.",
            "Previous feasibility gating relied on camera state samples only; this under-classified available camera evidence.",
        ],
    }

    findings = [
        {
            "id": "camera-evidence-type-mismatch",
            "classification": "captured-but-not-correctly-classified",
            "description": "Gesture-derived camera-turn evidence existed while camera state sample count was zero.",
            "impact": "Combat and navigation capabilities were over-blocked by camera sample gate.",
        },
        {
            "id": "loadout-gui-evidence-underused",
            "classification": "collected-but-not-correctly-extracted",
            "description": "Loadout and weapon GUI path tokens were present in observation click candidates.",
            "impact": "Loadout information capability was treated as generic evidence-required without capability split.",
        },
        {
            "id": "state-change-signal-absence",
            "classification": "genuinely-missing",
            "description": "No state-change signals were captured in the compiled interaction history.",
            "impact": "Trigger, recoil verification, and objective dashboards cannot progress to implementation-ready.",
        },
        {
            "id": "entity-scope-limitation",
            "classification": "partially-available",
            "description": "Single humanoid/local entity evidence exists but opponent/team coverage is incomplete.",
            "impact": "Target assist and full ESP enhancements remain blocked.",
        },
    ]

    return {
        "schemaVersion": SCHEMA_RECONCILIATION,
        "scan": signals["scan"],
        "cameraEvidenceBreakdown": camera_discrepancy,
        "reconciliationFindings": findings,
        "requirementTrace": requirement_trace,
        "requirementStatusSummary": dict(status_counter),
        "evidenceCoverage": {
            "missingEvidence": [
                item["requirementId"]
                for item in contracts.get("requirements", [])
                if isinstance(item, dict) and item.get("available") is False
            ],
            "capturedNotExtracted": [
                item["requirementId"]
                for item in contracts.get("requirements", [])
                if isinstance(item, dict) and item.get("status") == "captured-not-extracted"
            ],
            "capturedNotClassified": [
                item["requirementId"]
                for item in contracts.get("requirements", [])
                if isinstance(item, dict) and item.get("status") == "captured-not-classified"
            ],
            "available": [
                item["requirementId"]
                for item in contracts.get("requirements", [])
                if isinstance(item, dict) and item.get("status") == "available"
            ],
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _build_reassessed_feasibility(contracts: dict[str, Any]) -> dict[str, Any]:
    records = []
    summary_counter = collections.Counter()
    gameplay_ready = []

    for feature in contracts.get("features", []):
        if not isinstance(feature, dict):
            continue
        capability_records = []
        for capability in feature.get("capabilities", []):
            if not isinstance(capability, dict):
                continue
            stage = capability.get("stage")
            summary_counter[str(stage)] += 1
            if feature.get("featureType") == "gameplay" and stage == "Implementation ready":
                gameplay_ready.append({
                    "featureId": feature.get("featureId"),
                    "capabilityId": capability.get("capabilityId"),
                    "name": capability.get("name"),
                })
            capability_records.append({
                "capabilityId": capability.get("capabilityId"),
                "name": capability.get("name"),
                "stage": stage,
                "lifecycle": capability.get("lifecycle"),
                "missingEvidence": capability.get("missingEvidence"),
                "missingDependencies": capability.get("missingDependencies"),
                "claims": dict(FALSE_CLAIMS),
            })

        records.append({
            "featureId": feature.get("featureId"),
            "featureTitle": feature.get("featureTitle"),
            "featureType": feature.get("featureType"),
            "featureStage": feature.get("featureStage"),
            "capabilities": capability_records,
            "claims": dict(FALSE_CLAIMS),
        })

    return {
        "schemaVersion": SCHEMA_FEASIBILITY,
        "records": records,
        "summary": {
            "stageCounts": dict(summary_counter),
            "gameplayImplementationReadyCapabilities": gameplay_ready,
            "infrastructureFeatureCount": sum(1 for item in records if item.get("featureType") == "infrastructure"),
            "gameplayFeatureCount": sum(1 for item in records if item.get("featureType") == "gameplay"),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _build_targeted_inspection_plan(contracts: dict[str, Any], signals: dict[str, Any]) -> dict[str, Any]:
    missing_map: dict[str, set[str]] = collections.defaultdict(set)
    for feature in contracts.get("features", []):
        feature_id = feature.get("featureId")
        for capability in feature.get("capabilities", []):
            cap_id = capability.get("capabilityId")
            for req in capability.get("missingEvidence", []):
                if isinstance(req, str):
                    missing_map[req].add(f"{feature_id}:{cap_id}")

    requests = []

    if any(req in missing_map for req in ("player_entity_set", "team_relationship_signal", "character_spatial_positions")):
        requests.append({
            "requestId": "character-entity-observation",
            "targetFeatures": sorted(missing_map.get("player_entity_set", set()) | missing_map.get("team_relationship_signal", set())),
            "missingEvidence": [
                item for item in ["player_entity_set", "team_relationship_signal", "character_spatial_positions"] if item in missing_map
            ],
            "whyNeeded": "Targeting and ESP capabilities require opponent entity, team, and spatial evidence.",
            "serviceOrObjectCategory": "Players/Teams/Workspace character models",
            "safeObservationMethod": "Read-only tracking of PlayerAdded/CharacterAdded, Humanoid, HumanoidRootPart positions, and team changes.",
            "requiredObservationWindow": "At least one full live round with >=3 visible players.",
            "expectedOutputSchema": {
                "playerEntitySamples": "[{playerId, team, characterPath, humanoidPath, rootPartPath, positionSamples[]}]",
                "teamSnapshots": "[{timestamp, teams:[{name, memberCount}]}]",
            },
            "successCriteria": [
                "At least two non-local character entities captured with spatial samples",
                "Team relationship snapshots captured for the same entities",
            ],
            "failureConditions": [
                "Only local player entities captured",
                "Character root paths unavailable for all non-local entities",
            ],
        })

    if any(req in missing_map for req in ("camera_state_samples", "weapon_state_signal", "camera_movement_correlation")):
        requests.append({
            "requestId": "combat-camera-weapon-correlation",
            "targetFeatures": sorted(missing_map.get("camera_state_samples", set()) | missing_map.get("weapon_state_signal", set())),
            "missingEvidence": [
                item for item in ["camera_state_samples", "camera_movement_correlation", "weapon_state_signal", "weapon_equipped_signal"] if item in missing_map
            ],
            "whyNeeded": "Recoil and trigger capabilities require camera/weapon temporal evidence, not click-only signals.",
            "serviceOrObjectCategory": "CurrentCamera / Tool / HUD weapon state",
            "safeObservationMethod": "Read-only sampling of camera orientation, equipped tool identity, and HUD/state changes during controlled firing bursts.",
            "requiredObservationWindow": "Three burst sequences plus one non-firing camera pan sequence.",
            "expectedOutputSchema": {
                "cameraSamples": "[{timestamp, yaw, pitch}]",
                "weaponStateTransitions": "[{timestamp, key, before, after}]",
                "firingWindows": "[{start, end, inputSource}]",
            },
            "successCriteria": [
                "Camera sample stream available during firing and non-firing windows",
                "Weapon state transitions aligned to firing windows",
            ],
            "failureConditions": [
                "Camera samples remain empty",
                "No weapon-related state transitions during firing",
            ],
        })

    if "objective_hud_signals" in missing_map:
        requests.append({
            "requestId": "match-objective-state-observation",
            "targetFeatures": sorted(missing_map.get("objective_hud_signals", set())),
            "missingEvidence": ["objective_hud_signals"],
            "whyNeeded": "Objective dashboard capability requires reactive state transitions, not static HUD paths.",
            "serviceOrObjectCategory": "PlayerGui scoreboard/timer/objective components",
            "safeObservationMethod": "Read-only polling and transition capture for score/timer/objective labels across match phases.",
            "requiredObservationWindow": "Pre-round, mid-round, and round-end transition window.",
            "expectedOutputSchema": {
                "objectiveSignals": "[{timestamp, path, valueBefore, valueAfter}]",
                "roundPhases": "[{phase, startTimestamp, endTimestamp}]",
            },
            "successCriteria": [
                "At least one timer or objective value transition captured",
                "Transitions aligned with known round phase change",
            ],
            "failureConditions": [
                "Only static labels captured",
                "No objective-related value deltas",
            ],
        })

    if "weapon_equipped_signal" in missing_map or "hud_weapon_indicators" in missing_map:
        requests.append({
            "requestId": "loadout-runtime-observation",
            "targetFeatures": sorted(missing_map.get("weapon_equipped_signal", set()) | missing_map.get("hud_weapon_indicators", set())),
            "missingEvidence": [item for item in ["weapon_equipped_signal", "hud_weapon_indicators"] if item in missing_map],
            "whyNeeded": "Loadout runtime indicators require equipped-weapon and HUD linkage evidence.",
            "serviceOrObjectCategory": "Backpack/Character tools and loadout HUD widgets",
            "safeObservationMethod": "Read-only capture while switching weapons/loadouts in menu and live state.",
            "requiredObservationWindow": "At least two loadout switches and one in-match weapon swap.",
            "expectedOutputSchema": {
                "equippedTools": "[{timestamp, toolPath, toolName}]",
                "hudWeaponIndicators": "[{timestamp, path, text}]",
            },
            "successCriteria": [
                "Tool identity changes captured during switches",
                "HUD indicators update in sync with tool changes",
            ],
            "failureConditions": [
                "No tool identity changes detected",
                "HUD indicators static across switches",
            ],
        })

    return {
        "schemaVersion": SCHEMA_INSPECTION_PLAN,
        "scan": signals["scan"],
        "requests": requests,
        "summary": {
            "requestCount": len(requests),
            "missingRequirementCount": len(missing_map),
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _build_game_understanding_improvements(
    signals: dict[str, Any],
    gameplay_understanding: dict[str, Any],
    universal_intelligence: dict[str, Any],
    contracts: dict[str, Any],
) -> dict[str, Any]:
    mechanics = []

    for item in gameplay_understanding.get("systems", []) if isinstance(gameplay_understanding, dict) else []:
        if not isinstance(item, dict):
            continue
        mechanic_id = item.get("id")
        if not isinstance(mechanic_id, str):
            continue
        support = []
        if item.get("observedInteractions"):
            support.append(f"observed interactions: {item.get('observedInteractions')}")
        if item.get("observableOutcomeCandidates"):
            support.append(f"outcome candidates: {item.get('observableOutcomeCandidates')}")

        alternative = "Could be menu/context interaction without gameplay effect" if mechanic_id in {"item_management", "combat"} else "Could represent non-core gameplay utility interactions"
        mechanics.append({
            "mechanicId": mechanic_id,
            "label": item.get("label"),
            "supportingObservations": support,
            "confidence": "medium" if support else "low",
            "alternativeInterpretations": [alternative],
            "missingEvidence": [
                "state_change_signals" if signals["stateChangeTotal"] == 0 else None,
                "player_entity_set" if signals["entities"]["humanoidCount"] <= 1 else None,
            ],
            "objectiveLink": "improve player effectiveness in live rounds",
            "candidateTools": [
                cap.get("capabilityId")
                for feature in contracts.get("features", [])
                for cap in feature.get("capabilities", [])
                if isinstance(cap, dict) and isinstance(cap.get("capabilityId"), str)
            ][:8],
            "verificationMethod": "Controlled runtime telemetry in a live match with reproducible transitions.",
        })

    if not mechanics:
        mechanics.append({
            "mechanicId": "unknown",
            "label": "Unknown mechanics",
            "supportingObservations": [],
            "confidence": "low",
            "alternativeInterpretations": ["Insufficient interaction evidence"],
            "missingEvidence": ["observed_interaction_evidence"],
            "objectiveLink": "collect richer gameplay observations",
            "candidateTools": [],
            "verificationMethod": "Capture targeted observation windows with state transitions.",
        })

    return {
        "schemaVersion": SCHEMA_UNDERSTANDING,
        "scan": signals["scan"],
        "mechanics": mechanics,
        "evidenceToObjectiveMapping": {
            "observedEvidence": {
                "movementActions": signals["movement"]["movementActionCount"],
                "cameraTurnGestures": signals["camera"]["cameraTurnGestureCount"],
                "loadoutPathSignals": int(signals["pathTokenCounts"].get("loadout", 0)),
            },
            "inferredObjectives": [
                "combat effectiveness",
                "movement/navigation control",
                "loadout management",
            ],
            "challengeDrivers": [
                "limited state-change telemetry",
                "insufficient opponent entity evidence",
                "camera sample stream missing",
            ],
        },
        "multiGenreNote": {
            "principle": "Capability contracts rely on evidence primitives, not fixed FPS labels.",
            "nonFpsApplicability": "Movement, inventory, objective, and profile capabilities map to non-FPS genres through the same requirement layer.",
        },
        "claims": dict(FALSE_CLAIMS),
    }


def _movement_telemetry_overlay_lua() -> str:
    return """--!strict
-- Generated by Lycoles evidence reconciliation milestone v3.
-- Read-only movement telemetry module with lifecycle/config contract.

local MovementTelemetry = {}
MovementTelemetry.__index = MovementTelemetry

export type VisibleFieldConfig = {
    speed: boolean?,
    position: boolean?,
    state: boolean?,
    moveDirection: boolean?,
}

export type DisplayPosition = {
    anchorX: number?,
    anchorY: number?,
    xOffset: number?,
    yOffset: number?,
}

export type Config = {
    Enabled: boolean?,
    UpdateInterval: number?,
    DisplayPosition: DisplayPosition?,
    VisibleFields: VisibleFieldConfig?,
    DisplayScale: number?,
    TextSize: number?,
    Opacity: number?,
}

local DEFAULT_CONFIG: Config = {
    Enabled = true,
    UpdateInterval = 0.2,
    DisplayPosition = {anchorX = 0, anchorY = 0, xOffset = 20, yOffset = 120},
    VisibleFields = {speed = true, position = true, state = true, moveDirection = true},
    DisplayScale = 1,
    TextSize = 13,
    Opacity = 0.2,
}

local function clamp(value: number, minValue: number, maxValue: number): number
    if value < minValue then
        return minValue
    end
    if value > maxValue then
        return maxValue
    end
    return value
end

local function shallowCopy(source)
    local out = {}
    for key, value in pairs(source) do
        out[key] = value
    end
    return out
end

local function normalizeConfig(config: Config?): Config
    local merged: Config = shallowCopy(DEFAULT_CONFIG)
    if not config then
        return merged
    end
    if type(config.Enabled) == "boolean" then
        merged.Enabled = config.Enabled
    end
    if type(config.UpdateInterval) == "number" then
        merged.UpdateInterval = clamp(config.UpdateInterval, 0.05, 2.0)
    end
    if type(config.DisplayScale) == "number" then
        merged.DisplayScale = clamp(config.DisplayScale, 0.5, 2.5)
    end
    if type(config.TextSize) == "number" then
        merged.TextSize = clamp(config.TextSize, 10, 28)
    end
    if type(config.Opacity) == "number" then
        merged.Opacity = clamp(config.Opacity, 0, 1)
    end
    if type(config.DisplayPosition) == "table" then
        local position = shallowCopy(merged.DisplayPosition)
        if type(config.DisplayPosition.anchorX) == "number" then
            position.anchorX = clamp(config.DisplayPosition.anchorX, 0, 1)
        end
        if type(config.DisplayPosition.anchorY) == "number" then
            position.anchorY = clamp(config.DisplayPosition.anchorY, 0, 1)
        end
        if type(config.DisplayPosition.xOffset) == "number" then
            position.xOffset = config.DisplayPosition.xOffset
        end
        if type(config.DisplayPosition.yOffset) == "number" then
            position.yOffset = config.DisplayPosition.yOffset
        end
        merged.DisplayPosition = position
    end
    if type(config.VisibleFields) == "table" then
        local fields = shallowCopy(merged.VisibleFields)
        for _, key in ipairs({"speed", "position", "state", "moveDirection"}) do
            if type(config.VisibleFields[key]) == "boolean" then
                fields[key] = config.VisibleFields[key]
            end
        end
        merged.VisibleFields = fields
    end
    return merged
end

local function resolveCharacter(localPlayer: Player): (Humanoid?, BasePart?)
    local character = localPlayer.Character
    if not character then
        return nil, nil
    end
    local humanoid = character:FindFirstChildOfClass("Humanoid")
    local root = character:FindFirstChild("HumanoidRootPart")
    if root and root:IsA("BasePart") then
        return humanoid, root
    end
    return humanoid, nil
end

local function sampleTelemetry(state)
    local humanoid, root = resolveCharacter(state.localPlayer)
    if not humanoid or not root then
        state.lastPosition = nil
        return {
            available = false,
            reason = "Character unavailable",
            timestamp = os.clock(),
        }
    end

    local now = os.clock()
    local speed = 0
    if state.lastPosition and state.lastSampleClock then
        local elapsed = math.max(1e-3, now - state.lastSampleClock)
        speed = (root.Position - state.lastPosition).Magnitude / elapsed
    end

    local stateName = tostring(humanoid:GetState()):gsub("Enum.HumanoidStateType.", "")
    local moveDir = humanoid.MoveDirection

    state.lastPosition = root.Position
    state.lastSampleClock = now

    return {
        available = true,
        timestamp = now,
        speedStudsPerSecond = speed,
        position = root.Position,
        state = stateName,
        moveDirection = moveDir,
    }
end

local function renderTelemetry(state, sample)
    local label = state.bodyLabel
    if not label then
        return
    end
    if not sample.available then
        label.Text = sample.reason or "Character unavailable"
        return
    end

    local lines = {}
    local visible = state.config.VisibleFields
    if visible.speed then
        table.insert(lines, string.format("Speed: %.1f stud/s", sample.speedStudsPerSecond))
    end
    if visible.position and sample.position then
        table.insert(lines, string.format("Pos: (%.1f, %.1f, %.1f)", sample.position.X, sample.position.Y, sample.position.Z))
    end
    if visible.state then
        table.insert(lines, "State: " .. tostring(sample.state))
    end
    if visible.moveDirection and sample.moveDirection then
        table.insert(lines, string.format("MoveDir: (%.2f, %.2f, %.2f)", sample.moveDirection.X, sample.moveDirection.Y, sample.moveDirection.Z))
    end
    label.Text = table.concat(lines, "\n")
end

local function createOverlay(state)
    local playerGui = state.localPlayer:FindFirstChildOfClass("PlayerGui")
    if not playerGui then
        return
    end

    local scale = state.config.DisplayScale or 1
    local textSize = math.floor((state.config.TextSize or 13) * scale + 0.5)

    local screenGui = Instance.new("ScreenGui")
    screenGui.Name = "LycolesMovementTelemetry"
    screenGui.ResetOnSpawn = false
    screenGui.IgnoreGuiInset = false
    screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
    screenGui.Parent = playerGui

    local frame = Instance.new("Frame")
    frame.Name = "TelemetryFrame"
    frame.Size = UDim2.fromOffset(math.floor(280 * scale + 0.5), math.floor(110 * scale + 0.5))
    local pos = state.config.DisplayPosition or {}
    frame.Position = UDim2.new(pos.anchorX or 0, pos.xOffset or 20, pos.anchorY or 0, pos.yOffset or 120)
    frame.BackgroundColor3 = Color3.fromRGB(16, 18, 25)
    frame.BackgroundTransparency = state.config.Opacity or 0.2
    frame.BorderSizePixel = 0
    frame.Parent = screenGui

    local title = Instance.new("TextLabel")
    title.Size = UDim2.new(1, -12, 0, math.floor(24 * scale + 0.5))
    title.Position = UDim2.fromOffset(6, 4)
    title.BackgroundTransparency = 1
    title.TextXAlignment = Enum.TextXAlignment.Left
    title.Font = Enum.Font.GothamBold
    title.TextSize = math.max(11, textSize)
    title.TextColor3 = Color3.fromRGB(220, 236, 255)
    title.Text = "Movement Telemetry"
    title.Parent = frame

    local body = Instance.new("TextLabel")
    body.Size = UDim2.new(1, -12, 1, -math.floor(32 * scale + 0.5))
    body.Position = UDim2.fromOffset(6, math.floor(28 * scale + 0.5))
    body.BackgroundTransparency = 1
    body.TextXAlignment = Enum.TextXAlignment.Left
    body.TextYAlignment = Enum.TextYAlignment.Top
    body.Font = Enum.Font.Code
    body.TextSize = textSize
    body.TextColor3 = Color3.fromRGB(200, 215, 232)
    body.TextWrapped = true
    body.Text = "Waiting for character..."
    body.Parent = frame

    state.screenGui = screenGui
    state.bodyLabel = body
end

function MovementTelemetry.new(config: Config?, services)
    local svc = services or {}
    local players = svc.Players or game:GetService("Players")
    local runService = svc.RunService or game:GetService("RunService")
    local localPlayer = players.LocalPlayer

    local self = setmetatable({
        config = normalizeConfig(config),
        players = players,
        runService = runService,
        localPlayer = localPlayer,
        running = false,
        connections = {},
        elapsed = 0,
        lastPosition = nil,
        lastSampleClock = nil,
        lastSample = nil,
        screenGui = nil,
        bodyLabel = nil,
    }, MovementTelemetry)

    return self
end

function MovementTelemetry:UpdateConfig(configPatch: Config)
    self.config = normalizeConfig(configPatch)
    if self.running then
        self:Stop()
        self:Start()
    end
end

function MovementTelemetry:SetEnabled(enabled: boolean)
    local current = self.config
    current.Enabled = enabled
    self:UpdateConfig(current)
end

function MovementTelemetry:GetLatestSample()
    return self.lastSample
end

function MovementTelemetry:GetStatus()
    return {
        running = self.running,
        enabled = self.config.Enabled == true,
        hasCharacter = self.lastSample and self.lastSample.available == true,
        updateInterval = self.config.UpdateInterval,
    }
end

function MovementTelemetry:Start()
    if self.running or self.config.Enabled ~= true then
        return false
    end
    if not self.localPlayer then
        return false
    end

    self.running = true
    self.elapsed = 0
    self.lastPosition = nil
    self.lastSampleClock = nil

    createOverlay(self)

    table.insert(self.connections, self.localPlayer.CharacterAdded:Connect(function()
        self.lastPosition = nil
        self.lastSampleClock = nil
    end))

    table.insert(self.connections, self.runService.Heartbeat:Connect(function(deltaTime)
        if not self.running then
            return
        end
        self.elapsed += deltaTime
        if self.elapsed < (self.config.UpdateInterval or 0.2) then
            return
        end
        self.elapsed = 0

        local sample = sampleTelemetry(self)
        self.lastSample = sample
        renderTelemetry(self, sample)
    end))

    return true
end

function MovementTelemetry:Stop()
    if not self.running then
        return
    end
    self.running = false
    for _, connection in ipairs(self.connections) do
        pcall(function()
            connection:Disconnect()
        end)
    end
    self.connections = {}
    if self.screenGui then
        pcall(function()
            self.screenGui:Destroy()
        end)
        self.screenGui = nil
        self.bodyLabel = nil
    end
end

return MovementTelemetry
"""

def _build_generation_integration_report(
    *,
    scan: dict[str, Any],
    contracts: dict[str, Any],
    feasibility: dict[str, Any],
    targeted_plan: dict[str, Any],
    integration_context: Optional[dict[str, Any]],
) -> dict[str, Any]:
    ready_gameplay = feasibility.get("summary", {}).get("gameplayImplementationReadyCapabilities") if isinstance(feasibility.get("summary"), dict) else []

    return {
        "schemaVersion": SCHEMA_INTEGRATION,
        "scan": scan,
        "consumedArtifacts": [
            "capability-plan.json",
            "gameplay-understanding.json",
            "universal-gameplay-intelligence.json",
            "capability-evidence-contracts.json",
            "reassessed-feature-feasibility.json",
            "targeted-inspection-plan.json",
        ],
        "serviceIntegration": {
            "integrated": bool(integration_context),
            "context": integration_context or {},
            "consumption": {
                "normalizedEvidence": True,
                "gameUnderstandingRecords": True,
                "featureProposals": True,
                "capabilityFeasibility": True,
                "runtimeConfigSchemas": True,
                "targetedInspectionRequests": True,
            },
        },
        "plannerHints": {
            "gameplayReadyCapabilities": ready_gameplay,
            "blockedCapabilityCount": sum(
                1
                for feature in contracts.get("features", [])
                for capability in feature.get("capabilities", [])
                if isinstance(capability, dict) and capability.get("stage") not in {"Implementation ready", "Implemented", "Static validation passed", "Runtime tested", "Gameplay verified"}
            ),
            "targetedInspectionRequestCount": len(targeted_plan.get("requests", [])),
        },
        "claims": dict(FALSE_CLAIMS),
    }

def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_summary(path: pathlib.Path, *, recon: dict[str, Any], feasibility: dict[str, Any], targeted_plan: dict[str, Any]) -> None:
    stage_counts = (feasibility.get("summary") or {}).get("stageCounts", {})
    ready_gameplay = (feasibility.get("summary") or {}).get("gameplayImplementationReadyCapabilities", [])

    lines = [
        "# Milestone 2 Summary — Evidence Reconciliation and Capability Feasibility",
        "",
        f"- Scan: `{(recon.get('scan') or {}).get('scanId')}`",
        f"- Place: `{(recon.get('scan') or {}).get('placeId')}`",
        f"- Camera discrepancy: gestures={recon.get('cameraEvidenceBreakdown', {}).get('cameraRotationObservations')} vs stateSamples={recon.get('cameraEvidenceBreakdown', {}).get('cameraStateSamples')}",
        "",
        "## Requirement status counts",
        "",
    ]
    for key, value in sorted((recon.get("requirementStatusSummary") or {}).items()):
        lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Capability stage counts",
        "",
    ])
    for key, value in sorted(stage_counts.items()):
        lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Implementation-ready gameplay capabilities",
        "",
    ])
    if ready_gameplay:
        for item in ready_gameplay:
            lines.append(f"- {item.get('featureId')} :: {item.get('capabilityId')} ({item.get('name')})")
    else:
        lines.append("- None in current evidence package")

    lines.extend([
        "",
        "## Targeted inspection requests",
        "",
        f"- Request count: {len(targeted_plan.get('requests', []))}",
    ])
    for request in targeted_plan.get("requests", []):
        if not isinstance(request, dict):
            continue
        lines.append(f"- {request.get('requestId')}: missing {', '.join(request.get('missingEvidence', []))}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_with_plan(
    *,
    plan: dict[str, Any],
    observation: Optional[dict[str, Any]],
    output_dir: pathlib.Path,
    targeted_sessions: Optional[list[dict[str, Any]]] = None,
    integration_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    gameplay_understanding = UNDERSTAND_GAMEPLAY.analyze(plan)
    universal_intelligence = UNIVERSAL_INTELLIGENCE.analyze(plan)

    signals = _extract_evidence_signals(plan, observation, targeted_sessions=targeted_sessions)
    contracts = _build_capability_contracts(signals)
    reconciliation = _build_reconciliation_report(signals, contracts)
    feasibility = _build_reassessed_feasibility(contracts)
    targeted_plan = _build_targeted_inspection_plan(contracts, signals)
    understanding = _build_game_understanding_improvements(signals, gameplay_understanding, universal_intelligence, contracts)
    integration = _build_generation_integration_report(
        scan=signals["scan"],
        contracts=contracts,
        feasibility=feasibility,
        targeted_plan=targeted_plan,
        integration_context=integration_context,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "evidence-reconciliation-report.json", reconciliation)
    _write_json(output_dir / "capability-evidence-contracts.json", contracts)
    _write_json(output_dir / "reassessed-feature-feasibility.json", feasibility)
    _write_json(output_dir / "targeted-inspection-plan.json", targeted_plan)
    _write_json(output_dir / "game-understanding-improvements.json", understanding)
    _write_json(output_dir / "generation-integration-report.json", integration)
    _write_summary(output_dir / "milestone-2-summary.md", recon=reconciliation, feasibility=feasibility, targeted_plan=targeted_plan)

    gameplay_ready = (feasibility.get("summary") or {}).get("gameplayImplementationReadyCapabilities") or []
    movement_module_path = None
    if any(
        isinstance(item, dict)
        and item.get("capabilityId") == "movement_navigation_assist.movement_telemetry_overlay"
        for item in gameplay_ready
    ):
        movement_module_path = output_dir / "MovementTelemetryOverlay.lua"
        movement_module_path.write_text(_movement_telemetry_overlay_lua(), encoding="utf-8")

    return {
        "scanId": signals["scan"].get("scanId"),
        "placeId": signals["scan"].get("placeId"),
        "outputDir": str(output_dir),
        "files": {
            "evidenceReconciliationReport": str(output_dir / "evidence-reconciliation-report.json"),
            "capabilityEvidenceContracts": str(output_dir / "capability-evidence-contracts.json"),
            "reassessedFeatureFeasibility": str(output_dir / "reassessed-feature-feasibility.json"),
            "targetedInspectionPlan": str(output_dir / "targeted-inspection-plan.json"),
            "gameUnderstandingImprovements": str(output_dir / "game-understanding-improvements.json"),
            "generationIntegrationReport": str(output_dir / "generation-integration-report.json"),
            "milestone2Summary": str(output_dir / "milestone-2-summary.md"),
            "movementTelemetryOverlayModule": str(movement_module_path) if movement_module_path else None,
        },
        "summary": {
            "requirementStatusSummary": reconciliation.get("requirementStatusSummary"),
            "stageCounts": (feasibility.get("summary") or {}).get("stageCounts"),
            "gameplayImplementationReadyCapabilities": (feasibility.get("summary") or {}).get("gameplayImplementationReadyCapabilities"),
            "targetedInspectionRequestCount": len(targeted_plan.get("requests", [])),
            "targetedSessionsConsumed": len(targeted_sessions or []),
        },
    }


def run_from_parts(
    *,
    parts_dir: pathlib.Path,
    output_dir: pathlib.Path,
    observation_file: Optional[pathlib.Path] = None,
    integration_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    plan = COMPILE_SCAN.compile_scan(str(parts_dir))
    observation = _safe_json(observation_file) if observation_file is not None else None
    targeted_sessions = _extract_targeted_sessions([observation]) if isinstance(observation, dict) else []
    return _run_with_plan(
        plan=plan,
        observation=observation,
        targeted_sessions=targeted_sessions,
        output_dir=output_dir,
        integration_context=integration_context,
    )


def run_from_artifacts(
    *,
    capability_plan_path: pathlib.Path,
    output_dir: pathlib.Path,
    observation_files: tuple[pathlib.Path, ...] = (),
    integration_context: Optional[dict[str, Any]] = None,
) -> Optional[dict[str, Any]]:
    if not capability_plan_path.is_file():
        return None
    plan = _safe_json(capability_plan_path)

    loaded_payloads: list[dict[str, Any]] = []
    for path in observation_files:
        if not path.is_file():
            continue
        try:
            payload = _safe_json(path)
        except Exception:
            continue
        loaded_payloads.append(payload)

    observation = None
    for payload in loaded_payloads:
        diagnostics = payload.get("sourceDiagnostics") if isinstance(payload.get("sourceDiagnostics"), dict) else {}
        if diagnostics.get("scanMode") == "dynamic-observations" or payload.get("exportKind") == "dynamic-observations":
            observation = payload
            break

    targeted_sessions = _extract_targeted_sessions(loaded_payloads)
    return _run_with_plan(
        plan=plan,
        observation=observation,
        targeted_sessions=targeted_sessions,
        output_dir=output_dir,
        integration_context=integration_context,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parts-dir", required=True)
    parser.add_argument("--output-dir", default="generated/universal_milestone_v2")
    parser.add_argument("--observation-file", default=None)
    args = parser.parse_args()

    parts_dir = pathlib.Path(args.parts_dir).expanduser().resolve()
    output_dir = pathlib.Path(args.output_dir).expanduser().resolve()
    observation_file = pathlib.Path(args.observation_file).expanduser().resolve() if args.observation_file else None

    result = run_from_parts(parts_dir=parts_dir, output_dir=output_dir, observation_file=observation_file)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
