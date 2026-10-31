#!/usr/bin/env python3
"""v39 game-first evidence discovery and read-only Luau diagnostic generator."""
import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOTS={"Workspace","ReplicatedStorage","ReplicatedFirst","Players","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams"}
SIGNALS={"training":("train","weight","barbell","muscle","strength","treadmill","lift","gym"),
         "pets":("pet","egg","hatch","companion"),
         "trading":("trade","offer","session"),
         "economy":("coin","cash","currency","gem","money","shop","purchase"),
         "progression":("rebirth","level","xp","experience","rank","quest"),
         "combat":("damage","weapon","attack","fight","boss","health"),
         "movement":("speed","jump","teleport","portal","checkpoint"),
         "interface":("gui","button","label","frame","menu","screen"),
         "world":("map","zone","island","world","area","door")}
MAX_OBJECTS=200000
MAX_PATHS=60

def discover(bundle):
    if not isinstance(bundle,dict) or type(bundle.get("placeId")) is not int or not isinstance(bundle.get("scanId"),str):
        raise ValueError("Invalid receiver bundle identity")
    parts=bundle.get("parts")
    expected=bundle.get("expectedParts")
    if type(expected) is not int or not 1<=expected<=10000 or not isinstance(parts,list) or len(parts)!=expected:
        raise ValueError("Incomplete receiver bundle")
    indexes=[p.get("partIndex") for p in parts if isinstance(p,dict)]
    if sorted(indexes)!=list(range(1,expected+1)):raise ValueError("Missing or duplicate receiver parts")
    groups=defaultdict(lambda:{"paths":set(),"classes":Counter(),"observations":0,"roots":Counter()})
    path_count=Counter()
    records=0
    for part in parts:
        if not isinstance(part.get("objects"),list):raise ValueError("Invalid object list")
        for obj in part["objects"]:
            records+=1
            if records>MAX_OBJECTS:raise ValueError("Object limit exceeded")
            if not isinstance(obj,dict):raise ValueError("Invalid object")
            path,cls=obj.get("path"),obj.get("class",obj.get("className"))
            if not isinstance(path,str) or not 1<=len(path)<=1024 or not isinstance(cls,str) or not cls:
                raise ValueError("Invalid object evidence")
            path_count[path]+=1
            segments=re.findall(r"[a-z]+|[0-9]+",re.sub(r"([a-z])([A-Z])",r"\1 \2",path).lower())
            tokens=set(segments)
            for family,keywords in SIGNALS.items():
                hits=sorted(tokens.intersection(keywords))
                if not hits:continue
                group=groups[family]
                group["paths"].add(path)
                group["classes"][cls]+=1
                group["observations"]+=1
                group["roots"][path.split(".",1)[0]]+=1
    families=[]
    for family,group in sorted(groups.items(),key=lambda item:(-len(item[1]["paths"]),item[0])):
        paths=sorted(group["paths"])
        families.append({"id":family,"status":"structural-hypothesis","distinctPaths":len(paths),
                         "observations":group["observations"],"classes":dict(group["classes"]),
                         "roots":dict(group["roots"]),"examplePaths":paths[:MAX_PATHS],
                         "truncatedExamples":len(paths)>MAX_PATHS,
                         "runtimeVerified":False,"serverOutcomeVerified":False,
                         "automationReady":False})
    return {"schemaVersion":"39.0","source":"game-first-receiver-discovery",
            "placeId":bundle["placeId"],"scanId":bundle["scanId"],
            "summary":{"indexedParts":expected,"indexedRecords":records,
                       "uniquePaths":len(path_count),"pathCollisions":records-len(path_count),
                       "families":len(families),"coverageVerified":False},
            "families":families,"gameplayAutomationApproved":False,
            "notice":"Keyword classifications are hypotheses, not working gameplay functions."}

def generate_luau(report):
    if report.get("schemaVersion")!="39.0":raise ValueError("Expected v39 discovery report")
    paths=[]
    for family in report.get("families",[]):
        for path in family.get("examplePaths",[]):
            if not isinstance(path,str) or len(path)>1024:raise ValueError("Invalid path")
            if path.split(".",1)[0] in ROOTS and path not in paths:
                paths.append(path)
            if len(paths)>=MAX_PATHS:break
        if len(paths)>=MAX_PATHS:break
    # Only client-side, read-only instance resolution. Never invokes remotes or modifies game state.
    data=json.dumps(paths,ensure_ascii=True)
    return """-- Lycoles v39: read-only path existence diagnostic. No gameplay actions.
local Players = game:GetService("Players")
local player = Players.LocalPlayer
if not player then return end
local playerGui = player:WaitForChild("PlayerGui")
local previous = playerGui:FindFirstChild("LycolesV39Diagnostic")
if previous then previous:Destroy() end
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesV39Diagnostic"
gui.ResetOnSpawn = false
gui.Parent = playerGui
local panel = Instance.new("ScrollingFrame")
panel.Name = "ObservedPaths"
panel.Size = UDim2.fromOffset(560, 380)
panel.Position = UDim2.fromScale(0.05, 0.1)
panel.CanvasSize = UDim2.new()
panel.AutomaticCanvasSize = Enum.AutomaticSize.Y
panel.BackgroundColor3 = Color3.fromRGB(25, 28, 36)
panel.Parent = gui
local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 3)
layout.Parent = panel
local paths = %s
local function resolve(path)
    local parts = string.split(path, ".")
    local rootName = table.remove(parts, 1)
    local ok, current = pcall(function() return game:GetService(rootName) end)
    if not ok or not current then return false end
    for _, segment in ipairs(parts) do
        current = current:FindFirstChild(segment)
        if not current then return false end
    end
    return true
end
local function label(text, color)
    local item = Instance.new("TextLabel")
    item.Size = UDim2.new(1, -12, 0, 26)
    item.BackgroundTransparency = 1
    item.TextColor3 = color
    item.TextXAlignment = Enum.TextXAlignment.Left
    item.TextScaled = false
    item.TextSize = 14
    item.Text = text
    item.Parent = panel
end
label("Lycoles v39 | Read-only object checks", Color3.fromRGB(255, 255, 255))
for _, path in ipairs(paths) do
    local found = resolve(path)
    label((found and "[FOUND] " or "[NOT FOUND] ") .. path,
          found and Color3.fromRGB(130, 230, 150) or Color3.fromRGB(255, 180, 110))
end
""" % data

def read(path):
    p=Path(path)
    if p.stat().st_size>64000000:raise ValueError("Oversized input")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("bundle",type=Path)
    p.add_argument("--report",type=Path,default=Path("build/game-discovery-v39.json"))
    p.add_argument("--luau",type=Path,default=Path("build/diagnostic-v39.luau"))
    a=p.parse_args()
    report=discover(read(a.bundle))
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    a.luau.parent.mkdir(parents=True,exist_ok=True)
    a.luau.write_text(generate_luau(report),encoding="utf-8")
    print("Discovered",len(report["families"]),"structural families from",report["summary"]["indexedRecords"],"indexed records")
    print("Wrote",a.report,"and",a.luau)

if __name__=="__main__":main()
