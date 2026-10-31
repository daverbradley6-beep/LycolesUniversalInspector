#!/usr/bin/env python3
"""Create manual, read-only runtime verification plans from observed workflows.

The resulting harness samples client-visible state before/after a user action.
It never triggers GUI controls, remotes, or server-authoritative operations.
"""
import json
import re

KEY=re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
def build_checks(sequences):
    place=sequences.get("placeId")
    if type(place) is not int or place<1 or not isinstance(sequences.get("workflows"),list):
        raise ValueError("Invalid observed workflows")
    checks=[]
    for workflow in sequences["workflows"][:500]:
        if not isinstance(workflow,dict) or not isinstance(workflow.get("steps"),list):continue
        keys=set()
        for step in workflow["steps"]:
            if not isinstance(step,dict):continue
            for change in step.get("stateChanges",[]) if isinstance(step.get("stateChanges"),list) else []:
                if not isinstance(change,dict):continue
                key=change.get("key")
                if isinstance(key,str) and key.startswith("leaderstats.") and KEY.fullmatch(key[12:]):
                    keys.add(key[12:])
        if keys:
            checks.append({"feature":str(workflow.get("feature","unknown"))[:160],
              "transaction":str(workflow.get("transaction",""))[:80],
              "leaderstatsKeys":sorted(keys),"requiresManualAction":True,
              "automaticallyExecutable":False,"serverVerified":False})
    return {"schemaVersion":"21.0","placeId":place,"checks":checks,
      "note":"Checks are observational; a value change does not prove server authorization or cause."}

def render_harness(checks):
    place=checks["placeId"]
    keys=sorted({k for c in checks["checks"] for k in c["leaderstatsKeys"]})
    if not keys: return None
    quoted=",".join(json.dumps(k) for k in keys)
    check_entries=",".join("{feature="+json.dumps(c["feature"])+",transaction="+json.dumps(c["transaction"])+",keys={"+",".join(json.dumps(k) for k in c["leaderstatsKeys"])+"}}" for c in checks["checks"])
    return '''-- Lycoles manual verification harness (read-only)
assert(game.PlaceId == %d, "Incorrect Roblox place")
local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local player = Players.LocalPlayer
assert(player, "LocalPlayer unavailable")
local keys = {%s}
local checkDefinitions = {%s}
local function snapshot()
    local root = player:FindFirstChild("leaderstats")
    local data = {}
    for _, key in ipairs(keys) do
        local node = root and root:FindFirstChild(key)
        if node and node:IsA("ValueBase") then
            local ok, value = pcall(function() return node.Value end)
            if ok and (type(value) == "number" or type(value) == "string" or type(value) == "boolean") then
                data[key] = value
            end
        end
    end
    return data
end
local before = snapshot()
local recordedBefore = {}
local captureReady = false
local api = {}
function api.capture_before()
    before = snapshot()
    return before
end
function api.compare_after()
    local after = snapshot()
    local differences = {}
    for _, key in ipairs(keys) do
        if before[key] ~= after[key] then
            differences[key] = {before = before[key], after = after[key]}
        end
    end
    return {before = before, after = after, changes = differences,
        note = "Client observation only; perform any action manually."}
end
function api.capture_all_before()
    recordedBefore = snapshot()
    captureReady = true
    return recordedBefore
end
function api.export_report()
    if not captureReady then return nil, "Capture before state first" end
    local after = snapshot()
    local results = {}
    for _, check in ipairs(checkDefinitions) do
        local b, a = {}, {}
        for _, key in ipairs(check.keys) do
            if recordedBefore[key] ~= nil then b[key] = recordedBefore[key] end
            if after[key] ~= nil then a[key] = after[key] end
        end
        table.insert(results, {feature = check.feature, transaction = check.transaction,
            before = b, after = a})
    end
    return HttpService:JSONEncode({schemaVersion = "22.0", placeId = game.PlaceId,
        results = results})
end
return api
''' % (place,quoted,check_entries)

def compile_verification(sequences):
    checks=build_checks(sequences)
    return checks,render_harness(checks)
