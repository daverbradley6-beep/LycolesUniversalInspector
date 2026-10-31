#!/usr/bin/env python3
"""Validate operator-supplied runtime observations against a generated verification plan.

Never promote gameplay automation from client observations. A matched value
transition is evidence of observation, not causality or server authority.
"""
import json
import pathlib

def evaluate(plan, report):
    if not isinstance(plan,dict) or not isinstance(report,dict):
        raise ValueError("Plan and report must be objects")
    place=plan.get("placeId")
    if type(place) is not int or place<1 or report.get("placeId")!=place:
        raise ValueError("Place ID mismatch")
    if report.get("schemaVersion")!="22.0":
        raise ValueError("Unsupported runtime report schema")
    checks=plan.get("checks")
    results=report.get("results")
    if not isinstance(checks,list) or not isinstance(results,list) or len(results)>1000:
        raise ValueError("Invalid check or result inventory")
    allowed={(c["feature"],c["transaction"]):set(c["leaderstatsKeys"])
             for c in checks if isinstance(c,dict) and
             isinstance(c.get("feature"),str) and isinstance(c.get("transaction"),str)
             and isinstance(c.get("leaderstatsKeys"),list)}
    seen=set();evaluated=[]
    for item in results:
        if not isinstance(item,dict):raise ValueError("Malformed result")
        key=(item.get("feature"),item.get("transaction"))
        if key not in allowed or key in seen:raise ValueError("Unknown or duplicate check")
        seen.add(key)
        before,after=item.get("before"),item.get("after")
        if not isinstance(before,dict) or not isinstance(after,dict):
            raise ValueError("Before and after must be objects")
        if set(before)-allowed[key] or set(after)-allowed[key]:
            raise ValueError("Unexpected state key")
        if any(type(v) not in (int,float,str,bool) or len(str(v))>128
               for v in list(before.values())+list(after.values())):
            raise ValueError("Invalid state value")
        changed={k:{"before":before.get(k),"after":after.get(k)}
                 for k in sorted(allowed[key]) if k in before and k in after and before[k]!=after[k]}
        status="client-change-observed" if changed else (
            "no-client-change" if all(k in before and k in after for k in allowed[key])
            else "incomplete-observation")
        evaluated.append({"feature":key[0],"transaction":key[1],"status":status,
                          "changes":changed,"runtimeVerified":False,
                          "gameplayAutomationApproved":False})
    return {"schemaVersion":"22.0","placeId":place,"results":evaluated,
            "summary":{"submitted":len(evaluated),
                       "clientChangesObserved":sum(x["status"]=="client-change-observed" for x in evaluated),
                       "runtimeGameplayVerified":0},
            "notice":"Submitted observations are not trusted proof of execution, causality or server authority."}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("report")
    p.add_argument("--output",default="build/runtime-feedback.json")
    a=p.parse_args()
    result=evaluate(json.loads(pathlib.Path(a.plan).read_text()),
                    json.loads(pathlib.Path(a.report).read_text()))
    dest=pathlib.Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
