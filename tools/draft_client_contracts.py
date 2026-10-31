#!/usr/bin/env python3
"""Create a deterministic, review-required contract draft from a validated scan.

Only known read-only client operations can be proposed. A draft never
authorizes code generation until explicitly reviewed.
"""
import argparse
import json
from pathlib import Path

CAPABILITIES=(
    ("read_leaderstats","leaderstats",("IntValue","NumberValue","StringValue","BoolValue")),
    ("list_player_gui","gui",("ScreenGui","BillboardGui","SurfaceGui")),
    ("list_proximity_prompts","prompts",("ProximityPrompt",)),
)

def draft(plan):
    integrity=plan.get("integrity") or {}
    place=integrity.get("placeId")
    if integrity.get("scanComplete") is not True or type(place) is not int or place<=0:
        raise ValueError("Complete scan and valid Place ID required")
    counts=plan.get("classCounts")
    if not isinstance(counts,dict):raise ValueError("Missing class inventory")
    if any(type(v) is not int or v<0 for v in counts.values()):
        raise ValueError("Invalid class counts")
    known=sorted({f["feature"] for f in plan.get("features",[])
                  if isinstance(f,dict) and isinstance(f.get("feature"),str)})
    proposals=[]
    for action,category,classes in CAPABILITIES:
        evidence={c:counts[c] for c in classes if counts.get(c,0)>0}
        if not evidence:continue
        proposals.append({"action":action,"category":category,"observedClasses":evidence,
                          "reviewed":False,"implementationReady":False,
                          "reason":"Class presence supports a candidate, not a validated action contract"})
    return {"schemaVersion":"27.0","placeId":place,"scanId":integrity.get("scanId"),
            "knownFeatures":known,"proposals":proposals,
            "reviewRequired":True,"gameplayAutomationApproved":False}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("--output",default="build/contract-draft.json")
    args=parser.parse_args()
    result=draft(json.loads(Path(args.plan).read_text(encoding="utf-8")))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":main()
