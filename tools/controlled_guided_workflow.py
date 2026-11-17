#!/usr/bin/env python3
"""Execute a guided GUI workflow in bounded Roblox stubs; not live verification."""
import json
from pathlib import Path

from controlled_admin_commands import STUBS
from controlled_luau_v108 import ControlledExecutionError,run_bounded_program
from generate_guided_workflow import render

SCHEMA="115.controlled-guided-workflow.1"

SETUP=r'''
local previousGetService=game.GetService
local controlledHttpService={}
function controlledHttpService:GenerateGUID() return "controlled-guided-session" end
function controlledHttpService:JSONEncode() return "{}" end
function game:GetService(name)
    if name=="HttpService" then return controlledHttpService end
    return previousGetService(self,name)
end
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
local feedback=_G.LycolesGuidedWorkflowFeedback
assert(feedback and feedback.schemaVersion=="115.guided-workflow-feedback.1",
    "guided feedback schema missing")
assert(#feedback.entries==2 and feedback.entries[1].runId==1 and feedback.entries[1].stepSequence==1
    and feedback.entries[2].stepSequence==2,"complete run feedback order drifted")
assert(feedback.entries[1].status=="expected-change-observed"
    and feedback.entries[2].status=="expected-change-observed",
    "complete run feedback statuses drifted")
assert(feedback.claims.runtimeVerified==false and feedback.claims.gameplayVerified==false
    and feedback.claims.causalityProven==false,"feedback claims were upgraded")
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
_G.__workflowTest.stage.Value=0
_G.__workflowTest.confirmButton.Text="Drifted"
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==3 and _G.__workflowTest.stage.Value==1,
    "metadata drift should stop after the still-valid first step")
local drifted=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"prerequisites drifted at step 2",1,true) then drifted=true end
end
assert(drifted,"step-specific metadata drift was not reported")
assert(#feedback.entries==4 and feedback.entries[3].runId==2
    and feedback.entries[3].status=="expected-change-observed"
    and feedback.entries[4].stepSequence==2 and feedback.entries[4].status=="metadata-drift",
    "failed run feedback contract drifted")
_G.__workflowTest.confirmButton.Text="Confirm"
_G.__workflowTest.stage.Value=9
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==3 and _G.__workflowTest.stage.Value==9,
    "entry-state drift should stop before activation")
local stateDrifted=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"state prerequisite drifted at step 1",1,true) then stateDrifted=true end
end
assert(stateDrifted,"step-specific state prerequisite drift was not reported")
assert(#feedback.entries==5 and feedback.entries[5].stepSequence==1
    and feedback.entries[5].status=="metadata-drift",
    "state prerequisite drift feedback missing")
controls.CloseGuidedWorkflow.Activated:Fire()
assert(playerGui:FindFirstChild("LycolesGuidedWorkflow")==nil,"guided workflow UI did not close")
print("LYCOLES_GUIDED_WORKFLOW|PASS|2|1|1")
'''

CANCEL_WAIT=r'''
_G.__cancelWorkflow=true
task.wait=function()
    local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
    if _G.__workflowTest.selectButton:FindFirstChild("LycolesGuidedHighlight") then
        if _G.__cancelWorkflow and guide then
            for _,item in ipairs(guide:GetDescendants()) do
                if item.Name=="StopGuidedWorkflow" then _G.__cancelWorkflow=false;item.Activated:Fire();return 0 end
            end
        end
        _G.__workflowHighlightCount+=1;_G.__workflowTest.selectButton.Activated:Fire()
    elseif _G.__workflowTest.confirmButton:FindFirstChild("LycolesGuidedHighlight") then
        _G.__workflowHighlightCount+=1;_G.__workflowTest.confirmButton.Activated:Fire()
    end
    return 0
end
'''

