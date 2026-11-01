#!/usr/bin/env python3
"""v70 action contract compiler for explicitly configured, local Roblox GUI actions.

Contracts are user-supplied. Discovery alone never authorizes action invocation.
No arbitrary remote calls, bypasses, or unsupported success claims.
"""
import argparse
import json
import re
from pathlib import Path

MAX_CONTRACTS = 60
MAX_INPUT = 2_000_000
ID = re.compile(r"^[a-z][a-z0-9_]{0,47}$")
CLASSES = {"TextButton", "ImageButton"}
OPERATORS = {"changed", "increased", "decreased", "equals"}
LUA = r'''-- Lycoles v70 | Explicit local UI action contracts
-- Action execution requires a real click on this GUI.
local Players=game:GetService("Players")
local UIS=game:GetService("UserInputService")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("Lycoles v70: wrong place") return end
local pg=player:WaitForChild("PlayerGui")
local existing=pg:FindFirstChild("LycolesV70")
if existing then existing:Destroy() end
local root=Instance.new("ScreenGui")
root.Name="LycolesV70" root.ResetOnSpawn=false root.Parent=pg
local frame=Instance.new("Frame")
frame.Size=UDim2.fromOffset(560,430)
frame.Position=UDim2.new(0.08,0,0.13,0)
frame.BackgroundColor3=Color3.fromRGB(23,30,45) frame.Parent=root
local header=Instance.new("TextLabel")
header.Size=UDim2.new(1,-90,0,40)
header.Text="  Lycoles v70 | Contract runner"
header.TextXAlignment=Enum.TextXAlignment.Left
header.TextColor3=Color3.new(1,1,1)
header.BackgroundTransparency=1 header.Active=true header.Parent=frame
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(36,32) close.Position=UDim2.new(1,-38,0,4)
close.Text="X" close.Parent=frame
close.MouseButton1Click:Connect(function() root:Destroy() end)
local mini=Instance.new("TextButton")
mini.Size=UDim2.fromOffset(36,32) mini.Position=UDim2.new(1,-78,0,4)
mini.Text="-" mini.Parent=frame
local list=Instance.new("ScrollingFrame")
list.Size=UDim2.new(1,-14,1,-52) list.Position=UDim2.fromOffset(7,45)
list.CanvasSize=UDim2.fromOffset(0,0)
list.ScrollBarThickness=6 list.Parent=frame
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,6) layout.Parent=list
layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
 list.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+8)
end)
local minimized=false
mini.MouseButton1Click:Connect(function()
 minimized=not minimized
 frame.Size=minimized and UDim2.fromOffset(560,40) or UDim2.fromOffset(560,430)
 mini.Text=minimized and "+" or "-"
 list.Visible=not minimized
end)
local dragging=false local initial=nil local origin=nil local dragInput=nil
header.InputBegan:Connect(function(input)
 if input.UserInputType==Enum.UserInputType.MouseButton1 or input.UserInputType==Enum.UserInputType.Touch then
  dragging=true initial=input.Position origin=frame.Position
  local conn
  conn=input.Changed:Connect(function()
   if input.UserInputState==Enum.UserInputState.End then dragging=false conn:Disconnect() end
  end)
 end
end)
header.InputChanged:Connect(function(input)
 if input.UserInputType==Enum.UserInputType.MouseMovement or input.UserInputType==Enum.UserInputType.Touch then dragInput=input end
end)
UIS.InputChanged:Connect(function(input)
 if dragging and input==dragInput and initial and origin then
  local d=input.Position-initial
  frame.Position=UDim2.new(origin.X.Scale,origin.X.Offset+d.X,origin.Y.Scale,origin.Y.Offset+d.Y)
 end
end)
local contracts=__CONTRACTS__
local function resolve(rootObject,names)
 local current=rootObject
 for _,name in ipairs(names) do
  if not current then return nil end
  current=current:FindFirstChild(name)
 end
 return current
end
local function getStat(spec)
 local stats=player:FindFirstChild("leaderstats")
 local value=stats and stats:FindFirstChild(spec.stat)
 if not value or not value:IsA("ValueBase") then return nil end
 return value.Value
end
local function success(spec,before,after)
 if before==nil or after==nil then return false end
 if spec.op=="changed" then return after~=before end
 if spec.op=="equals" then return tostring(after)==spec.target end
 if typeof(before)~="number" or typeof(after)~="number" then return false end
 if spec.op=="increased" then return after>before end
 if spec.op=="decreased" then return after<before end
 return false
end
local running=false
for _,spec in ipairs(contracts) do
 local button=Instance.new("TextButton")
 button.Size=UDim2.new(1,-10,0,46)
 button.Text=spec.label.." | ready"
 button.TextColor3=Color3.new(1,1,1)
 button.BackgroundColor3=Color3.fromRGB(48,62,87)
 button.Parent=list
 button.MouseButton1Click:Connect(function()
  if running then return end
  running=true
  button.Text=spec.label.." | checking..."
  task.spawn(function()
   local ok,err=pcall(function()
    local before=getStat(spec)
    if before==nil then error("stat unavailable") end
    local target=resolve(pg,spec.path)
    if not target or not target:IsA(spec.className) then error("UI control unavailable") end
    if not target.Visible or not target.Active then error("UI control inactive") end
    target:Activate()
    local passed=false
    local deadline=os.clock()+spec.timeout
    repeat
     task.wait(0.15)
     passed=success(spec,before,getStat(spec))
    until passed or os.clock()>=deadline or not root.Parent
    if not passed then error("outcome not observed before timeout") end
   end)
   if root.Parent then
    button.Text=spec.label.." | "..(ok and "observed success" or ("failed: "..tostring(err)))
   end
   running=false
  end)
 end)
end
'''
def check_string(value, label, limit=160):
    if not isinstance(value, str) or not value or len(value)>limit or any(ord(c)<32 for c in value):
        raise ValueError(f"invalid {label}")
    return value

