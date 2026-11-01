#!/usr/bin/env python3
"""v54 universal balanced client discovery, offline evidence analysis, and read-only dashboard."""
import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict

ROOTS=("Workspace","Players","ReplicatedStorage","ReplicatedFirst","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams")
PRIORITY={"ValueBase","RemoteEvent","RemoteFunction","BindableEvent","BindableFunction","ProximityPrompt","ClickDetector","TextButton","ImageButton","Tool"}
MAX_RECORDS=4000
def generate(place_id, samples=12, interval=3, cap=3500):
    if type(place_id)!=int or place_id<=0: raise ValueError("Invalid place")
    if type(samples)!=int or not 2<=samples<=24: raise ValueError("Invalid samples")
    if type(interval)!=int or not 1<=interval<=10: raise ValueError("Invalid interval")
    if type(cap)!=int or not 200<=cap<=3500: raise ValueError("Invalid cap")
    t=r'''-- Lycoles v54. Read-only. No remote calls or gameplay manipulation.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
if game.PlaceId~=PLACE_ID then warn("Lycoles v54: wrong place") return end
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local prior=pg:FindFirstChild("LycolesV54")
if prior then prior:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV54"
gui.ResetOnSpawn=false
gui.Parent=pg
local label=Instance.new("TextLabel")
label.Size=UDim2.fromOffset(520,64)
label.Position=UDim2.fromScale(.02,.15)
label.BackgroundTransparency=.2
label.TextScaled=true
label.Text="Lycoles v54: starting"
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
local priorities={ValueBase=true,RemoteEvent=true,RemoteFunction=true,BindableEvent=true,
 BindableFunction=true,ProximityPrompt=true,ClickDetector=true,TextButton=true,
 ImageButton=true,Tool=true}
local function interested(obj)
 return priorities[obj.ClassName] or obj:IsA("ValueBase")
  or obj:IsA("GuiButton") or obj:IsA("ProximityPrompt")
end
local function readValue(obj)
 local ok,value=pcall(function()
  if obj:IsA("ValueBase") then return obj.Value end
  if obj:IsA("TextLabel") or obj:IsA("TextButton") then return obj.Text end
  if obj:IsA("ProximityPrompt") then return obj.Enabled end
  return nil
 end)
 if ok and (type(value)=="string" or type(value)=="number" or type(value)=="boolean") then
  return tostring(value):sub(1,120)
 end
 return nil
end
local function orderedChildren(obj)
 local ok,children=pcall(function() return obj:GetChildren() end)
 if not ok then return {} end
 table.sort(children,function(a,b)
  if a.Name==b.Name then return a.ClassName<b.ClassName end
  return a.Name<b.Name
 end)
 local counts={}
 local result={}
 for _,child in ipairs(children) do
  local key=child.Name.."|"..child.ClassName
  counts[key]=(counts[key] or 0)+1
  local segment=HttpService:JSONEncode(child.Name).."#"..tostring(counts[key]).."@"..child.ClassName
  table.insert(result,{child,segment})
 end
 return result
end
local tracked={}
local emittedPaths={}
local state={}
for _,root in ipairs(roots) do
 state[root[1]]={queue={{root[2],root[1],0}},cursor=1,visited=0}
end
local function capture()
 local items={}
 local seen={}
 local perRoot={}
 local budget=math.floor(CAP/#roots)
 local overflow=CAP-budget*#roots
 for _,root in ipairs(roots) do
  local name=root[1]
  local s=state[name]
  local allowed=budget+(overflow>0 and 1 or 0)
  if overflow>0 then overflow-=1 end
  local used=0
  while used<allowed and s.cursor<=#s.queue do
   local node=s.queue[s.cursor]
   s.cursor+=1
   local obj,path,depth=node[1],node[2],node[3]
   if obj and (depth==0 or obj.Parent) then
    used+=1
    s.visited+=1
    local item={path=path,className=obj.ClassName,root=name}
    local value=readValue(obj)
    if value~=nil then item.value=value end
    if interested(obj) then
     item.priority=true
     tracked[path]={object=obj,root=name,className=obj.ClassName}
    end
    table.insert(items,item)
    seen[path]=true
    if depth<12 then
     for _,pair in ipairs(orderedChildren(obj)) do
      if #s.queue-s.cursor<30000 then
       table.insert(s.queue,{pair[1],path.."/"..pair[2],depth+1})
      end
     end
    end
   end
  end
  perRoot[name]={visited=s.visited,pending=math.max(0,#s.queue-s.cursor+1),sampled=used}
 end
 -- Resample high-signal objects so changes are measurable despite incremental traversal.
 local revisited=0
 local keys={}
 for path,_ in pairs(tracked) do table.insert(keys,path) end
 table.sort(keys)
 for _,path in ipairs(keys) do
  if revisited>=300 then break end
  local info=tracked[path]
  if info.object.Parent and not seen[path] then
   local v=readValue(info.object)
   local item={path=path,className=info.className,root=info.root,priority=true,resampled=true}
   if v~=nil then item.value=v end
   table.insert(items,item)
   revisited+=1
  elseif not info.object.Parent then
   tracked[path]=nil
  end
 end
 return items,perRoot
end
-- v54.2 incremental bounded export; encode individual entry groups.
local function emitSample(index,items,coverage)
 local compact={}
 for _,item in ipairs(items) do
  if item.priority or not emittedPaths[item.path] then
   compact[#compact+1]=item
   emittedPaths[item.path]=true
  end
 end
 items=compact
 local batches={}
 local size=25
 for first=1,#items,size do
  local entries={}
  for k=first,math.min(#items,first+size-1) do
   entries[#entries+1]=items[k]
  end
  local ok,encoded=pcall(function()
   return HttpService:JSONEncode({index=index,entries=entries,
    coverage=(first==1 and coverage or nil)})
  end)
  if not ok then
   warn("Lycoles v54: batch JSON failed sample "..index.." entry "..first.." "..tostring(encoded))
   return false
  end
  batches[#batches+1]=encoded
 end
 print("LYCOLES_V54_BATCH_BEGIN "..index.." "..#batches)
 for i,encoded in ipairs(batches) do
  print("LYCOLES_V54_BATCH "..index.."/"..i.."/"..#batches.." "..encoded)
 end
 print("LYCOLES_V54_BATCH_END "..index)
 return true
end
task.spawn(function()
 print("LYCOLES_V54_BATCH_STREAM_BEGIN "..tostring(PLACE_ID).." "..tostring(SAMPLES))
 for i=1,SAMPLES do
  if not gui.Parent then return end
  local okCapture,items,coverage=pcall(capture)
  if not okCapture then
   warn("Lycoles v54: capture failed sample "..i..": "..tostring(items))
   label.Text="Lycoles v54 capture failed sample "..i
   return
  end
  label.Text="Lycoles v54 | "..tostring(i).."/"..tostring(SAMPLES).." | "..tostring(#items).." objects"
  local okExport,exported=pcall(emitSample,i,items,coverage)
  if not okExport then
   warn("Lycoles v54: export crashed sample "..i..": "..tostring(exported))
  end
  if not okExport or not exported then
   label.Text="Lycoles v54 failed to encode sample "..i
   return
  end
  items=nil
  if i<SAMPLES then task.wait(INTERVAL) end
 end
 print("LYCOLES_V54_BATCH_STREAM_END")
 label.Text="Lycoles v54 complete | Save all batch console lines"
end)
'''
    return t.replace("PLACE_ID",str(place_id)).replace("SAMPLES",str(samples)).replace("INTERVAL",str(interval)).replace("CAP",str(cap))

