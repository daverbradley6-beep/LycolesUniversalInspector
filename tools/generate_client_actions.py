#!/usr/bin/env python3
"""Generate real, place-guarded, read-only Roblox client functions from reviewed contracts.

No arbitrary Lua templates, server remotes, or inferred gameplay operations.
"""
import json
import re

ACTIONS={
 "read_leaderstats":'''local function read_leaderstats()
    local player = Players.LocalPlayer
    if not player then return nil, "LocalPlayer unavailable" end
    local stats = player:FindFirstChild("leaderstats")
    if not stats then return {}, nil end
    local result = {}
    for _, child in ipairs(stats:GetChildren()) do
        if child:IsA("ValueBase") then
            local ok, value = pcall(function() return child.Value end)
            if ok and (type(value) == "number" or type(value) == "string" or type(value) == "boolean") then
                result[child.Name] = value
            end
        end
    end
    return result, nil
end''',
 "list_player_gui":'''local function list_player_gui()
    local player = Players.LocalPlayer
    if not player then return nil, "LocalPlayer unavailable" end
    local root = player:FindFirstChildOfClass("PlayerGui")
    if not root then return {}, nil end
    local result = {}
    for _, child in ipairs(root:GetChildren()) do
        if child:IsA("LayerCollector") then
            table.insert(result, child.Name)
        end
    end
    table.sort(result)
    return result, nil
end''',
 "list_proximity_prompts":'''local function list_proximity_prompts()
    local result = {}
    for _, child in ipairs(workspace:GetDescendants()) do
        if child:IsA("ProximityPrompt") then
            table.insert(result, child:GetFullName())
            if #result >= 500 then break end
        end
    end
    table.sort(result)
    return result, nil
end'''
}

def render(contracts):
    if not isinstance(contracts,dict) or contracts.get("schemaVersion")!="15.0":
        raise ValueError("Validated contract document required")
    place=contracts.get("placeId")
    if type(place) is not int or place<1: raise ValueError("Invalid place ID")
    entries=contracts.get("contracts")
    if not isinstance(entries,list) or len(entries)>100: raise ValueError("Invalid contracts")
    lines=["-- Lycoles generated reviewed client actions; no server gameplay automation",
           "assert(game.PlaceId == "+str(place)+', "Incorrect Roblox place")',
           'local Players = game:GetService("Players")',""]
    selected=set()
    for entry in entries:
        if not isinstance(entry,dict) or entry.get("reviewed") is not True or entry.get("scope")!="client-read-only":
            raise ValueError("Unvalidated contract")
        action=entry.get("action")
        if action not in ACTIONS: raise ValueError("Unsupported action")
        selected.add(action)
    for action in sorted(selected):lines.extend([ACTIONS[action],""])
    lines.append("return {")
    for action in sorted(selected):lines.append("    "+action+" = "+action+",")
    lines.append("}")
    return "\n".join(lines)+"\n"

def main():
    import argparse,pathlib
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("contracts");p.add_argument("--output",default="build/LycolesClientActions.lua")
    a=p.parse_args()
    data=json.loads(pathlib.Path(a.contracts).read_text(encoding="utf-8"))
    output=pathlib.Path(a.output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(render(data),encoding="utf-8")
if __name__=="__main__":main()
