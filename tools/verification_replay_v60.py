#!/usr/bin/env python3
"""v60 deterministic gameplay verification replay and guarded release gate.

Replay verifies contract observations from author-controlled tests. It never
infers permission or remote call signatures from game discovery.
"""
import argparse,json,hashlib,math
from pathlib import Path
from gameplay_workflows_v58 import validate as validate_contract
from gameplay_planner_v59 import plan as gameplay_plan,build as build_v59
from balanced_discovery_v54 import analyze

MAX_EVENTS=10000
def verify(contract,trace):
    validate_contract(contract)
    if not isinstance(trace,dict) or trace.get("schemaVersion")!="60.trace":
        raise ValueError("Invalid trace schema")
    if trace.get("placeId")!=contract["placeId"]:
        raise ValueError("Trace place mismatch")
    events=trace.get("events")
    if not isinstance(events,list) or not 1<=len(events)<=MAX_EVENTS:
        raise ValueError("Invalid event count")
    allowed={a["id"]:a for a in contract["actions"]}
    grouped={key:[] for key in allowed}
    previous=-1.0
    for e in events:
        if not isinstance(e,dict) or set(e)!={"time","actionId","kind","value"}:
            raise ValueError("Malformed trace event")
        t=e["time"]
        if type(t) not in (int,float) or not math.isfinite(t) or t<previous:
            raise ValueError("Trace timestamps must be finite and sorted")
        previous=t
        if e["actionId"] not in allowed or e["kind"] not in ("before","after","error"):
            raise ValueError("Unknown action or event kind")
        if type(e["value"]) not in (int,float) or not math.isfinite(e["value"]):
            raise ValueError("Invalid metric value")
        grouped[e["actionId"]].append(e)
    results=[]
    for a in contract["actions"]:
        seq=grouped[a["id"]]
        attempts=[]
        index=0
        while index<len(seq):
            before=seq[index]
            if before["kind"]!="before":
                attempts.append({"status":"invalid_trace","reason":"Expected before event"})
                index+=1
                continue
            if index+1>=len(seq):
                attempts.append({"status":"incomplete","reason":"Missing outcome event"})
                index+=1
                continue
            after=seq[index+1]
            index+=2
            elapsed=after["time"]-before["time"]
            if after["kind"]=="error":
                status="failed"
            elif after["kind"]!="after" or elapsed<0:
                status="invalid_trace"
            elif elapsed>a.get("timeoutSeconds",5):
                status="timed_out"
            elif after["value"]-before["value"]>=a["expectedValue"]["minimumDelta"]:
                status="observed"
            else:
                status="unverified"
            attempts.append({"status":status,"elapsedSeconds":elapsed,
                             "delta":after["value"]-before["value"]})
        expected=a.get("repeatCount",1)
        observed=sum(x["status"]=="observed" for x in attempts)
        results.append({"id":a["id"],"expectedAttempts":expected,
                        "observedAttempts":observed,
                        "status":"observational_pass" if len(attempts)==expected and observed==expected
                                 else "not_verified",
                        "attempts":attempts})
    return {"schemaVersion":"60.verification","placeId":contract["placeId"],
            "results":results,
            "allObserved":all(x["status"]=="observational_pass" for x in results),
            "serverOutcomeVerified":False,
            "causalityVerified":False,
            "note":"Offline trace replay cannot establish server-side causality"}
def release(receipt,contract,trace,out):
    evidence=analyze(receipt)
    planned=gameplay_plan(receipt,contract)
    verification=verify(contract,trace)
    verified_ids={r["id"] for r in verification["results"] if r["status"]=="observational_pass"}
    ready_ids={r["id"] for r in planned["authorizedActions"]}
    approved=verified_ids & ready_ids
    manifest={"schemaVersion":"60.release","placeId":evidence["placeId"],
              "observationallyPassed":sorted(approved),
              "notVerified":sorted({a["id"] for a in contract["actions"]}-approved),
              "serverOutcomeVerified":False,
              "liveGameTestedByThisCompiler":False,
              "discoverySamples":evidence["samples"]}
    manifest["fingerprint"]=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    out.mkdir(parents=True,exist_ok=True)
    (out/"verification-v60.json").write_text(json.dumps(verification,indent=2)+"\n",encoding="utf-8")
    (out/"release-manifest-v60.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    if approved:
        selected={**contract,"actions":[a for a in contract["actions"] if a["id"] in approved]}
        build_v59(receipt,selected,out)
    return manifest
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--contract",type=Path,required=True)
    p.add_argument("--trace",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v60"))
    a=p.parse_args()
    for f in (a.receipt,a.contract,a.trace):
        if f.stat().st_size>50_000_000:raise ValueError("Input too large")
    result=release(a.receipt.read_text(encoding="utf-8-sig"),
                   json.loads(a.contract.read_text(encoding="utf-8-sig")),
                   json.loads(a.trace.read_text(encoding="utf-8-sig")),a.output)
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