def parse_receipt(raw):
    if isinstance(raw,dict): return raw
    if not isinstance(raw,str): raise ValueError("Expected JSON or console transcript")
    if "LYCOLES_V54_BATCH_STREAM_BEGIN " in raw:
        lines=raw.splitlines()
        start=next((x.split("LYCOLES_V54_BATCH_STREAM_BEGIN ",1)[1] for x in lines if "LYCOLES_V54_BATCH_STREAM_BEGIN " in x),None)
        if start is None or not any("LYCOLES_V54_BATCH_STREAM_END" in x for x in lines):
            raise ValueError("Incomplete batch stream")
        place,count=map(int,start.split())
        if not 2<=count<=24: raise ValueError("Invalid sample count")
        samples=[]
        for index in range(1,count+1):
            prefix="LYCOLES_V54_BATCH_BEGIN "+str(index)+" "
            total_line=next((x.split(prefix,1)[1] for x in lines if prefix in x),None)
            if total_line is None: raise ValueError("Missing sample "+str(index))
            total=int(total_line.strip())
            if not 1<=total<=1000: raise ValueError("Invalid batch count")
            chunks={}
            for line in lines:
                marker="LYCOLES_V54_BATCH "
                if marker not in line: continue
                key,sep,payload=line.split(marker,1)[1].partition(" ")
                if not sep: raise ValueError("Invalid batch")
                i,j,n=map(int,key.split("/"))
                if i!=index: continue
                if n!=total or not 1<=j<=total or j in chunks: raise ValueError("Invalid batch index")
                chunks[j]=json.loads(payload.strip())
            if len(chunks)!=total or not any("LYCOLES_V54_BATCH_END "+str(index) in x for x in lines):
                raise ValueError("Incomplete sample "+str(index))
            entries=[]
            for j in range(1,total+1):
                part=chunks[j]
                if part.get("index")!=index or not isinstance(part.get("entries"),list):
                    raise ValueError("Invalid batch contents")
                entries.extend(part["entries"])
            samples.append({"index":index,"entries":entries})
        return {"schemaVersion":"54.0","placeId":place,"observations":samples}
    if "LYCOLES_V54_STREAM_BEGIN " in raw:
        lines=raw.splitlines()
        start=next((line.split("LYCOLES_V54_STREAM_BEGIN ",1)[1] for line in lines if "LYCOLES_V54_STREAM_BEGIN " in line),None)
        if start is None or "LYCOLES_V54_STREAM_END" not in raw: raise ValueError("Incomplete v54 stream")
        place,count=map(int,start.split())
        if not 2<=count<=24: raise ValueError("Invalid sample count")
        samples=[]
        for index in range(1,count+1):
            begin="LYCOLES_V54_SAMPLE_BEGIN "+str(index)+" "
            header=next((line.split(begin,1)[1] for line in lines if begin in line),None)
            if header is None: raise ValueError("Missing sample "+str(index))
            total=int(header.strip())
            if not 1<=total<=10000: raise ValueError("Invalid sample chunk count")
            chunks={}
            prefix="LYCOLES_V54_SAMPLE_CHUNK "
            for line in lines:
                if prefix not in line: continue
                part=line.split(prefix,1)[1]
                key,sep,payload=part.partition(" ")
                if not sep: raise ValueError("Invalid sample chunk")
                i,j,n=map(int,key.split("/"))
                if i!=index: continue
                if n!=total or not 1<=j<=total or j in chunks: raise ValueError("Duplicate or invalid chunk")
                chunks[j]=payload.strip()
            if len(chunks)!=total or not any("LYCOLES_V54_SAMPLE_END "+str(index) in line for line in lines):
                raise ValueError("Incomplete sample "+str(index))
            sample=json.loads("".join(chunks[j] for j in range(1,total+1)))
            if sample.get("index")!=index: raise ValueError("Sample index mismatch")
            samples.append(sample)
        return {"schemaVersion":"54.0","placeId":place,"observations":samples}
    if "LYCOLES_V54_BEGIN" not in raw: return json.loads(raw)
    lines=raw.splitlines()
    begin=next((x for x in lines if "LYCOLES_V54_BEGIN " in x),None)
    if not begin: raise ValueError("Missing receipt start")
    count=int(begin.rsplit("LYCOLES_V54_BEGIN ",1)[1].strip())
    if not 1<=count<=10000: raise ValueError("Invalid chunk count")
    chunks={}
    for line in lines:
        if "LYCOLES_V54_CHUNK " not in line: continue
        part=line.split("LYCOLES_V54_CHUNK ",1)[1]
        header,sep,payload=part.partition(" ")
        if not sep: raise ValueError("Missing chunk payload")
        index,total=map(int,header.split("/"))
        if total!=count or not 1<=index<=count or index in chunks: raise ValueError("Invalid or duplicate chunk")
        chunks[index]=payload.strip()
    if "LYCOLES_V54_END" not in raw or len(chunks)!=count: raise ValueError("Incomplete receipt")
    return json.loads("".join(chunks[i] for i in range(1,count+1)))

