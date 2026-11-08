#!/usr/bin/env python3
"""Download a verified receiver scan for the offline pipeline.

The receiver read key is accepted only through LYCOLES_READ_KEY. The importer
requires HTTPS, does not follow redirects, publishes atomically, and never claims
that receiver bytes equal the inspector's original local payloads.
"""
import argparse
import concurrent.futures
import hashlib
import http.client
import importlib.util
import json
import os
import pathlib
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

MAX_JSON_BYTES = 3_000_000
MAX_OBJECTS = 2_000_000
MAX_PARTS = 2_000
MAX_WORKERS = 8
MAX_LEGACY_REPORT_PAGES = 500


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def _receiver_origin(endpoint, allow_http):
    if not isinstance(endpoint, str):
        raise ValueError("invalid receiver endpoint")
    parsed = urllib.parse.urlsplit(endpoint.strip())
    if parsed.scheme != "https" and not (allow_http and parsed.scheme == "http"):
        raise ValueError("HTTPS receiver endpoint required")
    if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("invalid receiver endpoint")
    if parsed.path not in {"", "/"}:
        raise ValueError("receiver endpoint must be an origin without a path")
    return f"{parsed.scheme}://{parsed.netloc}"


def _identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", value):
        raise ValueError(f"invalid {name}")
    return value


def _read_key(value):
    if (not isinstance(value, str) or not 8 <= len(value) <= 512
            or any(ord(character) < 33 or ord(character) == 127 for character in value)):
        raise ValueError("invalid receiver read key")
    return value


def _read_json_once(opener, url, timeout, require_digest=False, return_raw=False):
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "Lycoles-receiver-import/30.2"})
    response = opener.open(request, timeout=timeout)
    with response:
        if response.status != 200:
            raise ValueError(f"unexpected HTTP status {response.status}")
        declared = response.headers.get("Content-Length")
        if declared is not None:
            try:
                declared_size = int(declared)
            except ValueError:
                raise ValueError("invalid receiver content length") from None
            if declared_size < 0:
                raise ValueError("invalid receiver content length")
            if declared_size > MAX_JSON_BYTES:
                raise ValueError("receiver JSON exceeds size limit")
        persisted_digest = response.headers.get("X-Lycoles-Content-SHA256")
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("receiver JSON exceeds size limit")
    digest = hashlib.sha256(raw).hexdigest()
    if require_digest:
        if not isinstance(persisted_digest, str) or not re.fullmatch(
                r"[a-f0-9]{64}", persisted_digest):
            raise ValueError("receiver content digest is missing or invalid")
        if digest != persisted_digest:
            raise ValueError("receiver content digest mismatch")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("receiver returned invalid JSON") from None
    if not isinstance(document, dict):
        raise ValueError("receiver JSON must be an object")
    return (document, digest, raw) if require_digest or return_raw else document


def _read_json(opener, url, timeout, require_digest=False, return_raw=False):
    transient_statuses = {408, 425, 429, 500, 502, 503, 504}
    for attempt in range(3):
        try:
            return _read_json_once(opener, url, timeout, require_digest, return_raw)
        except urllib.error.HTTPError as exc:
            status = exc.code
            exc.close()
            if status not in transient_statuses:
                raise ValueError(f"unexpected HTTP status {status}") from None
            failure = f"unexpected HTTP status {status}"
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.IncompleteRead):
            failure = "receiver transport failed"
        if attempt == 2:
            raise ValueError(failure) from None
        time.sleep(0.2 * (2 ** attempt))


def _positive_integer(value, name, maximum=None, allow_zero=False):
    minimum = 0 if allow_zero else 1
    if type(value) is not int or value < minimum or (maximum is not None and value > maximum):
        raise ValueError(f"invalid {name}")
    return value


def _validate_metadata(document, scan_id):
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise ValueError("receiver metadata is incomplete")
    if metadata.get("scanId") != scan_id:
        raise ValueError("receiver scan identity mismatch")
    place_id = _positive_integer(metadata.get("placeId"), "receiver place ID")
    part_count = _positive_integer(metadata.get("partCount"), "receiver part count", MAX_PARTS)
    return metadata, place_id, part_count


