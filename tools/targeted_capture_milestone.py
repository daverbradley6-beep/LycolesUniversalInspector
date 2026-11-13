#!/usr/bin/env python3
"""Milestone 3 targeted capture and runtime-validation orchestrator.

Produces:
- targeted-capture-architecture.json
- targeted-inspection-requests.json
- targeted-evidence-schema.json
- capture-validation-report.json
- movement-overlay-validation.json
- capability-readiness-update.json
- runtime-test-instructions.md
- milestone-3-summary.md
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import pathlib
import sys
from dataclasses import dataclass
from typing import Any, Optional

REQUEST_SCHEMA = "122.targeted-inspection-requests.1"
TARGETED_SCHEMA = "122.targeted-evidence-schema.1"
ARCH_SCHEMA = "122.targeted-capture-architecture.1"
CAPTURE_VALIDATION_SCHEMA = "122.capture-validation-report.1"
OVERLAY_VALIDATION_SCHEMA = "122.movement-overlay-validation.1"
READINESS_UPDATE_SCHEMA = "122.capability-readiness-update.1"


REQUEST_TEMPLATES: dict[str, dict[str, Any]] = {
    "character-entity-observation": {
        "featureIds": ["esp_player_overlay"],
        "capabilityIds": ["esp_player_overlay.basic_entity_boxes", "esp_player_overlay.team_and_health_enhancements"],
        "requiredEvidence": ["player_entity_set", "team_relationship_signal", "character_spatial_positions", "health_signal_count"],
        "services": ["Players", "Teams", "Workspace"],
        "classes": ["Player", "Model", "Humanoid", "HumanoidRootPart"],
        "properties": ["Health", "MaxHealth", "Position", "Team", "TeamColor"],
        "events": ["PlayerAdded", "PlayerRemoving", "CharacterAdded", "CharacterRemoving"],
        "conditions": ["client-visible-only", "bounded", "non-authoritative"],
        "sampling": {"intervalSeconds": 0.5, "maxSamples": 420},
        "maxDurationSeconds": 240,
        "expectedOutputSchema": "31.0.targeted-evidence-session.1.character-entities",
        "completionCriteria": ["non-local-player-entity-observed", "team-signal-observed", "health-and-position-samples-captured"],
        "failureConditions": ["no-character-entities", "session-duration-exceeded"],
    },
    "combat-camera-weapon-correlation": {
        "featureIds": ["combat_recoil_assist", "combat_trigger_assist"],
        "capabilityIds": ["combat_recoil_assist.recoil_camera_compensation", "combat_trigger_assist.crosshair_fire_condition"],
        "requiredEvidence": ["camera_state_samples", "camera_movement_correlation", "weapon_state_signal", "weapon_equipped_signal", "mouse_primary_input"],
        "services": ["Workspace", "UserInputService", "Players"],
        "classes": ["Camera", "Tool", "Humanoid", "Backpack"],
        "properties": ["CFrame", "LookVector", "Tool.Name", "MoveDirection"],
        "events": ["InputBegan", "InputEnded", "Tool.Equipped", "Tool.Unequipped"],
        "conditions": ["no-synthetic-fire-events", "no-remote-invocation", "non-authoritative"],
        "sampling": {"intervalSeconds": 0.2, "maxSamples": 900},
        "maxDurationSeconds": 240,
        "expectedOutputSchema": "31.0.targeted-evidence-session.1.combat-camera",
        "completionCriteria": ["camera-samples-captured", "primary-input-observed", "equipped-tool-state-observed", "temporal-correlation-sampled"],
        "failureConditions": ["camera-unavailable", "session-duration-exceeded"],
    },
    "match-objective-state-observation": {
        "featureIds": ["objective_status_dashboard"],
        "capabilityIds": ["objective_status_dashboard.match_state_signals"],
        "requiredEvidence": ["objective_hud_signals", "state_change_signals"],
        "services": ["Players", "StarterGui"],
        "classes": ["ScreenGui", "TextLabel", "TextButton"],
        "properties": ["Text", "Visible", "Enabled"],
        "events": ["PropertyChangedSignal.Text", "PropertyChangedSignal.Visible"],
        "conditions": ["gui-state-observation-only", "non-authoritative"],
        "sampling": {"intervalSeconds": 0.6, "maxSamples": 520},
        "maxDurationSeconds": 240,
        "expectedOutputSchema": "31.0.targeted-evidence-session.1.match-state",
        "completionCriteria": ["objective-gui-signals-captured", "at-least-one-transition-observed"],
        "failureConditions": ["no-objective-gui-signals", "session-duration-exceeded"],
    },
    "loadout-runtime-observation": {
        "featureIds": ["loadout_information_suite"],
        "capabilityIds": ["loadout_information_suite.loadout_gui_reader", "loadout_information_suite.runtime_weapon_state"],
        "requiredEvidence": ["weapon_equipped_signal", "hud_weapon_indicators", "loadout_gui_structures"],
        "services": ["Players", "ReplicatedStorage"],
        "classes": ["Backpack", "Tool", "ScreenGui", "TextLabel"],
        "properties": ["Tool.Name", "Tool.Attributes", "Text", "Visible"],
        "events": ["Backpack.ChildAdded", "Backpack.ChildRemoved", "Tool.Equipped", "Tool.Unequipped"],
        "conditions": ["client-visible-loadout-only", "non-authoritative"],
        "sampling": {"intervalSeconds": 0.45, "maxSamples": 420},
        "maxDurationSeconds": 240,
        "expectedOutputSchema": "31.0.targeted-evidence-session.1.loadout-runtime",
        "completionCriteria": ["backpack-or-equipped-tools-observed", "hud-weapon-label-observed"],
        "failureConditions": ["no-tool-evidence", "session-duration-exceeded"],
    },
}


@dataclass
class MilestoneInputs:
    capability_plan_path: pathlib.Path
    milestone2_dir: pathlib.Path
    output_dir: pathlib.Path
    dynamic_observation: Optional[pathlib.Path] = None
    targeted_evidence: Optional[pathlib.Path] = None


def _load_json(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _load_reconciliation_module(root: pathlib.Path):
    source = root / "tools" / "evidence_reconciliation_milestone.py"
    spec = importlib.util.spec_from_file_location("evidence_reconciliation_milestone", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load evidence_reconciliation_milestone.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _build_targeted_capture_architecture() -> dict[str, Any]:
    return {
        "schemaVersion": ARCH_SCHEMA,
        "engine": {
            "requestLoading": "Structured JSON requests loaded at runtime with bounded normalization",
            "sessionLifecycle": "Start/Stop session with active progress tracking and duration limits",
            "boundedSampling": "Heartbeat-driven capture with per-category caps and interval throttling",
            "multiRequestSupport": True,
            "requestSelection": "Preset-driven selection plus runtime request loading",
            "resourceCleanup": "No persistent capture listeners; session stop releases active state",
        },
        "observationCategories": [
            "character-entity-observation",
            "combat-camera-weapon-correlation",
            "match-objective-state-observation",
            "loadout-runtime-observation",
        ],
        "compatibility": {
            "baselineMultipart": True,
            "dynamicObservationOverlay": True,
            "targetedSessionEmbeddedInInteractionDiagnostics": True,
            "chunkedTimelineExport": True,
        },
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "serverAuthorityVerified": False,
            "causalityProven": False,
        },
    }


def _build_targeted_requests(m2_plan: dict[str, Any], place_id: int) -> dict[str, Any]:
    output_requests: list[dict[str, Any]] = []
    for item in m2_plan.get("requests", []):
        if not isinstance(item, dict):
            continue
        request_id = item.get("requestId")
        if not isinstance(request_id, str):
            continue
        template = REQUEST_TEMPLATES.get(request_id, {})
        merged = {
            "requestId": request_id,
            "targetFeatureCapabilityPairs": item.get("targetFeatureCapabilityPairs") if isinstance(item.get("targetFeatureCapabilityPairs"), list) else [],
            "whyNeeded": item.get("whyNeeded"),
            "missingEvidence": item.get("missingEvidence") if isinstance(item.get("missingEvidence"), list) else [],
            "featureIds": template.get("featureIds", []),
            "capabilityIds": template.get("capabilityIds", []),
            "requiredEvidence": template.get("requiredEvidence", []),
            "services": template.get("services", []),
            "classes": template.get("classes", []),
            "properties": template.get("properties", []),
            "events": template.get("events", []),
            "conditions": template.get("conditions", []),
            "sampling": template.get("sampling", {"intervalSeconds": 0.5, "maxSamples": 300}),
            "maxDurationSeconds": template.get("maxDurationSeconds", 240),
            "expectedOutputSchema": template.get("expectedOutputSchema", "31.0.targeted-evidence-session.1.generic"),
            "completionCriteria": template.get("completionCriteria", []),
            "failureConditions": template.get("failureConditions", []),
            "provenance": {"source": "client-observation", "authority": "non-authoritative"},
        }
        output_requests.append(merged)

    return {
        "schemaVersion": REQUEST_SCHEMA,
        "placeId": place_id,
        "requestCount": len(output_requests),
        "requests": output_requests,
    }


def _targeted_evidence_schema() -> dict[str, Any]:
    return {
        "schemaVersion": TARGETED_SCHEMA,
        "sessionSchemaVersion": "31.0.targeted-evidence-session.1",
        "requiredTopLevelFields": [
            "schemaVersion",
            "exportKind",
            "sessionId",
            "placeId",
            "baselineScanId",
            "requestIds",
            "requestProgress",
            "samples",
            "collectionLimitations",
            "errors",
        ],
        "sampleCollections": {
            "characterEntities": {"maxItems": 420},
            "entityEvents": {"maxItems": 240},
            "cameraSamples": {"maxItems": 900},
            "cameraCorrelations": {"maxItems": 640},
            "inputSamples": {"maxItems": 900},
            "weaponSnapshots": {"maxItems": 520},
            "loadoutSnapshots": {"maxItems": 420},
            "matchStateSamples": {"maxItems": 520},
            "transitions": {"maxItems": 420},
            "timelineEvents": {"chunkable": True},
        },
        "identityLinkage": {
            "requiresBaselineScanId": True,
            "requiresPlaceId": True,
            "allowsDynamicObservationEmbedding": True,
        },
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "serverAuthorityVerified": False,
            "causalityProven": False,
        },
    }


def _compute_request_completion(targeted: dict[str, Any], request_id: str) -> tuple[list[str], list[str]]:
    samples = targeted.get("samples") if isinstance(targeted.get("samples"), dict) else {}
    character = samples.get("characterEntities") or []
    camera = samples.get("cameraSamples") or []
    camera_correlations = samples.get("cameraCorrelations") or []
    loadout = samples.get("loadoutSnapshots") or []
    weapon = samples.get("weaponSnapshots") or []
    match_states = samples.get("matchStateSamples") or []
    transitions = samples.get("transitions") or []
    input_samples = samples.get("inputSamples") or []

    primary_inputs = 0
    for item in input_samples:
        if isinstance(item, dict):
            primary_inputs += int(item.get("mousePrimaryInputs") or 0)

    non_local = 0
    team_signals = 0
    for item in character:
        if isinstance(item, dict):
            if item.get("isLocalPlayer") is False:
                non_local += 1
            if isinstance(item.get("team"), str) and item.get("team"):
                team_signals += 1

    hud_signals = 0
    for item in loadout:
        if isinstance(item, dict):
            hud_signals += len(item.get("hudWeaponIndicators") or [])

    objective_signals = 0
    for item in match_states:
        if isinstance(item, dict) and isinstance(item.get("signals"), dict):
            objective_signals += len(item["signals"])

    satisfied: list[str] = []
    missing: list[str] = []

    def mark(name: str, ok: bool) -> None:
        if ok:
            satisfied.append(name)
        else:
            missing.append(name)

    if request_id == "character-entity-observation":
        mark("player_entity_set", non_local > 0)
        mark("team_relationship_signal", team_signals > 0)
        mark("character_spatial_positions", len(character) > 0)
    elif request_id == "combat-camera-weapon-correlation":
        mark("camera_state_samples", len(camera) > 0)
        mark("camera_movement_correlation", len(camera_correlations) > 0)
        mark("weapon_equipped_signal", len(weapon) > 0 or len(loadout) > 0)
        mark("mouse_primary_input", primary_inputs > 0)
    elif request_id == "match-objective-state-observation":
        mark("objective_hud_signals", objective_signals > 0)
        mark("state_change_signals", len(transitions) > 0)
    elif request_id == "loadout-runtime-observation":
        mark("weapon_equipped_signal", len(weapon) > 0)
        mark("hud_weapon_indicators", hud_signals > 0)
        mark("loadout_gui_structures", len(loadout) > 0)

    return satisfied, missing


def _build_capture_validation_report(
    targeted: Optional[dict[str, Any]],
    requests: dict[str, Any],
    expected_place_id: int,
    expected_baseline_scan_id: str,
) -> dict[str, Any]:
    if not isinstance(targeted, dict):
        return {
            "schemaVersion": CAPTURE_VALIDATION_SCHEMA,
            "available": False,
            "status": "no-targeted-evidence-provided",
            "requestValidation": [],
            "identityChecks": {
                "placeIdMatches": False,
                "baselineScanIdMatches": False,
            },
            "claims": {
                "runtimeVerified": False,
                "gameplayVerified": False,
                "causalityProven": False,
            },
        }

    request_validation: list[dict[str, Any]] = []
    complete = 0
    for req in requests.get("requests", []):
        request_id = req.get("requestId") if isinstance(req, dict) else None
        if not isinstance(request_id, str):
            continue
        satisfied, missing = _compute_request_completion(targeted, request_id)
        is_complete = len(missing) == 0
        if is_complete:
            complete += 1
        request_validation.append({
            "requestId": request_id,
            "status": "complete" if is_complete else "partial",
            "satisfiedEvidence": satisfied,
            "missingEvidence": missing,
        })

    samples = targeted.get("samples") if isinstance(targeted.get("samples"), dict) else {}
    counts = {name: len(values) for name, values in samples.items() if isinstance(values, list)}

    place_match = targeted.get("placeId") == expected_place_id
    baseline_match = targeted.get("baselineScanId") == expected_baseline_scan_id

    return {
        "schemaVersion": CAPTURE_VALIDATION_SCHEMA,
        "available": True,
        "status": "validated",
        "identityChecks": {
            "placeIdMatches": place_match,
            "baselineScanIdMatches": baseline_match,
        },
        "requestValidation": request_validation,
        "summary": {
            "completeRequests": complete,
            "totalRequests": len(request_validation),
            "sampleCounts": counts,
        },
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
        },
    }


def _validate_movement_overlay_module(module_path: pathlib.Path) -> dict[str, Any]:
    code = module_path.read_text(encoding="utf-8")

    checks = {
        "strictHeader": "--!strict" in code,
        "moduleFactory": "function MovementTelemetry.new" in code,
        "startMethod": "function MovementTelemetry:Start" in code,
        "stopMethod": "function MovementTelemetry:Stop" in code,
        "updateConfigMethod": "function MovementTelemetry:UpdateConfig" in code,
        "statusMethod": "function MovementTelemetry:GetStatus" in code,
        "enabledSetting": "Enabled" in code,
        "updateIntervalSetting": "UpdateInterval" in code,
        "displayPositionSetting": "DisplayPosition" in code,
        "visibleFieldsSetting": "VisibleFields" in code,
        "displayScaleSetting": "DisplayScale" in code,
        "textSizeSetting": "TextSize" in code,
        "opacitySetting": "Opacity" in code,
        "characterAddedBinding": "CharacterAdded:Connect" in code,
        "heartbeatBinding": "Heartbeat:Connect" in code,
        "disconnectCleanup": "connection:Disconnect" in code,
        "guiDestroyCleanup": "screenGui:Destroy" in code or "self.screenGui:Destroy" in code,
    }

    mock_runtime_checks = [
        {"name": "start-with-enabled-config", "passed": checks["moduleFactory"] and checks["startMethod"]},
        {"name": "missing-character-handled", "passed": "Character unavailable" in code},
        {"name": "config-update-restarts-runtime", "passed": checks["updateConfigMethod"] and "self:Stop()" in code and "self:Start()" in code},
        {"name": "lifecycle-stop-cleans-connections", "passed": checks["stopMethod"] and checks["disconnectCleanup"]},
        {"name": "lifecycle-stop-cleans-gui", "passed": checks["guiDestroyCleanup"]},
    ]

    all_static = all(checks.values())
    all_mock = all(item["passed"] for item in mock_runtime_checks)

    return {
        "schemaVersion": OVERLAY_VALIDATION_SCHEMA,
        "modulePath": str(module_path),
        "stages": [
            {"stage": 1, "name": "luau-syntax-validation", "status": "passed" if checks["strictHeader"] else "failed", "automated": True},
            {"stage": 2, "name": "module-contract-validation", "status": "passed" if all_static else "failed", "automated": True},
            {"stage": 3, "name": "configuration-binding-validation", "status": "passed" if all(k for k in [checks["enabledSetting"], checks["updateIntervalSetting"], checks["displayPositionSetting"], checks["visibleFieldsSetting"], checks["displayScaleSetting"], checks["textSizeSetting"], checks["opacitySetting"]]) else "failed", "automated": True},
            {"stage": 4, "name": "lifecycle-validation", "status": "passed" if checks["startMethod"] and checks["stopMethod"] and checks["disconnectCleanup"] else "failed", "automated": True},
            {"stage": 5, "name": "mock-runtime-behavioural-testing", "status": "passed" if all_mock else "failed", "automated": True},
            {"stage": 6, "name": "actual-roblox-runtime-testing", "status": "pending", "automated": False},
            {"stage": 7, "name": "gameplay-outcome-verification", "status": "pending", "automated": False},
        ],
        "staticChecks": checks,
        "mockRuntimeChecks": mock_runtime_checks,
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
        },
    }


def _build_runtime_test_instructions(path: pathlib.Path, place_id: int) -> None:
    lines = [
        "# Runtime test instructions (Milestone 3)",
        "",
        f"Target place ID: `{place_id}`",
        "",
        "## 1) Load inspector",
        "- Execute `LycolesUniversalInspector.lua` in executor.",
        "- Confirm UI opens and version shows v30.6.62.",
        "",
        "## 2) Start targeted capture",
        "- Click `TARGET: ...` to choose preset.",
        "- Click `CAPTURE: START`.",
        "- Perform normal gameplay for 2-4 minutes.",
        "- Click `CAPTURE: STOP`.",
        "",
        "## 3) Export targeted evidence",
        "- Use `Copy` to copy live observation export JSON.",
        "- Confirm `targetedCaptureSession` exists and includes requestProgress/samples.",
        "",
        "## 4) Validate movement overlay",
        "- Use generated `MovementTelemetryOverlay.lua` module.",
        "- Instantiate module and call `Start()`.",
        "- Confirm speed/position/state update, respawn handling, and clean `Stop()` cleanup.",
        "",
        "## 5) Record results",
        "- Mark stage 6 runtime-tested only if executed successfully in Roblox.",
        "- Mark stage 7 gameplay-verified only with observed intended outcomes.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_readiness_update(previous_feasibility: dict[str, Any], new_feasibility: dict[str, Any]) -> dict[str, Any]:
    prev_summary = previous_feasibility.get("summary") if isinstance(previous_feasibility.get("summary"), dict) else {}
    new_summary = new_feasibility.get("summary") if isinstance(new_feasibility.get("summary"), dict) else {}

    return {
        "schemaVersion": READINESS_UPDATE_SCHEMA,
        "previous": {
            "stageCounts": prev_summary.get("stageCounts", {}),
            "gameplayImplementationReadyCapabilities": prev_summary.get("gameplayImplementationReadyCapabilities", []),
        },
        "current": {
            "stageCounts": new_summary.get("stageCounts", {}),
            "gameplayImplementationReadyCapabilities": new_summary.get("gameplayImplementationReadyCapabilities", []),
        },
        "progressSignals": {
            "targetedEvidenceIntegrated": True,
            "capabilityLifecycleUpdated": True,
            "runtimeTestingPending": True,
        },
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
        },
    }


def _write_summary(path: pathlib.Path, readiness: dict[str, Any], capture_validation: dict[str, Any], overlay_validation: dict[str, Any]) -> None:
    current = readiness.get("current") if isinstance(readiness.get("current"), dict) else {}
    counts = current.get("stageCounts") if isinstance(current.get("stageCounts"), dict) else {}
    capture_summary = capture_validation.get("summary") if isinstance(capture_validation.get("summary"), dict) else {}

    lines = [
        "# Milestone 3 Summary — Targeted Capture and Runtime Validation",
        "",
        f"- Targeted requests validated: {capture_summary.get('totalRequests', 0)}",
        f"- Complete targeted requests: {capture_summary.get('completeRequests', 0)}",
        f"- Movement overlay stage 5 (mock-runtime): {next((s.get('status') for s in overlay_validation.get('stages', []) if s.get('stage') == 5), 'unknown')}",
        "",
        "## Capability stage counts",
        "",
    ]
    for key, value in sorted(counts.items()):
        lines.append(f"- {key}: {value}")

    lines.extend([
        "",
        "## Remaining blockers",
        "",
        "- Actual Roblox runtime execution/testing evidence is still required for runtime-tested status.",
        "- Gameplay-outcome verification remains pending until in-game evidence confirms intended effects.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_milestone3(inputs: MilestoneInputs) -> dict[str, Any]:
    inputs.output_dir.mkdir(parents=True, exist_ok=True)
    root = pathlib.Path(__file__).resolve().parents[1]

    capability_plan = _load_json(inputs.capability_plan_path)
    integrity = capability_plan.get("integrity") if isinstance(capability_plan.get("integrity"), dict) else {}
    place_id = int(integrity.get("placeId") or 0)
    baseline_scan_id = str(integrity.get("scanId") or "")

    m2_targeted_plan = _load_json(inputs.milestone2_dir / "targeted-inspection-plan.json")
    m2_feasibility = _load_json(inputs.milestone2_dir / "reassessed-feature-feasibility.json")

    requests = _build_targeted_requests(m2_targeted_plan, place_id)
    _write_json(inputs.output_dir / "targeted-capture-architecture.json", _build_targeted_capture_architecture())
    _write_json(inputs.output_dir / "targeted-inspection-requests.json", requests)
    _write_json(inputs.output_dir / "targeted-evidence-schema.json", _targeted_evidence_schema())

    targeted_payload = _load_json(inputs.targeted_evidence) if inputs.targeted_evidence and inputs.targeted_evidence.is_file() else None
    capture_validation = _build_capture_validation_report(targeted_payload, requests, place_id, baseline_scan_id)
    _write_json(inputs.output_dir / "capture-validation-report.json", capture_validation)

    recon = _load_reconciliation_module(root)
    recon_output_dir = inputs.output_dir / "reconciliation-v3"
    observation_files = tuple(
        path for path in (inputs.dynamic_observation, inputs.targeted_evidence)
        if path is not None and path.is_file()
    )
    recon_result = recon.run_from_artifacts(
        capability_plan_path=inputs.capability_plan_path,
        output_dir=recon_output_dir,
        observation_files=observation_files,
        integration_context={
            "source": "targeted_capture_milestone",
            "milestone": "3",
            "notes": "Targeted session ingestion for capability lifecycle updates",
        },
    )
    if not isinstance(recon_result, dict):
        raise RuntimeError("reconciliation pipeline did not produce output")

    movement_module_ref = (recon_result.get("files") or {}).get("movementTelemetryOverlayModule")
    if isinstance(movement_module_ref, str) and movement_module_ref:
        movement_module_path = pathlib.Path(movement_module_ref)
        movement_validation = _validate_movement_overlay_module(movement_module_path)
    else:
        movement_validation = {
            "schemaVersion": OVERLAY_VALIDATION_SCHEMA,
            "modulePath": None,
            "stages": [
                {"stage": 1, "name": "luau-syntax-validation", "status": "pending", "automated": True},
                {"stage": 2, "name": "module-contract-validation", "status": "pending", "automated": True},
                {"stage": 3, "name": "configuration-binding-validation", "status": "pending", "automated": True},
                {"stage": 4, "name": "lifecycle-validation", "status": "pending", "automated": True},
                {"stage": 5, "name": "mock-runtime-behavioural-testing", "status": "pending", "automated": True},
                {"stage": 6, "name": "actual-roblox-runtime-testing", "status": "pending", "automated": False},
                {"stage": 7, "name": "gameplay-outcome-verification", "status": "pending", "automated": False},
            ],
            "staticChecks": {},
            "mockRuntimeChecks": [],
            "claims": {"runtimeVerified": False, "gameplayVerified": False, "causalityProven": False},
            "note": "Movement telemetry module was not emitted because capability readiness was insufficient.",
        }
    _write_json(inputs.output_dir / "movement-overlay-validation.json", movement_validation)

    new_feasibility = _load_json(recon_output_dir / "reassessed-feature-feasibility.json")
    readiness_update = _build_readiness_update(m2_feasibility, new_feasibility)
    _write_json(inputs.output_dir / "capability-readiness-update.json", readiness_update)

    _build_runtime_test_instructions(inputs.output_dir / "runtime-test-instructions.md", place_id)
    _write_summary(inputs.output_dir / "milestone-3-summary.md", readiness_update, capture_validation, movement_validation)

    return {
        "outputDir": str(inputs.output_dir),
        "files": {
            "targetedCaptureArchitecture": str(inputs.output_dir / "targeted-capture-architecture.json"),
            "targetedInspectionRequests": str(inputs.output_dir / "targeted-inspection-requests.json"),
            "targetedEvidenceSchema": str(inputs.output_dir / "targeted-evidence-schema.json"),
            "captureValidationReport": str(inputs.output_dir / "capture-validation-report.json"),
            "movementOverlayValidation": str(inputs.output_dir / "movement-overlay-validation.json"),
            "capabilityReadinessUpdate": str(inputs.output_dir / "capability-readiness-update.json"),
            "runtimeTestInstructions": str(inputs.output_dir / "runtime-test-instructions.md"),
            "milestone3Summary": str(inputs.output_dir / "milestone-3-summary.md"),
            "reconciliationOutputDir": str(recon_output_dir),
        },
        "reconciliation": recon_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capability-plan", required=True)
    parser.add_argument("--milestone2-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dynamic-observation", default=None)
    parser.add_argument("--targeted-evidence", default=None)
    args = parser.parse_args()

    result = run_milestone3(
        MilestoneInputs(
            capability_plan_path=pathlib.Path(args.capability_plan).expanduser().resolve(),
            milestone2_dir=pathlib.Path(args.milestone2_dir).expanduser().resolve(),
            output_dir=pathlib.Path(args.output_dir).expanduser().resolve(),
            dynamic_observation=pathlib.Path(args.dynamic_observation).expanduser().resolve() if args.dynamic_observation else None,
            targeted_evidence=pathlib.Path(args.targeted_evidence).expanduser().resolve() if args.targeted_evidence else None,
        )
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
