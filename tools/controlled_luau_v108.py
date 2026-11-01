#!/usr/bin/env python3
"""Execute generated v107 Luau in a bounded simulated Roblox client environment.

This runs actual Luau bytecode through the official CLI, but all Roblox objects are
strict local stubs. Success is simulation evidence, never live Roblox verification.
"""
import argparse
import hashlib
import json
import os
import resource
import subprocess
import tempfile
from pathlib import Path

from feature_planner_v107 import validate_feature_plan
from install_luau_v108 import (
    BINARY_SHA256,
    SHA256 as RUNTIME_ARCHIVE_SHA256,
    VERSION as RUNTIME_VERSION,
)
from integrated_pipeline_v107 import emit_luau
from release_pipeline_v104 import canonical
from resolver_harness_v107 import _validate_hierarchy, evaluate

SCHEMA_VERSION = "108.controlled-luau-execution"
RUNTIME_EXECUTABLE_SHA256 = BINARY_SHA256["luau"]
MAX_PROGRAM_BYTES = 2_000_000
MAX_OUTPUT_BYTES = 1_000_000
MAX_TIMEOUT_SECONDS = 5.0


class ControlledExecutionError(RuntimeError):
    pass


def _luau_string(value):
    output = ['"']
    for byte in value.encode("utf-8"):
        if 32 <= byte <= 126 and byte not in (34, 92):
            output.append(chr(byte))
        elif byte == 34:
            output.append('\\"')
        elif byte == 92:
            output.append("\\\\")
        else:
            output.append(f"\\{byte:03d}")
    output.append('"')
    return "".join(output)


def _luau(value):
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _luau_string(value)
    if type(value) in (int, float):
        return repr(value)
    if isinstance(value, list):
        return "{" + ",".join(_luau(item) for item in value) + "}"
    if isinstance(value, dict):
        return "{" + ",".join(
            "[" + _luau(key) + "]=" + _luau(item)
            for key, item in sorted(value.items())
        ) + "}"
    raise ValueError("unsupported fixture value")


