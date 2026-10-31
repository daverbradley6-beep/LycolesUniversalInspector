#!/usr/bin/env python3
"""v41: evidence-gated, game-agnostic feature specifications and implementation stubs."""
import argparse
import json
import re
from pathlib import Path

MAX_FAMILIES=100
MAX_PATHS=100
FAMILY_NAMES={"training":"Training","pets":"Pets","trading":"Trading","economy":"Economy",
              "progression":"Progression","combat":"Combat","movement":"Movement",
              "interface":"Interface","world":"World"}
ROOTS={"Workspace","ReplicatedStorage","ReplicatedFirst","Players","Lighting",
       "StarterGui","StarterPack","StarterPlayer","SoundService","Teams"}

def validate(report):
    if not isinstance(report,dict) or report.get("schemaVersion")!="39.0":
        raise ValueError("Expected v39 game-first report")
    if type(report.get("placeId")) is not int or report["placeId"]<=0:
        raise ValueError("Invalid place ID")
    if not isinstance(report.get("scanId"),str) or not report["scanId"]:
        raise ValueError("Invalid scan ID")
    families=report.get("families")
    if not isinstance(families,list) or len(families)>MAX_FAMILIES:
        raise ValueError("Invalid family list")
    return families

def build(report):
    families=validate(report)
    features=[]
    for family in families:
        if not isinstance(family,dict):raise ValueError("Invalid family")
        name=family.get("id")
        if name not in FAMILY_NAMES:continue
        paths=family.get("examplePaths",[])
        if not isinstance(paths,list):raise ValueError("Invalid evidence paths")
        unique=[]
        for path in paths:
            if not isinstance(path,str) or not 1<=len(path)<=1024:raise ValueError("Invalid evidence path")
            if path.split(".",1)[0] in ROOTS and "." in path and path not in unique:
                unique.append(path)
        unique=unique[:MAX_PATHS]
        if not unique:continue
        features.append({"id":"inspect-"+name,"label":"Inspect "+FAMILY_NAMES[name],
                         "family":name,"kind":"read-only-inspection",
                         "evidencePaths":unique,
                         "evidenceStrength":"structural-only",
                         "requiresLiveCheck":True,
                         "implementationStatus":"diagnostic-only",
                         "gameplayImplementationAvailable":False,
                         "runtimeVerified":False,"serverOutcomeVerified":False})
    return {"schemaVersion":"41.0","source":"evidence-gated-feature-specifications",
            "placeId":report["placeId"],"scanId":report["scanId"],
            "featureCount":len(features),"features":features,
            "gameplayAutomationApproved":False,
            "notice":"Only read-only diagnostics are generated. Game mechanics remain unverified."}

def luau_string(value):
    if not isinstance(value,str) or len(value)>1024:raise ValueError("Invalid string")
    out=[]
    for c in value:
        n=ord(c)
        if n<32 or n==127:out.append("\\%03d"%n)
        elif c=="\\":out.append("\\\\")
        elif c=='"':out.append('\\"')
        else:out.append(c)
    return '"'+''.join(out)+'"'

def generate(spec):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="41.0":raise ValueError("Expected v41 spec")
    entries=[]
    for feature in spec.get("features",[]):
        if feature.get("kind")!="read-only-inspection" or feature.get("gameplayImplementationAvailable") is not False:
            raise ValueError("Unsafe or unsupported feature")
        name=feature.get("label")
        paths=feature.get("evidencePaths")
        if not isinstance(name,str) or not isinstance(paths,list) or len(paths)>MAX_PATHS:
            raise ValueError("Invalid feature")
        checked=[]
        for path in paths:
            if not isinstance(path,str) or path.split(".",1)[0] not in ROOTS or "." not in path:
                raise ValueError("Unsafe path")
            checked.append(luau_string(path))
        entries.append("{name="+luau_string(name)+", paths={"+",".join(checked)+"}}")
    feature_table="{"+",\n".join(entries)+"}"
    return '''-- Lycoles v41 | evidence-gated, read-only feature inspector
-- Buttons report client-visible object presence; they do not automate gameplay.
local Players = game:GetService("Players")
local player = Players.LocalPlayer
if not player then return end
local playerGui = player:WaitForChild("PlayerGui")
local old = playerGui:FindFirstChild("LycolesV41")
if old then old:Destroy() end
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesV41"
gui.ResetOnSpawn = false
gui.Parent = playerGui
local panel = Instance.new("Frame")
panel.Size = UDim2.fromOffset(460, 390)
panel.Position = UDim2.fromScale(0.06, 0.15)
panel.BackgroundColor3 = Color3.fromRGB(26, 29, 37)
panel.Parent = gui
local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, -46, 0, 36)
title.BackgroundTransparency = 1
title.TextColor3 = Color3.fromRGB(255,255,255)
title.Text = "Lycoles v41 | Evidence inspector"
title.Parent = panel
local close = Instance.new("TextButton")
close.Size = UDim2.fromOffset(40, 32)
close.Position = UDim2.new(1, -42, 0, 2)
close.Text = "X"
close.Parent = panel
close.Activated:Connect(function() gui:Destroy() end)
local list = Instance.new("ScrollingFrame")
list.Position = UDim2.fromOffset(8, 40)
list.Size = UDim2.new(1, -16, 1, -48)
list.AutomaticCanvasSize = Enum.AutomaticSize.Y
list.CanvasSize = UDim2.fromOffset(0,0)
list.ScrollBarThickness = 7
list.BackgroundTransparency = 1
list.Parent = panel
local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 5)
layout.Parent = list
local features = %s
local function exists(path)
    local pieces = string.split(path, ".")
    local root = table.remove(pieces, 1)
    local ok, current = pcall(function() return game:GetService(root) end)
    if not ok or not current then return false end
    for _, piece in ipairs(pieces) do
        current = current:FindFirstChild(piece)
        if not current then return false end
    end
    return true
end
for _, feature in ipairs(features) do
    local button = Instance.new("TextButton")
    button.Size = UDim2.new(1, -12, 0, 42)
    button.BackgroundColor3 = Color3.fromRGB(52, 59, 73)
    button.TextColor3 = Color3.fromRGB(255,255,255)
    button.Text = feature.name .. " | Check paths"
    button.Parent = list
    button.Activated:Connect(function()
        local found = 0
        for _, path in ipairs(feature.paths) do
            if exists(path) then found += 1 end
        end
        button.Text = feature.name .. " | " .. found .. "/" .. #feature.paths .. " observed"
    end)
end
''' % feature_table

def read(path):
    p=Path(path)
    if p.stat().st_size>8000000:raise ValueError("Oversized input")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("discovery",type=Path)
    p.add_argument("--spec",type=Path,default=Path("build/feature-spec-v41.json"))
    p.add_argument("--luau",type=Path,default=Path("build/feature-inspector-v41.luau"))
    a=p.parse_args()
    spec=build(read(a.discovery))
    a.spec.parent.mkdir(parents=True,exist_ok=True)
    a.spec.write_text(json.dumps(spec,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    a.luau.parent.mkdir(parents=True,exist_ok=True)
    a.luau.write_text(generate(spec),encoding="utf-8")
    print("Generated",spec["featureCount"],"evidence-backed read-only features")

if __name__=="__main__":main()
