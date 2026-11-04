#!/usr/bin/env python3
"""Run a generated guided GUI trial in bounded Roblox stubs; not live verification."""
import json
from pathlib import Path

from controlled_admin_commands import STUBS
from controlled_luau_v108 import ControlledExecutionError,run_bounded_program
from generate_admin_commands import render as render_admin
from generate_prompt_interactions import render as render_interactions

SCHEMA="114.controlled-gui-activation.1"

SETUP=r'''
local replicatedStorage=newInstance("ReplicatedStorage","ReplicatedStorage");services.ReplicatedStorage=replicatedStorage
local previousIsA=methods.IsA
function methods:IsA(className)
    if className=="ValueBase" then
        return self.ClassName=="IntValue" or self.ClassName=="NumberValue" or self.ClassName=="BoolValue" or self.ClassName=="StringValue"
    end
    if className=="GuiButton" then return self.ClassName=="TextButton" or self.ClassName=="ImageButton" end
    if className=="GuiObject" then
        return self.ClassName=="TextButton" or self.ClassName=="ImageButton" or self.ClassName=="Frame" or self.ClassName=="ScrollingFrame"
    end
    return previousIsA(self,className)
end
local hud=newInstance("ScreenGui","HUD");hud.Enabled=true;hud.Parent=playerGui
local shop=newInstance("Frame","Shop");shop.Visible=true;shop.Parent=hud
local list=newInstance("ScrollingFrame","List");list.Visible=true
list.AbsolutePosition=Vector2.new(0,0);list.AbsoluteSize=Vector2.new(500,500);list.Parent=shop
local button=newInstance("TextButton","Buy");button.Text="Buy Upgrade";button.Visible=true
button.Active=true;button.Selectable=true;button.AutoButtonColor=true;button.Interactable=true
button.AbsolutePosition=Vector2.new(20,20);button.AbsoluteSize=Vector2.new(120,40)
button.Activated=signal();button.Parent=list
local data=newInstance("Folder","Data");data.Parent=player
local upgrades=newInstance("IntValue","Upgrades");upgrades.Value=2;upgrades.Parent=data
_G.__guiClicks=0;_G.__guideObserved=false;_G.__fireGui=true
button.Activated:Connect(function() _G.__guiClicks+=1 upgrades.Value+=1 end)
local httpService={}
function httpService:GenerateGUID(_wrap) return "controlled-gui-session-0001" end
function httpService:JSONEncode(_value) return "{\"controlled\":true}" end
services.HttpService=httpService
task.spawn=function(callback) callback() end
task.wait=function()
    if button:FindFirstChild("LycolesGuidedTarget") then
        _G.__guideObserved=true
        if _G.__fireGui then button.Activated:Fire() end
    end
    return 0
end
_G.__guiTest={button=button,upgrades=upgrades}
'''

DRIVER=r'''
local test=_G.__guiTest
player.Chatted:Fire(";interactionstart")
assert(_G.__guiClicks==25,"guided GUI loop did not require exactly 25 user-event activations")
assert(test.upgrades.Value==27,"guided GUI outcome was not observed")
assert(_G.__guideObserved,"exact GUI highlight was not observed")
assert(_G.LycolesPromptState.attempts==25 and _G.LycolesPromptState.running==false,
    "guided GUI attempt boundary was not synchronized")
assert(_G.LycolesPromptTrialFeedback.entries[25].status=="expected-change-observed",
    "guided GUI success feedback missing")
test.button.Text="Changed label"
player.Chatted:Fire(";interactionstart")
assert(_G.__guiClicks==25,"metadata-drifted GUI unexpectedly activated")
assert(_G.LycolesPromptState.failures==3 and _G.LycolesPromptTrialFeedback.entries[28].status=="gui-metadata-drift",
    "GUI metadata drift boundary missing")
test.button.Text="Buy Upgrade";test.button.Visible=false
player.Chatted:Fire(";interactionstart")
assert(_G.__guiClicks==25,"hidden GUI unexpectedly activated")
assert(_G.LycolesPromptState.failures==3 and _G.LycolesPromptTrialFeedback.entries[31].status=="gui-unavailable",
    "GUI availability boundary missing")
test.button.Visible=true;_G.__fireGui=false
player.Chatted:Fire(";interactionstart")
assert(_G.__guiClicks==25,"timed-out GUI unexpectedly activated")
assert(_G.LycolesPromptState.failures==3 and _G.LycolesPromptTrialFeedback.entries[34].status=="gui-activation-timeout",
    "GUI activation timeout boundary missing")
assert(test.button:FindFirstChild("LycolesGuidedTarget")==nil,"GUI highlight leaked after stop")
_G.LycolesPromptClose()
assert(test.button:FindFirstChild("LycolesGuidedTarget")==nil,"GUI highlight leaked after close")
print("LYCOLES_GUI|PASS|1|1|1|1")
'''


