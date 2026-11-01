#!/usr/bin/env python3
"""v91 temporal evidence attribution: quarantine ambiguous overlapping outcomes.

Review-only. Does not generate executable Roblox gameplay actions.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from evidence_release_v90 import read_events, analyse, write_release, canonical, changes, input_key

def valid_window(event):
    start=event.get("startedAt")
    delay=event.get("observationDelay")
    if type(start) not in (int,float) or type(delay) not in (int,float):
        return None
    if not (0<=start<1e12 and 0<delay<=60):
        return None
    return (start,start+delay)

def quarantine_overlaps(events):
    """Remove all events sharing the same observed transition in overlapping windows.

    A transition is (capture, stat, direction, before, after). No attempt is made
    to guess which key caused it. Missing timing is explicitly marked unknown.
    """
    by_capture=defaultdict(list)
    for i,event in enumerate(events):
        by_capture[event.get("captureId")].append((i,event))
    excluded=set()
    conflicts=[]
    unknown=[]
    for capture,items in by_capture.items():
        transition_groups=defaultdict(list)
        for i,event in items:
            win=valid_window(event)
            if win is None:
                unknown.append(i)
                continue
            for c in event.get("observedChanges",[]):
                if not isinstance(c,dict):
                    continue
                stat=c.get("stat")
                if not isinstance(stat,str):
                    continue
                for signal in changes({"observedChanges":[c]}):
                    try:
                        token=canonical([stat,signal[1],c.get("before"),c.get("after")])
                    except (TypeError,ValueError):
                        continue
                    transition_groups[token].append((i,win))
        for token,observations in transition_groups.items():
            for a in range(len(observations)):
                i,(start,end)=observations[a]
                for j,(other_start,other_end) in observations[a+1:]:
                    if start<other_end and other_start<end:
                        excluded.update((i,j))
                        conflicts.append({"captureId":capture,
                            "eventIndices":[events[i].get("index"),events[j].get("index")],
                            "inputIdentities":[input_key(events[i]),input_key(events[j])],
                            "reason":"same_outcome_overlapping_windows"})
    # Missing timing cannot support an unambiguous temporal conclusion.
    excluded.update(unknown)
    clean=[event for i,event in enumerate(events) if i not in excluded]
    diagnostics={"total":len(events),"retained":len(clean),
        "quarantined":len(excluded),"missingOrInvalidTiming":len(unknown),
        "overlapPairs":len(conflicts),"conflicts":conflicts}
    return clean,diagnostics

def release(events,place_id,min_per_capture=3,min_captures=2):
    clean,diagnostics=quarantine_overlaps(events)
    report=analyse(clean,min_per_capture,min_captures)
    report["schemaVersion"]="91.review"
    report["placeId"]=place_id
    report["temporalAttribution"]=diagnostics
    # A clean observation is still only a correlation.
    for candidate in report["candidates"]:
        candidate["causalityProven"]=False
        candidate["executionEnabled"]=False
        candidate["verifiedInGame"]=False
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-id",type=int,required=True)
    parser.add_argument("--event-log",type=Path,action="append",required=True)
    parser.add_argument("--output",type=Path,default=Path("build/release-v91"))
    parser.add_argument("--min-per-capture",type=int,default=3)
    parser.add_argument("--min-captures",type=int,default=2)
    args=parser.parse_args()
    events,sources,warnings=read_events(args.event_log,args.place_id)
    report=release(events,args.place_id,args.min_per_capture,args.min_captures)
    # Reuse v90's canonical output and integrity implementation.
    manifest=write_release(args.output,report,sources,warnings)
    # Additional v91 files with accurate names, not a mislabeled v90 artifact.
    directory=Path(args.output)
    names={"review-v91.json":report,
           "contracts-for-review-v91.json":{
               "schemaVersion":"91.contracts","placeId":args.place_id,
               "contracts":[{"id":c["id"],"input":c["input"],
                   "expectedOutcome":c["outcome"],"evidenceStatus":c["status"],
                   "approved":False,"executionEnabled":False,"executionAdapter":None}
                   for c in report["candidates"]]}}
    hashes={}
    for name,document in names.items():
        payload=canonical(document)
        (directory/name).write_bytes(payload)
        hashes[name]=hashlib.sha256(payload).hexdigest()
    manifest["schemaVersion"]="91.manifest"
    manifest["outputs"]=hashes
    (directory/"manifest-v91.json").write_bytes(canonical(manifest))
    # Remove legacy v90-named artifacts from the v91 output directory.
    for name in ("review-v90.json","contracts-for-review-v90.json","manifest-v90.json"):
        (directory/name).unlink(missing_ok=True)
    print(json.dumps({"events":len(events),
        "retained":report["temporalAttribution"]["retained"],
        "quarantined":report["temporalAttribution"]["quarantined"],
        "overlapPairs":report["temporalAttribution"]["overlapPairs"],
        "candidates":len(report["candidates"]),
        "reviewCandidates":sum(c["status"]=="review_candidate" for c in report["candidates"]),
        "warnings":len(warnings),"verifiedInGame":False,
        "output":str(args.output)}))
if __name__=="__main__":
    main()
