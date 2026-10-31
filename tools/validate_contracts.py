#!/usr/bin/env python3
"""Lycoles v15: validate explicit, inspectable client action contracts.

Contracts are authored and reviewed separately from passive scan evidence.
No server remotes, executor hooks or inferred gameplay calls are supported.
"""
import json
import pathlib
import re
import sys

ACTIONS={"read_leaderstats","list_player_gui","list_proximity_prompts",
         "list_visible_gui_buttons","read_local_player_attributes","inspect_local_character"}
IDENTIFIER=re.compile(r"^[A-Za-z][A-Za-z0-9_ -]{0,79}$")
def validate_contracts(plan,document):
    integrity=plan.get("integrity") or {}
    if integrity.get("scanComplete") is not True:
        raise ValueError("Validated complete scan required")
    place=integrity.get("placeId")
    if type(place) is not int or place<1: raise ValueError("Invalid scan place")
    if not isinstance(document,dict) or document.get("schemaVersion")!="15.0":
        raise ValueError("Unsupported contract schema")
    if document.get("placeId")!=place: raise ValueError("Place ID mismatch")
    entries=document.get("contracts")
    if not isinstance(entries,list) or len(entries)>100:
        raise ValueError("Invalid contract inventory")
    known={x.get("feature") for x in plan.get("features",[]) if isinstance(x,dict)}
    seen=set()
    approved=[]
    for item in entries:
        if not isinstance(item,dict): raise ValueError("Malformed contract")
        name=item.get("feature")
        action=item.get("action")
        if not isinstance(name,str) or not IDENTIFIER.fullmatch(name) or name not in known:
            raise ValueError("Contract feature not present in scan")
        if action not in ACTIONS: raise ValueError("Unsupported action type")
        if item.get("reviewed") is not True:
            raise ValueError("Explicit review required")
        if (name,action) in seen: raise ValueError("Duplicate contract")
        seen.add((name,action))
        approved.append({"feature":name,"action":action,
            "scope":"client-read-only","reviewed":True})
    return {"schemaVersion":"15.0","placeId":place,
            "contracts":sorted(approved,key=lambda x:(x["feature"],x["action"])),
            "clientActionsApproved":len(approved),"gameplayAutomationApproved":False}

def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("contracts")
    parser.add_argument("--output",default="build/validated-contracts.json")
    a=parser.parse_args()
    try:
        plan=json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
        contracts=json.loads(pathlib.Path(a.contracts).read_text(encoding="utf-8"))
        result=validate_contracts(plan,contracts)
        out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("Validated client contracts:",out)
        return 0
    except (OSError,ValueError,TypeError) as exc:
        print("CONTRACT VALIDATION BLOCKED:",exc,file=sys.stderr)
        return 2
if __name__=="__main__":sys.exit(main())
