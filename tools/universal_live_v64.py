#!/usr/bin/env python3
"""v64 game-agnostic live inspector with bounded local-player state monitoring."""
import argparse
import json
from pathlib import Path

LUA = r'''-- Lycoles v64 live read-only observer: no remotes invoked, no mutations.
local Players=game:GetService("Players")
if game.PlaceId~=__PLACE__ then warn("Lycoles v64 wrong place") return end
local me=Players.LocalPlayer
if not me then return end
local pg=me:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV64")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV64" gui.ResetOnSpawn=false gui.Parent=pg
local frame=Instance.new("Frame") frame.Size=UDim2.fromOffset(580,440)
frame.Position=UDim2.fromScale(.05,.16) frame.BackgroundColor3=Color3.fromRGB(25,29,40) frame.Parent=gui
local heading=Instance.new("TextLabel") heading.Size=UDim2.new(1,-50,0,42)
heading.Text="Lycoles v64 | Live observations only" heading.TextColor3=Color3.new(1,1,1)
heading.BackgroundTransparency=1 heading.Parent=frame
local close=Instance.new("TextButton") close.Size=UDim2.fromOffset(42,36)
close.Position=UDim2.new(1,-44,0,2) close.Text="X" close.Parent=frame
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local search=Instance.new("TextBox") search.Size=UDim2.new(1,-16,0,38)
search.Position=UDim2.fromOffset(8,44) search.Text="" search.ClearTextOnFocus=false
search.PlaceholderText="Filter observed values, tools, prompts" search.Parent=frame
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-16,1,-90)
scroll.Position=UDim2.fromOffset(8,86) scroll.CanvasSize=UDim2.fromOffset(0,0) scroll.Parent=frame
local layout=Instance.new("UIListLayout") layout.Padding=UDim.new(0,2) layout.Parent=scroll
local MAX_ROWS=__MAXROWS__
local function collect()
 local rows={}
 local function add(kind,name,value)
  if #rows<MAX_ROWS then rows[#rows+1]={kind=kind,name=name,value=tostring(value or "")} end
 end
 local stats=me:FindFirstChild("leaderstats")
 if stats then
  for _,v in ipairs(stats:GetChildren()) do
   if v:IsA("ValueBase") then
    local ok,value=pcall(function() return v.Value end)
    if ok then add("stat",v.Name,value) end
   end
  end
 end
 local bag=me:FindFirstChildOfClass("Backpack")
 if bag then for _,v in ipairs(bag:GetChildren()) do
  if v:IsA("Tool") then add("tool in backpack",v.Name,"observed") end
 end end
 local char=me.Character
 if char then for _,v in ipairs(char:GetChildren()) do
  if v:IsA("Tool") then add("equipped tool",v.Name,"observed") end
 end end
 local nearby=0
 for _,v in ipairs(workspace:GetDescendants()) do
  if v:IsA("ProximityPrompt") then
   nearby+=1
   if nearby<=40 then add("prompt",v.Name,v.Enabled and "enabled" or "disabled") end
  end
 end
 table.sort(rows,function(a,b) return a.kind..a.name<b.kind..b.name end)
 return rows
end
local function draw(rows)
 for _,v in ipairs(scroll:GetChildren()) do if v:IsA("TextLabel") then v:Destroy() end end
 local query=string.lower(search.Text)
 local shown=0
 for _,v in ipairs(rows) do
  local label=v.kind.." | "..v.name.." | "..v.value
  if query=="" or string.find(string.lower(label),query,1,true) then
   shown+=1
   local row=Instance.new("TextLabel") row.Size=UDim2.new(1,-12,0,30)
   row.TextColor3=Color3.new(1,1,1) row.BackgroundTransparency=.7
   row.TextXAlignment=Enum.TextXAlignment.Left row.Text=label row.Parent=scroll
  end
 end
 scroll.CanvasSize=UDim2.fromOffset(0,shown*32)
end
local rows={}
search:GetPropertyChangedSignal("Text"):Connect(function() draw(rows) end)
task.spawn(function()
 while gui.Parent do
  local ok,result=pcall(collect)
  if ok then rows=result draw(rows) else warn("Lycoles v64 observer error: "..tostring(result)) end
  task.wait(3)
 end
end)
'''

def generate(place_id, max_rows=200):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError('place_id must be positive integer')
    if type(max_rows) is not int or not 20 <= max_rows <= 500:
        raise ValueError('max_rows must be 20..500')
    return LUA.replace('__PLACE__', str(place_id)).replace('__MAXROWS__', str(max_rows))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--place-id', type=int, required=True)
    parser.add_argument('--max-rows', type=int, default=200)
    parser.add_argument('--output', type=Path, default=Path('build/release-v64'))
    args=parser.parse_args()
    source=generate(args.place_id,args.max_rows)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'live-observer-v64.luau').write_text(source,encoding='utf-8')
    (args.output/'release-manifest-v64.json').write_text(json.dumps({'schemaVersion':'64.0','placeId':args.place_id,'mode':'read_only_live','maxRows':args.max_rows,'serverOutcomeVerified':False,'automaticGameplayActions':0},indent=2)+'\n',encoding='utf-8')
    print('v64 generated')
if __name__=='__main__': main()
