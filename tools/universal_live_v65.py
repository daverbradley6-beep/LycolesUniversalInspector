#!/usr/bin/env python3
"""Lycoles v65: bounded, read-only live discovery and change-history interface."""
import argparse
import json
from pathlib import Path

SOURCE = r'''-- Lycoles v65: read-only live discovery, no remote invocation or gameplay mutation.
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
if game.PlaceId~=__PLACE__ then warn("Lycoles v65 wrong place") return end
local me=Players.LocalPlayer
if not me then return end
local pg=me:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV65")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV65" gui.ResetOnSpawn=false gui.Parent=pg
local frame=Instance.new("Frame") frame.Size=UDim2.fromOffset(650,490)
frame.Position=UDim2.fromScale(.06,.12) frame.BackgroundColor3=Color3.fromRGB(24,30,43)
frame.BorderSizePixel=0 frame.Parent=gui
local corner=Instance.new("UICorner") corner.CornerRadius=UDim.new(0,9) corner.Parent=frame
local title=Instance.new("TextLabel") title.Size=UDim2.new(1,-60,0,38)
title.Position=UDim2.fromOffset(12,4) title.BackgroundTransparency=1
title.TextColor3=Color3.fromRGB(238,244,255) title.TextXAlignment=Enum.TextXAlignment.Left
title.Font=Enum.Font.GothamBold title.TextSize=16
title.Text="Lycoles v65  |  Live evidence / unverified actions" title.Parent=frame
local close=Instance.new("TextButton") close.Size=UDim2.fromOffset(40,34)
close.Position=UDim2.new(1,-44,0,6) close.Text="X" close.Parent=frame
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local tabs={"All","Stats","Tools","Prompts","GUI","Changes"}
local active="All"
local tabButtons={}
for i,name in ipairs(tabs) do
 local b=Instance.new("TextButton") b.Size=UDim2.fromOffset(99,30)
 b.Position=UDim2.fromOffset(10+(i-1)*105,47) b.Text=name
 b.Parent=frame tabButtons[name]=b
end
local search=Instance.new("TextBox") search.Size=UDim2.new(1,-20,0,34)
search.Position=UDim2.fromOffset(10,83) search.Text=""
search.PlaceholderText="Search paths, prompt text, values and classes"
search.ClearTextOnFocus=false search.Parent=frame
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-20,0,25)
status.Position=UDim2.fromOffset(10,120) status.BackgroundTransparency=1
status.TextColor3=Color3.fromRGB(160,190,230) status.TextXAlignment=Enum.TextXAlignment.Left
status.TextSize=12 status.Text="Observing..." status.Parent=frame
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-20,1,-156)
scroll.Position=UDim2.fromOffset(10,148) scroll.CanvasSize=UDim2.fromOffset(0,0)
scroll.BackgroundColor3=Color3.fromRGB(32,40,56) scroll.BorderSizePixel=0 scroll.Parent=frame
local layout=Instance.new("UIListLayout") layout.Padding=UDim.new(0,3) layout.Parent=scroll
local MAX_ROWS=__MAXROWS__
local MAX_CHANGES=__MAXCHANGES__
local MAX_SCAN=__MAXSCAN__
local state={} local changes={} local rows={}
local function safePath(obj)
 local ok,value=pcall(function() return obj:GetFullName() end)
 if ok then return tostring(value):sub(1,220) end
 return tostring(obj.Name):sub(1,120)
end
local function add(out,kind,obj,value)
 if #out>=MAX_ROWS then return end
 local path=safePath(obj)
 out[#out+1]={kind=kind,path=path,value=tostring(value or ""):sub(1,180),
  className=obj.ClassName}
end
local function observe()
 local out={}
 local stats=me:FindFirstChild("leaderstats")
 if stats then for _,v in ipairs(stats:GetChildren()) do
  if v:IsA("ValueBase") then
   local ok,value=pcall(function() return v.Value end)
   if ok then add(out,"Stats",v,value) end
  end
 end end
 local backpack=me:FindFirstChildOfClass("Backpack")
 if backpack then for _,v in ipairs(backpack:GetChildren()) do
  if v:IsA("Tool") then add(out,"Tools",v,"in backpack") end
 end end
 if me.Character then for _,v in ipairs(me.Character:GetChildren()) do
  if v:IsA("Tool") then add(out,"Tools",v,"equipped") end
 end end
 local scan=0
 for _,root in ipairs({workspace,pg}) do
  local queue={root} local head=1
  while head<=#queue and scan<MAX_SCAN and #out<MAX_ROWS do
   local node=queue[head] head+=1 scan+=1
   if node:IsA("ProximityPrompt") then
    local ok,detail=pcall(function()
     return "action="..node.ActionText.." | object="..node.ObjectText..
      " | distance="..tostring(node.MaxActivationDistance)..
      " | "..(node.Enabled and "enabled" or "disabled")
    end)
    add(out,"Prompts",node,ok and detail or "properties unavailable")
   elseif node:IsA("TextButton") or node:IsA("ImageButton") then
    local ok,label=pcall(function()
     return node:IsA("TextButton") and node.Text or node.Name
    end)
    add(out,"GUI",node,ok and label or "button")
   end
   if scan<MAX_SCAN then
    local ok,kids=pcall(function() return node:GetChildren() end)
    if ok then for _,child in ipairs(kids) do
     if #queue-head<MAX_SCAN then queue[#queue+1]=child end
    end end
   end
  end
 end
 table.sort(out,function(a,b) return a.kind..a.path<b.kind..b.path end)
 return out,scan
end
local function render()
 for _,child in ipairs(scroll:GetChildren()) do
  if child:IsA("TextLabel") then child:Destroy() end
 end
 local shown=0 local query=string.lower(search.Text)
 local source=active=="Changes" and changes or rows
 for _,item in ipairs(source) do
  if active=="All" or active=="Changes" or item.kind==active then
   local label=item.kind.." | "..item.path.." | "..item.value
   if query=="" or string.find(string.lower(label),query,1,true) then
    shown+=1
    local row=Instance.new("TextLabel") row.Size=UDim2.new(1,-12,0,46)
    row.TextColor3=Color3.fromRGB(232,240,255)
    row.BackgroundColor3=shown%2==0 and Color3.fromRGB(42,53,73) or Color3.fromRGB(36,46,64)
    row.BorderSizePixel=0 row.TextWrapped=true row.TextSize=12
    row.TextXAlignment=Enum.TextXAlignment.Left row.Text=label row.Parent=scroll
   end
  end
 end
 scroll.CanvasSize=UDim2.fromOffset(0,shown*49)
end
for name,b in pairs(tabButtons) do
 b.MouseButton1Click:Connect(function() active=name render() end)
end
search:GetPropertyChangedSignal("Text"):Connect(render)
task.spawn(function()
 while gui.Parent do
  local ok,nextRows,visited=pcall(observe)
  if ok then
   local current={}
   for _,item in ipairs(nextRows) do
    local key=item.kind.."|"..item.path
    current[key]=item.value
    if state[key]~=nil and state[key]~=item.value then
     changes[#changes+1]={kind="Changes",path=item.path,
      value=os.date("!%H:%M:%S").." "..state[key].." -> "..item.value}
     if #changes>MAX_CHANGES then table.remove(changes,1) end
    end
   end
   state=current rows=nextRows
   status.Text="Observed "..#rows.." entries | scanned "..visited..
     " objects | "..#changes.." changes | read-only"
   render()
  else
   status.Text="Observer error: "..tostring(nextRows):sub(1,120)
  end
  task.wait(3)
 end
end)
'''
def generate(place_id, max_rows=240, max_changes=150, max_scan=3000):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("place_id must be a positive integer")
    if type(max_rows) is not int or not 30 <= max_rows <= 500:
        raise ValueError("max_rows must be 30..500")
    if type(max_changes) is not int or not 20 <= max_changes <= 500:
        raise ValueError("max_changes must be 20..500")
    if type(max_scan) is not int or not 100 <= max_scan <= 10000:
        raise ValueError("max_scan must be 100..10000")
    return (SOURCE.replace("__PLACE__", str(place_id))
            .replace("__MAXROWS__", str(max_rows))
            .replace("__MAXCHANGES__", str(max_changes))
            .replace("__MAXSCAN__", str(max_scan)))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v65"))
    p.add_argument("--max-rows",type=int,default=240)
    p.add_argument("--max-changes",type=int,default=150)
    p.add_argument("--max-scan",type=int,default=3000)
    a=p.parse_args()
    src=generate(a.place_id,a.max_rows,a.max_changes,a.max_scan)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"live-inspector-v65.luau").write_text(src,encoding="utf-8")
    manifest={"schemaVersion":"65.0","placeId":a.place_id,"mode":"live_read_only",
              "maxRows":a.max_rows,"maxChanges":a.max_changes,"maxScan":a.max_scan,
              "actionContractsVerified":0,"serverOutcomeVerified":False}
    (a.output/"release-manifest-v65.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("v65 generated")
if __name__=="__main__": main()
