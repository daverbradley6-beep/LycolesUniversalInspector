#!/usr/bin/env python3
"""v75 passive interaction evidence -> proposed v73 outcome mappings.

Only observes user-initiated UI events. No game remotes or automatic activation.
"""
import argparse,json
from pathlib import Path
from collections import defaultdict,Counter
LUA=r'''-- Lycoles v75 | Passive user interaction recorder
local Players=game:GetService("Players")
local Http=game:GetService("HttpService")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("v75: wrong place") return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV75")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV75" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(510,118)
panel.Position=UDim2.new(.1,0,.1,0) panel.BackgroundColor3=Color3.fromRGB(24,32,47) panel.Parent=gui
local label=Instance.new("TextLabel") label.Size=UDim2.new(1,-16,0,45)
label.Position=UDim2.fromOffset(8,5) label.BackgroundTransparency=1
label.TextColor3=Color3.new(1,1,1) label.TextWrapped=true label.Parent=panel
local function button(name,x)
 local b=Instance.new("TextButton") b.Text=name b.Size=UDim2.fromOffset(145,34)
 b.Position=UDim2.fromOffset(x,65) b.Parent=panel return b
end
local refresh=button("Refresh controls",8)
local stop=button("Stop",162)
local close=button("Close",316)
local capture=Http:GenerateGUID(false)
local connections={} local pending={} local serial=0 local recorded=0 local listening=true
local function disconnect()
 for _,c in ipairs(connections) do c:Disconnect() end
 connections={}
end
local function pathFor(node)
 local names={} local unique={}
 while node and node~=pg do
  table.insert(names,1,node.Name)
  local ordinal=1
  if node.Parent then
   for _,other in ipairs(node.Parent:GetChildren()) do
    if other==node then break end
    if other.Name==node.Name and other.ClassName==node.ClassName then ordinal+=1 end
   end
  end
  table.insert(unique,1,{name=node.Name,className=node.ClassName,ordinal=ordinal})
  node=node.Parent
 end
 if node~=pg then return nil,nil end
 return names,unique
end
local function snapshot()
 local out={} local stats=player:FindFirstChild("leaderstats")
 if stats then
  for _,v in ipairs(stats:GetChildren()) do
   if v:IsA("ValueBase") then
    local value=v.Value
    if type(value)=="number" or type(value)=="string" or type(value)=="boolean" then
     out[v.Name]=value
    end
   end
  end
 end
 return out
end
local function status()
 label.Text="Lycoles v75 | Passive recorder | "..recorded.." observations\nCapture: "..capture
end
local function record(node,before)
 if not listening or not gui.Parent then return end
 local path,unique=pathFor(node)
 if not path then return end
 serial+=1
 local index=serial
 local event={schemaVersion="75.event",placeId=game.PlaceId,captureId=capture,
  index=index,path=path,uniquePath=unique,className=node.ClassName,
  before=before or snapshot()}
 task.delay(__DELAY__,function()
  if not gui.Parent then return end
  event.after=snapshot()
  recorded+=1 status()
  print("LYCOLES_V75_EVENT "..Http:JSONEncode(event))
 end)
end
local function attach()
 disconnect()
 local count=0
 for _,node in ipairs(pg:GetDescendants()) do
  if (node:IsA("TextButton") or node:IsA("ImageButton")) and not node:IsDescendantOf(gui) then
   count+=1
   local before=nil
   table.insert(connections,node.InputBegan:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
     before=snapshot()
    end
   end))
   table.insert(connections,node.Activated:Connect(function()
    local saved=before
    before=nil
    record(node,saved)
   end))
  end
 end
 print("LYCOLES_V75_SESSION "..Http:JSONEncode({schemaVersion="75.session",placeId=game.PlaceId,captureId=capture,controls=count,delay=__DELAY__}))
 status()
end
refresh.MouseButton1Click:Connect(attach)
stop.MouseButton1Click:Connect(function() listening=false disconnect() status() end)
close.MouseButton1Click:Connect(function() listening=false disconnect() gui:Destroy() end)
attach()
'''
def script(place_id,delay=1.5):
 if type(place_id) is not int or place_id<=0:raise ValueError("invalid place")
 if type(delay) not in (float,int) or not .5<=delay<=10:raise ValueError("invalid delay")
 return LUA.replace("__PLACE__",str(place_id)).replace("__DELAY__",str(delay))