CANCEL_DRIVER=r'''
local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
assert(guide,"guided workflow UI missing")
local controls={}
for _,item in ipairs(guide:GetDescendants()) do controls[item.Name]=item end
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==0 and _G.__workflowTest.stage.Value==0,
    "cancelled workflow activated a control")
assert(_G.__workflowTest.selectButton:FindFirstChild("LycolesGuidedHighlight")==nil,
    "cancelled workflow leaked its highlight")
local stopped=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"Stopped by user",1,true) then stopped=true end
end
assert(stopped,"user cancellation was not reported")
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==2 and _G.__workflowTest.stage.Value==2,
    "workflow did not recover after cancellation")
local feedback=_G.LycolesGuidedWorkflowFeedback
assert(#feedback.entries==2 and feedback.entries[1].runId==3
    and feedback.entries[1].stepSequence==1 and feedback.entries[2].stepSequence==2,
    "recovered workflow feedback order drifted")
assert(feedback.entries[1].status=="expected-change-observed"
    and feedback.entries[2].status=="expected-change-observed",
    "recovered workflow observations missing")
for _=1,3 do
    _G.__workflowTest.stage.Value=0
    controls.StartGuidedWorkflow.Activated:Fire()
end
assert(_G.__workflowClicks==8 and #feedback.entries==8,
    "bounded retry attempts did not complete exactly five starts")
_G.__workflowTest.stage.Value=0
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==8 and _G.__workflowTest.stage.Value==0 and #feedback.entries==8,
    "sixth workflow start exceeded the bounded retry limit")
local retryLimited=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"bounded retry limit reached",1,true) then retryLimited=true end
end
assert(retryLimited,"bounded retry limit was not reported")
controls.CloseGuidedWorkflow.Activated:Fire()
assert(playerGui:FindFirstChild("LycolesGuidedWorkflow")==nil,"recovered workflow UI did not close")
print("LYCOLES_GUIDED_CANCEL_RECOVERY|PASS|5|8")
'''

