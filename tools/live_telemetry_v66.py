#!/usr/bin/env python3
"""v66 local gameplay telemetry: change-aware, bounded export for universal evidence pipeline."""
import argparse
import json
from pathlib import Path

LUA = r'''-- Lycoles v66: passive local observation. No gameplay actions or remote calls.
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
if game.PlaceId~=__PLACE__ then warn("Lycoles v66: wrong place") return end
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local previous=pg:FindFirstChild("LycolesV66")
if previous then previous:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV66" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(660,460)
panel.Position=UDim2.fromScale(.05,.12)
panel.BackgroundColor3=Color3.fromRGB(22,30,44) panel.Parent=gui
local title=Instance.new("TextLabel") title.Size=UDim2.new(1,-55,0,38)
title.BackgroundTransparency=1 title.TextColor3=Color3.new(1,1,1)
title.Text="Lycoles v66 | Passive telemetry and export" title.Parent=panel
local close=Instance.new("TextButton") close.Size=UDim2.fromOffset(44,34)
close.Position=UDim2.new(1,-46,0,3) close.Text="X" close.Parent=panel
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local filter=Instance.new("TextBox") filter.Size=UDim2.new(1,-16,0,34)
filter.Position=UDim2.fromOffset(8,42) filter.PlaceholderText="Filter changes"
filter.ClearTextOnFocus=false filter.Text="" filter.Parent=panel
local export=Instance.new("TextButton") export.Size=UDim2.fromOffset(150,34)
export.Position=UDim2.fromOffset(8,82) export.Text="Export telemetry" export.Parent=panel
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-170,0,34)
status.Position=UDim2.fromOffset(164,82) status.BackgroundTransparency=1
status.TextColor3=Color3.new(1,1,1) status.TextXAlignment=Enum.TextXAlignment.Left
status.Text="No observations yet" status.Parent=panel
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-16,1,-126)
scroll.Position=UDim2.fromOffset(8,122) scroll.CanvasSize=UDim2.fromOffset(0,0)
scroll.Parent=panel
local layout=Instance.new("UIListLayout") layout.Parent=scroll
local MAX_EVENTS=__MAXEVENTS__
local MAX_SCAN=__MAXSCAN__
local events={} local last={} local tick=0
local function safePath(obj)
 local ok,result=pcall(function() return obj:GetFullName() end)
 return ok and tostring(result):sub(1,180) or tostring(obj.Name):sub(1,100)
end
local function push(kind,obj,value)
 local key=kind.."|"..safePath(obj)
 local str=tostring(value):sub(1,120)
 if last[key]~=nil and last[key]~=str then
  events[#events+1]={tick=tick,kind=kind,path=safePath(obj),before=last[key],after=str}
  if #events>MAX_EVENTS then table.remove(events,1) end
 end
 last[key]=str
end
local function sample()
 tick+=1
 local stats=player:FindFirstChild("leaderstats")
 if stats then for _,v in ipairs(stats:GetChildren()) do
  if v:IsA("ValueBase") then
   local ok,value=pcall(function() return v.Value end)
   if ok then push("stat",v,value) end
  end
 end end
 local bag=player:FindFirstChildOfClass("Backpack")
 if bag then for _,v in ipairs(bag:GetChildren()) do
  if v:IsA("Tool") then push("tool",v,"backpack") end
 end end
 local char=player.Character
 if char then for _,v in ipairs(char:GetChildren()) do
  if v:IsA("Tool") then push("tool",v,"equipped") end
 end end
 local queue={workspace,pg} local head=1 local visited=0
 while head<=#queue and visited<MAX_SCAN do
  local obj=queue[head] head+=1 visited+=1
  if obj:IsA("ProximityPrompt") then
   local ok,desc=pcall(function()
    return obj.ActionText.." | "..obj.ObjectText.." | enabled="..tostring(obj.Enabled)
   end)
   if ok then push("prompt",obj,desc) end
  elseif obj:IsA("TextButton") then
   local ok,desc=pcall(function() return obj.Text.." | visible="..tostring(obj.Visible) end)
   if ok then push("gui",obj,desc) end
  end
  local ok,children=pcall(function() return obj:GetChildren() end)
  if ok then for _,child in ipairs(children) do
   if #queue-head<MAX_SCAN then queue[#queue+1]=child end
  end end
 end
 return visited
end
local function render()
 for _,v in ipairs(scroll:GetChildren()) do if v:IsA("TextLabel") then v:Destroy() end end
 local count=0 local q=string.lower(filter.Text)
 for i=#events,1,-1 do
  local e=events[i]
  local line="["..e.tick.."] "..e.kind.." | "..e.path.." | "..e.before.." -> "..e.after
  if q=="" or string.find(string.lower(line),q,1,true) then
   count+=1
   local row=Instance.new("TextLabel") row.Size=UDim2.new(1,-10,0,40)
   row.TextColor3=Color3.new(1,1,1) row.BackgroundTransparency=.4
   row.TextXAlignment=Enum.TextXAlignment.Left row.TextWrapped=true row.TextSize=12
   row.Text=line row.Parent=scroll
  end
 end
 scroll.CanvasSize=UDim2.fromOffset(0,count*41)
end
filter:GetPropertyChangedSignal("Text"):Connect(render)
export.MouseButton1Click:Connect(function()
 local header={schemaVersion="66.telemetry",placeId=game.PlaceId,eventCount=#events,ticks=tick}
 local ok,encoded=pcall(function() return HttpService:JSONEncode(header) end)
 if not ok then warn("Lycoles v66 header export failed") return end
 print("LYCOLES_V66_HEADER "..encoded)
 for i=1,#events do
  local success,part=pcall(function() return HttpService:JSONEncode(events[i]) end)
  if success then print("LYCOLES_V66_EVENT "..i.." "..part)
  else warn("Lycoles v66 event encode failure "..i) end
 end
 print("LYCOLES_V66_END "..#events)
 status.Text="Exported "..#events.." event lines"
end)
task.spawn(function()
 while gui.Parent do
  local ok,visited=pcall(sample)
  if ok then
   status.Text="Tick "..tick.." | changes "..#events.." | scanned "..visited
   render()
  else warn("Lycoles v66 sampling failed: "..tostring(visited)) end
  task.wait(3)
 end
end)
'''
def generate(place_id, max_events=300, max_scan=4000):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("place_id must be positive integer")
    if type(max_events) is not int or not 20 <= max_events <= 1000:
        raise ValueError("max_events must be 20..1000")
    if type(max_scan) is not int or not 100 <= max_scan <= 10000:
        raise ValueError("max_scan must be 100..10000")
    return (LUA.replace("__PLACE__",str(place_id)).replace("__MAXEVENTS__",str(max_events))
            .replace("__MAXSCAN__",str(max_scan)))