STUBS = r'''
local __scheduledTasks = 0
local __unsupportedApis = {}
local __writable = {
 Name=true,Parent=true,ResetOnSpawn=true,Size=true,Position=true,CanvasSize=true,
 Padding=true,Text=true,PlaceholderText=true,Visible=true,
}
local __readable = {
 Name=true,ClassName=true,Parent=true,ResetOnSpawn=true,Size=true,Position=true,
 CanvasSize=true,Padding=true,Text=true,PlaceholderText=true,Visible=true,
 Activated=true,AbsoluteContentSize=true,LocalPlayer=true,PlaceId=true,
 Value=true,Enabled=true,
}
local __methods = {}
local __instanceMeta = {}
local __signalMethods = {}
local __signalMeta = {__index=__signalMethods}

local function __signal(name)
 return setmetatable({__name=name,__callbacks={}},__signalMeta)
end
function __signalMethods:Connect(callback)
 if type(callback) ~= "function" then error("invalid signal callback") end
 table.insert(self.__callbacks,callback)
 local connected = true
 return {Disconnect=function()
  if not connected then return end
  connected = false
  for index,value in ipairs(self.__callbacks) do
   if value == callback then table.remove(self.__callbacks,index) break end
  end
 end}
end
function __signalMethods:Fire(...)
 for _,callback in ipairs(table.clone(self.__callbacks)) do callback(...) end
end

local function __detach(child)
 local parent = rawget(child,"__properties").Parent
 if parent == nil then return end
 local children = rawget(parent,"__children")
 for index,value in ipairs(children) do
  if value == child then table.remove(children,index) break end
 end
end
local function __assignParent(child,parent)
 __detach(child)
 rawget(child,"__properties").Parent = parent
 if parent ~= nil then table.insert(rawget(parent,"__children"),child) end
end
local function __new(className,name,properties)
 local object = {
  __properties={Name=name or className,ClassName=className,Parent=nil,Visible=true},
  __children={},__propertySignals={},__destroyed=false,
 }
 if className == "TextButton" then object.__properties.Activated = __signal("Activated") end
 if className == "UIListLayout" then object.__properties.AbsoluteContentSize = {Y=0} end
 if properties then
  for key,value in pairs(properties) do object.__properties[key]=value end
 end
 return setmetatable(object,__instanceMeta)
end
function __instanceMeta.__index(self,key)
 local method = __methods[key]
 if method ~= nil then return method end
 local properties = rawget(self,"__properties")
 local value = properties[key]
 if value ~= nil then return value end
 if __readable[key] then return nil end
 local className = properties.ClassName
 table.insert(__unsupportedApis,className.."."..tostring(key))
 error("unsupported API member "..className.."."..tostring(key))
end
function __instanceMeta.__newindex(self,key,value)
 local properties = rawget(self,"__properties")
 if key == "Parent" then
  __assignParent(self,value)
 elseif __writable[key] or properties[key] ~= nil then
  properties[key]=value
 else
  table.insert(__unsupportedApis,properties.ClassName.."."..tostring(key))
  error("unsupported API member "..properties.ClassName.."."..tostring(key))
 end
 local signal = rawget(self,"__propertySignals")[key]
 if signal then signal:Fire() end
end
function __methods:GetChildren()
 return table.clone(rawget(self,"__children"))
end
function __methods:FindFirstChild(name)
 for _,child in ipairs(rawget(self,"__children")) do
  if child.Name == name then return child end
 end
 return nil
end
function __methods:WaitForChild(name)
 local child = self:FindFirstChild(name)
 if child == nil then error("missing child "..tostring(name)) end
 return child
end
function __methods:GetPropertyChangedSignal(name)
 local signals = rawget(self,"__propertySignals")
 if signals[name] == nil then signals[name]=__signal("property:"..name) end
 return signals[name]
end
function __methods:Destroy()
 __assignParent(self,nil)
 rawset(self,"__destroyed",true)
end

local function __fixtureNode(spec)
 local object=__new(spec.className,spec.name,spec.properties)
 for _,childSpec in ipairs(spec.children) do
  local child=__fixtureNode(childSpec)
  child.Parent=object
 end
 return object
end
local __fixture=__FIXTURE
local __fixtureRoots={}
for _,rootSpec in ipairs(__fixture.roots) do
 __fixtureRoots[rootSpec.name]=__fixtureNode(rootSpec)
end
workspace=__fixtureRoots.Workspace or __new("Workspace","Workspace")
local __replicatedStorage=__fixtureRoots.ReplicatedStorage or __new("ReplicatedStorage","ReplicatedStorage")
local __players=__fixtureRoots.Players or __new("Players","Players")
local __player=__new("Player","LocalPlayer")
local __playerGui=__fixtureRoots.PlayerGui or __new("PlayerGui","PlayerGui")
__playerGui.Parent=__player
__players.__properties.LocalPlayer=__player
local __game=__new("DataModel","game",{PlaceId=__RUNTIME_PLACE})
function __methods:GetService(name)
 if self ~= __game then
  table.insert(__unsupportedApis,self.ClassName..".GetService")
  error("unsupported API member "..self.ClassName..".GetService")
 end
 if name == "Players" then return __players end
 if name == "ReplicatedStorage" then return __replicatedStorage end
 table.insert(__unsupportedApis,"DataModel.GetService:"..tostring(name))
 error("unsupported service "..tostring(name))
end
game=__game
Instance={new=function(className) return __new(className,className) end}
UDim={new=function(scale,offset) return {Scale=scale,Offset=offset} end}
UDim2={
 new=function(xScale,xOffset,yScale,yOffset)
  return {X={Scale=xScale,Offset=xOffset},Y={Scale=yScale,Offset=yOffset}}
 end,
 fromOffset=function(x,y) return {X={Scale=0,Offset=x},Y={Scale=0,Offset=y}} end,
 fromScale=function(x,y) return {X={Scale=x,Offset=0},Y={Scale=y,Offset=0}} end,
}
task={
 spawn=function(callback)
  if type(callback) ~= "function" then error("invalid task") end
  __scheduledTasks += 1
 end,
 wait=function() return 0 end,
}
'''

