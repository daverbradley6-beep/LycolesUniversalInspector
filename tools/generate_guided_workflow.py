#!/usr/bin/env python3
"""Generate a manual-only guided GUI workflow trial from exact linked evidence."""
import hashlib
import json
import math

FALSE_CLAIMS=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified")
REQUIRED_BOOL_METADATA=("visible","active","selectable","autoButtonColor",
    "ancestorVisible","screenEnabled","withinScrollingBounds","effectiveVisible")
BOOL_METADATA=REQUIRED_BOOL_METADATA+("interactable",)
AVAILABLE_TRUE=("visible","active","ancestorVisible","screenEnabled",
    "withinScrollingBounds","effectiveVisible")

def _text(value,limit):
    return isinstance(value,str) and 1<=len(value)<=limit and all(ord(c)>=32 and ord(c)!=127 for c in value)

def _identity(value):
    if not isinstance(value,list) or not 1<=len(value)<=21:return False
    return all(isinstance(item,dict) and set(item)=={"name","className","ordinal"}
        and _text(item["name"],100) and _text(item["className"],100)
        and type(item["ordinal"]) is int and 1<=item["ordinal"]<=10_000 for item in value)

def _scalar(value):
    return (value is None or type(value) in (str,bool,int)
        or type(value) is float and math.isfinite(value))


def digest(document):
    raw=json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _transition(before,after,change):
    if not _scalar(before) or not _scalar(after):return False
    if change=="increased":
        return type(before) in (int,float) and type(after) in (int,float) and after>before
    if change=="decreased":
        return type(before) in (int,float) and type(after) in (int,float) and after<before
    return before!=after


def _step(value):
    path_identity=value.get("pathIdentity") if isinstance(value,dict) else None
    if (not isinstance(value,dict) or value.get("kind")!="guided-gui-activation-trial"
            or value.get("manualActivationRequired") is not True
            or value.get("runtimeVerified") is not False or value.get("gameplayVerified") is not False
            or value.get("causalityProven") is not False or not _text(value.get("targetPath"),400)
            or not _text(value.get("targetLabel"),120) or value.get("controlType")!="GuiButton.Activated"
            or type(value.get("sequence")) is not int or value["sequence"]<1
            or type(value.get("transactionOrder")) is not int or value["transactionOrder"]<1
            or type(value.get("observedSequence")) is not int or value["observedSequence"]<1
            or not _identity(path_identity) or path_identity[0]!={"name":"PlayerGui",
                "className":"PlayerGui","ordinal":1}):
        raise ValueError("Malformed guided workflow step")
    metadata=value.get("prerequisiteMetadata");outcome=value.get("selectedOutcome")
    allowed={"controlClass","text",*BOOL_METADATA}
    text=metadata.get("text") if isinstance(metadata,dict) else None
    state_identity=outcome.get("stateIdentity") if isinstance(outcome,dict) else None
    change=outcome.get("change") if isinstance(outcome,dict) else None
    if (not isinstance(metadata,dict) or set(metadata)-allowed
            or not {"controlClass","text",*REQUIRED_BOOL_METADATA}.issubset(metadata)
            or metadata.get("controlClass") not in ("TextButton","ImageButton")
            or path_identity[-1]["className"]!=metadata.get("controlClass")
            or not isinstance(text,str) or len(text)>100
            or any(ord(character)<32 or ord(character)==127 for character in text)
            or any(type(metadata.get(key)) is not bool for key in REQUIRED_BOOL_METADATA)
            or ("interactable" in metadata and type(metadata["interactable"]) is not bool)
            or not all(metadata[key] for key in AVAILABLE_TRUE)
            or metadata.get("interactable") is False
            or not isinstance(outcome,dict) or not _text(outcome.get("key"),200)
            or change not in ("increased","decreased","changed")
            or not _identity(state_identity) or state_identity[0]["name"] not in ("leaderstats","Data")
            or ".".join(item["name"] for item in state_identity)!=outcome["key"]
            or "observedBefore" not in outcome or "observedAfter" not in outcome
            or not _transition(outcome["observedBefore"],outcome["observedAfter"],change)):
        raise ValueError("Malformed guided workflow step contract")
    return value

