#!/usr/bin/env python3
"""Conservative feature matching against receiver observations."""
import argparse
import json
from collections import Counter
from pathlib import Path

def match(features, scan):
    if features.get("schemaVersion")!="32.0" or scan.get("schemaVersion")!="37.0":
        raise ValueError("Expected v32 features and v37 receiver scan")
    if not scan.get("integrity",{}).get("indexedPartsComplete"):
        raise ValueError("Incomplete receiver parts")
    paths=Counter(o["path"] for o in scan["objects"])
    names=Counter(o["name"] for o in scan["objects"])
    results=[]
    for f in features.get("features",[]):
        dep=f.get("dependencies") or {}
        required=sorted(set(dep.get("paths") or []))
        hints=sorted(set(dep.get("lookups") or []))
        observed=[p for p in required if paths[p]]
        missing=[p for p in required if not paths[p]]
        results.append({"featureId":f.get("id"),"name":f.get("name"),
                        "status":"observed-only" if observed and not missing else "partially-observed" if observed else "not-observed",
                        "observedPaths":observed,"missingPaths":missing,
                        "ambiguousPaths":{p:paths[p] for p in observed if paths[p]>1},
                        "nameHints":{n:names[n] for n in hints if names[n]},
                        "runtimeVerified":False,"serverOutcomeVerified":False,
                        "approvedForAutomation":False})
    return {"schemaVersion":"37.0","source":"receiver-feature-evidence-match",
            "placeId":scan["placeId"],"scanId":scan["scanId"],
            "features":results,"featureCount":len(results),
            "coverageVerified":False,"gameplayAutomationApproved":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("features",type=Path)
    p.add_argument("scan",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/receiver-feature-match-v37.json"))
    a=p.parse_args()
    report=match(json.loads(a.features.read_text(encoding="utf-8")),json.loads(a.scan.read_text(encoding="utf-8")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Matched",report["featureCount"],"features; no gameplay execution verified")

if __name__=="__main__":main()