DRIVER = r'''
local function __hex(value)
 local text=tostring(value)
 local output={}
 for index=1,#text do output[index]=string.format("%02x",string.byte(text,index)) end
 return table.concat(output)
end
local function __featureStatus(message)
 if message == "missing object or identity mismatch" or message == "missing identity segment" then
  return "identity_mismatch",message
 end
 if message == "missing or ambiguous legacy path segment" then
  return "legacy_resolution_failed",message
 end
 if message == "property unavailable" then return "property_unavailable",message end
 if message == "unsupported path resolution" then return "unsupported_path_resolution",message end
 return "resolved",message
end
local __refreshActivated=false
local __filterApplied=false
local __autoRefreshToggled=false
local __unloadDestroyedGui=false
if gui.Parent ~= nil then
 status.Activated:Fire()
 __refreshActivated=string.find(status.Text,"Refresh all (",1,true) == 1
 search.Text="__lycoles_no_match__"
 __filterApplied=true
 for _,row in ipairs(rows) do
  if row.Visible ~= false then __filterApplied=false end
 end
 search.Text=""
 autoButton.Activated:Fire()
 __autoRefreshToggled=autoButton.Text == "Auto refresh: ON"
 for index,feature in ipairs(features) do
  local prefix=feature.label..": "
  local message=string.sub(rows[index].Text,#prefix+1)
  local statusName,value=__featureStatus(message)
  print("LYCOLES|FEATURE|"..__hex(feature.id).."|"..__hex(statusName).."|"..__hex(value))
 end
 local unload=nil
 for _,child in ipairs(panel:GetChildren()) do
  if child.ClassName == "TextButton" and child.Text == "Unload" then unload=child break end
 end
 if unload then unload.Activated:Fire() end
 __unloadDestroyedGui=gui.Parent == nil
else
 print("LYCOLES|NO_GUI")
end
print("LYCOLES|INTERACTIONS|"..(__refreshActivated and "1" or "0").."|"..(__filterApplied and "1" or "0").."|"..(__autoRefreshToggled and "1" or "0").."|"..(__unloadDestroyedGui and "1" or "0"))
print("LYCOLES|SCHEDULED|"..tostring(__scheduledTasks))
for _,name in ipairs(__unsupportedApis) do print("LYCOLES|UNSUPPORTED|"..__hex(name)) end
'''


def _resource_limits():
    resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))


def run_bounded_program(program, luau_binary, *, timeout_seconds=2.0, include_stubs=False):
    """Run Luau with OS resource limits and no inherited environment."""
    if not isinstance(program, str) or len(program.encode("utf-8")) > MAX_PROGRAM_BYTES:
        raise ValueError("invalid or oversized Luau program")
    if type(timeout_seconds) not in (int, float) or not 0 < timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ValueError("invalid timeout")
    binary = Path(luau_binary)
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ControlledExecutionError("Luau runtime unavailable")
    binary_digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    if binary_digest != RUNTIME_EXECUTABLE_SHA256:
        raise ControlledExecutionError("untrusted Luau runtime digest")
    source = (
        STUBS.replace("__FIXTURE", "{roots={}}", 1).replace("__RUNTIME_PLACE", "1", 1) + program
        if include_stubs else program
    )
    if len(source.encode("utf-8")) > MAX_PROGRAM_BYTES:
        raise ValueError("invalid or oversized Luau program")
    with tempfile.TemporaryDirectory(prefix="lycoles-luau-") as directory:
        script = Path(directory) / "controlled.luau"
        script.write_text(source, encoding="utf-8")
        stdout_path = Path(directory) / "stdout.log"
        stderr_path = Path(directory) / "stderr.log"
        try:
            with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
                completed = subprocess.run(
                    [str(binary.resolve()), str(script)],
                    cwd=directory,
                    env={"PATH": "", "LANG": "C", "LC_ALL": "C"},
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=float(timeout_seconds),
                    check=False,
                    preexec_fn=_resource_limits,
                )
        except subprocess.TimeoutExpired as exc:
            raise ControlledExecutionError("Luau execution timeout") from exc
        if stdout_path.stat().st_size >= MAX_OUTPUT_BYTES or stderr_path.stat().st_size >= MAX_OUTPUT_BYTES:
            raise ControlledExecutionError("Luau output limit exceeded")
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
        stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    if completed.returncode != 0:
        lines = stderr.strip().splitlines()
        detail = " | ".join(lines[:3]) if lines else "unknown runtime error"
        raise ControlledExecutionError("Luau runtime error: " + detail[:300])
    return stdout


