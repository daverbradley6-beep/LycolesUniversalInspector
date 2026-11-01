#!/usr/bin/env python3
"""v76 passive keyboard and GUI recorder with evidence summaries."""
import argparse,json
from pathlib import Path
from collections import defaultdict
LUA=r'''local Players=game:GetService("Players")
local UIS=game:GetService("UserInputService")
local Http=game:GetService("HttpService")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("v76: place mismatch") return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV76") if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV76" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(550,125) panel.Position=UDim2.new(.1,0,.12,0) panel.BackgroundColor3=Color3.fromRGB(25,34,51) panel.Parent=gui
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-16,0,50) status.Position=UDim2.fromOffset(8,5) status.BackgroundTransparency=1 status.TextColor3=Color3.new(1,1,1) status.TextWrapped=true status.Parent=panel
local function button(label,x)
 local b=Instance.new("TextButton") b.Text=label b.Size=UDim2.fromOffset(165,34) b.Position=UDim2.fromOffset(x,74) b.Parent=panel return b
end
local refresh=button("Refresh GUI",8)
local stop=button("Stop",184)
local close=button("Close",360)
local capture=Http:GenerateGUID(false)
local connections={} local listening=true local index=0 local lastKeyboard=nil
local function disconnect() for _,c in ipairs(connections) do c:Disconnect() end connections={} end
local function snapshot()
 local out={} local stats=player:FindFirstChild("leaderstats")
 if stats then
  for _,v in ipairs(stats:GetChildren()) do
   if v:IsA("ValueBase") then
    local val=v.Value
    if type(val)=="number" or type(val)=="string" or type(val)=="boolean" then out[v.Name]=val end
   end
  end
 end
 return out
end
local function pathFor(node)
 local path={} local unique={}
 while node and node~=pg do
  table.insert(path,1,node.Name)
  local ordinal=1
  if node.Parent then
   for _,sibling in ipairs(node.Parent:GetChildren()) do
    if sibling==node then break end
    if sibling.Name==node.Name and sibling.ClassName==node.ClassName then ordinal+=1 end
   end
  end
  table.insert(unique,1,{name=node.Name,className=node.ClassName,ordinal=ordinal})
  node=node.Parent
 end
 if node~=pg then return nil,nil end
 return path,unique
end
local function emit(kind,details,before,started)
 if not listening or not gui.Parent then return end
 index+=1
 local event={schemaVersion="76.event",placeId=game.PlaceId,captureId=capture,index=index,kind=kind,details=details,before=before,startedAt=started}
 task.delay(__DELAY__,function()
  if not gui.Parent or not listening then return end
  event.after=snapshot()
  print("LYCOLES_V76_EVENT "..Http:JSONEncode(event))
 end)
end
local function update() status.Text="Lycoles v76 | keyboard + GUI | events: "..index.."\nCapture: "..capture end
local function bindGui()
 disconnect()
 local count=0
 for _,node in ipairs(pg:GetDescendants()) do
  if (node:IsA("TextButton") or node:IsA("ImageButton")) and not node:IsDescendantOf(gui) then
   count+=1
   local pre=nil
   table.insert(connections,node.InputBegan:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then pre=snapshot() end
   end))
   table.insert(connections,node.Activated:Connect(function()
    if not listening then return end
    local path,unique=pathFor(node) if not path then return end
    local now=os.clock() local linked=nil
    if lastKeyboard and now-lastKeyboard.time<__WINDOW__ then linked=lastKeyboard.index end
    emit("gui",{path=path,uniquePath=unique,className=node.ClassName,linkedKeyboardIndex=linked},pre or snapshot(),now)
    pre=nil update()
   end))
  end
 end
 print("LYCOLES_V76_SESSION "..Http:JSONEncode({schemaVersion="76.session",placeId=game.PlaceId,captureId=capture,controls=count,delay=__DELAY__}))
 update()
end
local keyboardConnection=UIS.InputBegan:Connect(function(input,processed)
 if not listening or UIS:GetFocusedTextBox() then return end
 if input.UserInputType~=Enum.UserInputType.Keyboard or input.KeyCode==Enum.KeyCode.Unknown then return end
 local now=os.clock()
 lastKeyboard={time=now,index=index+1}
 emit("keyboard",{key=input.KeyCode.Name,gameProcessed=processed},snapshot(),now)
 update()
end)
refresh.MouseButton1Click:Connect(bindGui)
stop.MouseButton1Click:Connect(function() listening=false disconnect() keyboardConnection:Disconnect() update() end)
close.MouseButton1Click:Connect(function() listening=false disconnect() keyboardConnection:Disconnect() gui:Destroy() end)
bindGui()
'''
def script(place_id,delay=1.5,link_window=.25):
 if type(place_id) is not int or place_id<=0:raise ValueError("invalid place ID")
 if type(delay) not in (int,float) or not .5<=delay<=10:raise ValueError("invalid observation delay")
 if type(link_window) not in (int,float) or not .05<=link_window<=1:raise ValueError("invalid link window")
 return LUA.replace("__PLACE__",str(place_id)).replace("__DELAY__",str(delay)).replace("__WINDOW__",str(link_window))
