#!/usr/bin/env python3
"""v78 multi-state passive recorder and evidence review."""
import argparse,json,math
from pathlib import Path
from collections import defaultdict
LUA=r'''local P=game:GetService("Players").LocalPlayer
local UIS=game:GetService("UserInputService")
local H=game:GetService("HttpService")
if game.PlaceId~=__PLACE__ then return end
local pg=P:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV78") if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV78" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(420,100) panel.Position=UDim2.fromScale(.1,.1) panel.Parent=gui
local function btn(name,x)
 local b=Instance.new("TextButton") b.Size=UDim2.fromOffset(125,40) b.Position=UDim2.fromOffset(x,25) b.Text=name b.Parent=panel return b
end
local refresh,stop,close=btn("Refresh",5),btn("Stop",145),btn("Close",285)
local capture=H:GenerateGUID(false) local seq=0 local alive=true local links={}
local function path(node)
 local out={}
 while node and node~=pg do
  local ordinal=1
  if node.Parent then for _,other in ipairs(node.Parent:GetChildren()) do
   if other==node then break end
   if other.Name==node.Name and other.ClassName==node.ClassName then ordinal+=1 end
  end end
  table.insert(out,1,{name=node.Name,className=node.ClassName,ordinal=ordinal})
  node=node.Parent
 end
 return node==pg and out or nil
end
local function state()
 local s={leaderstats={},tools={backpackCount=0,equippedCount=0,equippedName=""},character={},gui={}}
 local stats=P:FindFirstChild("leaderstats")
 if stats then for _,v in ipairs(stats:GetChildren()) do if v:IsA("ValueBase") then
  local x=v.Value if type(x)=="number" or type(x)=="boolean" or type(x)=="string" then s.leaderstats[v.Name]=x end
 end end end
 local bag=P:FindFirstChildOfClass("Backpack")
 if bag then for _,t in ipairs(bag:GetChildren()) do if t:IsA("Tool") then s.tools.backpackCount+=1 end end end
 local c=P.Character
 if c then
  for _,t in ipairs(c:GetChildren()) do if t:IsA("Tool") then s.tools.equippedCount+=1 s.tools.equippedName=t.Name end end
  local root=c:FindFirstChild("HumanoidRootPart")
  if root then local p=root.Position s.character.position={x=math.floor(p.X*10+.5)/10,y=math.floor(p.Y*10+.5)/10,z=math.floor(p.Z*10+.5)/10} end
 end
 local n=0
 for _,v in ipairs(pg:GetDescendants()) do
  if n>=1500 then break end
  if not v:IsDescendantOf(gui) and (v:IsA("ScreenGui") or v:IsA("Frame")) then
   local segments=path(v)
   if segments then
    local names={} for _,segment in ipairs(segments) do table.insert(names,segment.name.."#"..segment.ordinal) end
    s.gui[table.concat(names,"/")]=(v:IsA("ScreenGui") and v.Enabled==true) or (v:IsA("Frame") and v.Visible==true)
    n+=1
   end
  end
 end
 return s
end
local function emit(kind,details,before)
 if not alive then return end
 seq+=1
 local event={schemaVersion="78.event",placeId=game.PlaceId,captureId=capture,index=seq,kind=kind,details=details,before=before}
 task.delay(1.5,function()
  if not alive then return end
  event.after=state()
  print("LYCOLES_V78_EVENT "..H:JSONEncode(event))
 end)
end
local function detach() for _,link in ipairs(links) do link:Disconnect() end links={} end
local function bind()
 detach() local count=0
 for _,v in ipairs(pg:GetDescendants()) do
  if not v:IsDescendantOf(gui) and (v:IsA("TextButton") or v:IsA("ImageButton")) then
   count+=1 local before=nil
   table.insert(links,v.InputBegan:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then before=state() end
   end))
   table.insert(links,v.Activated:Connect(function()
    local p=path(v) if p then emit("gui",{uniquePath=p,className=v.ClassName},before or state()) end
    before=nil
   end))
  end
 end
 print("LYCOLES_V78_SESSION "..H:JSONEncode({schemaVersion="78.session",placeId=game.PlaceId,captureId=capture,controls=count}))
end
local keyboard=UIS.InputBegan:Connect(function(input,processed)
 if alive and not UIS:GetFocusedTextBox() and input.UserInputType==Enum.UserInputType.Keyboard and input.KeyCode~=Enum.KeyCode.Unknown then
  emit("keyboard",{key=input.KeyCode.Name,gameProcessed=processed},state())
 end
end)
refresh.MouseButton1Click:Connect(bind)
stop.MouseButton1Click:Connect(function() alive=false detach() keyboard:Disconnect() end)
close.MouseButton1Click:Connect(function() alive=false detach() keyboard:Disconnect() gui:Destroy() end)
bind()
'''
def generate(place_id):
 if type(place_id) is not int or place_id<=0:raise ValueError("invalid place")
 return LUA.replace("__PLACE__",str(place_id))
