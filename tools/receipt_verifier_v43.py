#!/usr/bin/env python3
"""v43: correlate live client path-check receipts with an evidence manifest."""
import argparse
import json
from pathlib import Path

MAX_SIZE=8_000_000
MAX_CHECKS=10000

def verify(manifest, receipt):
    if not isinstance(manifest,dict) or manifest.get("schemaVersion")!="42.0":
        raise ValueError("Expected v42 manifest")
    if not isinstance(receipt,dict) or receipt.get("schemaVersion")!="43.0":
        raise ValueError("Expected v43 receipt")
    for key in ("scanId","placeId","sourceFingerprint"):
        if key not in manifest or receipt.get(key)!=manifest[key]:
            raise ValueError("Receipt does not match manifest: "+key)
    if type(receipt["placeId"]) is not int:
        raise ValueError("Invalid place ID")
    features=manifest.get("features")
    checks=receipt.get("checks")
    if not isinstance(features,list) or not isinstance(checks,list) or len(checks)>MAX_CHECKS:
        raise ValueError("Invalid feature or check list")
    expected={}
    for feature in features:
        if feature.get("kind")!="read-only-inspection" or feature.get("gameplayVerified") is not False:
            raise ValueError("Unexpected feature contract")
        for path in feature.get("evidencePaths",[]):
            if not isinstance(path,str) or len(path)>1024:
                raise ValueError("Invalid manifest path")
            if path in expected:
                expected[path].add(feature["id"])
            else:
                expected[path]={feature["id"]}
    seen={}
    for check in checks:
        if not isinstance(check,dict) or set(check)!={"path","found"}:
            raise ValueError("Invalid check")
        path=check["path"]
        if not isinstance(path,str) or path not in expected or path in seen:
            raise ValueError("Unknown or repeated path")
        if type(check["found"]) is not bool:
            raise ValueError("Nonboolean path result")
        seen[path]=check["found"]
    result=[]
    for feature in features:
        paths=feature["evidencePaths"]
        present=sum(seen.get(path) is True for path in paths)
        tested=sum(path in seen for path in paths)
        result.append({"id":feature["id"],"testedPaths":tested,"totalPaths":len(paths),
                       "foundPaths":present,"missingPaths":tested-present,
                       "unobservedPaths":len(paths)-tested,
                       "pathCheckComplete":tested==len(paths),
                       "mechanicVerified":False,"gameplayAutomationApproved":False})
    return {"schemaVersion":"43.0","placeId":manifest["placeId"],"scanId":manifest["scanId"],
            "sourceFingerprint":manifest["sourceFingerprint"],"checksReceived":len(seen),
            "checksExpected":len(expected),"complete":len(seen)==len(expected),
            "features":result,"clientReceiptUntrusted":True,
            "runtimeVerified":False,"serverOutcomeVerified":False,
            "gameplayAutomationApproved":False,
            "limitations":["Client-submitted receipt is not independently authenticated",
                           "Path existence is not evidence of gameplay functionality"]}

def read(path):
    p=Path(path)
    if p.stat().st_size>MAX_SIZE:raise ValueError("Input too large")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("receipt",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/receipt-verification-v43.json"))
    a=p.parse_args()
    result=verify(read(a.manifest),read(a.receipt))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Verified receipt structure:",result["checksReceived"],"/",result["checksExpected"],
          "path checks; independent runtime verification unavailable")

if __name__=="__main__":main()
