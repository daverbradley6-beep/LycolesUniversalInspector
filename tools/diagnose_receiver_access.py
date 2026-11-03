#!/usr/bin/env python3
"""Diagnose receiver access and deployment compatibility without downloading scans."""
import argparse
import importlib.util
import json
import os
import pathlib
import sys
import urllib.parse
import urllib.request


def _load_fetcher():
    source = pathlib.Path(__file__).with_name("fetch_receiver_scan.py")
    spec = importlib.util.spec_from_file_location("lycoles_receiver_diagnostic_fetcher", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FETCHER = _load_fetcher()


def diagnose(endpoint, read_key, scan_ids, *, timeout=30, allow_http=False,
             check_integrity=False):
    missing = []
    if not endpoint:
        missing.append("LYCOLES_RECEIVER_ORIGIN")
    if not read_key:
        missing.append("LYCOLES_READ_KEY")
    result = {
        "schemaVersion": "30.5.receiver-access-diagnostic.1",
        "status": "blocked-before-network" if missing else "probing",
        "missingConfiguration": missing,
        "receiverOriginConfigured": bool(endpoint),
        "readKeyConfigured": bool(read_key),
        "scanIds": list(scan_ids),
        "checks": [],
        "credentialsExposed": False,
    }
    if missing:
        return result
    origin = FETCHER._receiver_origin(endpoint, allow_http)
    key = FETCHER._read_key(read_key)
    validated_ids = [FETCHER._identifier(scan_id, "receiver scan ID") for scan_id in scan_ids]
    opener = urllib.request.build_opener(FETCHER._NoRedirect)
    for scan_id in validated_ids:
        check = {"scanId": scan_id, "metadataAccessible": False,
                 "partOneAccessible": False, "deploymentContract": "unknown",
                 "integrityChecked": False, "readyForImport": False}
        root = "/reports/" + urllib.parse.quote(key, safe="") + "/" + scan_id
        try:
            metadata_document = FETCHER._read_json(
                opener, origin + root + "/metadata", timeout)
            metadata, place_id, part_count = FETCHER._validate_metadata(
                metadata_document, scan_id)
            check.update({"metadataAccessible": True, "placeId": place_id,
                          "partCount": part_count})
            try:
                FETCHER._read_json(
                    opener, origin + root + "/part-1", timeout, require_digest=True)
                check.update({"partOneAccessible": True,
                              "deploymentContract": "v12-persisted-digests",
                              "readyForImport": True})
            except ValueError as exc:
                if str(exc) != "receiver content digest is missing or invalid":
                    raise
                FETCHER._read_json(
                    opener, origin + root + "/part-1", timeout, return_raw=True)
                check.update({"partOneAccessible": True,
                              "deploymentContract": "v11-no-persisted-digests",
                              "readyForImport": True,
                              "requiresExplicitLegacyFlag": True})
            if check_integrity:
                integrity = FETCHER._validate_legacy_integrity(
                    FETCHER._read_json(opener, origin + root + "/integrity", timeout),
                    scan_id, place_id, part_count)
                check.update({"integrityChecked": True,
                              "receiverReportedComplete": integrity["complete"]})
        except (ValueError, OSError) as exc:
            check["error"] = str(exc)
            check["readyForImport"] = False
        result["checks"].append(check)
    result["status"] = (
        "ready" if result["checks"] and all(item["readyForImport"] for item in result["checks"])
        else "blocked")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scan_ids", nargs="+", help="receiver scan IDs to probe")
    parser.add_argument("--endpoint", help="HTTPS receiver origin; defaults to LYCOLES_RECEIVER_ORIGIN")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--check-integrity", action="store_true",
                        help="also run the receiver's potentially expensive integrity endpoint")
    args = parser.parse_args()
    endpoint = args.endpoint or os.environ.get("LYCOLES_RECEIVER_ORIGIN")
    read_key = os.environ.get("LYCOLES_READ_KEY")
    try:
        result = diagnose(endpoint, read_key, args.scan_ids, timeout=args.timeout,
                          check_integrity=args.check_integrity)
    except (ValueError, OSError) as exc:
        result = {"schemaVersion": "30.5.receiver-access-diagnostic.1",
                  "status": "blocked-before-network", "error": str(exc),
                  "credentialsExposed": False}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "ready" else 2


if __name__ == "__main__":
    sys.exit(main())