def discovery(place_id):
    metadata={"controlClass":"TextButton","text":"Buy Upgrade","visible":True,
        "active":True,"selectable":True,"autoButtonColor":True,"interactable":True,
        "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
        "effectiveVisible":True}
    signal_value={"key":"Data.Upgrades","change":"increased","generationResolvable":True,
        "stateIdentity":[{"name":"Data","className":"Folder","ordinal":1},
            {"name":"Upgrades","className":"IntValue","ordinal":1}],
        "selection":{"score":2,"requestMatchedTerms":[],"contextMatchedTerms":[],
            "selectedForTrial":True,"outcomeVerified":False}}
    target={"path":"PlayerGui.HUD.Shop.List.Buy","label":"Buy Upgrade",
        "controlType":"GuiButton.Activated","pathIdentity":[
            {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
            {"name":"HUD","className":"ScreenGui","ordinal":1},
            {"name":"Shop","className":"Frame","ordinal":1},
            {"name":"List","className":"ScrollingFrame","ordinal":1},
            {"name":"Buy","className":"TextButton","ordinal":1}],
        "identityMode":"component","identityAmbiguous":False,"featureCandidate":"shops",
        "actionCandidate":"buy","observedActivations":1,"outcomeSignals":[signal_value],
        "selectedOutcome":signal_value,"guiOutcomeSignals":[],
        "evidenceTier":"interaction-with-temporal-state-change",
        "guidedActivationContractReady":True,"trialGenerationReady":True,
        "automaticActivationAvailable":False,"replayContractAvailable":False,
        "prerequisiteEvidence":{"metadataSnapshots":[metadata],"metadataDriftObserved":False},
        "guiMetadata":dict(metadata),"temporalCorrelationOnly":True,
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False,
        "objective":{"score":4,"requestMatchedTerms":[],"requestAligned":False,
            "classification":"interaction-candidate","objectiveVerified":False},"blockers":[]}
    false_claims={"sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"runtimeVerified":False,
        "gameplayVerified":False,"actionOutcomesVerified":False}
    return {"schemaVersion":"111.action-capabilities.1","placeId":place_id,
        "scanId":"controlled-gui-scan","claims":false_claims,
        "promptInteractions":{"targets":[],"trialReadyTargets":0,"selectedTargetPath":None,
            "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False},
        "guiInteractions":{"targets":[target],"guidedTrialReadyTargets":1,
            "selectedTargetPath":target["path"],"automaticActivationSupported":False,
            "generatorIntegrated":True,"generationReadyTargets":1,"causalityProven":False,
            "runtimeVerified":False,"gameplayVerified":False,"blockers":[]},
        "eggHatching":{"automaticSingleTrialReady":False,"targets":[]}}


def execute(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    source=(STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+
        render_interactions(discovery(place_id))+"\n"+render_admin(place_id)+"\n"+DRIVER)
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_GUI|PASS|1|1|1|1":
        raise ControlledExecutionError("invalid controlled GUI transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"guidedActivationObserved":True,
        "exactHighlightObserved":True,"counterIncrementObserved":True,
        "metadataDriftRejected":True,"unavailableControlRejected":True,
        "activationTimeoutObserved":True,"repeatAttemptBoundaryObserved":True,
        "automaticGuiActivationUsed":False,"robloxRuntimeVerified":False,
        "serverAuthorityVerified":False,"causalityProven":False,
        "gameplayVerified":False,"transcript":stdout.strip()}


def canonical(result):
    return json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
