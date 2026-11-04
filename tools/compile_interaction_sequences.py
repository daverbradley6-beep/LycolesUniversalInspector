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

def _event_path(item):
    """Recognize alternate observed path fields without inventing a target."""
    for field in ("path", "targetPath", "guiPath", "controlPath"):
        value=item.get(field)
        if _safe(value): return value
    target=item.get("target")
    if isinstance(target,dict):
        for field in ("path", "fullName"):
            if _safe(target.get(field)): return target[field]
    return None

def _state_changes(item):
    raw=item.get("stateChanges")
    if not isinstance(raw,list): raw=item.get("guiStateChanges")
    if not isinstance(raw,list): return []
    changes=[]
    for delta in raw[:MAX_CHANGES]:
        if not isinstance(delta,dict): continue
        key=delta.get("key") or delta.get("path")
        if not _safe(key): continue
        before,after=delta.get("before"),delta.get("after")
        if type(before) not in (int,float,str,bool) or type(after) not in (int,float,str,bool):continue
        if len(str(before))>80 or len(str(after))>80:continue
        changes.append({"key":key,"before":before,"after":after})
    return changes

_BASELINE_SOURCES={"GuiButton.InputBegan","ProximityPrompt.PromptButtonHoldBegan",
    "Tool.Equipped","activation-callback-fallback"}

def _baseline(item):
    fields=("baselineSource","baselineTiming","baselineAgeSeconds",
        "preActivationBaselineAvailable")
    if not any(field in item for field in fields):return "unknown",False
    source=item.get("baselineSource");timing=item.get("baselineTiming")
    available=item.get("preActivationBaselineAvailable");age=item.get("baselineAgeSeconds")
    expected="activation-callback" if source=="activation-callback-fallback" else "pre-activation"
    if (source not in _BASELINE_SOURCES or timing!=expected or type(available) is not bool
            or available!=(timing=="pre-activation") or (age is not None and
            (type(age) not in (int,float) or type(age) is bool or not 0<=age<=3600))):
        raise ValueError("Malformed interaction baseline timing")
    return timing,available


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
        if not isinstance(item,dict) or not _event_path(item):
            rejected+=1;continue
        feature=item.get("featureCandidate")
        if not _safe(feature):feature="unattributed"
        tid=item.get("transactionId")
        # Never merge unlinked events simply because their feature names match.
        key=(feature,str(tid) if type(tid) in (int,str) and len(str(tid))<=80 else "event-"+str(len(groups)))
        steps=groups.setdefault(key,[])
        changes=_state_changes(item);baseline_timing,baseline_available=_baseline(item)
        steps.append({"path":_event_path(item),"controlType":item.get("controlType") if _safe(item.get("controlType")) else None,
          "sequence":item.get("sequence") if type(item.get("sequence")) is int else (item.get("eventIndex") if type(item.get("eventIndex")) is int else None),
          "stateChanges":changes,"clientStateCorroborated":item.get("clientStateCorroborated") is True,
          "baselineTiming":baseline_timing,"preActivationBaselineAvailable":baseline_available,
          "outcomeVerified":item.get("outcomeVerified") is True})
    workflows=[]
    for (feature,tid),steps in sorted(groups.items()):
        steps.sort(key=lambda s:(s["sequence"] is None,s["sequence"] or 0))
        workflows.append({"feature":feature,"transaction":tid,"steps":steps,
          "observedStateChanges":sum(len(s["stateChanges"]) for s in steps),
          "preActivationBaselineSteps":sum(s["baselineTiming"]=="pre-activation" for s in steps),
          "activationCallbackBaselineSteps":sum(s["baselineTiming"]=="activation-callback" for s in steps),
          "unknownBaselineTimingSteps":sum(s["baselineTiming"]=="unknown" for s in steps),
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
