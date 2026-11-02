#!/usr/bin/env python3
"""Download a verified receiver scan for the offline pipeline.

The receiver read key is accepted only through LYCOLES_READ_KEY. The importer
requires HTTPS, does not follow redirects, publishes atomically, and never claims
that receiver bytes equal the inspector's original local payloads.
"""
import argparse
import concurrent.futures
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


def _read_json_once(opener, url, timeout):
    request = urllib.request.Request(url, headers={"Accept": "application/json",
                                                   "User-Agent": "Lycoles-receiver-import/30.1"})
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
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("receiver JSON exceeds size limit")
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("receiver returned invalid JSON") from None
    if not isinstance(document, dict):
        raise ValueError("receiver JSON must be an object")
    return document


def _read_json(opener, url, timeout):
    transient_statuses = {408, 425, 429, 500, 502, 503, 504}
    for attempt in range(3):
        try:
            return _read_json_once(opener, url, timeout)
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
    return "|".join((_worker_string(item.get("class") or item.get("className")),
                     _worker_string(item.get("path")),
                     _worker_string(item.get("scanOrdinal"))))


def _write_json(path, document):
    path.write_text(json.dumps(document, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n", encoding="utf-8")


def _compile_scan(directory):
    source = pathlib.Path(__file__).with_name("compile_scan.py")
    spec = importlib.util.spec_from_file_location("lycoles_receiver_compile_scan", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.compile_scan(directory)


def fetch_scan(endpoint, read_key, scan_id, output, *, timeout=30, workers=4,
               allow_http=False):
    origin = _receiver_origin(endpoint, allow_http)
    read_key = _read_key(read_key)
    scan_id = _identifier(scan_id, "receiver scan ID")
    if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 1 <= timeout <= 120:
        raise ValueError("invalid receiver timeout")
    workers = _positive_integer(workers, "worker count", MAX_WORKERS)
    output = pathlib.Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError("output path already exists")
    output.parent.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(_NoRedirect)
    root = "/reports/" + urllib.parse.quote(read_key, safe="") + "/" + scan_id
    metadata_document = _read_json(opener, origin + root + "/metadata", timeout)
    metadata, place_id, part_count = _validate_metadata(metadata_document, scan_id)

    with tempfile.TemporaryDirectory(prefix=".lycoles-receiver-", dir=output.parent) as temp:
        staging = pathlib.Path(temp)
        total_objects = 0
        object_keys = set()

        def retrieve(index):
            return index, _read_json(opener, origin + root + f"/part-{index}", timeout)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for start in range(1, part_count + 1, workers * 2):
                indexes = list(range(start, min(part_count + 1, start + workers * 2)))
                for index, part in executor.map(retrieve, indexes):
                    objects = _validate_part(part, scan_id, place_id, part_count, index)
                    for item in objects:
                        key = _object_key(item)
                        if key in object_keys:
                            raise ValueError("duplicate receiver object identity")
                        object_keys.add(key)
                    total_objects += len(objects)
                    if total_objects > MAX_OBJECTS:
                        raise ValueError("receiver object count exceeds safety limit")
                    _write_json(staging / f"part-{index:04d}.json", part)
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
        local_manifest = {
            "schemaVersion": "30.1.receiver-import.1",
            "scanId": scan_id,
            "placeId": place_id,
            "partCount": part_count,
            "expectedParts": part_count,
            "objectCount": total_objects,
            "metadata": metadata,
            "receiverIntegrity": integrity,
            "receiverIntegrityVerified": True,
            "receiverResponseAuthenticityVerified": False,
            "localPayloadEquivalent": False,
            "note": "All receiver parts were retrieved and locally passed identity, uniqueness, accounting, and compiler checks; original local payload equivalence was not established",
        }
        _write_json(staging / "receiver-manifest.json", local_manifest)
        plan = _compile_scan(staging)
        if output.exists() or output.is_symlink():
            raise ValueError("output path was created during import")
        staging.replace(output)
    return {
        "schemaVersion": "30.1.receiver-import.1",
        "scanId": scan_id,
        "placeId": place_id,
        "partCount": part_count,
        "objectCount": total_objects,
        "featureCount": plan["featureCount"],
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
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    read_key = os.environ.get("LYCOLES_READ_KEY")
    if not read_key:
        print("IMPORT BLOCKED: LYCOLES_READ_KEY is required", file=sys.stderr)
        return 2
    try:
        result = fetch_scan(args.endpoint, read_key, args.scan_id, args.output,
                            timeout=args.timeout, workers=args.workers)
    except (ValueError, OSError) as exc:
        print("IMPORT BLOCKED:", exc, file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
