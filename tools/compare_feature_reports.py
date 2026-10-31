#!/usr/bin/env python3
"""Lycoles v32 feature-level structural drift comparison.

Compare two offline feature reports to identify added, removed, or changed
source dependencies. This is a repair triage report, not an automatic patch.
"""
import argparse
import json
from pathlib import Path

def signature(feature):
    dep=feature.get("dependencies") or {}
    return {k:sorted(set(dep.get(k) or [])) for k in ("paths","lookups","services")}
def compare(old,new):
    if old.get("schemaVersion")!="32.0" or new.get("schemaVersion")!="32.0":
        raise ValueError("Both reports must be v32")
    def index(doc):
        result={}
        for f in doc.get("features",[]):
            key=(f.get("sourceFile"),f.get("name"))
            if key in result:raise ValueError("Duplicate source/name; compare requires unique function names per file")
            result[key]=f
        return result
    a=index(old);b=index(new)
    changes=[]
    for key in sorted(set(a)|set(b)):
        x=a.get(key);y=b.get(key)
        if x is None:
            changes.append({"sourceFile":key[0],"name":key[1],"change":"added","newDependencies":signature(y)})
        elif y is None:
            changes.append({"sourceFile":key[0],"name":key[1],"change":"removed","oldDependencies":signature(x)})
        elif signature(x)!=signature(y):
            before=signature(x);after=signature(y)
            changes.append({"sourceFile":key[0],"name":key[1],"change":"dependency-drift",
                            "added":{k:sorted(set(after[k])-set(before[k])) for k in before},
                            "removed":{k:sorted(set(before[k])-set(after[k])) for k in before}})
    return {"schemaVersion":"32.0","source":"offline-feature-diff",
            "oldFeatures":len(a),"newFeatures":len(b),"changes":changes,
            "changeCount":len(changes),
            "verifiedRepairCount":0,
            "notice":"Static structural changes only. No game-side patch or runtime verification."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("old",type=Path);p.add_argument("new",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/feature-drift.json"))
    args=p.parse_args()
    result=compare(json.loads(args.old.read_text(encoding="utf-8")),
                   json.loads(args.new.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Detected",result["changeCount"],"feature changes")
if __name__=="__main__":main()
