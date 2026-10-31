#!/usr/bin/env python3
"""Compare local inspection metadata with receiver index and diagnostics.

Never equate an indexed part count with complete upload verification.
"""
import argparse
import json
from pathlib import Path

def compare(local, receiver):
    if not isinstance(local, dict) or not isinstance(receiver, dict):
        raise ValueError("Both inputs must be JSON objects")
    scan_id = local.get("scanId") or local.get("scanID")
    place_id = local.get("placeId")
    if not isinstance(scan_id, str) or not scan_id.strip():
        raise ValueError("Local scanId required")
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("Local placeId required")
    entries = receiver.get("scans")
    if not isinstance(entries, list):
        raise ValueError("Receiver scans list required")
    matches = [x for x in entries if isinstance(x, dict) and x.get("scanId") == scan_id]
    if not matches:
        return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                "status":"NOT_FOUND_IN_PROVIDED_INDEX",
                "indexExhaustive":receiver.get("hasMore") is False,
                "verifiedEquivalent":False,
                "reason":"The receiver listing supplied does not contain the exact scan ID."}
    if len(matches) != 1:
        raise ValueError("Duplicate receiver scan IDs")
    match = matches[0]
    if match.get("placeId") != place_id:
        return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                "status":"PLACE_MISMATCH","verifiedEquivalent":False}
    expected = local.get("expectedParts")
    indexed = match.get("indexedParts")
    receiver_expected = match.get("expectedParts")
    if any(type(x) is not int or x < 1 for x in (expected,indexed,receiver_expected)):
        return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                "status":"INSUFFICIENT_PART_METADATA","verifiedEquivalent":False}
    if expected != receiver_expected or indexed != expected:
        status = "PART_COUNT_MISMATCH"
    else:
        status = "PART_COUNTS_MATCH_UNVERIFIED"
    return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
            "status":status,"expectedLocalParts":expected,
            "expectedReceiverParts":receiver_expected,"indexedReceiverParts":indexed,
            "verifiedEquivalent":False,
            "reason":"Matching part counts alone cannot prove payload equivalence; compare part hashes and object accounting."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("local");p.add_argument("receiver")
    p.add_argument("--output",default="build/receiver-reconciliation.json")
    a=p.parse_args()
    result=compare(json.loads(Path(a.local).read_text()),
                   json.loads(Path(a.receiver).read_text()))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(result["status"])
if __name__=="__main__":main()