REPEAT_DRIVER=r'''
local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
assert(guide,"guided workflow UI missing")
local controls={}
for _,item in ipairs(guide:GetDescendants()) do controls[item.Name]=item end
assert(controls.RepeatGuidedWorkflow,"bounded repeat control missing")
controls.RepeatGuidedWorkflow.Activated:Fire()
assert(controls.RepeatGuidedWorkflow.Text=="REPEAT: ON","bounded repeat did not arm")
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==10 and _G.__workflowTest.stage.Value==10,
    "bounded repeat did not execute exactly five two-step sequences")
assert(table.concat(_G.__workflowOrder,",")==
    "Select,Confirm,Select,Confirm,Select,Confirm,Select,Confirm,Select,Confirm",
    "bounded repeat order drifted")
local feedback=_G.LycolesGuidedWorkflowFeedback
assert(#feedback.entries==10,"bounded repeat feedback count drifted")
for index,entry in ipairs(feedback.entries) do
    assert(entry.runId==math.ceil(index/2),"bounded repeat run identity drifted")
    assert(entry.stepSequence==(index-1)%2+1,"bounded repeat step identity drifted")
    assert(entry.status=="expected-change-observed","bounded repeat outcome missing")
end
local bounded=false
for _,item in ipairs(guide:GetDescendants()) do
    if item.ClassName=="TextLabel" and type(item.Text)=="string"
        and string.find(item.Text,"bounded five-sequence limit",1,true) then bounded=true end
end
assert(bounded,"bounded repeat limit was not reported")
assert(feedback.claims.runtimeVerified==false and feedback.claims.gameplayVerified==false
    and feedback.claims.causalityProven==false,"bounded repeat claims were upgraded")
controls.CloseGuidedWorkflow.Activated:Fire()
print("LYCOLES_GUIDED_REPEAT|PASS|5|10")
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
        "metadataDriftRejected":True,"statePrerequisiteDriftRejected":True,
        "normalUserActivationEventsUsed":True,"feedbackRecordsObserved":5,"feedbackPlanBound":True,
        "automaticGuiActivationUsed":False,"robloxRuntimeVerified":False,
        "serverAuthorityVerified":False,"causalityProven":False,
        "gameplayVerified":False,"transcript":stdout.strip()}


def execute_cancel_recovery(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    generated=render(workflow(place_id))
    source=(STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+CANCEL_WAIT
        +"\n"+generated+"\n"+CANCEL_DRIVER)
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_GUIDED_CANCEL_RECOVERY|PASS|5|8":
        raise ControlledExecutionError("invalid controlled cancellation recovery transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"cancelledBeforeActivation":True,
        "activeHighlightCleaned":True,"recoveryRunCompleted":True,
        "boundedRunAttempts":5,"retryLimitRejected":True,
        "orderedStepsObserved":2,"feedbackRecordsObserved":8,"feedbackPlanBound":True,
        "robloxRuntimeVerified":False,"serverAuthorityVerified":False,
        "causalityProven":False,"gameplayVerified":False,"transcript":stdout.strip()}

def execute_repeat(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    generated=render(workflow(place_id))
    source=STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+generated+"\n"+REPEAT_DRIVER
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_GUIDED_REPEAT|PASS|5|10":
        raise ControlledExecutionError("invalid controlled guided repeat transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"boundedSequencesObserved":5,
        "orderedStepsObserved":10,"feedbackRecordsObserved":10,
        "stateContinuityRequired":True,"retryLimitRejected":True,
        "robloxRuntimeVerified":False,"serverAuthorityVerified":False,
        "causalityProven":False,"gameplayVerified":False,"transcript":stdout.strip()}


MIXED_SETUP=r'''
local world=newInstance("Workspace","Workspace");world.CurrentCamera=workspace.CurrentCamera;workspace=world
local backpack=newInstance("Backpack","Backpack");backpack.Parent=player
local humanoid=player.Character:FindFirstChildOfClass("Humanoid")
function humanoid:EquipTool(tool) tool.Parent=player.Character end
local tool=newInstance("Tool","Sword");tool.ToolTip="Train";tool.RequiresHandle=true
tool.CanBeDropped=false;tool.Enabled=true;tool.ManualActivationOnly=false;tool.Parent=backpack
local stage=_G.__workflowTest.stage
_G.__mixedToolActivations=0;_G.__mixedPromptActivations=0
function tool:Activate() _G.__mixedToolActivations+=1;stage.Value+=1 end
local shop=newInstance("Model","Shop");shop.Parent=workspace
local door=newInstance("Part","Door");door.CFrame=CFrame.new(1,2,3);door.Position=Vector3.new(1,2,3);door.Parent=shop
local prompt=newInstance("ProximityPrompt","Prompt");prompt.ActionText="Open";prompt.ObjectText="Shop Door"
prompt.Enabled=true;prompt.HoldDuration=0;prompt.MaxActivationDistance=10
prompt.KeyboardKeyCode={Name="E"};prompt.GamepadKeyCode={Name="ButtonX"};prompt.Parent=door
function fireproximityprompt(target)
    assert(target==prompt,"unexpected prompt target")
    _G.__mixedPromptActivations+=1;stage.Value+=1
end
task.spawn=function(callback) callback() end
task.wait=function() return 0 end
_G.__mixedWorkflowTest={stage=stage,prompt=prompt}
'''

MIXED_DRIVER=r'''
local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
assert(guide,"mixed workflow UI missing")
local controls={}
for _,item in ipairs(guide:GetDescendants()) do controls[item.Name]=item end
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__mixedToolActivations==1 and _G.__mixedPromptActivations==1,
    "mixed workflow did not activate Tool then Prompt")
assert(_G.__mixedWorkflowTest.stage.Value==2,"mixed workflow outcomes were not observed in order")
local feedback=_G.LycolesGuidedWorkflowFeedback
assert(#feedback.entries==2 and feedback.entries[1].stepSequence==1
    and feedback.entries[2].stepSequence==2,"mixed feedback order drifted")