def parse(texts,place_id):
 result={}
 for text in texts:
  for line in text.splitlines():
   if "LYCOLES_V76_EVENT " not in line:continue
   try:e=json.loads(line.split("LYCOLES_V76_EVENT ",1)[1])
   except json.JSONDecodeError:continue
   if not isinstance(e,dict) or e.get("schemaVersion")!="76.event" or e.get("placeId")!=place_id:continue
   if e.get("kind") not in ("keyboard","gui") or not isinstance(e.get("captureId"),str):continue
   if type(e.get("index")) is not int or e["index"]<=0:continue
   if not isinstance(e.get("details"),dict) or not isinstance(e.get("before"),dict) or not isinstance(e.get("after"),dict):continue
   if e["kind"]=="keyboard":
    key=e["details"].get("key")
    if not isinstance(key,str) or not key.isidentifier() or len(key)>40:continue
    if type(e["details"].get("gameProcessed")) is not bool:continue
   else:
    unique=e["details"].get("uniquePath")
    if not isinstance(unique,list) or not unique or len(unique)>30:continue
    if any(not isinstance(s,dict) or not isinstance(s.get("name"),str) or not isinstance(s.get("className"),str) or type(s.get("ordinal")) is not int or s["ordinal"]<1 for s in unique):continue
   identity=(e["captureId"],e["index"])
   if identity in result and result[identity]!=e:raise ValueError("conflicting event index")
   result[identity]=e
 return sorted(result.values(),key=lambda e:(e["captureId"],e["index"]))
def summarize(events,min_repeats=2):
 if type(min_repeats) is not int or not 2<=min_repeats<=20:raise ValueError("invalid minimum repeats")
 groups=defaultdict(list)
 for e in events:
  d=e["details"]
  key=("keyboard",d["key"],d["gameProcessed"]) if e["kind"]=="keyboard" else ("gui",json.dumps(d["uniquePath"],sort_keys=True,ensure_ascii=False))
  groups[key].append(e)
 results=[]
 for key,group in sorted(groups.items()):
  stats=set.intersection(*(set(e["before"])&set(e["after"]) for e in group))
  outcomes=[]
  for stat in sorted(stats):
   pairs=[(e["before"][stat],e["after"][stat]) for e in group]
   numeric=all(type(a) in (int,float) and type(b) in (int,float) for a,b in pairs)
   if numeric and all(b>a for a,b in pairs):direction="increased"
   elif numeric and all(b<a for a,b in pairs):direction="decreased"
   elif not numeric and all(type(a) is type(b) and a!=b for a,b in pairs):direction="changed"
   else:continue
   outcomes.append({"stat":stat,"operator":direction})
  n=len(group)
  results.append({"input":{"kind":key[0],"identity":key[1:]},"observations":n,
   "candidateOutcomes":outcomes if n>=min_repeats else [],
   "status":"hypothesis_requires_validation" if n>=min_repeats and len(outcomes)==1 else "insufficient_or_ambiguous_evidence",
   "captures":sorted(set(e["captureId"] for e in group))})
 return {"schemaVersion":"76.summary","observations":len(events),"groups":results,"verified":False,"automatedActions":0}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",required=True,type=int)
 p.add_argument("--output",type=Path,default=Path("build/release-v76"))
 p.add_argument("--event-log",type=Path,action="append",default=[])
 p.add_argument("--min-repeats",type=int,default=2)
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"input-recorder-v76.luau").write_text(script(a.place_id),encoding="utf-8")
 if a.event_log:
  texts=[]
  for f in a.event_log:
   if not f.is_file() or f.stat().st_size>30_000_000:p.error("missing or oversized event log "+str(f))
   texts.append(f.read_text(encoding="utf-8-sig",errors="replace"))
  data=summarize(parse(texts,a.place_id),a.min_repeats)
  data["placeId"]=a.place_id
  (a.output/"input-summary-v76.json").write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print(json.dumps({"observations":data["observations"],"groups":len(data["groups"]),"verified":False}))
if __name__=="__main__":main()
