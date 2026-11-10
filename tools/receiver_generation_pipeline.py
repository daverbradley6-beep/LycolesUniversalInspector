#!/usr/bin/env python3
"""Run Lycoles generation from either local parts or receiver scan IDs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import shutil
import sys
import tempfile
import zipfile
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


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: pathlib.Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1_048_576)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _parse_json_payload(raw: bytes, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{context} is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{context} must be a JSON object")
    return payload


def _validate_manifest_identity(manifest: dict[str, Any], *, scan_id: str, place_id: int, part_count: int, context: str) -> None:
    for key, expected in (("scanId", scan_id), ("placeId", place_id), ("partCount", part_count), ("expectedParts", part_count)):
        if key not in manifest:
            continue
        if manifest.get(key) != expected:
            raise ValueError(f"{context} identity mismatch for {key}")


def ingest_parts_archive(
    archive_path: pathlib.Path,
    extracted_root: pathlib.Path,
    *,
    expected_scan_id: Optional[str] = None,
) -> dict[str, Any]:
    archive = pathlib.Path(archive_path).resolve()
    if not archive.is_file():
        raise ValueError(f"parts archive not found: {archive}")
    if archive.suffix.lower() != ".zip":
        raise ValueError("parts archive must be a .zip file")

    extracted_root = pathlib.Path(extracted_root).resolve()
    extracted_root.mkdir(parents=True, exist_ok=True)

    archive_sha256 = _sha256_file(archive)

    part_records: dict[int, dict[str, Any]] = {}
    manifest_records: list[dict[str, Any]] = []
    name_digests: dict[str, str] = {}
    duplicate_part_count = 0
    extracted_json_count = 0

    scan_id: Optional[str] = None
    place_id: Optional[int] = None
    part_count: Optional[int] = None

    staging = pathlib.Path(tempfile.mkdtemp(prefix=".ingest-", dir=str(extracted_root)))
    try:
        with zipfile.ZipFile(archive) as bundle:
            members = [entry for entry in bundle.infolist() if not entry.is_dir() and entry.filename.lower().endswith(".json")]
            if not members:
                raise ValueError("archive has no JSON parts")
            for entry in members:
                if entry.file_size > 8_000_000:
                    raise ValueError(f"archive member too large: {entry.filename}")
                raw = bundle.read(entry)
                context = f"archive member {entry.filename}"
                payload = _parse_json_payload(raw, context)
                safe_name = pathlib.PurePosixPath(entry.filename).name
                if not safe_name:
                    raise ValueError(f"invalid archive member name: {entry.filename}")

                digest = _sha256_bytes(raw)
                previous_digest = name_digests.get(safe_name)
                if previous_digest is not None and previous_digest != digest:
                    raise ValueError(f"conflicting duplicate filename in archive: {safe_name}")
                name_digests[safe_name] = digest

                if "partIndex" in payload:
                    index = payload.get("partIndex")
                    sid = payload.get("scanId")
                    pid = payload.get("placeId")
                    pcount = payload.get("partCount")
                    if type(index) is not int or index <= 0:
                        raise ValueError(f"{context} has invalid partIndex")
                    if not isinstance(payload.get("objects"), list):
                        raise ValueError(f"{context} missing objects[] payload")
                    if not isinstance(sid, str) or not sid:
                        raise ValueError(f"{context} missing scanId")
                    if type(pid) is not int or pid <= 0:
                        raise ValueError(f"{context} has invalid placeId")
                    if type(pcount) is not int or pcount <= 0:
                        raise ValueError(f"{context} has invalid partCount")
                    if expected_scan_id is not None and sid != expected_scan_id:
                        raise ValueError(
                            f"archive scanId mismatch: expected {expected_scan_id}, got {sid}"
                        )
                    if scan_id is None:
                        scan_id = sid
                        place_id = pid
                        part_count = pcount
                    elif sid != scan_id or pid != place_id or pcount != part_count:
                        raise ValueError("mixed scan identity across archive parts")
                    existing = part_records.get(index)
                    if existing is not None:
                        duplicate_part_count += 1
                        if existing["sha256"] != digest:
                            raise ValueError(f"conflicting duplicate part content for index {index}")
                    else:
                        part_records[index] = {
                            "index": index,
                            "filename": safe_name,
                            "sha256": digest,
                        }
                else:
                    manifest_records.append(payload)

                target_path = staging / safe_name
                if target_path.exists() and target_path.read_bytes() != raw:
                    raise ValueError(f"conflicting duplicate archive payload for {safe_name}")
                target_path.write_bytes(raw)
                extracted_json_count += 1

        if not part_records:
            raise ValueError("archive does not contain multipart scan parts")
        assert scan_id is not None and place_id is not None and part_count is not None

        missing_parts = [index for index in range(1, part_count + 1) if index not in part_records]
        if missing_parts:
            preview = missing_parts[:20]
            raise ValueError(f"missing parts: {preview} (total {len(missing_parts)})")

        for manifest in manifest_records:
            _validate_manifest_identity(
                manifest,
                scan_id=scan_id,
                place_id=place_id,
                part_count=part_count,
                context="archive manifest",
            )

        target = extracted_root / f"archive_{scan_id}"
        metadata_path = target / ".archive-ingestion.meta"
        if target.is_dir() and metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = None
            if isinstance(metadata, dict) and metadata.get("archiveSha256") == archive_sha256:
                shutil.rmtree(staging)
                return {
                    "scanId": scan_id,
                    "placeId": place_id,
                    "partCount": part_count,
                    "jsonFiles": extracted_json_count,
                    "manifestFiles": len(manifest_records),
                    "duplicatePartCount": duplicate_part_count,
                    "missingPartCount": 0,
                    "archiveSha256": archive_sha256,
                    "archivePath": str(archive),
                    "outputDir": str(target),
                    "reusedExistingExtraction": True,
                }
        if target.exists():
            shutil.rmtree(target)
        staging.replace(target)

        metadata = {
            "scanId": scan_id,
            "placeId": place_id,
            "partCount": part_count,
            "jsonFiles": extracted_json_count,
            "manifestFiles": len(manifest_records),
            "duplicatePartCount": duplicate_part_count,
            "missingPartCount": 0,
            "archiveSha256": archive_sha256,
            "archivePath": str(archive),
            "reusedExistingExtraction": False,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        metadata["outputDir"] = str(target)
        return metadata
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _resolve_parts_input(parts_input: pathlib.Path, output_root: pathlib.Path) -> tuple[pathlib.Path, Optional[dict[str, Any]]]:
    source = pathlib.Path(parts_input).resolve()
    if source.is_dir():
        return source, None
    if source.is_file() and source.suffix.lower() == ".zip":
        ingestion_root = output_root / "ingested_parts_archives"
        info = ingest_parts_archive(source, ingestion_root)
        return pathlib.Path(info["outputDir"]), info
    raise ValueError(f"parts input must be a directory or .zip archive: {source}")


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



def _classify_observed_state_key(key: str) -> dict[str, bool]:
    lower = key.lower()
    is_leaderstats = ".leaderstats." in lower or lower.startswith("leaderstats.")
    is_quest = ".quests." in lower or "quest" in lower
    is_strength = "strength" in lower
    return {
        "is_leaderstats": is_leaderstats,
        "is_quest": is_quest,
        "is_repetition": "reps" in lower or "rep." in lower or "rep_" in lower,
        "is_minutes": "minutes.progress" in lower or ".minutes" in lower,
        "is_health": ".health" in lower or ".humanoid.health" in lower,
        "is_animation": "activeanimationcount" in lower,
        "is_movement": any(token in lower for token in ("walkspeed", "jump", "velocity", "position", "hipheight", "cframe")),
        "is_progress": "progress" in lower,
        "is_time": "time" in lower or "playtime" in lower or "cooldown" in lower,
        "is_level": any(token in lower for token in ("level", ".lvl", "rank")),
        "is_experience": any(token in lower for token in ("xp", "exp", "experience")),
        "is_currency": any(token in lower for token in ("coin", "cash", "gem", "gold", "token", "currency")),
        "is_rebirth": "rebirth" in lower,
        "is_stat_folder": any(token in lower for token in (".stats.", ".attributes.", ".data.")),
        "is_inventory_count": lower.endswith(".count") or ".equippedcount" in lower or ".tools.count" in lower,
        "is_equipment": lower.startswith("backpack.") or ".backpack." in lower or ".tools." in lower,
        "is_pet": ".petsfolder." in lower or ".pets." in lower,
        "is_strength": is_strength,
        "is_primary_strength": is_strength and is_leaderstats and not is_quest,
    }


def _stat_source_from_key(key: str) -> str:
    low = key.lower()
    if ".leaderstats." in low or low.startswith("leaderstats."):
        return "leaderstats"
    if ".playergui." in low or low.startswith("playergui."):
        return "gui-display"
    if low.startswith("localplayer.character.") or low.startswith("character."):
        return "character"
    if low.startswith("localplayer."):
        return "replicated-player"
    if low.startswith("workspace."):
        return "world"
    return "unknown"


def _stat_category_from_key(key: str, classification: dict[str, bool]) -> str:
    low = key.lower()
    if classification.get("is_primary_strength"):
        return "primary-progression"
    if classification.get("is_quest"):
        return "quest-progress"
    if classification.get("is_currency"):
        return "currency-resource"
    if classification.get("is_inventory_count"):
        return "inventory-count"
    if classification.get("is_pet") or (classification.get("is_experience") and ("pet" in low or "powerupsfolder" in low)):
        return "equipment-or-pet-experience"
    if classification.get("is_health") or classification.get("is_animation") or classification.get("is_movement") or classification.get("is_time"):
        return "transient-state"
    return "other-progression"



def _normalize_stat_name_from_key(key: str) -> str:
    raw = key.split(".")[-1].replace("_", " ").strip()
    if not raw:
        return key
    return " ".join(part[:1].upper() + part[1:] for part in raw.split())


def _confidence_level(score: float) -> str:
    if score >= 0.78:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"



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
    state_key_stats: dict[str, dict[str, Any]] = {}
    method_state_key_stats: dict[str, dict[str, dict[str, Any]]] = {}
    action_envelopes: list[dict[str, Any]] = []
    passive_stat_hits: dict[str, int] = {}

    for event in events:
        event_path = event.get("path") if isinstance(event.get("path"), str) else None
        if event in selected_events:
            observation_windows = event.get("observationWindows")
            if isinstance(observation_windows, list):
                for window in observation_windows:
                    if not isinstance(window, dict):
                        continue
                    seconds = _numeric(window.get("seconds"))
                    if seconds is not None and 0.05 <= seconds <= 8.0:
                        windows.append(seconds)

        action_envelopes.append({
            "path": event_path,
            "controlType": event.get("controlType") if isinstance(event.get("controlType"), str) else None,
            "elapsed": _numeric(event.get("sessionElapsedSeconds")),
        })

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
            change_delta = after - before
            absolute_delta = abs(change_delta)
            if absolute_delta <= 0:
                continue

            classification = _classify_observed_state_key(key)
            score = 0.0
            if change_delta > 0:
                score += 4.0
            score += min(5.0, absolute_delta)
            if classification["is_leaderstats"]:
                score += 20.0
            if classification["is_progress"]:
                score += 4.0
            if classification["is_level"] or classification["is_experience"]:
                score += 7.0
            if classification["is_rebirth"]:
                score += 5.0
            if classification["is_currency"]:
                score += 2.5
            if classification["is_stat_folder"]:
                score += 3.0
            if classification["is_quest"] and classification["is_repetition"]:
                score += 6.0
            if classification["is_minutes"] or classification["is_time"]:
                score -= 15.0
            if classification["is_health"] or classification["is_animation"] or classification["is_movement"]:
                score -= 24.0
            lower_key = key.lower()
            for token in capability_tokens:
                if token in lower_key:
                    score += 1.5

            control_type = event.get("controlType") if isinstance(event.get("controlType"), str) else ""
            if change_delta > 0 and control_type != "Tool.Activated":
                passive_stat_hits[key] = passive_stat_hits.get(key, 0) + 1

            bucket = state_key_stats.setdefault(key, {
                "changes": 0,
                "increases": 0,
                "decreases": 0,
                "delta_abs": 0.0,
                "delta_up": 0.0,
                "delta_down": 0.0,
                "weighted_score": 0.0,
                "classification": classification,
                "samples": [],
                "lastAfter": None,
            })
            bucket["changes"] += 1
            bucket["delta_abs"] += absolute_delta
            bucket["weighted_score"] += score
            bucket["lastAfter"] = after
            if change_delta > 0:
                bucket["increases"] += 1
                bucket["delta_up"] += change_delta
            else:
                bucket["decreases"] += 1
                bucket["delta_down"] += abs(change_delta)
            if len(bucket["samples"]) < 8:
                bucket["samples"].append({
                    "before": before,
                    "after": after,
                    "delta": change_delta,
                    "eventPath": event_path,
                    "controlType": event.get("controlType"),
                    "sessionElapsedSeconds": _numeric(event.get("sessionElapsedSeconds")),
                })

            if event_path:
                method_bucket = method_state_key_stats.setdefault(event_path, {}).setdefault(key, {
                    "changes": 0,
                    "increases": 0,
                    "decreases": 0,
                    "delta_up": 0.0,
                    "delta_down": 0.0,
                    "delta_abs": 0.0,
                    "samples": [],
                })
                method_bucket["changes"] += 1
                method_bucket["delta_abs"] += absolute_delta
                if change_delta > 0:
                    method_bucket["increases"] += 1
                    method_bucket["delta_up"] += change_delta
                else:
                    method_bucket["decreases"] += 1
                    method_bucket["delta_down"] += abs(change_delta)
                if len(method_bucket["samples"]) < 6:
                    method_bucket["samples"].append({
                        "before": before,
                        "after": after,
                        "delta": change_delta,
                        "sessionElapsedSeconds": _numeric(event.get("sessionElapsedSeconds")),
                    })

    ranked_keys = sorted(
        state_key_stats.items(),
        key=lambda item: (
            -float(item[1].get("weighted_score", 0.0)),
            -int(item[1].get("increases", 0)),
            -float(item[1].get("delta_up", 0.0)),
            item[0],
        ),
    )

    positive_ranked = [item for item in ranked_keys if int(item[1].get("increases", 0)) > 0]
    if len(positive_ranked) == 0:
        return None

    progression_ranked = [
        item
        for item in positive_ranked
        if not item[1]["classification"]["is_health"]
        and not item[1]["classification"]["is_animation"]
        and not item[1]["classification"]["is_movement"]
        and not item[1]["classification"]["is_minutes"]
        and not item[1]["classification"]["is_time"]
    ]
    if len(progression_ranked) == 0:
        progression_ranked = positive_ranked

    def _primary_sort_key(item: tuple[str, dict[str, Any]]) -> tuple[float, int, float, str]:
        key, stats = item
        return (
            -float(stats.get("weighted_score", 0.0)),
            -int(stats.get("increases", 0)),
            -float(stats.get("delta_up", 0.0)),
            key,
        )

    def _pick_primary_path(candidates: list[tuple[str, dict[str, Any]]]) -> Optional[str]:
        if not candidates:
            return None
        preferred_strength = [
            item for item in candidates
            if item[1]["classification"].get("is_primary_strength")
        ]
        if preferred_strength:
            return sorted(preferred_strength, key=_primary_sort_key)[0][0]

        leaderstats_non_quest = [
            item for item in candidates
            if item[1]["classification"].get("is_leaderstats")
            and not item[1]["classification"].get("is_quest")
        ]
        if leaderstats_non_quest:
            return sorted(leaderstats_non_quest, key=_primary_sort_key)[0][0]

        non_quest = [item for item in candidates if not item[1]["classification"].get("is_quest")]
        if non_quest:
            return sorted(non_quest, key=_primary_sort_key)[0][0]

        return sorted(candidates, key=_primary_sort_key)[0][0]

    primary_path = _pick_primary_path(progression_ranked) or progression_ranked[0][0]

    repetition_paths = [
        key
        for key, stats in progression_ranked
        if stats["classification"]["is_quest"]
        and stats["classification"]["is_repetition"]
        and not stats["classification"]["is_minutes"]
        and not stats["classification"]["is_time"]
    ][:8]

    noisy_paths = [
        key
        for key, stats in ranked_keys
        if stats["classification"]["is_health"]
        or stats["classification"]["is_animation"]
        or stats["classification"]["is_movement"]
        or stats["classification"]["is_minutes"]
        or stats["classification"]["is_time"]
    ][:20]

    candidate_paths = [primary_path]
    for key, stats in progression_ranked:
        if key == primary_path:
            continue
        if stats["classification"]["is_health"] or stats["classification"]["is_animation"] or stats["classification"]["is_movement"]:
            continue
        if stats["classification"]["is_minutes"] or stats["classification"]["is_time"]:
            continue
        candidate_paths.append(key)
        if len(candidate_paths) >= 16:
            break

    if windows:
        sorted_windows = sorted(windows)
        delay = sorted_windows[len(sorted_windows) // 2]
    else:
        delay = 0.45
    delay = max(0.2, min(2.8, float(delay)))

    activation_interval = max(0.12, min(1.5, round(delay * 0.28, 2)))
    poll_interval = max(0.1, min(1.0, round(delay * 0.45, 2)))
    stall_window = max(8.0, min(75.0, round(delay * 12.0 + 6.0, 2)))

    def is_actionable_gui_path(path: str) -> bool:
        low = path.lower()
        blocked_tokens = ("exitbutton", "xbutton", ".close", "declinebutton", ".no", "cancel")
        return not any(token in low for token in blocked_tokens)

    def is_probable_gui_button_path(path: str) -> bool:
        low = path.lower()
        if not is_actionable_gui_path(path):
            return False
        blocked_segments = ("buttonlabel", "textlabel", "uilistlayout", "uistroke", "uicorner", "image", "icon", "sunburst")
        if any(token in low for token in blocked_segments):
            return False
        button_tokens = ("button", "hitbox", "claim", "collect", "accept", "tab", "playtime", "yesbutton")
        return any(token in low for token in button_tokens)

    control_paths_by_type: dict[str, list[str]] = {}
    for event in events:
        control_type = event.get("controlType")
        path = event.get("path")
        if not isinstance(control_type, str) or not isinstance(path, str):
            continue
        bucket = control_paths_by_type.setdefault(control_type, [])
        if path not in bucket:
            bucket.append(path)

    def collect_gui_paths(feature: Optional[str] = None) -> list[str]:
        found: list[str] = []
        seen: set[str] = set()
        for event in events:
            if event.get("controlType") != "GuiButton.Activated":
                continue
            if feature is not None and event.get("featureCandidate") != feature:
                continue
            path = event.get("path")
            if not isinstance(path, str) or "PlayerGui" not in path:
                continue
            if not is_actionable_gui_path(path):
                continue
            if path not in seen:
                seen.add(path)
                found.append(path)
        return found

    features_by_name = {}
    for item in payload.get("features") or []:
        if isinstance(item, dict) and isinstance(item.get("feature"), str):
            features_by_name[item["feature"].lower()] = item

    readiness_by_name = {}
    feature_readiness = payload.get("featureReadiness")
    if isinstance(feature_readiness, dict):
        for key, value in feature_readiness.items():
            if isinstance(key, str) and isinstance(value, dict):
                readiness_by_name[key.lower()] = value

    def collect_payload_path_candidates(value: Any) -> set[str]:
        result: set[str] = set()

        def walk(item: Any) -> None:
            if isinstance(item, dict):
                for key, inner in item.items():
                    if key in {"path", "key", "statePath", "objectPath", "instancePath", "targetPath"} and isinstance(inner, str):
                        result.add(inner)
                    walk(inner)
                return
            if isinstance(item, list):
                for inner in item:
                    walk(inner)

        walk(value)
        return result

    payload_paths = collect_payload_path_candidates(payload)

    reward_paths_observed = collect_gui_paths(feature="rewards")
    reward_paths_payload: list[str] = []
    reward_indicator_paths: list[str] = []
    for path in sorted(payload_paths):
        low = path.lower()
        if "playergui" not in low:
            continue
        normalized = path
        if normalized.startswith("PlayerGui."):
            normalized = "LocalPlayer." + normalized
        reward_scope_match = any(token in low for token in ("reward", "gift", "fortune", "wheel", "crystal", "groupreward", "claim.notification"))
        if any(token in low for token in (".readytext", ".timer", ".claimed")) and reward_scope_match:
            reward_indicator_paths.append(normalized)
        if reward_scope_match and any(token in low for token in ("claimbutton", "collectbutton", "hitbox", "spinbutton", "wheelbtn", "claim")) and is_probable_gui_button_path(normalized):
            if not any(token in low for token in (".readytext", ".timer", ".claimed", "notification")):
                reward_paths_payload.append(normalized)

    reward_paths = sorted(set(reward_paths_observed + reward_paths_payload))
    reward_guarded_paths = [path for path in reward_paths if "spinbutton" in path.lower() or "wheelbtn" in path.lower()]
    reward_activation_paths = [path for path in reward_paths if path not in reward_guarded_paths]
    reward_claim_paths = [
        path
        for path in reward_activation_paths
        if any(token in path.lower() for token in ("hitbox", "collectbutton", "claimbutton", "rewards.gift", "freegifts"))
    ]
    reward_open_paths = [path for path in reward_activation_paths if path not in reward_claim_paths]
    reward_container_paths = sorted({
        path.split(".HitBox")[0].rsplit(".", 1)[0] if ".HitBox" in path else path.rsplit(".", 1)[0]
        for path in reward_paths
    })

    rebirth_open_paths = [path for path in collect_gui_paths(feature="rebirth") if "rebirth" in path.lower()]
    rebirth_confirm_paths = [
        path for path in collect_gui_paths() if "yesbutton" in path.lower() and "basechoice" in path.lower()
    ]

    quest_gui_paths_observed = [path for path in collect_gui_paths() if "quest" in path.lower()]
    quest_gui_paths_payload: list[str] = []
    for path in sorted(payload_paths):
        low = path.lower()
        if "playergui" not in low or "quest" not in low:
            continue
        normalized = path
        if normalized.startswith("PlayerGui."):
            normalized = "LocalPlayer." + normalized
        if not is_probable_gui_button_path(normalized):
            continue
        if any(token in low for token in ("button", "claim", "collect", "tab", "select", "playtime", "prizes", "accept", "quest")):
            quest_gui_paths_payload.append(normalized)

    quest_gui_paths = sorted(set(quest_gui_paths_observed + quest_gui_paths_payload))
    quest_claim_paths = [
        path for path in quest_gui_paths
        if any(token in path.lower() for token in ("claim", "collect", "reward", "prize"))
    ]
    quest_select_paths = [
        path for path in quest_gui_paths
        if any(token in path.lower() for token in ("tab", "select", "playtime", "objective", "quest"))
    ]

    quest_claim_state_paths = [
        key
        for key, stats in ranked_keys
        if stats["classification"]["is_quest"]
        and not stats["classification"]["is_minutes"]
        and not stats["classification"]["is_time"]
        and any(token in key.lower() for token in ("claim", "collect", "reward", "complete", "completed"))
    ][:10]


    proximity_paths = [path for path in control_paths_by_type.get("ProximityPrompt.Triggered", []) if isinstance(path, str)]

    inventory_feature = features_by_name.get("inventory", {})
    rewards_feature = features_by_name.get("rewards", {})
    rebirth_feature = features_by_name.get("rebirth", {})
    inventory_readiness = readiness_by_name.get("inventory", {})
    rewards_readiness = readiness_by_name.get("rewards", {})
    rebirth_readiness = readiness_by_name.get("rebirth", {})

    tool_name = selected["path"].split(".")[-1]

    strength_paths: list[str] = []
    for path in candidate_paths:
        low = path.lower()
        if path == primary_path or "leaderstats" in low or "progress" in low or "level" in low or "experience" in low:
            strength_paths.append(path)
    if len(strength_paths) == 0:
        strength_paths = [primary_path]

    reward_state_paths = sorted({
        path
        for path in (reward_indicator_paths + [item for item in payload_paths if isinstance(item, str)])
        if any(token in path.lower() for token in ("reward", "gift", ".claimed", ".timer", ".readytext", "claim.notification"))
    })
    reward_outcome_support_paths = [
        key
        for key, stats in ranked_keys
        if stats["classification"].get("is_currency")
    ][:8]
    reward_state_paths = sorted(set(reward_state_paths + reward_outcome_support_paths))

    inventory_gui_paths = [
        path
        for path in collect_gui_paths()
        if "itemsnewmenu" in path.lower() and is_actionable_gui_path(path)
    ]

    def classify_training_source(path: str) -> str:
        low = path.lower()
        if low.startswith("workspace.") or ".workspace." in low:
            return "world-station"
        if low.startswith("localplayer.backpack.") or low.startswith("character."):
            return "inventory-tool"
        return "unknown"

    training_methods: list[dict[str, Any]] = []
    seen_method_ids: set[str] = set()
    for index, item in enumerate(ranked[:10], start=1):
        path = item["path"]
        method_name = path.split(".")[-1]
        method_key = re.sub(r"[^a-z0-9]+", "_", method_name.lower()).strip("_") or f"method_{index}"
        method_id = f"training_{method_key}"
        unique_method_id = method_id
        suffix = 2
        while unique_method_id in seen_method_ids:
            unique_method_id = f"{method_id}_{suffix}"
            suffix += 1
        seen_method_ids.add(unique_method_id)

        low = path.lower()
        source_kind = classify_training_source(path)
        generic_input = low.startswith("localplayer.input.")
        safe_by_default = ("punch" not in low) and (source_kind != "unknown") and (not generic_input)
        default_selected = (path == selected["path"]) and safe_by_default

        training_methods.append({
            "id": unique_method_id,
            "name": method_name,
            "path": path,
            "source": source_kind,
            "observedActivations": int(item.get("count", 0)),
            "metadata": item.get("metadata") or {},
            "defaultSelected": bool(default_selected),
            "safeByDefault": bool(safe_by_default),
            "readiness": "observed-activation-candidate" if int(item.get("count", 0)) > 0 else "unobserved",
        })

    stat_registry_entries: list[dict[str, Any]] = []
    stat_by_path: dict[str, dict[str, Any]] = {}
    excluded_stat_signals: list[dict[str, Any]] = []
    for key, stats in ranked_keys[:80]:
        classification = stats.get("classification") or {}
        progression_candidate = (
            not classification.get("is_health")
            and not classification.get("is_animation")
            and not classification.get("is_movement")
            and not classification.get("is_minutes")
            and not classification.get("is_time")
            and (
                classification.get("is_leaderstats")
                or classification.get("is_progress")
                or classification.get("is_level")
                or classification.get("is_experience")
                or classification.get("is_rebirth")
                or classification.get("is_stat_folder")
                or int(stats.get("increases", 0)) > 0
            )
        )
        score = 0.16
        score += min(0.45, float(stats.get("increases", 0)) * 0.08)
        if classification.get("is_leaderstats"):
            score += 0.2
        if classification.get("is_level") or classification.get("is_experience"):
            score += 0.12
        if classification.get("is_health") or classification.get("is_animation") or classification.get("is_movement"):
            score -= 0.22
        if classification.get("is_minutes") or classification.get("is_time"):
            score -= 0.2
        confidence_score = max(0.0, min(0.98, score))
        entry = {
            "id": "stat_" + (re.sub(r"[^a-z0-9]+", "_", key.lower()).strip("_") or "unknown"),
            "name": _normalize_stat_name_from_key(key),
            "path": key,
            "source": _stat_source_from_key(key),
            "category": _stat_category_from_key(key, classification),
            "dataType": "number",
            "progressionCandidate": bool(progression_candidate),
            "observedChanges": {
                "changes": int(stats.get("changes", 0)),
                "increases": int(stats.get("increases", 0)),
                "decreases": int(stats.get("decreases", 0)),
                "positiveDelta": round(float(stats.get("delta_up", 0.0)), 6),
                "negativeDelta": round(float(stats.get("delta_down", 0.0)), 6),
                "passiveIncreaseHits": int(passive_stat_hits.get(key, 0)),
            },
            "lastObservedValue": stats.get("lastAfter"),
            "confidenceScore": round(confidence_score, 4),
            "confidenceLevel": _confidence_level(confidence_score),
            "classification": classification,
        }
        stat_registry_entries.append(entry)
        if progression_candidate:
            stat_by_path[key] = entry
        else:
            excluded_stat_signals.append({
                "path": key,
                "reason": "non-progression-or-noisy-signal",
            })

    if primary_path not in stat_by_path:
        fallback_entry = {
            "id": "stat_" + (re.sub(r"[^a-z0-9]+", "_", primary_path.lower()).strip("_") or "primary"),
            "name": _normalize_stat_name_from_key(primary_path),
            "path": primary_path,
            "source": _stat_source_from_key(primary_path),
            "category": _stat_category_from_key(primary_path, _classify_observed_state_key(primary_path)),
            "dataType": "number",
            "progressionCandidate": True,
            "observedChanges": {
                "changes": 1,
                "increases": 1,
                "decreases": 0,
                "positiveDelta": 0.0,
                "negativeDelta": 0.0,
                "passiveIncreaseHits": int(passive_stat_hits.get(primary_path, 0)),
            },
            "lastObservedValue": None,
            "confidenceScore": 0.65,
            "confidenceLevel": "medium",
            "classification": _classify_observed_state_key(primary_path),
        }
        stat_registry_entries.insert(0, fallback_entry)
        stat_by_path[primary_path] = fallback_entry

    action_stat_relationships: list[dict[str, Any]] = []
    relationships_by_method_path: dict[str, list[dict[str, Any]]] = {}
    for method_path, related_stats in method_state_key_stats.items():
        for key, method_stats in related_stats.items():
            stat_entry = stat_by_path.get(key)
            if not stat_entry:
                continue
            increases = int(method_stats.get("increases", 0))
            decreases = int(method_stats.get("decreases", 0))
            relation_score = 0.18 + min(0.5, increases * 0.12)
            relation_score += min(0.2, float(method_stats.get("delta_up", 0.0)) * 0.05)
            if decreases > 0:
                relation_score -= min(0.25, decreases * 0.07)
            confidence_score = max(0.0, min(0.95, relation_score))
            relation = {
                "methodPath": method_path,
                "statId": stat_entry["id"],
                "statName": stat_entry["name"],
                "statPath": stat_entry["path"],
                "increases": increases,
                "decreases": decreases,
                "positiveDelta": round(float(method_stats.get("delta_up", 0.0)), 6),
                "negativeDelta": round(float(method_stats.get("delta_down", 0.0)), 6),
                "confidenceScore": round(confidence_score, 4),
                "confidenceLevel": _confidence_level(confidence_score),
                "samples": method_stats.get("samples") or [],
                "temporalCorrelationOnly": True,
                "causalityProven": False,
            }
            action_stat_relationships.append(relation)
            relationships_by_method_path.setdefault(method_path, []).append(relation)

    for relations in relationships_by_method_path.values():
        relations.sort(key=lambda item: (-float(item.get("confidenceScore", 0.0)), -float(item.get("positiveDelta", 0.0)), item.get("statPath") or ""))

    for method in training_methods:
        relations = relationships_by_method_path.get(str(method.get("path") or ""), [])
        method["candidateStats"] = [
            {
                "statId": rel["statId"],
                "statName": rel["statName"],
                "statPath": rel["statPath"],
                "confidenceScore": rel["confidenceScore"],
                "confidenceLevel": rel["confidenceLevel"],
                "positiveDelta": rel["positiveDelta"],
            }
            for rel in relations[:6]
        ]
        method["relationCount"] = len(relations)

    stat_training_targets: list[dict[str, Any]] = []
    unsupported_stat_targets: list[dict[str, Any]] = []
    for stat in [item for item in stat_registry_entries if item.get("progressionCandidate")]:
        methods_for_stat: list[dict[str, Any]] = []
        for method in training_methods:
            for relation in method.get("candidateStats") or []:
                if relation.get("statId") == stat.get("id"):
                    methods_for_stat.append({
                        "methodId": method["id"],
                        "name": method["name"],
                        "path": method["path"],
                        "source": method["source"],
                        "safeByDefault": method.get("safeByDefault") is True,
                        "readiness": method.get("readiness"),
                        "confidenceScore": relation.get("confidenceScore"),
                        "confidenceLevel": relation.get("confidenceLevel"),
                        "positiveDelta": relation.get("positiveDelta"),
                    })
                    break
        methods_for_stat.sort(key=lambda item: (-float(item.get("confidenceScore") or 0.0), -float(item.get("positiveDelta") or 0.0), str(item.get("name") or "")))
        default_selected_method_ids = [
            method["methodId"]
            for method in methods_for_stat
            if method.get("safeByDefault") and float(method.get("confidenceScore") or 0.0) >= 0.62
        ][:2]
        if len(default_selected_method_ids) == 0 and len(methods_for_stat) > 0:
            default_selected_method_ids = [methods_for_stat[0]["methodId"]]
        target = {
            "id": stat["id"],
            "name": stat["name"],
            "path": stat["path"],
            "source": stat.get("source"),
            "category": stat.get("category"),
            "dataType": stat.get("dataType", "number"),
            "lastObservedValue": stat.get("lastObservedValue"),
            "confidenceScore": stat.get("confidenceScore"),
            "confidenceLevel": stat.get("confidenceLevel"),
            "observedChanges": stat.get("observedChanges"),
            "methods": methods_for_stat,
            "defaultSelectedMethodIds": default_selected_method_ids,
            "defaultActive": stat.get("path") == primary_path,
            "temporalCorrelationOnly": True,
            "causalityProven": False,
        }
        if len(methods_for_stat) == 0:
            target["unsupportedReason"] = "No evidence-backed training relationship observed"
            unsupported_stat_targets.append({
                "statId": stat["id"],
                "statPath": stat["path"],
                "reason": target["unsupportedReason"],
            })
        stat_training_targets.append(target)

    method_stat_map: dict[str, list[str]] = {}
    for target in stat_training_targets:
        for method in target.get("methods") or []:
            method_id = method.get("methodId")
            if isinstance(method_id, str):
                method_stat_map.setdefault(method_id, []).append(str(target.get("id")))

    passive_progression_stats = [
        {
            "statPath": key,
            "statId": stat_by_path[key]["id"],
            "name": stat_by_path[key]["name"],
            "passiveIncreaseHits": count,
            "source": stat_by_path[key].get("source"),
        }
        for key, count in sorted(passive_stat_hits.items(), key=lambda item: (-item[1], item[0]))
        if key in stat_by_path and count > 0
    ]

    world_station_candidates: list[dict[str, Any]] = []
    seen_world_paths: set[str] = set()

    default_selected_method_ids: list[str] = []
    selected_seen: set[str] = set()
    for target in stat_training_targets:
        if target.get("defaultActive") is not True:
            continue
        for method_id in target.get("defaultSelectedMethodIds") or []:
            if isinstance(method_id, str) and method_id not in selected_seen:
                selected_seen.add(method_id)
                default_selected_method_ids.append(method_id)
    if len(default_selected_method_ids) == 0:
        for item in training_methods:
            method_id = item.get("id")
            if isinstance(method_id, str) and item.get("defaultSelected") is True:
                default_selected_method_ids.append(method_id)
    if len(default_selected_method_ids) == 0 and len(training_methods) > 0:
        fallback_id = training_methods[0].get("id")
        if isinstance(fallback_id, str):
            default_selected_method_ids = [fallback_id]

    for path in sorted(payload_paths):
        low = path.lower()
        if "workspace." not in low and not low.startswith("workspace"):
            continue
        if not any(token in low for token in (
            "proximityprompt", "clickdetector", "seat", "vehicle", "bench", "machine", "trainer", "training", "treadmill", "punch",
        )):
            continue
        normalized = path
        mechanism = "unknown"
        if "proximityprompt" in low:
            mechanism = "proximity"
        elif "clickdetector" in low:
            mechanism = "click"
        elif "seat" in low:
            mechanism = "seat"
        if normalized in seen_world_paths:
            continue
        seen_world_paths.add(normalized)
        world_station_candidates.append({
            "path": normalized,
            "mechanism": mechanism,
            "readiness": "observed-interaction-candidate",
        })

    training_discovery = {
        "inventoryMethods": training_methods,
        "inventoryMethodEvidencePresent": len(training_methods) > 0,
        "worldStations": world_station_candidates,
        "worldStationEvidencePresent": len(world_station_candidates) > 0 or len(proximity_paths) > 0,
        "statRegistry": {
            "stats": stat_registry_entries,
            "excludedSignals": excluded_stat_signals,
        },
        "statTrainingTargets": stat_training_targets,
        "unsupportedStatTargets": unsupported_stat_targets,
        "actionStatEvidence": {
            "relationships": action_stat_relationships,
            "passiveProgressionStats": passive_progression_stats,
            "temporalCorrelationOnly": True,
            "causalityProven": False,
        },
        "methodStatMap": method_stat_map,
    }

    feature_contracts: list[dict[str, Any]] = []
    unsupported_features: list[dict[str, Any]] = []
    deduplicated_features: list[dict[str, Any]] = []
    feature_dependencies: dict[str, list[str]] = {}

    seen_action_signatures: dict[str, str] = {}

    def action_signature(action: dict[str, Any]) -> str:
        kind = str(action.get("kind") or "")
        parts: list[str] = [kind]
        for key in ("toolPath", "toolName", "trainToolPath", "trainToolName"):
            value = action.get(key)
            if isinstance(value, str):
                parts.append(f"{key}:{value}")
        if isinstance(action.get("paths"), list):
            parts.append("paths:" + "|".join(sorted(str(item) for item in action.get("paths") if isinstance(item, str))))
        if isinstance(action.get("toolPaths"), list):
            parts.append("toolPaths:" + "|".join(sorted(str(item) for item in action.get("toolPaths") if isinstance(item, str))))
        if isinstance(action.get("steps"), list):
            normalized_steps = []
            for step in action.get("steps"):
                if isinstance(step, dict):
                    normalized_steps.append(f"{step.get('kind')}:{step.get('path')}")
            parts.append("steps:" + "|".join(sorted(normalized_steps)))
        return "||".join(parts)

    def add_feature(feature: dict[str, Any]) -> None:
        action = feature.get("action") if isinstance(feature.get("action"), dict) else {}
        signature = action_signature(action)
        duplicate_of = seen_action_signatures.get(signature)
        if duplicate_of:
            deduplicated_features.append({
                "id": feature.get("id"),
                "duplicateOf": duplicate_of,
                "actionSignature": signature,
            })
            unsupported_features.append({
                "id": feature.get("id"),
                "title": feature.get("title"),
                "category": feature.get("category"),
                "reason": f"Deduplicated with {duplicate_of}",
                "evidence": {"actionSignature": signature},
            })
            return
        seen_action_signatures[signature] = str(feature.get("id") or "unknown")
        feature_contracts.append(feature)

    add_feature({
        "id": "auto_train",
        "title": "Auto Train",
        "category": "auto-train",
        "supported": True,
        "actionable": True,
        "destructive": False,
        "includeInStartAll": True,
        "defaultEnabled": True,
        "action": {
            "kind": "tool_activate_selectable",
            "primaryToolPath": selected["path"],
            "primaryToolName": tool_name,
            "requiresEquippedTool": True,
            "implicitActions": ["ensure_tool_equipped"],
            "cycleMode": "round-robin-selected",
            "methods": training_methods,
            "defaultSelectedMethodIds": default_selected_method_ids,
            "statTargets": stat_training_targets,
            "methodStatMap": method_stat_map,
            "allowConcurrentStatRoutines": True,
            "conflictPolicy": "single-tool-activation-queue",
            "intervalSeconds": activation_interval,
        },
        "monitor": {
            "kind": "delayed-cumulative",
            "primaryOutcomePath": primary_path,
            "candidateStatePaths": strength_paths,
            "questRepetitionStatePaths": repetition_paths,
            "ignoredNoisyStatePaths": noisy_paths,
            "stallWindowSeconds": stall_window,
            "pollIntervalSeconds": poll_interval,
        },
        "evidence": {
            "featureCandidate": "inventory",
            "interactionEvents": len(tool_events),
            "matchingPathEvents": selected["count"],
            "trainingMethodCount": len(training_methods),
            "trainingMethods": training_methods,
            "statRegistryCount": len(stat_registry_entries),
            "statTrainingTargetCount": len(stat_training_targets),
            "actionStatRelationshipCount": len(action_stat_relationships),
            "readiness": inventory_feature.get("readiness") or inventory_readiness.get("readiness"),
            "observableOutcomeCandidates": inventory_feature.get("observableOutcomeCandidates") or inventory_readiness.get("observableOutcomeCandidates"),
        },
    })

    if len(reward_paths) > 0:
        add_feature({
            "id": "auto_rewards",
            "title": "Auto Rewards",
            "category": "auto-rewards",
            "supported": True,
            "actionable": True,
            "destructive": False,
            "includeInStartAll": True,
            "defaultEnabled": False,
            "action": {
                "kind": "auto_rewards_discovery",
                "paths": reward_claim_paths + reward_open_paths,
                "claimPaths": reward_claim_paths,
                "menuOpenPaths": reward_open_paths,
                "guardedPaths": reward_guarded_paths,
                "rewardContainerPaths": reward_container_paths,
                "eligibilityIndicatorPaths": reward_indicator_paths,
                "intervalSeconds": max(0.75, round(delay * 1.6, 2)),
            },
            "outcomeContract": {
                "kind": "reward-state-change",
                "verificationWindowSeconds": max(2.0, round(delay * 3.5, 2)),
                "statePaths": reward_state_paths,
                "strictlyRequireObservedDelta": True,
            },
            "monitor": {
                "kind": "multi-state",
                "candidateStatePaths": reward_state_paths,
            },
            "evidence": {
                "featureCandidate": "rewards",
                "guiActionPathCount": len(reward_paths),
                "claimPathCount": len(reward_claim_paths),
                "menuOpenPathCount": len(reward_open_paths),
                "guardedPathCount": len(reward_guarded_paths),
                "rewardContainerPathCount": len(reward_container_paths),
                "eligibilityIndicatorPathCount": len(reward_indicator_paths),
                "readiness": rewards_feature.get("readiness") or rewards_readiness.get("readiness"),
                "observableOutcomeCandidates": rewards_feature.get("observableOutcomeCandidates") or rewards_readiness.get("observableOutcomeCandidates"),
            },
        })
    else:
        unsupported_features.append({
            "id": "auto_rewards",
            "title": "Auto Rewards",
            "category": "auto-rewards",
            "reason": "No actionable reward GUI controls were observed",
            "evidence": {
                "featureCandidate": "rewards",
                "observedGuiInteractions": len(reward_paths_observed),
                "payloadDerivedInteractions": len(reward_paths_payload),
            },
        })

    if len(rebirth_open_paths) > 0 and len(rebirth_confirm_paths) > 0:
        add_feature({
            "id": "auto_rebirth",
            "title": "Auto Rebirth",
            "category": "auto-rebirth",
            "supported": True,
            "actionable": True,
            "destructive": True,
            "includeInStartAll": False,
            "defaultEnabled": False,
            "action": {
                "kind": "gui_sequence",
                "requiresExplicitConfirmation": True,
                "steps": [
                    {"kind": "gui_activate", "path": rebirth_open_paths[0]},
                    {"kind": "gui_activate", "path": rebirth_confirm_paths[0]},
                ],
                "intervalSeconds": max(1.5, round(delay * 3.0, 2)),
            },
            "monitor": {
                "kind": "multi-state",
                "candidateStatePaths": [path for path in candidate_paths if "rebirth" in path.lower()],
            },
            "evidence": {
                "featureCandidate": "rebirth",
                "openPath": rebirth_open_paths[0],
                "confirmPath": rebirth_confirm_paths[0],
                "readiness": rebirth_feature.get("readiness") or rebirth_readiness.get("readiness"),
            },
        })
    else:
        unsupported_features.append({
            "id": "auto_rebirth",
            "title": "Auto Rebirth",
            "category": "auto-rebirth",
            "reason": "Observed rebirth interactions do not include both open and confirm actions",
            "evidence": {
                "rebirthOpenPaths": rebirth_open_paths,
                "rebirthConfirmPaths": rebirth_confirm_paths,
                "featureCandidate": "rebirth",
            },
        })

    if len(inventory_gui_paths) >= 2:
        add_feature({
            "id": "inventory_management",
            "title": "Inventory Actions",
            "category": "inventory",
            "supported": True,
            "actionable": True,
            "destructive": False,
            "includeInStartAll": False,
            "defaultEnabled": False,
            "action": {
                "kind": "gui_activate_many",
                "paths": inventory_gui_paths,
                "intervalSeconds": max(1.0, round(delay * 2.0, 2)),
            },
            "monitor": {
                "kind": "multi-state",
                "candidateStatePaths": [
                    path for path in candidate_paths
                    if "backpack.tools.count" in path.lower() or "inventory" in path.lower()
                ],
            },
            "evidence": {
                "inventoryGuiPathCount": len(inventory_gui_paths),
            },
        })

    quest_actionable_paths = sorted(set(quest_select_paths + quest_claim_paths))

    if len(quest_select_paths) > 0 and len(quest_claim_paths) > 0 and len(quest_claim_state_paths) > 0:
        add_feature({
            "id": "quest_automation",
            "title": "Quest Automation",
            "category": "quest",
            "supported": True,
            "actionable": True,
            "destructive": False,
            "includeInStartAll": False,
            "defaultEnabled": False,
            "action": {
                "kind": "quest_train_workflow",
                "trainFeatureId": "auto_train",
                "questOpenPaths": quest_select_paths[:8],
                "questClaimPaths": quest_claim_paths[:8],
                "intervalSeconds": max(0.9, round(delay * 1.8, 2)),
            },
            "outcomeContract": {
                "kind": "quest-state-change",
                "verificationWindowSeconds": max(2.5, round(delay * 4.0, 2)),
                "statePaths": quest_claim_state_paths,
                "strictlyRequireObservedDelta": True,
            },
            "monitor": {
                "kind": "quest-repetition",
                "candidateStatePaths": quest_claim_state_paths,
            },
            "evidence": {
                "guiQuestPathCount": len(quest_gui_paths),
                "questSelectPathCount": len(quest_select_paths),
                "questClaimPathCount": len(quest_claim_paths),
                "questClaimStatePathCount": len(quest_claim_state_paths),
                "repetitionStatePathCount": len(repetition_paths),
                "workflowBasis": "quest claim-state plus actionable quest GUI evidence",
            },
        })
        feature_dependencies["quest_automation"] = ["auto_train"]
    elif len(repetition_paths) > 0:
        missing_requirements: list[str] = []
        if len(quest_select_paths) == 0:
            missing_requirements.append("quest selection/acceptance controls")
        if len(quest_claim_paths) == 0:
            missing_requirements.append("quest claim controls")
        if len(quest_claim_state_paths) == 0:
            missing_requirements.append("quest completion/claim state deltas")
        add_feature({
            "id": "quest_monitor",
            "title": "Quest Monitor",
            "category": "quest-monitor",
            "supported": True,
            "actionable": False,
            "destructive": False,
            "includeInStartAll": False,
            "defaultEnabled": False,
            "action": {
                "kind": "observe_only",
                "intervalSeconds": max(1.0, round(delay * 2.2, 2)),
            },
            "monitor": {
                "kind": "quest-repetition",
                "candidateStatePaths": repetition_paths,
            },
            "evidence": {
                "guiQuestPathCount": len(quest_gui_paths),
                "questSelectPathCount": len(quest_select_paths),
                "questClaimPathCount": len(quest_claim_paths),
                "questClaimStatePathCount": len(quest_claim_state_paths),
                "repetitionStatePathCount": len(repetition_paths),
                "workflowBasis": "progress monitoring only; actionable quest steps not fully evidenced",
                "missingEvidence": missing_requirements,
            },
        })
    elif len(quest_gui_paths) > 0:
        add_feature({
            "id": "quest_interface",
            "title": "Quest Interface",
            "category": "quest-interface",
            "supported": True,
            "actionable": True,
            "destructive": False,
            "includeInStartAll": False,
            "defaultEnabled": False,
            "action": {
                "kind": "gui_activate_many",
                "paths": quest_actionable_paths[:10],
                "intervalSeconds": max(1.0, round(delay * 2.2, 2)),
            },
            "monitor": {
                "kind": "quest-repetition",
                "candidateStatePaths": [],
            },
            "evidence": {
                "guiQuestPathCount": len(quest_gui_paths),
                "questSelectPathCount": len(quest_select_paths),
                "questClaimPathCount": len(quest_claim_paths),
                "repetitionStatePathCount": 0,
                "workflowBasis": "quest GUI interactions only",
            },
        })
    else:
        unsupported_features.append({
            "id": "quest_automation",
            "title": "Quest Automation",
            "category": "quest",
            "reason": "No quest GUI controls or repetition-progress states were observed",
            "evidence": {"repetitionStatePathCount": len(repetition_paths)},
        })

    if len(proximity_paths) == 0:
        unsupported_features.append({
            "id": "proximity_interactions",
            "title": "Proximity Interactions",
            "category": "proximity",
            "reason": "No explicit ProximityPrompt trigger paths were observed",
            "evidence": {
                "observedInteractActionKinds": sum(1 for event in events if event.get("actionKind") == "interact"),
            },
        })

    if not training_discovery["worldStationEvidencePresent"]:
        unsupported_features.append({
            "id": "world_training_stations",
            "title": "World Training Stations",
            "category": "training-stations",
            "reason": "No world-space training station interactions were evidenced in this export",
            "evidence": {
                "worldStationCandidates": len(training_discovery["worldStations"]),
                "proximityPromptTriggers": len(proximity_paths),
            },
        })

    version_file = pathlib.Path(__file__).resolve().parent.parent / "version.txt"
    try:
        project_version = version_file.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        project_version = "unknown"

    generated_feature_ids = [item["id"] for item in feature_contracts]

    return {
        "schemaVersion": "117.observation-tool-contract.6",
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
        "timing": {
            "activationIntervalSeconds": activation_interval,
            "pollIntervalSeconds": poll_interval,
            "delayedOutcomeWindowSeconds": round(delay, 3),
            "stallWindowSeconds": stall_window,
            "minActivationIntervalSeconds": 0.10,
            "maxActivationIntervalSeconds": 2.00,
            "minOutcomeWindowSeconds": 0.25,
            "maxOutcomeWindowSeconds": 10.00,
        },
        "outcomeModel": {
            "kind": "delayed-cumulative",
            "primaryStatePath": primary_path,
            "candidateStatePaths": candidate_paths,
            "questRepetitionStatePaths": repetition_paths,
            "ignoredNoisyStatePaths": noisy_paths,
            "observedStateKeyCount": len(state_key_stats),
        },
        "outcomeStateKeys": candidate_paths,
        "trainingDiscovery": training_discovery,
        "featureContracts": feature_contracts,
        "unsupportedFeatures": unsupported_features,
        "featureDependencies": feature_dependencies,
        "deduplicatedFeatures": deduplicated_features,
        "generatedFeatureIds": generated_feature_ids,
        "interactionSummary": {
            "totalObservedEvents": len(events),
            "controlTypesObserved": sorted(control_paths_by_type.keys()),
            "featureCandidatesObserved": sorted({event.get("featureCandidate") for event in events if isinstance(event.get("featureCandidate"), str)}),
            "rewardActionPathCount": len(reward_activation_paths),
            "rewardClaimPathCount": len(reward_claim_paths),
            "rewardMenuOpenPathCount": len(reward_open_paths),
            "rewardGuardedPathCount": len(reward_guarded_paths),
            "rewardStatePathCount": len(reward_state_paths),
            "questGuiPathCount": len(quest_gui_paths),
            "questSelectPathCount": len(quest_select_paths),
            "questClaimPathCount": len(quest_claim_paths),
            "questClaimStatePathCount": len(quest_claim_state_paths),
            "questRepetitionPathCount": len(repetition_paths),
            "trainingMethodCount": len(training_methods),
            "statRegistryCount": len(stat_registry_entries),
            "progressionStatCount": len(stat_training_targets),
            "actionStatRelationshipCount": len(action_stat_relationships),
            "passiveProgressionSignalCount": len(passive_progression_stats),
            "worldTrainingStationCount": len(world_station_candidates),
            "proximityPromptTriggerCount": len(proximity_paths),
        },
        "generatorMetadata": {
            "generatorVersion": "receiver_generation_pipeline.observation-contract.6",
            "projectVersion": project_version,
            "inspectorSchemaVersion": payload.get("schemaVersion"),
        },
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
    }



def _render_observation_auto_train_luau(contract: dict[str, Any]) -> str:
    template_path = pathlib.Path(__file__).with_name("observation_auto_train_template.lua")
    template = template_path.read_text(encoding="utf-8")
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
    script_path = scenario_output_root / "LycolesGeneratedFeatureBatch.lua"
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

    supported_features = [item for item in (contract.get("featureContracts") or []) if item.get("supported") is not False]
    unsupported_features = list(contract.get("unsupportedFeatures") or [])
    executable_features = [
        item
        for item in supported_features
        if item.get("actionable", True) and ((item.get("action") or {}).get("kind") != "observe_only")
    ]
    monitor_features = [item for item in supported_features if item not in executable_features]

    summary = {
        "schemaVersion": "117.observation-recovery-summary.5",
        "status": "generated-observation-contract",
        "generatedScriptPath": str(script_path),
        "generatedScriptKind": "observation-multi-feature-batch",
        "loaderTemplatePath": str(loader_path),
        "contractPath": str(contract_path),
        "toolPath": contract["toolPath"],
        "primaryOutcomePath": ((contract.get("outcomeModel") or {}).get("primaryStatePath")),
        "questRepetitionStatePathCount": len(((contract.get("outcomeModel") or {}).get("questRepetitionStatePaths") or [])),
        "outcomeStateKeyCount": len(contract.get("outcomeStateKeys") or []),
        "statRegistryCount": len((((contract.get("trainingDiscovery") or {}).get("statRegistry") or {}).get("stats") or [])),
        "statTrainingTargetCount": len(((contract.get("trainingDiscovery") or {}).get("statTrainingTargets") or [])),
        "actionStatRelationshipCount": len((((contract.get("trainingDiscovery") or {}).get("actionStatEvidence") or {}).get("relationships") or [])),
        "implementedFeatures": [item.get("id") for item in executable_features],
        "monitoredFeatures": [item.get("id") for item in monitor_features],
        "excludedFeatures": [item.get("id") for item in unsupported_features],
        "unsupportedFeatures": unsupported_features,
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
            "automaticExecutionReadyWorkflowCandidates": len(executable_features),
            "requestAlignedAutomaticExecutionReadyWorkflows": len(executable_features),
            "selectedWorkflowCandidateId": "observation-recovery-multi-feature-contract",
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
    output_root = pathlib.Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    resolved_parts_dir, archive_ingestion = _resolve_parts_input(pathlib.Path(parts_dir), output_root)

    service = SERVICE.LycolesGenerationService(output_root=output_root)
    request = SERVICE.GenerationRequest(
        evidence_kind="parts_dir",
        evidence_path=resolved_parts_dir,
        requested_capability=requested_capability,
        observation_paths=tuple(pathlib.Path(path).resolve() for path in (observation_paths or [])),
        require_executable=require_executable,
    )
    result = service.run_sync(request)
    if archive_ingestion is not None:
        result["partsArchiveIngestion"] = archive_ingestion
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

    local_parser = subparsers.add_parser("from-parts", help="Generate from local parts directory or zipped multipart archive")
    local_parser.add_argument("--parts-dir", required=True,
        help="Path to parts directory or .zip archive containing multipart JSON payloads")
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
