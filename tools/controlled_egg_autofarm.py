#!/usr/bin/env python3
"""Run a generated egg trial in bounded Roblox stubs; not live gameplay verification."""
import json
from pathlib import Path

from controlled_admin_commands import STUBS
from controlled_luau_v108 import ControlledExecutionError,run_bounded_program
from generate_admin_commands import render as render_admin
from generate_egg_autofarm import render as render_egg

SCHEMA="111.controlled-egg-autofarm.1"

SETUP=r'''
local previousIsA=methods.IsA
function methods:IsA(className)
    if className=="ValueBase" then
        return self.ClassName=="IntValue" or self.ClassName=="NumberValue" or self.ClassName=="BoolValue" or self.ClassName=="StringValue"
    end
    return previousIsA(self,className)
end
function methods:FindFirstChildWhichIsA(className,recursive)
    for _,child in ipairs(self.__children) do if child:IsA(className) then return child end end
    if recursive then
        for _,child in ipairs(self.__children) do local found=child:FindFirstChildWhichIsA(className,true) if found then return found end end
    end
end
workspace=newInstance("Workspace","Workspace");workspace.CurrentCamera=camera;services.Workspace=workspace
local replicatedStorage=newInstance("ReplicatedStorage","ReplicatedStorage");services.ReplicatedStorage=replicatedStorage
function game:FindFirstChild(name) if name=="Workspace" then return workspace elseif name=="ReplicatedStorage" then return replicatedStorage end end
local rendered=newInstance("Folder","Rendered");rendered.Parent=workspace
local chunker=newInstance("Folder","Chunker");chunker.Parent=rendered
local egg=newInstance("Model","Rainbow.Egg");egg.Parent=chunker
local anchor=newInstance("Part","Anchor");anchor.CFrame=CFrame.new(20,4,30);anchor.Parent=egg
local promptFolder=newInstance("Folder","Prompt");promptFolder.Parent=egg
local prompt=newInstance("ProximityPrompt","ProximityPrompt");prompt.MaxActivationDistance=10;prompt.Parent=promptFolder
local leaderstats=newInstance("Folder","leaderstats");leaderstats.Parent=player
local hatches=newInstance("IntValue","🥚 Hatches");hatches.Value=285;hatches.Parent=leaderstats
_G.__promptCalls=0
function fireproximityprompt(target)
    assert(target==prompt,"unexpected prompt target")
    _G.__promptCalls+=1 hatches.Value+=1
    if type(_G.LycolesGameStopAll)=="function" then _G.LycolesGameStopAll() end
end
task.spawn=function(callback) callback() end
_G.__eggTest={prompt=prompt,anchor=anchor,hatches=hatches}
'''

DRIVER=r'''
local test=_G.__eggTest
local root=player.Character:FindFirstChild("HumanoidRootPart")
local beforeCFrame=root.CFrame
player.Chatted:Fire(";eggstart")
assert(_G.__promptCalls==1,"egg prompt was not activated exactly once")
assert(test.hatches.Value==286,"hatch outcome was not observed")
assert(root.CFrame~=beforeCFrame,"automatic teleport was not attempted")
local eggGui=playerGui:FindFirstChild("LycolesEggAutofarm")
assert(eggGui~=nil,"egg GUI missing")
local observed=false
for _,item in ipairs(eggGui:GetDescendants()) do
    if item:IsA("TextLabel") and string.find(item.Text or "","Observed leaderstats.🥚 Hatches increase",1,true) then observed=true end
end
assert(observed,"outcome status was not displayed")
player.Chatted:Fire(";eggmode multi")
assert(_G.__promptCalls==1,"unobserved multi mode activated a prompt")
player.Chatted:Fire(";stopall")
assert(_G.__promptCalls==1,"stopall activated a prompt")
print("LYCOLES_EGG|PASS|1|1|1|1")
'''


def discovery(place_id):
    return {"schemaVersion":"111.action-capabilities.1","placeId":place_id,
        "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"runtimeVerified":False,
            "gameplayVerified":False,"actionOutcomesVerified":False},
        "eggHatching":{"automaticSingleTrialReady":True,"targets":[{
            "label":"Rainbow.Egg","path":"Workspace.Rendered.Chunker.Rainbow.Egg.Prompt.ProximityPrompt",
            "pathIdentity":[
                {"name":"Workspace","className":"Workspace","ordinal":1},
                {"name":"Rendered","className":"Folder","ordinal":1},
                {"name":"Chunker","className":"Folder","ordinal":1},
                {"name":"Rainbow.Egg","className":"Model","ordinal":1},
                {"name":"Prompt","className":"Folder","ordinal":1},
                {"name":"ProximityPrompt","className":"ProximityPrompt","ordinal":1}],
            "controlType":"ProximityPrompt.Triggered","observedTriggers":1,
            "incrementObservations":1,"outcomeKeys":["leaderstats.🥚 Hatches"],
            "evidenceTier":"temporal-state-increment-observed","causalityProven":False,
            "runtimeVerified":False,"gameplayVerified":False}]}}


def execute(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    source=(STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+
        render_egg(discovery(place_id))+"\n"+render_admin(place_id)+"\n"+DRIVER)
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_EGG|PASS|1|1|1|1":
        raise ControlledExecutionError("invalid controlled egg transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"promptActivationObserved":True,
        "teleportAttemptObserved":True,"counterIncrementObserved":True,
        "failureBoundaryObserved":True,"robloxRuntimeVerified":False,
        "serverAuthorityVerified":False,"causalityProven":False,"gameplayVerified":False,
        "transcript":stdout.strip()}


def canonical(result):
    return json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