def validate(document):
    if (not isinstance(document,dict) or document.get("schemaVersion")!="114.generated-workflow-plan.1"
            or type(document.get("placeId")) is not int or document["placeId"]<1
            or not _text(document.get("scanId"),128)):
        raise ValueError("Expected identified generated workflow plan")
    claims=document.get("claims")
    if not isinstance(claims,dict) or any(claims.get(field) is not False for field in FALSE_CLAIMS):
        raise ValueError("Workflow plan claims must remain false")
    candidates=document.get("workflowCandidates")
    if not isinstance(candidates,list) or len(candidates)>64:raise ValueError("Malformed workflow candidates")
    eligible=[]
    for item in candidates:
        if not isinstance(item,dict):raise ValueError("Malformed workflow candidate")
        if item.get("guidedTrialGenerationReady") is not True:continue
        steps=item.get("steps")
        if (not _text(item.get("id"),80) or not _text(item.get("transactionId"),128)
                or not isinstance(steps,list) or not 2<=len(steps)<=16
                or item.get("stepCount")!=len(steps) or item.get("unmappedLinkedEvents")!=0
                or item.get("exactOrderObserved") is not True
                or item.get("allStepsGenerationReady") is not True
                or item.get("manualGuiActivationRequired") is not True
                or item.get("operatorStartRequired") is not True
                or item.get("automaticallyExecutable") is not False
                or item.get("executionReady") is not False or item.get("runtimeVerified") is not False
                or item.get("gameplayVerified") is not False or item.get("causalityProven") is not False):
            raise ValueError("Malformed guided workflow candidate")
        normalized=[_step(step) for step in steps]
        expected_order=list(range(1,len(normalized)+1))
        observed=[step["observedSequence"] for step in normalized]
        if ([step["sequence"] for step in normalized]!=expected_order
                or [step["transactionOrder"] for step in normalized]!=expected_order
                or observed!=sorted(observed) or len(set(observed))!=len(observed)):
            raise ValueError("Malformed guided workflow step order")
        eligible.append(item)
    eligible.sort(key=lambda item:item["id"])
    return eligible

def _lua(value):
    return json.dumps(value,ensure_ascii=False).replace("\\/","/")

def _identity_lua(value):
    return "{"+",".join("{name="+_lua(item["name"])+",className="+_lua(item["className"])
        +",ordinal="+str(item["ordinal"])+"}" for item in value)+"}"

def _step_lua(step):
    metadata=step["prerequisiteMetadata"];outcome=step["selectedOutcome"]
    metadata_lua="{"+",".join(["controlClass="+_lua(metadata["controlClass"]),
        "text="+_lua(metadata["text"])] + [key+"="+str(metadata[key]).lower()
            for key in BOOL_METADATA if key in metadata])+"}"
    return ("{label="+_lua(step["targetLabel"])+",path="+_lua(step["targetPath"])
        +",identity="+_identity_lua(step["pathIdentity"])+",metadata="+metadata_lua
        +",outcome={key="+_lua(outcome["key"])+",change="+_lua(outcome["change"])
        +",identity="+_identity_lua(outcome["stateIdentity"])+"}}")

