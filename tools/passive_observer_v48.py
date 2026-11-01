#!/usr/bin/env python3
"""v48: passive state-change correlation; no gameplay actions or remote calls."""
import argparse,json
from pathlib import Path
from adaptive_probe_v44 import paths

def generate(manifest, seconds=30, period=2):
    if type(seconds) is not int or not 6<=seconds<=120 or type(period) is not int or not 1<=period<=10:
        raise ValueError("Invalid sampling configuration")
    pp=paths(manifest)
    if len(pp)>10000:raise ValueError("Excessive paths")
    cfg=json.dumps({"paths":pp,"placeId":manifest["placeId"],"scanId":manifest["scanId"],"sourceFingerprint":manifest["sourceFingerprint"]},ensure_ascii=True)
    delimiter="="
    while "]"+delimiter+"]" in cfg:delimiter+="="
    template=r'''-- Lycoles v48 passive state-change observer.
-- Observe normal gameplay; no RemoteEvent calls, no interaction injection.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local cfg=HttpService:JSONDecode(CONFIG_LITERAL)
if game.PlaceId~=cfg.placeId then warn("Lycoles v48: place mismatch") return end
local old=pg:FindFirstChild("LycolesV48")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV48"
gui.ResetOnSpawn=false
gui.Parent=pg
local label=Instance.new("TextLabel")
label.Size=UDim2.fromOffset(430,55)
label.Position=UDim2.fromScale(.05,.2)
label.Text="Lycoles v48 | Passive observation"
label.Parent=gui
local roots={
 Workspace=workspace,Players=Players,ReplicatedStorage=game:GetService("ReplicatedStorage"),
 ReplicatedFirst=game:GetService("ReplicatedFirst"),Lighting=game:GetService("Lighting"),
 StarterGui=game:GetService("StarterGui"),StarterPack=game:GetService("StarterPack"),
 StarterPlayer=game:GetService("StarterPlayer"),SoundService=game:GetService("SoundService"),
 Teams=game:GetService("Teams")
}
local function resolve(path)
 local parts=string.split(path,".")
 local current=roots[table.remove(parts,1)]
 if not current then return nil end
 for _,part in ipairs(parts) do
  if current==Players and (part=="LocalPlayer" or part==player.Name) then current=player
  elseif current==player and part=="PlayerGui" then current=pg
  else current=current:FindFirstChild(part) end
  if not current then return nil end
 end
 return current
end
local function sample(path)
 local inst=resolve(path)
 if not inst then return {path=path,present=false} end
 local item={path=path,present=true,className=inst.ClassName}
 if inst:IsA("ValueBase") then
  local ok,v=pcall(function() return inst.Value end)
  if ok and (type(v)=="number" or type(v)=="boolean" or type(v)=="string") then
   item.value=tostring(v):sub(1,120)
  end
 elseif inst:IsA("TextLabel") or inst:IsA("TextButton") then
  item.value=inst.Text:sub(1,120)
 end
 return item
end
local observations={}
task.spawn(function()
 for index=1, SAMPLE_COUNT do
  if not gui.Parent then return end
  local checks={}
  for _,path in ipairs(cfg.paths) do table.insert(checks,sample(path)) end
  table.insert(observations,{index=index,checks=checks})
  label.Text="Lycoles v48 | "..index.."/"..SAMPLE_COUNT.." samples"
  if index<SAMPLE_COUNT then task.wait(SAMPLE_PERIOD) end
 end
 local receipt={schemaVersion="48.0",placeId=cfg.placeId,scanId=cfg.scanId,
  sourceFingerprint=cfg.sourceFingerprint,observations=observations,clientReceiptUntrusted=true}
 print("LYCOLES_V48_BEGIN")
 print(HttpService:JSONEncode(receipt))
 print("LYCOLES_V48_END")
 label.Text="Lycoles v48 | Complete; see console"
end)
'''
    return template.replace("CONFIG_LITERAL","["+delimiter+"["+cfg+"]"+delimiter+"]").replace("SAMPLE_COUNT",str(seconds//period+1)).replace("SAMPLE_PERIOD",str(period))

def analyze(manifest,receipt):
    pp=paths(manifest)
    if not isinstance(receipt,dict) or receipt.get("schemaVersion")!="48.0":raise ValueError("Expected v48 receipt")
    for key in ("placeId","scanId","sourceFingerprint"):
        if type(receipt.get(key))!=type(manifest[key]) or receipt[key]!=manifest[key]:raise ValueError("Identity mismatch")
    obs=receipt.get("observations")
    if not isinstance(obs,list) or not 2<=len(obs)<=121:raise ValueError("Invalid observation count")
    states={p:[] for p in pp}
    for index,snapshot in enumerate(obs,1):
        if not isinstance(snapshot,dict) or snapshot.get("index")!=index:raise ValueError("Invalid snapshot index")
        checks=snapshot.get("checks")
        if not isinstance(checks,list) or len(checks)!=len(pp):raise ValueError("Incomplete inventory")
        seen=set()
        for item in checks:
            if not isinstance(item,dict):raise ValueError("Invalid observation")
            p=item.get("path")
            if not isinstance(p,str) or p not in states or p in seen:raise ValueError("Unknown or duplicate path")
            seen.add(p)
            present=item.get("present")
            if type(present) is not bool:raise ValueError("Invalid presence")
            if present:
                cls=item.get("className")
                if not isinstance(cls,str) or not 1<=len(cls)<=100:raise ValueError("Invalid class")
            elif "value" in item or "className" in item:raise ValueError("Missing object has value")
            val=item.get("value")
            if val is not None and (not present or not isinstance(val,str) or len(val)>120):raise ValueError("Invalid value")
            states[p].append((present,item.get("className") if present else None,val))
    result={}
    for p,sequence in states.items():
        changes=sum(sequence[i]!=sequence[i-1] for i in range(1,len(sequence)))
        visible=sum(item[0] for item in sequence)
        result[p]={"visibleSamples":visible,"samples":len(sequence),"stateTransitions":changes,
                   "valueChanged":len({v for present,cls,v in sequence if present and v is not None})>1,
                   "classification":"changing" if changes else "stable-visible" if visible else "not-observed"}
    return {"schemaVersion":"48.0","placeId":manifest["placeId"],"scanId":manifest["scanId"],
            "sourceFingerprint":manifest["sourceFingerprint"],"samples":len(obs),"paths":result,
            "clientReceiptUntrusted":True,"mechanicVerified":False,"serverOutcomeVerified":False,
            "gameplayAutomationApproved":False,
            "limitations":["State changes are correlation only, not causation","Client observations are untrusted","No gameplay actions are generated"]}

def main():
    a=argparse.ArgumentParser()
    a.add_argument("manifest",type=Path)
    a.add_argument("--receipt",type=Path)
    a.add_argument("--output",type=Path,default=Path("build"))
    args=a.parse_args()
    if args.manifest.stat().st_size>8000000:raise ValueError("Oversized manifest")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"passive-observer-v48.luau").write_text(generate(manifest),encoding="utf-8")
    if args.receipt:
        if args.receipt.stat().st_size>16000000:raise ValueError("Oversized receipt")
        raw=args.receipt.read_text(encoding="utf-8-sig")
        if "LYCOLES_V48_BEGIN" in raw:
            raw=raw.split("LYCOLES_V48_BEGIN")[-1].split("LYCOLES_V48_END")[0].strip()
        report=analyze(manifest,json.loads(raw))
        (args.output/"state-changes-v48.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("Analysed",report["samples"],"passive samples")
    print("Generated v48 passive observer for",len(paths(manifest)),"paths")
if __name__=="__main__":main()
