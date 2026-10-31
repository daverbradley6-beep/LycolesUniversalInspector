#!/usr/bin/env python3
"""Bridge observed scan evidence into a reviewable, schema-valid action contract template.

No approval is inferred. Users must independently review each proposed operation
before changing reviewed to true and passing it to the release builder.
"""
import argparse
import json
from pathlib import Path

def make_template(plan, proposals):
    integrity=plan.get("integrity") or {}
    place=integrity.get("placeId")
    scan=integrity.get("scanId")
    if integrity.get("scanComplete") is not True or type(place) is not int or place<1:
        raise ValueError("Complete scan required")
    if proposals.get("placeId")!=place or proposals.get("scanId")!=scan:
        raise ValueError("Proposals must originate from same scan")
    features={f.get("feature") for f in plan.get("features",[]) if isinstance(f,dict)}
    candidates=proposals.get("proposals")
    if not isinstance(candidates,list):raise ValueError("Invalid proposals")
    contracts=[]
    seen=set()
    for candidate in candidates:
        if not isinstance(candidate,dict):raise ValueError("Malformed proposal")
        feature=candidate.get("feature")
        action=candidate.get("action")
        if not isinstance(feature,str) or feature not in features:
            continue
        if not isinstance(action,str) or (feature,action) in seen:continue
        seen.add((feature,action))
        contracts.append({"feature":feature,"action":action,"reviewed":False})
    return {"schemaVersion":"15.0","placeId":place,"contracts":contracts,
            "_reviewInstructions":"Remove unwanted contracts. Verify feature associations. Set reviewed=true only after explicit review; never infer gameplay execution from scan data.",
            "_scanId":scan}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("proposals")
    p.add_argument("--output",default="build/review-contracts-template.json")
    a=p.parse_args()
    read=lambda x:json.loads(Path(x).read_text(encoding="utf-8"))
    result=make_template(read(a.plan),read(a.proposals))
    target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":main()
