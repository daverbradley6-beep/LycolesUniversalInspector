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
    collection_root = "/reports/" + urllib.parse.quote(key, safe="")
    collection = {"accessible": False, "requestedScansListed": {
        scan_id: False for scan_id in validated_ids}}
    try:
        collection_document = FETCHER._read_json(
            opener, origin + collection_root, timeout)
        scans = collection_document.get("scans") if isinstance(collection_document, dict) else None
        reports = collection_document.get("reports") if isinstance(collection_document, dict) else None
        has_more = collection_document.get("hasMore") if isinstance(collection_document, dict) else None
        if (isinstance(scans, list) and reports is None
                and all(isinstance(item, str) for item in scans)):
            listed = scans
            collection_contract = "multipart-scans"
        elif (isinstance(reports, list) and scans is None
              and all(isinstance(item, str) for item in reports)):
            listed = reports
            collection_contract = "legacy-single-reports"
        else:
            raise ValueError("receiver collection response is invalid")
        if type(has_more) is not bool:
            raise ValueError("receiver collection response is invalid")
        listed_set = set(listed)
        collection.update({"accessible": True, "collectionContract": collection_contract,
                           "listedRecordCount": len(listed), "hasMore": has_more,
                           "requestedScansListed": {
                               scan_id: scan_id in listed_set for scan_id in validated_ids}})
    except (ValueError, OSError) as exc:
        collection["error"] = str(exc)
    result["collection"] = collection

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
    if (collection["accessible"]
            and collection["collectionContract"] == "legacy-single-reports"):
        for check in result["checks"]:
            check["readyForImport"] = False
            check["collectionContractBlocker"] = "pre-multipart-single-report-storage"
    result["status"] = (
        "ready" if (collection["accessible"]
                    and collection["collectionContract"] == "multipart-scans"
                    and result["checks"]
                    and all(item["readyForImport"] for item in result["checks"]))
        else "blocked")
    if not collection["accessible"]:
        result["diagnosis"] = "receiver-origin-or-read-key-route-not-recognized"
    elif collection["collectionContract"] == "legacy-single-reports":
        if any(collection["requestedScansListed"].values()):
            result["diagnosis"] = "requested-records-are-legacy-single-reports"
        elif collection["hasMore"]:
            result["diagnosis"] = "requested-records-not-in-first-legacy-page"
        else:
            result["diagnosis"] = "requested-records-not-listed-in-legacy-collection"
    elif (not collection["hasMore"]
          and not any(collection["requestedScansListed"].values())):
        result["diagnosis"] = "requested-scans-not-listed"
    elif result["status"] == "ready":
        result["diagnosis"] = "requested-scans-ready"
    else:
        result["diagnosis"] = "requested-scans-require-individual-check-review"

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
