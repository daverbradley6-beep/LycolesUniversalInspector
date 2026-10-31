#!/usr/bin/env python3
"""Generate actionable evidence coverage and review guidance for each discovered feature."""
import argparse
import json
from pathlib import Path

def report(plan, backlog, contracts=None, action_audit=None):
    integrity=plan.get("integrity") or {}
    place=integrity.get("placeId")
    scan=integrity.get("scanId")
    if integrity.get("scanComplete") is not True or type(place) is not int or place<=0:
        raise ValueError("Complete scan required")
    if backlog.get("placeId")!=place or backlog.get("scanId")!=scan:
        raise ValueError("Backlog provenance mismatch")
    if contracts is not None and contracts.get("placeId")!=place:
        raise ValueError("Contract place mismatch")
    if action_audit is not None and action_audit.get("placeId")!=place:
        raise ValueError("Audit place mismatch")
    workflows=backlog.get("candidates")
    if not isinstance(workflows,list):raise ValueError("Invalid backlog")
    approved=set()
    if contracts is not None:
        for c in contracts.get("contracts",[]):
            if c.get("reviewed") is True and c.get("scope")=="client-read-only":
                approved.add(c.get("feature"))
    tested={}
    if action_audit is not None:
        tested={a.get("action"):a.get("status") for a in action_audit.get("results",[])}
    grouped={}
    for item in workflows:
        if not isinstance(item,dict) or not isinstance(item.get("feature"),str):
            raise ValueError("Invalid workflow")
        grouped.setdefault(item["feature"],[]).append(item)
    features=[]
    for f in plan.get("features",[]):
        name=f.get("feature")
        if not isinstance(name,str):continue
        observed=grouped.get(name,[])
        reviewed=name in approved
        features.append({"feature":name,"observedWorkflows":len(observed),
            "reviewedClientActionAssociated":reviewed,
            "clientExecutionEvidence":tested if reviewed else {},
            "gameplayImplemented":False,
            "missingEvidence":(["observed workflow"] if not observed else [])+
              (["reviewed supported client action"] if not reviewed else [])+
              ["verified gameplay effect and permitted implementation contract"]})
    return {"schemaVersion":"29.0","placeId":place,"scanId":scan,
            "features":features,"featureCount":len(features),
            "gameplayFunctionsVerified":0,"note":"Coverage report is not an implementation claim."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("backlog");p.add_argument("--contracts")
    p.add_argument("--audit");p.add_argument("--output",default="build/feature-coverage.json")
    a=p.parse_args()
    read=lambda path:json.loads(Path(path).read_text(encoding="utf-8"))
    result=report(read(a.plan),read(a.backlog),read(a.contracts) if a.contracts else None,
                  read(a.audit) if a.audit else None)
    dest=Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__":main()
