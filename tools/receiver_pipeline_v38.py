#!/usr/bin/env python3
"""v38: assemble receiver batches and plan conservative source-feature diagnostics."""
import argparse
import json
from collections import Counter
from pathlib import Path

def assemble(batches, place_id):
    if type(place_id) is not int or place_id <= 0 or not batches: raise ValueError("Invalid place or batches")
    scan_id = None
    expected = None
    parts = {}
    for batch in batches:
        if not isinstance(batch, dict): raise ValueError("Invalid batch")
        sid, count = batch.get("scanId"), batch.get("expectedParts")
        if not isinstance(sid, str) or not sid or type(count) is not int or not 1 <= count <= 10000:
            raise ValueError("Invalid scan identity")
        if scan_id is None: scan_id, expected = sid, count
        if (sid,count)!=(scan_id,expected) or batch.get("missingParts"):
            raise ValueError("Mixed scan or missing parts")
        for part in batch.get("parts",[]):
            if not isinstance(part,dict): raise ValueError("Invalid part")
            idx=part.get("partIndex")
            if type(idx) is not int or not 1 <= idx <= expected or not isinstance(part.get("objects"),list):
                raise ValueError("Invalid part index or objects")
            if idx in parts and parts[idx]!=part: raise ValueError("Conflicting duplicate part")
            parts[idx]=part
    if set(parts)!=set(range(1,expected+1)): raise ValueError("Incomplete receiver batch coverage")
    if sum(len(x["objects"]) for x in parts.values())>2000000: raise ValueError("Object limit exceeded")
    return {"scanId":scan_id,"placeId":place_id,"expectedParts":expected,
            "parts":[parts[i] for i in range(1,expected+1)]}

def summarize(bundle):
    parts=bundle.get("parts")
    if not isinstance(parts,list) or len(parts)!=bundle.get("expectedParts"): raise ValueError("Incomplete bundle")
    paths=Counter()
    classes=Counter()
    for idx,part in enumerate(parts,1):
        if part.get("partIndex")!=idx or not isinstance(part.get("objects"),list): raise ValueError("Invalid part order")
        for obj in part["objects"]:
            if not isinstance(obj,dict) or not isinstance(obj.get("path"),str) or not obj["path"]:
                raise ValueError("Invalid object path")
            cls=obj.get("class",obj.get("className"))
            if not isinstance(cls,str) or not cls: raise ValueError("Invalid class")
            paths[obj["path"]]+=1
            classes[cls]+=1
    return {"scanId":bundle["scanId"],"placeId":bundle["placeId"],
            "indexedPartsComplete":True,"coverageVerified":False,
            "indexedRecords":sum(paths.values()),"uniquePaths":len(paths),
            "pathCollisions":sum(paths.values())-len(paths),
            "classCounts":dict(sorted(classes.items())),
            "reportedObservations":(parts[0].get("scanStats") or {}).get("recorded"),
            "runtimeVerified":False,"serverOutcomeVerified":False}

def plan(features,bundle):
    if features.get("schemaVersion")!="32.0": raise ValueError("Expected v32 source features")
    summary=summarize(bundle)
    observed=Counter(o["path"] for p in bundle["parts"] for o in p["objects"])
    results=[]
    for feature in features.get("features",[]):
        deps=feature.get("dependencies") or {}
        required=sorted(set(deps.get("paths") or []))
        present=[p for p in required if observed[p]]
        missing=[p for p in required if not observed[p]]
        results.append({"featureId":feature.get("id"),"name":feature.get("name"),
                        "status":"observed-only" if present and not missing else "partial" if present else "not-observed",
                        "observedPaths":present,"missingPaths":missing,
                        "ambiguousPaths":{p:observed[p] for p in present if observed[p]>1},
                        "suggestedDiagnostic":"read-only-path-existence-check" if required else "manual-source-review",
                        "runtimeVerified":False,"approvedForAutomation":False})
    return {"schemaVersion":"38.0","source":"offline-receiver-evidence-planner",
            "scan":summary,"featureCount":len(results),"features":results,
            "gameplayAutomationApproved":False,
            "limitations":["Receiver index does not prove complete game coverage",
                           "No live gameplay or server outcome verified"]}

def read(path):
    path=Path(path)
    if path.stat().st_size>64000000: raise ValueError("Oversized input")
    return json.loads(path.read_text(encoding="utf-8-sig"))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest="command",required=True)
    a=sub.add_parser("assemble")
    a.add_argument("batches",nargs="+",type=Path)
    a.add_argument("--place-id",type=int,required=True)
    a.add_argument("--output",type=Path,default=Path("build/receiver-bundle-v38.json"))
    v=sub.add_parser("validate")
    v.add_argument("bundle",type=Path)
    v.add_argument("--output",type=Path,default=Path("build/receiver-summary-v38.json"))
    m=sub.add_parser("plan")
    m.add_argument("features",type=Path)
    m.add_argument("bundle",type=Path)
    m.add_argument("--output",type=Path,default=Path("build/feature-plan-v38.json"))
    args=parser.parse_args()
    if args.command=="assemble": result=assemble([read(x) for x in args.batches],args.place_id)
    elif args.command=="validate": result=summarize(read(args.bundle))
    else: result=plan(read(args.features),read(args.bundle))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Wrote",args.output)

if __name__=="__main__": main()
