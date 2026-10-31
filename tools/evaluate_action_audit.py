#!/usr/bin/env python3
"""Evaluate bounded client-action audit records against reviewed contracts.

The result describes execution observations, not gameplay success or server
authority. A missing action remains untested, never silently passed.
"""
import argparse
import json
from pathlib import Path

def evaluate(contracts, report):
    if not isinstance(contracts,dict) or contracts.get("schemaVersion")!="15.0":
        raise ValueError("Validated v15 contracts required")
    place=contracts.get("placeId")
    if type(place) is not int or place<=0:raise ValueError("Invalid Place ID")
    entries=contracts.get("contracts")
    if not isinstance(entries,list) or len(entries)>100:raise ValueError("Invalid contracts")
    allowed=set()
    for entry in entries:
        if not isinstance(entry,dict) or entry.get("reviewed") is not True or entry.get("scope")!="client-read-only":
            raise ValueError("Unreviewed or invalid contract")
        action=entry.get("action")
        if not isinstance(action,str):raise ValueError("Invalid action")
        allowed.add(action)
    if not isinstance(report,dict) or report.get("schemaVersion")!="28.0" or report.get("placeId")!=place or report.get("source")!="reviewed-client-actions":
        raise ValueError("Audit identity or schema mismatch")
    records=report.get("results")
    if not isinstance(records,list) or len(records)>100:raise ValueError("Invalid bounded audit")
    statuses={name:[] for name in sorted(allowed)}
    for item in records:
        if not isinstance(item,dict):raise ValueError("Malformed audit item")
        action=item.get("action")
        if action not in statuses:raise ValueError("Unknown action in audit")
        success=item.get("success")
        duration=item.get("durationSeconds")
        if type(success) is not bool or type(duration) not in (int,float) or not 0<=duration<=3600:
            raise ValueError("Invalid audit result")
        err=item.get("error")
        if err is not None and (not isinstance(err,str) or len(err)>5000):
            raise ValueError("Invalid audit error")
        statuses[action].append({"success":success,"durationSeconds":duration,
                                 "error":err[:500] if isinstance(err,str) else None})
    results=[]
    for action,items in statuses.items():
        state=("not-tested" if not items else
               "client-function-returned" if all(x["success"] for x in items) else
               "client-function-error")
        results.append({"action":action,"status":state,"attempts":len(items),
                        "successfulCalls":sum(x["success"] for x in items),
                        "errors":[x["error"] for x in items if not x["success"]][:10]})
    return {"schemaVersion":"29.0","placeId":place,"results":results,
            "observedActions":sum(bool(x["attempts"]) for x in results),
            "runtimeGameplayVerified":False,"serverAuthorityVerified":False,
            "note":"Client function call outcomes do not establish gameplay effects."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("contracts");p.add_argument("audit")
    p.add_argument("--output",default="build/action-audit-evaluation.json")
    args=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evaluate(read(args.contracts),read(args.audit)),indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":main()
