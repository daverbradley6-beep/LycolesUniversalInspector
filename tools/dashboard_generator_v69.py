#!/usr/bin/env python3
"""v69: Generate a read-only, functional Roblox evidence dashboard from v68 data.

No remote invocation or action claims are inferred from names or passive telemetry.
"""
import argparse
import json
import re
from pathlib import Path

MAX_INPUT = 50_000_000
MAX_ITEMS = 300
MAX_NAME = 160
SUPPORTED = {"observable_value", "gui_control", "proximity_prompt",
             "click_detector", "standard_tool", "remote_observed", "bindable_observed"}

def validate_release(data, expected_place):
    if not isinstance(data, dict) or data.get("schemaVersion") != "68.release":
        raise ValueError("expected a v68 release manifest")
    if type(expected_place) is not int or expected_place <= 0 or data.get("placeId") != expected_place:
        raise ValueError("place ID mismatch")
    if data.get("readyForActionGeneration") is True:
        raise ValueError("unexpected executable-action claim in passive release")
    return data

def candidates(catalog):
    if not isinstance(catalog, dict) or not isinstance(catalog.get("capabilities"), list):
        raise ValueError("invalid catalog")
    unique = {}
    for item in catalog["capabilities"]:
        if not isinstance(item, dict):
            continue
        kind, path = item.get("kind"), item.get("path")
        if kind not in SUPPORTED or not isinstance(path, str) or not 0 < len(path) <= 10000:
            continue
        if item.get("actionStatus") not in ("unverified", None):
            continue
        unique[(path, kind)] = {"path": path, "kind": kind,
                                "className": str(item.get("className", ""))[:60]}
    return sorted(unique.values(), key=lambda x: (x["kind"], x["path"]))[:MAX_ITEMS]