def validate_source(source,place_id):
    if not isinstance(source,str) or not 1<=len(source)<=500_000:
        raise ValueError("Guided workflow source missing or oversized")
    required=(f"assert(game.PlaceId == {place_id}",
        "button.Activated:Connect(function() activated=true end)",
        "for index,step in ipairs(steps) do","normal user activation",
        "No GUI event is synthesized","115.guided-workflow-feedback.1",
        "_G.LycolesGuidedWorkflowFeedback=feedback","recordFeedback(",
        "HttpService:JSONEncode(feedback)","actionOutcomesVerified=false")
    for token in required:
        if token not in source:raise ValueError("Missing guided workflow safeguard: "+token)
    banned=("firesignal","virtualinput","virtualuser","fireclickdetector",
        "fireproximityprompt","mouse1click","mouse1press",":Activate(","FireServer(",
        "InvokeServer(","loadstring(","getrawmetatable(","hookmetamethod(",
        "setclipboard(","PostAsync(","RequestAsync(","http_request(","syn.request(")
    lowered=source.lower()
    for token in banned:
        if token.lower() in lowered:raise ValueError("Forbidden guided workflow operation: "+token)
    return {"placeGuard":True,"manualActivationRequired":True,
        "automaticActivationFound":False,"unsafeOperationsFound":False,
        "note":"Structural safety checks only; live Roblox runtime and gameplay are unverified"}