def validate(data, place_id):
    if not isinstance(data, dict) or data.get("schemaVersion")!="70.contracts":
        raise ValueError("expected 70.contracts")
    if type(place_id) is not int or place_id<=0 or data.get("placeId")!=place_id:
        raise ValueError("place ID mismatch")
    contracts=data.get("contracts")
    if not isinstance(contracts,list) or not 1<=len(contracts)<=MAX_CONTRACTS:
        raise ValueError("contracts must contain 1 to 60 entries")
    seen=set()
    for item in contracts:
        if not isinstance(item,dict) or set(item)!={"id","label","action","outcome"}:
            raise ValueError("invalid contract shape")
        identifier=check_string(item["id"],"id",48)
        if not ID.fullmatch(identifier) or identifier in seen:
            raise ValueError("invalid or duplicate id")
        seen.add(identifier)
        check_string(item["label"],"label")
        action=item["action"]
        if not isinstance(action,dict) or set(action)!={"type","className","path"}:
            raise ValueError("invalid action")
        if action["type"]!="local_gui_activate" or action["className"] not in CLASSES:
            raise ValueError("unsupported action type")
        if not isinstance(action["path"],list) or not 1<=len(action["path"])<=20:
            raise ValueError("invalid action path")
        for part in action["path"]: check_string(part,"path segment")
        outcome=item["outcome"]
        if not isinstance(outcome,dict) or set(outcome)!={"type","stat","operator","target","timeoutSeconds"}:
            raise ValueError("invalid outcome")
        if outcome["type"]!="leaderstat" or outcome["operator"] not in OPERATORS:
            raise ValueError("unsupported outcome")
        check_string(outcome["stat"],"stat")
        if outcome["operator"]=="equals":
            check_string(outcome["target"],"target")
        elif outcome["target"] is not None:
            raise ValueError("target must be null unless equals")
        timeout=outcome["timeoutSeconds"]
        if type(timeout) not in (int,float) or not 0.5<=timeout<=30:
            raise ValueError("timeout must be 0.5 to 30 seconds")
    return contracts

def luau_quote(value):
    # Luau supports escaped quotes/backslashes and literal UTF-8.
    return json.dumps(value,ensure_ascii=False)

def generate(data,place_id):
    contracts=validate(data,place_id)
    rows=[]
    for c in contracts:
        a,o=c["action"],c["outcome"]
        path="{"+",".join(luau_quote(x) for x in a["path"])+"}"
        rows.append("{label="+luau_quote(c["label"])+",className="+luau_quote(a["className"])+
                    ",path="+path+",stat="+luau_quote(o["stat"])+
                    ",op="+luau_quote(o["operator"])+",target="+luau_quote(o["target"] or "")+
                    ",timeout="+str(o["timeoutSeconds"])+"}")
    return LUA.replace("__PLACE__",str(place_id)).replace("__CONTRACTS__","{"+",".join(rows)+"}")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--contracts",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v70"))
    a=p.parse_args()
    if not a.contracts.is_file(): p.error("contract file not found")
    if a.contracts.stat().st_size>MAX_INPUT: p.error("contract file too large")
    data=json.loads(a.contracts.read_text(encoding="utf-8-sig"))
    script=generate(data,a.place_id)
    a.output.mkdir(parents=True,exist_ok=True)
    target=a.output/"contract-runner-v70.luau"
    target.write_text(script,encoding="utf-8")
    print(f"v70 generated {target} ({len(data['contracts'])} explicit contracts)")
if __name__=="__main__": main()
