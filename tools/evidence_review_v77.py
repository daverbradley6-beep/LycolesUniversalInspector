#!/usr/bin/env python3
"""v77: strict multi-signal observation analysis and review-only action contracts."""
import argparse, json, math, re
from collections import defaultdict
from pathlib import Path

def _num(v):
    return type(v) in (int,float) and math.isfinite(v)

def read_events(paths, place_id):
    found={}
    for path in paths:
        p=Path(path)
        if not p.is_file() or p.stat().st_size>30_000_000:
            raise ValueError("missing or oversized log: "+str(p))
        for line in p.read_text(encoding="utf-8-sig",errors="replace").splitlines():
            match=re.search(r"LYCOLES_V7[67]_EVENT\s+(\{.*)$",line)
            if not match: continue
            try: e=json.loads(match.group(1))
            except json.JSONDecodeError: continue
            if not isinstance(e,dict) or e.get("placeId")!=place_id or e.get("kind") not in ("gui","keyboard"): continue
            if type(e.get("index")) is not int or e["index"]<1 or not isinstance(e.get("captureId"),str):continue
            if not all(isinstance(e.get(k),dict) for k in ("before","after","details")):continue
            if e["kind"]=="keyboard" and not isinstance(e["details"].get("key"),str):continue
            if e["kind"]=="gui" and not isinstance(e["details"].get("uniquePath"),list):continue
            identity=(e["captureId"],e["index"])
            if identity in found and found[identity]!=e: raise ValueError("conflicting capture/index")
            found[identity]=e
    return sorted(found.values(),key=lambda e:(e["captureId"],e["index"]))

def identity(e):
    d=e["details"]
    if e["kind"]=="keyboard":
        return "keyboard:"+d["key"]+":processed="+str(d.get("gameProcessed"))
    return "gui:"+json.dumps(d["uniquePath"],ensure_ascii=False,sort_keys=True,separators=(",",":"))

def flatten(state):
    out={}
    for k,v in state.items():
        if isinstance(v,dict):
            for sub,val in flatten(v).items():out[str(k)+"."+sub]=val
        elif isinstance(v,(str,bool,int,float)) and not (type(v) is float and not math.isfinite(v)):
            out[str(k)]=v
    return out

def diff(before,after):
    a,b=flatten(before),flatten(after)
    changes={}
    for k in sorted(a.keys() & b.keys()):
        x,y=a[k],b[k]
        if type(x)!=type(y) or x==y:continue
        if _num(x) and _num(y):
            op="increased" if y>x else "decreased"
            changes[k]={"operator":op,"delta":y-x}
        elif type(x) is bool and type(y) is bool:changes[k]={"operator":"toggled"}
        else:changes[k]={"operator":"changed"}
    return changes

def analyze(events,min_repeats=3):
    if type(min_repeats) is not int or not 2<=min_repeats<=100:raise ValueError("min_repeats must be 2..100")
    groups=defaultdict(list)
    for e in events:groups[identity(e)].append(e)
    results=[]
    for key,items in sorted(groups.items()):
        change_sets=[diff(e["before"],e["after"]) for e in items]
        names=set.intersection(*(set(c) for c in change_sets)) if change_sets else set()
        consistent=[]
        for name in sorted(names):
            ops={c[name]["operator"] for c in change_sets}
            if len(ops)==1:
                op=next(iter(ops))
                deltas=[c[name].get("delta") for c in change_sets]
                consistent.append({"signal":name,"operator":op,"samples":len(items),
                    "deltaRange":[min(deltas),max(deltas)] if all(_num(d) for d in deltas) else None})
        qualified=len(items)>=min_repeats and len(set(e["captureId"] for e in items))>=1
        results.append({"input":key,"observations":len(items),"captures":sorted(set(e["captureId"] for e in items)),
          "consistentSignals":consistent if qualified else [],
          "status":"review_candidate" if qualified and len(consistent)==1 else "insufficient_or_ambiguous",
          "examples":[{"captureId":e["captureId"],"index":e["index"]} for e in items[:5]]})
    return {"schemaVersion":"77.review","events":len(events),"groups":results,
      "verified":False,"automaticExecution":False}

def contracts(report,place_id):
    proposed=[]
    for g in report["groups"]:
        if g["status"]!="review_candidate":continue
        signal=g["consistentSignals"][0]
        proposed.append({"input":g["input"],"expected":signal,"observations":g["observations"],
            "status":"unverified_review_required","executionEnabled":False})
    return {"schemaVersion":"77.contract-drafts","placeId":place_id,"contracts":proposed,
            "executionEnabled":False,"warning":"Observational correlation only; never execute without independent verification."}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--place-id",type=int,required=True)
    ap.add_argument("--event-log",type=Path,action="append",required=True)
    ap.add_argument("--output",type=Path,default=Path("build/release-v77"))
    ap.add_argument("--min-repeats",type=int,default=3)
    args=ap.parse_args()
    if args.place_id<=0:ap.error("invalid place ID")
    events=read_events(args.event_log,args.place_id)
    report=analyze(events,args.min_repeats)
    draft=contracts(report,args.place_id)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"evidence-review-v77.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (args.output/"contract-drafts-v77.json").write_text(json.dumps(draft,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"events":len(events),"groups":len(report["groups"]),"drafts":len(draft["contracts"]),"verified":False}))
if __name__=="__main__":main()