def render(document):
    candidates=validate(document)
    if not candidates:return None
    candidate=candidates[0]
    steps="{\n"+",\n".join("  "+_step_lua(step) for step in candidate["steps"])+"\n}"
    source=f'''-- Lycoles guided GUI workflow trial; static-generated, runtime/gameplay unverified.
-- Every GUI step requires normal user activation. No GUI event is synthesized.
assert(game.PlaceId == {document["placeId"]}, "Wrong place for generated workflow trial")
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
local player=Players.LocalPlayer
local steps={steps}
local feedbackSequence=0
local feedback={{schemaVersion="115.guided-workflow-feedback.1",placeId={document["placeId"]},
  scanId={_lua(document["scanId"])},workflowPlanSHA256={_lua(digest(document))},
  candidateId={_lua(candidate["id"])},sessionId=HttpService:GenerateGUID(false),entries={{}},
  claims={{sourceAuthenticityVerified=false,causalityProven=false,serverAuthorityVerified=false,
    runtimeVerified=false,gameplayVerified=false,actionOutcomesVerified=false}}}}
_G.LycolesGuidedWorkflowFeedback=feedback
local running=false
local runId=0
local activeConnection=nil
local activeStroke=nil
local activationTimeoutSeconds=15
local outcomeTimeoutSeconds=5

local function clearActive()
  if activeConnection then activeConnection:Disconnect(); activeConnection=nil end
  if activeStroke then activeStroke:Destroy(); activeStroke=nil end
end
local function resolve(root,identity)
  if not root or root.Name~=identity[1].name or not root:IsA(identity[1].className) then return nil end
  local current=root
  for index=2,#identity do
    local wanted=identity[index]
    local ordinal=0
    local found=nil
    for _,child in ipairs(current:GetChildren()) do
      if child.Name==wanted.name and child:IsA(wanted.className) then
        ordinal=ordinal+1
        if ordinal==wanted.ordinal then found=child;break end
      end
    end
    if not found then return nil end
    current=found
  end
  return current
end
local function resolveButton(identity)
  return resolve(player:FindFirstChildOfClass("PlayerGui"),identity)
end
local function resolveState(identity)
  return resolve(player:FindFirstChild(identity[1].name),identity)
end
local function currentMetadata(button)
  local visible=button.Visible
  local ancestorVisible,screenEnabled,withinScrollingBounds=true,true,true
  local current=button.Parent
  while current and not current:IsA("PlayerGui") do
    if current:IsA("GuiObject") then ancestorVisible=ancestorVisible and current.Visible end
    if current:IsA("ScreenGui") then screenEnabled=screenEnabled and current.Enabled end
    if current:IsA("ScrollingFrame") then
      local p,s,bp,bs=button.AbsolutePosition,button.AbsoluteSize,current.AbsolutePosition,current.AbsoluteSize
      withinScrollingBounds=withinScrollingBounds and p.X+s.X>=bp.X and p.X<=bp.X+bs.X
        and p.Y+s.Y>=bp.Y and p.Y<=bp.Y+bs.Y
    end
    current=current.Parent
  end
  local interactable=true
  pcall(function() interactable=button.Interactable end)
  return {{controlClass=button.ClassName,text=button:IsA("TextButton") and button.Text or "",
    visible=button.Visible,active=button.Active,selectable=button.Selectable,
    autoButtonColor=button.AutoButtonColor,interactable=interactable,
    ancestorVisible=ancestorVisible,screenEnabled=screenEnabled,
    withinScrollingBounds=withinScrollingBounds,
    effectiveVisible=visible and ancestorVisible and screenEnabled}}
end
local function sameMetadata(actual,expected)
  for key,value in pairs(expected) do if actual[key]~=value then return false end end
  return true
end
local function outcomeReached(change,before,after)
  if change=="changed" then return after~=before end
  if type(before)~="number" or type(after)~="number" then return false end
  return (change=="increased" and after>before) or (change=="decreased" and after<before)
end
local function recordFeedback(thisRun,index,step,before,after,activated,observed,resultStatus,message)
  feedbackSequence=feedbackSequence+1
  table.insert(feedback.entries,{{sequence=feedbackSequence,runId=thisRun,stepSequence=index,
    targetPath=step.path,outcomeKey=step.outcome.key,expected=step.outcome.change,
    before=before,after=after,activationObserved=activated==true,
    observedExpectedChange=observed==true,status=resultStatus,
    message=tostring(message or ""):sub(1,240),observedAtUnix=os.time()}})
end

local gui=Instance.new("ScreenGui");gui.Name="LycolesGuidedWorkflow";gui.ResetOnSpawn=false
gui.Parent=player:WaitForChild("PlayerGui")
local frame=Instance.new("Frame");frame.Size=UDim2.fromOffset(460,230);frame.Position=UDim2.new(.5,-230,.5,-115)
frame.BackgroundColor3=Color3.fromRGB(18,22,32);frame.Active=true;frame.Draggable=true;frame.Parent=gui
local title=Instance.new("TextLabel");title.Size=UDim2.new(1,-20,0,34);title.Position=UDim2.fromOffset(10,8)
title.BackgroundTransparency=1;title.TextColor3=Color3.fromRGB(235,240,255);title.Text={_lua("Guided workflow ("+candidate["id"]+")")};title.Parent=frame
local status=Instance.new("TextLabel");status.Size=UDim2.new(1,-20,0,72);status.Position=UDim2.fromOffset(10,44)
status.BackgroundTransparency=1;status.TextWrapped=true;status.TextColor3=Color3.fromRGB(205,214,235)
status.Text="Ready. You must click every highlighted game control normally.";status.Parent=frame
local function makeButton(name,text,x)
  local button=Instance.new("TextButton");button.Name=name;button.Size=UDim2.fromOffset(135,38)
  button.Position=UDim2.fromOffset(x,134);button.Text=text;button.Parent=frame;return button
end
local startButton=makeButton("StartGuidedWorkflow","START",10)
local stopButton=makeButton("StopGuidedWorkflow","STOP",162)
local closeButton=makeButton("CloseGuidedWorkflow","CLOSE",314)
local feedbackButton=Instance.new("TextButton");feedbackButton.Name="ExportGuidedWorkflowFeedback"
feedbackButton.Size=UDim2.new(1,-20,0,34);feedbackButton.Position=UDim2.fromOffset(10,184)
feedbackButton.Text="PRINT DIGEST-BOUND FEEDBACK JSON";feedbackButton.Parent=frame
feedbackButton.Activated:Connect(function()
  local ok,payload=pcall(function() return HttpService:JSONEncode(feedback) end)
  if ok then print("LYCOLES_GUIDED_WORKFLOW_FEEDBACK|"..payload)
    status.Text="Feedback JSON printed locally; all verification claims remain false."
  else status.Text="Feedback JSON encoding failed; no data was sent." end
end)
local function finish(message)
  running=false;clearActive();status.Text=message
end
local function runWorkflow()
  if running then return end
  if #feedback.entries+#steps>400 then
    finish("Stopped: feedback record limit reached; export before rerunning.");return
  end
  running=true;runId=runId+1;local thisRun=runId
  for index,step in ipairs(steps) do
    if not running or runId~=thisRun then return end
    local button=resolveButton(step.identity);local state=resolveState(step.outcome.identity)
    if not button or not button:IsA("GuiButton") or not state then
      recordFeedback(thisRun,index,step,nil,nil,false,false,"control-or-state-unavailable",
        "Exact control or state identity unavailable")
      finish("Stopped: exact control or state identity unavailable at step "..index);return
    end
    if not sameMetadata(currentMetadata(button),step.metadata) then
      recordFeedback(thisRun,index,step,nil,nil,false,false,"metadata-drift",
        "Control prerequisite metadata changed")
      finish("Stopped: control prerequisites drifted at step "..index);return
    end
    local ok,before=pcall(function() return state.Value end)
    if not ok or type(before)~="number" and type(before)~="string" and type(before)~="boolean" then
      recordFeedback(thisRun,index,step,nil,nil,false,false,"state-unreadable",
        "Selected client-visible state is not readable scalar")
      finish("Stopped: selected state is not readable scalar at step "..index);return
    end
    activeStroke=Instance.new("UIStroke");activeStroke.Name="LycolesGuidedHighlight"
    activeStroke.Color=Color3.fromRGB(255,205,50);activeStroke.Thickness=3;activeStroke.Parent=button
    local activated=false
    activeConnection=button.Activated:Connect(function() activated=true end)
    status.Text="Step "..index.."/"..#steps..": click highlighted "..step.label.." normally."
    local deadline=os.clock()+activationTimeoutSeconds
    while running and runId==thisRun and not activated and os.clock()<deadline do task.wait(.05) end
    clearActive()
    if not running or runId~=thisRun then return end
    if not activated then
      recordFeedback(thisRun,index,step,before,before,false,false,"activation-timeout",
        "Normal user activation was not observed within the bounded window")
      finish("Stopped: user activation timed out at step "..index);return
    end
    status.Text="Step "..index..": activation observed; watching selected client-visible outcome."
    local observed=false;local after=before;deadline=os.clock()+outcomeTimeoutSeconds
    while running and runId==thisRun and os.clock()<deadline do
      local read,current=pcall(function() return state.Value end)
      if read then after=current end
      if read and outcomeReached(step.outcome.change,before,current) then observed=true;break end
      task.wait(.05)
    end
    if not observed then
      recordFeedback(thisRun,index,step,before,after,true,false,"outcome-not-observed",
        "Selected client-visible direction was not observed within the bounded window")
      finish("Stopped: selected outcome not observed at step "..index);return
    end
    recordFeedback(thisRun,index,step,before,after,true,true,"expected-change-observed",
      "Selected client-visible direction observed after normal user activation")
  end
  finish("Candidate completed with client-visible observations; causality and gameplay remain unverified.")
end
startButton.Activated:Connect(function() task.spawn(runWorkflow) end)
stopButton.Activated:Connect(function() runId=runId+1;finish("Stopped by user; no verification claim.") end)
closeButton.Activated:Connect(function() runId=runId+1;running=false;clearActive();gui:Destroy() end)
'''
    validate_source(source,document["placeId"])
    return source

def main():
    import argparse,pathlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_plan");parser.add_argument("--output",required=True)
    args=parser.parse_args();document=json.loads(pathlib.Path(args.workflow_plan).read_text())
    code=render(document)
    if code is None:raise SystemExit("No guided workflow candidate is generation-ready")
    pathlib.Path(args.output).write_text(code,encoding="utf-8")

if __name__=="__main__":main()
