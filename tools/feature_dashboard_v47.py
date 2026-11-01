#!/usr/bin/env python3
"""v47: generate a runnable game-specific read-only diagnostic dashboard."""
import argparse
import json
from pathlib import Path
from adaptive_probe_v44 import paths

MAX_FEATURES=100
SUPPORTED_ROOTS=frozenset(("Workspace","Players","ReplicatedStorage","ReplicatedFirst","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams"))

def supported_path(path):
    """Match roots actually supported by the generated Luau resolver."""
    if not isinstance(path,str) or not 1<=len(path)<=1024:
        return False
    parts=path.split(".")
    return len(parts)>=2 and parts[0] in SUPPORTED_ROOTS and all(parts)

def validate(manifest):
    inventory=set(paths(manifest))
    features=manifest.get("features")
    if not isinstance(features,list) or not 1<=len(features)<=MAX_FEATURES:
        raise ValueError("Invalid feature count")
    ids=set()
    output=[]
    for feature in features:
        fid=feature.get("id")
        pp=feature.get("evidencePaths")
        if not isinstance(fid,str) or not fid.startswith("inspect-") or fid in ids:
            raise ValueError("Invalid feature ID")
        if not isinstance(pp,list) or not pp or any(p not in inventory or not supported_path(p) for p in pp):
            raise ValueError("Invalid feature evidence")
        if len(pp)!=len(set(pp)):
            raise ValueError("Duplicate feature paths")
        if feature.get("kind")!="read-only-inspection" or feature.get("gameplayVerified") is not False:
            raise ValueError("Unsupported feature contract")
        ids.add(fid)
        output.append({"id":fid,"label":str(feature.get("label",fid))[:80],"paths":pp})
    return sorted(output,key=lambda f:f["id"])

def generate(manifest):
    features=validate(manifest)
    config=json.dumps({"placeId":manifest["placeId"],"features":features},ensure_ascii=True)
    delim="="
    while "]"+delim+"]" in config:delim+="="
    template=r'''-- Lycoles v47: game-specific read-only diagnostic dashboard.
-- Buttons perform real client-visible path checks; no gameplay mechanics are inferred.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local cfg=HttpService:JSONDecode(CONFIG_LITERAL)
if game.PlaceId~=cfg.placeId then
 warn("Lycoles v47: wrong place ID; diagnostic not started")
 return
end
local old=pg:FindFirstChild("LycolesV47")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV47"
gui.ResetOnSpawn=false
gui.Parent=pg
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(440,420)
panel.Position=UDim2.fromScale(.04,.12)
panel.BackgroundColor3=Color3.fromRGB(25,29,37)
panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-48,0,42)
title.BackgroundTransparency=1
title.TextColor3=Color3.new(1,1,1)
title.Text="Lycoles v47 | Evidence-backed diagnostics"
title.Parent=panel
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(40,36)
close.Position=UDim2.new(1,-42,0,3)
close.Text="X"
close.Parent=panel
close.Activated:Connect(function() gui:Destroy() end)
local list=Instance.new("ScrollingFrame")
list.Size=UDim2.new(1,-16,1,-54)
list.Position=UDim2.fromOffset(8,46)
list.BackgroundTransparency=1
list.ScrollBarThickness=7
list.CanvasSize=UDim2.fromOffset(0,0)
list.AutomaticCanvasSize=Enum.AutomaticSize.Y
list.Parent=panel
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,6)
layout.Parent=list
local roots={
 Workspace=workspace,Players=Players,ReplicatedStorage=game:GetService("ReplicatedStorage"),
 ReplicatedFirst=game:GetService("ReplicatedFirst"),Lighting=game:GetService("Lighting"),
 StarterGui=game:GetService("StarterGui"),StarterPack=game:GetService("StarterPack"),
 StarterPlayer=game:GetService("StarterPlayer"),SoundService=game:GetService("SoundService"),
 Teams=game:GetService("Teams")
}
local function exists(path)
 local pieces=string.split(path,".")
 local root=table.remove(pieces,1)
 local current=roots[root]
 if not current then return false end
 for _,part in ipairs(pieces) do
  if current==Players and (part=="LocalPlayer" or part==player.Name) then current=player
  elseif current==player and part=="PlayerGui" then current=pg
  else current=current:FindFirstChild(part) end
  if not current then return false end
 end
 return true
end
local function newButton(label,callback)
 local b=Instance.new("TextButton")
 b.Size=UDim2.new(1,-12,0,45)
 b.TextColor3=Color3.new(1,1,1)
 b.BackgroundColor3=Color3.fromRGB(49,59,75)
 b.Text=label
 b.Parent=list
 b.Activated:Connect(callback)
 return b
end
local function inspect(feature)
 local found=0
 for _,path in ipairs(feature.paths) do
  if exists(path) then found+=1 end
 end
 return found,#feature.paths
end
local buttons={}
for _,feature in ipairs(cfg.features) do
 local button
 button=newButton(feature.label.." | Check",function()
  local found,total=inspect(feature)
  button.Text=feature.label.." | "..found.."/"..total.." visible"
 end)
 buttons[feature.id]=button
end
newButton("Inspect all systems",function()
 for _,feature in ipairs(cfg.features) do
  local found,total=inspect(feature)
  buttons[feature.id].Text=feature.label.." | "..found.."/"..total.." visible"
 end
end)
'''
    return template.replace("CONFIG_LITERAL","["+delim+"["+config+"]"+delim+"]")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/feature-dashboard-v47.luau"))
    args=p.parse_args()
    if args.manifest.stat().st_size>8_000_000:raise ValueError("Manifest too large")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    script=generate(manifest)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(script,encoding="utf-8")
    print("Generated",len(validate(manifest)),"working read-only diagnostic controls:",args.output)
if __name__=="__main__":main()