def _validate_legacy_integrity(document, scan_id, place_id, part_count):
    if (not isinstance(document, dict) or document.get("scanId") != scan_id
            or document.get("placeId") != place_id
            or document.get("partCount") != part_count
            or document.get("receivedParts") != part_count
            or document.get("missingParts") != []
            or document.get("identityErrors") != []
            or document.get("duplicateObjectKeys") != 0
            or document.get("complete") is not True
            or document.get("integrityStatus") != "verified"):
        raise ValueError("legacy receiver integrity is incomplete or inconsistent")
    indexed = _positive_integer(document.get("indexedObjects"), "legacy indexed objects",
                                MAX_OBJECTS, allow_zero=True)
    unique = _positive_integer(document.get("uniqueObjectKeys"), "legacy unique objects",
                               MAX_OBJECTS, allow_zero=True)
    expected = _positive_integer(document.get("expectedObjects"), "legacy expected objects",
                                 MAX_OBJECTS, allow_zero=True)
    if indexed != unique or indexed != expected:
        raise ValueError("legacy receiver object accounting mismatch")
    return {key: document.get(key) for key in (
        "scanId", "placeId", "partCount", "receivedParts", "missingParts",
        "indexedObjects", "uniqueObjectKeys", "duplicateObjectKeys", "identityErrors",
        "expectedObjects", "complete", "integrityStatus")}



def _read_bounded_file(path, label):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    try:
        with path.open("rb") as handle:
            raw = handle.read(MAX_JSON_BYTES + 1)
    except OSError as exc:
        raise ValueError(f"cannot read {label}: {exc}") from None
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"{label} exceeds size limit")
    return raw


def _acknowledged_digests(path, scan_id, place_id, part_count):
    if path is None:
        return {}
    path = pathlib.Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError("local manifest must be a regular file")
    raw = _read_bounded_file(path, "local manifest")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("local manifest is invalid JSON") from None
    if not isinstance(manifest, dict):
        raise ValueError("local manifest must be an object")
    if (manifest.get("scanId") != scan_id or manifest.get("placeId") != place_id
            or manifest.get("partCount") != part_count):
        raise ValueError("local manifest identity mismatch")
    transport = manifest.get("reportTransport")
    if not isinstance(transport, dict):
        return {}
    entries = transport.get("acknowledgedPartDigests")
    if entries is None:
        return {}
    if not isinstance(entries, list):
        raise ValueError("invalid acknowledgement digest list")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid acknowledgement digest entry")
        index = _positive_integer(entry.get("partIndex"), "acknowledged part index",
                                  part_count)
        digest = entry.get("sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid acknowledgement digest")
        if index in result:
            raise ValueError("duplicate acknowledgement digest index")
        result[index] = digest
    return result


def _validate_part(part, scan_id, place_id, part_count, index):
    if (part.get("scanId") != scan_id or part.get("placeId") != place_id
            or part.get("partCount") != part_count or part.get("partIndex") != index):
        raise ValueError(f"part identity mismatch at index {index}")
    objects = part.get("objects")
    if not isinstance(objects, list) or any(not isinstance(item, dict) for item in objects):
        raise ValueError(f"invalid object records in part {index}")
    return objects


def _worker_string(value):
    if value is None:
        return "undefined"
    if type(value) is bool:
        return "true" if value else "false"
    return str(value)


def _object_key(item):
    return _worker_string(item.get("path") or "") + "#" + _worker_string(
        item.get("scanOrdinal") or "")


