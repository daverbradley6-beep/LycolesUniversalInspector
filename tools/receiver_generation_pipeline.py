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


_OCCURRENCE_SUFFIX_RE = re.compile(r"\[occurrence:\d+\]$", re.IGNORECASE)


def _canonical_object_path(path: Any) -> Optional[str]:
    if not isinstance(path, str):
        return None
    value = path.strip()
    if not value:
        return None
    value = _OCCURRENCE_SUFFIX_RE.sub("", value).rstrip(".")
    return value or None


def _path_depth(path: str) -> int:
    return len([item for item in path.split(".") if item])



def _workspace_root_like_path(path: Optional[str]) -> bool:
    if not isinstance(path, str):
        return False
    low = path.strip().lower().rstrip(".")
    if low in {"workspace", "workspace.rendered", "workspace.rendered.pets"}:
        return True
    return low.startswith("workspace.") and low.count(".") <= 1


_PICKUP_NAME_CATEGORY_TOKENS: dict[str, tuple[str, ...]] = {
    "currency": ("coin", "coins", "gem", "gems", "ticket", "tickets", "gold", "cash", "money", "token", "orb"),
    "ammunition": ("ammo", "bullet", "shell", "mag", "magazine", "rocket"),
    "health-or-armour": ("health", "heart", "med", "medkit", "armor", "armour", "shield"),
    "resource": ("resource", "ore", "wood", "stone", "crystal", "material", "drop"),
    "quest-or-progress": ("quest", "objective", "artifact", "collect", "pickup", "reward"),
    "boost-or-status": ("boost", "buff", "multiplier", "xp", "exp"),
}

_DECORATIVE_PATH_TOKENS = (
    "decoration", "decor", "foliage", "tree", "rock", "terrain", "mesh", "statue", "grass", "mountain",
)


def _pickup_category_from_path(path: str) -> str:
    low = path.lower()
    for category, tokens in _PICKUP_NAME_CATEGORY_TOKENS.items():
        if any(token in low for token in tokens):
            return category
    return "unknown"


def _pickup_like_name_score(path: str) -> float:
    low = path.lower()
    score = 0.0
    for tokens in _PICKUP_NAME_CATEGORY_TOKENS.values():
        if any(token in low for token in tokens):
            score += 1.5
            break
    if "pickup" in low or "collect" in low:
        score += 1.0
    if any(token in low for token in _DECORATIVE_PATH_TOKENS):
        score -= 1.4
    return score


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


def ingest_parts_archives(
    archive_paths: Sequence[pathlib.Path],
    extracted_root: pathlib.Path,
    *,
    expected_scan_id: Optional[str] = None,
) -> dict[str, Any]:
    archives = [pathlib.Path(item).resolve() for item in archive_paths]
    if not archives:
        raise ValueError("at least one parts archive is required")
    if len(archives) == 1:
        result = ingest_parts_archive(archives[0], extracted_root, expected_scan_id=expected_scan_id)
        result["sourceArchiveCount"] = 1
        result["sourceArchives"] = [str(archives[0])]
        result["combinedArchiveSha256"] = result.get("archiveSha256")
        return result

    for archive in archives:
        if not archive.is_file():
            raise ValueError(f"parts archive not found: {archive}")
        if archive.suffix.lower() != ".zip":
            raise ValueError("parts archive must be a .zip file")

    extracted_root = pathlib.Path(extracted_root).resolve()
    extracted_root.mkdir(parents=True, exist_ok=True)

    archive_sha256_map = {str(archive): _sha256_file(archive) for archive in archives}
    combined_archive_sha256 = hashlib.sha256(
        json.dumps(sorted(archive_sha256_map.items()), separators=(",", ":")).encode("utf-8")
    ).hexdigest()

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
        for archive in archives:
            with zipfile.ZipFile(archive) as bundle:
                members = [entry for entry in bundle.infolist() if not entry.is_dir() and entry.filename.lower().endswith(".json")]
                if not members:
                    raise ValueError(f"archive has no JSON parts: {archive.name}")
                for entry in members:
                    if entry.file_size > 8_000_000:
                        raise ValueError(f"archive member too large: {archive.name}:{entry.filename}")
                    raw = bundle.read(entry)
                    context = f"archive member {archive.name}:{entry.filename}"
                    payload = _parse_json_payload(raw, context)
                    safe_name = pathlib.PurePosixPath(entry.filename).name
                    if not safe_name:
                        raise ValueError(f"invalid archive member name: {entry.filename}")

                    digest = _sha256_bytes(raw)
                    previous_digest = name_digests.get(safe_name)
                    if previous_digest is not None and previous_digest != digest:
                        raise ValueError(f"conflicting duplicate filename across archives: {safe_name}")
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
                    if not target_path.exists():
                        target_path.write_bytes(raw)
                        extracted_json_count += 1

        if not part_records:
            raise ValueError("archives do not contain multipart scan parts")
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

        manifest_uploaded_parts = [
            int(item.get("uploadedParts"))
            for item in manifest_records
            if type(item.get("uploadedParts")) is int and item.get("uploadedParts") >= 0
        ]
        uploaded_parts_observed = max(manifest_uploaded_parts) if manifest_uploaded_parts else None
        upload_ack_gap = (
            max(0, part_count - uploaded_parts_observed)
            if uploaded_parts_observed is not None
            else None
        )

        target = extracted_root / f"archive_{scan_id}"
        metadata_path = target / ".archive-ingestion.meta"
        if target.is_dir() and metadata_path.is_file():
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                metadata = None
            if isinstance(metadata, dict) and metadata.get("combinedArchiveSha256") == combined_archive_sha256:
                shutil.rmtree(staging)
                metadata["reusedExistingExtraction"] = True
                metadata["outputDir"] = str(target)
                return metadata
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
            "combinedArchiveSha256": combined_archive_sha256,
            "archiveSha256": combined_archive_sha256,
            "archiveSha256Map": archive_sha256_map,
            "sourceArchiveCount": len(archives),
            "sourceArchives": [str(item) for item in archives],
            "manifestUploadedPartsObserved": uploaded_parts_observed,
            "receiverAcknowledgementGap": upload_ack_gap,
            "receiverAcknowledgementComplete": (
                uploaded_parts_observed is not None and uploaded_parts_observed >= part_count
            ),
            "localArchiveComplete": True,
            "reusedExistingExtraction": False,
        }
        metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        metadata["outputDir"] = str(target)
        return metadata
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _build_baseline_parts_context(parts_dir: pathlib.Path) -> dict[str, Any]:
    root = pathlib.Path(parts_dir).resolve()
    if not root.is_dir():
        raise ValueError(f"baseline parts directory not found: {root}")

    part_files = sorted(root.glob("*_part-*.json"))
    if not part_files:
        part_files = sorted(path for path in root.glob("*.json") if path.name != "receiver-manifest.json")

    object_count = 0
    workspace_object_count = 0
    replicated_storage_object_count = 0
    actionable_world_index: dict[str, dict[str, Any]] = {}

    scan_id: Optional[str] = None
    place_id: Optional[int] = None
    part_count: Optional[int] = None

    for path in part_files:
        try:
            payload = _read_json_document(path)
        except Exception:
            continue
        if scan_id is None and isinstance(payload.get("scanId"), str):
            scan_id = payload.get("scanId")
        if place_id is None and type(payload.get("placeId")) is int:
            place_id = payload.get("placeId")
        if part_count is None and type(payload.get("partCount")) is int:
            part_count = payload.get("partCount")

        objects = payload.get("objects") if isinstance(payload.get("objects"), list) else []
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            object_count += 1
            raw_path = _canonical_object_path(obj.get("path"))
            if not raw_path:
                continue
            low_path = raw_path.lower()
            if low_path.startswith("replicatedstorage."):
                replicated_storage_object_count += 1
                continue
            if low_path.startswith("workspace."):
                workspace_object_count += 1

            interaction = obj.get("interaction") if isinstance(obj.get("interaction"), dict) else {}
            gui_control = obj.get("guiControl") if isinstance(obj.get("guiControl"), dict) else {}
            class_name = obj.get("class") if isinstance(obj.get("class"), str) else "unknown"

            mechanisms: list[str] = []
            if class_name == "ProximityPrompt" or interaction.get("hasPrompt") is True or "actionText" in interaction:
                mechanisms.append("prompt")
            if class_name == "ClickDetector" or interaction.get("hasClickDetector") is True:
                mechanisms.append("click")
            if interaction.get("touchInterest") is True:
                mechanisms.append("touch")

            gui_actionable = bool(gui_control) and bool(gui_control.get("interactable") is True or gui_control.get("active") is True)
            if not mechanisms and not gui_actionable:
                continue
            if not low_path.startswith("workspace."):
                continue

            bucket = actionable_world_index.setdefault(raw_path, {
                "path": raw_path,
                "class": class_name,
                "count": 0,
                "mechanisms": {},
                "guiActionable": False,
                "interactionScore": 0,
            })
            bucket["count"] += 1
            if gui_actionable:
                bucket["guiActionable"] = True
                bucket["interactionScore"] += 1
            for mechanism in mechanisms:
                bucket["mechanisms"][mechanism] = bucket["mechanisms"].get(mechanism, 0) + 1
                bucket["interactionScore"] += 2

    return {
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "objectCount": object_count,
        "workspaceObjectCount": workspace_object_count,
        "replicatedStorageObjectCount": replicated_storage_object_count,
        "actionableWorldObjectIndex": actionable_world_index,
    }

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


_DISCOVERY_FIXTURE_TOKENS: dict[str, tuple[str, ...]] = {
    "muscle_legends": (
        "leaderstats.strength",
        "backpack.weight",
        "protein shake",
        "rep titan",
        "tough bar",
        "handstands",
    ),
    "arsenal": (
        "weapon",
        "reload",
        "magazine",
        "headshot",
        "killstreak",
    ),
}


def _infer_system_category(path: Optional[str], feature_candidate: Optional[str], action_kind: Optional[str]) -> str:
    candidate = (feature_candidate or "").strip().lower()
    if candidate:
        if "quest" in candidate:
            return "quests-and-achievements"
        if "reward" in candidate:
            return "rewards-and-cooldowns"
        if "pet" in candidate:
            return "pets-and-companions"
        if "inventory" in candidate:
            return "inventory-and-equipment"
        if "rebirth" in candidate or "prestige" in candidate:
            return "rebirth-or-prestige"
        if "shop" in candidate or "upgrade" in candidate:
            return "shops-and-upgrades"
        if "travel" in candidate or "portal" in candidate or "teleport" in candidate:
            return "movement-and-navigation"
        if candidate in {"combat", "train", "training"}:
            return "tools-and-abilities"
        return candidate.replace("_", "-")

    low_path = (path or "").lower()
    low_action = (action_kind or "").lower()
    if any(token in low_path for token in ("quest", "objective", "achievement")):
        return "quests-and-achievements"
    if any(token in low_path for token in ("reward", "gift", "claim", "cooldown", "timer")):
        return "rewards-and-cooldowns"
    if any(token in low_path for token in ("egg", "hatch", "pet", "companion")):
        return "pets-and-companions"
    if any(token in low_path for token in ("shop", "upgrade", "buy", "sell")):
        return "shops-and-upgrades"
    if any(token in low_path for token in ("inventory", "equip", "backpack")):
        return "inventory-and-equipment"
    if any(token in low_path for token in ("bubble", "coin", "currency", "gem", "gold", "money")):
        return "progression-and-currencies"
    if any(token in low_path for token in ("rebirth", "prestige", "reset")):
        return "rebirth-or-prestige"
    if any(token in low_path for token in ("portal", "teleport", "world", "zone", "island")):
        return "movement-and-navigation"
    if "tool.activated" in low_action or "fire" in low_action or "interact" in low_action:
        return "tools-and-abilities"
    return "uncategorized"


