#!/usr/bin/env python3
"""v40: valid Luau, read-only, game-first diagnostic script builder."""
import argparse
import json
import re
from pathlib import Path

ROOTS={"Workspace","ReplicatedStorage","ReplicatedFirst","Players","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams"}
MAX_PATHS=200
MAX_BYTES=4_000_000

def lua_string(value):
    if not isinstance(value,str) or len(value)>1024:
        raise ValueError("Invalid path literal")
    # JSON quoted strings are valid Luau double-quoted literals after escaping Unicode.
    # Escape JSON-only \u sequences as literal UTF-8 rather than Lua unicode escapes.
    return '"' + ''.join(("\\%03d" % ord(c)) if ord(c)<32 or ord(c)==127 else
                         ('\\\\' if c=="\\" else '\\"' if c=='"' else c)
                         for c in value) + '"'

def collect(report):
    if report.get("schemaVersion")!="39.0" or not isinstance(report.get("families"),list):
        raise ValueError("Expected v39 game-first discovery report")
    paths=[]
    seen=set()
    for family in report["families"]:
        for path in family.get("examplePaths",[]):
            if not isinstance(path,str) or not 1<=len(path)<=1024:
                raise ValueError("Invalid path")
            root=path.split(".",1)[0]
            if root not in ROOTS or "." not in path or path in seen:
                continue
            if any(ord(c)<32 for c in path):continue
            seen.add(path)
            paths.append(path)
            if len(paths)>=MAX_PATHS:return paths
    return paths

def generate(report):
    paths=collect(report)
    table="{"+",\n".join(lua_string(path) for path in paths)+"}"
    return '''-- Lycoles v40 | client-visible object existence diagnostic only
-- No gameplay automation, remotes, metatable hooks, or server-side claims.
local Players = game:GetService("Players")
local player = Players.LocalPlayer
if not player then return end
local playerGui = player:WaitForChild("PlayerGui")
local old = playerGui:FindFirstChild("LycolesV40Diagnostic")
if old then old:Destroy() end
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesV40Diagnostic"
gui.ResetOnSpawn = false
gui.Parent = playerGui
local panel = Instance.new("Frame")
panel.Size = UDim2.fromOffset(580, 420)
panel.Position = UDim2.fromScale(0.04, 0.12)
panel.BackgroundColor3 = Color3.fromRGB(25, 28, 36)
panel.Parent = gui
local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, -50, 0, 40)
title.BackgroundTransparency = 1
title.TextColor3 = Color3.fromRGB(255,255,255)
title.TextXAlignment = Enum.TextXAlignment.Left
title.Text = "Lycoles v40 | Read-only object checks"
title.Parent = panel
local close = Instance.new("TextButton")
close.Size = UDim2.fromOffset(42, 34)
close.Position = UDim2.new(1, -44, 0, 3)
close.Text = "X"
close.Parent = panel
close.Activated:Connect(function() gui:Destroy() end)
local list = Instance.new("ScrollingFrame")
list.Position = UDim2.fromOffset(6, 44)
list.Size = UDim2.new(1, -12, 1, -50)
list.BackgroundTransparency = 1
list.ScrollBarThickness = 8
list.AutomaticCanvasSize = Enum.AutomaticSize.Y
list.CanvasSize = UDim2.fromOffset(0,0)
list.Parent = panel
local layout = Instance.new("UIListLayout")
layout.Padding = UDim.new(0, 3)
layout.Parent = list
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
local function add(text, found)
    local item = Instance.new("TextLabel")
    item.Size = UDim2.new(1, -12, 0, 30)
    item.BackgroundTransparency = 1
    item.TextXAlignment = Enum.TextXAlignment.Left
    item.TextTruncate = Enum.TextTruncate.AtEnd
    item.TextSize = 14
    item.TextColor3 = found and Color3.fromRGB(130,230,150) or Color3.fromRGB(255,180,110)
    item.Text = text
    item.Parent = list
end
for _, path in ipairs(paths) do
    local found = resolve(path)
    add((found and "[FOUND] " or "[NOT FOUND] ") .. path, found)
end
''' % table

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("report",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/diagnostic-v40.luau"))
    args=p.parse_args()
    if args.report.stat().st_size>MAX_BYTES:raise ValueError("Oversized report")
    script=generate(json.loads(args.report.read_text(encoding="utf-8-sig")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(script,encoding="utf-8")
    print("Generated read-only Luau diagnostic:",args.output)

if __name__=="__main__":main()
