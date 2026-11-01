#!/usr/bin/env python3
"""v88 evidence gate: cross-session input/control comparisons and safe action specifications."""
import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from passive_recorder_v87 import parse

def rate_interval(successes,total,z=1.96):
    if total == 0:
        return [0.0,1.0]
    p=successes/total
    d=1+z*z/total
    mid=(p+z*z/(2*total))/d
    half=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/d
    return [round(max(0,mid-half),4),round(min(1,mid+half),4)]

def identity(event):
    details=event["details"]
    if event["kind"]=="keyboard":
        key=details.get("key")
        if not isinstance(key,str) or not key or len(key)>50:
            return None
        return "keyboard:"+key+":processed="+str(details.get("gameProcessed"))
    path=details.get("path")
    if not isinstance(path,list) or not path or len(path)>50:
        return None
    for segment in path:
        if not isinstance(segment,dict) or not isinstance(segment.get("name"),str) or not isinstance(segment.get("className"),str) or type(segment.get("ordinal")) is not int or segment["ordinal"]<1:
            return None
    return "gui:"+json.dumps(path,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def changed(event,stat,operator):
    for change in event["observedChanges"]:
        if not isinstance(change,dict) or change.get("stat")!=stat:
            continue
        a,b=change.get("before"),change.get("after")
        if type(a) is not type(b):
            continue
        if type(a) in (int,float) and all(math.isfinite(v) for v in (a,b)):
            if operator=="increase" and b>a:return True
            if operator=="decrease" and b<a:return True
        elif operator=="change" and type(a) in (str,bool) and a!=b:
            return True
    return False

def evaluate(events, candidate, control, stat, operator="increase", minimum=5, sessions=2):
    if candidate==control:
        raise ValueError("candidate and control must differ")
    if not isinstance(stat,str) or not stat.strip():
        raise ValueError("stat required")
    if operator not in ("increase","decrease","change"):
        raise ValueError("unsupported operator")
    if type(minimum) is not int or minimum<1 or type(sessions) is not int or sessions<1:
        raise ValueError("minimum and sessions must be positive integers")
    groups={candidate:[],control:[]}
    invalid=0
    for event in events:
        key=identity(event)
        if key in groups:
            groups[key].append(event)
        elif key is None:
            invalid+=1
    summaries={}
    for name,items in groups.items():
        per_session=defaultdict(lambda:{"total":0,"successes":0})
        for event in items:
            session=per_session[event["captureId"]]
            session["total"]+=1
            session["successes"]+=int(changed(event,stat,operator))
        successes=sum(x["successes"] for x in per_session.values())
        total=len(items)
        summaries[name]={
            "observations":total,"successes":successes,"rate":round(successes/total,4) if total else None,
            "wilson95":rate_interval(successes,total),
            "independentCaptures":len(per_session),
            "captures":[{"captureId":k,**v} for k,v in sorted(per_session.items())]
        }
    positive=summaries[candidate]
    negative=summaries[control]
    issues=[]
    for name,summary in ((candidate,positive),(control,negative)):
        if summary["observations"]<minimum:
            issues.append(f"{name}: fewer than {minimum} observations")
        if summary["independentCaptures"]<sessions:
            issues.append(f"{name}: fewer than {sessions} independent captures")
    if not issues:
        if positive["rate"]<=negative["rate"]:
            issues.append("candidate rate does not exceed control rate")
        if positive["rate"]<0.8:
            issues.append("candidate increase rate below 80%")
        if negative["rate"]>0.2:
            issues.append("control increase rate above 20%")
        if any(x["successes"]==0 for x in positive["captures"]):
            issues.append("candidate has a capture without an observed success")
        if any(x["successes"]>0 for x in negative["captures"]):
            issues.append("control has a capture with an observed change")
    eligible=not issues
    return {
        "schemaVersion":"88.evidence","candidate":candidate,"control":control,
        "target":{"stat":stat,"operator":operator},
        "requirements":{"minimumObservationsPerInput":minimum,"minimumIndependentCapturesPerInput":sessions},
        "inputs":summaries,"eligibleForHumanReview":eligible,
        "issues":issues,"invalidInputEvents":invalid,
        "causalityProven":False,"verifiedInGame":False,
        "executionEnabled":False,
        "actionSpecification":{
            "input":candidate,"expectedOutcome":{"stat":stat,"operator":operator},
            "executionStrategy":"manual_observation_only",
            "implementationAvailable":False,
            "requiresAuthorizedExecutionAdapter":True
        }
    }

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--event-log",type=Path,action="append",required=True)
    p.add_argument("--candidate",default="keyboard:E:processed=False")
    p.add_argument("--control",default="keyboard:W:processed=False")
    p.add_argument("--stat",default="🥚 Hatches")
    p.add_argument("--operator",choices=["increase","decrease","change"],default="increase")
    p.add_argument("--minimum",type=int,default=5)
    p.add_argument("--sessions",type=int,default=2)
    p.add_argument("--output",type=Path,default=Path("build/release-v88"))
    a=p.parse_args()
    if a.place_id<=0: p.error("place ID must be positive")
    events,warnings=parse(a.event_log,a.place_id)
    report=evaluate(events,a.candidate,a.control,a.stat,a.operator,a.minimum,a.sessions)
    report["placeId"]=a.place_id
    report["totalEvents"]=len(events)
    report["warnings"]=warnings
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"evidence-gate-v88.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"events":len(events),"candidate":report["inputs"][a.candidate],"control":report["inputs"][a.control],"eligibleForHumanReview":report["eligibleForHumanReview"],"issues":report["issues"],"verifiedInGame":False},ensure_ascii=False))
if __name__=="__main__":
    main()