LUA = r'''-- Lycoles v69 | Universal read-only evidence dashboard
-- This GUI reports discovered objects and current local leaderstats. It never calls remotes.
local Players=game:GetService("Players")
local UIS=game:GetService("UserInputService")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("Lycoles v69: wrong place") return end
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV69")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV69" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame")
panel.Name="Panel" panel.Size=UDim2.fromOffset(610,430)
panel.Position=UDim2.new(0.07,0,0.14,0)
panel.BackgroundColor3=Color3.fromRGB(25,32,48) panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-100,0,40) title.BackgroundTransparency=1
title.TextColor3=Color3.new(1,1,1) title.TextXAlignment=Enum.TextXAlignment.Left
title.Text="  Lycoles v69 | Evidence dashboard (read-only)" title.Parent=panel
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(38,32) close.Position=UDim2.new(1,-40,0,4)
close.Text="X" close.Parent=panel
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local mini=Instance.new("TextButton")
mini.Size=UDim2.fromOffset(38,32) mini.Position=UDim2.new(1,-82,0,4)
mini.Text="-" mini.Parent=panel
local search=Instance.new("TextBox")
search.Size=UDim2.new(1,-16,0,34) search.Position=UDim2.fromOffset(8,44)
search.PlaceholderText="Search discovered objects or live stats"
search.Text="" search.ClearTextOnFocus=false search.Parent=panel
local refresh=Instance.new("TextButton")
refresh.Size=UDim2.fromOffset(110,32) refresh.Position=UDim2.fromOffset(8,84)
refresh.Text="Refresh" refresh.Parent=panel
local status=Instance.new("TextLabel")
status.Size=UDim2.new(1,-140,0,32) status.Position=UDim2.fromOffset(126,84)
status.BackgroundTransparency=1 status.TextColor3=Color3.new(1,1,1)
status.TextXAlignment=Enum.TextXAlignment.Left status.Parent=panel
local scroll=Instance.new("ScrollingFrame")
scroll.Size=UDim2.new(1,-16,1,-126) scroll.Position=UDim2.fromOffset(8,122)
scroll.CanvasSize=UDim2.fromOffset(0,0) scroll.ScrollBarThickness=6
scroll.Parent=panel
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,3) layout.Parent=scroll
local items=__ITEMS__
local minimized=false
mini.MouseButton1Click:Connect(function()
 minimized=not minimized
 panel.Size=minimized and UDim2.fromOffset(610,40) or UDim2.fromOffset(610,430)
 mini.Text=minimized and "+" or "-"
 for _,v in ipairs({search,refresh,status,scroll}) do v.Visible=not minimized end
end)
local dragging=false local start=nil local origin=nil local dragInput=nil
title.Active=true
title.InputBegan:Connect(function(input)
 if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
  dragging=true start=input.Position origin=panel.Position
  local conn
  conn=input.Changed:Connect(function()
   if input.UserInputState==Enum.UserInputState.End then
    dragging=false conn:Disconnect()
   end
  end)
 end
end)
title.InputChanged:Connect(function(input)
 if input.UserInputType==Enum.UserInputType.MouseMovement or input.UserInputType==Enum.UserInputType.Touch then dragInput=input end
end)
UIS.InputChanged:Connect(function(input)
 if dragging and input==dragInput and start and origin then
  local d=input.Position-start
  panel.Position=UDim2.new(origin.X.Scale,origin.X.Offset+d.X,origin.Y.Scale,origin.Y.Offset+d.Y)
 end
end)
local function line(text)
 local l=Instance.new("TextLabel")
 l.Size=UDim2.new(1,-10,0,26) l.BackgroundColor3=Color3.fromRGB(37,47,67)
 l.TextColor3=Color3.new(1,1,1) l.TextXAlignment=Enum.TextXAlignment.Left
 l.TextTruncate=Enum.TextTruncate.AtEnd l.Text="  "..text l.Parent=scroll
end
local function render()
 for _,child in ipairs(scroll:GetChildren()) do if child:IsA("TextLabel") then child:Destroy() end end
 local q=search.Text:lower()
 local count=0
 local stats=player:FindFirstChild("leaderstats")
 if stats then
  for _,v in ipairs(stats:GetChildren()) do
   if v:IsA("ValueBase") then
    local ok,val=pcall(function() return tostring(v.Value) end)
    local msg="[LIVE STAT] "..v.Name.." = "..(ok and val or "?")
    if q=="" or msg:lower():find(q,1,true) then line(msg) count+=1 end
   end
  end
 end
 for _,item in ipairs(items) do
  local msg="["..item.kind.."] "..item.path
  if q=="" or msg:lower():find(q,1,true) then line(msg) count+=1 end
 end
 status.Text=tostring(count).." shown | "..tostring(#items).." discovered | passive only"
 scroll.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+8)
end
refresh.MouseButton1Click:Connect(render)
search:GetPropertyChangedSignal("Text"):Connect(render)
layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
 scroll.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+8)
end)
render()
task.spawn(function()
 while gui.Parent do
  task.wait(3)
  if not minimized and gui.Parent then render() end
 end
end)
'''

def generate(manifest, catalog, place_id):
    validate_release(manifest, place_id)
    entries=candidates(catalog)
    payload=json.dumps(entries, ensure_ascii=True, separators=(",", ":"))
    # JSON array/object literals are compatible with Luau only after translating JSON syntax.
    # Encode as a Luau table with escaped string values instead.
    def quote(s):
        return json.dumps(s, ensure_ascii=True)
    table="{" + ",".join("{path="+quote(x["path"])+",kind="+quote(x["kind"])+"}" for x in entries) + "}"
    return LUA.replace("__PLACE__",str(place_id)).replace("__ITEMS__",table)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--catalog",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v69"))
    a=p.parse_args()
    for path in (a.manifest,a.catalog):
        if not path.is_file(): p.error(f"missing input: {path}")
        if path.stat().st_size>MAX_INPUT: p.error(f"input exceeds 50 MB: {path}")
    manifest=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    cat=json.loads(a.catalog.read_text(encoding="utf-8-sig"))
    script=generate(manifest,cat,a.place_id)
    a.output.mkdir(parents=True,exist_ok=True)
    target=a.output/"dashboard-v69.luau"
    target.write_text(script,encoding="utf-8")
    print(f"v69 generated {target}; {len(candidates(cat))} discovery entries; read-only")
if __name__=="__main__": main()
