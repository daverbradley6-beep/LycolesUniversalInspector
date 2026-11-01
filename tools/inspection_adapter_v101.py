#!/usr/bin/env python3
"""v101 adapter: normalize client-visible inspection exports for v100.

Offline and read-only. Unknown object formats are rejected or reported,
never converted into invented object paths or executable actions.
"""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from client_observer_compiler_v100 import generate, audit, validate

ROOTS={"Workspace","PlayerGui","ReplicatedStorage","Players"}
PROPERTIES={"Name","ClassName","Visible","Text","Value","Enabled"}
SEGMENT=re.compile(r"^[A-Za-z0-9_ .:-]{1,80}$")

def _path(value):
    if isinstance(value,list):
        parts=value[:]
    elif isinstance(value,str):
        parts=value.split(".")
        if parts and parts[0]=="game":
            parts=parts[1:]
    else:
        return None
    if len(parts)<2 or len(parts)>12 or parts[0] not in ROOTS:
        return None
    if not all(isinstance(p,str) and SEGMENT.fullmatch(p) for p in parts):
        return None
    return parts

def _candidates(document):
    if isinstance(document,list):
        return document
    if not isinstance(document,dict):
        raise ValueError("inspection export must be an object or array")
    for key in ("observations","objects","instances","entries"):
        value=document.get(key)
        if isinstance(value,list):
            return value
    raise ValueError("no recognized object collection")

def adapt(document,place_id,max_items=150):
    if type(place_id)!=int or place_id<=0:
        raise ValueError("invalid place ID")
    if type(max_items)!=int or not 1<=max_items<=150:
        raise ValueError("invalid max items")
    rows=_candidates(document)
    observations=[]
    counts=Counter()
    used=set()
    for index,row in enumerate(rows):
        if not isinstance(row,dict):
            counts["invalid_entry"]+=1
            continue
        raw=row.get("path",row.get("fullName",row.get("fullPath")))
        path=_path(raw)
        if path is None:
            counts["unsupported_path"]+=1
            continue
        prop=row.get("property")
        if prop is None:
            # Conservative inference: the presence of a value is not proof
            # that a property is readable. Prefer identity-only observation.
            prop="Name"
        if prop not in PROPERTIES:
            counts["unsupported_property"]+=1
            continue
        name=row.get("id")
        if not isinstance(name,str) or not SEGMENT.fullmatch(name):
            name="Object"+str(index+1)
        base=name
        suffix=2
        while name in used:
            name=(base[:65]+"_"+str(suffix))
            suffix+=1
        used.add(name)
        label=row.get("label")
        if not isinstance(label,str) or not 1<=len(label)<=100:
            label=name
        observations.append({"id":name,"path":path,"property":prop,"label":label})
        if len(observations)>=max_items:
            counts["limit_reached"]+=max(0,len(rows)-index-1)
            break
    if not observations:
        raise ValueError("no supported client-visible observations")
    report={"schemaVersion":"100.client-observations",
            "placeId":place_id,"observations":observations}
    validate(report)
    return report,{"schemaVersion":"101.adapter","inputEntries":len(rows),
        "accepted":len(observations),"rejected":sum(v for k,v in counts.items() if k!="limit_reached"),
        "reasons":dict(sorted(counts.items())),
        "inferredProperties":"Name only when unspecified",
        "verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--inspection",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v101"))
    p.add_argument("--max-items",type=int,default=150)
    args=p.parse_args()
    document=json.loads(args.inspection.read_text(encoding="utf-8-sig"))
    report,summary=adapt(document,args.place_id,args.max_items)
    manifest=generate(report,args.output)
    result=audit(args.output)
    if not result["ok"]:
        raise RuntimeError("generated v100 artifact failed audit: "+repr(result["issues"]))
    (args.output/"adapter-v101.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"summary":summary,"manifest":manifest,
                      "auditPassed":True,"verifiedInGame":False}))
if __name__=="__main__":
    main()
