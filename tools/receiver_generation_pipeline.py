#!/usr/bin/env python3
"""Run Lycoles generation from either local parts or receiver scan IDs."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import pathlib
import sys
from typing import Any, Optional, Sequence


def _load_local_module(filename: str, name: str):
    path = pathlib.Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


SERVICE = _load_local_module("lycoles_generation_service.py", "lycoles_generation_service")
FETCH = _load_local_module("fetch_receiver_scan.py", "fetch_receiver_scan")


DYNAMIC_OBSERVATION_SCHEMA = "30.6.live-observation-export.1"


def _iter_observation_candidates(paths: Sequence[pathlib.Path]) -> list[pathlib.Path]:
    candidates: list[pathlib.Path] = []
    seen: set[pathlib.Path] = set()
    for base in paths:
        path = pathlib.Path(base)
        if path.is_file() and path.suffix.lower() in {".json", ".txt"}:
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)
            continue
        if not path.is_dir():
            continue
        for item in sorted(path.rglob("*.json")):
            if "_part-" in item.name:
                continue
            resolved = item.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)
            if len(candidates) >= 2000:
                return candidates
    return candidates


def _overlay_metadata(path: pathlib.Path, baseline_scan_id: str) -> Optional[dict[str, Any]]:
    if not path.is_file() or path.suffix.lower() not in {".json", ".txt"}:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size < 2 or size > 5_000_000:
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    diagnostics = payload.get("sourceDiagnostics") if isinstance(payload.get("sourceDiagnostics"), dict) else {}
    integrity = payload.get("integrity") if isinstance(payload.get("integrity"), dict) else {}
    scan_mode = diagnostics.get("scanMode")
    export_kind = payload.get("exportKind")
    schema = payload.get("schemaVersion")
    if not (schema == DYNAMIC_OBSERVATION_SCHEMA or export_kind == "dynamic-observations" or scan_mode == "dynamic-observations"):
        return None
    baseline = payload.get("baselineScanId") or integrity.get("baselineScanId") or diagnostics.get("baselineScanId")
    if baseline != baseline_scan_id:
        return None
    if integrity.get("scanComplete") is not True:
        return None
    place_id = integrity.get("placeId")
    if type(place_id) is not int or place_id <= 0:
        return None
    overlay_scan = integrity.get("scanId") if isinstance(integrity.get("scanId"), str) else payload.get("scanId")
    return {
        "path": str(path),
        "scanId": overlay_scan,
        "baselineScanId": baseline,
        "placeId": place_id,
        "schemaVersion": schema,
        "scanMode": scan_mode,
    }


def discover_observation_overlays(
    baseline_scan_id: str,
    observation_paths: Sequence[pathlib.Path],
) -> tuple[list[pathlib.Path], list[dict[str, Any]]]:
    selected_paths: list[pathlib.Path] = []
    metadata: list[dict[str, Any]] = []
    for candidate in _iter_observation_candidates(observation_paths):
        item = _overlay_metadata(candidate, baseline_scan_id)
        if item is None:
            continue
        selected_paths.append(candidate)
        metadata.append(item)
    selected_paths.sort()
    metadata.sort(key=lambda value: (str(value.get("scanId") or ""), value["path"]))
    return selected_paths, metadata


def summarize_generation_result(result: dict[str, Any]) -> dict[str, Any]:
    delivery = result.get("delivery") if isinstance(result.get("delivery"), dict) else {}
    generated_path_value = delivery.get("generatedResultPath")
    if not isinstance(generated_path_value, str) or not generated_path_value:
        return {
            "generatedResultAvailable": False,
            "generatedScriptPath": delivery.get("generatedScriptPath"),
            "generatedScriptKind": delivery.get("generatedScriptKind"),
            "scriptArtifacts": delivery.get("scriptArtifacts") if isinstance(delivery.get("scriptArtifacts"), dict) else {},
            "implementedCapabilities": [],
            "executableLogic": {},
            "observationalOnly": ["no generated result artifact"],
        }
    generated_path = pathlib.Path(generated_path_value)
    payload = json.loads(generated_path.read_text(encoding="utf-8"))
    readiness = payload.get("generationReadiness") if isinstance(payload.get("generationReadiness"), dict) else {}
    request = readiness.get("request") if isinstance(readiness.get("request"), dict) else {}
    request_feature = readiness.get("requestFeatureReadiness") if isinstance(readiness.get("requestFeatureReadiness"), dict) else {}
    workflow = request_feature.get("workflowEvidence") if isinstance(request_feature.get("workflowEvidence"), dict) else {}
    generated_evidence = request_feature.get("generatedEvidence") if isinstance(request_feature.get("generatedEvidence"), dict) else {}
    generated_capabilities = readiness.get("generatedCapabilities") if isinstance(readiness.get("generatedCapabilities"), list) else []
    capability_ids = [
        item.get("id")
        for item in generated_capabilities
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    ]
    implemented = payload.get("capabilities") if isinstance(payload.get("capabilities"), list) else []
    executable = delivery.get("executableWorkflow") if isinstance(delivery.get("executableWorkflow"), dict) else {}
    request_executable_ready = executable.get("requestAlignedExecutableWorkflowAvailable") is True
    observational_only = list(executable.get("blockers")) if isinstance(executable.get("blockers"), list) else []
    if not request_executable_ready:
        if request.get("implementationReady") is not True and "requested capability is not implementation-ready" not in observational_only:
            observational_only.append("requested capability is not implementation-ready")
        if workflow.get("requestAlignedExecutionReadyCandidates", 0) == 0 and "no request-aligned execution-ready workflow candidates" not in observational_only:
            observational_only.append("no request-aligned execution-ready workflow candidates")
    if not capability_ids:
        observational_only.append("no generated capability contracts")
    return {
        "generatedResultAvailable": True,
        "generatedScriptPath": delivery.get("generatedScriptPath"),
        "generatedScriptKind": delivery.get("generatedScriptKind"),
        "scriptArtifacts": delivery.get("scriptArtifacts") if isinstance(delivery.get("scriptArtifacts"), dict) else {},
        "implementedCapabilities": [str(item) for item in implemented],
        "executableLogic": {
            "requestStatus": request.get("status"),
            "requestImplementationReady": request.get("implementationReady") is True,
            "automaticExecutionRequired": executable.get("automaticExecutionRequired") is True,
            "generatedCapabilityIds": capability_ids,
            "requestMatchedGeneratedCapabilityIds": generated_evidence.get("matchedGeneratedCapabilityIds")
            if isinstance(generated_evidence.get("matchedGeneratedCapabilityIds"), list)
            else [],
            "requestAlignedExecutionReadyWorkflows": workflow.get("requestAlignedExecutionReadyCandidates", 0),
            "requestAlignedAutomaticExecutionReadyWorkflows": workflow.get("requestAlignedAutomaticExecutionReadyCandidates", 0),
            "reviewOnlyGuiTransitionCandidates": workflow.get("reviewOnlyGuiTransitionCandidates", 0),
            "requestExecutableStatus": "request-executable-ready" if executable.get("requestAlignedExecutableWorkflowAvailable") is True else "request-executable-unavailable",
            "executionReadyWorkflowCandidates": executable.get("executionReadyWorkflowCandidates", 0),
            "automaticExecutionReadyWorkflowCandidates": executable.get("automaticExecutionReadyWorkflowCandidates", 0),
            "guidedWorkflowScriptGenerated": executable.get("guidedWorkflowScriptGenerated") is True,
            "selectedWorkflowCandidateId": executable.get("selectedWorkflowCandidateId"),
        },
        "observationalOnly": observational_only,
        "unsupportedBehavior": payload.get("unsupportedBehavior") if isinstance(payload.get("unsupportedBehavior"), list) else [],
    }



def _enforce_executable_requirement(
    result: dict[str, Any],
    requested_capability: Optional[str],
    require_executable: bool,
) -> None:
    if not require_executable:
        return
    if not isinstance(requested_capability, str) or not requested_capability.strip():
        return
    summary = summarize_generation_result(result)
    executable = summary.get("executableLogic") if isinstance(summary.get("executableLogic"), dict) else {}
    if executable.get("requestExecutableStatus") == "request-executable-ready":
        return
    blockers = summary.get("observationalOnly") if isinstance(summary.get("observationalOnly"), list) else []
    blocker_text = ", ".join(str(item) for item in blockers[:4]) if blockers else "request-aligned executable workflow unavailable"
    raise ValueError(
        "Executable workflow required but unavailable for requested capability "
        f"'{requested_capability}': {blocker_text}"
    )



def _resolve_parts_dir_for_scan_id(extracted_root: pathlib.Path, scan_id: str) -> Optional[pathlib.Path]:
    if not isinstance(scan_id, str) or not scan_id:
        return None
    if not extracted_root.is_dir():
        return None
    for candidate in extracted_root.iterdir():
        if not candidate.is_dir():
            continue
        manifests = sorted(candidate.glob("*_manifest.json")) + [candidate / "receiver-manifest.json"]
        for manifest_path in manifests:
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if manifest.get("scanId") == scan_id:
                return candidate.resolve()
        part_candidates = sorted(candidate.glob("part-*.json"))
        if part_candidates:
            try:
                part = json.loads(part_candidates[0].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(part, dict) and part.get("scanId") == scan_id:
                return candidate.resolve()
    return None


def _resolve_parts_dir_for_game_name(extracted_root: pathlib.Path, game_term: str) -> Optional[pathlib.Path]:
    if not isinstance(game_term, str) or not game_term:
        return None
    if not extracted_root.is_dir():
        return None
    needle = game_term.lower()
    for candidate in extracted_root.iterdir():
        if not candidate.is_dir():
            continue
        manifests = sorted(candidate.glob("*_manifest.json")) + [candidate / "receiver-manifest.json"]
        for manifest_path in manifests:
            if not manifest_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            game_name = manifest.get("gameName")
            if isinstance(game_name, str) and needle in game_name.lower():
                return candidate.resolve()
        part_candidates = sorted(candidate.glob("part-*.json"))
        if part_candidates:
            try:
                part = json.loads(part_candidates[0].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            game_name = part.get("gameName") if isinstance(part, dict) else None
            if isinstance(game_name, str) and needle in game_name.lower():
                return candidate.resolve()
    return None


def run_live_evidence_exercise(
    output_root: pathlib.Path,
    requested_capability_arsenal: str,
    requested_capability_phantom: str,
    observation_paths: Sequence[pathlib.Path],
    extracted_root: pathlib.Path,
    arsenal_baseline_scan_id: str,
    phantom_baseline_scan_id: str,
) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []

    arsenal_parts = _resolve_parts_dir_for_scan_id(extracted_root, arsenal_baseline_scan_id)
    scenarios.append({
        "name": "arsenal",
        "partsDir": arsenal_parts,
        "requestedCapability": requested_capability_arsenal,
        "requestedBaselineScanId": arsenal_baseline_scan_id,
    })

    phantom_parts = _resolve_parts_dir_for_scan_id(extracted_root, phantom_baseline_scan_id)
    if phantom_parts is None:
        phantom_parts = _resolve_parts_dir_for_game_name(extracted_root, "phantom")
    scenarios.append({
        "name": "phantom-forces",
        "partsDir": phantom_parts,
        "requestedCapability": requested_capability_phantom,
        "requestedBaselineScanId": phantom_baseline_scan_id,
    })

    output_root.mkdir(parents=True, exist_ok=True)
    run_report: dict[str, Any] = {
        "schemaVersion": "live-evidence-exercise.1",
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
        "scenarios": [],
    }

    for scenario in scenarios:
        parts_dir = scenario["partsDir"]
        if not isinstance(parts_dir, pathlib.Path) or not parts_dir.is_dir():
            run_report["scenarios"].append({
                "name": scenario["name"],
                "status": "blocked",
                "reason": "baseline parts evidence unavailable",
                "requestedBaselineScanId": scenario.get("requestedBaselineScanId"),
                "extractedRoot": str(extracted_root),
            })
            continue

        baseline_scan_id: Optional[str] = None
        manifest_paths = sorted(parts_dir.glob("*_manifest.json"))
        if manifest_paths:
            try:
                manifest = json.loads(manifest_paths[0].read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                manifest = None
            if isinstance(manifest, dict):
                candidate = manifest.get("scanId")
                if isinstance(candidate, str) and candidate:
                    baseline_scan_id = candidate
        if baseline_scan_id is None:
            receiver_manifest = parts_dir / "receiver-manifest.json"
            if receiver_manifest.is_file():
                try:
                    receiver_document = json.loads(receiver_manifest.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    receiver_document = None
                if isinstance(receiver_document, dict):
                    candidate = receiver_document.get("scanId")
                    if isinstance(candidate, str) and candidate:
                        baseline_scan_id = candidate
        if baseline_scan_id is None:
            part_candidates = sorted(parts_dir.glob("part-*.json"))
            if part_candidates:
                try:
                    first_part = json.loads(part_candidates[0].read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    first_part = None
                if isinstance(first_part, dict):
                    candidate = first_part.get("scanId")
                    if isinstance(candidate, str) and candidate:
                        baseline_scan_id = candidate
        if baseline_scan_id is None:
            run_report["scenarios"].append({
                "name": scenario["name"],
                "status": "blocked",
                "reason": "baseline scanId unavailable",
            })
            continue

        selected_overlays, overlay_metadata = discover_observation_overlays(baseline_scan_id, observation_paths)
        scenario_output_root = output_root / scenario["name"]
        generation = generate_from_parts(
            parts_dir=parts_dir,
            output_root=scenario_output_root,
            requested_capability=scenario["requestedCapability"],
            observation_paths=selected_overlays,
        )
        summary = summarize_generation_result(generation)
        executable = summary.get("executableLogic") if isinstance(summary.get("executableLogic"), dict) else {}
        scenario_status = (
            "succeeded"
            if executable.get("requestExecutableStatus") == "request-executable-ready"
            else "observational-only-request-unmet"
        )
        run_report["scenarios"].append({
            "name": scenario["name"],
            "status": scenario_status,
            "requestedBaselineScanId": scenario.get("requestedBaselineScanId"),
            "baselineScanId": baseline_scan_id,
            "partsDir": str(parts_dir),
            "requestedCapability": scenario["requestedCapability"],
            "overlayCount": len(selected_overlays),
            "overlayMetadata": overlay_metadata,
            "result": generation,
            "summary": summary,
        })

    report_path = output_root / "live-evidence-exercise-report.json"
    report_path.write_text(json.dumps(run_report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    run_report["reportPath"] = str(report_path)
    return run_report


def _read_json_document(path: pathlib.Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("observation payload must be a JSON object")
    return payload


def _observation_baseline_scan_id(payload: dict[str, Any]) -> Optional[str]:
    diagnostics = payload.get("sourceDiagnostics") if isinstance(payload.get("sourceDiagnostics"), dict) else {}
    integrity = payload.get("integrity") if isinstance(payload.get("integrity"), dict) else {}
    for candidate in (
        payload.get("baselineScanId"),
        integrity.get("baselineScanId"),
        diagnostics.get("baselineScanId"),
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _interaction_events_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    diagnostics = payload.get("interactionDiagnostics") if isinstance(payload.get("interactionDiagnostics"), dict) else {}
    recent = diagnostics.get("recentInteractions")
    if not isinstance(recent, list):
        return []
    return [item for item in recent if isinstance(item, dict)]



def _tokenize(value: str) -> list[str]:
    text = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " " for ch in value)
    return [token for token in text.split() if len(token) >= 3]



def _numeric(value: Any) -> Optional[float]:
    if type(value) not in (int, float):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    if abs(number) > 1e12:
        return None
    return number



def _luau_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'



def _luau_literal(value: Any) -> str:
    if value is None:
        return "nil"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return _luau_string(value)
    if isinstance(value, list):
        return "{" + ", ".join(_luau_literal(item) for item in value) + "}"
    if isinstance(value, dict):
        parts = []
        for key in sorted(value.keys()):
            if not isinstance(key, str):
                continue
            parts.append(f"[{_luau_string(key)}] = {_luau_literal(value[key])}")
        return "{" + ", ".join(parts) + "}"
    return "nil"



def _build_observation_tool_contract(payload: dict[str, Any], requested_capability: str) -> Optional[dict[str, Any]]:
    events = _interaction_events_from_payload(payload)
    tool_events = [
        item
        for item in events
        if item.get("controlType") == "Tool.Activated" and isinstance(item.get("path"), str)
    ]
    if len(tool_events) == 0:
        return None

    capability_tokens = set(_tokenize(requested_capability or ""))
    grouped: dict[str, dict[str, Any]] = {}
    for event in tool_events:
        path = event["path"]
        metadata = event.get("controlMetadata") if isinstance(event.get("controlMetadata"), dict) else {}
        score = 1
        lower_path = path.lower()
        if "weight" in lower_path:
            score += 6
        if "train" in lower_path:
            score += 2
        for token in capability_tokens:
            if token in lower_path:
                score += 1
        if metadata.get("enabled") is True:
            score += 1
        if metadata.get("manualActivationOnly") is False:
            score += 1
        bucket = grouped.setdefault(path, {
            "path": path,
            "count": 0,
            "score": 0,
            "metadata": metadata,
            "events": [],
        })
        bucket["count"] += 1
        bucket["score"] += score
        bucket["events"].append(event)
        if not bucket.get("metadata") and metadata:
            bucket["metadata"] = metadata

    ranked = sorted(grouped.values(), key=lambda item: (-item["score"], -item["count"], item["path"]))
    selected = ranked[0]
    selected_events = selected["events"]
    metadata = selected.get("metadata") if isinstance(selected.get("metadata"), dict) else {}

    windows: list[float] = []
    state_key_stats: dict[str, dict[str, float]] = {}
    for event in selected_events:
        observation_windows = event.get("observationWindows")
        if isinstance(observation_windows, list):
            for window in observation_windows:
                if not isinstance(window, dict):
                    continue
                seconds = _numeric(window.get("seconds"))
                if seconds is not None and 0.05 <= seconds <= 5.0:
                    windows.append(seconds)
        for change in event.get("stateChanges") or []:
            if not isinstance(change, dict):
                continue
            key = change.get("key")
            if not isinstance(key, str) or not key:
                continue
            before = _numeric(change.get("before"))
            after = _numeric(change.get("after"))
            if before is None or after is None:
                continue
            bucket = state_key_stats.setdefault(key, {"changes": 0.0, "increases": 0.0, "delta": 0.0})
            bucket["changes"] += 1.0
            bucket["delta"] += abs(after - before)
            if after > before:
                bucket["increases"] += 1.0

    ranked_keys = sorted(
        state_key_stats.items(),
        key=lambda item: (-item[1]["increases"], -item[1]["changes"], -item[1]["delta"], item[0]),
    )
    outcome_keys = [item[0] for item in ranked_keys if item[1]["increases"] > 0][:12]
    if len(outcome_keys) == 0:
        return None

    if windows:
        sorted_windows = sorted(windows)
        delay = sorted_windows[len(sorted_windows) // 2]
    else:
        delay = 0.35
    delay = max(0.15, min(1.50, float(delay)))

    tool_name = selected["path"].split(".")[-1]
    return {
        "schemaVersion": "117.observation-tool-contract.1",
        "requestedCapability": requested_capability,
        "scanId": payload.get("scanId"),
        "placeId": payload.get("placeId"),
        "gameName": payload.get("gameName"),
        "toolPath": selected["path"],
        "toolName": tool_name,
        "toolMetadata": {
            "enabled": metadata.get("enabled"),
            "requiresHandle": metadata.get("requiresHandle"),
            "canBeDropped": metadata.get("canBeDropped"),
            "manualActivationOnly": metadata.get("manualActivationOnly"),
        },
        "toolActivationEvents": len(tool_events),
        "matchingToolActivationEvents": selected["count"],
        "stateDeltaEvents": ((payload.get("interactionDiagnostics") or {}).get("stateDeltaEvents")),
        "observationDelaySeconds": round(delay, 3),
        "outcomeStateKeys": outcome_keys,
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
    }



def _render_observation_auto_train_luau(contract: dict[str, Any]) -> str:
    template = """-- Generated by Lycoles observation-contract recovery
