#!/usr/bin/env python3
"""v33: propose read-only diagnostic specifications from v32 evidence.

All generated features remain unreviewed. Human approval is required before
generate_diagnostic_gui.py will compile a runnable GUI.
"""
import argparse
import json
import pathlib
import re

VERSION="33.0"
VALID=re.compile(r"^(?:game|workspace|Workspace|ReplicatedStorage|Players|PlayerGui)(?:\.[A-Za-z_]\w*){0,12}$")
def propose(report,place_id):
    if report.get("schemaVersion")!="32.0":raise ValueError("Expected v32 feature report")
    if type(place_id) is not int or place_id<=0:raise ValueError("Invalid placeId")
    features=[];seen=set()
    for item in report.get("features",[]):
        paths=item.get("dependencies",{}).get("paths",[])
        usable=sorted(set(p for p in paths if isinstance(p,str) and VALID.fullmatch(p)))[:20]
        if not usable:continue
        name="Inspect_"+re.sub(r"[^A-Za-z0-9_]","_",item.get("name","feature"))[:40]
        if name in seen:continue
        seen.add(name)
        features.append({"name":name,"reviewed":False,"action":"read_object_presence",
                         "paths":usable,"sourceFeatureId":item.get("id"),
                         "reviewNote":"Check these exact paths against your live inspection before approval"})
        if len(features)>=100:break
    return {"schemaVersion":VERSION,"placeId":place_id,"features":features,
            "reviewStatus":"requires-explicit-approval",
            "notice":"No feature is automatically approved. Review paths and set reviewed=true individually."}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("feature_report",type=pathlib.Path)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/proposed-diagnostics.json"))
    a=p.parse_args()
    report=json.loads(a.feature_report.read_text(encoding="utf-8"))
    result=propose(report,a.place_id)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Proposed",len(result["features"]),"unreviewed diagnostics; approval required")
if __name__=="__main__":main()