assert(feedback.entries[1].status=="expected-change-observed"
    and feedback.entries[2].status=="expected-change-observed","mixed feedback outcomes missing")
assert(feedback.claims.runtimeVerified==false and feedback.claims.gameplayVerified==false
    and feedback.claims.causalityProven==false,"mixed feedback claims were upgraded")
_G.__mixedWorkflowTest.stage.Value=0
_G.__mixedWorkflowTest.prompt.ActionText="Drifted"
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__mixedToolActivations==2 and _G.__mixedPromptActivations==1
    and _G.__mixedWorkflowTest.stage.Value==1,"Prompt drift did not stop after valid Tool step")
assert(#feedback.entries==4 and feedback.entries[3].status=="expected-change-observed"
    and feedback.entries[4].status=="metadata-drift","Prompt drift feedback missing")
controls.CloseGuidedWorkflow.Activated:Fire()
print("LYCOLES_MIXED_WORKFLOW|PASS|2|2|1")
'''

THREE_KIND_WAIT=r'''
task.wait=function()
    if _G.__workflowTest.selectButton:FindFirstChild("LycolesGuidedHighlight") then
        _G.__workflowHighlightCount+=1;_G.__workflowTest.selectButton.Activated:Fire()
    end
    return 0
end
'''

THREE_KIND_DRIVER=r'''
local guide=playerGui:FindFirstChild("LycolesGuidedWorkflow")
assert(guide,"three-kind workflow UI missing")
local controls={}
for _,item in ipairs(guide:GetDescendants()) do controls[item.Name]=item end
controls.StartGuidedWorkflow.Activated:Fire()
assert(_G.__workflowClicks==1 and _G.__workflowHighlightCount==1,
    "GUI step did not use one normal activation event")
assert(_G.__mixedToolActivations==1 and _G.__mixedPromptActivations==1
    and _G.__workflowTest.stage.Value==3,"three-kind sequence did not complete in order")
