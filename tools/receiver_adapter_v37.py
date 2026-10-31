#!/usr/bin/env python3
"""Normalize receiver-indexed dynamic observations without claiming snapshot completeness."""
import argparse
import json
from collections import Counter
from pathlib import Path

VERSION = "37.0"

def adapt(bundle):
    if not isinstance(bundle, dict): raise ValueError("Invalid bundle")
    scan_id, place_id = bundle.get("scanId"), bundle.get("placeId")
    expected, parts = bundle.get("expectedParts"), bundle.get("parts")
    if not isinstance(scan_id, str) or not scan_id or type(place_id) is not int or place_id <= 0:
        raise ValueError("Missing scan identity")
    if type(expected) is not int or not 1 <= expected <= 10000 or not isinstance(parts, list) or len(parts) != expected:
        raise ValueError("Incomplete receiver parts")
    indexed = {}
    for part in parts:
        if not isinstance(part, dict): raise ValueError("Invalid part")
        idx = part.get("partIndex")
        if type(idx) is not int or idx < 1 or idx > expected or idx in indexed or not isinstance(part.get("objects"), list):
            raise ValueError("Invalid or duplicate part")
        indexed[idx] = part
    if set(indexed) != set(range(1, expected + 1)): raise ValueError("Missing parts")
    objects, counts = [], Counter()
    for idx in range(1, expected + 1):
        for ordinal, obj in enumerate(indexed[idx]["objects"]):
            if not isinstance(obj, dict) or not isinstance(obj.get("path"), str) or not obj["path"]:
                raise ValueError("Invalid object path")
            path, cls = obj["path"], obj.get("class", obj.get("className"))
            if not isinstance(cls, str) or not cls: raise ValueError("Invalid object class")
            objects.append({"path":path,"name":path.rsplit(".",1)[-1],"className":cls,
                            "scanOrdinal":obj.get("scanOrdinal"),"partIndex":idx,"observationIndex":ordinal})
            counts[path] += 1
            if len(objects) > 2000000: raise ValueError("Too many objects")
    stats = indexed[1].get("scanStats")
    return {"schemaVersion":VERSION,"source":"receiver-indexed-dynamic-observations",
            "scanId":scan_id,"placeId":place_id,"objects":objects,
            "integrity":{"indexedPartsComplete":True,"scanComplete":False,
                         "expectedParts":expected,"indexedParts":len(parts),
                         "indexedObjectRecords":len(objects),
                         "reportedRecordedObservations":stats.get("recorded") if isinstance(stats,dict) else None,
                         "uniquePaths":len(counts),"pathCollisions":sum(n-1 for n in counts.values()),
                         "coverageVerified":False},
            "runtimeVerified":False,"serverOutcomeVerified":False,
            "notice":"Receiver index complete; source coverage and gameplay effects unverified."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/receiver-objects-v37.json"))
    a=p.parse_args()
    report=adapt(json.loads(a.bundle.read_text(encoding="utf-8-sig")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Indexed",report["integrity"]["indexedParts"],"parts;",len(report["objects"]),"objects; coverage unverified")

if __name__=="__main__": main()
