#!/usr/bin/env python3
"""v87: passive, event-driven Roblox GUI/input recorder with real player actions.

Produces evidence, never simulates clicks, keypresses or server requests.
"""
import argparse
import json
from pathlib import Path

LUA = r'''local Players=game:GetService("Players")
local UIS=game:GetService("UserInputService")
local Http=game:GetService("HttpService")
if game.PlaceId~=__PLACE__ then warn("Lycoles v87: wrong place") return end
local player=Players.LocalPlayer
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV87") if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV87"
gui.ResetOnSpawn=false
gui.Parent=pg
local panel=Instance.new("Frame")
panel.Name="Panel"
panel.Size=UDim2.fromOffset(420,110)
panel.Position=UDim2.fromScale(.08,.12)
panel.BackgroundColor3=Color3.fromRGB(24,31,45)
panel.Parent=gui
local label=Instance.new("TextLabel")
label.Size=UDim2.new(1,-12,0,46)
label.Position=UDim2.fromOffset(6,4)
label.TextWrapped=true
label.TextColor3=Color3.new(1,1,1)
label.BackgroundTransparency=1
label.Parent=panel
local function makeButton(text,x)
 local b=Instance.new("TextButton")
 b.Size=UDim2.fromOffset(125,36)
 b.Position=UDim2.fromOffset(x,65)
 b.Text=text
 b.Parent=panel
 return b
end
local refresh=makeButton("Refresh",6)
local stop=makeButton("Stop",147)
local close=makeButton("Close",288)
local capture=Http:GenerateGUID(false)
local seq=0
local alive=true
local connections={}
local uiConnections={}
local function track(signal,callback,bag)
 local connection=signal:Connect(callback)
 table.insert(bag or connections,connection)
 return connection
end
local function disconnect(bag)
 for _,connection in ipairs(bag) do connection:Disconnect() end
 table.clear(bag)
end
local function snapshot()
 local result={}
 local leaderstats=player:FindFirstChild("leaderstats")
 if leaderstats then
  for _,value in ipairs(leaderstats:GetChildren()) do
   if value:IsA("ValueBase") then
    local x=value.Value
    if type(x)=="number" or type(x)=="boolean" or type(x)=="string" then result[value.Name]=x end
   end
  end
 end
 return result
end
local function pathFor(node)
 local result={}
 while node and node~=pg do
  local ordinal=1
  if node.Parent then
   for _,other in ipairs(node.Parent:GetChildren()) do
    if other==node then break end
    if other.Name==node.Name and other.ClassName==node.ClassName then ordinal+=1 end
   end
  end
  table.insert(result,1,{name=node.Name,className=node.ClassName,ordinal=ordinal})
  node=node.Parent
 end
 return node==pg and result or nil
end
local function available(node)
 local reasons={}
 local current=node
 if not node.Active then table.insert(reasons,"inactive") end
 while current and current~=pg do
  if current:IsA("GuiObject") and not current.Visible then table.insert(reasons,"hidden:"..current.Name) end
  if current:IsA("ScreenGui") and not current.Enabled then table.insert(reasons,"disabled:"..current.Name) end
  current=current.Parent
 end
 return #reasons==0,reasons
end
local function update()
 label.Text="Lycoles v87 | Passive capture | events: "..seq.."\nUse the real game's E key or Hatch button"
end
local function emit(kind,details,before)
 if not alive then return end
 seq+=1
 local index=seq
 local started=os.clock()
 task.delay(__DELAY__,function()
  if not alive then return end
  local after=snapshot()
  local changes={}
  for stat,value in pairs(before) do
   if after[stat]~=nil and after[stat]~=value then
    table.insert(changes,{stat=stat,before=value,after=after[stat]})
   end
  end
  table.sort(changes,function(a,b) return a.stat<b.stat end)
  print("LYCOLES_V87_EVENT "..Http:JSONEncode({
   schemaVersion="87.event",placeId=game.PlaceId,captureId=capture,index=index,
   kind=kind,details=details,observedChanges=changes,
   startedAt=started,observationDelay=__DELAY__,verified=false
  }))
 end)
 update()
end
local bound={}
local function bind(node)
 if not (node:IsA("TextButton") or node:IsA("ImageButton")) then return end
 if node:IsDescendantOf(gui) or bound[node] then return end
 bound[node]=true
 local before=nil
 track(node.InputBegan,function(input)
  if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
   before=snapshot()
  end
 end,uiConnections)
 track(node.Activated,function()
  if not alive then return end
  local path=pathFor(node)
  if not path then return end
  local isAvailable,reasons=available(node)
  emit("gui",{path=path,available=isAvailable,reasons=reasons},before or snapshot())
  before=nil
 end,uiConnections)
end
local function refreshAll()
 disconnect(uiConnections)
 table.clear(bound)
 local count=0
 for _,node in ipairs(pg:GetDescendants()) do
  if node:IsA("GuiButton") and not node:IsDescendantOf(gui) then
   bind(node)
   count+=1
  end
 end
 print("LYCOLES_V87_SESSION "..Http:JSONEncode({
  schemaVersion="87.session",placeId=game.PlaceId,captureId=capture,buttons=count
 }))
 update()
end
track(pg.DescendantAdded,function(node)
 if alive then bind(node) end
end)
track(UIS.InputBegan,function(input,processed)
 if not alive or UIS:GetFocusedTextBox() then return end
 if input.UserInputType~=Enum.UserInputType.Keyboard or input.KeyCode==Enum.KeyCode.Unknown then return end
 emit("keyboard",{key=input.KeyCode.Name,gameProcessed=processed},snapshot())
end)
track(refresh.Activated,refreshAll)
track(stop.Activated,function()
 alive=false
 disconnect(uiConnections)
 disconnect(connections)
 update()
end)
track(close.Activated,function()
 alive=false
 disconnect(uiConnections)
 disconnect(connections)
 gui:Destroy()
end)
refreshAll()
'''
def generate(place_id, delay=1.5):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("positive place ID required")
    if type(delay) not in (float,int) or not 0.5 <= delay <= 10:
        raise ValueError("delay must be 0.5 to 10 seconds")
    return LUA.replace("__PLACE__",str(place_id)).replace("__DELAY__",str(delay))