local feedback=_G.LycolesGuidedWorkflowFeedback
assert(#feedback.entries==3,"three-kind feedback count drifted")
for index=1,3 do
    assert(feedback.entries[index].stepSequence==index
        and feedback.entries[index].status=="expected-change-observed",
        "three-kind feedback order or result drifted")
end
controls.CloseGuidedWorkflow.Activated:Fire()
print("LYCOLES_THREE_KIND_WORKFLOW|PASS|3|1|1|1")
'''


def _mixed_step(kind,sequence):
    outcome={"key":"Data.Stage","change":"increased","stateIdentity":[
        {"name":"Data","className":"Folder","ordinal":1},
        {"name":"Stage","className":"IntValue","ordinal":1}],
        "observedBefore":sequence-1,"observedAfter":sequence}
    common={"sequence":sequence,"transactionOrder":sequence,"observedSequence":sequence,
        "selectedOutcome":outcome,"manualActivationRequired":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False}
    if kind=="tool":
        common.update(targetPath="LocalPlayer.Backpack.Sword",targetLabel="Sword",
            controlType="Tool.Activated",kind="official-tool-activation-trial",
            activationMode="official-tool-activate",pathIdentity=[
                {"name":"LocalPlayer","className":"Player","ordinal":1},
                {"name":"Backpack","className":"Backpack","ordinal":1},
                {"name":"Sword","className":"Tool","ordinal":1}],
            prerequisiteMetadata={"tooltip":"Train","requiresHandle":True,
                "canBeDropped":False,"enabled":True,"manualActivationOnly":False})
    else:
        common.update(targetPath="Workspace.Shop.Door.Prompt",targetLabel="Shop Door",
            controlType="ProximityPrompt.Triggered",kind="proximity-prompt-trial",
            activationMode="executor-fireproximityprompt",pathIdentity=[
                {"name":"Workspace","className":"Workspace","ordinal":1},
                {"name":"Shop","className":"Model","ordinal":1},
                {"name":"Door","className":"Part","ordinal":1},
                {"name":"Prompt","className":"ProximityPrompt","ordinal":1}],
            prerequisiteMetadata={"actionText":"Open","objectText":"Shop Door","enabled":True,
                "holdDuration":0,"maxActivationDistance":10,"keyboardKeyCode":"E",
                "gamepadKeyCode":"ButtonX","anchorPath":"Workspace.Shop.Door",
                "anchorPosition":{"x":1,"y":2,"z":3}})
    return common


def mixed_workflow(place_id):
    claims={field:False for field in ("sourceAuthenticityVerified","causalityProven",
        "serverAuthorityVerified","runtimeVerified","gameplayVerified","actionOutcomesVerified")}
    steps=[_mixed_step("tool",1),_mixed_step("prompt",2)]
    return {"schemaVersion":"114.generated-workflow-plan.1","placeId":place_id,
        "scanId":"controlled-mixed-workflow","claims":claims,"workflowCandidates":[{
            "id":"controlled-mixed-flow","transactionId":"controlled-mixed-transaction",
            "steps":steps,"stepCount":2,"unmappedLinkedEvents":0,"exactOrderObserved":True,
            "allStepsGenerationReady":True,"operatorStartRequired":True,
            "manualGuiActivationRequired":False,"guidedTrialGenerationReady":True,
            "executionMode":"bounded-automatic","automaticallyExecutable":True,
            "executionReady":True,"runtimeVerified":False,"gameplayVerified":False,
            "causalityProven":False}]}


def execute_mixed(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    generated=render(mixed_workflow(place_id))
    source=STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+MIXED_SETUP+"\n"+generated+"\n"+MIXED_DRIVER
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_MIXED_WORKFLOW|PASS|2|2|1":
        raise ControlledExecutionError("invalid controlled mixed workflow transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"orderedStepsObserved":2,"toolActivationsObserved":2,
        "promptActivationsObserved":1,"expectedChangesObserved":3,"metadataDriftRejected":True,
        "feedbackPlanBound":True,
        "normalUserActivationEventsUsed":False,"robloxRuntimeVerified":False,
        "serverAuthorityVerified":False,"causalityProven":False,"gameplayVerified":False,
        "transcript":stdout.strip()}


def three_kind_workflow(place_id):
    document=mixed_workflow(place_id);candidate=document["workflowCandidates"][0]
    candidate.update(id="controlled-three-kind-flow",transactionId="controlled-three-kind-transaction",
        manualGuiActivationRequired=True,executionMode="mixed-guided",
        automaticallyExecutable=False)
    candidate["steps"]=[_step("Select",1),_mixed_step("tool",2),_mixed_step("prompt",3)]
    candidate["stepCount"]=3
    return document


def execute_three_kind(place_id,luau_binary,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<1:raise ValueError("invalid place ID")
    generated=render(three_kind_workflow(place_id))
    source=(STUBS.replace("__RUNTIME_PLACE",str(place_id),1)+"\n"+SETUP+"\n"+MIXED_SETUP
        +"\n"+THREE_KIND_WAIT+"\n"+generated+"\n"+THREE_KIND_DRIVER)
    stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    if stdout.strip()!="LYCOLES_THREE_KIND_WORKFLOW|PASS|3|1|1|1":
        raise ControlledExecutionError("invalid controlled three-kind workflow transcript")
    return {"schemaVersion":SCHEMA,"placeId":place_id,"luauExecuted":True,
        "simulatedEnvironment":True,"orderedStepsObserved":3,"guiActivationsObserved":1,
        "toolActivationsObserved":1,"promptActivationsObserved":1,
        "feedbackRecordsObserved":3,"feedbackPlanBound":True,
        "normalUserActivationEventsUsed":True,"automaticGuiActivationUsed":False,
        "robloxRuntimeVerified":False,"serverAuthorityVerified":False,
        "causalityProven":False,"gameplayVerified":False,"transcript":stdout.strip()}


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
