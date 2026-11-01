#!/usr/bin/env python3
"""v79 independent-session evidence validation; review-only action drafts."""
import argparse,json,math,re
from pathlib import Path
from collections import defaultdict
def finite(v):return type(v) in (int,float) and math.isfinite(v)
def flatten(d,prefix=""):
 out={}
 if not isinstance(d,dict):return out
 for k,v in d.items():
  key=prefix+"."+str(k) if prefix else str(k)
  if isinstance(v,dict):out.update(flatten(v,key))
  elif type(v) in (str,bool) or finite(v):out[key]=v
 return out
def classify(a,b):
 if type(a)!=type(b) or a==b:return None
 if finite(a) and finite(b):return "increase" if b>a else "decrease"
 if type(a) is bool:return "toggle"
 if type(a) is str:return "change"
 return None
def parse(paths,place_id):
 records={};warnings=[]
 for path in paths:
  p=Path(path)
  if not p.is_file() or p.stat().st_size>30000000:raise ValueError("Invalid log: "+str(p))
  for line_no,line in enumerate(p.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
   m=re.search(r"LYCOLES_V(76|78|79)_EVENT\s+(\{.*)$",line)
   if not m:continue
   try:e=json.loads(m.group(2))
   except json.JSONDecodeError:warnings.append(str(p)+":"+str(line_no)+": invalid JSON");continue
   if not isinstance(e,dict) or e.get("placeId")!=place_id or e.get("kind") not in ("keyboard","gui"):continue
   if not isinstance(e.get("captureId"),str) or type(e.get("index")) is not int or e["index"]<1:continue
   if not all(isinstance(e.get(k),dict) for k in ("before","after","details")):continue
   d=e["details"]
   if e["kind"]=="keyboard" and (not isinstance(d.get("key"),str) or type(d.get("gameProcessed")) is not bool):continue
   if e["kind"]=="gui" and not isinstance(d.get("uniquePath"),list):continue
   key=(e["captureId"],e["index"])
   if key in records and records[key]!=e:raise ValueError("Conflicting event "+str(key))
   records[key]=e
 return list(records.values()),warnings
def action_key(e):
 d=e["details"]
 if e["kind"]=="keyboard":return json.dumps(["keyboard",d["key"],d["gameProcessed"]],ensure_ascii=False)
 return json.dumps(["gui",d["uniquePath"]],ensure_ascii=False,sort_keys=True)
def evaluate(events,minimum=3,minimum_sessions=2):
 if type(minimum) is not int or minimum<2 or type(minimum_sessions) is not int or minimum_sessions<1:raise ValueError("Invalid thresholds")
 groups=defaultdict(list)
 for e in events:groups[action_key(e)].append(e)
 changed=defaultdict(set)
 for key,items in groups.items():
  for e in items:
   a,b=flatten(e["before"]),flatten(e["after"])
   for s in a.keys()&b.keys():
    op=classify(a[s],b[s])
    if op:changed[(s,op)].add(key)
 results=[]
 for key,items in sorted(groups.items()):
  common=None
  for e in items:
   a,b=flatten(e["before"]),flatten(e["after"])
   current={(s,op) for s in a.keys()&b.keys() if (op:=classify(a[s],b[s]))}
   common=current if common is None else common&current
  enough=len(items)>=minimum and len({e["captureId"] for e in items})>=minimum_sessions
  signals=[{"signal":s,"change":op,"alsoSeenInOtherInputs":len(changed[(s,op)]-{key})>0} for s,op in sorted(common or [])]
  status="review_candidate" if enough and len(signals)==1 and not signals[0]["alsoSeenInOtherInputs"] else "insufficient_or_confounded"
  results.append({"input":json.loads(key),"observations":len(items),"independentSessions":len({e["captureId"] for e in items}),"consistentSignals":signals if enough else [],"status":status,"executionEnabled":False})
 return {"schemaVersion":"79.validation","events":len(events),"groups":results,"verified":False,"executionEnabled":False}
def draft(report,place_id):
 return {"schemaVersion":"79.contract-drafts","placeId":place_id,"executionEnabled":False,"contracts":[{"input":g["input"],"expected":g["consistentSignals"][0],"observations":g["observations"],"sessions":g["independentSessions"],"status":"requires_manual_validation","executionEnabled":False} for g in report["groups"] if g["status"]=="review_candidate"]}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",type=int,required=True);p.add_argument("--event-log",type=Path,action="append",required=True)
 p.add_argument("--output",type=Path,default=Path("build/release-v79"))
 p.add_argument("--min-observations",type=int,default=3);p.add_argument("--min-sessions",type=int,default=2)
 a=p.parse_args()
 if a.place_id<=0:p.error("Place ID must be positive")
 events,warnings=parse(a.event_log,a.place_id)
 report=evaluate(events,a.min_observations,a.min_sessions);contracts=draft(report,a.place_id)
 a.output.mkdir(parents=True,exist_ok=True)
 for name,data in [("validation-v79.json",report),("contract-drafts-v79.json",contracts),("parse-warnings-v79.json",warnings)]:
  (a.output/name).write_text(json.dumps(data,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
 print(json.dumps({"events":len(events),"groups":len(report["groups"]),"drafts":len(contracts["contracts"]),"warnings":len(warnings),"verified":False}))
if __name__=="__main__":main()
