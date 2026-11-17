#!/usr/bin/env python3
"""Reusable Lycoles evidence replay importer.

Builds a deterministic replay package from baseline multipart archives/directories,
manifest snapshots, live observation JSON exports, and previously reconstructed
replay packages.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import tempfile
import time
import zipfile
from typing import Any, Optional

MAX_JSON_BYTES = 25_000_000
MAX_PARTS = 2_000
MAX_INPUT_FILES = 20_000
FALSE_CLAIMS = {
    "sourceAuthenticityVerified": False,
    "causalityProven": False,
    "serverAuthorityVerified": False,
    "runtimeVerified": False,
    "gameplayVerified": False,
    "actionOutcomesVerified": False,
}


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _bounded_bytes(path: pathlib.Path, *, label: str, limit: int = MAX_JSON_BYTES) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file: {path}")
    raw = path.read_bytes()
    if len(raw) > limit:
        raise ValueError(f"{label} exceeds size limit: {path}")
    return raw


def _read_json_bytes(raw: bytes, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label}: {exc}") from None
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required for {label}")
    return value


def _read_json_file(path: pathlib.Path, *, label: str) -> dict[str, Any]:
    return _read_json_bytes(_bounded_bytes(path, label=label), label=label)


def _part_identity(payload: dict[str, Any], *, label: str) -> tuple[str, int, int, int]:
    scan_id = payload.get("scanId")
    place_id = payload.get("placeId")
    part_count = payload.get("partCount")
    part_index = payload.get("partIndex")
    if (not isinstance(scan_id, str) or not scan_id.strip()
            or type(place_id) is not int or place_id <= 0
            or type(part_count) is not int or not 1 <= part_count <= MAX_PARTS
            or type(part_index) is not int or not 1 <= part_index <= part_count):
        raise ValueError(f"invalid multipart part identity in {label}")
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise ValueError(f"multipart part missing objects[] in {label}")
    return scan_id, place_id, part_count, part_index


def _manifest_identity(payload: dict[str, Any]) -> tuple[Optional[str], Optional[int], Optional[int]]:
    scan_id = payload.get("scanId")
    place_id = payload.get("placeId")
    part_count = payload.get("partCount")
    if not isinstance(scan_id, str):
        scan_id = None
    if type(place_id) is not int:
        place_id = None
    if type(part_count) is not int:
        part_count = None
    return scan_id, place_id, part_count


def _manifest_score(payload: dict[str, Any]) -> int:
    score = 0
    if isinstance(payload.get("metadata"), dict):
        score += 3
    if isinstance(payload.get("integrity"), dict):
        score += 3
    if isinstance(payload.get("reportTransport"), dict):
        score += 2
    if isinstance(payload.get("partContentDigests"), list):
        score += 2
    if payload.get("schemaVersion"):
        score += 1
    return score


def _is_replay_package_payload(payload: dict[str, Any]) -> bool:
    return payload.get("schemaVersion") == "30.6.evidence-replay-package.1" and isinstance(payload.get("baseline"), dict)


def _iter_json_files_in_dir(directory: pathlib.Path) -> list[pathlib.Path]:
    files = [path for path in sorted(directory.rglob("*.json")) if path.is_file()]
    if len(files) > MAX_INPUT_FILES:
        raise ValueError(f"too many JSON files under {directory}")
    return files


def _resolve_replay_manifest_path(path: pathlib.Path) -> pathlib.Path:
    candidate = path.resolve()
    if candidate.is_dir():
        manifest = candidate / "replay-package.json"
        if not manifest.is_file():
            raise ValueError(f"replay package directory missing replay-package.json: {candidate}")
        return manifest
    return candidate


def load_replay_package(path: pathlib.Path | str) -> dict[str, Any]:
    manifest_path = _resolve_replay_manifest_path(pathlib.Path(path))
    payload = _read_json_file(manifest_path, label="replay package")
    if not _is_replay_package_payload(payload):
        raise ValueError("invalid replay package schema")

    baseline = payload.get("baseline")
    assert isinstance(baseline, dict)
    mode = baseline.get("mode")
    if mode not in {"multipart", "manifest-only"}:
        raise ValueError("replay package baseline mode must be multipart or manifest-only")

    root = manifest_path.parent

    parts_dir = None
    manifest_source = None
    if mode == "multipart":
        raw_parts = baseline.get("partsDir")
        if not isinstance(raw_parts, str) or not raw_parts.strip():
            raise ValueError("replay package multipart baseline is missing partsDir")
        parts_dir = (root / raw_parts).resolve()
        if not parts_dir.is_dir():
            raise ValueError("replay package partsDir does not exist")
        raw_manifest = baseline.get("manifestPath")
        if isinstance(raw_manifest, str) and raw_manifest.strip():
            manifest_source = (root / raw_manifest).resolve()
            if not manifest_source.is_file():
                raise ValueError("replay package manifestPath does not exist")
    else:
        raw_manifest = baseline.get("manifestPath")
        if not isinstance(raw_manifest, str) or not raw_manifest.strip():
            raise ValueError("replay package manifest-only baseline requires manifestPath")
        manifest_source = (root / raw_manifest).resolve()
        if not manifest_source.is_file():
            raise ValueError("replay package manifestPath does not exist")

    observations: list[dict[str, Any]] = []
    raw_observations = payload.get("observations")
    if raw_observations is not None:
        if not isinstance(raw_observations, list):
            raise ValueError("replay package observations must be a list")
        for item in raw_observations:
            if not isinstance(item, dict):
                raise ValueError("invalid replay observation record")
            rel = item.get("path")
            if not isinstance(rel, str) or not rel.strip():
                raise ValueError("replay observation record missing path")
            file_path = (root / rel).resolve()
            if not file_path.is_file():
                raise ValueError("replay observation path does not exist")
            record = dict(item)
            record["resolvedPath"] = str(file_path)
            observations.append(record)

    return {
        "schemaVersion": payload.get("schemaVersion"),
        "packagePath": str(manifest_path),
        "baseline": {
            **baseline,
            "mode": mode,
            "partsDir": str(parts_dir) if parts_dir is not None else None,
            "manifestPath": str(manifest_source) if manifest_source is not None else None,
        },
        "observations": observations,
        "warnings": payload.get("warnings") if isinstance(payload.get("warnings"), list) else [],
        "provenance": payload.get("provenance") if isinstance(payload.get("provenance"), dict) else {},
    }


def _collect_json_payloads_from_zip(path: pathlib.Path) -> list[tuple[str, bytes, str]]:
    out: list[tuple[str, bytes, str]] = []
    with zipfile.ZipFile(path) as archive:
        members = [item for item in archive.infolist() if not item.is_dir() and item.filename.lower().endswith(".json")]
        if not members:
            raise ValueError(f"zip has no JSON payloads: {path}")
        for member in sorted(members, key=lambda item: item.filename):
            if member.file_size > MAX_JSON_BYTES:
                raise ValueError(f"oversized zip payload {member.filename} in {path}")
            raw = archive.read(member)
            out.append((path.name + ":" + member.filename, raw, "baseline-zip-member"))
    return out


def _collect_baseline_payloads(source: pathlib.Path) -> tuple[list[tuple[str, bytes, str]], dict[str, Any]]:
    resolved = source.resolve()
    provenance = {
        "path": str(resolved),
        "kind": "baseline-input",
    }

    if resolved.is_file() and resolved.suffix.lower() == ".zip":
        provenance.update({"kind": "baseline-zip", "sha256": _sha256_file(resolved), "bytes": resolved.stat().st_size})
        return _collect_json_payloads_from_zip(resolved), provenance

    if resolved.is_file() and resolved.suffix.lower() in {".json", ".txt"}:
        raw = _bounded_bytes(resolved, label="baseline JSON")
        provenance.update({"kind": "baseline-json", "sha256": _sha256_bytes(raw), "bytes": len(raw)})
        return [(resolved.name, raw, "baseline-json")], provenance

    if resolved.is_dir():
        payloads: list[tuple[str, bytes, str]] = []
        total = 0
        for file_path in _iter_json_files_in_dir(resolved):
            if file_path.name == "replay-package.json":
                continue
            raw = _bounded_bytes(file_path, label="baseline directory JSON")
            payloads.append((str(file_path.relative_to(resolved)), raw, "baseline-dir-json"))
            total += len(raw)
        provenance.update({"kind": "baseline-directory", "bytes": total, "jsonFileCount": len(payloads)})
        return payloads, provenance

    raise ValueError(f"baseline input path not found: {source}")


def _iter_observation_files(path: pathlib.Path) -> list[pathlib.Path]:
    resolved = path.resolve()
    if resolved.is_file() and resolved.suffix.lower() in {".json", ".txt"}:
        return [resolved]
    if resolved.is_dir():
        candidates = [item.resolve() for item in sorted(resolved.rglob("*.json")) if item.is_file()]
        if len(candidates) > MAX_INPUT_FILES:
            raise ValueError(f"too many observation JSON files under {resolved}")
        return candidates
    raise ValueError(f"observation input path not found: {path}")


def _parse_observation(path: pathlib.Path) -> tuple[dict[str, Any], bytes]:
    raw = _bounded_bytes(path, label="observation JSON")
    payload = _read_json_bytes(raw, label=f"observation {path.name}")
    diagnostics = payload.get("sourceDiagnostics")
    if not isinstance(diagnostics, dict) or diagnostics.get("scanMode") != "dynamic-observations":
        raise ValueError(f"observation file must declare dynamic-observations scan mode: {path}")
    integrity = payload.get("integrity")
    if not isinstance(integrity, dict):
        raise ValueError(f"observation integrity object missing: {path}")
    if (integrity.get("scanComplete") is not True
            or type(integrity.get("placeId")) is not int
            or not isinstance(integrity.get("scanId"), str)
            or not integrity.get("scanId")):
        raise ValueError(f"observation integrity identity is invalid: {path}")
    if not isinstance(payload.get("features"), list):
        raise ValueError(f"observation features[] missing: {path}")
    return payload, raw


def _validate_manifest_digests(
    manifest_payload: dict[str, Any],
    *,
    raw_digests_by_index: dict[int, str],
    part_count: int,
) -> None:
    digest_entries: Any = None
    if isinstance(manifest_payload.get("partContentDigests"), list):
        digest_entries = manifest_payload.get("partContentDigests")
    else:
        metadata = manifest_payload.get("metadata") if isinstance(manifest_payload.get("metadata"), dict) else {}
        if isinstance(metadata.get("partContentDigests"), list):
            digest_entries = metadata.get("partContentDigests")

    if digest_entries is None:
        return

    if not isinstance(digest_entries, list):
        raise ValueError("manifest part digests are malformed")

    seen: set[int] = set()
    for entry in digest_entries:
        if not isinstance(entry, dict) or set(entry) != {"partIndex", "sha256"}:
            raise ValueError("manifest part digest entry is malformed")
        index = entry.get("partIndex")
        digest = entry.get("sha256")
        if (type(index) is not int or not 1 <= index <= part_count
                or not isinstance(digest, str) or len(digest) != 64):
            raise ValueError("manifest part digest identity is invalid")
        if index in seen:
            raise ValueError("manifest includes duplicate part digest entries")
        seen.add(index)
        if raw_digests_by_index.get(index) != digest:
            raise ValueError(f"manifest digest mismatch for part {index}")


def import_replay_package(
    *,
    baseline_inputs: list[pathlib.Path | str],
    observation_inputs: list[pathlib.Path | str],
    output_dir: pathlib.Path | str,
    expected_place_id: Optional[int] = None,
    expected_baseline_scan_id: Optional[str] = None,
    expected_observation_scan_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    if not baseline_inputs:
        raise ValueError("at least one baseline input is required")

    expected_obs = set(expected_observation_scan_ids or [])
    if expected_obs and any(not isinstance(item, str) or not item.strip() for item in expected_obs):
        raise ValueError("expected observation scan IDs must be non-empty strings")

    all_observation_paths: list[pathlib.Path] = [pathlib.Path(item).expanduser().resolve() for item in observation_inputs]
    expanded_baseline_inputs: list[pathlib.Path] = []
    provenance_sources: list[dict[str, Any]] = []

    for item in baseline_inputs:
        source = pathlib.Path(item).expanduser().resolve()
        try:
            replay = load_replay_package(source)
        except Exception:
            replay = None
        if replay is None:
            expanded_baseline_inputs.append(source)
            continue

        baseline = replay["baseline"]
        if baseline.get("mode") == "multipart":
            parts_dir = baseline.get("partsDir")
            if not isinstance(parts_dir, str) or not pathlib.Path(parts_dir).is_dir():
                raise ValueError("replay package multipart baseline is invalid")
            expanded_baseline_inputs.append(pathlib.Path(parts_dir))
        else:
            manifest_path = baseline.get("manifestPath")
            if not isinstance(manifest_path, str) or not pathlib.Path(manifest_path).is_file():
                raise ValueError("replay package manifest-only baseline is invalid")
            expanded_baseline_inputs.append(pathlib.Path(manifest_path))
        for observation in replay.get("observations") or []:
            resolved_path = observation.get("resolvedPath")
            if isinstance(resolved_path, str):
                all_observation_paths.append(pathlib.Path(resolved_path))
        provenance_sources.append({
            "path": str(pathlib.Path(replay["packagePath"])),
            "kind": "replay-package",
            "sha256": _sha256_file(pathlib.Path(replay["packagePath"])),
            "bytes": pathlib.Path(replay["packagePath"]).stat().st_size,
        })

    part_records: dict[int, dict[str, Any]] = {}
    manifest_candidates: list[dict[str, Any]] = []
    scan_id: Optional[str] = None
    place_id: Optional[int] = None
    part_count: Optional[int] = None

    for source in expanded_baseline_inputs:
        payloads, provenance = _collect_baseline_payloads(source)
        provenance_sources.append(provenance)
        for name, raw, source_kind in payloads:
            payload = _read_json_bytes(raw, label=f"baseline payload {name}")
            if _is_replay_package_payload(payload):
                raise ValueError("nested replay-package payloads are not allowed in baseline inputs")

            if "partIndex" in payload:
                sid, pid, pcount, index = _part_identity(payload, label=f"baseline payload {name}")
                if expected_baseline_scan_id is not None and sid != expected_baseline_scan_id:
                    raise ValueError(f"baseline scanId mismatch: expected {expected_baseline_scan_id}, got {sid}")
                if expected_place_id is not None and pid != expected_place_id:
                    raise ValueError(f"baseline placeId mismatch: expected {expected_place_id}, got {pid}")
                if scan_id is None:
                    scan_id, place_id, part_count = sid, pid, pcount
                elif sid != scan_id or pid != place_id or pcount != part_count:
                    raise ValueError("mixed baseline scan identity across multipart inputs")

                digest = _sha256_bytes(raw)
                existing = part_records.get(index)
                if existing is not None:
                    if existing["sha256"] != digest:
                        raise ValueError(f"conflicting duplicate part content for index {index}")
                    continue
                part_records[index] = {
                    "index": index,
                    "raw": raw,
                    "sha256": digest,
                    "source": source_kind,
                    "name": name,
                }
                continue

            m_scan, m_place, m_count = _manifest_identity(payload)
            manifest_candidates.append({
                "payload": payload,
                "raw": raw,
                "sha256": _sha256_bytes(raw),
                "name": name,
                "scanId": m_scan,
                "placeId": m_place,
                "partCount": m_count,
            })

    if part_records:
        assert scan_id is not None and place_id is not None and part_count is not None
        missing = [index for index in range(1, part_count + 1) if index not in part_records]
        if missing:
            preview = missing[:20]
            raise ValueError(f"baseline parts are incomplete: missing {preview} (total {len(missing)})")
    elif manifest_candidates:
        chosen = max(manifest_candidates, key=lambda item: _manifest_score(item["payload"]))
        scan_id = chosen["scanId"]
        place_id = chosen["placeId"]
        part_count = chosen["partCount"]
        if not isinstance(scan_id, str) or type(place_id) is not int or type(part_count) is not int:
            raise ValueError("manifest-only baseline does not provide complete identity")
    else:
        raise ValueError("no baseline multipart parts or compatible manifest found")

    assert scan_id is not None and place_id is not None and part_count is not None

    if expected_baseline_scan_id is not None and scan_id != expected_baseline_scan_id:
        raise ValueError(f"baseline scanId mismatch: expected {expected_baseline_scan_id}, got {scan_id}")
    if expected_place_id is not None and place_id != expected_place_id:
        raise ValueError(f"baseline placeId mismatch: expected {expected_place_id}, got {place_id}")

    matching_manifests = [
        item for item in manifest_candidates
        if (item.get("scanId") in {None, scan_id}
            and item.get("placeId") in {None, place_id}
            and item.get("partCount") in {None, part_count})
    ]
    if len(matching_manifests) != len(manifest_candidates):
        raise ValueError("one or more baseline manifests do not match multipart identity")

    chosen_manifest = None
    if matching_manifests:
        chosen_manifest = max(matching_manifests, key=lambda item: (_manifest_score(item["payload"]), len(item["raw"])))

    if part_records and chosen_manifest is not None:
        _validate_manifest_digests(
            chosen_manifest["payload"],
            raw_digests_by_index={index: data["sha256"] for index, data in part_records.items()},
            part_count=part_count,
        )

    observations: list[dict[str, Any]] = []
    observation_scan_ids: set[str] = set()
    for source in all_observation_paths:
        for candidate in _iter_observation_files(source):
            payload, raw = _parse_observation(candidate)
            integrity = payload["integrity"]
            obs_scan_id = integrity["scanId"]
            baseline_scan_id = integrity.get("baselineScanId") if isinstance(integrity.get("baselineScanId"), str) else None
            obs_place_id = integrity["placeId"]
            if obs_place_id != place_id:
                raise ValueError(
                    f"observation/baseline place mismatch for {candidate}: observation={obs_place_id}, baseline={place_id}"
                )
            if baseline_scan_id is not None and baseline_scan_id != scan_id:
                raise ValueError(
                    f"observation baselineScanId mismatch for {candidate}: observation={baseline_scan_id}, baseline={scan_id}"
                )
            if expected_obs and obs_scan_id not in expected_obs:
                raise ValueError(f"unexpected observation scanId {obs_scan_id} in {candidate}")
            observations.append({
                "sourcePath": str(candidate),
                "payload": payload,
                "raw": raw,
                "sha256": _sha256_bytes(raw),
                "scanId": obs_scan_id,
                "baselineScanId": baseline_scan_id,
                "placeId": obs_place_id,
            })
            observation_scan_ids.add(obs_scan_id)
            provenance_sources.append({
                "path": str(candidate),
                "kind": "observation-json",
                "sha256": _sha256_bytes(raw),
                "bytes": len(raw),
            })

    if expected_obs and observation_scan_ids != expected_obs:
        missing = sorted(expected_obs - observation_scan_ids)
        extra = sorted(observation_scan_ids - expected_obs)
        raise ValueError(
            f"observation scanId mismatch: missing={missing or []}, unexpected={extra or []}"
        )

    output_root = pathlib.Path(output_dir).expanduser().resolve()
    staging = pathlib.Path(tempfile.mkdtemp(prefix=".replay-import-", dir=str(output_root.parent if output_root.parent.exists() else pathlib.Path.cwd())))
    try:
        parts_dir = staging / "parts"
        observations_dir = staging / "observations"
        parts_dir.mkdir(parents=True, exist_ok=True)
        observations_dir.mkdir(parents=True, exist_ok=True)

        baseline_mode = "multipart" if part_records else "manifest-only"
        part_digests: list[dict[str, Any]] = []
        if part_records:
            for index in range(1, part_count + 1):
                record = part_records[index]
                target = parts_dir / f"{scan_id}_part-{index:04d}.json"
                target.write_bytes(record["raw"])
                part_digests.append({"partIndex": index, "sha256": record["sha256"]})

        manifest_rel = None
        if chosen_manifest is not None:
            manifest_name = f"{scan_id}_manifest.json"
            manifest_target = parts_dir / manifest_name
            manifest_target.write_bytes(chosen_manifest["raw"])
            manifest_rel = str(pathlib.Path("parts") / manifest_name)

        observation_entries: list[dict[str, Any]] = []
        for idx, record in enumerate(sorted(observations, key=lambda item: (item["scanId"], item["sourcePath"])), 1):
            safe_scan = "".join(ch for ch in record["scanId"] if ch.isalnum() or ch in {"-", "_"}) or f"observation-{idx:03d}"
            target_name = f"{safe_scan}-{idx:03d}.json"
            target = observations_dir / target_name
            target.write_bytes(record["raw"])
            observation_entries.append({
                "scanId": record["scanId"],
                "baselineScanId": record["baselineScanId"],
                "placeId": record["placeId"],
                "path": str(pathlib.Path("observations") / target_name),
                "sha256": record["sha256"],
            })

        normalized_sources: list[dict[str, Any]] = []
        seen_source_keys: set[tuple[str, str]] = set()
        for source in provenance_sources:
            path_value = source.get("path")
            kind = source.get("kind")
            if not isinstance(path_value, str) or not isinstance(kind, str):
                continue
            key = (path_value, kind)
            if key in seen_source_keys:
                continue
            seen_source_keys.add(key)
            normalized_sources.append(source)

        package_payload = {
            "schemaVersion": "30.6.evidence-replay-package.1",
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "baseline": {
                "mode": baseline_mode,
                "scanId": scan_id,
                "placeId": place_id,
                "partCount": part_count,
                "partsDir": "parts" if baseline_mode == "multipart" else None,
                "manifestPath": manifest_rel,
                "partDigests": part_digests,
                "partsComplete": bool(part_records),
                "missingPartCount": 0 if part_records else None,
            },
            "observations": observation_entries,
            "validation": {
                "expectedPlaceId": expected_place_id,
                "expectedBaselineScanId": expected_baseline_scan_id,
                "expectedObservationScanIds": sorted(expected_obs),
                "matchedPlaceId": place_id,
                "matchedBaselineScanId": scan_id,
                "matchedObservationScanIds": sorted(observation_scan_ids),
                "baselineIdentityVerified": True,
                "partCompletenessVerified": bool(part_records),
                "sourceProvenanceRecorded": True,
                "receiverIntegrityVerified": False,
            },
            "provenance": {
                "sources": normalized_sources,
                "claims": dict(FALSE_CLAIMS),
            },
            "warnings": [],
        }

        (staging / "replay-package.json").write_text(
            json.dumps(package_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

        if output_root.exists():
            if output_root.is_file():
                raise ValueError(f"replay output path is a file: {output_root}")
            shutil.rmtree(output_root)
        output_root.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(output_root)

        result = dict(package_payload)
        result["outputDir"] = str(output_root)
        result["replayPackagePath"] = str(output_root / "replay-package.json")
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
