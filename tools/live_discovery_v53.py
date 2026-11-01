#!/usr/bin/env python3
"""v53 bounded, game-independent, read-only live discovery and offline analysis."""
import argparse, json
from collections import Counter
from pathlib import Path

ROOTS=("Workspace","Players","ReplicatedStorage","ReplicatedFirst","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams")
MAX_OBJECTS=2500
MAX_SAMPLES=24

def generate(place_id,seconds=30,period=3,max_objects=MAX_OBJECTS):
    if type(place_id) is not int or place_id<=0: raise ValueError("Invalid place")
    if type(seconds) is not int or not 6<=seconds<=120: raise ValueError("Invalid duration")
    if type(period) is not int or not 1<=period<=10: raise ValueError("Invalid period")
    if type(max_objects) is not int or not 50<=max_objects<=MAX_OBJECTS: raise ValueError("Invalid cap")
    count=min(MAX_SAMPLES,seconds//period+1)
    template=r'''-- Lycoles v53: bounded, read-only discovery. No remote invocation.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player then return end
if game.PlaceId~=PLACE_ID then warn("Lycoles v53: place mismatch") return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV53")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV53"
gui.ResetOnSpawn=false
gui.Parent=pg
local label=Instance.new("TextLabel")
label.Size=UDim2.fromOffset(440,65)
label.Position=UDim2.fromScale(.04,.16)
label.Text="Lycoles v53 | Discovery starting"
label.Parent=gui
local roots={
 {"Workspace",workspace},{"Players",Players},
 {"ReplicatedStorage",game:GetService("ReplicatedStorage")},
 {"ReplicatedFirst",game:GetService("ReplicatedFirst")},
 {"Lighting",game:GetService("Lighting")},
 {"StarterGui",game:GetService("StarterGui")},
 {"StarterPack",game:GetService("StarterPack")},
 {"StarterPlayer",game:GetService("StarterPlayer")},
 {"SoundService",game:GetService("SoundService")},
 {"Teams",game:GetService("Teams")}
}
local function valueOf(inst)
 local ok,v=pcall(function()
  if inst:IsA("ValueBase") then return inst.Value end
  if inst:IsA("TextLabel") or inst:IsA("TextButton") then return inst.Text end
  if inst:IsA("ProximityPrompt") then return inst.Enabled end
  return nil
 end)
 if ok and (type(v)=="string" or type(v)=="number" or type(v)=="boolean") then
  return tostring(v):sub(1,100)
 end
 return nil
end
local function capture()
 local queue={}
 for _,root in ipairs(roots) do
  table.insert(queue,{root[2],root[1],0})
 end
 local entries={}
 local visited=0
 local cursor=1
 local truncated=false
 while cursor<=#queue do
  if visited>=MAX_OBJECTS then truncated=true break end
  local node=queue[cursor]
  cursor+=1
  local inst,path,depth=node[1],node[2],node[3]
  visited+=1
  local item={path=path,className=inst.ClassName}
  local v=valueOf(inst)
  if v~=nil then item.value=v end
  table.insert(entries,item)
  if depth<8 then
   local ok,children=pcall(function() return inst:GetChildren() end)
   if ok then
    table.sort(children,function(a,b) return a.Name<b.Name end)
    for _,child in ipairs(children) do
     if #queue>=MAX_OBJECTS*3 then truncated=true break end
     -- Preserve exact names in segments; dots are not split.
     local encoded=HttpService:JSONEncode(child.Name)
     table.insert(queue,{child,path.."/"..encoded,depth+1})
    end
   end
  end
 end
 return entries,truncated
end
local observations={}
task.spawn(function()
 for i=1,SAMPLE_COUNT do
  if not gui.Parent then return end
  local entries,truncated=capture()
  table.insert(observations,{index=i,entries=entries,truncated=truncated})
  label.Text="Lycoles v53 | "..tostring(i).."/"..tostring(SAMPLE_COUNT).." samples; "..tostring(#entries).." objects"
  if i<SAMPLE_COUNT then task.wait(SAMPLE_PERIOD) end
 end
 local receipt={schemaVersion="53.0",placeId=PLACE_ID,clientReceiptUntrusted=true,observations=observations}
 print("LYCOLES_V53_BEGIN")
 print(HttpService:JSONEncode(receipt))
 print("LYCOLES_V53_END")
 label.Text="Lycoles v53 | Complete; save console receipt"
end)
'''
    return (template.replace("PLACE_ID",str(place_id)).replace("MAX_OBJECTS",str(max_objects))
            .replace("SAMPLE_COUNT",str(count)).replace("SAMPLE_PERIOD",str(period)))

def analyze(receipt,expected_place=None):
    if not isinstance(receipt,dict) or receipt.get("schemaVersion")!="53.0": raise ValueError("Invalid v53 receipt")
    pid=receipt.get("placeId")
    if type(pid) is not int or pid<=0 or (expected_place is not None and pid!=expected_place): raise ValueError("Place mismatch")
    samples=receipt.get("observations")
    if not isinstance(samples,list) or not 2<=len(samples)<=MAX_SAMPLES: raise ValueError("Invalid samples")
    states={}
    truncations=0
    for n,sample in enumerate(samples,1):
        if not isinstance(sample,dict) or sample.get("index")!=n: raise ValueError("Invalid sample index")
        items=sample.get("entries")
        if not isinstance(items,list) or len(items)>MAX_OBJECTS: raise ValueError("Invalid inventory")
        if type(sample.get("truncated")) is not bool: raise ValueError("Invalid truncation")
        truncations+=int(sample["truncated"])
        seen=set()
        for item in items:
            if not isinstance(item,dict): raise ValueError("Invalid entry")
            p,c=item.get("path"),item.get("className")
            if not isinstance(p,str) or not 1<=len(p)<=1024 or not isinstance(c,str) or not 1<=len(c)<=100 or p in seen: raise ValueError("Invalid path or class")
            seen.add(p)
            v=item.get("value")
            if v is not None and (not isinstance(v,str) or len(v)>100): raise ValueError("Invalid value")
            states.setdefault(p,{})[n]=(c,v)
    rows=[]
    for p,observed in sorted(states.items()):
        ordered=[observed.get(i) for i in range(1,len(samples)+1)]
        transitions=sum(ordered[i]!=ordered[i-1] for i in range(1,len(ordered)))
        vals={x[1] for x in ordered if x is not None and x[1] is not None}
        rows.append({"path":p,"className":Counter(x[0] for x in observed.values()).most_common(1)[0][0],
                     "visibleSamples":len(observed),"stateTransitions":transitions,"valueChanged":len(vals)>1,
                     "classification":"changing" if transitions else "stable-visible" if len(observed)==len(samples) else "intermittent"})
    return {"schemaVersion":"53.0","placeId":pid,"samples":len(samples),"discoveredPaths":len(rows),
            "truncatedSamples":truncations,"changingPaths":sum(r["stateTransitions"]>0 for r in rows),
            "paths":rows,"mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,
            "limitations":["Client receipt is untrusted","Discovery is bounded by depth and object count","Object changes are not proof of gameplay mechanics","Path segments are JSON-quoted to preserve dots"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v53"))
    p.add_argument("--receipt",type=Path)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"live-discovery-v53.luau").write_text(generate(a.place_id),encoding="utf-8")
    if a.receipt:
        if a.receipt.stat().st_size>24_000_000: raise ValueError("Receipt too large")
        raw=a.receipt.read_text(encoding="utf-8-sig")
        if "LYCOLES_V53_BEGIN" in raw: raw=raw.split("LYCOLES_V53_BEGIN")[-1].split("LYCOLES_V53_END")[0].strip()
        report=analyze(json.loads(raw),a.place_id)
        (a.output/"live-discovery-analysis-v53.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
        print("Analysed",report["discoveredPaths"],"paths")
    print("Generated v53 live discovery")
if __name__=="__main__": main()
