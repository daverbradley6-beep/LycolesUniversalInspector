#!/usr/bin/env python3
"""v84 reproducible, fail-closed release builder for approved GUI actions."""
import argparse,hashlib,json,re
from pathlib import Path
MAX_ACTIONS=100
ALLOWED={"TextButton","ImageButton"}
def validate(doc,place):
 if not isinstance(doc,dict) or type(doc.get("placeId")) is not int or doc["placeId"]!=place:raise ValueError("placeId mismatch")
 contracts=doc.get("contracts")
 if not isinstance(contracts,list) or len(contracts)>MAX_ACTIONS:raise ValueError("contracts must be list with <=100 entries")
 approved=[];ids=set()
 for c in contracts:
  if not isinstance(c,dict):raise ValueError("invalid contract")
  if c.get("approved") is not True:continue
  if c.get("executionEnabled") is True:raise ValueError("pre-enabled execution forbidden")
  ident=c.get("id")
  if not isinstance(ident,str) or not re.fullmatch("[A-Za-z][A-Za-z0-9_-]{0,39}",ident):raise ValueError("invalid ID")
  if ident in ids:raise ValueError("duplicate ID")
  ids.add(ident)
  action=c.get("input")
  if not isinstance(action,list) or len(action)!=2 or action[0]!="gui":raise ValueError("only GUI actions supported")
  path=action[1]
  if isinstance(path,str):path=json.loads(path)
  if not isinstance(path,list) or not 1<=len(path)<=30:raise ValueError("invalid path")
  for s in path:
   if not isinstance(s,dict) or not isinstance(s.get("name"),str) or not isinstance(s.get("className"),str) or type(s.get("ordinal")) is not int:raise ValueError("invalid segment")
   if not 1<=s["ordinal"]<=1000 or len(s["name"])>120 or len(s["className"])>80:raise ValueError("segment out of bounds")
  if path[-1]["className"] not in ALLOWED:raise ValueError("not a GUI button")
  signals=c.get("expectedSignals",[])
  if not isinstance(signals,list) or len(signals)>10:raise ValueError("invalid signals")
  for sig in signals:
   if not isinstance(sig,dict) or not isinstance(sig.get("stat"),str) or sig.get("operator") not in ("increase","decrease","toggle","change"):raise ValueError("invalid expected signal")
  approved.append({"id":ident,"path":path,"expectedSignals":signals})
 return approved
def luau_long_string(value):
 for n in range(32):
  eq="="*n;close="]"+eq+"]"
  if close not in value:return "["+eq+"["+value+close
 raise ValueError("no safe delimiter")
def compile_runner(contracts,place,template):
 payload=json.dumps(contracts,ensure_ascii=False,separators=(",",":"))
 if template.count("__PLACE__")!=1 or template.count("__PAYLOAD__")!=1:raise ValueError("invalid template markers")
 return template.replace("__PLACE__",str(place)).replace("__PAYLOAD__",luau_long_string(payload))
def build(doc,place,template):
 approved=validate(doc,place);script=compile_runner(approved,place,template);raw=script.encode("utf-8")
 manifest={"schemaVersion":"84.release","placeId":place,"approvedActions":len(approved),"actionIds":[x["id"] for x in approved],"runnerSha256":hashlib.sha256(raw).hexdigest(),"runnerBytes":len(raw),"automaticallyExecuted":0,"verifiedInGame":False,"supportsRemotes":False}
 return script,manifest
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",type=int,required=True);p.add_argument("--contracts",type=Path,required=True)
 p.add_argument("--output",type=Path,default=Path("build/release-v84"));p.add_argument("--force",action="store_true")
 a=p.parse_args()
 if a.place_id<=0:p.error("invalid place ID")
 from interactive_runner_v82 import LUA
 script,manifest=build(json.loads(a.contracts.read_text(encoding="utf-8-sig")),a.place_id,LUA)
 a.output.mkdir(parents=True,exist_ok=True)
 target=a.output/"interactive-runner-v84.luau";report=a.output/"release-manifest-v84.json"
 if not a.force and (target.exists() or report.exists()):p.error("release exists; use --force")
 target.write_text(script,encoding="utf-8")
 report.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if hashlib.sha256(target.read_bytes()).hexdigest()!=manifest["runnerSha256"]:raise RuntimeError("integrity mismatch")
 print(json.dumps(manifest,ensure_ascii=False))
if __name__=="__main__":main()
