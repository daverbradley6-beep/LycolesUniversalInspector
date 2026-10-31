#!/usr/bin/env python3
"""Generate a game-agnostic evidence-backed implementation backlog.

A discovered interaction is not an executable contract. This tool separates
reviewable implementation candidates from unsupported automation.
"""
import json
import pathlib

def compile_backlog(plan, sequences, feedback=None):
    integrity=plan.get("integrity",{})
    if integrity.get("scanComplete") is not True:
        raise ValueError("Complete scan required")
    place=integrity.get("placeId")
    if type(place) is not int or place<1 or sequences.get("placeId")!=place:
        raise ValueError("Place ID mismatch")
    if sequences.get("scanId")!=integrity.get("scanId"):
        raise ValueError("Scan ID mismatch")
    workflows=sequences.get("workflows")
    if not isinstance(workflows,list) or len(workflows)>2000:
        raise ValueError("Invalid workflows")
    observed={}
    if feedback is not None:
        if feedback.get("placeId")!=place:raise ValueError("Feedback place mismatch")
        for item in feedback.get("results",[]):
            if not isinstance(item,dict):raise ValueError("Invalid feedback")
            observed[(item.get("feature"),item.get("transaction"))]=item.get("status")
    candidates=[]
    for workflow in workflows:
        if not isinstance(workflow,dict):raise ValueError("Invalid workflow")
        feature=workflow.get("feature")
        transaction=workflow.get("transaction")
        steps=workflow.get("steps")
        if not isinstance(feature,str) or not isinstance(transaction,str) or not isinstance(steps,list):
            raise ValueError("Malformed workflow")
        paths=[s["path"] for s in steps if isinstance(s,dict) and isinstance(s.get("path"),str)]
        state_changes=sum(len(s.get("stateChanges",[])) for s in steps if isinstance(s,dict) and isinstance(s.get("stateChanges"),list))
        status=observed.get((feature,transaction),"not-tested")
        candidates.append({"feature":feature,"transaction":transaction,
          "observedControls":paths[:32],"observedStateChanges":state_changes,
          "clientFeedbackStatus":status,
          "implementationStage":"needs-interface-review",
          "supportedExecutableContract":False,"runtimeGameplayVerified":False,
          "requiredEvidence":["reviewed supported interface","explicit operation contract",
                              "per-operation runtime test"],
          "nextAction":"Review supported client API; do not infer remote arguments from observed names."})
    return {"schemaVersion":"25.0","placeId":place,"scanId":integrity["scanId"],
      "candidates":candidates,"candidateCount":len(candidates),
      "automaticallyGeneratedGameplayFunctions":0,
      "note":"Evidence-backed implementation backlog, not generated gameplay automation."}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("sequences")
    p.add_argument("--feedback");p.add_argument("--output",default="build/implementation-backlog.json")
    a=p.parse_args()
    read=lambda path:json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    result=compile_backlog(read(a.plan),read(a.sequences),read(a.feedback) if a.feedback else None)
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
