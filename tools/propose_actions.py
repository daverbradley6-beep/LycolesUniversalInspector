#!/usr/bin/env python3
"""Suggest safe client-action contracts from a validated universal scan.

Suggestions are NOT approvals. The operator must explicitly review and mark
contracts before the existing validator can generate executable Lua.
"""
import json
import pathlib
import re

ACTIONS=(
 ("read_leaderstats",("IntValue","NumberValue","StringValue","BoolValue"),
  "Inspect replicated leaderstats using supported client APIs"),
 ("list_player_gui",("ScreenGui","TextButton","ImageButton"),
  "Enumerate local PlayerGui interfaces without activating controls"),
 ("list_proximity_prompts",("ProximityPrompt",),
  "Enumerate visible world prompts without triggering them"),
 ("list_visible_gui_buttons",("TextButton","ImageButton"),
  "List visible local GUI buttons without activating them"),
 ("read_local_player_attributes",("Player",),
  "Read primitive attributes of the local player"),
 ("inspect_local_character",("Humanoid","HumanoidRootPart"),
  "Inspect local character humanoid properties without modification"),
)
SAFE_NAME=re.compile(r"^[A-Za-z][A-Za-z0-9_ -]{0,79}$")

def propose(plan):
    integrity=plan.get("integrity") or {}
    place=integrity.get("placeId")
    if integrity.get("scanComplete") is not True or type(place) is not int or place<1:
        raise ValueError("Complete validated scan required")
    counts=plan.get("classCounts")
    if not isinstance(counts,dict): raise ValueError("Missing class inventory")
    if any(not isinstance(k,str) or type(v) is not int or v<0 for k,v in counts.items()):
        raise ValueError("Invalid class counts")
    features=[f.get("feature") for f in plan.get("features",[]) if isinstance(f,dict)]
    candidates=sorted({f for f in features if isinstance(f,str) and SAFE_NAME.fullmatch(f)})
    proposals=[]
    for action,classes,reason in ACTIONS:
        observed={name:counts[name] for name in classes if counts.get(name,0)>0}
        if not observed:continue
        # A feature label is merely a validated inventory association, not proof
        # that the action implements that feature's gameplay.
        feature=(next((f for f in candidates if f.lower() in
                 {"stats","statistics","leaderstats","diagnostics","inspection"}),None)
                 or (candidates[0] if candidates else None))
        proposals.append({"action":action,"feature":feature,
            "reviewed":False,"scope":"client-read-only",
            "evidenceClasses":observed,"reason":reason,
            "implementationReady":False,
            "reviewInstructions":"Confirm action relevance and select a valid feature; set reviewed=true only after explicit review"})
    return {"schemaVersion":"19.0","placeId":place,"scanId":integrity.get("scanId"),
        "proposals":proposals,"automaticallyApproved":0,
        "notice":"Proposals do not authorize execution or establish gameplay automation."}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("--output",default="build/action-proposals.json")
    a=p.parse_args()
    result=propose(json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8")))
    dest=pathlib.Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":main()