def parse_log(log, expected_place=None):
    header=None
    records={}
    end=None
    for line in log.splitlines():
        if "LYCOLES_V66_HEADER " in line:
            candidate=json.loads(line.split("LYCOLES_V66_HEADER ",1)[1])
            if candidate.get("schemaVersion")!="66.telemetry": raise ValueError("wrong schema")
            if header is not None and header!=candidate: raise ValueError("conflicting headers")
            header=candidate
        elif "LYCOLES_V66_EVENT " in line:
            tail=line.split("LYCOLES_V66_EVENT ",1)[1]
            index,_,raw=tail.partition(" ")
            if not index.isdecimal(): continue
            record=json.loads(raw)
            if not isinstance(record,dict) or not all(k in record for k in ("tick","kind","path","before","after")):
                raise ValueError("invalid event")
            i=int(index)
            if i in records and records[i]!=record: raise ValueError("conflicting event")
            records[i]=record
        elif "LYCOLES_V66_END " in line:
            tail=line.split("LYCOLES_V66_END ",1)[1].strip()
            if tail.isdecimal(): end=int(tail)
    if header is None: raise ValueError("missing header")
    if expected_place is not None and header.get("placeId")!=expected_place:
        raise ValueError("place mismatch")
    n=header.get("eventCount")
    if type(n) is not int or not 0<=n<=1000: raise ValueError("invalid event count")
    complete=(end==n and set(records)==set(range(1,n+1)))
    return {"schemaVersion":"66.import","placeId":header["placeId"],"complete":complete,
            "expectedEvents":n,"receivedEvents":len(records),
            "missingIndices":[i for i in range(1,n+1) if i not in records],
            "events":[records[i] for i in sorted(records) if 1<=i<=n],
            "serverOutcomeVerified":False,"causalityVerified":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v66"))
    p.add_argument("--log",type=Path)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"telemetry-v66.luau").write_text(generate(a.place_id),encoding="utf-8")
    if a.log:
        if a.log.stat().st_size>20_000_000: p.error("log too large")
        result=parse_log(a.log.read_text(encoding="utf-8-sig",errors="replace"),a.place_id)
        (a.output/"telemetry-import-v66.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
        print("v66 imported",result["receivedEvents"],"events; complete:",result["complete"])
    else: print("v66 generated")
if __name__=="__main__": main()
