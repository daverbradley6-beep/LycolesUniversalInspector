#!/usr/bin/env python3
"""v44 adaptive bounded read-only evidence sampler."""
import argparse,json
from pathlib import Path
def load(p):
 p=Path(p)
 if p.stat().st_size>8000000: raise ValueError("File too large")
 return json.loads(p.read_text(encoding="utf-8-sig"))
def paths(m):
 if m.get("schemaVersion")!="42.0" or m.get("readOnly") is not True: raise ValueError("Expected read-only v42 manifest")
 out=set()
 for f in m["features"]:
  if f.get("kind")!="read-only-inspection" or f.get("gameplayVerified") is not False: raise ValueError("Invalid contract")
  for p in f["evidencePaths"]:
   if not isinstance(p,str) or not 1<=len(p)<=1024 or "." not in p: raise ValueError("Invalid path")
   out.add(p)
 if not 1<=len(out)<=10000: raise ValueError("Invalid path count")
 return sorted(out)
def generate(m):
 p=paths(m)
 config=json.dumps({"paths":p,"scanId":m["scanId"],"placeId":m["placeId"],"sourceFingerprint":m["sourceFingerprint"]},ensure_ascii=True)
 delim="="
 while "]"+delim+"]" in config: delim+="="
 template=r'''-- Lycoles v44: bounded read-only snapshots. No remote calls or gameplay actions.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local previous=pg:FindFirstChild("LycolesV44")
if previous then previous:Destroy() end
local cfg=HttpService:JSONDecode(CONFIG_LITERAL)
if game.PlaceId~=cfg.placeId then warn("Lycoles v44: incorrect place ID") return end
local roots={
 Workspace=workspace,Players=Players,
 ReplicatedStorage=game:GetService("ReplicatedStorage"),
 ReplicatedFirst=game:GetService("ReplicatedFirst"),
 Lighting=game:GetService("Lighting"),StarterGui=game:GetService("StarterGui"),
 StarterPack=game:GetService("StarterPack"),StarterPlayer=game:GetService("StarterPlayer"),
 SoundService=game:GetService("SoundService"),Teams=game:GetService("Teams")
}
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV44"
gui.ResetOnSpawn=false
gui.Parent=pg
local btn=Instance.new("TextButton")
btn.Size=UDim2.fromOffset(400,70)
btn.Position=UDim2.fromScale(.05,.12)
btn.Text="Lycoles v44 | Snapshot 0/8"
btn.Parent=gui
local snapshots={}
local last=-math.huge
local function inspect(path)
 local segments=string.split(path,".")
 local root=table.remove(segments,1)
 local current=roots[root]
 if not current then return {path=path,found=false,reason="unsupported-root",depth=0} end
 local depth=0
 for _,segment in ipairs(segments) do
  if current==Players and (segment=="LocalPlayer" or segment==player.Name) then current=player
  elseif current==player and segment=="PlayerGui" then current=pg
  else
   local child=current:FindFirstChild(segment)
   if not child then return {path=path,found=false,reason="missing-segment",depth=depth,missingSegment=segment} end
   current=child
  end
  depth+=1
 end
 return {path=path,found=true,reason="found",depth=depth,className=current.ClassName}
end
local function emit()
 local receipt={schemaVersion="44.0",scanId=cfg.scanId,placeId=cfg.placeId,
  sourceFingerprint=cfg.sourceFingerprint,snapshots=snapshots,clientReceiptUntrusted=true}
 print("LYCOLES_V44_RECEIPT_BEGIN")
 print(HttpService:JSONEncode(receipt))
 print("LYCOLES_V44_RECEIPT_END")
end
btn.Activated:Connect(function()
 if #snapshots>=8 then emit() return end
 local now=os.clock()
 if now-last<3 then btn.Text="Wait 3 seconds before next snapshot" return end
 last=now
 local checks={}
 local found=0
 for _,path in ipairs(cfg.paths) do
  local c=inspect(path)
  if c.found then found+=1 end
  table.insert(checks,c)
 end
 table.insert(snapshots,{index=#snapshots+1,checks=checks})
 btn.Text="Lycoles v44 | "..#snapshots.."/8 snapshots; "..found.." found"
 emit()
end)
'''
 return template.replace("CONFIG_LITERAL","["+delim+"["+config+"]"+delim+"]")
def analyze(m,r):
 pp=paths(m)
 if r.get("schemaVersion")!="44.0": raise ValueError("Wrong receipt schema")
 for k in ("placeId","scanId","sourceFingerprint"):
  if r.get(k)!=m[k]: raise ValueError("Receipt identity mismatch: "+k)
 snaps=r.get("snapshots")
 if not isinstance(snaps,list) or not 1<=len(snaps)<=32: raise ValueError("Invalid snapshots")
 stats={p:{"foundSnapshots":0,"reasons":{},"missingSegments":{}} for p in pp}
 for i,s in enumerate(snaps,1):
  if s.get("index")!=i or not isinstance(s.get("checks"),list) or len(s["checks"])!=len(pp): raise ValueError("Incomplete snapshot")
  seen=set()
  for c in s["checks"]:
   if not isinstance(c,dict): raise ValueError("Invalid check")
   p=c.get("path"); found=c.get("found"); reason=c.get("reason"); depth=c.get("depth")
   if p not in stats or p in seen or type(found) is not bool: raise ValueError("Unknown or duplicate check")
   if reason not in ("found","missing-segment","unsupported-root") or (reason=="found")!=found: raise ValueError("Inconsistent reason")
   if type(depth) is not int or not 0<=depth<=128: raise ValueError("Invalid depth")
   if reason=="missing-segment":
    seg=c.get("missingSegment")
    if not isinstance(seg,str) or not 1<=len(seg)<=1024: raise ValueError("Invalid missing segment")
    d=stats[p]["missingSegments"];d[seg]=d.get(seg,0)+1
   elif "missingSegment" in c: raise ValueError("Unexpected segment")
   seen.add(p);d=stats[p];d["foundSnapshots"]+=int(found);d["reasons"][reason]=d["reasons"].get(reason,0)+1
 for p,d in stats.items():
  n=d["foundSnapshots"];d["status"]="persistent" if n==len(snaps) else "intermittent" if n else "not-observed"
  d["totalSnapshots"]=len(snaps)
 features=[]
 for f in m["features"]:
  features.append({"id":f["id"],**{state:sum(stats[p]["status"]==state for p in f["evidencePaths"]) for state in ("persistent","intermittent","not-observed")},"mechanicVerified":False,"gameplayAutomationApproved":False})
 return {"schemaVersion":"44.0","placeId":m["placeId"],"scanId":m["scanId"],"sourceFingerprint":m["sourceFingerprint"],"snapshotsAnalyzed":len(snaps),"uniquePaths":len(pp),"paths":stats,"features":features,"runtimeVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,"limitations":["Client receipt is untrusted","Missing paths can be dynamic, streamed or ambiguous dotted names","Object existence does not verify mechanics"]}
def main():
 a=argparse.ArgumentParser()
 a.add_argument("manifest");a.add_argument("--luau",default="build/adaptive-probe-v44.luau")
 a.add_argument("--receipt");a.add_argument("--report",default="build/adaptive-report-v44.json")
 args=a.parse_args();m=load(args.manifest);script=generate(m)
 p=Path(args.luau);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(script,encoding="utf-8")
 print("Generated",p,"with",len(paths(m)),"unique paths")
 if args.receipt:
  result=analyze(m,load(args.receipt));p=Path(args.report);p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
  print("Analyzed",result["snapshotsAnalyzed"],"snapshots into",p)
if __name__=="__main__":main()