def _build_universal_discovery_report(
    payload: dict[str, Any],
    *,
    requested_capability: Optional[str] = None,
    generation_contract: Optional[dict[str, Any]] = None,
    baseline_context: Optional[dict[str, Any]] = None,
    baseline_archive_validation: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    events = _interaction_events_from_payload(payload)
    objects = payload.get("objects") if isinstance(payload.get("objects"), list) else []
    features = payload.get("features") if isinstance(payload.get("features"), list) else []
    readiness = payload.get("featureReadiness") if isinstance(payload.get("featureReadiness"), dict) else {}
    baseline_context = baseline_context if isinstance(baseline_context, dict) else {}
    baseline_archive_validation = baseline_archive_validation if isinstance(baseline_archive_validation, dict) else {}
    baseline_actionable_index = (
        baseline_context.get("actionableWorldObjectIndex")
        if isinstance(baseline_context.get("actionableWorldObjectIndex"), dict)
        else {}
    )

    control_type_counts: dict[str, int] = {}
    action_kind_counts: dict[str, int] = {}
    feature_candidate_counts: dict[str, int] = {}
    unique_paths: set[str] = set()

    state_registry: dict[str, dict[str, Any]] = {}
    relationships: list[dict[str, Any]] = []

    workflow_nodes: dict[str, dict[str, Any]] = {}
    workflow_edges: dict[tuple[str, str], int] = {}
    workflow_transactions: dict[str, list[dict[str, Any]]] = {}

    requirements_samples: list[dict[str, Any]] = []
    world_candidates: dict[str, dict[str, Any]] = {}

    attributed_events = 0
    events_with_state_delta = 0
    events_with_gui_transition = 0
    path_identity_resolved = 0
    path_identity_total = 0


    def _position_from_value(value: Any) -> Optional[dict[str, float]]:
        if not isinstance(value, dict):
            return None
        x = _numeric(value.get("x"))
        y = _numeric(value.get("y"))
        z = _numeric(value.get("z"))
        if x is None or y is None or z is None:
            return None
        return {"x": round(x, 4), "y": round(y, 4), "z": round(z, 4)}

    def _normalize_snapshot(sample: dict[str, Any], *, fallback_phase: str) -> Optional[dict[str, Any]]:
        if not isinstance(sample, dict):
            return None
        position = _position_from_value(sample.get("position"))
        sampled = bool(sample.get("sampled", position is not None))
        sequence = sample.get("interactionSequence") if isinstance(sample.get("interactionSequence"), int) else None
        tx = sample.get("transactionId") if isinstance(sample.get("transactionId"), str) else None
        phase = sample.get("phase") if isinstance(sample.get("phase"), str) and sample.get("phase") else fallback_phase
        elapsed = _numeric(sample.get("sessionElapsedSeconds"))
        return {
            "interactionSequence": sequence,
            "transactionId": tx,
            "phase": phase,
            "sampled": sampled,
            "interpolated": bool(sample.get("interpolated") is True),
            "position": position,
            "sessionElapsedSeconds": round(elapsed, 4) if elapsed is not None else None,
            "characterGeneration": sample.get("characterGeneration") if isinstance(sample.get("characterGeneration"), int) else None,
            "worldContext": sample.get("worldContext") if isinstance(sample.get("worldContext"), dict) else None,
            "source": sample.get("source") if isinstance(sample.get("source"), str) else None,
            "sampleKind": sample.get("sampleKind") if isinstance(sample.get("sampleKind"), str) else None,
            "windowSeconds": _numeric(sample.get("windowSeconds")),
            "speedStudsPerSecond": _numeric(sample.get("speedStudsPerSecond")),
            "characterState": sample.get("characterState") if isinstance(sample.get("characterState"), str) else None,
            "characterOrientation": _normalize_orientation(sample.get("characterOrientation")),
            "cameraOrientation": _normalize_orientation(sample.get("cameraOrientation")),
            "cameraCharacterHeadingDeltaDegrees": _numeric(sample.get("cameraCharacterHeadingDeltaDegrees")),
        }


    def _normalize_heading(value: Any) -> Optional[float]:
        heading = _numeric(value)
        if heading is None:
            return None
        heading = heading % 360.0
        if heading < 0:
            heading += 360.0
        return round(heading, 2)

    def _compass_from_heading(heading: Optional[float]) -> Optional[str]:
        if heading is None:
            return None
        labels = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        index = int(((heading + 22.5) % 360.0) // 45.0)
        return labels[index]

    def _heading_from_forward(forward: Optional[dict[str, float]]) -> Optional[float]:
        if not isinstance(forward, dict):
            return None
        x = _numeric(forward.get("x"))
        z = _numeric(forward.get("z"))
        if x is None or z is None:
            return None
        if abs(x) < 1e-6 and abs(z) < 1e-6:
            return None
        return _normalize_heading(math.degrees(math.atan2(x, -z)))

    def _normalize_orientation(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        forward = _position_from_value(value.get("forward"))
        heading = _normalize_heading(value.get("headingDegrees"))
        if heading is None:
            heading = _heading_from_forward(forward)
        return {
            "id": value.get("id") if isinstance(value.get("id"), str) else None,
            "source": value.get("source") if isinstance(value.get("source"), str) else None,
            "sampledAt": value.get("sampledAt") if isinstance(value.get("sampledAt"), str) else None,
            "sessionElapsedSeconds": _numeric(value.get("sessionElapsedSeconds")),
            "characterGeneration": value.get("characterGeneration") if isinstance(value.get("characterGeneration"), int) else None,
            "characterId": value.get("characterId") if isinstance(value.get("characterId"), str) else None,
            "worldPosition": _position_from_value(value.get("worldPosition")),
            "forward": forward,
            "headingDegrees": heading,
            "compass": value.get("compass") if isinstance(value.get("compass"), str) else _compass_from_heading(heading),
            "worldContext": value.get("worldContext") if isinstance(value.get("worldContext"), dict) else None,
            "cameraToCharacterHeadingDeltaDegrees": _numeric(value.get("cameraToCharacterHeadingDeltaDegrees")),
        }

    def _normalize_cursor_observation(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        screen = value.get("screen") if isinstance(value.get("screen"), dict) else {}
        normalized = value.get("normalizedViewport") if isinstance(value.get("normalizedViewport"), dict) else {}
        viewport = value.get("viewportSize") if isinstance(value.get("viewportSize"), dict) else {}
        return {
            "id": value.get("id") if isinstance(value.get("id"), str) else None,
            "observedAt": value.get("observedAt") if isinstance(value.get("observedAt"), str) else None,
            "sessionElapsedSeconds": _numeric(value.get("sessionElapsedSeconds")),
            "reason": value.get("reason") if isinstance(value.get("reason"), str) else None,
            "cursorAvailable": bool(value.get("cursorAvailable") is True),
            "inputType": value.get("inputType") if isinstance(value.get("inputType"), str) else None,
            "screen": {"x": _numeric(screen.get("x")), "y": _numeric(screen.get("y"))} if isinstance(screen, dict) else None,
            "normalizedViewport": {
                "x": _numeric(normalized.get("x")),
                "y": _numeric(normalized.get("y")),
            } if isinstance(normalized, dict) else None,
            "viewportSize": {
                "width": _numeric(viewport.get("width")),
                "height": _numeric(viewport.get("height")),
            } if isinstance(viewport, dict) else None,
            "coordinateSpace": value.get("coordinateSpace") if isinstance(value.get("coordinateSpace"), str) else None,
        }

    def _normalize_input_gesture_intent(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        signals = value.get("targetAndOutcomeSignals") if isinstance(value.get("targetAndOutcomeSignals"), dict) else {}
        return {
            "schemaVersion": value.get("schemaVersion") if isinstance(value.get("schemaVersion"), str) else None,
            "primaryIntent": value.get("primaryIntent") if isinstance(value.get("primaryIntent"), str) else None,
            "clickCandidate": bool(value.get("clickCandidate") is True),
            "cameraDragCandidate": bool(value.get("cameraDragCandidate") is True),
            "heldInputCandidate": bool(value.get("heldInputCandidate") is True),
            "guiInteractionCandidate": bool(value.get("guiInteractionCandidate") is True),
            "worldInteractionCandidate": bool(value.get("worldInteractionCandidate") is True),
            "ambiguousInput": bool(value.get("ambiguousInput") is True),
            "likelyCameraMovement": bool(value.get("likelyCameraMovement") is True),
            "likelyGameplayInteraction": bool(value.get("likelyGameplayInteraction") is True),
            "targetAndOutcomeSignals": {
                "guiTargetConfirmed": bool(signals.get("guiTargetConfirmed") is True),
                "worldTargetConfirmed": bool(signals.get("worldTargetConfirmed") is True),
                "worldRaycastOnly": bool(signals.get("worldRaycastOnly") is True),
                "callbackObserved": bool(signals.get("callbackObserved") is True),
                "stateChangeTemporallyAssociated": bool(signals.get("stateChangeTemporallyAssociated") is True),
                "meaningfulGameplayOutcomeObserved": bool(signals.get("meaningfulGameplayOutcomeObserved") is True),
                "outcomeCorroborated": bool(signals.get("outcomeCorroborated") is True),
                "targetAmbiguous": bool(signals.get("targetAmbiguous") is True),
            },
            "note": value.get("note") if isinstance(value.get("note"), str) else None,
        }

    def _normalize_click_target_observation(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        cursor = _normalize_cursor_observation(value.get("cursor"))
        topmost = value.get("topmostGuiTarget") if isinstance(value.get("topmostGuiTarget"), dict) else None
        raycast = value.get("raycastTarget") if isinstance(value.get("raycastTarget"), dict) else None
        confidence = value.get("targetIdentificationConfidence") if isinstance(value.get("targetIdentificationConfidence"), dict) else {}
        candidates: list[dict[str, Any]] = []
        for item in (value.get("guiCandidates") if isinstance(value.get("guiCandidates"), list) else [])[:12]:
            if not isinstance(item, dict):
                continue
            candidates.append({
                "path": item.get("path") if isinstance(item.get("path"), str) else None,
                "class": item.get("class") if isinstance(item.get("class"), str) else None,
                "name": item.get("name") if isinstance(item.get("name"), str) else None,
                "visible": bool(item.get("visible") is True),
                "active": bool(item.get("active") is True),
                "interactable": bool(item.get("interactable") is True),
                "zIndex": item.get("zIndex") if isinstance(item.get("zIndex"), int) else None,
            })
        missing = [
            item for item in (value.get("missingEvidence") if isinstance(value.get("missingEvidence"), list) else [])
            if isinstance(item, str)
        ][:8]
        diagnostics = value.get("pipelineDiagnostics") if isinstance(value.get("pipelineDiagnostics"), dict) else {}
        resolution = value.get("targetResolution") if isinstance(value.get("targetResolution"), dict) else {}
        return {
            "id": value.get("id") if isinstance(value.get("id"), str) else None,
            "observedAt": value.get("observedAt") if isinstance(value.get("observedAt"), str) else None,
            "sessionElapsedSeconds": _numeric(value.get("sessionElapsedSeconds")),
            "mouseButton": value.get("mouseButton") if isinstance(value.get("mouseButton"), str) else None,
            "inputType": value.get("inputType") if isinstance(value.get("inputType"), str) else None,
            "inputGestureId": value.get("inputGestureId") if isinstance(value.get("inputGestureId"), str) else None,
            "inputIntent": _normalize_input_gesture_intent(value.get("inputIntent")),
            "cursorObservationId": value.get("cursorObservationId") if isinstance(value.get("cursorObservationId"), str) else None,
            "cursor": cursor,
            "guiCandidates": candidates,
            "topmostGuiTarget": {
                "path": topmost.get("path") if topmost and isinstance(topmost.get("path"), str) else None,
                "class": topmost.get("class") if topmost and isinstance(topmost.get("class"), str) else None,
            } if topmost else None,
            "raycastTarget": {
                "path": raycast.get("path") if raycast and isinstance(raycast.get("path"), str) else None,
                "class": raycast.get("class") if raycast and isinstance(raycast.get("class"), str) else None,
                "hitPosition": _position_from_value(raycast.get("hitPosition")) if raycast else None,
            } if raycast else None,
            "targetScope": value.get("targetScope") if isinstance(value.get("targetScope"), str) else None,
            "targetClassification": value.get("targetClassification") if isinstance(value.get("targetClassification"), str) else None,
            "inspectorOwnedTarget": bool(value.get("inspectorOwnedTarget") is True),
            "targetResolution": {
                "status": resolution.get("status") if isinstance(resolution.get("status"), str) else None,
                "classification": resolution.get("classification") if isinstance(resolution.get("classification"), str) else None,
                "unresolved": bool(resolution.get("unresolved") is True),
                "ambiguous": bool(resolution.get("ambiguous") is True),
                "inspectorOwnedTarget": bool(resolution.get("inspectorOwnedTarget") is True),
                "confirmedGuiTarget": bool(resolution.get("confirmedGuiTarget") is True),
                "confirmedWorldTarget": bool(resolution.get("confirmedWorldTarget") is True),
            },
            "playerPositionAtClick": _position_from_value(value.get("playerPositionAtClick")),
            "characterOrientationAtClick": _normalize_orientation(value.get("characterOrientationAtClick")),
            "cameraOrientationAtClick": _normalize_orientation(value.get("cameraOrientationAtClick")),
            "cameraCharacterHeadingDeltaDegrees": _numeric(value.get("cameraCharacterHeadingDeltaDegrees")),
            "pipelineDiagnostics": {
                "captureAttempted": bool(diagnostics.get("captureAttempted") is True),
                "guiHitTestAttempted": bool(diagnostics.get("guiHitTestAttempted") is True),
                "guiHitTestSucceeded": bool(diagnostics.get("guiHitTestSucceeded") is True),
                "guiHitTestReliable": bool(diagnostics.get("guiHitTestReliable") is True),
                "guiHitTestFailed": bool(diagnostics.get("guiHitTestFailed") is True),
                "guiHitTestApiAvailable": bool(diagnostics.get("guiHitTestApiAvailable") is True),
                "guiHitTestCoordinateSpace": diagnostics.get("guiHitTestCoordinateSpace") if isinstance(diagnostics.get("guiHitTestCoordinateSpace"), str) else None,
                "targetClassification": diagnostics.get("targetClassification") if isinstance(diagnostics.get("targetClassification"), str) else None,
                "ambiguousTarget": bool(diagnostics.get("ambiguousTarget") is True),
                "raycastAttempted": bool(diagnostics.get("raycastAttempted") is True),
                "raycastSucceeded": bool(diagnostics.get("raycastSucceeded") is True),
                "unresolvedTarget": bool(diagnostics.get("unresolvedTarget") is True),
            },
            "targetIdentificationConfidence": {
                "level": confidence.get("level") if isinstance(confidence.get("level"), str) else None,
                "score": _numeric(confidence.get("score")),
                "overlapDetected": bool(confidence.get("overlapDetected") is True),
                "cursorAvailable": bool(confidence.get("cursorAvailable") is True),
            },
            "missingEvidence": missing,
        }

    def _normalize_click_outcome_relationship(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        linked_sequences = [item for item in (value.get("linkedInteractionSequences") if isinstance(value.get("linkedInteractionSequences"), list) else []) if isinstance(item, int)]
        linked_transactions = [item for item in (value.get("linkedTransactionIds") if isinstance(value.get("linkedTransactionIds"), list) else []) if isinstance(item, str)]
        missing = [item for item in (value.get("missingEvidence") if isinstance(value.get("missingEvidence"), list) else []) if isinstance(item, str)][:10]
        verification = value.get("verificationStages") if isinstance(value.get("verificationStages"), dict) else {}
        diagnostics = value.get("clickLinkDiagnostics") if isinstance(value.get("clickLinkDiagnostics"), dict) else {}
        ambiguous = [item for item in (value.get("ambiguousCandidateClickObservationIds") if isinstance(value.get("ambiguousCandidateClickObservationIds"), list) else []) if isinstance(item, str)]
        provenance = value.get("provenance") if isinstance(value.get("provenance"), dict) else {}
        input_gesture_id = value.get("inputGestureId") if isinstance(value.get("inputGestureId"), str) else None
        if input_gesture_id is None and isinstance(provenance.get("inputGestureId"), str):
            input_gesture_id = provenance.get("inputGestureId")
        return {
            "id": value.get("id") if isinstance(value.get("id"), str) else None,
            "clickObservationId": value.get("clickObservationId") if isinstance(value.get("clickObservationId"), str) else None,
            "inputGestureId": input_gesture_id,
            "inputIntent": _normalize_input_gesture_intent(value.get("inputIntent")),
            "clickObserved": bool(value.get("clickObserved") is True),
            "targetIdentified": bool(value.get("targetIdentified") is True),
            "interactionCallbackObserved": bool(value.get("interactionCallbackObserved") is True),
            "stateChangeTemporallyAssociated": bool(value.get("stateChangeTemporallyAssociated") is True),
            "meaningfulGameplayOutcomeObserved": bool(value.get("meaningfulGameplayOutcomeObserved") is True),
            "outcomeCorroborated": bool(value.get("outcomeCorroborated") is True),
            "reproduciblyLiveValidated": bool(value.get("reproduciblyLiveValidated") is True),
            "causalityProven": bool(value.get("causalityProven") is True),
            "stage": value.get("stage") if isinstance(value.get("stage"), str) else None,
            "status": value.get("status") if isinstance(value.get("status"), str) else None,
            "verificationStages": {
                "clickObserved": bool(verification.get("clickObserved") is True),
                "targetIdentified": bool(verification.get("targetIdentified") is True),
                "interactionCallbackObserved": bool(verification.get("interactionCallbackObserved") is True),
                "stateChangeObserved": bool(verification.get("stateChangeObserved") is True),
                "temporallyAssociated": bool(verification.get("temporallyAssociated") is True),
                "multiSignalCorroborated": bool(verification.get("multiSignalCorroborated") is True),
                "reproduciblyValidated": bool(verification.get("reproduciblyValidated") is True),
                "causalityProven": bool(verification.get("causalityProven") is True),
            },
            "clickLinkDiagnostics": {
                "linkMethod": diagnostics.get("linkMethod") if isinstance(diagnostics.get("linkMethod"), str) else None,
                "resolutionScore": _numeric(diagnostics.get("resolutionScore")),
                "evaluatedCandidates": int(diagnostics.get("evaluatedCandidates")) if isinstance(diagnostics.get("evaluatedCandidates"), int) else None,
            },
            "ambiguousAssociation": bool(value.get("ambiguousAssociation") is True),
            "ambiguousCandidateClickObservationIds": ambiguous[:16],
            "linkedInteractionSequences": linked_sequences[:32],
            "linkedTransactionIds": linked_transactions[:32],
            "missingEvidence": missing,
        }

    def _normalize_input_gesture_observation(value: Any) -> Optional[dict[str, Any]]:
        if not isinstance(value, dict):
            return None
        metrics = value.get("metrics") if isinstance(value.get("metrics"), dict) else {}
        start_screen = value.get("startScreen") if isinstance(value.get("startScreen"), dict) else {}
        end_screen = value.get("endScreen") if isinstance(value.get("endScreen"), dict) else {}
        start_orientation = value.get("startOrientation") if isinstance(value.get("startOrientation"), dict) else {}
        end_orientation = value.get("endOrientation") if isinstance(value.get("endOrientation"), dict) else {}
        return {
            "id": value.get("id") if isinstance(value.get("id"), str) else None,
            "observedAt": value.get("observedAt") if isinstance(value.get("observedAt"), str) else None,
            "startedAt": value.get("startedAt") if isinstance(value.get("startedAt"), str) else None,
            "endedAt": value.get("endedAt") if isinstance(value.get("endedAt"), str) else None,
            "startSessionElapsedSeconds": _numeric(value.get("startSessionElapsedSeconds")),
            "endSessionElapsedSeconds": _numeric(value.get("endSessionElapsedSeconds")),
            "mouseButton": value.get("mouseButton") if isinstance(value.get("mouseButton"), str) else None,
            "inputType": value.get("inputType") if isinstance(value.get("inputType"), str) else None,
            "clickObservationId": value.get("clickObservationId") if isinstance(value.get("clickObservationId"), str) else None,
            "startCursorObservationId": value.get("startCursorObservationId") if isinstance(value.get("startCursorObservationId"), str) else None,
            "endCursorObservationId": value.get("endCursorObservationId") if isinstance(value.get("endCursorObservationId"), str) else None,
            "completionReason": value.get("completionReason") if isinstance(value.get("completionReason"), str) else None,
            "interrupted": bool(value.get("interrupted") is True),
            "startScreen": {
                "x": _numeric(start_screen.get("x")),
                "y": _numeric(start_screen.get("y")),
            } if isinstance(start_screen, dict) else None,
            "endScreen": {
                "x": _numeric(end_screen.get("x")),
                "y": _numeric(end_screen.get("y")),
            } if isinstance(end_screen, dict) else None,
            "startOrientation": {
                "cameraHeadingDegrees": _numeric(start_orientation.get("cameraHeadingDegrees")),
                "characterHeadingDegrees": _numeric(start_orientation.get("characterHeadingDegrees")),
                "cameraCharacterHeadingDeltaDegrees": _numeric(start_orientation.get("cameraCharacterHeadingDeltaDegrees")),
            } if isinstance(start_orientation, dict) else None,
            "endOrientation": {
                "cameraHeadingDegrees": _numeric(end_orientation.get("cameraHeadingDegrees")),
                "characterHeadingDegrees": _numeric(end_orientation.get("characterHeadingDegrees")),
                "cameraCharacterHeadingDeltaDegrees": _numeric(end_orientation.get("cameraCharacterHeadingDeltaDegrees")),
            } if isinstance(end_orientation, dict) else None,
            "metrics": {
                "durationSeconds": _numeric(metrics.get("durationSeconds")),
                "cursorDisplacementPixels": _numeric(metrics.get("cursorDisplacementPixels")),
                "cumulativeCursorTravelPixels": _numeric(metrics.get("cumulativeCursorTravelPixels")),
                "maxCursorDeltaPixels": _numeric(metrics.get("maxCursorDeltaPixels")),
                "movementSamples": int(metrics.get("movementSamples")) if isinstance(metrics.get("movementSamples"), int) else None,
                "cameraHeadingDeltaDegrees": _numeric(metrics.get("cameraHeadingDeltaDegrees")),
                "cameraCumulativeTurnDegrees": _numeric(metrics.get("cameraCumulativeTurnDegrees")),
                "maxCameraTurnStepDegrees": _numeric(metrics.get("maxCameraTurnStepDegrees")),
            },
            "intent": _normalize_input_gesture_intent(value.get("intent")),
        }

    def _cluster_key(
        position: dict[str, float],
        *,
        character_generation: Optional[int],
        world_context_key: Optional[str],
        object_anchor: Optional[str],
    ) -> tuple[Any, ...]:
        return (
            int(round(position["x"] / 22.0)),
            int(round(position["y"] / 12.0)),
            int(round(position["z"] / 22.0)),
            character_generation if isinstance(character_generation, int) else -1,
            (world_context_key or "height-band:" + str(int(round(position["y"] / 300.0))))[:80],
            (object_anchor or "")[:96],
        )

    for event in events:
        control_type = event.get("controlType") if isinstance(event.get("controlType"), str) else "unknown"
        action_kind = event.get("actionKind") if isinstance(event.get("actionKind"), str) else "unknown"
        feature_candidate = event.get("featureCandidate") if isinstance(event.get("featureCandidate"), str) else None
        path = event.get("path") if isinstance(event.get("path"), str) else None
        attribution = event.get("attribution") if isinstance(event.get("attribution"), str) else "unknown"

        control_type_counts[control_type] = control_type_counts.get(control_type, 0) + 1
        action_kind_counts[action_kind] = action_kind_counts.get(action_kind, 0) + 1
        if feature_candidate:
            feature_candidate_counts[feature_candidate] = feature_candidate_counts.get(feature_candidate, 0) + 1
        if path:
            unique_paths.add(path)

        if attribution not in {"unknown", "unattributed", "unattributed-input"}:
            attributed_events += 1

        path_identity = event.get("pathIdentity")
        if isinstance(path_identity, list):
            path_identity_total += 1
            if len(path_identity) > 0:
                path_identity_resolved += 1

        transaction_id = event.get("transactionId") if isinstance(event.get("transactionId"), str) else None
        if transaction_id:
            workflow_transactions.setdefault(transaction_id, []).append(event)

        preconditions = {}
        metadata = event.get("controlMetadata") if isinstance(event.get("controlMetadata"), dict) else {}
        for key in ("enabled", "active", "visible", "effectiveVisible", "interactable", "ancestorVisible", "screenEnabled", "requiresHandle"):
            if key in metadata:
                preconditions[key] = metadata.get(key)
        if preconditions and len(requirements_samples) < 80:
            requirements_samples.append({
                "path": path,
                "controlType": control_type,
                "featureCandidate": feature_candidate,
                "preconditions": preconditions,
            })

        gui_changes = event.get("guiStateChanges") if isinstance(event.get("guiStateChanges"), list) else []
        if len(gui_changes) > 0:
            events_with_gui_transition += 1

        state_changes = event.get("stateChanges") if isinstance(event.get("stateChanges"), list) else []
        numeric_delta_detected = False
        relationship_state_changes: list[dict[str, Any]] = []
        for change in state_changes:
            if not isinstance(change, dict):
                continue
            key = change.get("key")
            if not isinstance(key, str) or not key:
                continue
            before = change.get("before")
            after = change.get("after")
            before_num = _numeric(before)
            after_num = _numeric(after)
            delta = None
            if before_num is not None and after_num is not None:
                delta = round(after_num - before_num, 6)
                if delta != 0:
                    numeric_delta_detected = True

            classification = _classify_observed_state_key(key)
            category = _stat_category_from_key(key, classification)
            bucket = state_registry.setdefault(key, {
                "id": "state_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                "key": key,
                "name": _normalize_stat_name_from_key(key),
                "source": _stat_source_from_key(key),
                "category": category,
                "classification": classification,
                "changes": 0,
                "increases": 0,
                "decreases": 0,
                "lastBefore": None,
                "lastAfter": None,
                "sampleActions": [],
            })
            bucket["changes"] += 1
            bucket["lastBefore"] = before
            bucket["lastAfter"] = after
            if delta is not None and delta > 0:
                bucket["increases"] += 1
            elif delta is not None and delta < 0:
                bucket["decreases"] += 1
            if len(bucket["sampleActions"]) < 8:
                bucket["sampleActions"].append({
                    "path": path,
                    "controlType": control_type,
                    "featureCandidate": feature_candidate,
                    "before": before,
                    "after": after,
                    "delta": delta,
                })

            relationship_state_changes.append({
                "key": key,
                "before": before,
                "after": after,
                "delta": delta,
                "category": category,
            })

        if relationship_state_changes:
            events_with_state_delta += 1

        relationship_confidence = "low"
        if numeric_delta_detected:
            relationship_confidence = "medium"
            if feature_candidate and control_type in {"Tool.Activated", "GuiButton.Activated", "ProximityPrompt.Triggered"}:
                relationship_confidence = "high"

        relationships.append({
            "id": "rel_" + hashlib.sha256(f"{control_type}|{path}|{event.get('sequence')}|{event.get('sessionElapsedSeconds')}".encode("utf-8")).hexdigest()[:16],
            "interactionSequence": event.get("sequence") if isinstance(event.get("sequence"), int) else None,
            "transactionId": event.get("transactionId") if isinstance(event.get("transactionId"), str) else None,
            "sessionElapsedSeconds": event.get("sessionElapsedSeconds") if isinstance(event.get("sessionElapsedSeconds"), (int, float)) else None,
            "action": {
                "type": control_type,
                "kind": action_kind,
                "targetPath": path,
                "featureCandidate": feature_candidate,
                "clickObservationId": event.get("clickObservationId") if isinstance(event.get("clickObservationId"), str) else None,
                "clickTargetObservation": _normalize_click_target_observation(event.get("clickTargetObservation")),
                "characterOrientationAtAction": _normalize_orientation(event.get("characterOrientationAtAction")),
                "cameraOrientationAtAction": _normalize_orientation(event.get("cameraOrientationAtAction")),
                "cameraCharacterHeadingDeltaDegrees": _numeric(event.get("cameraCharacterHeadingDeltaDegrees")),
            },
            "objectIdentity": {
                "pathIdentity": path_identity if isinstance(path_identity, list) else None,
            },
            "preconditions": preconditions,
            "stateBeforeAfter": relationship_state_changes,
            "guiTransitionsObserved": len(gui_changes),
            "observationWindows": event.get("observationWindows") if isinstance(event.get("observationWindows"), list) else [],
            "possibleDependencies": [feature_candidate] if feature_candidate else [],
            "conflictingActivity": {
                "attribution": attribution,
                "signals": [] if attribution not in {"unattributed", "unattributed-input"} else ["unattributed-activity"],
            },
            "confidence": {
                "level": relationship_confidence,
                "causality": "not-proven-temporal-correlation-only",
                "limitations": [
                    "Client-observed temporal correlation only",
                    "No server authority proof",
                ],
            },
        })

        if path:
            node = workflow_nodes.setdefault(path, {
                "id": "node_" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:12],
                "path": path,
                "controlTypes": set(),
                "featureCandidates": set(),
                "activationCount": 0,
            })
            node["controlTypes"].add(control_type)
            if feature_candidate:
                node["featureCandidates"].add(feature_candidate)
            node["activationCount"] += 1

        if path and (path.lower().startswith("workspace.") or control_type == "ProximityPrompt.Triggered"):
            candidate = world_candidates.setdefault(path, {
                "path": path,
                "controlTypes": set(),
                "observedInteractions": 0,
            })
            candidate["controlTypes"].add(control_type)
            candidate["observedInteractions"] += 1

    for transaction_id, transaction_events in workflow_transactions.items():
        def _event_order_key(item: dict[str, Any]) -> tuple[float, int]:
            elapsed = _numeric(item.get("sessionElapsedSeconds"))
            if elapsed is None:
                elapsed = _numeric(item.get("transactionOrder"))
            if elapsed is None:
                elapsed = _numeric(item.get("sequence"))
            if elapsed is None:
                elapsed = 0.0
            sequence = item.get("sequence") if isinstance(item.get("sequence"), int) else 0
            return (float(elapsed), sequence)

        ordered = sorted(transaction_events, key=_event_order_key)
        for left, right in zip(ordered, ordered[1:]):
            left_path = left.get("path") if isinstance(left.get("path"), str) else None
            right_path = right.get("path") if isinstance(right.get("path"), str) else None
            if not left_path or not right_path:
                continue
            edge_key = (left_path, right_path)
            workflow_edges[edge_key] = workflow_edges.get(edge_key, 0) + 1

    discovered_systems: dict[str, dict[str, Any]] = {}

    for feature_item in features:
        if not isinstance(feature_item, dict):
            continue
        feature_name = feature_item.get("feature") if isinstance(feature_item.get("feature"), str) else None
        if not feature_name:
            continue
        system_id = _infer_system_category(None, feature_name, None)
        bucket = discovered_systems.setdefault(system_id, {
            "id": system_id,
            "title": system_id.replace("-", " ").title(),
            "sourceSignals": set(),
            "observedInteractionEvents": 0,
            "observedStateChanges": 0,
            "observedGuiTransitions": 0,
            "actionableWorkflowDiscovered": False,
            "evidenceSufficientForGeneration": False,
            "additionalObservationNeeded": set(),
        })
        bucket["sourceSignals"].add("feature-summary")
        if isinstance(feature_item.get("interactionEvents"), int):
            bucket["observedInteractionEvents"] += int(feature_item.get("interactionEvents") or 0)
        if isinstance(feature_item.get("temporalTransitionEvents"), int):
            bucket["observedStateChanges"] += int(feature_item.get("temporalTransitionEvents") or 0)
        if not feature_item.get("implementationReady", False):
            bucket["additionalObservationNeeded"].add("actionable-workflow-validation")

    for key, value in readiness.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        system_id = _infer_system_category(None, key, None)
        bucket = discovered_systems.setdefault(system_id, {
            "id": system_id,
            "title": system_id.replace("-", " ").title(),
            "sourceSignals": set(),
            "observedInteractionEvents": 0,
            "observedStateChanges": 0,
            "observedGuiTransitions": 0,
            "actionableWorkflowDiscovered": False,
            "evidenceSufficientForGeneration": False,
            "additionalObservationNeeded": set(),
        })
        bucket["sourceSignals"].add("feature-readiness")
        if not value.get("implemented", False):
            bucket["additionalObservationNeeded"].add("implementation-validation")

    for event in events:
        path = event.get("path") if isinstance(event.get("path"), str) else None
        feature_candidate = event.get("featureCandidate") if isinstance(event.get("featureCandidate"), str) else None
        action_kind = event.get("actionKind") if isinstance(event.get("actionKind"), str) else None
        control_type = event.get("controlType") if isinstance(event.get("controlType"), str) else None
        system_id = _infer_system_category(path, feature_candidate, action_kind)
        bucket = discovered_systems.setdefault(system_id, {
            "id": system_id,
            "title": system_id.replace("-", " ").title(),
            "sourceSignals": set(),
            "observedInteractionEvents": 0,
            "observedStateChanges": 0,
            "observedGuiTransitions": 0,
            "actionableWorkflowDiscovered": False,
            "evidenceSufficientForGeneration": False,
            "additionalObservationNeeded": set(),
        })
        bucket["sourceSignals"].add("interaction-events")
        bucket["observedInteractionEvents"] += 1
        if isinstance(event.get("stateChanges"), list) and len(event.get("stateChanges") or []) > 0:
            bucket["observedStateChanges"] += len(event.get("stateChanges") or [])
        if isinstance(event.get("guiStateChanges"), list) and len(event.get("guiStateChanges") or []) > 0:
            bucket["observedGuiTransitions"] += len(event.get("guiStateChanges") or [])
        if control_type in {"Tool.Activated", "GuiButton.Activated", "ProximityPrompt.Triggered"} and path:
            bucket["actionableWorkflowDiscovered"] = True

    systems_list: list[dict[str, Any]] = []
    for bucket in discovered_systems.values():
        evidence_score = 0.0
        if bucket["observedInteractionEvents"] > 0:
            evidence_score += min(0.4, bucket["observedInteractionEvents"] / 50.0)
        if bucket["observedStateChanges"] > 0:
            evidence_score += min(0.4, bucket["observedStateChanges"] / 80.0)
        if bucket["actionableWorkflowDiscovered"]:
            evidence_score += 0.2
        bucket["evidenceSufficientForGeneration"] = bool(
            bucket["actionableWorkflowDiscovered"] and bucket["observedStateChanges"] > 0
        )
        if not bucket["actionableWorkflowDiscovered"]:
            bucket["additionalObservationNeeded"].add("actionable-control-paths")
        if bucket["observedStateChanges"] == 0:
            bucket["additionalObservationNeeded"].add("outcome-state-deltas")
        systems_list.append({
            "id": bucket["id"],
            "title": bucket["title"],
            "sourceSignals": sorted(bucket["sourceSignals"]),
            "observedInteractionEvents": bucket["observedInteractionEvents"],
            "observedStateChanges": bucket["observedStateChanges"],
            "observedGuiTransitions": bucket["observedGuiTransitions"],
            "actionableWorkflowDiscovered": bucket["actionableWorkflowDiscovered"],
            "evidenceSufficientForGeneration": bucket["evidenceSufficientForGeneration"],
            "confidence": {
                "score": round(min(1.0, evidence_score), 3),
                "level": _confidence_level(min(1.0, evidence_score)),
            },
            "additionalObservationNeeded": sorted(bucket["additionalObservationNeeded"]),
        })

    interaction_diagnostics = payload.get("interactionDiagnostics") if isinstance(payload.get("interactionDiagnostics"), dict) else {}
    input_observation_stats = interaction_diagnostics.get("inputObservationStats") if isinstance(interaction_diagnostics.get("inputObservationStats"), dict) else {}
    raw_position_history = interaction_diagnostics.get("playerPositionHistory")
    raw_cursor_history = interaction_diagnostics.get("cursorObservationHistory")
    if not isinstance(raw_cursor_history, list):
        raw_cursor_history = payload.get("cursorObservationHistory") if isinstance(payload.get("cursorObservationHistory"), list) else []

    raw_click_targets = interaction_diagnostics.get("clickTargetObservations")
    if not isinstance(raw_click_targets, list):
        raw_click_targets = payload.get("clickTargetObservations") if isinstance(payload.get("clickTargetObservations"), list) else []

    raw_click_outcomes = interaction_diagnostics.get("clickOutcomeRelationships")
    if not isinstance(raw_click_outcomes, list):
        raw_click_outcomes = payload.get("clickOutcomeRelationships") if isinstance(payload.get("clickOutcomeRelationships"), list) else []

    raw_input_gestures = interaction_diagnostics.get("inputGestureObservations")
    if not isinstance(raw_input_gestures, list):
        raw_input_gestures = payload.get("inputGestureObservations") if isinstance(payload.get("inputGestureObservations"), list) else []

    raw_character_orientations = interaction_diagnostics.get("characterOrientationSamples")
    if not isinstance(raw_character_orientations, list):
        raw_character_orientations = payload.get("characterOrientationSamples") if isinstance(payload.get("characterOrientationSamples"), list) else []

    raw_camera_orientations = interaction_diagnostics.get("cameraOrientationSamples")
    if not isinstance(raw_camera_orientations, list):
        raw_camera_orientations = payload.get("cameraOrientationSamples") if isinstance(payload.get("cameraOrientationSamples"), list) else []

    def _append_unique_by_id(collection: list[dict[str, Any]], seen: set[str], item: Optional[dict[str, Any]], *, fallback_prefix: str, fallback_index: int) -> None:
        if not isinstance(item, dict):
            return
        raw_id = item.get("id")
        item_id = raw_id if isinstance(raw_id, str) and raw_id else f"{fallback_prefix}-{fallback_index}"
        if item_id in seen:
            return
        normalized = dict(item)
        normalized["id"] = item_id
        seen.add(item_id)
        collection.append(normalized)

    cursor_observation_history: list[dict[str, Any]] = []
    cursor_seen: set[str] = set()
    for idx, sample in enumerate(raw_cursor_history[:1800]):
        _append_unique_by_id(
            cursor_observation_history,
            cursor_seen,
            _normalize_cursor_observation(sample),
            fallback_prefix="cursor-observation",
            fallback_index=idx + 1,
        )

    click_target_observations: list[dict[str, Any]] = []
    click_target_seen: set[str] = set()
    for idx, sample in enumerate(raw_click_targets[:1200]):
        _append_unique_by_id(
            click_target_observations,
            click_target_seen,
            _normalize_click_target_observation(sample),
            fallback_prefix="click-target",
            fallback_index=idx + 1,
        )

    click_outcome_relationships: list[dict[str, Any]] = []
    click_outcome_seen: set[str] = set()
    for idx, sample in enumerate(raw_click_outcomes[:1200]):
        _append_unique_by_id(
            click_outcome_relationships,
            click_outcome_seen,
            _normalize_click_outcome_relationship(sample),
            fallback_prefix="click-outcome",
            fallback_index=idx + 1,
        )

    input_gesture_observations: list[dict[str, Any]] = []
    input_gesture_seen: set[str] = set()
    for idx, sample in enumerate(raw_input_gestures[:1400]):
        _append_unique_by_id(
            input_gesture_observations,
            input_gesture_seen,
            _normalize_input_gesture_observation(sample),
            fallback_prefix="input-gesture",
            fallback_index=idx + 1,
        )

    character_orientation_samples: list[dict[str, Any]] = []
    character_orientation_seen: set[str] = set()
    for idx, sample in enumerate(raw_character_orientations[:2200]):
        _append_unique_by_id(
            character_orientation_samples,
            character_orientation_seen,
            _normalize_orientation(sample),
            fallback_prefix="character-orientation",
            fallback_index=idx + 1,
        )

    camera_orientation_samples: list[dict[str, Any]] = []
    camera_orientation_seen: set[str] = set()
    for idx, sample in enumerate(raw_camera_orientations[:2200]):
        _append_unique_by_id(
            camera_orientation_samples,
            camera_orientation_seen,
            _normalize_orientation(sample),
            fallback_prefix="camera-orientation",
            fallback_index=idx + 1,
        )

    if not isinstance(raw_position_history, list):
        raw_position_history = payload.get("playerPositionHistory") if isinstance(payload.get("playerPositionHistory"), list) else []

    position_history: list[dict[str, Any]] = []
    for idx, sample in enumerate(raw_position_history[:1200]):
        if not isinstance(sample, dict):
            continue
        position_history.append({
            "snapshotSequence": sample.get("snapshotSequence") if isinstance(sample.get("snapshotSequence"), int) else idx + 1,
            "sampledAt": sample.get("sampledAt") if isinstance(sample.get("sampledAt"), str) else None,
            "sessionElapsedSeconds": _numeric(sample.get("sessionElapsedSeconds")),
            "reason": sample.get("reason") if isinstance(sample.get("reason"), str) else None,
            "characterGeneration": sample.get("characterGeneration") if isinstance(sample.get("characterGeneration"), int) else None,
            "characterId": sample.get("characterId") if isinstance(sample.get("characterId"), str) else None,
            "positionValid": bool(sample.get("positionValid", _position_from_value(sample.get("position")) is not None)),
            "position": _position_from_value(sample.get("position")),
            "speedStudsPerSecond": _numeric(sample.get("speedStudsPerSecond")),
            "directionUnit": sample.get("directionUnit") if isinstance(sample.get("directionUnit"), dict) else None,
            "characterState": sample.get("characterState") if isinstance(sample.get("characterState"), str) else None,
            "worldContext": sample.get("worldContext") if isinstance(sample.get("worldContext"), dict) else None,
            "characterOrientation": _normalize_orientation(sample.get("characterOrientation")),
            "cameraOrientation": _normalize_orientation(sample.get("cameraOrientation")),
            "cameraCharacterHeadingDeltaDegrees": _numeric(sample.get("cameraCharacterHeadingDeltaDegrees")),
            "interpolated": bool(sample.get("interpolated") is True),
            "sampleKind": sample.get("sampleKind") if isinstance(sample.get("sampleKind"), str) else None,
            "discontinuity": sample.get("discontinuity") if isinstance(sample.get("discontinuity"), dict) else None,
            "invalidReason": sample.get("invalidReason") if isinstance(sample.get("invalidReason"), str) else None,
        })

    event_snapshots: list[dict[str, Any]] = []
    event_snapshot_seen: set[tuple[Any, ...]] = set()

    def _push_snapshot(raw_sample: dict[str, Any], *, fallback_phase: str, sequence: Optional[int], tx_id: Optional[str]) -> None:
        normalized = _normalize_snapshot(raw_sample, fallback_phase=fallback_phase)
        if not normalized:
            return
        if normalized.get("interactionSequence") is None and sequence is not None:
            normalized["interactionSequence"] = sequence
        if not normalized.get("transactionId") and tx_id:
            normalized["transactionId"] = tx_id
        position = normalized.get("position")
        pos_key = None if not isinstance(position, dict) else (
            round(position.get("x", 0.0), 4),
            round(position.get("y", 0.0), 4),
            round(position.get("z", 0.0), 4),
        )
        dedupe_key = (
            normalized.get("interactionSequence"),
            normalized.get("transactionId"),
            normalized.get("phase"),
            normalized.get("sessionElapsedSeconds"),
            pos_key,
            normalized.get("source"),
        )
        if dedupe_key in event_snapshot_seen:
            return
        event_snapshot_seen.add(dedupe_key)
        event_snapshots.append(normalized)

    raw_event_snapshot_list = interaction_diagnostics.get("eventPositionSnapshots")
    if not isinstance(raw_event_snapshot_list, list):
        raw_event_snapshot_list = payload.get("eventPositionSnapshots") if isinstance(payload.get("eventPositionSnapshots"), list) else []
    for sample in raw_event_snapshot_list[:2200]:
        if isinstance(sample, dict):
            _push_snapshot(sample, fallback_phase="event-snapshot", sequence=None, tx_id=None)

    for event in events:
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        tx_id = event.get("transactionId") if isinstance(event.get("transactionId"), str) else None
        for field_name, fallback_phase in (
            ("beforePositionSample", "before-action"),
            ("actionPositionSample", "at-action"),
        ):
            sample = event.get(field_name)
            if isinstance(sample, dict):
                _push_snapshot(sample, fallback_phase=fallback_phase, sequence=sequence, tx_id=tx_id)
        nested = event.get("eventPositionSnapshots")
        if isinstance(nested, list):
            for sample in nested[:16]:
                if isinstance(sample, dict):
                    _push_snapshot(sample, fallback_phase="event-linked", sequence=sequence, tx_id=tx_id)
        windows = event.get("observationWindows") if isinstance(event.get("observationWindows"), list) else []
        for window in windows[:8]:
            if not isinstance(window, dict):
                continue
            sample = window.get("positionSample")
            if isinstance(sample, dict):
                seconds = _numeric(window.get("seconds"))
                fallback_phase = f"observation-window-{seconds}" if seconds is not None else "observation-window"
                _push_snapshot(sample, fallback_phase=fallback_phase, sequence=sequence, tx_id=tx_id)


    transient_outcome_tokens = (
        "humanoid.activeanimation",
        "humanoid.activeanimations",
        "humanoid.movedirection",
        "humanoid.floormaterial",
        "humanoid.walkspeed",
        "humanoid.jumppower",
        "velocitymagnitude",
        "rootpart.velocity",
        ".position",
        ".cframe",
    )

    def _is_gameplay_outcome_key(key: str) -> bool:
        lower = key.lower()
        if any(token in lower for token in transient_outcome_tokens):
            return False
        if lower.startswith("camera."):
            return False
        return True


    click_target_by_id = {item.get("id"): item for item in click_target_observations if isinstance(item.get("id"), str)}
    click_outcome_by_click_id = {
        item.get("clickObservationId"): item
        for item in click_outcome_relationships
        if isinstance(item.get("clickObservationId"), str)
    }

    for idx, event in enumerate(events[:1600]):
        click_ref = event.get("clickObservationId") if isinstance(event.get("clickObservationId"), str) else None
        click_payload = _normalize_click_target_observation(event.get("clickTargetObservation"))
        if click_payload is not None:
            if click_ref and not click_payload.get("id"):
                click_payload["id"] = click_ref
            _append_unique_by_id(
                click_target_observations,
                click_target_seen,
                click_payload,
                fallback_prefix="event-click-target",
                fallback_index=idx + 1,
            )
            if isinstance(click_payload.get("id"), str):
                click_target_by_id[click_payload["id"]] = click_payload
        if click_ref and click_ref not in click_target_by_id:
            fallback_click = {
                "id": click_ref,
                "observedAt": event.get("observedAt") if isinstance(event.get("observedAt"), str) else None,
                "sessionElapsedSeconds": _numeric(event.get("sessionElapsedSeconds")),
                "mouseButton": "MouseButton1",
                "inputType": "InputBegan.MouseButton1",
                "guiCandidates": [],
                "topmostGuiTarget": {"path": event.get("path"), "class": None} if isinstance(event.get("path"), str) else None,
                "raycastTarget": None,
                "targetIdentificationConfidence": {
                    "level": "low",
                    "score": 0.35,
                    "overlapDetected": False,
                    "cursorAvailable": False,
                },
                "missingEvidence": ["Derived from interaction event; no direct click-target payload available"],
            }
            _append_unique_by_id(
                click_target_observations,
                click_target_seen,
                fallback_click,
                fallback_prefix="event-click-target",
                fallback_index=idx + 1,
            )
            click_target_by_id[click_ref] = fallback_click
        if click_ref and click_ref not in click_outcome_by_click_id:
            state_changes = event.get("stateChanges") if isinstance(event.get("stateChanges"), list) else []
            meaningful_count = sum(
                1
                for item in state_changes
                if isinstance(item, dict)
                and isinstance(item.get("key"), str)
                and _is_gameplay_outcome_key(item.get("key"))
            )
            derived_outcome = {
                "id": f"derived-click-outcome-{idx + 1}",
                "clickObservationId": click_ref,
                "clickObserved": True,
                "targetIdentified": click_ref in click_target_by_id,
                "interactionCallbackObserved": True,
                "stateChangeTemporallyAssociated": len(state_changes) > 0,
                "meaningfulGameplayOutcomeObserved": meaningful_count > 0,
                "outcomeCorroborated": meaningful_count >= 2 or bool(event.get("clientStateCorroborated") is True),
                "reproduciblyLiveValidated": False,
                "stage": "state-change-temporally-associated" if len(state_changes) > 0 else "interaction-callback-observed",
                "status": "observational-only",
                "linkedInteractionSequences": [event.get("sequence")] if isinstance(event.get("sequence"), int) else [],
                "linkedTransactionIds": [event.get("transactionId")] if isinstance(event.get("transactionId"), str) else [],
                "missingEvidence": [
                    "No controlled live validation proving reproducible outcome",
                ],
            }
            _append_unique_by_id(
                click_outcome_relationships,
                click_outcome_seen,
                derived_outcome,
                fallback_prefix="event-click-outcome",
                fallback_index=idx + 1,
            )
            click_outcome_by_click_id[click_ref] = derived_outcome

        _append_unique_by_id(
            character_orientation_samples,
            character_orientation_seen,
            _normalize_orientation(event.get("characterOrientationAtAction")),
            fallback_prefix="event-character-orientation",
            fallback_index=idx + 1,
        )
        _append_unique_by_id(
            camera_orientation_samples,
            camera_orientation_seen,
            _normalize_orientation(event.get("cameraOrientationAtAction")),
            fallback_prefix="event-camera-orientation",
            fallback_index=idx + 1,
        )

    for idx, sample in enumerate(position_history[:1800]):
        _append_unique_by_id(
            character_orientation_samples,
            character_orientation_seen,
            sample.get("characterOrientation") if isinstance(sample.get("characterOrientation"), dict) else None,
            fallback_prefix="position-character-orientation",
            fallback_index=idx + 1,
        )
        _append_unique_by_id(
            camera_orientation_samples,
            camera_orientation_seen,
            sample.get("cameraOrientation") if isinstance(sample.get("cameraOrientation"), dict) else None,
            fallback_prefix="position-camera-orientation",
            fallback_index=idx + 1,
        )

    for idx, sample in enumerate(event_snapshots[:2200]):
        _append_unique_by_id(
            character_orientation_samples,
            character_orientation_seen,
            sample.get("characterOrientation") if isinstance(sample.get("characterOrientation"), dict) else None,
            fallback_prefix="snapshot-character-orientation",
            fallback_index=idx + 1,
        )
        _append_unique_by_id(
            camera_orientation_samples,
            camera_orientation_seen,
            sample.get("cameraOrientation") if isinstance(sample.get("cameraOrientation"), dict) else None,
            fallback_prefix="snapshot-camera-orientation",
            fallback_index=idx + 1,
        )

    snapshots_by_sequence: dict[int, list[dict[str, Any]]] = {}
    snapshots_by_transaction: dict[str, list[dict[str, Any]]] = {}
    for sample in event_snapshots:
        sequence = sample.get("interactionSequence")
        tx_id = sample.get("transactionId")
        if isinstance(sequence, int):
            snapshots_by_sequence.setdefault(sequence, []).append(sample)
        if isinstance(tx_id, str) and tx_id:
            snapshots_by_transaction.setdefault(tx_id, []).append(sample)

    def _choose_snapshot_for_event(event: dict[str, Any], *, phase_hint: str) -> Optional[dict[str, Any]]:
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        tx_id = event.get("transactionId") if isinstance(event.get("transactionId"), str) else None
        pool: list[dict[str, Any]] = []
        if sequence is not None:
            pool.extend(snapshots_by_sequence.get(sequence, []))
        if tx_id:
            pool.extend(snapshots_by_transaction.get(tx_id, []))
        if not pool:
            return None
        best: Optional[dict[str, Any]] = None
        best_score = -1
        for sample in pool:
            position = sample.get("position")
            if not isinstance(position, dict):
                continue
            phase = (sample.get("phase") or "").lower()
            score = 1
            if phase_hint in phase:
                score += 4
            if phase_hint == "at-action" and "action" in phase:
                score += 2
            if phase_hint == "before-action" and "before" in phase:
                score += 2
            if sample.get("sampled") is True:
                score += 1
            if score > best_score:
                best_score = score
                best = sample
        return best


    baseline_actionable_descendant_index: dict[str, dict[str, Any]] = {}
    for actionable_path, entry in baseline_actionable_index.items():
        if not isinstance(actionable_path, str):
            continue
        segments = [segment for segment in actionable_path.split(".") if segment]
        if len(segments) < 2:
            continue
        mechanisms = entry.get("mechanisms") if isinstance(entry, dict) and isinstance(entry.get("mechanisms"), dict) else {}
        interaction_score = float(_numeric(entry.get("interactionScore")) or 0.0) if isinstance(entry, dict) else 0.0
        for idx in range(1, len(segments)):
            ancestor_path = ".".join(segments[:idx])
            if not ancestor_path.lower().startswith("workspace."):
                continue
            bucket = baseline_actionable_descendant_index.setdefault(ancestor_path, {
                "descendantCount": 0,
                "interactionScore": 0.0,
                "mechanisms": {},
            })
            bucket["descendantCount"] += 1
            bucket["interactionScore"] += interaction_score
            for mechanism, count in mechanisms.items():
                if isinstance(mechanism, str) and type(count) is int and count > 0:
                    bucket["mechanisms"][mechanism] = bucket["mechanisms"].get(mechanism, 0) + count

    def _derived_mechanisms(control_types: Sequence[str], likely_paths: Sequence[str], nearby_mechanisms: Sequence[str]) -> list[str]:
        out: set[str] = {item for item in nearby_mechanisms if isinstance(item, str)}
        for control_type in control_types:
            if not isinstance(control_type, str):
                continue
            if control_type.startswith("GuiButton."):
                out.add("gui-button")
            elif control_type.startswith("InputBegan.Keyboard"):
                out.add("keybind")
            elif control_type.startswith("InputBegan.MouseButton"):
                out.add("pointer-input")
            elif control_type.startswith("ProximityPrompt."):
                out.add("prompt")
            elif control_type.startswith("Tool."):
                out.add("tool")
        for path in likely_paths:
            if isinstance(path, str) and path.lower().startswith("localplayer.playergui."):
                out.add("gui-button")
        return sorted(out)

    def _infer_location_purpose_from_context(
        *,
        existing_purpose: Optional[str],
        feature_candidates: Sequence[str],
        likely_paths: Sequence[str],
        workspace_paths: Sequence[str],
        gui_controls: Sequence[str],
        outcome_keys: Sequence[str],
    ) -> str:
        if isinstance(existing_purpose, str) and existing_purpose and existing_purpose != "uncategorized":
            return existing_purpose

        scores: dict[str, float] = {
            "shops-or-upgrades": 0.0,
            "eggs-or-hatching": 0.0,
            "travel-or-teleport": 0.0,
            "rewards-or-claims": 0.0,
            "quests-and-objectives": 0.0,
            "progression-or-training": 0.0,
        }

        for candidate in feature_candidates:
            low = candidate.lower()
            if "shop" in low or "upgrade" in low or "purchase" in low:
                scores["shops-or-upgrades"] += 2.0
            if "egg" in low or "hatch" in low or "pet" in low:
                scores["eggs-or-hatching"] += 2.0
            if "reward" in low or "claim" in low:
                scores["rewards-or-claims"] += 2.0
            if "quest" in low:
                scores["quests-and-objectives"] += 2.0
            if "travel" in low or "portal" in low:
                scores["travel-or-teleport"] += 2.0

        context_paths = [
            item.lower()
            for item in list(likely_paths) + list(workspace_paths) + list(gui_controls)
            if isinstance(item, str)
        ]
        for low in context_paths:
            if any(token in low for token in ("shop", "vendor", "merchant", "upgrade", "buy", "purchase")):
                scores["shops-or-upgrades"] += 1.0
            if any(token in low for token in ("egg", "hatch", "pet", "incubator")):
                scores["eggs-or-hatching"] += 1.0
            if any(token in low for token in ("reward", "claim", "chest", "prize", "gift")):
                scores["rewards-or-claims"] += 1.0
            if any(token in low for token in ("quest", "mission", "objective")):
                scores["quests-and-objectives"] += 1.0
            if any(token in low for token in ("travel", "portal", "spawn", "teleport", "gate", "island")):
                scores["travel-or-teleport"] += 1.0

        for key in outcome_keys:
            low = key.lower()
            if any(token in low for token in ("coin", "gem", "currency", "leaderstats")):
                scores["progression-or-training"] += 0.8
            if any(token in low for token in ("bubble", "strength", "hatch", "xp", "level")):
                scores["progression-or-training"] += 1.0

        best = max(scores.items(), key=lambda item: item[1])
        return best[0] if best[1] >= 1.5 else "uncategorized"


    def _path_identity_key(path: Optional[str]) -> Optional[str]:
        if not isinstance(path, str) or not path:
            return None
        normalized = _canonical_object_path(path)
        if not normalized:
            return None
        parts = [part for part in normalized.split(".") if part]
        if len(parts) < 2:
            return normalized.lower()
        lower_head = ".".join(parts[:3]).lower()
        if lower_head.startswith("localplayer.playergui"):
            return ".".join(parts[:5]).lower()
        if lower_head.startswith("workspace.worlds"):
            return ".".join(parts[:5]).lower()
        if parts[0].lower() == "workspace":
            return ".".join(parts[:4]).lower()
        return ".".join(parts[:4]).lower()

    def _position_distance(a: Optional[dict[str, Any]], b: Optional[dict[str, Any]]) -> Optional[float]:
        if not isinstance(a, dict) or not isinstance(b, dict):
            return None
        ax, ay, az = _numeric(a.get("x")), _numeric(a.get("y")), _numeric(a.get("z"))
        bx, by, bz = _numeric(b.get("x")), _numeric(b.get("y")), _numeric(b.get("z"))
        if None in (ax, ay, az, bx, by, bz):
            return None
        return math.dist((ax, ay, az), (bx, by, bz))

    def _same_world_identity(a: dict[str, Any], b: dict[str, Any]) -> bool:
        worlds_a = [item for item in (a.get("worldContexts") or []) if isinstance(item, str)]
        worlds_b = [item for item in (b.get("worldContexts") or []) if isinstance(item, str)]
        if worlds_a and worlds_b:
            return worlds_a[0] == worlds_b[0]
        return True

    clusters: dict[tuple[Any, ...], dict[str, Any]] = {}
    sequence_to_location: dict[int, str] = {}
    transaction_to_location: dict[str, str] = {}
    row_by_sequence: dict[int, dict[str, Any]] = {}
    actionable_nearby_candidates = 0
    uncertain_nearby_candidates = 0
    rejected_nearby_candidates = 0

    for event in events:
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        tx_id = event.get("transactionId") if isinstance(event.get("transactionId"), str) else None
        action_snapshot = _choose_snapshot_for_event(event, phase_hint="at-action")
        if not action_snapshot:
            direct_sample = event.get("actionPositionSample")
            if isinstance(direct_sample, dict):
                action_snapshot = _normalize_snapshot(direct_sample, fallback_phase="at-action")
                if isinstance(action_snapshot, dict):
                    if action_snapshot.get("interactionSequence") is None and sequence is not None:
                        action_snapshot["interactionSequence"] = sequence
                    if not action_snapshot.get("transactionId") and tx_id:
                        action_snapshot["transactionId"] = tx_id
        if not action_snapshot:
            continue
        position = action_snapshot.get("position")
        if not isinstance(position, dict):
            continue

        world_context = action_snapshot.get("worldContext") if isinstance(action_snapshot.get("worldContext"), dict) else {}
        world_context_key = world_context.get("path") if isinstance(world_context.get("path"), str) else world_context.get("name")

        nearby = event.get("nearbyWorldObjects") if isinstance(event.get("nearbyWorldObjects"), list) else []
        filtered_nearby: list[dict[str, Any]] = []
        for obj in nearby[:24]:
            if not isinstance(obj, dict):
                continue
            normalized_path = _canonical_object_path(obj.get("path"))
            if not normalized_path:
                continue
            low_path = normalized_path.lower()
            if _workspace_root_like_path(normalized_path):
                rejected_nearby_candidates += 1
                continue
            if low_path.startswith("replicatedstorage."):
                rejected_nearby_candidates += 1
                continue
            mechanisms = [item for item in (obj.get("interactionMechanisms") if isinstance(obj.get("interactionMechanisms"), list) else []) if isinstance(item, str)]
            baseline_entry = baseline_actionable_index.get(normalized_path)
            baseline_descendant_entry = baseline_actionable_descendant_index.get(normalized_path)
            if isinstance(baseline_entry, dict):
                for mechanism, count in (baseline_entry.get("mechanisms") if isinstance(baseline_entry.get("mechanisms"), dict) else {}).items():
                    if isinstance(mechanism, str) and type(count) is int and count > 0 and mechanism not in mechanisms:
                        mechanisms.append(mechanism)
            if isinstance(baseline_descendant_entry, dict):
                for mechanism, count in (baseline_descendant_entry.get("mechanisms") if isinstance(baseline_descendant_entry.get("mechanisms"), dict) else {}).items():
                    if isinstance(mechanism, str) and type(count) is int and count > 0 and mechanism not in mechanisms:
                        mechanisms.append(mechanism)

            score = float(_numeric(obj.get("actionableScore")) or 0.0)
            if isinstance(baseline_entry, dict):
                score += float(_numeric(baseline_entry.get("interactionScore")) or 0.0)
            if isinstance(baseline_descendant_entry, dict):
                score += min(
                    4.0,
                    float(_numeric(baseline_descendant_entry.get("interactionScore")) or 0.0) * 0.15
                    + float(baseline_descendant_entry.get("descendantCount") or 0) * 0.4,
                )

            decorative = any(token in low_path for token in ("decoration", "foliage", "mountain", "tree", "rock", "mesh", "terrain", "barrier"))
            if mechanisms:
                tier = "actionable"
                actionable_nearby_candidates += 1
            elif decorative and score < 6.0:
                rejected_nearby_candidates += 1
                continue
            elif score >= 6.0:
                tier = "actionable"
                actionable_nearby_candidates += 1
            else:
                tier = "uncertain"
                uncertain_nearby_candidates += 1

            filtered_nearby.append({
                "path": normalized_path,
                "tier": tier,
                "mechanisms": mechanisms,
                "distanceStuds": _numeric(obj.get("distanceStuds")),
                "derivedFromBaseline": isinstance(baseline_entry, dict) or isinstance(baseline_descendant_entry, dict),
            })

        object_anchor = None
        if filtered_nearby:
            ranked = sorted(
                filtered_nearby,
                key=lambda item: (
                    0 if item["tier"] == "actionable" else 1,
                    item["distanceStuds"] if isinstance(item.get("distanceStuds"), (int, float)) else 1e9,
                    item["path"],
                ),
            )
            object_anchor = ranked[0]["path"]

        key = _cluster_key(
            position,
            character_generation=action_snapshot.get("characterGeneration") if isinstance(action_snapshot.get("characterGeneration"), int) else None,
            world_context_key=world_context_key if isinstance(world_context_key, str) and world_context_key else None,
            object_anchor=object_anchor,
        )
        cluster = clusters.get(key)
        if cluster is None:
            cluster = {
                "id": "loc_" + hashlib.sha256("|".join(str(item) for item in key).encode("utf-8")).hexdigest()[:14],
                "count": 0,
                "sumX": 0.0,
                "sumY": 0.0,
                "sumZ": 0.0,
                "minX": position["x"],
                "maxX": position["x"],
                "minY": position["y"],
                "maxY": position["y"],
                "minZ": position["z"],
                "maxZ": position["z"],
                "paths": {},
                "controlTypes": {},
                "actionKinds": {},
                "featureCandidates": {},
                "purposes": {},
                "transactions": set(),
                "sequences": set(),
                "nearby": {},
                "nearbyTier": {},
                "nearbyMechanisms": {},
                "worldContexts": {},
                "beforePositions": [],
                "postPositions": [],
                "requiredConditions": {},
                "outcomeStateKeys": {},
                "guiControls": {},
                "characterGenerations": set(),
            }
            clusters[key] = cluster

        cluster["count"] += 1
        cluster["sumX"] += position["x"]
        cluster["sumY"] += position["y"]
        cluster["sumZ"] += position["z"]
        cluster["minX"] = min(cluster["minX"], position["x"])
        cluster["maxX"] = max(cluster["maxX"], position["x"])
        cluster["minY"] = min(cluster["minY"], position["y"])
        cluster["maxY"] = max(cluster["maxY"], position["y"])
        cluster["minZ"] = min(cluster["minZ"], position["z"])
        cluster["maxZ"] = max(cluster["maxZ"], position["z"])

        path = event.get("path") if isinstance(event.get("path"), str) else None
        control_type = event.get("controlType") if isinstance(event.get("controlType"), str) else "unknown"
        action_kind = event.get("actionKind") if isinstance(event.get("actionKind"), str) else "unknown"
        feature_candidate = event.get("featureCandidate") if isinstance(event.get("featureCandidate"), str) else None
        purpose = event.get("inferredLocationPurpose") if isinstance(event.get("inferredLocationPurpose"), str) else _infer_system_category(path, feature_candidate, action_kind)

        if path:
            cluster["paths"][path] = cluster["paths"].get(path, 0) + 1
        cluster["controlTypes"][control_type] = cluster["controlTypes"].get(control_type, 0) + 1
        cluster["actionKinds"][action_kind] = cluster["actionKinds"].get(action_kind, 0) + 1
        if feature_candidate:
            cluster["featureCandidates"][feature_candidate] = cluster["featureCandidates"].get(feature_candidate, 0) + 1
        if purpose:
            cluster["purposes"][purpose] = cluster["purposes"].get(purpose, 0) + 1

        if isinstance(sequence, int):
            cluster["sequences"].add(sequence)
            sequence_to_location.setdefault(sequence, cluster["id"])
        if tx_id:
            cluster["transactions"].add(tx_id)
            transaction_to_location.setdefault(tx_id, cluster["id"])

        if isinstance(world_context_key, str) and world_context_key:
            cluster["worldContexts"][world_context_key] = cluster["worldContexts"].get(world_context_key, 0) + 1

        before_snapshot = _choose_snapshot_for_event(event, phase_hint="before-action")
        if before_snapshot and isinstance(before_snapshot.get("position"), dict):
            cluster["beforePositions"].append(before_snapshot.get("position"))

        post_snapshot = None
        sequence_snapshots = snapshots_by_sequence.get(sequence, []) if isinstance(sequence, int) else []
        tx_snapshots = snapshots_by_transaction.get(tx_id, []) if tx_id else []
        for sample in sequence_snapshots + tx_snapshots:
            if not isinstance(sample, dict) or not isinstance(sample.get("position"), dict):
                continue
            phase = (sample.get("phase") or "").lower()
            if "observation-window" in phase or "after" in phase:
                post_snapshot = sample
                break
        if post_snapshot and isinstance(post_snapshot.get("position"), dict):
            cluster["postPositions"].append(post_snapshot.get("position"))

        for item in filtered_nearby:
            nearby_path = item["path"]
            cluster["nearby"][nearby_path] = cluster["nearby"].get(nearby_path, 0) + 1
            cluster["nearbyTier"][nearby_path] = item["tier"]
            for mechanism in item["mechanisms"]:
                cluster["nearbyMechanisms"][mechanism] = cluster["nearbyMechanisms"].get(mechanism, 0) + 1

        metadata = event.get("controlMetadata") if isinstance(event.get("controlMetadata"), dict) else {}
        for key_name in ("enabled", "active", "visible", "effectiveVisible", "interactable", "ancestorVisible", "screenEnabled", "requiresHandle"):
            if key_name in metadata:
                marker = f"{key_name}={metadata.get(key_name)}"
                cluster["requiredConditions"][marker] = cluster["requiredConditions"].get(marker, 0) + 1

        for change in event.get("stateChanges") if isinstance(event.get("stateChanges"), list) else []:
            if isinstance(change, dict) and isinstance(change.get("key"), str):
                change_key = change["key"]
                cluster["outcomeStateKeys"][change_key] = cluster["outcomeStateKeys"].get(change_key, 0) + 1

        generation = action_snapshot.get("characterGeneration")
        if isinstance(generation, int):
            cluster["characterGenerations"].add(generation)

        if path and path.lower().startswith("localplayer.playergui."):
            cluster["guiControls"][path] = cluster["guiControls"].get(path, 0) + 1

        if isinstance(sequence, int) and sequence not in row_by_sequence:
            row_by_sequence[sequence] = {
                "before": before_snapshot.get("position") if isinstance(before_snapshot, dict) else None,
                "action": position,
                "post": post_snapshot.get("position") if isinstance(post_snapshot, dict) else None,
                "observationWindows": event.get("observationWindows") if isinstance(event.get("observationWindows"), list) else [],
                "attribution": event.get("attribution") if isinstance(event.get("attribution"), str) else "unknown",
                "clickObservationId": event.get("clickObservationId") if isinstance(event.get("clickObservationId"), str) else None,
                "characterOrientation": _normalize_orientation(event.get("characterOrientationAtAction"))
                    or (action_snapshot.get("characterOrientation") if isinstance(action_snapshot, dict) else None),
                "cameraOrientation": _normalize_orientation(event.get("cameraOrientationAtAction"))
                    or (action_snapshot.get("cameraOrientation") if isinstance(action_snapshot, dict) else None),
                "cameraCharacterHeadingDeltaDegrees": _numeric(event.get("cameraCharacterHeadingDeltaDegrees"))
                    or (action_snapshot.get("cameraCharacterHeadingDeltaDegrees") if isinstance(action_snapshot, dict) else None),
            }

    location_registry: list[dict[str, Any]] = []
    for cluster in sorted(clusters.values(), key=lambda value: (-value["count"], value["id"]))[:140]:
        control_types = [item[0] for item in sorted(cluster["controlTypes"].items(), key=lambda item: (-item[1], item[0]))]
        action_kinds = [item[0] for item in sorted(cluster["actionKinds"].items(), key=lambda item: (-item[1], item[0]))]
        feature_candidates = [item[0] for item in sorted(cluster["featureCandidates"].items(), key=lambda item: (-item[1], item[0]))]
        likely_target_paths = [item[0] for item in sorted(cluster["paths"].items(), key=lambda item: (-item[1], item[0]))[:12]]
        actionable_world_paths = [
            item[0]
            for item in sorted(cluster["nearby"].items(), key=lambda item: (-item[1], item[0]))
            if cluster["nearbyTier"].get(item[0]) == "actionable"
        ]
        uncertain_world_paths = [
            item[0]
            for item in sorted(cluster["nearby"].items(), key=lambda item: (-item[1], item[0]))
            if cluster["nearbyTier"].get(item[0]) != "actionable"
        ]
        associated_gui_controls = [item[0] for item in sorted(cluster["guiControls"].items(), key=lambda item: (-item[1], item[0]))[:14]]
        nearby_mechanisms = [item[0] for item in sorted(cluster["nearbyMechanisms"].items(), key=lambda item: (-item[1], item[0]))]
        derived_mechanisms = _derived_mechanisms(control_types, likely_target_paths, nearby_mechanisms)

        observed_outcomes = [
            {"key": item[0], "occurrences": item[1], "gameplayRelevant": _is_gameplay_outcome_key(item[0])}
            for item in sorted(cluster["outcomeStateKeys"].items(), key=lambda item: (-item[1], item[0]))[:20]
        ]
        meaningful_outcome_keys = [item["key"] for item in observed_outcomes if item["gameplayRelevant"]]

        representative = {
            "x": round(cluster["sumX"] / cluster["count"], 4),
            "y": round(cluster["sumY"] / cluster["count"], 4),
            "z": round(cluster["sumZ"] / cluster["count"], 4),
        }
        range_box = {
            "min": {"x": round(cluster["minX"], 4), "y": round(cluster["minY"], 4), "z": round(cluster["minZ"], 4)},
            "max": {"x": round(cluster["maxX"], 4), "y": round(cluster["maxY"], 4), "z": round(cluster["maxZ"], 4)},
        }

        confidence_score = min(1.0, 0.2 + (cluster["count"] / 10.0) + (len(cluster["transactions"]) / 10.0))
        if meaningful_outcome_keys:
            confidence_score = min(1.0, confidence_score + 0.12)
        elif len(associated_gui_controls) >= 2 and any(item.startswith("GuiButton.") for item in control_types):
            confidence_score = min(1.0, confidence_score + 0.06)
        if len(actionable_world_paths) == 0 and len(associated_gui_controls) == 0 and len(uncertain_world_paths) > 0:
            confidence_score = max(0.0, confidence_score - 0.08)

        raw_purpose = sorted(cluster["purposes"].items(), key=lambda item: (-item[1], item[0]))[0][0] if cluster["purposes"] else "uncategorized"
        purpose = _infer_location_purpose_from_context(
            existing_purpose=raw_purpose,
            feature_candidates=feature_candidates,
            likely_paths=likely_target_paths,
            workspace_paths=actionable_world_paths + uncertain_world_paths,
            gui_controls=associated_gui_controls,
            outcome_keys=meaningful_outcome_keys,
        )

        missing_evidence = []
        if len(actionable_world_paths) == 0 and len(associated_gui_controls) == 0:
            missing_evidence.append("No actionable world anchor or GUI target observed")
        if len(meaningful_outcome_keys) == 0:
            missing_evidence.append("No gameplay-linked outcome signal (state changes are transient or absent)")
        if len(cluster["transactions"]) <= 1:
            missing_evidence.append("Single-transaction evidence only")

        location_registry.append({
            "id": cluster["id"],
            "candidatePurpose": purpose,
            "representativePosition": representative,
            "positionBounds": range_box,
            "supportingInteractionCount": cluster["count"],
            "supportingTransactionCount": len(cluster["transactions"]),
            "controlTypes": control_types,
            "actionKinds": action_kinds,
            "featureCandidates": feature_candidates,
            "likelyTargetPaths": likely_target_paths,
            "relevantWorkspaceObjectPaths": actionable_world_paths[:16],
            "nearbyWorldObjectPaths": (actionable_world_paths + uncertain_world_paths)[:16],
            "uncertainNearbyObjectPaths": uncertain_world_paths[:16],
            "interactionMechanisms": derived_mechanisms,
            "associatedGuiControls": associated_gui_controls,
            "requiredActivationConditions": [item[0] for item in sorted(cluster["requiredConditions"].items(), key=lambda item: (-item[1], item[0]))[:16]],
            "observedOutcomes": observed_outcomes,
            "meaningfulOutcomeKeys": meaningful_outcome_keys[:20],
            "worldContexts": [item[0] for item in sorted(cluster["worldContexts"].items(), key=lambda item: (-item[1], item[0]))[:8]],
            "characterGenerations": sorted(cluster["characterGenerations"]),
            "revisited": len(cluster["transactions"]) > 1,
            "outcomeLinked": len(meaningful_outcome_keys) > 0,
            "proximityEvidenceOnly": True,
            "confidence": {
                "score": round(confidence_score, 3),
                "level": _confidence_level(confidence_score),
                "limitations": [
                    "Observed client-visible positional proximity only",
                    "No automatic server-side causality proof",
                ],
            },
            "uncertaintyNotes": [
                "Location clustering is spatially inferred from observed action positions",
            ],
            "missingEvidence": missing_evidence,
            "unresolvedRequirements": [
                item
                for item in (
                    "Validate deterministic navigation path" if len(cluster["beforePositions"]) == 0 else None,
                    "Collect repeat run with explicit gameplay-linked outcomes" if len(meaningful_outcome_keys) == 0 else None,
                )
                if item
            ],
            "sequences": sorted(cluster["sequences"])[:60],
            "transactions": sorted(cluster["transactions"])[:60],
            "beforePositions": cluster["beforePositions"][:10],
            "postPositions": cluster["postPositions"][:10],
        })

    location_by_id = {item["id"]: item for item in location_registry}

    spatial_relationships: list[dict[str, Any]] = []
    for relation in relationships[:400]:
        if not isinstance(relation, dict):
            continue
        seq = relation.get("interactionSequence") if isinstance(relation.get("interactionSequence"), int) else None
        tx_id = relation.get("transactionId") if isinstance(relation.get("transactionId"), str) else None
        location_id = sequence_to_location.get(seq) if seq is not None else None
        if location_id is None and tx_id:
            location_id = transaction_to_location.get(tx_id)
        if location_id is None:
            continue
        positional = row_by_sequence.get(seq) if isinstance(seq, int) else {}
        action_payload = relation.get("action") if isinstance(relation.get("action"), dict) else {}
        action_type = action_payload.get("type") if isinstance(action_payload.get("type"), str) else None
        inferred_relationship_mechanism = None
        if isinstance(action_type, str):
            if action_type.startswith("GuiButton."):
                inferred_relationship_mechanism = "gui-button"
            elif action_type.startswith("InputBegan.Keyboard"):
                inferred_relationship_mechanism = "keybind"
            elif action_type.startswith("InputBegan.MouseButton"):
                inferred_relationship_mechanism = "pointer-input"
            elif action_type.startswith("ProximityPrompt."):
                inferred_relationship_mechanism = "prompt"
            elif action_type.startswith("Tool."):
                inferred_relationship_mechanism = "tool"

        spatial_relationships.append({
            "id": "spatial_" + str(relation.get("id") or "unknown"),
            "relationshipId": relation.get("id"),
            "locationId": location_id,
            "interactionSequence": seq,
            "transactionId": tx_id,
            "timestamp": relation.get("sessionElapsedSeconds"),
            "beforeActionPosition": positional.get("before") if isinstance(positional, dict) else None,
            "atActionPosition": positional.get("action") if isinstance(positional, dict) else None,
            "postActionPosition": positional.get("post") if isinstance(positional, dict) else None,
            "observationWindows": positional.get("observationWindows") if isinstance(positional, dict) else relation.get("observationWindows"),
            "clickObservationId": (
                action_payload.get("clickObservationId") if isinstance(action_payload.get("clickObservationId"), str)
                else (positional.get("clickObservationId") if isinstance(positional, dict) and isinstance(positional.get("clickObservationId"), str) else None)
            ),
            "clickTargetObservation": _normalize_click_target_observation(action_payload.get("clickTargetObservation")),
            "characterOrientationAtAction": (
                _normalize_orientation(action_payload.get("characterOrientationAtAction"))
                or (positional.get("characterOrientation") if isinstance(positional, dict) and isinstance(positional.get("characterOrientation"), dict) else None)
            ),
            "cameraOrientationAtAction": (
                _normalize_orientation(action_payload.get("cameraOrientationAtAction"))
                or (positional.get("cameraOrientation") if isinstance(positional, dict) and isinstance(positional.get("cameraOrientation"), dict) else None)
            ),
            "cameraCharacterHeadingDeltaDegrees": (
                _numeric(action_payload.get("cameraCharacterHeadingDeltaDegrees"))
                or (positional.get("cameraCharacterHeadingDeltaDegrees") if isinstance(positional, dict) else None)
            ),
            "action": action_payload,
            "interactionType": action_type,
            "interactionMechanism": inferred_relationship_mechanism,
            "objectIdentity": {
                "targetPath": action_payload.get("targetPath") if isinstance(action_payload.get("targetPath"), str) else None,
                "candidateWorldObjects": (location_by_id.get(location_id) or {}).get("relevantWorkspaceObjectPaths", [])[:8],
                "candidateGuiTargets": (location_by_id.get(location_id) or {}).get("associatedGuiControls", [])[:8],
            },
            "stateSignalCount": len(relation.get("stateBeforeAfter") or []),
            "stateBeforeAfter": relation.get("stateBeforeAfter") if isinstance(relation.get("stateBeforeAfter"), list) else [],
            "outcomeStateKeys": [
                item.get("key")
                for item in (relation.get("stateBeforeAfter") or [])
                if isinstance(item, dict) and isinstance(item.get("key"), str)
            ][:16],
            "meaningfulOutcomeStateKeys": [
                key
                for key in [
                    item.get("key")
                    for item in (relation.get("stateBeforeAfter") or [])
                    if isinstance(item, dict) and isinstance(item.get("key"), str)
                ]
                if _is_gameplay_outcome_key(key)
            ][:16],
            "outcomeVerification": {
                "interactionObserved": True,
                "stateChangeObserved": len(relation.get("stateBeforeAfter") or []) > 0,
                "temporallyAssociated": any(
                    isinstance(item, dict)
                    and isinstance(item.get("key"), str)
                    and _is_gameplay_outcome_key(item.get("key"))
                    for item in (relation.get("stateBeforeAfter") or [])
                ),
                "multiSignalCorroborated": len({
                    item.get("key")
                    for item in (relation.get("stateBeforeAfter") or [])
                    if isinstance(item, dict)
                    and isinstance(item.get("key"), str)
                    and _is_gameplay_outcome_key(item.get("key"))
                }) >= 2,
                "causalityProven": False,
            },
            "confidence": relation.get("confidence") if isinstance(relation.get("confidence"), dict) else {},
            "causality": "not-proven-temporal-correlation-only",
            "potentialConfoundingInteractions": {
                "attribution": positional.get("attribution") if isinstance(positional, dict) else (relation.get("conflictingActivity") or {}).get("attribution"),
                "signals": (
                    (relation.get("conflictingActivity") or {}).get("signals")
                    if isinstance((relation.get("conflictingActivity") or {}).get("signals"), list)
                    else []
                ),
            },
        })

    source_provenance = payload.get("sourceProvenance") if isinstance(payload.get("sourceProvenance"), dict) else {}
    runtime_verified = bool(payload.get("runtimeVerified") is True or source_provenance.get("runtimeVerified") is True)
    gameplay_verified = bool(payload.get("gameplayVerified") is True or source_provenance.get("gameplayVerified") is True)

    navigation_candidates: list[dict[str, Any]] = []
    actionable_navigation_candidates = 0
    ready_navigation_candidates = 0
    live_validated_destinations = 0

    for location in location_registry[:120]:
        before_positions = location.get("beforePositions") if isinstance(location.get("beforePositions"), list) else []
        approach_position = before_positions[0] if before_positions else None

        observed_location = isinstance(location.get("representativePosition"), dict)
        interaction_associated = (location.get("supportingInteractionCount") or 0) > 0
        outcome_associated = bool(location.get("outcomeLinked"))

        world_targets = location.get("relevantWorkspaceObjectPaths") or []
        gui_targets = location.get("associatedGuiControls") or []
        has_world_target = len(world_targets) > 0
        has_gui_target = len(gui_targets) > 0
        has_action_target = has_world_target or has_gui_target

        mechanisms = [item for item in (location.get("interactionMechanisms") or []) if isinstance(item, str)]
        has_mechanism = len(mechanisms) > 0
        pointer_only = has_mechanism and set(mechanisms) == {"pointer-input"}
        if pointer_only and not has_world_target and not has_gui_target:
            has_mechanism = False

        gui_flow_evidence = has_gui_target and (
            len(gui_targets) >= 2
            or any(isinstance(item, str) and item.startswith("GuiButton.") for item in (location.get("controlTypes") or []))
        )

        actionable_candidate = (
            observed_location
            and interaction_associated
            and has_action_target
            and has_mechanism
            and (outcome_associated or gui_flow_evidence)
        )
        if actionable_candidate:
            actionable_navigation_candidates += 1

        repeated_support = (location.get("supportingTransactionCount") or 0) >= 2 or (location.get("supportingInteractionCount") or 0) >= 3
        ready_for_live_validation = (
            actionable_candidate
            and (location.get("confidence") or {}).get("score", 0) >= 0.72
            and repeated_support
        )
        if ready_for_live_validation:
            ready_navigation_candidates += 1

        live_validated = ready_for_live_validation and runtime_verified and gameplay_verified
        if live_validated:
            live_validated_destinations += 1

        readiness_blockers: list[str] = []
        if not has_action_target:
            readiness_blockers.append("No actionable target path (world anchor or GUI control)")
        if not has_mechanism:
            readiness_blockers.append("No reliable interaction mechanism evidence")
        if not (outcome_associated or gui_flow_evidence):
            readiness_blockers.append("No gameplay-linked outcome or repeatable GUI flow evidence")
        if actionable_candidate and not repeated_support:
            readiness_blockers.append("Insufficient repeat observations (single transaction and low interaction count)")
        if actionable_candidate and (location.get("confidence") or {}).get("score", 0) < 0.72:
            readiness_blockers.append("Location confidence below live-validation-ready threshold")
        if ready_for_live_validation and not live_validated:
            readiness_blockers.append("Live gameplay validation not yet performed")

        if live_validated:
            validation_status = "live-validated-destination"
        elif ready_for_live_validation:
            validation_status = "actionable-navigation-candidate"
        elif actionable_candidate:
            validation_status = "actionable-navigation-candidate-partial"
        elif outcome_associated:
            validation_status = "outcome-associated-position"
        elif interaction_associated:
            validation_status = "interaction-position"
        elif observed_location:
            validation_status = "observed-position"
        else:
            validation_status = "insufficient-evidence"

        navigation_candidates.append({
            "destinationId": location.get("id"),
            "candidatePurpose": location.get("candidatePurpose"),
            "targetObjectCoordinates": None,
            "observedPlayerInteractionCoordinates": location.get("representativePosition"),
            "suggestedApproachPosition": approach_position,
            "interactionRadiusStuds": None,
            "requiredActionMechanisms": mechanisms,
            "prerequisites": location.get("requiredActivationConditions") or [],
            "worldAreaIdentity": (location.get("worldContexts") or [None])[0],
            "confidence": location.get("confidence"),
            "validationStatus": validation_status,
            "evidenceStatus": {
                "observedPosition": observed_location,
                "interactionPosition": interaction_associated,
                "outcomeAssociatedPosition": outcome_associated,
                "actionableNavigationCandidate": actionable_candidate,
                "readyForLiveValidation": ready_for_live_validation,
                "liveValidatedDestination": live_validated,
            },
            "targetObjectPaths": world_targets,
            "targetGuiPaths": gui_targets,
            "supportingEvidence": {
                "supportingInteractionCount": location.get("supportingInteractionCount"),
                "supportingTransactionCount": location.get("supportingTransactionCount"),
                "meaningfulOutcomeKeys": location.get("meaningfulOutcomeKeys") or [],
            },
            "readinessBlockers": readiness_blockers,
            "limitations": [
                "Approach positions are observational, not guaranteed valid navigation meshes",
                "Server-side interaction acceptance must be validated in controlled runs",
            ],
        })


    location_navigation_candidates = [dict(item) for item in navigation_candidates]

    location_ids = [item.get("id") for item in location_registry if isinstance(item.get("id"), str)]
    parent = {location_id: location_id for location_id in location_ids}
    rank = {location_id: 0 for location_id in location_ids}

    def _find_parent(location_id: str) -> str:
        while parent[location_id] != location_id:
            parent[location_id] = parent[parent[location_id]]
            location_id = parent[location_id]
        return location_id

    def _union_locations(left: str, right: str) -> None:
        left_root = _find_parent(left)
        right_root = _find_parent(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        if rank[left_root] == rank[right_root]:
            rank[left_root] += 1

    def _identity_set(paths: Sequence[str]) -> set[str]:
        out: set[str] = set()
        for path in paths:
            key = _path_identity_key(path)
            if key:
                out.add(key)
        return out

    for index, left_id in enumerate(location_ids):
        left = location_by_id.get(left_id)
        if not isinstance(left, dict):
            continue
        for right_id in location_ids[index + 1:]:
            right = location_by_id.get(right_id)
            if not isinstance(right, dict):
                continue
            if not _same_world_identity(left, right):
                continue

            distance = _position_distance(left.get("representativePosition"), right.get("representativePosition"))
            if distance is None or distance > 12.0:
                continue

            left_world_targets = _identity_set(left.get("relevantWorkspaceObjectPaths") or [])
            right_world_targets = _identity_set(right.get("relevantWorkspaceObjectPaths") or [])
            left_gui_targets = _identity_set(left.get("associatedGuiControls") or [])
            right_gui_targets = _identity_set(right.get("associatedGuiControls") or [])
            left_nearby = _identity_set(left.get("nearbyWorldObjectPaths") or [])
            right_nearby = _identity_set(right.get("nearbyWorldObjectPaths") or [])

            shared_world_targets = len(left_world_targets & right_world_targets)
            shared_gui_targets = len(left_gui_targets & right_gui_targets)
            shared_nearby = len(left_nearby & right_nearby)
            shared_feature_candidates = len(
                {item for item in (left.get("featureCandidates") or []) if isinstance(item, str)}
                & {item for item in (right.get("featureCandidates") or []) if isinstance(item, str)}
            )
            same_purpose = left.get("candidatePurpose") == right.get("candidatePurpose")

            pair_score = 0
            if distance <= 3.0:
                pair_score += 3
            elif distance <= 6.0:
                pair_score += 2
            elif distance <= 10.0:
                pair_score += 1
            if shared_world_targets > 0:
                pair_score += 2
            if shared_gui_targets > 0:
                pair_score += 2
            if shared_nearby >= 3:
                pair_score += 1
            if same_purpose:
                pair_score += 1
            if shared_feature_candidates > 0:
                pair_score += 1
            if left_world_targets and right_world_targets and shared_world_targets == 0 and distance > 4.0:
                pair_score -= 2

            if pair_score >= 4:
                _union_locations(left_id, right_id)

    location_components: dict[str, list[str]] = {}
    for location_id in location_ids:
        root = _find_parent(location_id)
        location_components.setdefault(root, []).append(location_id)

    physical_destination_registry: list[dict[str, Any]] = []
    location_to_destination: dict[str, str] = {}

    for member_ids in sorted(location_components.values(), key=lambda values: (len(values), values), reverse=True):
        member_ids = sorted(member_ids)
        members = [location_by_id[item] for item in member_ids if isinstance(location_by_id.get(item), dict)]
        if not members:
            continue

        weighted_x = 0.0
        weighted_y = 0.0
        weighted_z = 0.0
        total_weight = 0.0
        world_counts: dict[str, int] = {}

        supporting_position_samples: list[dict[str, Any]] = []
        interaction_targets: set[str] = set()
        workspace_paths: set[str] = set()
        gui_paths: set[str] = set()
        interaction_mechanisms: set[str] = set()
        activation_conditions: set[str] = set()
        candidate_purposes: dict[str, int] = {}
        feature_candidates: set[str] = set()
        confidence_weighted_sum = 0.0
        confidence_weight_total = 0.0
        confidence_values: list[float] = []

        interaction_count = 0
        transaction_count = 0
        missing_evidence: set[str] = set()
        unresolved_requirements: set[str] = set()

        for member in members:
            representative = member.get("representativePosition") if isinstance(member.get("representativePosition"), dict) else None
            weight = float(max(1, int(member.get("supportingInteractionCount") or 0)))
            if representative:
                rx = float(_numeric(representative.get("x")) or 0.0)
                ry = float(_numeric(representative.get("y")) or 0.0)
                rz = float(_numeric(representative.get("z")) or 0.0)
                weighted_x += rx * weight
                weighted_y += ry * weight
                weighted_z += rz * weight
                total_weight += weight
                supporting_position_samples.append({"source": member.get("id"), "position": representative})

            for position in (member.get("beforePositions") or [])[:4]:
                if isinstance(position, dict):
                    supporting_position_samples.append({"source": member.get("id"), "position": position})
            for position in (member.get("postPositions") or [])[:4]:
                if isinstance(position, dict):
                    supporting_position_samples.append({"source": member.get("id"), "position": position})

            interaction_count += int(member.get("supportingInteractionCount") or 0)
            transaction_count += int(member.get("supportingTransactionCount") or 0)

            confidence_score = _numeric((member.get("confidence") or {}).get("score"))
            if confidence_score is not None:
                confidence_weighted_sum += float(confidence_score) * weight
                confidence_weight_total += weight
                confidence_values.append(float(confidence_score))

            for world in member.get("worldContexts") or []:
                if isinstance(world, str):
                    world_counts[world] = world_counts.get(world, 0) + 1
            for path in member.get("likelyTargetPaths") or []:
                if isinstance(path, str):
                    interaction_targets.add(path)
            for path in member.get("relevantWorkspaceObjectPaths") or []:
                if isinstance(path, str):
                    workspace_paths.add(path)
            for path in member.get("associatedGuiControls") or []:
                if isinstance(path, str):
                    gui_paths.add(path)
            for mechanism in member.get("interactionMechanisms") or []:
                if isinstance(mechanism, str):
                    interaction_mechanisms.add(mechanism)
            for condition in member.get("requiredActivationConditions") or []:
                if isinstance(condition, str):
                    activation_conditions.add(condition)
            for candidate in member.get("featureCandidates") or []:
                if isinstance(candidate, str):
                    feature_candidates.add(candidate)
            purpose = member.get("candidatePurpose") if isinstance(member.get("candidatePurpose"), str) else "uncategorized"
            candidate_purposes[purpose] = candidate_purposes.get(purpose, 0) + 1
            for note in member.get("missingEvidence") or []:
                if isinstance(note, str):
                    missing_evidence.add(note)
            for note in member.get("unresolvedRequirements") or []:
                if isinstance(note, str):
                    unresolved_requirements.add(note)

        representative_coordinates = None
        if total_weight > 0:
            representative_coordinates = {
                "x": round(weighted_x / total_weight, 4),
                "y": round(weighted_y / total_weight, 4),
                "z": round(weighted_z / total_weight, 4),
            }

        world_identity = sorted(world_counts.items(), key=lambda item: (-item[1], item[0]))[0][0] if world_counts else None
        primary_purpose = sorted(candidate_purposes.items(), key=lambda item: (-item[1], item[0]))[0][0] if candidate_purposes else "uncategorized"

        seed_parts = [
            world_identity or "world:unknown",
            primary_purpose,
            str(round((representative_coordinates or {}).get("x", 0.0), 1)),
            str(round((representative_coordinates or {}).get("y", 0.0), 1)),
            str(round((representative_coordinates or {}).get("z", 0.0), 1)),
        ]
        seed_parts.extend(sorted(_identity_set(sorted(workspace_paths | gui_paths | interaction_targets)))[:4])
        destination_id = "dest_" + hashlib.sha256("|".join(seed_parts).encode("utf-8")).hexdigest()[:14]

        for location_id in member_ids:
            location_to_destination[location_id] = destination_id

        physical_destination_registry.append({
            "destinationId": destination_id,
            "sourceLocationIds": member_ids,
            "worldAreaIdentity": world_identity,
            "representativeCoordinates": representative_coordinates,
            "supportingPositionSamples": supporting_position_samples[:36],
            "candidatePurpose": primary_purpose,
            "candidatePurposes": candidate_purposes,
            "associatedInteractionTargets": sorted(interaction_targets)[:24],
            "relevantWorkspacePaths": sorted(workspace_paths)[:24],
            "relevantGuiPaths": sorted(gui_paths)[:24],
            "observedInteractionMechanisms": sorted(interaction_mechanisms),
            "activationConditions": sorted(activation_conditions)[:24],
            "featureCandidates": sorted(feature_candidates),
            "supportingInteractionCount": interaction_count,
            "supportingTransactionCount": transaction_count,
            "evidenceConfidence": {
                "score": round(confidence_weighted_sum / confidence_weight_total, 3) if confidence_weight_total > 0 else 0.0,
                "maxScore": round(max(confidence_values), 3) if confidence_values else 0.0,
                "minScore": round(min(confidence_values), 3) if confidence_values else 0.0,
                "locationCount": len(member_ids),
            },
            "missingEvidence": sorted(missing_evidence),
            "unresolvedRequirements": sorted(unresolved_requirements),
        })

    for location in location_registry:
        location["physicalDestinationId"] = location_to_destination.get(location.get("id"))

    destination_relationships: dict[str, list[dict[str, Any]]] = {}
    workflow_buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for relationship in spatial_relationships:
        destination_id = location_to_destination.get(relationship.get("locationId"))
        relationship["physicalDestinationId"] = destination_id
        if not isinstance(destination_id, str):
            continue

        destination_relationships.setdefault(destination_id, []).append(relationship)
        action = relationship.get("action") if isinstance(relationship.get("action"), dict) else {}
        target_path = action.get("targetPath") if isinstance(action.get("targetPath"), str) else None
        workflow_identity = relationship.get("transactionId") if isinstance(relationship.get("transactionId"), str) else None
        if workflow_identity is None:
            workflow_identity = "|".join([
                _path_identity_key(target_path) or "target:unknown",
                relationship.get("interactionType") if isinstance(relationship.get("interactionType"), str) else "type:unknown",
                relationship.get("interactionMechanism") if isinstance(relationship.get("interactionMechanism"), str) else "mechanism:unknown",
            ])

        workflow_key = (destination_id, workflow_identity)
        bucket = workflow_buckets.setdefault(workflow_key, {
            "destinationId": destination_id,
            "workflowIdentity": workflow_identity,
            "relationshipIds": [],
            "interactionSequences": set(),
            "transactionIds": set(),
            "interactionTargets": set(),
            "interactionMechanisms": set(),
            "interactionTypes": set(),
            "stateSignalKeys": {},
            "meaningfulOutcomeKeys": {},
            "actionKinds": {},
        })

        if isinstance(relationship.get("id"), str):
            bucket["relationshipIds"].append(relationship.get("id"))
        if isinstance(relationship.get("interactionSequence"), int):
            bucket["interactionSequences"].add(relationship.get("interactionSequence"))
        if isinstance(relationship.get("transactionId"), str):
            bucket["transactionIds"].add(relationship.get("transactionId"))
        if isinstance(target_path, str):
            bucket["interactionTargets"].add(target_path)
        if isinstance(relationship.get("interactionMechanism"), str):
            bucket["interactionMechanisms"].add(relationship.get("interactionMechanism"))
        if isinstance(relationship.get("interactionType"), str):
            bucket["interactionTypes"].add(relationship.get("interactionType"))

        action_kind = action.get("kind") if isinstance(action.get("kind"), str) else None
        if action_kind:
            bucket["actionKinds"][action_kind] = bucket["actionKinds"].get(action_kind, 0) + 1

        for state_key in relationship.get("outcomeStateKeys") or []:
            if isinstance(state_key, str):
                bucket["stateSignalKeys"][state_key] = bucket["stateSignalKeys"].get(state_key, 0) + 1
        for state_key in relationship.get("meaningfulOutcomeStateKeys") or []:
            if isinstance(state_key, str):
                bucket["meaningfulOutcomeKeys"][state_key] = bucket["meaningfulOutcomeKeys"].get(state_key, 0) + 1

    destination_workflows: list[dict[str, Any]] = []
    workflows_by_destination: dict[str, list[dict[str, Any]]] = {}
    for (_, _), bucket in sorted(workflow_buckets.items(), key=lambda item: (item[1]["destinationId"], item[1]["workflowIdentity"])):
        workflow_id = "wf_" + hashlib.sha256((bucket["destinationId"] + "|" + str(bucket["workflowIdentity"])).encode("utf-8")).hexdigest()[:14]
        workflow = {
            "workflowId": workflow_id,
            "destinationId": bucket["destinationId"],
            "workflowIdentity": bucket["workflowIdentity"],
            "relationshipIds": bucket["relationshipIds"][:80],
            "interactionSequences": sorted(bucket["interactionSequences"]),
            "transactionIds": sorted(bucket["transactionIds"]),
            "interactionTargets": sorted(bucket["interactionTargets"])[:24],
            "interactionMechanisms": sorted(bucket["interactionMechanisms"]),
            "interactionTypes": sorted(bucket["interactionTypes"]),
            "actionKinds": [item[0] for item in sorted(bucket["actionKinds"].items(), key=lambda item: (-item[1], item[0]))],
            "stateSignalKeys": [item[0] for item in sorted(bucket["stateSignalKeys"].items(), key=lambda item: (-item[1], item[0]))[:24]],
            "meaningfulOutcomeKeys": [item[0] for item in sorted(bucket["meaningfulOutcomeKeys"].items(), key=lambda item: (-item[1], item[0]))[:24]],
            "outcomeVerificationTier": (
                "temporally-correlated-multi-signal"
                if len(bucket["meaningfulOutcomeKeys"]) >= 2
                else ("temporally-correlated-single-signal" if len(bucket["meaningfulOutcomeKeys"]) == 1 else "interaction-observed-only")
            ),
        }
        destination_workflows.append(workflow)
        workflows_by_destination.setdefault(bucket["destinationId"], []).append(workflow)

    consolidated_navigation_candidates: list[dict[str, Any]] = []
    consolidated_actionable_count = 0
    consolidated_ready_count = 0
    consolidated_live_validated_count = 0
    consolidated_gameplay_verified_count = 0

    for destination in sorted(physical_destination_registry, key=lambda item: (-int(item.get("supportingInteractionCount") or 0), item.get("destinationId") or "")):
        destination_id = destination.get("destinationId")
        destination_relationship_list = destination_relationships.get(destination_id, []) if isinstance(destination_id, str) else []
        destination_workflow_list = workflows_by_destination.get(destination_id, []) if isinstance(destination_id, str) else []

        meaningful_outcomes: set[str] = set()
        state_signals: set[str] = set()
        interaction_sequences: set[int] = set()
        transaction_ids: set[str] = set()
        for relationship in destination_relationship_list:
            for key in relationship.get("meaningfulOutcomeStateKeys") or []:
                if isinstance(key, str):
                    meaningful_outcomes.add(key)
            for key in relationship.get("outcomeStateKeys") or []:
                if isinstance(key, str):
                    state_signals.add(key)
            if isinstance(relationship.get("interactionSequence"), int):
                interaction_sequences.add(relationship.get("interactionSequence"))
            if isinstance(relationship.get("transactionId"), str):
                transaction_ids.add(relationship.get("transactionId"))

        representative_coordinates = destination.get("representativeCoordinates") if isinstance(destination.get("representativeCoordinates"), dict) else None
        observed_position = representative_coordinates is not None
        interaction_observed = int(destination.get("supportingInteractionCount") or 0) > 0
        workspace_targets = [item for item in (destination.get("relevantWorkspacePaths") or []) if isinstance(item, str)]
        gui_targets = [item for item in (destination.get("relevantGuiPaths") or []) if isinstance(item, str)]
        has_action_target = len(workspace_targets) > 0 or len(gui_targets) > 0

        mechanisms = [item for item in (destination.get("observedInteractionMechanisms") or []) if isinstance(item, str)]
        pointer_only = len(mechanisms) > 0 and set(mechanisms) == {"pointer-input"}
        has_mechanism = len(mechanisms) > 0 and not (pointer_only and not has_action_target)

        repeated_support = int(destination.get("supportingTransactionCount") or 0) >= 2 or int(destination.get("supportingInteractionCount") or 0) >= 3
        confidence_score = float(_numeric((destination.get("evidenceConfidence") or {}).get("score")) or 0.0)

        actionable_candidate = observed_position and interaction_observed and has_action_target and has_mechanism
        ready_for_live_validation = actionable_candidate and repeated_support and confidence_score >= 0.68
        live_validated = bool(ready_for_live_validation and runtime_verified and gameplay_verified)

        if actionable_candidate:
            consolidated_actionable_count += 1
        if ready_for_live_validation:
            consolidated_ready_count += 1
        if live_validated:
            consolidated_live_validated_count += 1

        temporal_associated = len(meaningful_outcomes) > 0
        multi_signal_corroborated = len(meaningful_outcomes) >= 2
        gameplay_tier = (
            "live-validated"
            if live_validated and temporal_associated
            else (
                "temporally-correlated-multi-signal"
                if multi_signal_corroborated
                else (
                    "temporally-correlated-single-signal"
                    if temporal_associated
                    else ("state-change-observed" if len(state_signals) > 0 else "interaction-observed-only")
                )
            )
        )
        if gameplay_tier == "live-validated":
            consolidated_gameplay_verified_count += 1

        readiness_blockers: list[str] = []
        if not observed_position:
            readiness_blockers.append("No representative destination coordinates observed")
        if not has_action_target:
            readiness_blockers.append("No actionable target path (workspace or GUI)")
        if not has_mechanism:
            readiness_blockers.append("No reliable interaction mechanism evidence")
        if actionable_candidate and not repeated_support:
            readiness_blockers.append("Insufficient repeat observations for navigation confidence")
        if actionable_candidate and confidence_score < 0.68:
            readiness_blockers.append("Destination confidence below navigation-ready threshold")
        if ready_for_live_validation and not live_validated:
            readiness_blockers.append("Live gameplay validation not yet performed")

        if live_validated:
            navigation_status = "live-validated-destination"
        elif ready_for_live_validation:
            navigation_status = "navigation-ready"
        elif actionable_candidate:
            navigation_status = "actionable-navigation-candidate"
        elif interaction_observed:
            navigation_status = "interaction-position"
        elif observed_position:
            navigation_status = "observed-position"
        else:
            navigation_status = "insufficient-evidence"

        outcome_missing_evidence: list[str] = []
        if len(state_signals) == 0:
            outcome_missing_evidence.append("No state change observed after interaction")
        if len(meaningful_outcomes) == 0:
            outcome_missing_evidence.append("No gameplay-relevant outcome signal observed")
        if temporal_associated and not multi_signal_corroborated:
            outcome_missing_evidence.append("Outcome supported by only one gameplay-relevant signal")
        if not live_validated:
            outcome_missing_evidence.append("No controlled live validation proving reproducible outcome")

        destination["associatedWorkflows"] = [item.get("workflowId") for item in destination_workflow_list if isinstance(item.get("workflowId"), str)]
        destination["navigationReadiness"] = {
            "status": navigation_status,
            "actionable": actionable_candidate,
            "readyForLiveValidation": ready_for_live_validation,
            "liveValidated": live_validated,
            "blockers": readiness_blockers,
        }
        destination["gameplayOutcomeVerification"] = {
            "status": "verified" if gameplay_tier == "live-validated" else "unverified",
            "tier": gameplay_tier,
            "interactionObserved": interaction_observed,
            "stateChangeObserved": len(state_signals) > 0,
            "temporallyAssociated": temporal_associated,
            "multiSignalCorroborated": multi_signal_corroborated,
            "causalityProven": False,
            "liveValidated": live_validated,
            "meaningfulOutcomeKeys": sorted(meaningful_outcomes)[:24],
            "missingEvidence": outcome_missing_evidence,
        }
        destination["provenanceReferences"] = {
            "interactionSequences": sorted(interaction_sequences),
            "transactionIds": sorted(transaction_ids),
            "relationshipIds": [item.get("id") for item in destination_relationship_list if isinstance(item.get("id"), str)][:120],
        }

        consolidated_navigation_candidates.append({
            "destinationId": destination_id,
            "sourceLocationIds": destination.get("sourceLocationIds") or [],
            "candidatePurpose": destination.get("candidatePurpose"),
            "worldAreaIdentity": destination.get("worldAreaIdentity"),
            "representativeCoordinates": representative_coordinates,
            "supportingPositionSamples": destination.get("supportingPositionSamples") or [],
            "associatedInteractionTargets": destination.get("associatedInteractionTargets") or [],
            "associatedWorkflowIds": destination.get("associatedWorkflows") or [],
            "observedInteractionMechanisms": mechanisms,
            "requiredActionMechanisms": mechanisms,
            "activationConditions": destination.get("activationConditions") or [],
            "prerequisites": destination.get("activationConditions") or [],
            "relevantWorkspacePaths": workspace_targets,
            "targetObjectPaths": workspace_targets,
            "relevantGuiPaths": gui_targets,
            "targetGuiPaths": gui_targets,
            "evidenceConfidence": destination.get("evidenceConfidence"),
            "confidence": destination.get("evidenceConfidence"),
            "navigationReadiness": destination.get("navigationReadiness"),
            "gameplayOutcomeVerification": destination.get("gameplayOutcomeVerification"),
            "evidenceStatus": {
                "observedPosition": observed_position,
                "interactionPosition": interaction_observed,
                "outcomeAssociatedPosition": temporal_associated,
                "actionableNavigationCandidate": actionable_candidate,
                "readyForLiveValidation": ready_for_live_validation,
                "liveValidatedDestination": live_validated,
            },
            "unresolvedRequirements": sorted(set((destination.get("unresolvedRequirements") or []) + readiness_blockers + outcome_missing_evidence))[:32],
            "missingEvidence": sorted(set((destination.get("missingEvidence") or []) + readiness_blockers + outcome_missing_evidence))[:32],
            "provenanceReferences": destination.get("provenanceReferences"),
            "validationStatus": navigation_status,
            "readinessBlockers": readiness_blockers,
            "limitations": [
                "Approach positions are observational, not guaranteed valid navigation meshes",
                "Server-side interaction acceptance must be validated in controlled runs",
            ],
        })

    navigation_candidates = consolidated_navigation_candidates
    actionable_navigation_candidates = consolidated_actionable_count
    ready_navigation_candidates = consolidated_ready_count
    live_validated_destinations = consolidated_live_validated_count
    gameplay_verified_destinations = consolidated_gameplay_verified_count

    # Universal pickup/collectible discovery (evidence-driven, bounded, non-causal).
    pickup_candidates_by_path: dict[str, dict[str, Any]] = {}
    max_pickup_candidates = 5000

    def _pickup_mechanisms_from_object(obj: dict[str, Any], class_name: str) -> list[str]:
        interaction = obj.get("interaction") if isinstance(obj.get("interaction"), dict) else {}
        out: set[str] = set()
        if class_name == "ProximityPrompt" or interaction.get("hasPrompt") is True or "actionText" in interaction:
            out.add("prompt")
        if class_name == "ClickDetector" or interaction.get("hasClickDetector") is True:
            out.add("click")
        if interaction.get("touchInterest") is True:
            out.add("touch")
        gui_control = obj.get("guiControl") if isinstance(obj.get("guiControl"), dict) else {}
        if bool(gui_control.get("interactable") is True or gui_control.get("active") is True):
            out.add("gui")
        return sorted(out)

    def _pickup_state_delta_summary(state_changes: list[dict[str, Any]]) -> dict[str, Any]:
        impacts: list[dict[str, Any]] = []
        meaningful = 0
        for change in state_changes[:24]:
            if not isinstance(change, dict):
                continue
            key = change.get("key") if isinstance(change.get("key"), str) else None
            if not key:
                continue
            if not _is_gameplay_outcome_key(key):
                continue
            meaningful += 1
            before = _numeric(change.get("before"))
            after = _numeric(change.get("after"))
            delta = (after - before) if before is not None and after is not None else None
            low = key.lower()
            if any(token in low for token in ("coin", "cash", "money", "gold", "gem", "ticket", "token", "currency")):
                category = "currency"
            elif any(token in low for token in ("inventory", "item", "backpack", "pet", "equip")):
                category = "inventory"
            elif any(token in low for token in ("ammo", "bullet", "shell", "mag", "reload")):
                category = "ammunition"
            elif any(token in low for token in ("health", "armor", "armour", "shield")):
                category = "health-or-armour"
            elif any(token in low for token in ("quest", "objective", "mission", "progress")):
                category = "quest-or-progress"
            else:
                category = "other"
            impacts.append({
                "key": key,
                "category": category,
                "before": before,
                "after": after,
                "delta": round(delta, 4) if isinstance(delta, float) else delta,
            })
        return {"meaningfulCount": meaningful, "impacts": impacts}

    def _upsert_pickup_candidate(path: str, class_name: Optional[str], mechanisms: list[str],
                                 position: Optional[dict[str, float]], source: str,
                                 supporting_event: Optional[dict[str, Any]] = None) -> Optional[dict[str, Any]]:
        if not path or _workspace_root_like_path(path):
            return None
        low = path.lower()
        if not low.startswith("workspace."):
            return None
        candidate = pickup_candidates_by_path.get(path)
        if candidate is None:
            if len(pickup_candidates_by_path) >= max_pickup_candidates:
                return None
            name_score = _pickup_like_name_score(path)
            category = _pickup_category_from_path(path)
            decorative = any(token in low for token in _DECORATIVE_PATH_TOKENS)
            candidate = {
                "candidateId": "pickup_" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:16],
                "instancePath": path,
                "class": class_name or "unknown",
                "pickupCategory": category,
                "candidateConfidence": {
                    "score": 0.0,
                    "level": "low",
                    "supportingSignals": [],
                    "decorativeRisk": decorative,
                },
                "collectionMechanisms": [],
                "supportingEvidenceIds": [],
                "worldContexts": set(),
                "positions": [],
                "firstObservedElapsed": None,
                "lastObservedElapsed": None,
                "appearanceCount": 0,
                "nameScore": name_score,
                "observedInteractions": 0,
                "stateLinkedOutcomes": 0,
                "availabilityStatus": "unknown",
                "moving": False,
            }
            pickup_candidates_by_path[path] = candidate

        candidate["appearanceCount"] += 1
        for mechanism in mechanisms:
            if isinstance(mechanism, str) and mechanism not in candidate["collectionMechanisms"]:
                candidate["collectionMechanisms"].append(mechanism)
        if position and isinstance(position, dict):
            candidate["positions"].append(position)
        if isinstance(supporting_event, dict):
            elapsed = _numeric(supporting_event.get("sessionElapsedSeconds"))
            if elapsed is not None:
                if candidate["firstObservedElapsed"] is None or elapsed < candidate["firstObservedElapsed"]:
                    candidate["firstObservedElapsed"] = elapsed
                if candidate["lastObservedElapsed"] is None or elapsed > candidate["lastObservedElapsed"]:
                    candidate["lastObservedElapsed"] = elapsed
            world_ctx = supporting_event.get("worldContext") if isinstance(supporting_event.get("worldContext"), dict) else {}
            world_path = world_ctx.get("path") if isinstance(world_ctx.get("path"), str) else world_ctx.get("name")
            if isinstance(world_path, str) and world_path:
                candidate["worldContexts"].add(world_path)
            if isinstance(supporting_event.get("sequence"), int):
                candidate["supportingEvidenceIds"].append(f"event-seq-{supporting_event.get('sequence')}")

        return candidate

    # Seed candidates from baseline actionable index.
    for path, entry in list(baseline_actionable_index.items())[:12000]:
        if not isinstance(path, str):
            continue
        if _workspace_root_like_path(path):
            continue
        mechanisms: list[str] = []
        if isinstance(entry, dict):
            for mechanism, count in (entry.get("mechanisms") if isinstance(entry.get("mechanisms"), dict) else {}).items():
                if isinstance(mechanism, str) and type(count) is int and count > 0:
                    mechanisms.append(mechanism)
        _upsert_pickup_candidate(path, entry.get("class") if isinstance(entry, dict) and isinstance(entry.get("class"), str) else None, mechanisms, None, "baseline-index")

    # Seed candidates from current observation object inventory.
    for obj in objects[:14000]:
        if not isinstance(obj, dict):
            continue
        path = _canonical_object_path(obj.get("path"))
        if not isinstance(path, str):
            continue
        class_name = obj.get("class") if isinstance(obj.get("class"), str) else None
        mechanisms = _pickup_mechanisms_from_object(obj, class_name or "unknown")
        position = _position_from_value(obj.get("position"))
        candidate = _upsert_pickup_candidate(path, class_name, mechanisms, position, "object-inventory")
        if candidate is None:
            continue
        if position:
            candidate["supportingEvidenceIds"].append(f"object:{path}")

    pickup_collection_observations: list[dict[str, Any]] = []
    pickup_outcome_relationships: list[dict[str, Any]] = []

    # Event-linked candidate enrichment and collection observation capture.
    for event in events[:4200]:
        if not isinstance(event, dict):
            continue
        sequence = event.get("sequence") if isinstance(event.get("sequence"), int) else None
        tx_id = event.get("transactionId") if isinstance(event.get("transactionId"), str) else None
        elapsed = _numeric(event.get("sessionElapsedSeconds"))
        control_type = event.get("controlType") if isinstance(event.get("controlType"), str) else "unknown"
        state_changes = event.get("stateChanges") if isinstance(event.get("stateChanges"), list) else []
        state_summary = _pickup_state_delta_summary(state_changes)
        meaningful_count = int(state_summary.get("meaningfulCount") or 0)

        nearby = event.get("nearbyWorldObjects") if isinstance(event.get("nearbyWorldObjects"), list) else []
        for nearby_idx, nearby_obj in enumerate(nearby[:14]):
            if not isinstance(nearby_obj, dict):
                continue
            path = _canonical_object_path(nearby_obj.get("path"))
            if not isinstance(path, str) or _workspace_root_like_path(path):
                continue
            mechanisms = [item for item in (nearby_obj.get("interactionMechanisms") if isinstance(nearby_obj.get("interactionMechanisms"), list) else []) if isinstance(item, str)]
            position = _position_from_value(nearby_obj.get("position"))
            candidate = _upsert_pickup_candidate(path, nearby_obj.get("class") if isinstance(nearby_obj.get("class"), str) else None, mechanisms, position, "nearby-world", supporting_event=event)
            if candidate is None:
                continue

            candidate["observedInteractions"] += 1
            if meaningful_count > 0:
                candidate["stateLinkedOutcomes"] += 1

            before_position = _position_from_value((event.get("beforePositionSample") or {}).get("position") if isinstance(event.get("beforePositionSample"), dict) else None)
            action_position = _position_from_value((event.get("actionPositionSample") or {}).get("position") if isinstance(event.get("actionPositionSample"), dict) else None)
            distance = _numeric(nearby_obj.get("distanceStuds"))
            if distance is None and action_position and position:
                dx = action_position.get("x", 0.0) - position.get("x", 0.0)
                dy = action_position.get("y", 0.0) - position.get("y", 0.0)
                dz = action_position.get("z", 0.0) - position.get("z", 0.0)
                distance = math.sqrt(dx * dx + dy * dy + dz * dz)

            approached = isinstance(distance, (int, float)) and float(distance) <= 24.0
            interaction_observed = control_type.startswith("ProximityPrompt.") or control_type.startswith("ClickDetector.") or control_type.startswith("Tool.") or control_type.startswith("GuiButton.") or control_type.startswith("InputBegan.MouseButton")
            gameplay_state_changed = meaningful_count > 0
            correlated = approached and interaction_observed and gameplay_state_changed
            corroborated = correlated and (len(state_summary.get("impacts") or []) >= 2 or bool(event.get("clientStateCorroborated") is True))

            observation_id = "pickup-observation-" + hashlib.sha256(f"{path}|{sequence}|{nearby_idx}|{elapsed}".encode("utf-8")).hexdigest()[:14]
            observation = {
                "observationId": observation_id,
                "candidateId": candidate["candidateId"],
                "instancePath": path,
                "sessionElapsedSeconds": round(float(elapsed), 4) if isinstance(elapsed, (int, float)) else None,
                "interactionSequence": sequence,
                "transactionId": tx_id,
                "controlType": control_type,
                "playerPositionBefore": before_position,
                "playerPositionAtAction": action_position,
                "candidatePosition": position,
                "distanceStuds": round(float(distance), 4) if isinstance(distance, (int, float)) else None,
                "characterOrientationAtAction": _normalize_orientation(event.get("characterOrientationAtAction")),
                "cameraOrientationAtAction": _normalize_orientation(event.get("cameraOrientationAtAction")),
                "cameraCharacterHeadingDeltaDegrees": _numeric(event.get("cameraCharacterHeadingDeltaDegrees")),
                "relevantInputEvents": [control_type],
                "collectionMechanismEvidence": sorted(set((mechanisms or []) + (["pointer-input"] if control_type.startswith("InputBegan.MouseButton") else []))),
                "objectStateBeforeAfterObserved": False,
                "approached": approached,
                "interactionObserved": interaction_observed,
                "gameplayStateChanged": gameplay_state_changed,
                "stateDeltaImpacts": (state_summary.get("impacts") or [])[:12],
                "temporallyCorrelated": correlated,
                "multiSignalCorroborated": corroborated,
                "verificationTier": (
                    "multi-signal-corroborated" if corroborated
                    else "temporally-correlated" if correlated
                    else "interaction-or-approach-observed" if (approached or interaction_observed)
                    else "candidate-only"
                ),
                "missingEvidence": [
                    item
                    for item in (
                        "No approach proximity observed" if not approached else None,
                        "No direct interaction callback observed" if not interaction_observed else None,
                        "No gameplay-relevant state change observed" if not gameplay_state_changed else None,
                        "No multi-signal corroboration yet" if not corroborated else None,
                    )
                    if item
                ],
            }
            pickup_collection_observations.append(observation)

            relationship = {
                "relationshipId": "pickup-outcome-" + hashlib.sha256(f"{observation_id}|{candidate['candidateId']}".encode("utf-8")).hexdigest()[:14],
                "candidateId": candidate["candidateId"],
                "observationId": observation_id,
                "interactionSequence": sequence,
                "transactionId": tx_id,
                "stateDeltaImpacts": (state_summary.get("impacts") or [])[:12],
                "verification": {
                    "candidateDiscovered": True,
                    "playerApproached": approached,
                    "contactOrInteractionObserved": interaction_observed,
                    "objectStateChanged": False,
                    "gameplayStateChanged": gameplay_state_changed,
                    "stateChangeCorrelated": correlated,
                    "multiSignalCorroborated": corroborated,
                    "repeatedCollectionValidated": False,
                    "causalityProven": False,
                },
                "status": (
                    "corroborated" if corroborated
                    else "temporally-correlated" if correlated
                    else "observed-no-outcome"
                ),
                "missingEvidence": observation["missingEvidence"],
            }
            pickup_outcome_relationships.append(relationship)

    # Candidate confidence scoring and registry finalization.
    pickup_candidate_registry: list[dict[str, Any]] = []
    for path, candidate in sorted(pickup_candidates_by_path.items(), key=lambda item: item[0])[:max_pickup_candidates]:
        mechanisms = sorted(set(item for item in candidate.get("collectionMechanisms", []) if isinstance(item, str)))
        positions = [item for item in candidate.get("positions", []) if isinstance(item, dict)]
        representative_position = positions[-1] if positions else None

        score = float(candidate.get("nameScore") or 0.0)
        score += min(3.0, len(mechanisms) * 0.9)
        score += min(2.0, float(candidate.get("observedInteractions") or 0) * 0.2)
        score += min(2.5, float(candidate.get("stateLinkedOutcomes") or 0) * 0.45)
        if any(token in path.lower() for token in _DECORATIVE_PATH_TOKENS):
            score -= 1.8
        if _workspace_root_like_path(path):
            score -= 5.0
        score = max(0.0, min(0.99, score / 6.5))

        if score < 0.22 and len(mechanisms) == 0 and candidate.get("pickupCategory") == "unknown":
            continue

        if score >= 0.75:
            level = "high"
        elif score >= 0.45:
            level = "medium"
        else:
            level = "low"

        # Movement inference from position variance.
        moving = False
        if len(positions) >= 2:
            xs = [_numeric(item.get("x")) for item in positions if _numeric(item.get("x")) is not None]
            ys = [_numeric(item.get("y")) for item in positions if _numeric(item.get("y")) is not None]
            zs = [_numeric(item.get("z")) for item in positions if _numeric(item.get("z")) is not None]
            if xs and ys and zs:
                spread = (max(xs) - min(xs)) + (max(ys) - min(ys)) + (max(zs) - min(zs))
                moving = spread >= 3.2

        pickup_candidate_registry.append({
            "candidateId": candidate["candidateId"],
            "instancePath": path,
            "class": candidate.get("class"),
            "pickupCategory": candidate.get("pickupCategory") or _pickup_category_from_path(path),
            "worldContexts": sorted(item for item in candidate.get("worldContexts", set()) if isinstance(item, str))[:8],
            "currentWorldCoordinates": representative_position,
            "positionConfidence": "observed" if representative_position else "unknown",
            "firstObservedSessionElapsedSeconds": round(float(candidate["firstObservedElapsed"]), 4) if isinstance(candidate.get("firstObservedElapsed"), (int, float)) else None,
            "lastObservedSessionElapsedSeconds": round(float(candidate["lastObservedElapsed"]), 4) if isinstance(candidate.get("lastObservedElapsed"), (int, float)) else None,
            "availabilityStatus": "observed" if isinstance(candidate.get("lastObservedElapsed"), (int, float)) else "unknown",
            "moving": moving,
            "appearsToRespawn": False,
            "collectionMechanisms": mechanisms,
            "candidateConfidence": {
                "score": round(score, 4),
                "level": level,
                "supportingSignals": [
                    "pickup-like-path-token" if float(candidate.get("nameScore") or 0.0) > 0 else "",
                    "interaction-mechanism-observed" if len(mechanisms) > 0 else "",
                    "state-outcome-linked" if (candidate.get("stateLinkedOutcomes") or 0) > 0 else "",
                ],
            },
            "supportingEvidenceIds": sorted(set(candidate.get("supportingEvidenceIds", [])))[:40],
            "uncertainty": [
                item
                for item in (
                    "No direct interaction mechanism observed" if len(mechanisms) == 0 else None,
                    "No gameplay state impact yet linked" if (candidate.get("stateLinkedOutcomes") or 0) <= 0 else None,
                )
                if item
            ],
        })

    pickup_candidate_registry.sort(key=lambda item: (-(item.get("candidateConfidence") or {}).get("score", 0.0), item.get("instancePath") or ""))

    # Spawn-location registry groups candidate positions into reusable location points.
    spawn_registry_map: dict[str, dict[str, Any]] = {}
    for candidate in pickup_candidate_registry[:4000]:
        position = candidate.get("currentWorldCoordinates") if isinstance(candidate.get("currentWorldCoordinates"), dict) else None
        if not position:
            continue
        world = (candidate.get("worldContexts") or [None])[0]
        key = "|".join([
            str(world or "world:unknown"),
            candidate.get("pickupCategory") or "unknown",
            str(round(float(position.get("x", 0.0)), 1)),
            str(round(float(position.get("y", 0.0)), 1)),
            str(round(float(position.get("z", 0.0)), 1)),
        ])
        location_id = "pickup-location-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
        bucket = spawn_registry_map.setdefault(location_id, {
            "spawnLocationId": location_id,
            "worldAreaIdentity": world,
            "pickupCategory": candidate.get("pickupCategory"),
            "representativeCoordinates": position,
            "candidateIds": [],
            "availabilityStatus": "unknown",
            "spawnObservations": 0,
            "despawnObservations": 0,
            "reappearancesObserved": 0,
            "respawnEvidence": {
                "status": "insufficient-evidence",
                "estimatedIntervalSeconds": None,
            },
        })
        bucket["candidateIds"].append(candidate.get("candidateId"))
        bucket["spawnObservations"] += 1
        if candidate.get("availabilityStatus") == "observed":
            bucket["availabilityStatus"] = "observed"

    pickup_spawn_location_registry = list(spawn_registry_map.values())

    candidate_to_spawn: dict[str, str] = {}
    for item in pickup_spawn_location_registry:
        for candidate_id in item.get("candidateIds") or []:
            if isinstance(candidate_id, str):
                candidate_to_spawn[candidate_id] = item.get("spawnLocationId")

    for observation in pickup_collection_observations:
        candidate_id = observation.get("candidateId")
        if isinstance(candidate_id, str):
            observation["spawnLocationId"] = candidate_to_spawn.get(candidate_id)

    for relationship in pickup_outcome_relationships:
        candidate_id = relationship.get("candidateId")
        if isinstance(candidate_id, str):
            relationship["spawnLocationId"] = candidate_to_spawn.get(candidate_id)

    # Repeated-validation signal for same candidate with multiple corroborated outcomes.
    corroborated_by_candidate: dict[str, int] = {}
    for relationship in pickup_outcome_relationships:
        candidate_id = relationship.get("candidateId")
        verification = relationship.get("verification") if isinstance(relationship.get("verification"), dict) else {}
        if isinstance(candidate_id, str) and verification.get("multiSignalCorroborated") is True:
            corroborated_by_candidate[candidate_id] = corroborated_by_candidate.get(candidate_id, 0) + 1
    for relationship in pickup_outcome_relationships:
        candidate_id = relationship.get("candidateId")
        verification = relationship.get("verification") if isinstance(relationship.get("verification"), dict) else {}
        if isinstance(candidate_id, str) and corroborated_by_candidate.get(candidate_id, 0) >= 2:
            verification["repeatedCollectionValidated"] = True
            relationship["status"] = "repeatedly-validated-observational"

    max_observed_elapsed = max(
        [_numeric(item.get("sessionElapsedSeconds")) for item in pickup_collection_observations if _numeric(item.get("sessionElapsedSeconds")) is not None] or [0.0]
    )

    pickup_navigation_candidates: list[dict[str, Any]] = []
    for location in pickup_spawn_location_registry[:3000]:
        location_id = location.get("spawnLocationId") if isinstance(location.get("spawnLocationId"), str) else None
        if not location_id:
            continue
        candidate_ids = [item for item in (location.get("candidateIds") or []) if isinstance(item, str)]
        location_observations = [
            item for item in pickup_collection_observations
            if isinstance(item, dict) and item.get("spawnLocationId") == location_id
        ]
        location_outcomes = [
            item for item in pickup_outcome_relationships
            if isinstance(item, dict) and item.get("spawnLocationId") == location_id
        ]

        last_elapsed = max(
            [_numeric(item.get("sessionElapsedSeconds")) for item in location_observations if _numeric(item.get("sessionElapsedSeconds")) is not None] or [None]
        )
        stale = isinstance(last_elapsed, (int, float)) and (max_observed_elapsed - float(last_elapsed) > 22.0)
        corroborated = sum(
            1 for item in location_outcomes
            if ((item.get("verification") if isinstance(item.get("verification"), dict) else {}).get("multiSignalCorroborated") is True)
        )
        repeated_validated = sum(
            1 for item in location_outcomes
            if ((item.get("verification") if isinstance(item.get("verification"), dict) else {}).get("repeatedCollectionValidated") is True)
        )

        blockers = []
        if len(location_observations) == 0:
            blockers.append("No collection observation captured for this pickup location yet")
        if corroborated <= 0:
            blockers.append("No multi-signal pickup outcome corroboration yet")
        if stale:
            blockers.append("Pickup location may be stale relative to latest observations")

        pickup_navigation_candidates.append({
            "navigationCandidateId": "pickup-navigation-" + hashlib.sha256(location_id.encode("utf-8")).hexdigest()[:12],
            "spawnLocationId": location_id,
            "candidateIds": candidate_ids,
            "pickupCategory": location.get("pickupCategory"),
            "worldAreaIdentity": location.get("worldAreaIdentity"),
            "targetCoordinates": location.get("representativeCoordinates"),
            "locationFreshness": "stale" if stale else "current-or-recent",
            "collectionMechanisms": sorted({
                mechanism
                for candidate in pickup_candidate_registry
                if candidate.get("candidateId") in candidate_ids
                for mechanism in (candidate.get("collectionMechanisms") or [])
                if isinstance(mechanism, str)
            }),
            "observedOutcomeStatus": {
                "observationCount": len(location_observations),
                "corroboratedOutcomeCount": corroborated,
                "repeatedValidationCount": repeated_validated,
                "outcomeVerified": corroborated > 0,
                "repeatedlyValidated": repeated_validated > 0,
            },
            "navigationReadiness": {
                "status": "ready-with-observed-collection-corroboration" if corroborated > 0 and not stale else "observed-needs-validation",
                "blockers": blockers,
                "limitations": [
                    "Coordinate evidence is client-observed and not guaranteed navigation mesh path",
                    "Collection still requires live validation for current server state and availability",
                ],
            },
        })

    pickup_discovery_quality_metrics = {
        "pickupCandidates": {
            "total": len(pickup_candidate_registry),
            "highConfidence": sum(1 for item in pickup_candidate_registry if ((item.get("candidateConfidence") or {}).get("level") == "high")),
            "withMechanisms": sum(1 for item in pickup_candidate_registry if len(item.get("collectionMechanisms") or []) > 0),
            "withObservedStateOutcomes": sum(1 for item in pickup_candidate_registry if "No gameplay state impact yet linked" not in (item.get("uncertainty") or [])),
        },
        "pickupSpawnLocations": {
            "total": len(pickup_spawn_location_registry),
            "observed": sum(1 for item in pickup_spawn_location_registry if item.get("availabilityStatus") == "observed"),
        },
        "pickupCollectionObservations": {
            "total": len(pickup_collection_observations),
            "approached": sum(1 for item in pickup_collection_observations if item.get("approached") is True),
            "interactionObserved": sum(1 for item in pickup_collection_observations if item.get("interactionObserved") is True),
            "gameplayStateChanged": sum(1 for item in pickup_collection_observations if item.get("gameplayStateChanged") is True),
            "temporallyCorrelated": sum(1 for item in pickup_collection_observations if item.get("temporallyCorrelated") is True),
            "multiSignalCorroborated": sum(1 for item in pickup_collection_observations if item.get("multiSignalCorroborated") is True),
        },
        "pickupOutcomes": {
            "total": len(pickup_outcome_relationships),
            "corroborated": sum(1 for item in pickup_outcome_relationships if ((item.get("verification") or {}).get("multiSignalCorroborated") is True)),
            "repeatedValidation": sum(1 for item in pickup_outcome_relationships if ((item.get("verification") or {}).get("repeatedCollectionValidated") is True)),
            "causalityProven": 0,
        },
        "pickupNavigation": {
            "candidateCount": len(pickup_navigation_candidates),
            "readyCount": sum(1 for item in pickup_navigation_candidates if ((item.get("navigationReadiness") or {}).get("status") == "ready-with-observed-collection-corroboration")),
            "staleCount": sum(1 for item in pickup_navigation_candidates if item.get("locationFreshness") == "stale"),
        },
    }

    click_link_attempts = int(_numeric(input_observation_stats.get("clickLinksAttempted")) or 0)
    click_link_matched = int(_numeric(input_observation_stats.get("clickLinksMatched")) or 0)
    click_link_missed = int(_numeric(input_observation_stats.get("clickLinksMissed")) or 0)
    click_link_missing_source = int(_numeric(input_observation_stats.get("clickLinksMissedMissingSource")) or 0)
    click_link_no_eligible = int(_numeric(input_observation_stats.get("clickLinksMissedNoEligibleCandidate")) or 0)
    if click_link_missed > 0 and click_link_missing_source == 0 and click_link_no_eligible == 0:
        click_captures_recorded = int(_numeric(input_observation_stats.get("clickCapturesRecorded")) or 0)
        click_capture_attempts = int(_numeric(input_observation_stats.get("clickCaptureAttempts")) or 0)
        click_capture_failures = int(_numeric(input_observation_stats.get("clickCaptureFailures")) or 0)
        if click_captures_recorded == 0 and (click_capture_attempts == 0 or click_capture_failures >= click_capture_attempts):
            click_link_missing_source = click_link_missed


    spatial_quality_metrics = {
        "playerPositionSamples": {
            "total": len(position_history),
            "withCoordinates": sum(1 for item in position_history if isinstance(item.get("position"), dict)),
            "invalid": sum(1 for item in position_history if item.get("positionValid") is False),
            "interpolated": sum(1 for item in position_history if item.get("interpolated") is True),
        },
        "eventPositionSnapshots": {
            "total": len(event_snapshots),
            "withCoordinates": sum(1 for item in event_snapshots if isinstance(item.get("position"), dict)),
            "sampled": sum(1 for item in event_snapshots if item.get("sampled") is True),
            "interpolated": sum(1 for item in event_snapshots if item.get("interpolated") is True),
            "linkedToInteractions": sum(1 for item in event_snapshots if isinstance(item.get("interactionSequence"), int)),
        },
        "cursorObservations": {
            "total": len(cursor_observation_history),
            "withScreenCoordinates": sum(
                1 for item in cursor_observation_history
                if isinstance(item.get("screen"), dict)
                and _numeric((item.get("screen") or {}).get("x")) is not None
                and _numeric((item.get("screen") or {}).get("y")) is not None
            ),
            "withNormalizedViewport": sum(
                1 for item in cursor_observation_history
                if isinstance(item.get("normalizedViewport"), dict)
                and _numeric((item.get("normalizedViewport") or {}).get("x")) is not None
                and _numeric((item.get("normalizedViewport") or {}).get("y")) is not None
            ),
        },
        "clickTargetDiscovery": {
            "total": len(click_target_observations),
            "withTopmostGuiTarget": sum(1 for item in click_target_observations if isinstance(item.get("topmostGuiTarget"), dict)),
            "withRaycastTarget": sum(1 for item in click_target_observations if isinstance(item.get("raycastTarget"), dict)),
            "highConfidence": sum(
                1
                for item in click_target_observations
                if isinstance(item.get("targetIdentificationConfidence"), dict)
                and (item.get("targetIdentificationConfidence") or {}).get("level") == "high"
            ),
        },
        "clickOutcomeCorrelation": {
            "total": len(click_outcome_relationships),
            "callbackObserved": sum(1 for item in click_outcome_relationships if item.get("interactionCallbackObserved") is True),
            "stateAssociated": sum(1 for item in click_outcome_relationships if item.get("stateChangeTemporallyAssociated") is True),
            "meaningfulOutcomeObserved": sum(1 for item in click_outcome_relationships if item.get("meaningfulGameplayOutcomeObserved") is True),
            "corroborated": sum(1 for item in click_outcome_relationships if item.get("outcomeCorroborated") is True),
            "liveValidated": sum(1 for item in click_outcome_relationships if item.get("reproduciblyLiveValidated") is True),
            "missAttribution": {
                "linkAttempts": click_link_attempts,
                "linkMatched": click_link_matched,
                "linkMissed": click_link_missed,
                "missingSource": click_link_missing_source,
                "noEligibleCandidate": click_link_no_eligible,
                "reasonCounts": input_observation_stats.get("clickLinkMissReasonCounts") if isinstance(input_observation_stats.get("clickLinkMissReasonCounts"), dict) else {},
            },
        },
        "inputGestureIntent": {
            "total": len(input_gesture_observations),
            "clickCandidates": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("clickCandidate") is True)),
            "cameraDragCandidates": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("cameraDragCandidate") is True)),
            "heldInputCandidates": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("heldInputCandidate") is True)),
            "guiInteractionCandidates": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("guiInteractionCandidate") is True)),
            "worldInteractionCandidates": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("worldInteractionCandidate") is True)),
            "ambiguousInputs": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("ambiguousInput") is True)),
            "likelyCameraMovements": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("likelyCameraMovement") is True)),
            "likelyGameplayInteractions": sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("likelyGameplayInteraction") is True)),
            "worldRaycastOnlySignals": sum(
                1
                for item in input_gesture_observations
                if ((((item.get("intent") or {}).get("targetAndOutcomeSignals") or {}).get("worldRaycastOnly")) is True)
            ),
            "cameraMovementToGameplayRatio": (
                round(
                    sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("likelyCameraMovement") is True))
                    / max(1, sum(1 for item in input_gesture_observations if ((item.get("intent") or {}).get("likelyGameplayInteraction") is True))),
                    4,
                )
                if len(input_gesture_observations) > 0
                else None
            ),
        },

        "orientationTracking": {
            "characterSamples": len(character_orientation_samples),
            "cameraSamples": len(camera_orientation_samples),
            "characterHeadingAvailable": sum(1 for item in character_orientation_samples if _numeric(item.get("headingDegrees")) is not None),
            "cameraHeadingAvailable": sum(1 for item in camera_orientation_samples if _numeric(item.get("headingDegrees")) is not None),
            "cameraCharacterHeadingDeltaAvailable": sum(
                1
                for item in camera_orientation_samples
                if _numeric(item.get("cameraToCharacterHeadingDeltaDegrees")) is not None
            ),
        },
        "locationClustering": {
            "functionalLocationCount": len(location_registry),
            "physicalDestinationCount": len(physical_destination_registry),
            "destinationMerges": max(0, len(location_registry) - len(physical_destination_registry)),
            "duplicateObservationsMerged": max(0, len([item for item in events if isinstance(item, dict)]) - len(location_registry)),
            "interactionLinkedLocations": sum(1 for item in location_registry if (item.get("supportingInteractionCount") or 0) > 0),
            "outcomeLinkedLocations": sum(1 for item in location_registry if item.get("outcomeLinked") is True),
            "multiWorkflowDestinationCount": sum(1 for item in physical_destination_registry if len(item.get("associatedWorkflows") or []) > 1),
            "destinationWorkflowCount": len(destination_workflows),
            "spatialActionOutcomeRelationshipCount": len(spatial_relationships),
            "navigationCandidateCount": len(navigation_candidates),
            "actionableNavigationCandidates": actionable_navigation_candidates,
            "navigationCandidatesReady": ready_navigation_candidates,
            "liveValidatedDestinations": live_validated_destinations,
            "gameplayVerifiedDestinations": gameplay_verified_destinations,
        },
        "nearbyObjectRelevance": {
            "actionableCandidateCount": actionable_nearby_candidates,
            "uncertainCandidateCount": uncertain_nearby_candidates,
            "rejectedCandidateCount": rejected_nearby_candidates,
        },
        "coverage": {
            "interactionToLocationCoverage": (
                round(
                    len({item.get("interactionSequence") for item in spatial_relationships if isinstance(item.get("interactionSequence"), int)}) / len(events),
                    4,
                )
                if len(events) > 0
                else None
            ),
            "coordinateCoverage": (
                round(
                    min(
                        1.0,
                        sum(1 for item in spatial_relationships if isinstance(item.get("atActionPosition"), dict)) / len(events),
                    ),
                    4,
                )
                if len(events) > 0
                else None
            ),
        },
        "missingLocationEvidence": {
            "count": sum(1 for item in location_registry if len(item.get("missingEvidence") or []) > 0),
            "examples": [
                {
                    "locationId": item.get("id"),
                    "missingEvidence": item.get("missingEvidence"),
                }
                for item in location_registry
                if len(item.get("missingEvidence") or []) > 0
            ][:12],
        },
        "evidenceBoundaries": {
            "workspaceActiveObjectsOnly": True,
            "replicatedStorageTemplatesExcluded": True,
            "causalityProven": False,
            "serverAuthorityVerified": False,
        },
        "warnings": [
            warning
            for warning in (
                "No valid player position history available" if len(position_history) == 0 else None,
                "No event-linked position snapshots with coordinates" if sum(1 for item in event_snapshots if isinstance(item.get("position"), dict)) == 0 else None,
                "No cursor observations captured" if len(cursor_observation_history) == 0 else None,
                "No click-target observations captured" if len(click_target_observations) == 0 else None,
                "No orientation samples captured" if len(character_orientation_samples) == 0 and len(camera_orientation_samples) == 0 else None,
                "No functional locations could be clustered from current evidence" if len(location_registry) == 0 else None,
            )
            if warning
        ],
    }

    systems_list.sort(key=lambda item: (-item["confidence"]["score"], -item["observedInteractionEvents"], item["id"]))

    state_signals = []
    for value in sorted(state_registry.values(), key=lambda item: (-item["changes"], -item["increases"], item["key"])):
        confidence_score = min(1.0, (value["changes"] / 8.0) + (value["increases"] / 8.0))
        state_signals.append({
            "id": value["id"],
            "key": value["key"],
            "name": value["name"],
            "source": value["source"],
            "category": value["category"],
            "changes": value["changes"],
            "increases": value["increases"],
            "decreases": value["decreases"],
            "lastBefore": value["lastBefore"],
            "lastAfter": value["lastAfter"],
            "confidence": {
                "score": round(confidence_score, 3),
                "level": _confidence_level(confidence_score),
            },
            "sampleActions": value["sampleActions"],
            "limitations": [
                "Temporal observation only",
                "No server-authority proof",
            ],
        })

    workflow_node_items = []
    for item in sorted(workflow_nodes.values(), key=lambda value: (-value["activationCount"], value["path"])):
        workflow_node_items.append({
            "id": item["id"],
            "path": item["path"],
            "activationCount": item["activationCount"],
            "controlTypes": sorted(item["controlTypes"]),
            "featureCandidates": sorted(item["featureCandidates"]),
        })

    workflow_edge_items = []
    for (left, right), count in sorted(workflow_edges.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
        workflow_edge_items.append({
            "from": left,
            "to": right,
            "observedTransitions": count,
        })

    mechanisms = []
    mechanism_map = {
        "Tool.Activated": "tool-activation",
        "GuiButton.Activated": "gui-button-activation",
        "ProximityPrompt.Triggered": "proximity-prompt-trigger",
        "InputBegan.Keyboard": "keyboard-input",
        "InputBegan.MouseButton1": "pointer-input",
    }
    for control_type, count in sorted(control_type_counts.items(), key=lambda item: (-item[1], item[0])):
        mechanisms.append({
            "kind": mechanism_map.get(control_type, control_type.lower().replace(".", "-")),
            "controlType": control_type,
            "observedCount": count,
            "confidence": "observed",
            "limitations": ["Observed client execution path only"],
        })

    contamination_signals: list[dict[str, Any]] = []
    joined_paths = "\n".join(sorted(unique_paths)).lower()
    joined_states = "\n".join(item["key"].lower() for item in state_signals)
    requested_text = (requested_capability or "").lower()
    game_name = (payload.get("gameName") or "") if isinstance(payload.get("gameName"), str) else ""
    normalized_game = game_name.lower()
    for fixture_name, tokens in _DISCOVERY_FIXTURE_TOKENS.items():
        if fixture_name.replace("_", " ") in normalized_game:
            continue
        hits = [token for token in tokens if token in joined_paths or token in joined_states or token in requested_text]
        if hits:
            contamination_signals.append({
                "fixture": fixture_name,
                "tokenHits": sorted(set(hits)),
                "severity": "review",
            })

    relationship_with_outcome = sum(1 for item in relationships if len(item["stateBeforeAfter"]) > 0)
    workflow_transaction_count = len(workflow_transactions)
    workflow_complete_transactions = sum(1 for events_in_tx in workflow_transactions.values() if len(events_in_tx) >= 2)

    distinct_mechanics = len(systems_list)
    object_count = len(objects)
    if object_count == 0 and type(baseline_context.get("objectCount")) is int:
        object_count = int(baseline_context.get("objectCount"))
    interaction_target_count = len(unique_paths)
    actionable_systems = sum(1 for item in systems_list if item["actionableWorkflowDiscovered"])

    quality_metrics = {
        "distinctMechanicsIdentified": distinct_mechanics,
        "objectCoverage": {
            "objectCount": object_count,
            "uniqueInteractionTargets": interaction_target_count,
            "interactionTargetToObjectRatio": round(interaction_target_count / object_count, 4) if object_count > 0 else None,
        },
        "interactionCoverage": {
            "totalObservedInteractions": len(events),
            "interactionsWithStateDeltas": events_with_state_delta,
            "interactionsWithGuiTransitions": events_with_gui_transition,
            "attributedInteractionCount": attributed_events,
        },
        "actionOutcomeRelationships": {
            "totalRelationships": len(relationships),
            "relationshipsWithOutcomeSignals": relationship_with_outcome,
        },
        "resolvableObjectPaths": {
            "pathIdentityObserved": path_identity_total,
            "pathIdentityResolved": path_identity_resolved,
            "resolutionRatio": round(path_identity_resolved / path_identity_total, 4) if path_identity_total > 0 else None,
        },
        "workflowCompleteness": {
            "transactionCount": workflow_transaction_count,
            "multiStepTransactions": workflow_complete_transactions,
            "multiStepRatio": round(workflow_complete_transactions / workflow_transaction_count, 4) if workflow_transaction_count > 0 else None,
            "graphNodeCount": len(workflow_node_items),
            "graphEdgeCount": len(workflow_edge_items),
        },
        "evidenceConfidence": {
            "actionableSystemCount": actionable_systems,
            "systemsSufficientForGeneration": sum(1 for item in systems_list if item["evidenceSufficientForGeneration"]),
            "highConfidenceSystems": sum(1 for item in systems_list if item["confidence"]["level"] == "high"),
        },
        "spatialDiscovery": spatial_quality_metrics,
        "pickupDiscovery": pickup_discovery_quality_metrics,
        "unsupportedAssumptions": {
            "count": 0,
            "notes": ["No server-side capability inference is treated as proven"],
        },
        "crossGameContamination": {
            "signalCount": len(contamination_signals),
            "signals": contamination_signals,
        },
    }

    uncertainties: list[str] = [
        "Temporal correlation does not prove server-side causality",
        "Client-visible state does not prove remote invocation authority",
    ]
    claims = {
        "runtimeVerified": bool(payload.get("runtimeVerified") is True),
        "gameplayVerified": bool(payload.get("gameplayVerified") is True),
        "causalityProven": bool(payload.get("causalityProven") is True),
        "serverAuthorityVerified": bool(payload.get("serverAuthorityVerified") is True),
        "sourceAuthenticityVerified": bool(payload.get("sourceAuthenticityVerified") is True),
    }
    for key, value in claims.items():
        if not value:
            uncertainties.append(f"{key} is not verified")

    recommended_steps: list[str] = []
    if actionable_systems == 0:
        recommended_steps.append("Record interactions that activate actionable controls for candidate systems")
    if relationship_with_outcome == 0:
        recommended_steps.append("Capture additional runs with clear pre/post progression state changes")
    if workflow_complete_transactions == 0:
        recommended_steps.append("Capture complete multi-step GUI workflows using workflow recording")
    if len(pickup_candidate_registry) == 0:
        recommended_steps.append("Capture world-space movement near collectible candidates to seed pickup discovery")
    if sum(
        1
        for item in pickup_outcome_relationships
        if ((item.get("verification") or {}).get("multiSignalCorroborated") is True)
    ) == 0:
        recommended_steps.append("Perform repeated pickup interactions with clear pre/post currency or inventory deltas")
    if len(contamination_signals) > 0:
        recommended_steps.append("Review fixture-token overlap to rule out cross-game heuristic leakage")

    if not recommended_steps:
        recommended_steps.append("Run targeted validation for highest-confidence mechanics in live gameplay")

    return {
        "schemaVersion": "30.8.universal-discovery-report.1",
        "gameIdentity": {
            "placeId": payload.get("placeId"),
            "gameId": payload.get("gameId"),
            "gameName": payload.get("gameName"),
            "scanId": payload.get("scanId"),
            "baselineScanId": payload.get("baselineScanId"),
            "snapshotId": payload.get("snapshotId"),
            "sessionId": payload.get("sessionId"),
        },
        "scanMetadata": {
            "inspectorSchemaVersion": payload.get("schemaVersion"),
            "exportKind": payload.get("exportKind"),
            "integrity": payload.get("integrity") if isinstance(payload.get("integrity"), dict) else {},
            "sourceDiagnostics": payload.get("sourceDiagnostics") if isinstance(payload.get("sourceDiagnostics"), dict) else {},
            "sourceProvenance": payload.get("sourceProvenance") if isinstance(payload.get("sourceProvenance"), dict) else {},
            "requestedCapability": requested_capability,
            "baselineContext": {
                "scanId": baseline_context.get("scanId"),
                "placeId": baseline_context.get("placeId"),
                "partCount": baseline_context.get("partCount"),
                "objectCount": baseline_context.get("objectCount"),
                "workspaceObjectCount": baseline_context.get("workspaceObjectCount"),
                "replicatedStorageObjectCount": baseline_context.get("replicatedStorageObjectCount"),
                "actionableWorldObjectCount": len(baseline_actionable_index),
            },
            "baselineArchiveValidation": {
                "sourceArchiveCount": baseline_archive_validation.get("sourceArchiveCount"),
                "partCount": baseline_archive_validation.get("partCount"),
                "jsonFiles": baseline_archive_validation.get("jsonFiles"),
                "manifestFiles": baseline_archive_validation.get("manifestFiles"),
                "localArchiveComplete": baseline_archive_validation.get("localArchiveComplete"),
                "manifestUploadedPartsObserved": baseline_archive_validation.get("manifestUploadedPartsObserved"),
                "receiverAcknowledgementGap": baseline_archive_validation.get("receiverAcknowledgementGap"),
                "receiverAcknowledgementComplete": baseline_archive_validation.get("receiverAcknowledgementComplete"),
                "combinedArchiveSha256": baseline_archive_validation.get("combinedArchiveSha256"),
            },
        },
        "objectAndInteractionInventory": {
            "objectsObserved": object_count,
            "interactionEventsObserved": len(events),
            "controlTypes": control_type_counts,
            "actionKinds": action_kind_counts,
            "featureCandidates": feature_candidate_counts,
            "uniqueInteractionTargets": sorted(unique_paths)[:250],
        },
        "playerProgressionRegistry": {
            "stateSignals": state_signals,
            "totalStateSignals": len(state_signals),
        },
        "discoveredGameplaySystems": systems_list,
        "candidateActionOutcomeRelationships": relationships[:240],
        "playerPositionHistory": position_history[:900],
        "eventPositionSnapshots": event_snapshots[:1400],
        "cursorObservationHistory": cursor_observation_history[:1200],
        "clickTargetObservations": click_target_observations[:900],
        "clickOutcomeRelationships": click_outcome_relationships[:900],
        "inputGestureObservations": input_gesture_observations[:900],
        "characterOrientationSamples": character_orientation_samples[:1400],
        "cameraOrientationSamples": camera_orientation_samples[:1400],
        "cursorClickOrientationSchemas": {
            "cursorObservation": "30.6.cursor-observation.1",
            "clickTargetObservation": "30.6.click-target-observation.1",
            "clickOutcomeRelationship": "30.6.click-outcome-relationship.1",
            "inputGestureObservation": "30.6.input-gesture-observation.1",
            "characterOrientation": "30.6.character-orientation.1",
            "cameraOrientation": "30.6.camera-orientation.1",
        },
        "functionalLocationRegistry": location_registry,
        "physicalDestinationRegistry": physical_destination_registry,
        "destinationWorkflows": destination_workflows[:260],
        "spatialActionOutcomeRelationships": spatial_relationships[:260],
        "locationNavigationCandidates": location_navigation_candidates[:260],
        "navigationCandidates": navigation_candidates,
        "pickupCandidateRegistry": pickup_candidate_registry[:3200],
        "pickupSpawnLocationRegistry": pickup_spawn_location_registry[:3200],
        "pickupCollectionObservations": pickup_collection_observations[:4200],
        "pickupOutcomeRelationships": pickup_outcome_relationships[:4200],
        "pickupNavigationCandidates": pickup_navigation_candidates[:3200],
        "pickupDiscoveryQualityMetrics": pickup_discovery_quality_metrics,
        "spatialDiscovery": {
            "status": "captured" if len(event_snapshots) > 0 or len(position_history) > 0 else "not-captured",
            "workspaceActiveObjectsOnly": True,
            "replicatedStorageTemplatesExcluded": True,
            "interpolationPolicy": "sampled-only-no-interpolated-positions",
            "continuityPolicy": "character-generation-boundaries-preserved",
            "notes": [
                "Spatial inference is evidence-driven and bounded to observed client-visible data",
                "No server-authority assumptions are made from spatial proximity alone",
            ],
        },
        "spatialDiscoveryQualityMetrics": spatial_quality_metrics,
        "guiWorkflowGraph": {
            "nodes": workflow_node_items,
            "edges": workflow_edge_items,
            "transactionCount": workflow_transaction_count,
        },
        "requirementsAndEligibilityEvidence": {
            "samples": requirements_samples,
            "sampleCount": len(requirements_samples),
        },
        "worldInteractionCandidates": [
            {
                "path": item["path"],
                "controlTypes": sorted(item["controlTypes"]),
                "observedInteractions": item["observedInteractions"],
            }
            for item in sorted(world_candidates.values(), key=lambda value: (-value["observedInteractions"], value["path"]))[:120]
        ],
        "knownExecutableInteractionMechanisms": mechanisms,
        "uncertaintiesAndValidation": {
            "uncertainties": sorted(set(uncertainties)),
            "recommendedValidationSteps": recommended_steps,
            "claims": claims,
        },
        "qualityMetrics": quality_metrics,
        "crossGameIsolation": {
            "fixturesReviewed": sorted(_DISCOVERY_FIXTURE_TOKENS.keys()),
            "potentialContaminationSignals": contamination_signals,
        },
        "generationLayerContext": {
            "contractSchemaVersion": generation_contract.get("schemaVersion") if isinstance(generation_contract, dict) else None,
            "generatedFeatureIds": generation_contract.get("generatedFeatureIds") if isinstance(generation_contract, dict) else [],
            "generationOptional": True,
            "note": "Discovery export is produced independently of generated automation availability",
        },
    }


def _render_universal_discovery_summary(report: dict[str, Any]) -> str:
    identity = report.get("gameIdentity") if isinstance(report.get("gameIdentity"), dict) else {}
    metrics = report.get("qualityMetrics") if isinstance(report.get("qualityMetrics"), dict) else {}
    systems = report.get("discoveredGameplaySystems") if isinstance(report.get("discoveredGameplaySystems"), list) else []
    spatial_metrics = (metrics.get("spatialDiscovery") if isinstance(metrics, dict) and isinstance(metrics.get("spatialDiscovery"), dict) else {})
    pickup_metrics = (metrics.get("pickupDiscovery") if isinstance(metrics, dict) and isinstance(metrics.get("pickupDiscovery"), dict) else {})
    uncertainties = ((report.get("uncertaintiesAndValidation") or {}).get("uncertainties") or []) if isinstance(report.get("uncertaintiesAndValidation"), dict) else []
    steps = ((report.get("uncertaintiesAndValidation") or {}).get("recommendedValidationSteps") or []) if isinstance(report.get("uncertaintiesAndValidation"), dict) else []

    top_system_lines = []
    for item in systems[:8]:
        if not isinstance(item, dict):
            continue
        top_system_lines.append(
            f"- {item.get('title')} | interactions={item.get('observedInteractionEvents')} | stateChanges={item.get('observedStateChanges')} | actionable={item.get('actionableWorkflowDiscovered')} | generationReady={item.get('evidenceSufficientForGeneration')} | confidence={((item.get('confidence') or {}).get('level'))}"
        )

    scan_metadata = report.get("scanMetadata") if isinstance(report.get("scanMetadata"), dict) else {}
    archive_validation = scan_metadata.get("baselineArchiveValidation") if isinstance(scan_metadata.get("baselineArchiveValidation"), dict) else {}

    lines = [
        "Lycoles Universal Discovery Summary",
        "",
        f"Schema: {report.get('schemaVersion')}",
        f"Game: {identity.get('gameName') or 'unknown'}",
        f"Place ID: {identity.get('placeId')}",
        f"Scan ID: {identity.get('scanId')}",
        "",
        "Discovery quality metrics:",
        f"- Distinct mechanics identified: {(metrics.get('distinctMechanicsIdentified') if isinstance(metrics, dict) else None)}",
        f"- Observed interactions: {(((metrics.get('interactionCoverage') or {}).get('totalObservedInteractions')) if isinstance(metrics, dict) else None)}",
        f"- Relationships with outcome signals: {((metrics.get('actionOutcomeRelationships') or {}).get('relationshipsWithOutcomeSignals') if isinstance(metrics, dict) else None)}",
        f"- Workflow transactions: {((metrics.get('workflowCompleteness') or {}).get('transactionCount') if isinstance(metrics, dict) else None)}",
        f"- Functional locations clustered: {(spatial_metrics.get('locationClustering') or {}).get('functionalLocationCount') if isinstance(spatial_metrics, dict) else None}",
        f"- Physical destinations consolidated: {(spatial_metrics.get('locationClustering') or {}).get('physicalDestinationCount') if isinstance(spatial_metrics, dict) else None}",
        f"- Destination merges applied: {(spatial_metrics.get('locationClustering') or {}).get('destinationMerges') if isinstance(spatial_metrics, dict) else None}",
        f"- Destination workflows identified: {(spatial_metrics.get('locationClustering') or {}).get('destinationWorkflowCount') if isinstance(spatial_metrics, dict) else None}",
        f"- Duplicate observations merged: {(spatial_metrics.get('locationClustering') or {}).get('duplicateObservationsMerged') if isinstance(spatial_metrics, dict) else None}",
        f"- Actionable navigation candidates: {(spatial_metrics.get('locationClustering') or {}).get('actionableNavigationCandidates') if isinstance(spatial_metrics, dict) else None}",
        f"- Navigation candidates ready: {(spatial_metrics.get('locationClustering') or {}).get('navigationCandidatesReady') if isinstance(spatial_metrics, dict) else None}",
        f"- Live-validated destinations: {(spatial_metrics.get('locationClustering') or {}).get('liveValidatedDestinations') if isinstance(spatial_metrics, dict) else None}",
        f"- Gameplay-verified destinations: {(spatial_metrics.get('locationClustering') or {}).get('gameplayVerifiedDestinations') if isinstance(spatial_metrics, dict) else None}",
        f"- Event snapshots with coordinates: {(spatial_metrics.get('eventPositionSnapshots') or {}).get('withCoordinates') if isinstance(spatial_metrics, dict) else None}",
        f"- Cursor observations captured: {(spatial_metrics.get('cursorObservations') or {}).get('total') if isinstance(spatial_metrics, dict) else None}",
        f"- Click-target observations captured: {(spatial_metrics.get('clickTargetDiscovery') or {}).get('total') if isinstance(spatial_metrics, dict) else None}",
        f"- Click outcomes corroborated: {(spatial_metrics.get('clickOutcomeCorrelation') or {}).get('corroborated') if isinstance(spatial_metrics, dict) else None}",
        f"- Input gestures captured: {(spatial_metrics.get('inputGestureIntent') or {}).get('total') if isinstance(spatial_metrics, dict) else None}",
        f"- Likely camera-movement gestures: {(spatial_metrics.get('inputGestureIntent') or {}).get('likelyCameraMovements') if isinstance(spatial_metrics, dict) else None}",
        f"- Likely gameplay-interaction gestures: {(spatial_metrics.get('inputGestureIntent') or {}).get('likelyGameplayInteractions') if isinstance(spatial_metrics, dict) else None}",
        f"- Character orientation samples: {(spatial_metrics.get('orientationTracking') or {}).get('characterSamples') if isinstance(spatial_metrics, dict) else None}",
        f"- Camera orientation samples: {(spatial_metrics.get('orientationTracking') or {}).get('cameraSamples') if isinstance(spatial_metrics, dict) else None}",
        f"- Pickup candidates discovered: {(pickup_metrics.get('pickupCandidates') or {}).get('total') if isinstance(pickup_metrics, dict) else None}",
        f"- Pickup spawn locations identified: {(pickup_metrics.get('pickupSpawnLocations') or {}).get('total') if isinstance(pickup_metrics, dict) else None}",
        f"- Pickup collection observations: {(pickup_metrics.get('pickupCollectionObservations') or {}).get('total') if isinstance(pickup_metrics, dict) else None}",
        f"- Pickup outcomes corroborated: {(pickup_metrics.get('pickupOutcomes') or {}).get('corroborated') if isinstance(pickup_metrics, dict) else None}",
        f"- Pickup navigation candidates ready: {(pickup_metrics.get('pickupNavigation') or {}).get('readyCount') if isinstance(pickup_metrics, dict) else None}",
        f"- Interaction→location coverage: {(spatial_metrics.get('coverage') or {}).get('interactionToLocationCoverage') if isinstance(spatial_metrics, dict) else None}",
        f"- Potential cross-game contamination signals: {((metrics.get('crossGameContamination') or {}).get('signalCount') if isinstance(metrics, dict) else None)}",
        "",
        "Baseline archive integrity:",
        f"- Local archive complete: {archive_validation.get('localArchiveComplete')}",
        f"- Manifest uploaded parts observed: {archive_validation.get('manifestUploadedPartsObserved')}",
        f"- Receiver acknowledgement gap: {archive_validation.get('receiverAcknowledgementGap')}",
        "",
        "Top discovered systems:",
    ]
    lines.extend(top_system_lines or ["- none identified"])
    lines.extend([
        "",
        "Uncertainties:",
    ])
    lines.extend([f"- {item}" for item in uncertainties] or ["- none"])
    lines.extend([
        "",
        "Recommended next validation steps:",
    ])
    lines.extend([f"- {item}" for item in steps] or ["- none"])
    return "\n".join(lines) + "\n"


def _write_universal_discovery_artifacts(
    payload: dict[str, Any],
    *,
    requested_capability: Optional[str],
    output_root: pathlib.Path,
    generation_contract: Optional[dict[str, Any]] = None,
    baseline_context: Optional[dict[str, Any]] = None,
    baseline_archive_validation: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    output_root = pathlib.Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    report = _build_universal_discovery_report(
        payload,
        requested_capability=requested_capability,
        generation_contract=generation_contract,
        baseline_context=baseline_context,
        baseline_archive_validation=baseline_archive_validation,
    )
    report_path = output_root / "universal-discovery-report.json"
    summary_path = output_root / "universal-discovery-summary.txt"

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    summary_path.write_text(_render_universal_discovery_summary(report), encoding="utf-8")

    return {
        "schemaVersion": report.get("schemaVersion"),
        "reportPath": str(report_path),
        "summaryPath": str(summary_path),
        "qualityMetrics": report.get("qualityMetrics"),
    }





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
) -> dict[str, Any]:
    scenario_output_root.mkdir(parents=True, exist_ok=True)
    summary_path = scenario_output_root / "observation-recovery-summary.json"

    contract = _build_observation_tool_contract(payload, requested_capability)
    discovery = _write_universal_discovery_artifacts(
        payload,
        requested_capability=requested_capability,
        output_root=scenario_output_root,
        generation_contract=contract if isinstance(contract, dict) else None,
    )

    if not isinstance(contract, dict):
        summary = {
            "schemaVersion": "117.observation-recovery-summary.6",
            "status": "generated-discovery-only",
            "generatedScriptPath": None,
            "generatedScriptKind": "none",
            "loaderTemplatePath": None,
            "contractPath": None,
            "toolPath": None,
            "primaryOutcomePath": None,
            "questRepetitionStatePathCount": 0,
            "outcomeStateKeyCount": 0,
            "statRegistryCount": 0,
            "statTrainingTargetCount": 0,
            "actionStatRelationshipCount": 0,
            "implementedFeatures": [],
            "monitoredFeatures": [],
            "excludedFeatures": [],
            "unsupportedFeatures": [],
            "discoveryReportPath": discovery.get("reportPath"),
            "discoverySummaryPath": discovery.get("summaryPath"),
            "discoveryQualityMetrics": discovery.get("qualityMetrics"),
            "claims": {
                "runtimeVerified": False,
                "gameplayVerified": False,
                "causalityProven": False,
                "serverAuthorityVerified": False,
                "sourceAuthenticityVerified": False,
            },
            "executableLogic": {
                "requestExecutableStatus": "request-executable-unavailable",
                "automaticExecutionRequired": True,
                "automaticExecutionReadyWorkflowCandidates": 0,
                "requestAlignedAutomaticExecutionReadyWorkflows": 0,
                "selectedWorkflowCandidateId": None,
                "requestImplementationReady": False,
                "requestStatus": "discovery-only-evidence",
            },
        }
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
        return summary

    script_path = scenario_output_root / "LycolesGeneratedFeatureBatch.lua"
    contract_path = scenario_output_root / "observation-tool-contract.json"
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
        "schemaVersion": "117.observation-recovery-summary.6",
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
        "discoveryReportPath": discovery.get("reportPath"),
        "discoverySummaryPath": discovery.get("summaryPath"),
        "discoveryQualityMetrics": discovery.get("qualityMetrics"),
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

    scenario_output_root = output_root / scenario_name
    discovery = _write_universal_discovery_artifacts(
        payload,
        requested_capability=requested_capability,
        output_root=scenario_output_root,
        generation_contract=None,
    )

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
        "discovery": discovery,
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

    parts_dir = _resolve_parts_dir_for_scan_id(extracted_root, selected_baseline)
    if not isinstance(parts_dir, pathlib.Path) or not parts_dir.is_dir():
        recovery = _recover_observation_only_auto_train(payload, requested_capability, scenario_output_root)
        executable_status = ((recovery.get("executableLogic") or {}).get("requestExecutableStatus") if isinstance(recovery, dict) else None)
        if require_executable and executable_status != "request-executable-ready":
            raise ValueError("Executable workflow required but unavailable in observation-only recovery")

        if recovery.get("status") == "generated-observation-contract":
            report["status"] = "recovered-observation-contract"
            report["reason"] = "baseline parts unavailable; generated bounded observation-only action contract"
        else:
            report["status"] = "discovery-only"
            report["reason"] = "baseline parts unavailable and executable contract not evidenced; produced discovery export"
        report["extractedRoot"] = str(extracted_root)
        report["recovery"] = recovery
        report["summary"] = recovery
        report["discovery"] = {
            "schemaVersion": recovery.get("schemaVersion"),
            "reportPath": recovery.get("discoveryReportPath"),
            "summaryPath": recovery.get("discoverySummaryPath"),
            "qualityMetrics": recovery.get("discoveryQualityMetrics"),
        }
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


def run_universal_discovery_export(
    observation_path: pathlib.Path,
    output_root: pathlib.Path,
    requested_capability: Optional[str] = None,
    scenario_name: str = "universal-discovery",
    baseline_archives: Optional[Sequence[pathlib.Path]] = None,
) -> dict[str, Any]:
    observation = pathlib.Path(observation_path).resolve()
    if not observation.is_file():
        raise ValueError(f"observation file not found: {observation}")
    payload = _read_json_document(observation)

    output_root = pathlib.Path(output_root).resolve()
    discovery_output_root = output_root / scenario_name

    baseline_archive_validation: dict[str, Any] = {}
    baseline_context: dict[str, Any] = {}
    baseline_archive_paths = [pathlib.Path(item).resolve() for item in (baseline_archives or [])]
    if baseline_archive_paths:
        expected_scan_id = _observation_baseline_scan_id(payload) or (payload.get("scanId") if isinstance(payload.get("scanId"), str) else None)
        ingestion_root = output_root / "ingested_parts_archives"
        baseline_archive_validation = ingest_parts_archives(
            baseline_archive_paths,
            ingestion_root,
            expected_scan_id=expected_scan_id,
        )
        baseline_parts_dir = pathlib.Path(baseline_archive_validation["outputDir"])
        baseline_context = _build_baseline_parts_context(baseline_parts_dir)

        if isinstance(payload.get("scanId"), str) and isinstance(baseline_context.get("scanId"), str):
            payload_scan_id = payload.get("scanId")
            if payload_scan_id != baseline_context.get("scanId"):
                raise ValueError(
                    f"observation/baseline scan mismatch: observation={payload_scan_id}, baseline={baseline_context.get('scanId')}"
                )
        if type(payload.get("placeId")) is int and type(baseline_context.get("placeId")) is int:
            if payload.get("placeId") != baseline_context.get("placeId"):
                raise ValueError(
                    f"observation/baseline place mismatch: observation={payload.get('placeId')}, baseline={baseline_context.get('placeId')}"
                )

    discovery = _write_universal_discovery_artifacts(
        payload,
        requested_capability=requested_capability,
        output_root=discovery_output_root,
        generation_contract=None,
        baseline_context=baseline_context,
        baseline_archive_validation=baseline_archive_validation,
    )

    return {
        "schemaVersion": "live-observation-discovery.1",
        "status": "succeeded",
        "scenario": scenario_name,
        "observationPath": str(observation),
        "scanId": payload.get("scanId"),
        "placeId": payload.get("placeId"),
        "gameName": payload.get("gameName"),
        "requestedCapability": requested_capability,
        "baselineArchiveValidation": baseline_archive_validation,
        "baselineContext": {
            "scanId": baseline_context.get("scanId"),
            "placeId": baseline_context.get("placeId"),
            "partCount": baseline_context.get("partCount"),
            "objectCount": baseline_context.get("objectCount"),
            "actionableWorldObjectCount": (
                len(baseline_context.get("actionableWorldObjectIndex"))
                if isinstance(baseline_context.get("actionableWorldObjectIndex"), dict)
                else 0
            ),
        },
        "discovery": discovery,
        "claims": {
            "runtimeVerified": False,
            "gameplayVerified": False,
            "causalityProven": False,
            "serverAuthorityVerified": False,
            "sourceAuthenticityVerified": False,
        },
    }




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

    discovery_parser = subparsers.add_parser(
        "discover-observation",
        help="Produce universal discovery report/summary from one dynamic-observation export",
    )
    discovery_parser.add_argument("--observation", required=True,
        help="Path to one dynamic-observations JSON export")
    discovery_parser.add_argument("--output-root", default="build/live-observation-discovery")
    discovery_parser.add_argument("--scenario-name", default="universal-discovery")
    discovery_parser.add_argument("--requested-capability", default=None)
    discovery_parser.add_argument("--baseline-archive", action="append", default=[],
        help="Optional .zip archive(s) containing baseline multipart scan parts; repeatable")

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
        elif args.mode == "exercise-observation":
            result = run_live_observation_scenario(
                output_root=output_root,
                observation_path=pathlib.Path(args.observation).resolve(),
                requested_capability=args.requested_capability,
                extracted_root=pathlib.Path(args.extracted_root).resolve(),
                baseline_scan_id=args.baseline_scan_id,
                scenario_name=args.scenario_name,
                require_executable=args.require_executable,
            )
        else:
            result = run_universal_discovery_export(
                observation_path=pathlib.Path(args.observation).resolve(),
                output_root=output_root,
                requested_capability=args.requested_capability,
                scenario_name=args.scenario_name,
                baseline_archives=[pathlib.Path(item).resolve() for item in (args.baseline_archive or [])],
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"PIPELINE BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