def _write_json(path, document):
    path.write_text(json.dumps(document, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def _compile_scan(directory):
    source = pathlib.Path(__file__).with_name("compile_scan.py")
    spec = importlib.util.spec_from_file_location("lycoles_receiver_compile_scan", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compile_scan(directory)


def _atomic_write(path, raw):
    descriptor, temporary = tempfile.mkstemp(prefix=".resume-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def _canonical_digest(document):
    raw = json.dumps(document, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _checkpoint_document(origin, scan_id, place_id, part_count,
                         metadata_digest, digests):
    return {
        "schemaVersion": "30.2.receiver-resume.1",
        "receiverOrigin": origin,
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "metadataSha256": metadata_digest,
        "parts": [
            {"partIndex": index, "sha256": digests[index]}
            for index in sorted(digests)
        ],
        "authenticated": False,
        "note": "Local resume state records earlier receiver-digest verification but is not independently authenticated",
    }


def _write_checkpoint(directory, document):
    raw = (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False)
           + "\n").encode("utf-8")
    _atomic_write(directory / "receiver-resume.json", raw)


def _load_resume(directory, origin, scan_id, place_id, part_count,
                 metadata_digest, acknowledgement_digests):
    checkpoint_path = directory / "receiver-resume.json"
    if not checkpoint_path.exists():
        if any(directory.iterdir()):
            raise ValueError("resume directory lacks a checkpoint")
        _write_checkpoint(directory, _checkpoint_document(
            origin, scan_id, place_id, part_count, metadata_digest, {}))
        return {}
    if checkpoint_path.is_symlink() or not checkpoint_path.is_file():
        raise ValueError("invalid resume checkpoint")
    raw = _read_bounded_file(checkpoint_path, "resume checkpoint")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid resume checkpoint JSON") from None
    expected = {
        "schemaVersion": "30.2.receiver-resume.1",
        "receiverOrigin": origin,
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "metadataSha256": metadata_digest,
        "authenticated": False,
        "note": "Local resume state records earlier receiver-digest verification but is not independently authenticated",
    }
    if (not isinstance(document, dict)
            or set(document) != set(expected) | {"parts"}
            or any(document.get(key) != value for key, value in expected.items())):
        raise ValueError("resume checkpoint identity mismatch")
    entries = document.get("parts")
    if not isinstance(entries, list) or len(entries) > part_count:
        raise ValueError("invalid resume checkpoint parts")
    result = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"partIndex", "sha256"}:
            raise ValueError("invalid resume checkpoint part")
        index = _positive_integer(entry.get("partIndex"), "resume part index", part_count)
        digest = entry.get("sha256")
        if (index in result or not isinstance(digest, str)
                or not re.fullmatch(r"[a-f0-9]{64}", digest)):
            raise ValueError("invalid resume checkpoint part")
        part_path = directory / f"part-{index:04d}.json"
        if part_path.is_symlink() or not part_path.is_file():
            raise ValueError("resume part is missing or invalid")
        part_raw = _read_bounded_file(part_path, "resume part")
        if hashlib.sha256(part_raw).hexdigest() != digest:
            raise ValueError("resume part digest mismatch")
        try:
            part = json.loads(part_raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("resume part is invalid JSON") from None
        if not isinstance(part, dict):
            raise ValueError("resume part JSON must be an object")
        _validate_part(part, scan_id, place_id, part_count, index)
        acknowledged = acknowledgement_digests.get(index)
        if acknowledged is not None and acknowledged != digest:
            raise ValueError("resume part does not match local acknowledgement digest")
        result[index] = digest
    return result


def _resume_directory(path, output):
    if path is None:
        return None
    directory = pathlib.Path(path)
    output_resolved = output.resolve(strict=False)
    directory_resolved = directory.resolve(strict=False)
    try:
        common = pathlib.Path(os.path.commonpath((output_resolved, directory_resolved)))
    except ValueError:
        common = None
    if common in {output_resolved, directory_resolved}:
        raise ValueError("output and resume paths must not overlap")
    if directory.is_symlink() or (directory.exists() and not directory.is_dir()):
        raise ValueError("invalid resume directory")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _legacy_reports_page(opener, origin, read_key, timeout, cursor=None):
    root = "/reports/" + urllib.parse.quote(read_key, safe="")
    url = origin + root
    if cursor is not None:
        if not isinstance(cursor, str) or not cursor:
            raise ValueError("invalid legacy report cursor")
        url += "?" + urllib.parse.urlencode({"cursor": cursor})
    document = _read_json(opener, url, timeout)
    if not isinstance(document, dict):
        raise ValueError("legacy report collection response is invalid")
    records = document.get("reports")
    has_more = document.get("hasMore")
    next_cursor = document.get("nextCursor")
    if (not isinstance(records, list)
            or any(not isinstance(item, str) for item in records)
            or type(has_more) is not bool):
        raise ValueError("legacy report collection response is invalid")
    if has_more and (not isinstance(next_cursor, str) or not next_cursor):
        raise ValueError("legacy report collection response is invalid")
    return records, has_more, next_cursor


def _legacy_report_part(document):
    if not isinstance(document, dict):
        raise ValueError("legacy report payload is invalid")
    report = document.get("report")
    if isinstance(report, str):
        try:
            report = json.loads(report)
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("legacy report payload is invalid") from None
    if not isinstance(report, dict):
        raise ValueError("legacy report payload is invalid")
    return report, document.get("receivedAt")


def _fetch_scan_legacy_reports(opener, origin, read_key, scan_id, output, timeout,
                               workers, max_legacy_report_pages):
    cursor = None
    pages_scanned = 0
    part_count = None
    place_id = None
    metadata = None
    matched_records = 0
    matched_parts = {}

    root = "/reports/" + urllib.parse.quote(read_key, safe="")

    while pages_scanned < max_legacy_report_pages:
        records, has_more, next_cursor = _legacy_reports_page(
            opener, origin, read_key, timeout, cursor)
        pages_scanned += 1

        def retrieve(record_id):
            document = _read_json(opener, origin + root + "/" + record_id, timeout)
            report, received_at = _legacy_report_part(document)
            return record_id, report, received_at

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(retrieve, record_id) for record_id in records]
            for future in concurrent.futures.as_completed(futures):
                record_id, part, received_at = future.result()
                if part.get("scanId") != scan_id:
                    continue
                matched_records += 1
                current_place = _positive_integer(part.get("placeId"), "receiver place ID")
                current_parts = _positive_integer(part.get("partCount"), "receiver part count",
                                                  MAX_PARTS)
                if part_count is None:
                    part_count = current_parts
                    place_id = current_place
                    metadata = {
                        "scanId": scan_id,
                        "placeId": place_id,
                        "partCount": part_count,
                        "version": part.get("version"),
                        "gameName": part.get("gameName"),
                    }
                    if isinstance(received_at, str):
                        metadata["receivedAt"] = received_at
                elif part_count != current_parts or place_id != current_place:
                    raise ValueError("legacy reports contain conflicting scan metadata")

                index = _positive_integer(part.get("partIndex"), "receiver part index", part_count)
                _validate_part(part, scan_id, place_id, part_count, index)
                raw = json.dumps(part, sort_keys=True, separators=(",", ":"),
                                 ensure_ascii=False).encode("utf-8")
                digest = hashlib.sha256(raw).hexdigest()
                previous = matched_parts.get(index)
                if previous is not None and previous["sha256"] != digest:
                    raise ValueError("legacy reports contain conflicting duplicate part content")
                if previous is None:
                    matched_parts[index] = {
                        "recordId": record_id,
                        "sha256": digest,
                        "raw": raw,
                        "part": part,
                    }

        if part_count is not None and len(matched_parts) == part_count:
            break
        if not has_more:
            break
        cursor = next_cursor

    if part_count is None:
        raise ValueError("requested scan not found in legacy report collection")
    missing = [index for index in range(1, part_count + 1) if index not in matched_parts]
    if missing:
        raise ValueError("legacy report collection is missing required parts")

    with tempfile.TemporaryDirectory(prefix=".lycoles-receiver-", dir=output.parent) as temp:
        staging = pathlib.Path(temp)
        total_objects = 0
        object_keys = set()
        object_identities = {}
        collapsed_duplicate_objects = 0
        synthesized_scan_ordinals = 0
        part_digests = {}

        for index in range(1, part_count + 1):
            entry = matched_parts[index]
            part = entry["part"]
            objects = _validate_part(part, scan_id, place_id, part_count, index)
            filtered_objects = []
            for object_index, original_item in enumerate(objects, start=1):
                item = original_item
                if original_item.get("scanOrdinal") in (None, ""):
                    item = dict(original_item)
                    item["scanOrdinal"] = f"legacy-{index}-{object_index}"
                    synthesized_scan_ordinals += 1
                key = _object_key(item)
                snapshot = json.dumps(item, sort_keys=True, ensure_ascii=False)
                previous = object_identities.get(key)
                if previous is None:
                    object_identities[key] = snapshot
                    object_keys.add(key)
                    filtered_objects.append(item)
                    continue
                if previous == snapshot:
                    collapsed_duplicate_objects += 1
                    continue
                raise ValueError("duplicate receiver object identity")
            total_objects += len(filtered_objects)
            if total_objects > MAX_OBJECTS:
                raise ValueError("receiver object count exceeds safety limit")
            sanitized_part = dict(part)
            sanitized_part["objects"] = filtered_objects
            scan_stats = part.get("scanStats")
            if isinstance(scan_stats, dict) and "complete" not in scan_stats:
                synthesized_stats = dict(scan_stats)
                recorded = synthesized_stats.get("recorded")
                eligible = synthesized_stats.get("eligible")
                omitted = synthesized_stats.get("omitted")
                synthesized_stats["complete"] = (
                    type(recorded) is int and type(eligible) is int
                    and type(omitted) is int and omitted == 0 and recorded == eligible
                )
                sanitized_part["scanStats"] = synthesized_stats
            raw = json.dumps(sanitized_part, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False).encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()
            part_digests[index] = digest
            (staging / f"part-{index:04d}.json").write_bytes(raw)

        receiver_part_digests = [
            {"partIndex": index, "sha256": part_digests[index]}
            for index in range(1, part_count + 1)
        ]
        integrity = {
            "scanId": scan_id,
            "placeId": place_id,
            "partCount": part_count,
            "receivedParts": part_count,
            "missingParts": [],
            "indexedObjects": total_objects,
            "uniqueObjectKeys": len(object_keys),
            "duplicateObjectKeys": 0,
            "identityErrors": [],
            "expectedObjects": total_objects,
            "complete": True,
            "integrityStatus": "verified-after-retrieval",
            "verificationMethod": "legacy report retrieval plus local multipart compilation",
        }
        import_manifest = {
            "schemaVersion": "30.2.receiver-import-legacy-reports.1",
            "scanId": scan_id,
            "placeId": place_id,
            "partCount": part_count,
            "expectedParts": part_count,
            "objectCount": total_objects,
            "metadata": metadata,
            "receiverIntegrity": integrity,
            "retrievedPartContentDigests": receiver_part_digests,
            "resumableRetrievalEnabled": False,
            "resumedPartCount": 0,
            "downloadedPartCount": part_count,
            "resumeCheckpointAuthenticated": False,
            "receiverStoredPayloadDigestsRevalidatedThisRun": False,
            "receiverStoredPayloadDigestsVerified": False,
            "receiverAcknowledgementDigestEquivalent": False,
            "receiverIntegrityVerified": True,
            "receiverResponseAuthenticityVerified": False,
            "localPayloadEquivalent": False,
            "receiverReportedIntegrityUnavailable": True,
            "legacyReportPagesScanned": pages_scanned,
            "legacyReportRecordsMatched": matched_records,
            "note": ("Legacy report-index import reconstructed multipart scan from wrapped records; "
                     "receiver-stored per-part payload digests and dedicated integrity endpoint were unavailable; "
                     f"collapsed identical duplicate object identities: {collapsed_duplicate_objects}; "
                     f"synthesized missing scan ordinals: {synthesized_scan_ordinals}"),
        }
        _write_json(staging / "receiver-manifest.json", import_manifest)
        plan = _compile_scan(staging)
        if output.exists() or output.is_symlink():
            raise ValueError("output path was created during import")
        staging.replace(output)

    return {
        "schemaVersion": import_manifest["schemaVersion"],
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "objectCount": total_objects,
        "featureCount": plan["featureCount"],
        "resumableRetrievalEnabled": False,
        "resumedPartCount": 0,
        "downloadedPartCount": part_count,
        "resumeCheckpointAuthenticated": False,
        "receiverStoredPayloadDigestsRevalidatedThisRun": False,
        "receiverStoredPayloadDigestsVerified": False,
        "receiverAcknowledgementDigestEquivalent": False,
        "receiverIntegrityVerified": True,
        "receiverResponseAuthenticityVerified": False,
        "localPayloadEquivalent": False,
        "output": str(output),
        "legacyReportPagesScanned": pages_scanned,
        "legacyReportRecordsMatched": matched_records,
    }


def fetch_scan(endpoint, read_key, scan_id, output, *, timeout=30, workers=4,
               local_manifest=None, resume=None, allow_http=False,
               allow_legacy_v11=False, allow_legacy_report_index=False,
               max_legacy_report_pages=MAX_LEGACY_REPORT_PAGES):
    origin = _receiver_origin(endpoint, allow_http)
    read_key = _read_key(read_key)
    scan_id = _identifier(scan_id, "receiver scan ID")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 120:
        raise ValueError("invalid receiver timeout")
    workers = _positive_integer(workers, "worker count", MAX_WORKERS)
    if type(allow_legacy_v11) is not bool:
        raise ValueError("invalid legacy receiver option")
    if type(allow_legacy_report_index) is not bool:
        raise ValueError("invalid legacy report index option")
    max_legacy_report_pages = _positive_integer(
        max_legacy_report_pages, "legacy report page limit", 5000)
    if allow_legacy_v11 and resume is not None:
        raise ValueError("legacy receiver retrieval does not support resume checkpoints")
    output = pathlib.Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("output path already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(_NoRedirect)
    root = "/reports/" + urllib.parse.quote(read_key, safe="") + "/" + scan_id
    try:
        metadata_document = _read_json(opener, origin + root + "/metadata", timeout)
    except ValueError as exc:
        if (allow_legacy_report_index and str(exc) == "unexpected HTTP status 404"
                and not allow_legacy_v11):
            if resume is not None:
                raise ValueError("legacy report-index retrieval does not support resume checkpoints")
            if local_manifest is not None:
                raise ValueError("legacy report-index retrieval does not support local manifest acknowledgement validation")
            return _fetch_scan_legacy_reports(
                opener, origin, read_key, scan_id, output, timeout,
                workers, max_legacy_report_pages)
        raise
    metadata, place_id, part_count = _validate_metadata(metadata_document, scan_id)
    legacy_integrity = (_validate_legacy_integrity(
        _read_json(opener, origin + root + "/integrity", timeout),
        scan_id, place_id, part_count) if allow_legacy_v11 else None)
    metadata_digest = _canonical_digest(metadata)
    acknowledgement_digests = _acknowledged_digests(
        local_manifest, scan_id, place_id, part_count)
    resume_directory = _resume_directory(resume, output)
    resumed_parts = (_load_resume(
        resume_directory, origin, scan_id, place_id, part_count,
        metadata_digest, acknowledgement_digests)
        if resume_directory is not None else {})

    with tempfile.TemporaryDirectory(prefix=".lycoles-receiver-", dir=output.parent) as temp:
        staging = pathlib.Path(temp)
        total_objects = 0
        object_keys = set()
        part_digests = {}
        resume_digests = dict(resumed_parts)
        downloaded_part_count = 0

        def admit(index, part, digest, raw, *, cache):
            nonlocal total_objects, downloaded_part_count
            if hashlib.sha256(raw).hexdigest() != digest:
                raise ValueError("part digest changed during import")
            acknowledged_digest = acknowledgement_digests.get(index)
            if acknowledged_digest is not None and acknowledged_digest != digest:
                raise ValueError("receiver part does not match local acknowledgement digest")
            objects = _validate_part(part, scan_id, place_id, part_count, index)
            for item in objects:
                key = _object_key(item)
                if key in object_keys:
                    raise ValueError("duplicate receiver object identity")
                object_keys.add(key)
            total_objects += len(objects)
            if total_objects > MAX_OBJECTS:
                raise ValueError("receiver object count exceeds safety limit")
            part_digests[index] = digest
            (staging / f"part-{index:04d}.json").write_bytes(raw)
            if cache:
                downloaded_part_count += 1
                if resume_directory is not None:
                    _atomic_write(resume_directory / f"part-{index:04d}.json", raw)
                    resume_digests[index] = digest
                    _write_checkpoint(resume_directory, _checkpoint_document(
                        origin, scan_id, place_id, part_count,
                        metadata_digest, resume_digests))

        for index in sorted(resumed_parts):
            raw = _read_bounded_file(
                resume_directory / f"part-{index:04d}.json", "resume part")
            part = json.loads(raw)
            admit(index, part, resumed_parts[index], raw, cache=False)

        def retrieve(index):
            part, digest, raw = _read_json(
                opener, origin + root + f"/part-{index}", timeout,
                require_digest=not allow_legacy_v11, return_raw=allow_legacy_v11)
            return index, part, digest, raw

        missing_indexes = [
            index for index in range(1, part_count + 1)
            if index not in resumed_parts
        ]
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(0, len(missing_indexes), workers * 2):
                batch = missing_indexes[start:start + workers * 2]
                futures = {executor.submit(retrieve, index): index for index in batch}
                results = []
                failure = None
                for future in concurrent.futures.as_completed(futures):
                    try:
                        results.append(future.result())
                    except (ValueError, OSError) as exc:
                        if failure is None:
                            failure = exc
                for index, part, digest, raw in sorted(results):
                    admit(index, part, digest, raw, cache=True)
                if failure is not None:
                    raise failure
        acknowledgement_equivalent = (
            len(acknowledgement_digests) == part_count
            and all(acknowledgement_digests.get(index) == part_digests.get(index)
                    for index in range(1, part_count + 1)))
        receiver_part_digests = [
            {"partIndex": index, "sha256": part_digests[index]}
            for index in range(1, part_count + 1)]
        integrity = {
            "scanId": scan_id,
            "placeId": place_id,
            "partCount": part_count,
            "receivedParts": part_count,
            "missingParts": [],
            "indexedObjects": total_objects,
            "uniqueObjectKeys": len(object_keys),
            "duplicateObjectKeys": 0,
            "identityErrors": [],
            "expectedObjects": total_objects,
            "complete": True,
            "integrityStatus": "verified-after-retrieval",
            "verificationMethod": "complete receiver part retrieval plus local multipart compilation",
        }
        if allow_legacy_v11:
            import_manifest = {
                "schemaVersion": "30.2.receiver-import-legacy.1",
                "scanId": scan_id,
                "placeId": place_id,
                "partCount": part_count,
                "expectedParts": part_count,
                "objectCount": total_objects,
                "metadata": metadata,
                "receiverIntegrity": integrity,
                "receiverReportedIntegrity": legacy_integrity,
                "retrievedPartContentDigests": receiver_part_digests,
                "resumableRetrievalEnabled": False,
                "resumedPartCount": 0,
                "downloadedPartCount": downloaded_part_count,
                "resumeCheckpointAuthenticated": False,
                "receiverStoredPayloadDigestsRevalidatedThisRun": False,
                "receiverStoredPayloadDigestsVerified": False,
                "receiverAcknowledgementDigestEquivalent": acknowledgement_equivalent,
                "receiverIntegrityVerified": True,
                "receiverResponseAuthenticityVerified": False,
                "localPayloadEquivalent": False,
                "note": "Explicit legacy v11 import: receiver-reported integrity and complete local retrieval/compilation passed, but the deployment supplied no persisted per-part digest headers; retrieved-byte digests are local observations, not receiver-stored proof",
            }
        else:
            import_manifest = {
                "schemaVersion": "30.2.receiver-import.2",
                "scanId": scan_id,
                "placeId": place_id,
                "partCount": part_count,
                "expectedParts": part_count,
                "objectCount": total_objects,
                "metadata": metadata,
                "receiverIntegrity": integrity,
                "receiverPartContentDigests": receiver_part_digests,
                "resumableRetrievalEnabled": resume_directory is not None,
                "resumedPartCount": len(resumed_parts),
                "downloadedPartCount": downloaded_part_count,
                "resumeCheckpointAuthenticated": False,
                "receiverStoredPayloadDigestsRevalidatedThisRun": not resumed_parts,
                "receiverStoredPayloadDigestsVerified": True,
                "receiverAcknowledgementDigestEquivalent": acknowledgement_equivalent,
                "receiverIntegrityVerified": True,
                "receiverResponseAuthenticityVerified": False,
                "localPayloadEquivalent": False,
                "note": "Downloaded bytes matched receiver-stored upload digests; resumed bytes matched an unauthenticated local checkpoint of prior verification; all parts passed current identity, uniqueness, accounting, and compiler checks; ACK equivalence remains separate from local payload equivalence and response authenticity",
            }
        _write_json(staging / "receiver-manifest.json", import_manifest)
        plan = _compile_scan(staging)
        if output.exists() or output.is_symlink():
            raise ValueError("output path was created during import")
        staging.replace(output)
    return {
        "schemaVersion": import_manifest["schemaVersion"],
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "objectCount": total_objects,
        "featureCount": plan["featureCount"],
        "resumableRetrievalEnabled": resume_directory is not None,
        "resumedPartCount": len(resumed_parts),
        "downloadedPartCount": downloaded_part_count,
        "resumeCheckpointAuthenticated": False,
        "receiverStoredPayloadDigestsRevalidatedThisRun": not resumed_parts and not allow_legacy_v11,
        "receiverStoredPayloadDigestsVerified": not allow_legacy_v11,
        "receiverAcknowledgementDigestEquivalent": acknowledgement_equivalent,
        "receiverIntegrityVerified": True,
        "receiverResponseAuthenticityVerified": False,
        "localPayloadEquivalent": False,
        "output": str(output),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("endpoint", help="HTTPS receiver origin, without a path")
    parser.add_argument("scan_id", help="receiver scan ID from the local manifest")
    parser.add_argument("--output", required=True, help="new directory for verified numbered parts")
    parser.add_argument("--local-manifest",
                        help="optional inspector manifest containing receiver ACK digests")
    parser.add_argument("--resume",
                        help="persistent directory for verified part resume checkpoints")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--allow-legacy-v11", action="store_true",
                        help="explicitly accept v11 parts without persisted digest headers after complete /integrity validation")
    parser.add_argument("--allow-legacy-report-index", action="store_true",
                        help="allow fallback import from paged legacy report records when /metadata is unavailable")
    parser.add_argument("--max-legacy-report-pages", type=int,
                        default=MAX_LEGACY_REPORT_PAGES,
                        help="maximum paged legacy-report index pages to scan during fallback import")
    args = parser.parse_args()
    read_key = os.environ.get("LYCOLES_READ_KEY")
    if not read_key:
        print("IMPORT BLOCKED: LYCOLES_READ_KEY is required", file=sys.stderr)
        return 2
    try:
        result = fetch_scan(args.endpoint, read_key, args.scan_id, args.output,
                            timeout=args.timeout, workers=args.workers,
                            local_manifest=args.local_manifest, resume=args.resume,
                            allow_legacy_v11=args.allow_legacy_v11,
                            allow_legacy_report_index=args.allow_legacy_report_index,
                            max_legacy_report_pages=args.max_legacy_report_pages)
    except (ValueError, OSError) as exc:
        print("IMPORT BLOCKED:", exc, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
