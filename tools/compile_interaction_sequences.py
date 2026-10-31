#!/usr/bin/env python3
"""Convert observed GUI interactions into reviewable, non-executable workflows.

All paths, state transitions and links are observed client evidence. Never
infer remote arguments, invoke remotes, or assert server-side causality.
"""
import json

MAX_EVENTS=2000
MAX_TEXT=240
MAX_CHANGES=24

def _safe(value):
    return isinstance(value,str) and 0<len(value)<=MAX_TEXT and all(ord(c)>=32 for c in value)

def compile_sequences(plan):
    integrity=plan.get("integrity") or {}
    if integrity.get("scanComplete") is not True or type(integrity.get("placeId")) is not int:
        raise ValueError("Complete validated scan required")
    history=plan.get("observedInteractionHistory",[])
    if not isinstance(history,list) or len(history)>MAX_EVENTS:
        raise ValueError("Invalid interaction history")
    groups={}
    rejected=0
    for item in history:
        if not isinstance(item,dict) or not _safe(item.get("path")):
            rejected+=1;continue
        feature=item.get("featureCandidate")
        if not _safe(feature):feature="unattributed"
        tid=item.get("transactionId")
        # Never merge unlinked events simply because their feature names match.
        key=(feature,str(tid) if type(tid) in (int,str) and len(str(tid))<=80 else "event-"+str(len(groups)))
        steps=groups.setdefault(key,[])
        changes=[]
        for delta in (item.get("stateChanges") or [])[:MAX_CHANGES]:
            if not isinstance(delta,dict) or not _safe(delta.get("key")):continue
            before,after=delta.get("before"),delta.get("after")
            if type(before) not in (int,float,str,bool) or type(after) not in (int,float,str,bool):continue
            if len(str(before))>80 or len(str(after))>80:continue
            changes.append({"key":delta["key"],"before":before,"after":after})
        steps.append({"path":item["path"],"controlType":item.get("controlType") if _safe(item.get("controlType")) else None,
          "sequence":item.get("sequence") if type(item.get("sequence")) is int else None,
          "stateChanges":changes,"clientStateCorroborated":item.get("clientStateCorroborated") is True,
          "outcomeVerified":item.get("outcomeVerified") is True})
    workflows=[]
    for (feature,tid),steps in sorted(groups.items()):
        steps.sort(key=lambda s:(s["sequence"] is None,s["sequence"] or 0))
        workflows.append({"feature":feature,"transaction":tid,"steps":steps,
          "observedStateChanges":sum(len(s["stateChanges"]) for s in steps),
          "clientCorroborated":any(s["clientStateCorroborated"] for s in steps),
          "serverVerified":False,"automaticallyExecutable":False,
          "requiredNextStep":"Review actual supported action interface and test a permitted implementation"})
    return {"schemaVersion":"20.0","placeId":integrity["placeId"],"scanId":integrity.get("scanId"),
      "workflowCount":len(workflows),"rejectedEvents":rejected,"workflows":workflows,
      "notice":"Temporal correlation is not proof of causality or permission to invoke game remotes."}

def main():
    import argparse,pathlib
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("--output",default="build/observed-workflows.json")
    a=p.parse_args()
    result=compile_sequences(json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8")))
    target=pathlib.Path(a.output);target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
if __name__=="__main__":main()