def _decode_hex(value):
    try:
        return bytes.fromhex(value).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise ControlledExecutionError("invalid Luau transcript encoding") from exc


def _parse_transcript(stdout, feature_plan, model):
    feature_rows = {}
    interactions = None
    scheduled = None
    unsupported = []
    no_gui = False
    for line in stdout.splitlines():
        parts = line.split("|")
        if parts[:2] == ["LYCOLES", "FEATURE"] and len(parts) == 5:
            identifier, status, value = map(_decode_hex, parts[2:])
            if identifier in feature_rows:
                raise ControlledExecutionError("duplicate feature transcript")
            feature_rows[identifier] = {"id": identifier, "status": status, "runtimeMessage": value}
            if status == "resolved":
                feature_rows[identifier]["observedValue"] = value
        elif parts == ["LYCOLES", "NO_GUI"]:
            no_gui = True
        elif parts[:2] == ["LYCOLES", "INTERACTIONS"] and len(parts) == 6:
            interactions = {
                "refreshActivated": parts[2] == "1",
                "filterApplied": parts[3] == "1",
                "autoRefreshToggled": parts[4] == "1",
                "unloadDestroyedGui": parts[5] == "1",
            }
        elif parts[:2] == ["LYCOLES", "SCHEDULED"] and len(parts) == 3:
            scheduled = int(parts[2])
        elif parts[:2] == ["LYCOLES", "UNSUPPORTED"] and len(parts) == 3:
            unsupported.append(_decode_hex(parts[2]))
    expected_ids = [feature["id"] for feature in feature_plan["features"]]
    if no_gui:
        if any(item["status"] != "place_mismatch" for item in model["features"]):
            raise ControlledExecutionError("generated script did not initialize")
        features = [
            {"id": identifier, "status": "place_mismatch", "runtimeMessage": "place guard returned"}
            for identifier in expected_ids
        ]
    else:
        if set(feature_rows) != set(expected_ids):
            raise ControlledExecutionError("incomplete feature transcript")
        features = [feature_rows[identifier] for identifier in expected_ids]
    if interactions is None or scheduled is None:
        raise ControlledExecutionError("incomplete execution transcript")
    return features, interactions, scheduled, sorted(set(unsupported))


def _value_agrees(actual, expected):
    if expected is True:
        return actual == "true"
    if expected is False:
        return actual == "false"
    if type(expected) in (int, float):
        try:
            return float(actual) == float(expected)
        except ValueError:
            return False
    return actual == expected


def _status_agrees(actual, expected):
    if actual == expected:
        return True
    return actual == "legacy_resolution_failed" and expected in {"legacy_missing", "legacy_ambiguity"}


def _instrument_generated_source(source, place_id):
    guard = f"if not player or game.PlaceId ~= {place_id} then return end"
    if source.count(guard) != 1:
        raise ControlledExecutionError("generated place guard not instrumentable")
    instrumented_guard = f"if player and game.PlaceId == {place_id} then"
    mismatch = """
else
 print("LYCOLES|NO_GUI")
 print("LYCOLES|INTERACTIONS|0|0|0|0")
 print("LYCOLES|SCHEDULED|0")
end
"""
    return source.replace(guard, instrumented_guard, 1) + "\n" + DRIVER + mismatch