def events(text,place_id):
 result=[];seen=set()
 for line in text.splitlines():
  if "LYCOLES_V75_EVENT " not in line:continue
  try:e=json.loads(line.split("LYCOLES_V75_EVENT ",1)[1])
  except json.JSONDecodeError:continue
  if not isinstance(e,dict) or e.get("schemaVersion")!="75.event" or e.get("placeId")!=place_id:continue
  if not isinstance(e.get("captureId"),str) or type(e.get("index")) is not int or e["index"]<1:continue
  key=(e["captureId"],e["index"])
  if key in seen:continue
  seen.add(key)
  if not isinstance(e.get("before"),dict) or not isinstance(e.get("after"),dict):continue
  up=e.get("uniquePath")
  if not isinstance(up,list) or not up:continue
  if not all(isinstance(s,dict) and isinstance(s.get("name"),str) and isinstance(s.get("className"),str) and type(s.get("ordinal")) is int and s["ordinal"]>=1 for s in up):continue
  result.append(e)
 return result
def signature(path):
 return json.dumps(path,sort_keys=True,ensure_ascii=False,separators=(",",":"))
def propose(catalog,observations,place_id,min_repeats=2):
 if catalog.get("schemaVersion")!="72.candidates" or catalog.get("placeId")!=place_id:raise ValueError("candidate mismatch")
 if type(min_repeats) is not int or not 2<=min_repeats<=20:raise ValueError("invalid repeat count")
 lookup=defaultdict(list)
 for c in catalog.get("candidates",[]):
  up=c.get("action",{}).get("uniquePath")
  if up:lookup[signature(up)].append(c)
 grouped=defaultdict(list)
 for e in observations:grouped[signature(e["uniquePath"])].append(e)
 proposed={};diagnostics=[]
 for sig,group in grouped.items():
  matches=lookup.get(sig,[])
  if len(matches)!=1:
   diagnostics.append({"events":len(group),"reason":"no unique candidate match"})
   continue
  c=matches[0]
  if len(group)<min_repeats:
   diagnostics.append({"id":c["id"],"events":len(group),"reason":"insufficient repeats"})
   continue
  stats=set.intersection(*(set(e["before"])&set(e["after"]) for e in group))
  options=[]
  for stat in sorted(stats):
   values=[(e["before"][stat],e["after"][stat]) for e in group]
   if all(type(a) in (int,float) and type(b) in (int,float) and b>a for a,b in values):op="increased"
   elif all(type(a) in (int,float) and type(b) in (int,float) and b<a for a,b in values):op="decreased"
   elif all(a!=b for a,b in values) and not all(type(a) in (int,float) and type(b) in (int,float) for a,b in values):op="changed"
   else:continue
   options.append((stat,op))
  if len(options)!=1:
   diagnostics.append({"id":c["id"],"events":len(group),"reason":"ambiguous or no consistent stat outcome","possibleStats":[x[0] for x in options]})
   continue
  stat,op=options[0]
  proposed[c["id"]]={"type":"leaderstat","stat":stat,"operator":op,"target":None,"timeoutSeconds":5}
  diagnostics.append({"id":c["id"],"events":len(group),"reason":"proposed; manual review required","stat":stat,"operator":op})
 return {"schemaVersion":"75.proposals","placeId":place_id,"observations":len(observations),
         "proposals":proposed,"diagnostics":diagnostics,"verified":False}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",required=True,type=int)
 p.add_argument("--output",type=Path,default=Path("build/release-v75"))
 p.add_argument("--event-log",type=Path,action="append",default=[])
 p.add_argument("--candidates",type=Path)
 p.add_argument("--min-repeats",type=int,default=2)
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"interaction-recorder-v75.luau").write_text(script(a.place_id),encoding="utf-8")
 if a.event_log:
  if not a.candidates or not a.candidates.is_file():p.error("candidates file required")
  if a.candidates.stat().st_size>30_000_000:p.error("oversized candidates")
  logs=[]
  for f in a.event_log:
   if not f.is_file() or f.stat().st_size>30_000_000:p.error("missing or oversized event log")
   logs.append(f.read_text(encoding="utf-8-sig",errors="replace"))
  data=propose(json.loads(a.candidates.read_text(encoding="utf-8-sig")),events("\n".join(logs),a.place_id),a.place_id,a.min_repeats)
  (a.output/"proposals-v75.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  (a.output/"review-outcomes-v75.json").write_text(json.dumps({"schemaVersion":"73.outcomes","placeId":a.place_id,"outcomes":data["proposals"]},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print(json.dumps({"observations":data["observations"],"proposals":len(data["proposals"]),"verified":False}))
if __name__=="__main__":main()