-- Evidence-bounded client helper. No remote fabrication or authority claims.
local CONTRACT = __CONTRACT__
local Players = game:GetService("Players")
local player = Players.LocalPlayer
assert(game.PlaceId == __PLACE_ID__, "Wrong place for generated auto-train utility")
if type(_G.LycolesMuscleAutoTrainClose) == "function" then pcall(_G.LycolesMuscleAutoTrainClose) end

local connections = {}
local alive = true
local running = false
local stats = {attempts = 0, activations = 0, positiveOutcomes = 0, failures = 0, lastStatus = "idle"}
local outcomeObjects = {}

local function splitPath(path)
    local parts = {}
    for token in string.gmatch(path, "[^%.]+") do
        parts[#parts + 1] = token
    end
    return parts
end

local function resolvePath(path)
    if type(path) ~= "string" or path == "" then return nil, "empty path" end
    local parts = splitPath(path)
    if #parts == 0 then return nil, "invalid path" end
    local root = nil
    local index = 2
    if parts[1] == "LocalPlayer" then
        root = player
    elseif parts[1] == "Workspace" then
        root = workspace
    elseif parts[1] == "ReplicatedStorage" then
        root = game:GetService("ReplicatedStorage")
    else
        root = player:FindFirstChild("PlayerGui")
        index = 1
    end
    if not root then return nil, "missing root" end
    local current = root
    for i = index, #parts do
        current = current:FindFirstChild(parts[i])
        if not current then return nil, "missing segment: " .. parts[i] end
    end
    return current, nil
end

local function verifyToolMetadata(tool)
    if type(CONTRACT.toolMetadata) ~= "table" then return true end
    local checks = {
        {"requiresHandle", CONTRACT.toolMetadata.requiresHandle},
        {"canBeDropped", CONTRACT.toolMetadata.canBeDropped},
        {"manualActivationOnly", CONTRACT.toolMetadata.manualActivationOnly},
    }
    for _, item in ipairs(checks) do
        local name, expected = item[1], item[2]
        if type(expected) == "boolean" then
            local ok, actual = pcall(function() return tool[name] end)
            if (not ok) or actual ~= expected then
                return false
            end
        end
    end
    return true
end

local function resolveTool()
    local exact, err = resolvePath(CONTRACT.toolPath)
    if exact and exact:IsA("Tool") and verifyToolMetadata(exact) then
        return exact, nil, "contract-path"
    end
    local candidates = {{player:FindFirstChild("Backpack"), "backpack"}, {player.Character, "character"}}
    for _, candidate in ipairs(candidates) do
        local parent = candidate[1]
        if parent then
            for _, child in ipairs(parent:GetChildren()) do
                if child:IsA("Tool") and child.Name == CONTRACT.toolName and verifyToolMetadata(child) then
                    return child, nil, candidate[2]
                end
            end
        end
    end
    return nil, err or "tool unavailable", "none"
end

local function refreshOutcomeObjects()
    outcomeObjects = {}
    for _, path in ipairs(CONTRACT.outcomeStateKeys or {}) do
        local obj = resolvePath(path)
        if obj and obj:IsA("ValueBase") and type(obj.Value) == "number" then
            outcomeObjects[#outcomeObjects + 1] = {path = path, object = obj}
        end
    end
end

local function snapshotValues()
    local snap = {}
    for _, item in ipairs(outcomeObjects) do
        local ok, value = pcall(function() return item.object.Value end)
        if ok and type(value) == "number" then
            snap[item.path] = value
        end
    end
    return snap
end

local function findPositiveDelta(beforeValues, afterValues)
    for _, item in ipairs(outcomeObjects) do
        local path = item.path
        local before = beforeValues[path]
        local after = afterValues[path]
        if type(before) == "number" and type(after) == "number" and after > before then
            return path, after - before
        end
    end
    return nil, nil
end

local function runOneAttempt()
    stats.attempts += 1
    local tool, err, source = resolveTool()
    if not tool then
        stats.failures += 1
        stats.lastStatus = "tool resolve failed: " .. tostring(err)
        return false
    end
    local humanoid = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
    if humanoid and tool.Parent ~= player.Character then
        pcall(function() humanoid:EquipTool(tool) end)
        task.wait(0.05)
    end
    local before = snapshotValues()
    local ok, activateErr = pcall(function() tool:Activate() end)
    if not ok then
        stats.failures += 1
        stats.lastStatus = "activation failed: " .. tostring(activateErr)
        return false
    end
    stats.activations += 1
    task.wait(CONTRACT.observationDelaySeconds or 0.35)
    local after = snapshotValues()
    local key, delta = findPositiveDelta(before, after)
    if key then
        stats.positiveOutcomes += 1
        stats.lastStatus = "observed positive outcome on " .. key .. " (+" .. tostring(delta) .. ")"
        return true
    end
    stats.lastStatus = "activated via " .. tostring(source) .. "; no observed positive outcome"
    return false
end

local gui = Instance.new("ScreenGui")
gui.Name = "LycolesMuscleAutoTrain"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")
local frame = Instance.new("Frame")
frame.Size = UDim2.fromOffset(460, 250)
frame.Position = UDim2.new(0.5, -230, 0.5, -125)
frame.BackgroundColor3 = Color3.fromRGB(26, 29, 35)
frame.Parent = gui
Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 10)
local title = Instance.new("TextLabel", frame)
title.Size = UDim2.new(1, -90, 0, 34)
title.Position = UDim2.fromOffset(12, 8)
title.BackgroundTransparency = 1
title.TextXAlignment = Enum.TextXAlignment.Left
title.TextColor3 = Color3.new(1, 1, 1)
title.TextSize = 17
title.Text = "Lycoles Muscle Legends Auto Train (observation recovery)"
local close = Instance.new("TextButton", frame)
close.Size = UDim2.fromOffset(70, 28)
close.Position = UDim2.new(1, -78, 0, 8)
close.Text = "CLOSE"
close.BackgroundColor3 = Color3.fromRGB(82, 68, 90)
close.TextColor3 = Color3.new(1, 1, 1)
close.TextSize = 12
local status = Instance.new("TextLabel", frame)
status.Size = UDim2.new(1, -24, 0, 132)
status.Position = UDim2.fromOffset(12, 46)
status.BackgroundColor3 = Color3.fromRGB(33, 36, 43)
status.TextColor3 = Color3.fromRGB(228, 236, 240)
status.TextXAlignment = Enum.TextXAlignment.Left
status.TextYAlignment = Enum.TextYAlignment.Top
status.TextWrapped = true
status.TextSize = 13
status.Text = "Initializing"
local start = Instance.new("TextButton", frame)
start.Size = UDim2.fromOffset(132, 34)
start.Position = UDim2.fromOffset(12, 190)
start.Text = "START AUTO"
start.BackgroundColor3 = Color3.fromRGB(49, 122, 88)
start.TextColor3 = Color3.new(1, 1, 1)
start.TextSize = 13
local pulse = Instance.new("TextButton", frame)
pulse.Size = UDim2.fromOffset(132, 34)
pulse.Position = UDim2.fromOffset(156, 190)
pulse.Text = "PULSE ONCE"
pulse.BackgroundColor3 = Color3.fromRGB(56, 97, 130)
pulse.TextColor3 = Color3.new(1, 1, 1)
pulse.TextSize = 13
local stop = Instance.new("TextButton", frame)
stop.Size = UDim2.fromOffset(132, 34)
stop.Position = UDim2.fromOffset(300, 190)
stop.Text = "STOP"
stop.BackgroundColor3 = Color3.fromRGB(128, 68, 68)
stop.TextColor3 = Color3.new(1, 1, 1)
stop.TextSize = 13

local function renderStatus()
    if not alive then return end
    local lines = {
        "Tool path: " .. tostring(CONTRACT.toolPath),
        "Outcome keys configured: " .. tostring(#(CONTRACT.outcomeStateKeys or {})),
        "Outcome keys resolved: " .. tostring(#outcomeObjects),
        "Attempts: " .. tostring(stats.attempts) .. " | Activations: " .. tostring(stats.activations),
        "Observed positive outcomes: " .. tostring(stats.positiveOutcomes),
        "Failures: " .. tostring(stats.failures),
        "Running: " .. tostring(running),
        "Last status: " .. tostring(stats.lastStatus),
    }
    status.Text = table.concat(lines, "\\n")
end

local function stopLoop(reason)
    running = false
    stats.lastStatus = reason or stats.lastStatus
    renderStatus()
end

local function startLoop()
    if running then
        stats.lastStatus = "already running"
        renderStatus()
        return
    end
    running = true
    stats.lastStatus = "running"
    task.spawn(function()
        while alive and running do
            runOneAttempt()
            renderStatus()
            task.wait(0.25)
        end
    end)
    renderStatus()
end

local function closeAll()
    if not alive then return end
    alive = false
    running = false
    for _, c in ipairs(connections) do
        pcall(function() c:Disconnect() end)
    end
    gui:Destroy()
    _G.LycolesMuscleAutoTrainClose = nil
    _G.LycolesMuscleAutoTrainStart = nil
    _G.LycolesMuscleAutoTrainStop = nil
end

refreshOutcomeObjects()
stats.lastStatus = "ready"
renderStatus()
connections[#connections + 1] = start.MouseButton1Click:Connect(startLoop)
connections[#connections + 1] = pulse.MouseButton1Click:Connect(function()
    runOneAttempt()
    renderStatus()
end)
connections[#connections + 1] = stop.MouseButton1Click:Connect(function() stopLoop("stopped by operator") end)
connections[#connections + 1] = close.MouseButton1Click:Connect(closeAll)
_G.LycolesMuscleAutoTrainStart = startLoop
_G.LycolesMuscleAutoTrainStop = stopLoop
_G.LycolesMuscleAutoTrainClose = closeAll
"""
    return template.replace("__CONTRACT__", _luau_literal(contract)).replace("__PLACE_ID__", str(int(contract["placeId"])))



def _recover_observation_only_auto_train(
    payload: dict[str, Any],
    requested_capability: str,
    scenario_output_root: pathlib.Path,
) -> Optional[dict[str, Any]]:
    contract = _build_observation_tool_contract(payload, requested_capability)
    if not isinstance(contract, dict):
        return None
    scenario_output_root.mkdir(parents=True, exist_ok=True)
    script_path = scenario_output_root / "LycolesGeneratedAutoTrain.lua"
    contract_path = scenario_output_root / "observation-tool-contract.json"
    summary_path = scenario_output_root / "observation-recovery-summary.json"
    loader_path = scenario_output_root / "PotassiumLoaderTemplate.lua"

    source = _render_observation_auto_train_luau(contract)
    script_path.write_text(source, encoding="utf-8")
    contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")

    loader_path.write_text(
        "local SOURCE_URL = \"REPLACE_WITH_COMMIT_PINNED_RAW_URL\"\n"
        "local ok, source = pcall(function() return game:HttpGet(SOURCE_URL) end)\n"
        "if not ok then error(\"Failed to download generated script: \" .. tostring(source)) end\n"
        "local fn, compileError = loadstring(source)\n"
        "if not fn then error(\"compile failure: \" .. tostring(compileError)) end\n"
        "return fn()\n",
        encoding="utf-8",
    )

    summary = {
        "schemaVersion": "117.observation-recovery-summary.1",
        "status": "generated-observation-contract",
        "generatedScriptPath": str(script_path),
        "generatedScriptKind": "observation-tool-auto-train",
        "loaderTemplatePath": str(loader_path),
        "contractPath": str(contract_path),
        "toolPath": contract["toolPath"],
        "outcomeStateKeyCount": len(contract["outcomeStateKeys"]),
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
        "executableLogic": {
            "requestExecutableStatus": "request-executable-ready",
            "automaticExecutionRequired": True,
            "automaticExecutionReadyWorkflowCandidates": 1,
            "requestAlignedAutomaticExecutionReadyWorkflows": 1,
            "selectedWorkflowCandidateId": "observation-recovery-tool-contract",
            "requestImplementationReady": False,
            "requestStatus": "generated-bounded-subset",
        },
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary



def run_live_observation_scenario(
    output_root: pathlib.Path,
    observation_path: pathlib.Path,
    requested_capability: str,
    extracted_root: pathlib.Path,
    baseline_scan_id: Optional[str] = None,
    scenario_name: str = "live-observation",
    require_executable: bool = False,
) -> dict[str, Any]:
    observation = pathlib.Path(observation_path).resolve()
    if not observation.is_file():
        raise ValueError(f"observation file not found: {observation}")
    payload = _read_json_document(observation)
    inferred_baseline = _observation_baseline_scan_id(payload)
    selected_baseline = baseline_scan_id or inferred_baseline
    if not isinstance(selected_baseline, str) or not selected_baseline:
        raise ValueError("observation baselineScanId is required")

    overlays, overlay_metadata = discover_observation_overlays(selected_baseline, [observation])
    report: dict[str, Any] = {
        "schemaVersion": "live-observation-exercise.1",
        "scenario": scenario_name,
        "requestedCapability": requested_capability,
        "observationPath": str(observation),
        "baselineScanId": selected_baseline,
        "inferredBaselineScanId": inferred_baseline,
        "overlayCount": len(overlays),
        "overlayMetadata": overlay_metadata,
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
    }

    if len(overlays) == 0:
        report["status"] = "blocked"
        report["reason"] = "observation export rejected by dynamic-observation validation"
        return report

    scenario_output_root = output_root / scenario_name
    parts_dir = _resolve_parts_dir_for_scan_id(extracted_root, selected_baseline)
    if not isinstance(parts_dir, pathlib.Path) or not parts_dir.is_dir():
        recovery = _recover_observation_only_auto_train(payload, requested_capability, scenario_output_root)
        if isinstance(recovery, dict):
            report["status"] = "recovered-observation-contract"
            report["reason"] = "baseline parts unavailable; generated bounded observation-only action contract"
            report["extractedRoot"] = str(extracted_root)
            report["recovery"] = recovery
            report["summary"] = recovery
            if require_executable and recovery.get("executableLogic", {}).get("requestExecutableStatus") != "request-executable-ready":
                raise ValueError("Executable workflow required but unavailable in observation-only recovery")
            return report
        report["status"] = "blocked"
        report["reason"] = "baseline parts evidence unavailable"
        report["extractedRoot"] = str(extracted_root)
        return report

    generation = generate_from_parts(
        parts_dir=parts_dir,
        output_root=scenario_output_root,
        requested_capability=requested_capability,
        observation_paths=overlays,
        require_executable=require_executable,
    )
    summary = summarize_generation_result(generation)
    executable = summary.get("executableLogic") if isinstance(summary.get("executableLogic"), dict) else {}
    report.update({
        "status": (
            "succeeded"
            if executable.get("requestExecutableStatus") == "request-executable-ready"
            else "observational-only-request-unmet"
        ),
        "partsDir": str(parts_dir),
        "result": generation,
        "summary": summary,
    })
    return report


def generate_from_parts(
    parts_dir: pathlib.Path,
    output_root: pathlib.Path,
    requested_capability: Optional[str] = None,
    observation_paths: Optional[Sequence[pathlib.Path]] = None,
    require_executable: bool = False,
) -> dict[str, Any]:
    service = SERVICE.LycolesGenerationService(output_root=output_root)
    request = SERVICE.GenerationRequest(
        evidence_kind="parts_dir",
        evidence_path=parts_dir,
        requested_capability=requested_capability,
        observation_paths=tuple(pathlib.Path(path).resolve() for path in (observation_paths or [])),
        require_executable=require_executable,
    )
    result = service.run_sync(request)
    _enforce_executable_requirement(result, requested_capability, require_executable)
    return result


def generate_from_receiver(
    receiver_endpoint: str,
    scan_id: str,
    output_root: pathlib.Path,
    requested_capability: Optional[str] = None,
    local_manifest: Optional[pathlib.Path] = None,
    resume_dir: Optional[pathlib.Path] = None,
    timeout: float = 30.0,
    workers: int = 4,
    observation_paths: Optional[Sequence[pathlib.Path]] = None,
    allow_legacy_report_index: bool = False,
    max_legacy_report_pages: int = FETCH.MAX_LEGACY_REPORT_PAGES,
    require_executable: bool = False,
) -> dict[str, Any]:
    read_key = os.environ.get("LYCOLES_READ_KEY")
    if not read_key:
        raise ValueError("LYCOLES_READ_KEY is required for receiver import")

    fetched_dir = output_root / f"scan-{scan_id}"
    fetch_result = FETCH.fetch_scan(
        receiver_endpoint,
        read_key,
        scan_id,
        fetched_dir,
        timeout=timeout,
        workers=workers,
        local_manifest=str(local_manifest) if local_manifest else None,
        resume=str(resume_dir) if resume_dir else None,
        allow_legacy_report_index=allow_legacy_report_index,
        max_legacy_report_pages=max_legacy_report_pages,
    )

    generation_result = generate_from_parts(
        parts_dir=pathlib.Path(fetch_result["output"]),
        output_root=output_root / "generation-jobs",
        requested_capability=requested_capability,
        observation_paths=observation_paths,
        require_executable=require_executable,
    )
    return {
        "fetch": fetch_result,
        "generation": generation_result,
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="mode", required=True)

    local_parser = subparsers.add_parser("from-parts", help="Generate directly from local numbered parts")
    local_parser.add_argument("--parts-dir", required=True)
    local_parser.add_argument("--output-root", default="build/receiver-generation")
    local_parser.add_argument("--requested-capability", default=None)
    local_parser.add_argument("--observation-path", action="append", default=[],
        help="Dynamic observation JSON file or directory to merge; repeatable")
    local_parser.add_argument("--require-executable", action="store_true",
        help="Fail if requested capability does not produce request-aligned executable workflow output")

    receiver_parser = subparsers.add_parser("from-receiver", help="Fetch receiver scan then generate")
    receiver_parser.add_argument("--receiver-endpoint", required=True)
    receiver_parser.add_argument("--scan-id", required=True)
    receiver_parser.add_argument("--output-root", default="build/receiver-generation")
    receiver_parser.add_argument("--requested-capability", default=None)
    receiver_parser.add_argument("--local-manifest", default=None)
    receiver_parser.add_argument("--resume-dir", default=None)
    receiver_parser.add_argument("--timeout", type=float, default=30.0)
    receiver_parser.add_argument("--workers", type=int, default=4)
    receiver_parser.add_argument("--observation-path", action="append", default=[],
        help="Dynamic observation JSON file or directory to merge; repeatable")
    receiver_parser.add_argument("--allow-legacy-report-index", action="store_true",
        help="allow receiver fetch fallback from paged legacy report records")
    receiver_parser.add_argument("--max-legacy-report-pages", type=int,
        default=FETCH.MAX_LEGACY_REPORT_PAGES,
        help="maximum paged legacy-report index pages to scan during fallback import")
    receiver_parser.add_argument("--require-executable", action="store_true",
        help="Fail if requested capability does not produce request-aligned executable workflow output")

    exercise_parser = subparsers.add_parser(
        "exercise-live",
        help="Run Arsenal/Phantom live-evidence generation exercise from local extracted scans",
    )
    exercise_parser.add_argument("--output-root", default="build/live-evidence-exercise")
    exercise_parser.add_argument("--extracted-root", default="build/live_scans/extracted",
        help="Root directory containing extracted multipart scan folders")
    exercise_parser.add_argument("--arsenal-baseline-scan-id",
        default="DBFC72C6-749B-4F95-BBA2-433B8B61745C")
    exercise_parser.add_argument("--phantom-baseline-scan-id",
        default="6D3741EF-9569-4F40-B38A-E4FD2AE0A063")
    exercise_parser.add_argument(
        "--requested-capability-arsenal",
        default="Automatically shoot, reload, and switch weapons in Arsenal",
    )
    exercise_parser.add_argument(
        "--requested-capability-phantom",
        default="Automatically shoot, reload, and switch weapons in Phantom Forces",
    )
    exercise_parser.add_argument("--observation-path", action="append", default=[],
        help="Dynamic observation JSON file or directory to discover and merge; repeatable")

    observation_parser = subparsers.add_parser(
        "exercise-observation",
        help="Run one dynamic-observation export against local extracted baseline parts",
    )
    observation_parser.add_argument("--observation", required=True,
        help="Path to one dynamic-observations JSON export")
    observation_parser.add_argument("--requested-capability", required=True)
    observation_parser.add_argument("--output-root", default="build/live-observation-exercise")
    observation_parser.add_argument("--extracted-root", default="build/live_scans/extracted",
        help="Root directory containing extracted multipart scan folders")
    observation_parser.add_argument("--baseline-scan-id", default=None,
        help="Optional baseline scan override; otherwise inferred from observation export")
    observation_parser.add_argument("--scenario-name", default="live-observation")
    observation_parser.add_argument("--require-executable", action="store_true",
        help="Fail if requested capability does not produce request-aligned executable workflow output")

    args = parser.parse_args()
    try:
        output_root = pathlib.Path(args.output_root).resolve()
        output_root.mkdir(parents=True, exist_ok=True)
        observation_paths = [pathlib.Path(item).resolve() for item in getattr(args, "observation_path", [])]
        if args.mode == "from-parts":
            result = generate_from_parts(
                parts_dir=pathlib.Path(args.parts_dir).resolve(),
                output_root=output_root,
                requested_capability=args.requested_capability,
                observation_paths=observation_paths,
                require_executable=args.require_executable,
            )
        elif args.mode == "from-receiver":
            result = generate_from_receiver(
                receiver_endpoint=args.receiver_endpoint,
                scan_id=args.scan_id,
                output_root=output_root,
                requested_capability=args.requested_capability,
                local_manifest=pathlib.Path(args.local_manifest).resolve()
                if args.local_manifest
                else None,
                resume_dir=pathlib.Path(args.resume_dir).resolve() if args.resume_dir else None,
                timeout=args.timeout,
                workers=args.workers,
                observation_paths=observation_paths,
                allow_legacy_report_index=args.allow_legacy_report_index,
                max_legacy_report_pages=args.max_legacy_report_pages,
                require_executable=args.require_executable,
            )
        elif args.mode == "exercise-live":
            result = run_live_evidence_exercise(
                output_root=output_root,
                requested_capability_arsenal=args.requested_capability_arsenal,
                requested_capability_phantom=args.requested_capability_phantom,
                observation_paths=observation_paths,
                extracted_root=pathlib.Path(args.extracted_root).resolve(),
                arsenal_baseline_scan_id=args.arsenal_baseline_scan_id,
                phantom_baseline_scan_id=args.phantom_baseline_scan_id,
            )
        else:
            result = run_live_observation_scenario(
                output_root=output_root,
                observation_path=pathlib.Path(args.observation).resolve(),
                requested_capability=args.requested_capability,
                extracted_root=pathlib.Path(args.extracted_root).resolve(),
                baseline_scan_id=args.baseline_scan_id,
                scenario_name=args.scenario_name,
                require_executable=args.require_executable,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"PIPELINE BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