def flatten(obj,prefix=""):
 out={}
 if isinstance(obj,dict):
  for k,v in obj.items():out.update(flatten(v,(prefix+"." if prefix else "")+str(k)))
 elif isinstance(obj,(str,bool,int,float)) and (type(obj) is not float or math.isfinite(obj)):out[prefix]=obj
 return out
def changes(a,b):
 a,b=flatten(a),flatten(b);out={}
 for k in a.keys()&b.keys():
  x,y=a[k],b[k]
  if type(x)!=type(y) or x==y:continue
  out[k]=("increase" if y>x else "decrease") if type(x) in (int,float) else ("toggle" if type(x) is bool else "change")
 return out
def parse_logs(paths,place_id):
 found={}
 for p in paths:
  p=Path(p)
  if not p.is_file() or p.stat().st_size>30000000:raise ValueError("invalid log")
  for line in p.read_text(encoding="utf-8-sig",errors="replace").splitlines():
   if "LYCOLES_V78_EVENT " not in line:continue
   try:e=json.loads(line.split("LYCOLES_V78_EVENT ",1)[1])
   except json.JSONDecodeError:continue
   if not isinstance(e,dict) or e.get("schemaVersion")!="78.event" or e.get("placeId")!=place_id:continue
   if e.get("kind") not in ("keyboard","gui") or type(e.get("index")) is not int or e["index"]<1 or not isinstance(e.get("captureId"),str):continue
   if not all(isinstance(e.get(k),dict) for k in ("details","before","after")):continue
   key=(e["captureId"],e["index"])
   if key in found and found[key]!=e:raise ValueError("conflicting event")
   found[key]=e
 return sorted(found.values(),key=lambda e:(e["captureId"],e["index"]))
def analyze(events,minimum=3):
 if type(minimum) is not int or not 2<=minimum<=100:raise ValueError("invalid minimum")
 groups=defaultdict(list)
 for e in events:
  d=e["details"]
  key="keyboard:"+str(d.get("key"))+":processed="+str(d.get("gameProcessed")) if e["kind"]=="keyboard" else "gui:"+json.dumps(d.get("uniquePath"),ensure_ascii=False,sort_keys=True)
  groups[key].append(e)
 result=[]
 for key,items in sorted(groups.items()):
  diffs=[changes(e["before"],e["after"]) for e in items]
  common=set.intersection(*(set(d) for d in diffs))
  signals=[{"signal":s,"change":next(iter({d[s] for d in diffs}))} for s in sorted(common) if len({d[s] for d in diffs})==1]
  eligible=len(items)>=minimum
  result.append({"input":key,"observations":len(items),"consistentSignals":signals if eligible else [],"status":"review_candidate" if eligible and len(signals)==1 else "insufficient_or_ambiguous"})
 return {"schemaVersion":"78.review","events":len(events),"groups":result,"verified":False,"executionEnabled":False}
def main():
 p=argparse.ArgumentParser();p.add_argument("--place-id",type=int,required=True);p.add_argument("--event-log",type=Path,action="append",default=[]);p.add_argument("--output",type=Path,default=Path("build/release-v78"))
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"state-recorder-v78.luau").write_text(generate(a.place_id),encoding="utf-8")
 if a.event_log:
  report=analyze(parse_logs(a.event_log,a.place_id))
  (a.output/"state-review-v78.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print(json.dumps({"events":report["events"],"groups":len(report["groups"]),"verified":False}))
if __name__=="__main__":main()
