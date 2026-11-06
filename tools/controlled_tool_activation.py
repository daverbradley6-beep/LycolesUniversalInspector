#!/usr/bin/env python3
"""Run a generated Tool trial in bounded Roblox stubs; not live gameplay verification."""
import json
from pathlib import Path

from controlled_admin_commands import STUBS
from controlled_luau_v108 import ControlledExecutionError,run_bounded_program
from generate_admin_commands import render as render_admin
from generate_prompt_interactions import render as render_interactions

SCHEMA="114.controlled-tool-activation.1"

SETUP=r'''
local replicatedStorage=newInstance("ReplicatedStorage","ReplicatedStorage");services.ReplicatedStorage=replicatedStorage
local previousIsA=methods.IsA
function methods:IsA(className)
    if className=="ValueBase" then
        return self.ClassName=="IntValue" or self.ClassName=="NumberValue" or self.ClassName=="BoolValue" or self.ClassName=="StringValue"
    end
    return previousIsA(self,className)
end
local backpack=newInstance("Backpack","Backpack");backpack.Parent=player
local tool=newInstance("Tool","Training Sword")
tool.ToolTip="Training weapon";tool.RequiresHandle=false;tool.CanBeDropped=false
tool.ManualActivationOnly=false;tool.Enabled=true;tool.Parent=backpack
local leaderstats=newInstance("Folder","leaderstats");leaderstats.Parent=player
local hits=newInstance("IntValue","Hits");hits.Value=4;hits.Parent=leaderstats
local humanoid=player.Character:FindFirstChildOfClass("Humanoid")
function humanoid:EquipTool(target) assert(target==tool,"unexpected Tool");target.Parent=player.Character end
_G.__toolCalls=0
function tool:Activate()
    _G.__toolCalls+=1 hits.Value+=1
    if type(_G.LycolesGameStopAll)=="function" then _G.LycolesGameStopAll() end
end
local httpService={}
function httpService:GenerateGUID(_wrap) return "controlled-tool-session-0001" end
function httpService:JSONEncode(_value) return "{\"controlled\":true}" end
services.HttpService=httpService
task.spawn=function(callback) callback() end
_G.__toolTest={tool=tool,hits=hits,backpack=backpack}
'''

DRIVER=r'''
local test=_G.__toolTest
player.Chatted:Fire(";interactionstart")
assert(_G.__toolCalls==1,"Tool was not activated exactly once")
assert(test.tool.Parent==player.Character,"Tool was not equipped")
assert(test.hits.Value==5,"selected Tool outcome was not observed")
local interactionGui=playerGui:FindFirstChild("LycolesPromptInteractions")
assert(interactionGui~=nil,"interaction GUI missing")
local observed=false
for _,item in ipairs(interactionGui:GetDescendants()) do
    if item:IsA("TextLabel") and string.find(item.Text or "","Observed leaderstats.Hits increased",1,true) then observed=true end
end
assert(observed,"Tool outcome status was not displayed")
assert(_G.LycolesPromptState.selectedLabel=="Training Sword","Tool selection not synchronized")
assert(_G.LycolesPromptState.running==false,"Tool running state not synchronized")
test.tool.ToolTip="Drifted metadata"
player.Chatted:Fire(";interactionstart")
assert(_G.__toolCalls==1,"metadata-drifted Tool unexpectedly activated")
assert(_G.LycolesPromptState.failures==3 and _G.LycolesPromptState.running==false,
    "Tool metadata drift boundary not synchronized")
assert(_G.LycolesPromptTrialFeedback.entries[#_G.LycolesPromptTrialFeedback.entries].status=="tool-metadata-drift",
    "Tool metadata drift feedback missing")
test.tool.ToolTip="Training weapon";test.tool.Enabled=false
player.Chatted:Fire(";interactionstart")
assert(_G.__toolCalls==1,"disabled Tool unexpectedly activated")
assert(_G.LycolesPromptState.failures==3 and _G.LycolesPromptState.running==false,
    "Tool failure boundary not synchronized")
test.tool.Enabled=true
test.tool.Activate=function(_self)
    _G.__toolCalls=_G.__toolCalls+1 test.hits.Value=test.hits.Value+1
end
player.Chatted:Fire(";interactionstart")
assert(_G.__toolCalls==26,"Tool loop did not stop at exactly 25 successful attempts")
assert(_G.LycolesPromptState.attempts==25,"Bounded attempt count mismatch")
assert(_G.LycolesPromptState.running==false,"Tool loop remained active after bounded attempt cap")
player.Chatted:Fire(";stopall")
assert(_G.__toolCalls==26,"stopall activated the Tool")
print("LYCOLES_TOOL|PASS|1|1|1")
'''


