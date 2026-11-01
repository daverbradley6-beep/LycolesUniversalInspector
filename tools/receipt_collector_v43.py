#!/usr/bin/env python3
"""v43: generate a client-side read-only diagnostic that prints JSON receipts."""
import argparse
import json
from pathlib import Path

def quote(value):
    if not isinstance(value,str) or len(value)>1024:raise ValueError("Invalid string")
    return '"'+''.join(("\\%03d"%ord(c)) if ord(c)<32 or ord(c)==127 else
                     ("\\\\" if c=="\\" else '\\"' if c=='"' else c)
                     for c in value)+'"'

def generate(manifest):
    if manifest.get("schemaVersion")!="42.0" or manifest.get("readOnly") is not True:
        raise ValueError("Expected read-only v42 manifest")
    paths=[]
    for feature in manifest.get("features",[]):
        if feature.get("kind")!="read-only-inspection" or feature.get("gameplayVerified") is not False:
            raise ValueError("Unsupported feature")
        for path in feature.get("evidencePaths",[]):
            if not isinstance(path,str) or "." not in path or len(path)>1024:
                raise ValueError("Invalid path")
            if path not in paths:paths.append(path)
    if len(paths)>10000:raise ValueError("Too many paths")
    for key in ("scanId","sourceFingerprint"):
        if not isinstance(manifest.get(key),str):raise ValueError("Missing identity")
    if type(manifest.get("placeId")) is not int:raise ValueError("Missing place ID")
    luau_paths="{"+",".join(quote(x) for x in paths)+"}"
    return '''-- Lycoles v43: read-only client-visible path checks.
-- Open Roblox developer console to copy the JSON receipt from output.
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local player = Players.LocalPlayer
if not player then return end
local playerGui = player:WaitForChild("PlayerGui")
local previous = playerGui:FindFirstChild("LycolesV43")
if previous then previous:Destroy() end
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesV43"
gui.ResetOnSpawn = false
gui.Parent = playerGui
local button = Instance.new("TextButton")
button.Size = UDim2.fromOffset(390, 70)
button.Position = UDim2.fromScale(0.05, 0.12)
button.Text = "Lycoles v43 | Run read-only checks"
button.Parent = gui
local paths = %s
local function exists(path)
    local segments = string.split(path, ".")
    local root = table.remove(segments, 1)
    local ok, current = pcall(function() return game:GetService(root) end)
    if not ok or not current then return false end
    for _, segment in ipairs(segments) do
        current = current:FindFirstChild(segment)
        if not current then return false end
    end
    return true
end
button.Activated:Connect(function()
    local checks = {}
    local found = 0
    for _, path in ipairs(paths) do
        local yes = exists(path)
        if yes then found += 1 end
        table.insert(checks, {path=path, found=yes})
    end
    local receipt = {
        schemaVersion="43.0",
        scanId=%s,
        placeId=%d,
        sourceFingerprint=%s,
        checks=checks
    }
    print("LYCOLES_V43_RECEIPT_BEGIN")
    print(HttpService:JSONEncode(receipt))
    print("LYCOLES_V43_RECEIPT_END")
    button.Text = "Checked " .. #checks .. " paths; " .. found .. " found (see console)"
end)
''' % (luau_paths,quote(manifest["scanId"]),manifest["placeId"],quote(manifest["sourceFingerprint"]))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/receipt-collector-v43.luau"))
    a=p.parse_args()
    if a.manifest.stat().st_size>8000000:raise ValueError("Input too large")
    script=generate(json.loads(a.manifest.read_text(encoding="utf-8-sig")))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(script,encoding="utf-8")
    print("Wrote",a.output)

if __name__=="__main__":main()
