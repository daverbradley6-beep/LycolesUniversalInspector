#!/usr/bin/env python3
"""v99 independent trial evaluator for authorized Roblox Studio test sessions.

Consumes structured trial logs; reports observed action outcomes, never proof
of causation or anti-ban/third-party execution. No Roblox access required.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

SCHEMA="99.trial"
OUTCOMES={"increase","decrease","equal"}
def validate(trial):
    if not isinstance(trial,dict) or trial.get("schemaVersion")!=SCHEMA:
        raise ValueError("invalid trial schema")
    for field in ("placeId","userId"):
        if type(trial.get(field))!=int or trial[field]<=0:
            raise ValueError("invalid "+field)
    for field in ("sessionId","actionId","stat"):
        v=trial.get(field)
        if not isinstance(v,str) or not 1<=len(v)<=128:
            raise ValueError("invalid "+field)
    if trial.get("kind") not in ("action","control"):
        raise ValueError("invalid trial kind")
    if trial.get("expected") not in OUTCOMES:
        raise ValueError("invalid expected outcome")
    for field in ("before","after"):
        v=trial.get(field)
        if type(v) not in (int,float) or not math.isfinite(v):
            raise ValueError("invalid "+field)
    if type(trial.get("index"))!=int or trial["index"]<0:
        raise ValueError("invalid trial index")
    return trial

def observed(t):
    delta=t["after"]-t["before"]
    if delta>0:return "increase"
    if delta<0:return "decrease"
    return "equal"

def wilson_lower(successes,n,z=1.96):
    if n<=0:return 0.0
    p=successes/n
    den=1+z*z/n
    return max(0.0,(p+z*z/(2*n)-z*math.sqrt(p*(1-p)/n+z*z/(4*n*n)))/den)

def evaluate(trials,min_sessions=2,min_per_kind=3,threshold=0.5):
    if type(min_sessions)!=int or min_sessions<2:
        raise ValueError("min_sessions must be >=2")
    if type(min_per_kind)!=int or min_per_kind<1:
        raise ValueError("min_per_kind must be >=1")
    if not 0<=threshold<=1:
        raise ValueError("invalid threshold")
    seen=set()
    groups=defaultdict(list)
    place=None
    for t in trials:
        validate(t)
        if place is None:place=t["placeId"]
        if t["placeId"]!=place:raise ValueError("mixed places")
        key=(t["sessionId"],t["index"])
        if key in seen:raise ValueError("duplicate trial identity")
        seen.add(key)
        groups[(t["actionId"],t["stat"],t["expected"])].append(t)
    results=[]
    for (action,stat,expected),items in sorted(groups.items()):
        sessions=defaultdict(list)
        for t in items:sessions[t["sessionId"]].append(t)
        reasons=[]
        for session,rows in sessions.items():
            actions=[r for r in rows if r["kind"]=="action"]
            controls=[r for r in rows if r["kind"]=="control"]
            if len(actions)<min_per_kind or len(controls)<min_per_kind:
                reasons.append("insufficient_matched_trials:"+session)
        if len(sessions)<min_sessions:
            reasons.append("insufficient_independent_sessions")
        actions=[r for r in items if r["kind"]=="action"]
        controls=[r for r in items if r["kind"]=="control"]
        successes=sum(observed(t)==expected for t in actions)
        # A control matching the action's expected change is contamination.
        contamination=sum(observed(t)==expected for t in controls)
        action_lb=wilson_lower(successes,len(actions))
        control_rate=contamination/len(controls) if controls else 1.0
        if control_rate>0:reasons.append("control_contamination")
        if action_lb<threshold:reasons.append("low_confidence")
        if not actions or not controls:reasons.append("missing_trials")
        results.append({"actionId":action,"stat":stat,"expected":expected,
            "sessions":len(sessions),"actionTrials":len(actions),
            "controlTrials":len(controls),"matchedActions":successes,
            "contaminatedControls":contamination,
            "wilsonLower95":round(action_lb,6),
            "controlContaminationRate":round(control_rate,6),
            "status":"review_candidate" if not reasons else "insufficient_evidence",
            "issues":sorted(set(reasons)),"verifiedInGame":False,
            "causalityProven":False})
    return {"schemaVersion":"99.evaluation","placeId":place,
        "trialCount":len(trials),"groups":results,
        "verifiedInGame":False,"automaticGameplayExecution":False}

def parse_logs(paths):
    trials=[]
    for path in paths:
        for line_number,line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(),1):
            if not line.strip():continue
            try:
                obj=json.loads(line)
                validate(obj)
                trials.append(obj)
            except (ValueError,TypeError) as exc:
                raise ValueError(str(path)+":"+str(line_number)+": "+str(exc)) from exc
    return trials

def write_report(report,output):
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    payload=(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")
    output.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--trial-log",type=Path,action="append",required=True)
    p.add_argument("--output",type=Path,default=Path("build/v99-evaluation.json"))
    p.add_argument("--min-sessions",type=int,default=2)
    p.add_argument("--min-per-kind",type=int,default=3)
    p.add_argument("--wilson-threshold",type=float,default=.5)
    args=p.parse_args()
    result=evaluate(parse_logs(args.trial_log),args.min_sessions,
                    args.min_per_kind,args.wilson_threshold)
    digest=write_report(result,args.output)
    print(json.dumps({"groups":len(result["groups"]),"trials":result["trialCount"],
                      "sha256":digest,"verifiedInGame":False,"output":str(args.output)}))
if __name__=="__main__":
    main()
