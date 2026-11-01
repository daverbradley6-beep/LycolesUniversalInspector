#!/usr/bin/env python3
"""v89 universal evidence compiler: discover, validate, and export review-only action contracts.

No input injection, game remotes, unsupported GuiButton methods or bypasses.
"""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from passive_recorder_v87 import parse
from evidence_gate_v88 import identity, changed, rate_interval

def discover(events, min_observations=5, min_sessions=2, min_rate=.8, max_control_rate=.2):
    if type(min_observations) is not int or min_observations<1:
        raise ValueError("invalid minimum observations")
    if type(min_sessions) is not int or min_sessions<1:
        raise ValueError("invalid minimum sessions")
    if not (0<=min_rate<=1 and 0<=max_control_rate<=1):
        raise ValueError("invalid thresholds")
    buckets=defaultdict(list)
    signals=set()
    rejected=0
    for event in events:
        key=identity(event)
        if key is None:
            rejected+=1
            continue
        buckets[key].append(event)
        for change in event.get("observedChanges",[]):
            if not isinstance(change,dict) or not isinstance(change.get("stat"),str):
                continue
            stat=change["stat"]
            a,b=change.get("before"),change.get("after")
            if type(a) in (int,float) and type(a) is type(b) and math.isfinite(a) and math.isfinite(b) and a!=b:
                signals.add((stat,"increase" if b>a else "decrease"))
            elif type(a) in (bool,str) and type(a) is type(b) and a!=b:
                signals.add((stat,"change"))
    actions=[]
    for stat,op in sorted(signals):
        counts={}
        for key,items in sorted(buckets.items()):
            captures=defaultdict(lambda:{"observations":0,"matches":0})
            matches=0
            for event in items:
                match=changed(event,stat,op)
                matches+=int(match)
                captures[event["captureId"]]["observations"]+=1
                captures[event["captureId"]]["matches"]+=int(match)
            total=len(items)
            counts[key]={
                "observations":total,"matches":matches,"rate":round(matches/total,5),
                "independentCaptures":len(captures),
                "captures":[{"id":k,**v} for k,v in sorted(captures.items())],
                "wilson95":rate_interval(matches,total)
            }
        for key,positive in counts.items():
            if positive["rate"]<min_rate:
                continue
            controls=[]
            for other,negative in counts.items():
                if other==key:
                    continue
                if negative["rate"]<=max_control_rate and negative["observations"]>=min_observations and negative["independentCaptures"]>=min_sessions:
                    controls.append((other,negative))
            controls.sort(key=lambda x:(x[1]["rate"],-x[1]["observations"],x[0]))
            issues=[]
            if positive["observations"]<min_observations:
                issues.append("insufficient_candidate_observations")
            if positive["independentCaptures"]<min_sessions:
                issues.append("insufficient_candidate_sessions")
            if any(c["matches"]==0 for c in positive["captures"]):
                issues.append("inconsistent_candidate_sessions")
            if not controls:
                issues.append("no_adequate_negative_control")
            if not issues:
                # Require a control with zero matched outcomes in every capture,
                # reducing delayed-outcome false positives.
                controls=[(k,c) for k,c in controls if all(s["matches"]==0 for s in c["captures"])]
                if not controls:
                    issues.append("control_contaminated_by_outcome")
            selected=controls[0] if controls else None
            # Correlation can be a review candidate, never a verified action.
            actions.append({
                "id":"candidate-"+hashlib.sha256((key+"\x00"+stat+"\x00"+op).encode("utf-8")).hexdigest()[:12],
                "input":key,"outcome":{"stat":stat,"operator":op},
                "evidence":positive,"negativeControl":(
                    {"input":selected[0],"evidence":selected[1]} if selected else None),
                "status":"review_candidate" if not issues else "insufficient_evidence",
                "issues":issues,"approved":False,"executionEnabled":False,
                "executionStrategy":"manual_observation_only",
                "implementationAvailable":False,"causalityProven":False
            })
    actions.sort(key=lambda a:(a["status"]!="review_candidate",-a["evidence"]["observations"],a["id"]))
    return {"schemaVersion":"89.discovery","events":len(events),"inputs":len(buckets),
            "invalidInputs":rejected,"actions":actions,
            "verifiedInGame":False,"automaticallyExecuted":0}

def compile_release(events,place_id,minimum=5,sessions=2):
    if type(place_id) is not int or place_id<=0:
        raise ValueError("invalid place ID")
    report=discover(events,minimum,sessions)
    report["placeId"]=place_id
    report["catalog"]={
        "schemaVersion":"89.catalog","placeId":place_id,
        "contracts":[{"id":a["id"],"input":a["input"],"expectedOutcome":a["outcome"],
                      "approved":False,"executionEnabled":False,
                      "evidenceStatus":a["status"],"implementationAvailable":False}
                     for a in report["actions"]]
    }
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--event-log",type=Path,action="append",required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v89"))
    p.add_argument("--minimum",type=int,default=5)
    p.add_argument("--sessions",type=int,default=2)
    args=p.parse_args()
    events,warnings=parse(args.event_log,args.place_id)
    report=compile_release(events,args.place_id,args.minimum,args.sessions)
    report["warnings"]=warnings
    args.output.mkdir(parents=True,exist_ok=True)
    artifacts={
        "discovery-v89.json":{k:v for k,v in report.items() if k!="catalog"},
        "contracts-for-review-v89.json":report["catalog"]
    }
    hashes={}
    for filename,document in artifacts.items():
        data=(json.dumps(document,ensure_ascii=False,indent=2,sort_keys=True)+"\n").encode("utf-8")
        (args.output/filename).write_bytes(data)
        hashes[filename]=hashlib.sha256(data).hexdigest()
        if hashlib.sha256((args.output/filename).read_bytes()).hexdigest()!=hashes[filename]:
            raise RuntimeError("output integrity mismatch: "+filename)
    manifest={"schemaVersion":"89.manifest","placeId":args.place_id,
              "sha256":hashes,"verifiedInGame":False,"automaticallyExecuted":0}
    (args.output/"manifest-v89.json").write_bytes((json.dumps(manifest,indent=2)+"\n").encode("utf-8"))
    print(json.dumps({"events":len(events),"inputs":report["inputs"],
        "candidates":len(report["actions"]),
        "reviewCandidates":sum(a["status"]=="review_candidate" for a in report["actions"]),
        "warnings":len(warnings),"output":str(args.output),"verifiedInGame":False}))
if __name__=="__main__":
    main()