def analyze(receipt, expected_place=None):
    r=parse_receipt(receipt)
    if not isinstance(r,dict) or r.get("schemaVersion") not in ("53.0","54.0"): raise ValueError("Unsupported receipt")
    place=r.get("placeId")
    if type(place)!=int or place<=0 or (expected_place is not None and place!=expected_place): raise ValueError("Place mismatch")
    samples=r.get("observations")
    if not isinstance(samples,list) or not 2<=len(samples)<=24: raise ValueError("Invalid samples")
    observations=defaultdict(list)
    roots=Counter()
    duplicates=0
    truncations=0
    for idx,s in enumerate(samples,1):
        if not isinstance(s,dict) or s.get("index")!=idx: raise ValueError("Invalid sample index")
        entries=s.get("entries")
        if not isinstance(entries,list) or len(entries)>MAX_RECORDS: raise ValueError("Invalid sample size")
        truncations+=int(s.get("truncated",False))
        within=Counter()
        for e in entries:
            if not isinstance(e,dict): raise ValueError("Invalid entry")
            path,cl=e.get("path"),e.get("className")
            if not isinstance(path,str) or not 1<=len(path)<=2048 or not isinstance(cl,str) or not 1<=len(cl)<=128: raise ValueError("Invalid path/class")
            val=e.get("value")
            if val is not None and (not isinstance(val,str) or len(val)>120): raise ValueError("Invalid value")
            within[path]+=1
            roots[path.split("/",1)[0]]+=1
            # v53 duplicate names are explicitly ambiguous; retain multiplicity without inventing identities.
            key=path if r["schemaVersion"]=="54.0" else path+" [ambiguous duplicate]" if within[path]>1 else path
            observations[key].append((idx,cl,val))
        duplicates+=sum(max(0,n-1) for n in within.values())
    rows=[]
    for path,events in observations.items():
        values=[v for _,_,v in events if v is not None]
        unique=list(dict.fromkeys(values))
        observed_samples=len({i for i,_,_ in events})
        rows.append({"path":path,"className":Counter(c for _,c,_ in events).most_common(1)[0][0],
                     "observedSamples":observed_samples,"observations":len(events),
                     "valueChanged":len(unique)>1,"exampleValues":unique[:3],
                     "readOnly":True,"verifiedGameplayAction":False,
                     "priority":any(x in path.lower() for x in ("leaderstats","value","strength","rebirth","prompt","button","pet","training"))})
    rows.sort(key=lambda x:(not x["valueChanged"],not x["priority"],-x["observedSamples"],x["path"]))
    return {"schemaVersion":"54.analysis","sourceSchema":r["schemaVersion"],"placeId":place,
            "samples":len(samples),"recordedEntries":sum(len(s["entries"]) for s in samples),
            "distinctPathKeys":len(rows),"ambiguousDuplicateOccurrences":duplicates,
            "truncatedSamples":truncations,"rootEntries":dict(roots),
            "changingPaths":sum(x["valueChanged"] for x in rows),
            "paths":rows,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,
            "limitations":["Client-only, untrusted observations","v53 duplicate path identities cannot be recovered",
                           "v54 scanning is incremental, so absence in later samples does not imply deletion",
                           "State changes do not establish action causality"]}

