#!/usr/bin/env python3
"""Compare local inspection metadata with receiver index or integrity diagnostics.

A verified receiver response establishes stored multipart availability, not byte-for-byte
identity with local payloads unless matching part hashes are also available.
"""
import argparse
import json
from pathlib import Path

def _direct_integrity(local, receiver, scan_id, place_id):
    base={"schemaVersion":"24.1","scanId":scan_id,"placeId":place_id,
          "receiverIntegrityVerified":False,"downstreamReportAvailable":False,
          "receiverResponseAuthenticityVerified":False,"verifiedEquivalent":False}
    if receiver.get("scanId")!=scan_id:
        return {**base,"status":"SCAN_ID_MISMATCH"}
    if receiver.get("placeId")!=place_id:
        return {**base,"status":"PLACE_MISMATCH"}
    expected=local.get("expectedParts")
    local_objects=local.get("objectCount")
    part_count=receiver.get("partCount")
    received=receiver.get("receivedParts")
    missing=receiver.get("missingParts")
    identity_errors=receiver.get("identityErrors")
    indexed=receiver.get("indexedObjects")
    unique=receiver.get("uniqueObjectKeys")
    duplicates=receiver.get("duplicateObjectKeys")
    expected_objects=receiver.get("expectedObjects")
    integers=(expected,local_objects,part_count,received,indexed,unique,duplicates,expected_objects)
    metadata_valid=(all(type(value) is int and value>=0 for value in integers)
                    and expected>0 and part_count>0
                    and isinstance(missing,list) and isinstance(identity_errors,list))
    verified=(metadata_valid and receiver.get("complete") is True
              and receiver.get("integrityStatus")=="verified"
              and part_count==expected and received==expected
              and not missing and not identity_errors and duplicates==0
              and local_objects==expected_objects==indexed==unique)
    if verified:
        return {**base,"status":"RECEIVER_INTEGRITY_VERIFIED",
                "receiverIntegrityVerified":True,"downstreamReportAvailable":True,
                "verifiedScope":"Receiver-stored multipart identity and object accounting",
                "reason":"Receiver integrity passed; local payload equivalence still requires matching part hashes."}
    return {**base,"status":"RECEIVER_INTEGRITY_INCOMPLETE",
            "expectedLocalParts":expected,"receivedReceiverParts":received,
            "expectedLocalObjects":local_objects,"indexedReceiverObjects":indexed,
            "missingParts":missing if isinstance(missing,list) else None,
            "identityErrors":identity_errors if isinstance(identity_errors,list) else None,
            "reason":"Receiver integrity is incomplete or inconsistent; downstream processing remains blocked."}


def compare(local, receiver):
    if not isinstance(local, dict) or not isinstance(receiver, dict):
        raise ValueError("Both inputs must be JSON objects")
    scan_id = local.get("scanId") or local.get("scanID")
    place_id = local.get("placeId")
    if not isinstance(scan_id, str) or not scan_id.strip():
        raise ValueError("Local scanId required")
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("Local placeId required")
    if "complete" in receiver and "partCount" in receiver:
        return _direct_integrity(local,receiver,scan_id,place_id)
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
    local_hashes=local.get("partHashes")
    remote_hashes=match.get("partHashes")
    if isinstance(local_hashes,dict) and isinstance(remote_hashes,dict):
        if set(local_hashes)!=set(remote_hashes):
            return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                    "status":"PART_HASH_SET_MISMATCH","verifiedEquivalent":False}
        if any(not isinstance(v,str) or len(v)!=64 for v in local_hashes.values()):
            raise ValueError("Expected SHA-256 hex digests")
        if any(local_hashes[k]!=remote_hashes[k] for k in local_hashes):
            return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                    "status":"PART_HASH_MISMATCH","verifiedEquivalent":False}
        if len(local_hashes)==expected and expected==receiver_expected and indexed==expected:
            return {"schemaVersion":"24.0","scanId":scan_id,"placeId":place_id,
                    "status":"PART_HASHES_MATCH","verifiedEquivalent":True,
                    "verifiedScope":"All declared part payload hashes only"}
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
    p.add_argument("local",help="local inspector manifest JSON")
    p.add_argument("receiver",help="receiver index or /integrity response JSON")
    p.add_argument("--output",default="build/receiver-reconciliation.json")
    a=p.parse_args()
    result=compare(json.loads(Path(a.local).read_text()),
                   json.loads(Path(a.receiver).read_text()))
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(result["status"])
if __name__=="__main__":main()
