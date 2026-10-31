#!/usr/bin/env python3
"""Lycoles v35 offline inspection-to-feature evidence bridge. No game execution."""
import argparse
import json
import pathlib
import re

VERSION="35.0"
SAFE=re.compile(r"^(?:game|workspace|Workspace|ReplicatedStorage|Players|PlayerGui|Lighting|StarterGui)(?:\.[A-Za-z_]\w*){0,16}$")
def load(path):
    p=pathlib.Path(path)
    if p.stat().st_size>32000000:raise ValueError("Input too large")
    return json.loads(p.read_text(encoding="utf-8-sig"))
def normalize(raw):
    if not isinstance(raw,dict):raise ValueError("Invalid inspection")
    container=raw.get("data") if isinstance(raw.get("data"),dict) else raw
    place=container.get("placeId",raw.get("placeId"))
    scan=container.get("scanId",raw.get("scanId"))
    objects=container.get("objects",container.get("instances"))
    if type(place) is not int or place<=0 or not isinstance(scan,str) or not scan.strip():
        raise ValueError("Explicit placeId and scanId required")
    if not isinstance(objects,list) or len(objects)>200000:raise ValueError("Invalid objects list")
    found={};rejected=0
    for o in objects:
        if not isinstance(o,dict) or not isinstance(o.get("path"),str) or not SAFE.fullmatch(o["path"]):
            rejected+=1;continue
        path=o["path"]
        name=o.get("name")
        if not isinstance(name,str):name=path.rsplit(".",1)[-1]
        found[path]={"path":path,"name":name[:128],"className":o.get("className",o.get("class"))}
    return {"schemaVersion":VERSION,"source":"offline-inspection-normalized",
            "placeId":place,"scanId":scan,"objectCount":len(found),
            "rejectedObjects":rejected,"objects":[found[k] for k in sorted(found)]}
def bridge(features,inspection,audit=None):
    if features.get("schemaVersion")!="32.0" or inspection.get("schemaVersion")!=VERSION:
        raise ValueError("Expected v32 features and v35 inspection")
    fs=features.get("features")
    if not isinstance(fs,list) or len(fs)>10000:raise ValueError("Invalid features")
    if audit is not None and audit.get("schemaVersion")!="34.0":raise ValueError("Invalid v34 audit")
    evidence={f.get("featureId"):f.get("status") for f in (audit or {}).get("features",[])}
    paths={o["path"]:o for o in inspection["objects"]}
    names={}
    for o in inspection["objects"]:names.setdefault(o["name"],[]).append(o["path"])
    results=[]
    for f in fs:
        dep=f.get("dependencies") or {}
        required=sorted(set(p for p in dep.get("paths",[]) if isinstance(p,str)))
        lookups=sorted(set(n for n in dep.get("lookups",[]) if isinstance(n,str)))
        exact=[p for p in required if p in paths]
        missing=[p for p in required if p not in paths]
        status=("no-static-dependencies" if not required and not lookups else
                "exact-paths-observed" if required and not missing else
                "partial-path-evidence" if exact else "unresolved")
        results.append({"featureId":f.get("id"),"sourceFile":f.get("sourceFile"),
            "name":f.get("name"),"status":status,
            "lexicalStatus":evidence.get(f.get("id"),"not-provided"),
            "exactPaths":exact,"missingPaths":missing,
            "uniqueNameHints":{n:names[n][0] for n in lookups if len(names.get(n,[]))==1},
            "ambiguousNameHints":{n:names[n][:10] for n in lookups if len(names.get(n,[]))>1},
            "missingNames":[n for n in lookups if n not in names],
            "runtimeVerified":False,"serverOutcomeVerified":False,"reviewRequired":True})
    return {"schemaVersion":VERSION,"source":"offline-feature-inspection-bridge",
            "placeId":inspection["placeId"],"scanId":inspection["scanId"],
            "featureCount":len(results),"features":results,
            "limitations":["Name matches are hints, not identity","Path presence is not gameplay success",
                           "No remote invocations or runtime testing"]}
def propose(result):
    if result.get("schemaVersion")!=VERSION or result.get("source")!="offline-feature-inspection-bridge":
        raise ValueError("Expected v35 bridge report")
    proposals=[]
    for f in result["features"]:
        if not f["exactPaths"]:continue
        name="Inspect_"+re.sub(r"[^A-Za-z0-9_]","_",str(f.get("name") or "Feature"))[:40]
        proposals.append({"name":name,"action":"read_object_presence","paths":f["exactPaths"][:20],
                          "reviewed":False,"sourceFeatureId":f["featureId"],
                          "reviewNote":"Confirm place and paths before approval"})
    return {"schemaVersion":"33.0","placeId":result["placeId"],
            "features":proposals[:100],"reviewStatus":"requires-explicit-approval",
            "runtimeVerified":False}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("feature_report",type=pathlib.Path)
    p.add_argument("inspection",type=pathlib.Path)
    p.add_argument("--audit",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/inspection-bridge-v35.json"))
    p.add_argument("--proposals",type=pathlib.Path,default=pathlib.Path("build/inspection-proposals-v35.json"))
    a=p.parse_args()
    result=bridge(load(a.feature_report),normalize(load(a.inspection)),load(a.audit) if a.audit else None)
    for path,doc in ((a.output,result),(a.proposals,propose(result))):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Matched",result["featureCount"],"features; proposed",len(propose(result)["features"]),"unreviewed diagnostics")
if __name__=="__main__":main()
