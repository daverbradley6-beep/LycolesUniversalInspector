#!/usr/bin/env python3
"""v90: reproducible, fail-closed evidence pipeline and review-only action plans."""
import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path

PREFIX = "LYCOLES_V87_EVENT "
MAX_LOG_BYTES = 30_000_000

def canonical(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode("utf-8")

def read_events(paths, place_id):
    if type(place_id) is not int or place_id<=0:
        raise ValueError("place ID must be positive")
    events={}
    sources=[]
    warnings=[]
    for source in paths:
        path=Path(source)
        if not path.is_file() or path.stat().st_size>MAX_LOG_BYTES:
            raise ValueError("missing or oversized log: "+str(path))
        data=path.read_bytes()
        sources.append({"filename":path.name,"sha256":hashlib.sha256(data).hexdigest(),"bytes":len(data)})
        for number,line in enumerate(data.decode("utf-8-sig",errors="replace").splitlines(),1):
            if PREFIX not in line:
                continue
            try:
                event=json.loads(line.split(PREFIX,1)[1])
            except (ValueError,TypeError):
                warnings.append(f"{path.name}:{number}: invalid JSON")
                continue
            if not isinstance(event,dict) or event.get("schemaVersion")!="87.event" or event.get("placeId")!=place_id:
                warnings.append(f"{path.name}:{number}: incompatible event")
                continue
            capture=event.get("captureId");index=event.get("index")
            if not isinstance(capture,str) or not capture or type(index) is not int or index<=0:
                warnings.append(f"{path.name}:{number}: invalid event identity")
                continue
            if event.get("kind") not in ("keyboard","gui") or not isinstance(event.get("details"),dict) or not isinstance(event.get("observedChanges"),list):
                warnings.append(f"{path.name}:{number}: invalid event shape")
                continue
            identity=(capture,index)
            if identity in events and events[identity]!=event:
                raise ValueError("conflicting capture/index identity: "+repr(identity))
            events[identity]=event
    return [events[k] for k in sorted(events)],sources,warnings

def input_key(event):
    d=event["details"]
    if event["kind"]=="keyboard":
        key=d.get("key")
        if not isinstance(key,str) or not key or len(key)>64:
            return None
        return "keyboard:"+key+":processed="+str(d.get("gameProcessed"))
    path=d.get("path")
    if not isinstance(path,list) or not 1<=len(path)<=60:
        return None
    for segment in path:
        if not isinstance(segment,dict) or not isinstance(segment.get("name"),str) or not isinstance(segment.get("className"),str) or type(segment.get("ordinal")) is not int or segment["ordinal"]<1:
            return None
    return "gui:"+json.dumps(path,ensure_ascii=False,sort_keys=True,separators=(",",":"))

def changes(event):
    result=set()
    for c in event["observedChanges"][:200]:
        if not isinstance(c,dict) or not isinstance(c.get("stat"),str) or not c["stat"]:
            continue
        a,b=c.get("before"),c.get("after")
        if type(a) is not type(b) or a==b:
            continue
        if type(a) in (int,float) and math.isfinite(a) and math.isfinite(b):
            op="increase" if b>a else "decrease"
        elif type(a) in (bool,str):
            op="change"
        else:
            continue
        result.add((c["stat"],op))
    return result

def analyse(events, min_per_capture=3, min_captures=2, max_control_rate=0.1):
    if type(min_per_capture) is not int or min_per_capture<1 or type(min_captures) is not int or min_captures<2:
        raise ValueError("minimums invalid")
    if not 0<=max_control_rate<=1:
        raise ValueError("control threshold invalid")
    grouped=defaultdict(list)
    signals=set()
    invalid=0
    for event in events:
        key=input_key(event)
        if key is None:
            invalid+=1
            continue
        grouped[key].append(event)
        signals.update(changes(event))
    candidates=[]
    for signal in sorted(signals):
        stats={}
        for key,items in sorted(grouped.items()):
            captures=defaultdict(lambda:{"total":0,"matches":0})
            for event in items:
                c=captures[event["captureId"]]
                c["total"]+=1
                c["matches"]+=int(signal in changes(event))
            total=sum(c["total"] for c in captures.values())
            matched=sum(c["matches"] for c in captures.values())
            stats[key]={"total":total,"matches":matched,"rate":matched/total,
                        "captures":dict(sorted(captures.items()))}
        for key,positive in stats.items():
            if positive["matches"]==0:
                continue
            issues=[]
            if len(positive["captures"])<min_captures:
                issues.append("candidate_requires_independent_captures")
            if any(c["total"]<min_per_capture for c in positive["captures"].values()):
                issues.append("candidate_capture_has_too_few_observations")
            if any(c["matches"]!=c["total"] for c in positive["captures"].values()):
                issues.append("candidate_not_consistent_across_observations")
            controls=[]
            for other,negative in stats.items():
                if other==key or len(negative["captures"])<min_captures:
                    continue
                if any(c["total"]<min_per_capture for c in negative["captures"].values()):
                    continue
                if negative["rate"]>max_control_rate:
                    continue
                if set(positive["captures"])!=set(negative["captures"]):
                    continue
                if any(c["matches"] for c in negative["captures"].values()):
                    continue
                controls.append(other)
            if not controls:
                issues.append("no_clean_matched_session_control")
            candidate_id=hashlib.sha256(canonical([key,*signal])).hexdigest()[:16]
            candidates.append({
                "id":"observation-"+candidate_id,
                "input":key,"outcome":{"stat":signal[0],"operator":signal[1]},
                "observations":positive["total"],
                "captureCount":len(positive["captures"]),
                "perCapture":positive["captures"],
                "negativeControl":sorted(controls)[0] if controls else None,
                "status":"review_candidate" if not issues else "insufficient_evidence",
                "issues":issues,
                "executionAdapter":None,"implementationAvailable":False,
                "approved":False,"executionEnabled":False,"verifiedInGame":False
            })
    candidates.sort(key=lambda c:(c["status"]!="review_candidate",c["id"]))
    return {"schemaVersion":"90.review","events":len(events),"inputGroups":len(grouped),
            "invalidInputEvents":invalid,"candidates":candidates,
            "verifiedInGame":False,"automaticallyExecuted":0}

def write_release(directory,report,sources,warnings):
    target=Path(directory)
    target.mkdir(parents=True,exist_ok=True)
    contracts={"schemaVersion":"90.contracts","placeId":report["placeId"],
               "contracts":[{"id":c["id"],"input":c["input"],"expectedOutcome":c["outcome"],
                             "evidenceStatus":c["status"],"approved":False,
                             "executionEnabled":False,"executionAdapter":None}
                            for c in report["candidates"]]}
    artifacts={"review-v90.json":report,"contracts-for-review-v90.json":contracts}
    hashes={}
    for name,data in artifacts.items():
        payload=canonical(data)
        (target/name).write_bytes(payload)
        digest=hashlib.sha256(payload).hexdigest()
        if hashlib.sha256((target/name).read_bytes()).hexdigest()!=digest:
            raise RuntimeError("integrity failure: "+name)
        hashes[name]=digest
    manifest={"schemaVersion":"90.manifest","placeId":report["placeId"],
              "inputs":sources,"warnings":warnings,"outputs":hashes,
              "verifiedInGame":False}
    (target/"manifest-v90.json").write_bytes(canonical(manifest))
    return manifest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-id",type=int,required=True)
    parser.add_argument("--event-log",type=Path,action="append",required=True)
    parser.add_argument("--output",type=Path,default=Path("build/release-v90"))
    parser.add_argument("--min-per-capture",type=int,default=3)
    parser.add_argument("--min-captures",type=int,default=2)
    args=parser.parse_args()
    events,sources,warnings=read_events(args.event_log,args.place_id)
    report=analyse(events,args.min_per_capture,args.min_captures)
    report["placeId"]=args.place_id
    write_release(args.output,report,sources,warnings)
    print(json.dumps({"events":len(events),"inputs":report["inputGroups"],
          "candidates":len(report["candidates"]),
          "reviewCandidates":sum(c["status"]=="review_candidate" for c in report["candidates"]),
          "warnings":len(warnings),"verifiedInGame":False,"output":str(args.output)}))
if __name__=="__main__":
    main()