def discovery(place_id):
    signal={"key":"leaderstats.Hits","change":"increased","generationResolvable":True,
        "stateIdentity":[{"name":"leaderstats","className":"Folder","ordinal":1},
            {"name":"Hits","className":"IntValue","ordinal":1}],
        "selection":{"score":2,"requestMatchedTerms":[],"contextMatchedTerms":[],
            "selectedForTrial":True,"outcomeVerified":False}}
    target={"path":"LocalPlayer.Backpack.Training Sword","label":"Training Sword",
        "controlType":"Tool.Activated","pathIdentity":[
            {"name":"LocalPlayer","className":"Player","ordinal":1},
            {"name":"Backpack","className":"Backpack","ordinal":1},
            {"name":"Training Sword","className":"Tool","ordinal":1}],
        "identityMode":"component","identityAmbiguous":False,"featureCandidate":"combat",
        "actionCandidate":"attack","observedActivations":1,"outcomeSignals":[signal],
        "selectedOutcome":signal,"guiOutcomeSignals":[],
        "evidenceTier":"interaction-with-temporal-state-change",
        "activationContractReady":True,"trialGenerationReady":True,
        "replayContractAvailable":True,"prerequisites":{"officialToolActivate":True,
            "humanoidEquipTool":True,"toolEnabledAtRuntime":True,"uniqueToolIdentityAtRuntime":True},
        "prerequisiteEvidence":{"metadataSnapshots":[{"tooltip":"Training weapon",
            "requiresHandle":False,"canBeDropped":False,"enabled":True,
            "manualActivationOnly":False}],"metadataDriftObserved":False},
        "toolMetadata":{"tooltip":"Training weapon","requiresHandle":False,
            "canBeDropped":False,"enabled":True,"manualActivationOnly":False},
        "temporalCorrelationOnly":True,"causalityProven":False,
        "runtimeVerified":False,"gameplayVerified":False,
        "objective":{"score":4,"requestMatchedTerms":[],"requestAligned":False,
            "classification":"interaction-candidate","objectiveVerified":False},"blockers":[]}
    false_claims={"sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"runtimeVerified":False,
        "gameplayVerified":False,"actionOutcomesVerified":False}
    return {"schemaVersion":"111.action-capabilities.1","placeId":place_id,
        "scanId":"controlled-tool-scan","claims":false_claims,
        "promptInteractions":{"targets":[],"trialReadyTargets":0,"selectedTargetPath":None,
            "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False},
        "toolInteractions":{"targets":[target],"activationContractReadyTargets":1,
            "selectedTargetPath":target["path"],"executionMechanism":"official Tool:Activate() after bounded equip",
            "generatorIntegrated":True,"generationReadyTargets":1,"causalityProven":False,
            "runtimeVerified":False,"gameplayVerified":False,"blockers":[]},
        "eggHatching":{"automaticSingleTrialReady":False,"targets":[]}}


def execute(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    source=(STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+
        render_interactions(discovery(place_id))+"\n"+render_admin(place_id)+"\n"+DRIVER)
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_TOOL|PASS|1|1|1":
        raise ControlledExecutionError("invalid controlled Tool transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"toolEquipped":True,"toolActivationObserved":True,
        "counterIncrementObserved":True,"failureBoundaryObserved":True,
        "metadataDriftRejected":True,"repeatAttemptBoundaryObserved":True,
        "robloxRuntimeVerified":False,"serverAuthorityVerified":False,
        "causalityProven":False,"gameplayVerified":False,"transcript":stdout.strip()}


def canonical(result):
    return json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