def parse(paths,place_id):
    found={}
    warnings=[]
    for source in paths:
        path=Path(source)
        if not path.is_file() or path.stat().st_size>30_000_000:
            raise ValueError("missing or oversized event log")
        for lineno,line in enumerate(path.read_text(encoding="utf-8-sig",errors="replace").splitlines(),1):
            if "LYCOLES_V87_EVENT " not in line:
                continue
            try:
                item=json.loads(line.split("LYCOLES_V87_EVENT ",1)[1])
            except json.JSONDecodeError:
                warnings.append(f"{path}:{lineno}: malformed JSON")
                continue
            if not isinstance(item,dict) or item.get("schemaVersion")!="87.event" or item.get("placeId")!=place_id:
                warnings.append(f"{path}:{lineno}: incompatible event")
                continue
            if item.get("kind") not in ("gui","keyboard") or not isinstance(item.get("details"),dict):
                warnings.append(f"{path}:{lineno}: invalid event")
                continue
            capture=item.get("captureId");index=item.get("index")
            if not isinstance(capture,str) or not capture or type(index) is not int or index<1:
                warnings.append(f"{path}:{lineno}: invalid identity")
                continue
            changes=item.get("observedChanges")
            if not isinstance(changes,list) or len(changes)>200:
                warnings.append(f"{path}:{lineno}: invalid changes")
                continue
            identity=(capture,index)
            if identity in found and found[identity]!=item:
                raise ValueError(f"conflicting event identity {identity}")
            found[identity]=item
    return sorted(found.values(),key=lambda e:(e["captureId"],e["index"])),warnings

def summarize(events):
    groups={}
    for item in events:
        d=item["details"]
        if item["kind"]=="keyboard":
            key="keyboard:"+str(d.get("key"))+":processed="+str(d.get("gameProcessed"))
        else:
            key="gui:"+json.dumps(d.get("path"),ensure_ascii=False,sort_keys=True)
        group=groups.setdefault(key,{"kind":item["kind"],"input":key,"observations":0,"captures":set(),"signals":{}})
        group["observations"]+=1
        group["captures"].add(item["captureId"])
        seen=set()
        for change in item["observedChanges"]:
            if not isinstance(change,dict) or not isinstance(change.get("stat"),str):
                continue
            a=change.get("before");b=change.get("after")
            if type(a)!=type(b) or a==b:
                continue
            if type(a) in (int,float):
                op="increase" if b>a else "decrease"
            elif type(a) is bool:
                op="toggle"
            elif type(a) is str:
                op="change"
            else:
                continue
            seen.add((change["stat"],op))
        for signal in seen:
            group["signals"][signal]=group["signals"].get(signal,0)+1
    rows=[]
    for key,g in sorted(groups.items()):
        rows.append({"input":key,"kind":g["kind"],"observations":g["observations"],
                     "independentCaptures":len(g["captures"]),
                     "signals":[{"stat":stat,"operator":op,"observations":count}
                                for (stat,op),count in sorted(g["signals"].items())],
                     "verified":False,"executionEnabled":False})
    return {"schemaVersion":"87.review","totalEvents":len(events),"groups":rows,
            "verified":False,"executionEnabled":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--event-log",type=Path,action="append",default=[])
    p.add_argument("--output",type=Path,default=Path("build/release-v87"))
    p.add_argument("--delay",type=float,default=1.5)
    a=p.parse_args()
    script=generate(a.place_id,a.delay)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"passive-recorder-v87.luau").write_bytes(script.encode("utf-8"))
    report={"generated":True,"eventLogs":len(a.event_log),"verified":False}
    if a.event_log:
        events,warnings=parse(a.event_log,a.place_id)
        review=summarize(events)
        (a.output/"evidence-review-v87.json").write_text(json.dumps(review,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        (a.output/"warnings-v87.json").write_text(json.dumps(warnings,indent=2)+"\n",encoding="utf-8")
        report.update({"events":len(events),"groups":len(review["groups"]),"warnings":len(warnings)})
    print(json.dumps(report))
if __name__=="__main__":
    main()
