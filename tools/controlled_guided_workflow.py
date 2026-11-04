#!/usr/bin/env python3
"""Execute a guided GUI workflow in bounded Roblox stubs; not live verification."""
import json
from pathlib import Path

from controlled_admin_commands import STUBS
from controlled_luau_v108 import ControlledExecutionError,run_bounded_program
from generate_guided_workflow import render

SCHEMA="115.controlled-guided-workflow.1"

SETUP=r'''
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
local originalNew=Instance.new
Instance.new=function(className)
    local object=originalNew(className)
    if className=="TextButton" or className=="ImageButton" then
        object.Activated=signal();object.Visible=true;object.Active=true;object.Selectable=true
        object.AutoButtonColor=true;object.Interactable=true
        object.AbsolutePosition=Vector2.new(0,0);object.AbsoluteSize=Vector2.new(120,40)
    end
    return object
end
local hud=newInstance("ScreenGui","HUD");hud.Enabled=true;hud.Parent=playerGui
local selectButton=Instance.new("TextButton");selectButton.Name="Select";selectButton.Text="Select";selectButton.Parent=hud
local confirmButton=Instance.new("TextButton");confirmButton.Name="Confirm";confirmButton.Text="Confirm";confirmButton.Parent=hud
local data=newInstance("Folder","Data");data.Parent=player
local stage=newInstance("IntValue","Stage");stage.Value=0;stage.Parent=data
_G.__workflowClicks=0;_G.__workflowOrder={};_G.__workflowHighlightCount=0
selectButton.Activated:Connect(function()
    _G.__workflowClicks+=1;table.insert(_G.__workflowOrder,"Select");stage.Value+=1
end)
confirmButton.Activated:Connect(function()
    _G.__workflowClicks+=1;table.insert(_G.__workflowOrder,"Confirm");stage.Value+=1
end)
task.spawn=function(callback) callback() end
task.wait=function()
    if selectButton:FindFirstChild("LycolesGuidedHighlight") then
        _G.__workflowHighlightCount+=1;selectButton.Activated:Fire()
    elseif confirmButton:FindFirstChild("LycolesGuidedHighlight") then
        _G.__workflowHighlightCount+=1;confirmButton.Activated:Fire()
    end
    return 0
end
_G.__workflowTest={selectButton=selectButton,confirmButton=confirmButton,stage=stage}
'''

DRIVER=r'''
local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
assert(guide,"guided workflow UI missing")
local controls={}
for _,item in ipairs(guide:GetDescendants()) do controls[item.Name]=item end
assert(controls.StartGuidedWorkflow and controls.StopGuidedWorkflow and controls.CloseGuidedWorkflow,
    "guided workflow controls missing")
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==2 and _G.__workflowTest.stage.Value==2,
    "two-step guided workflow did not observe both user activations")
assert(table.concat(_G.__workflowOrder,",")=="Select,Confirm","guided workflow order drifted")
assert(_G.__workflowHighlightCount==2,"exact step highlights were not observed")
local completed=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"causality and gameplay remain unverified",1,true) then completed=true end
end
assert(completed,"completion limitation was not displayed")
assert(_G.__workflowTest.selectButton:FindFirstChild("LycolesGuidedHighlight")==nil,
    "first step highlight leaked")
assert(_G.__workflowTest.confirmButton:FindFirstChild("LycolesGuidedHighlight")==nil,
    "second step highlight leaked")
_G.__workflowTest.confirmButton.Text="Drifted"
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==3 and _G.__workflowTest.stage.Value==3,
    "metadata drift should stop after the still-valid first step")
local drifted=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"prerequisites drifted at step 2",1,true) then drifted=true end
end
assert(drifted,"step-specific metadata drift was not reported")
controls.CloseGuidedWorkflow.Activated:Fire()
assert(playerGui:FindFirstChild("LycolesGuidedWorkflow")==nil,"guided workflow UI did not close")
print("LYCOLES_GUIDED_WORKFLOW|PASS|2|1|1")
'''

def _identity(name):
    return [{"name":"PlayerGui","className":"PlayerGui","ordinal":1},
        {"name":"HUD","className":"ScreenGui","ordinal":1},
        {"name":name,"className":"TextButton","ordinal":1}]

def _step(name,sequence):
    return {"sequence":sequence,"transactionOrder":sequence,"observedSequence":sequence,
        "targetPath":"PlayerGui.HUD."+name,"targetLabel":name,
        "controlType":"GuiButton.Activated","kind":"guided-gui-activation-trial",
        "pathIdentity":_identity(name),"prerequisiteMetadata":{
            "controlClass":"TextButton","text":name,"visible":True,"active":True,
            "selectable":True,"autoButtonColor":True,"interactable":True,
            "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
            "effectiveVisible":True},"selectedOutcome":{"key":"Data.Stage","change":"increased",
                "stateIdentity":[{"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Stage","className":"IntValue","ordinal":1}],
                "observedBefore":sequence-1,"observedAfter":sequence},
        "manualActivationRequired":True,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False}

def workflow(place_id):
    claims={field:False for field in ("sourceAuthenticityVerified","causalityProven",
        "serverAuthorityVerified","runtimeVerified","gameplayVerified","actionOutcomesVerified")}
    steps=[_step("Select",1),_step("Confirm",2)]
    return {"schemaVersion":"114.generated-workflow-plan.1","placeId":place_id,
        "scanId":"controlled-guided-workflow","claims":claims,"workflowCandidates":[{
            "id":"controlled-guided-flow","transactionId":"controlled-transaction",
            "steps":steps,"stepCount":2,
            "unmappedLinkedEvents":0,"exactOrderObserved":True,
            "allStepsGenerationReady":True,"operatorStartRequired":True,
            "manualGuiActivationRequired":True,"guidedTrialGenerationReady":True,
            "automaticallyExecutable":False,"executionReady":False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False}]}

def execute(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    generated=render(workflow(place_id))
    source=STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+generated+"\n"+DRIVER
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_GUIDED_WORKFLOW|PASS|2|1|1":
        raise ControlledExecutionError("invalid controlled guided workflow transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"orderedStepsObserved":2,"exactHighlightsObserved":2,
        "metadataDriftRejected":True,"normalUserActivationEventsUsed":True,
        "automaticGuiActivationUsed":False,"robloxRuntimeVerified":False,
        "serverAuthorityVerified":False,"causalityProven":False,
        "gameplayVerified":False,"transcript":stdout.strip()}

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