def dashboard(report):
    candidates=[r for r in report["paths"] if r["valueChanged"] or r["priority"]][:100]
    lines=['-- v54 read-only evidence dashboard; no gameplay actions',
           'local player=game:GetService("Players").LocalPlayer',
           'if not player then return end',
           'local pg=player:WaitForChild("PlayerGui")',
           'local old=pg:FindFirstChild("LycolesV54Evidence")',
           'if old then old:Destroy() end',
           'local gui=Instance.new("ScreenGui") gui.Name="LycolesV54Evidence" gui.ResetOnSpawn=false gui.Parent=pg',
           'local frame=Instance.new("ScrollingFrame") frame.Size=UDim2.fromOffset(570,430) frame.Position=UDim2.fromScale(.03,.2) frame.CanvasSize=UDim2.fromOffset(0,0) frame.Parent=gui',
           'local layout=Instance.new("UIListLayout") layout.Parent=frame',
           'local title=Instance.new("TextLabel") title.Size=UDim2.fromOffset(550,50) title.Text="Lycoles v54 | Observed evidence (not verified actions)" title.Parent=frame',
           'local rows='+json.dumps([{"path":x["path"],"className":x["className"],"changed":x["valueChanged"]} for x in candidates],ensure_ascii=True).replace('true','true').replace('false','false'),
           'for _,item in ipairs(rows) do',
           ' local label=Instance.new("TextLabel") label.Size=UDim2.fromOffset(550,35) label.TextXAlignment=Enum.TextXAlignment.Left',
           ' label.Text=(item.changed and "[CHANGED] " or "[SEEN] ")..item.className.." "..item.path:sub(1,90) label.Parent=frame',
           'end',
           'frame.CanvasSize=UDim2.fromOffset(0,(#rows+1)*36)']
    # Luau tables are not JSON objects; use explicit table literals.
    lines[10]='local rows={'+','.join('{path='+json.dumps(x["path"])+',className='+json.dumps(x["className"])+',changed='+str(x["valueChanged"]).lower()+'}' for x in candidates)+'}'
    return "\n".join(lines)+"\n"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--receipt",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/release-v54"))
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"balanced-discovery-v54.luau").write_text(generate(a.place_id),encoding="utf-8")
    if a.receipt:
        if a.receipt.stat().st_size>50_000_000: raise ValueError("Receipt too large")
        report=analyze(a.receipt.read_text(encoding="utf-8-sig"),a.place_id)
        (a.output/"evidence-analysis-v54.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"
",encoding="utf-8")
        (a.output/"evidence-dashboard-v54.luau").write_text(dashboard(report),encoding="utf-8")
        print("Analysed",report["recordedEntries"],"entries;",report["distinctPathKeys"],"keys")
    print("v54 generated")
if __name__=="__main__": main()