def execute(feature_plan, hierarchy, runtime_place_id, luau_binary, timeout_seconds=2.0):
    """Execute generated Luau and compare its simulated observations to the model."""
    validate_feature_plan(feature_plan)
    _validate_hierarchy(hierarchy)
    if type(runtime_place_id) is not int or runtime_place_id <= 0:
        raise ValueError("invalid runtime place")
    model = evaluate(feature_plan, hierarchy, runtime_place_id)
    generated_source = emit_luau(feature_plan)
    instrumented_source = _instrument_generated_source(generated_source, feature_plan["placeId"])
    fixture_source = _luau(hierarchy)
    prelude = STUBS.replace("__FIXTURE", fixture_source, 1).replace("__RUNTIME_PLACE", str(runtime_place_id), 1)
    source = prelude + "\n" + instrumented_source
    stdout = run_bounded_program(source, luau_binary, timeout_seconds=timeout_seconds)
    features, interactions, scheduled, unsupported = _parse_transcript(stdout, feature_plan, model)
    agreements = []
    for actual, expected in zip(features, model["features"]):
        status_ok = _status_agrees(actual["status"], expected["status"])
        value_ok = (
            _value_agrees(actual.get("observedValue"), expected.get("value"))
            if expected["status"] == "resolved" else True
        )
        agreements.append(status_ok and value_ok)
        actual["modelStatus"] = expected["status"]
        actual["modelAgreement"] = status_ok and value_ok
    executable = Path(luau_binary).read_bytes()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "placeId": feature_plan["placeId"],
        "fixturePlaceId": hierarchy["placeId"],
        "fixturePlaceMatches": hierarchy["placeId"] == feature_plan["placeId"],
        "runtimeVersion": RUNTIME_VERSION,
        "runtimeArchiveSha256": RUNTIME_ARCHIVE_SHA256,
        "runtimeExecutableSha256": hashlib.sha256(executable).hexdigest(),
        "fixtureSha256": hashlib.sha256(canonical(hierarchy)).hexdigest(),
        "sourceSha256": hashlib.sha256(generated_source.encode("utf-8")).hexdigest(),
        "instrumentedSourceSha256": hashlib.sha256(instrumented_source.encode("utf-8")).hexdigest(),
        "features": features,
        "interactions": interactions,
        "scheduledTasks": scheduled,
        "unsupportedApiUsages": unsupported,
        "resourceLimits": {
            "addressSpaceBytes": 256 * 1024 * 1024,
            "cpuSeconds": 2,
            "fileBytes": 1024 * 1024,
            "openFiles": 32,
            "timeoutSeconds": timeout_seconds,
        },
        "modelAgreement": all(agreements),
        "readOnly": True,
        "simulatedEnvironment": True,
        "simulationPassed": (
            runtime_place_id == feature_plan["placeId"] == hierarchy["placeId"]
            and all(agreements)
            and all(interactions.values())
            and scheduled == 1
            and not unsupported
        ),
        "luauExecuted": True,
        "generatedBodyExecuted": runtime_place_id == feature_plan["placeId"],
        "robloxRuntimeVerified": False,
        "liveGameVerified": False,
        "gameplayVerified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature-plan", type=Path, required=True)
    parser.add_argument("--hierarchy", type=Path, required=True)
    parser.add_argument("--runtime-place-id", type=int, required=True)
    parser.add_argument("--luau", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=2.0)
    args = parser.parse_args()
    feature_plan = json.loads(args.feature_plan.read_text(encoding="utf-8-sig"))
    hierarchy = json.loads(args.hierarchy.read_text(encoding="utf-8-sig"))
    result = execute(feature_plan, hierarchy, args.runtime_place_id, args.luau, args.timeout)
    if args.output.is_symlink():
        raise ValueError("symlink output forbidden")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(result))
    print(json.dumps({
        "ok": True,
        "features": len(result["features"]),
        "modelAgreement": result["modelAgreement"],
        "simulatedEnvironment": True,
        "luauExecuted": True,
        "robloxRuntimeVerified": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
