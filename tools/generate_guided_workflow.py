#!/usr/bin/env python3
"""Generate a bounded mixed-action workflow trial from exact linked evidence."""
import hashlib
import json
import math
import re

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



_STOP_WORDS={"a","an","and","auto","automate","automated","automatic",
    "automatically","complete","do","for","from","in","of","observed","please",
    "the","to","with","workflow","flow"}
_TOKEN_ALIASES={
    "attacking":"attack","attacked":"attack","buying":"buy",
    "claiming":"claim","claimed":"claim","collecting":"collect",
    "collected":"collect","fighting":"fight","hatching":"hatch",
    "hatched":"hatch","purchasing":"purchase","purchased":"purchase",
    "rebirthing":"rebirth","selling":"sell","sold":"sell",
    "training":"train","trained":"train","traveling":"travel",
    "travelled":"travel","travelling":"travel","upgrading":"upgrade",
    "upgraded":"upgrade",
}


def _token_forms(token):
    forms={token}
    if len(token)>4 and token.endswith("ies"):
        forms.add(token[:-3]+"y")
    if len(token)>4 and token.endswith("es"):
        forms.add(token[:-2])
    if len(token)>4 and token.endswith("s") and not token.endswith("ss"):
        forms.add(token[:-1])
    if len(token)>5 and token.endswith("ing"):
        forms.add(token[:-3])
    if len(token)>4 and token.endswith("ed"):
        forms.add(token[:-2])
    return forms


def _tokens(value):
    if not isinstance(value,str):return set()
    result=set()
    for token in re.findall(r"[a-z0-9]+",value.casefold())[:128]:
        for form in _token_forms(token):
            canonical=_TOKEN_ALIASES.get(form,form)
            if len(canonical)>=2 and canonical not in _STOP_WORDS:
                result.add(canonical)
    return result

def _selection(steps,requested_terms):
    requested=set(requested_terms);weighted={}
    for step in steps:
        for value,weight in ((step.get("targetFeature"),5),(step.get("actionCandidate"),4),
                (step.get("targetLabel"),3),(step.get("targetPath"),1),
                (step.get("selectedOutcome",{}).get("key"),1)):
            for token in _tokens(value):weighted[token]=max(weighted.get(token,0),weight)
    matched=sorted(requested&set(weighted))
    return {"requestAligned":bool(matched),"requestScore":sum(weighted[token] for token in matched),
        "matchedTerms":matched,"requestedTerms":sorted(requested)}

def _step(value):
    path_identity=value.get("pathIdentity") if isinstance(value,dict) else None
    kind=value.get("kind") if isinstance(value,dict) else None
    contracts={"guided-gui-activation-trial":("GuiButton.Activated",
            "normal-user-gui-activation",True,"PlayerGui","GuiButton"),
        "official-tool-activation-trial":("Tool.Activated",
            "official-tool-activate",False,"LocalPlayer","Tool"),
        "proximity-prompt-trial":("ProximityPrompt.Triggered",
            "executor-fireproximityprompt",False,"Workspace","ProximityPrompt")}
    contract=contracts.get(kind)
    if (not isinstance(value,dict) or contract is None
            or value.get("manualActivationRequired") is not contract[2]
            or value.get("activationMode",contract[1])!=contract[1]
            or value.get("runtimeVerified") is not False or value.get("gameplayVerified") is not False
            or value.get("causalityProven") is not False or not _text(value.get("targetPath"),400)
            or not _text(value.get("targetLabel"),120)
            or value.get("targetFeature") is not None and not _text(value.get("targetFeature"),120)
            or value.get("actionCandidate") is not None and not _text(value.get("actionCandidate"),120)
            or value.get("controlType")!=contract[0]
            or type(value.get("sequence")) is not int or value["sequence"]<1
            or type(value.get("transactionOrder")) is not int or value["transactionOrder"]<1
            or type(value.get("observedSequence")) is not int or value["observedSequence"]<1
            or not _identity(path_identity) or path_identity[0]["name"]!=contract[3]
            or path_identity[-1]["className"]!=contract[4]
                and not (contract[4]=="GuiButton" and path_identity[-1]["className"] in
                    ("TextButton","ImageButton"))):
        raise ValueError("Malformed guided workflow step")
    baseline=value.get("observationBaseline")
    baseline_valid=(baseline is None or isinstance(baseline,dict)
        and set(baseline)=={"timing","preActivationBaselineAvailable","possibleSynchronousLoss"}
        and baseline.get("timing") in ("pre-activation","activation-callback","unknown")
        and type(baseline.get("preActivationBaselineAvailable")) is bool
        and baseline["preActivationBaselineAvailable"] is (baseline["timing"]=="pre-activation")
        and type(baseline.get("possibleSynchronousLoss")) is bool
        and baseline["possibleSynchronousLoss"] is (baseline["timing"]!="pre-activation"))
    metadata=value.get("prerequisiteMetadata");outcome=value.get("selectedOutcome")
    if not baseline_valid or not isinstance(metadata,dict):
        raise ValueError("Malformed guided workflow step contract")
    if kind=="guided-gui-activation-trial":
        allowed={"controlClass","text",*BOOL_METADATA};text=metadata.get("text")
        valid_metadata=(not set(metadata)-allowed
            and {"controlClass","text",*REQUIRED_BOOL_METADATA}.issubset(metadata)
            and metadata.get("controlClass") in ("TextButton","ImageButton")
            and path_identity[-1]["className"]==metadata.get("controlClass")
            and isinstance(text,str) and len(text)<=100
            and all(ord(character)>=32 and ord(character)!=127 for character in text)
            and all(type(metadata.get(key)) is bool for key in REQUIRED_BOOL_METADATA)
            and ("interactable" not in metadata or type(metadata["interactable"]) is bool)
            and all(metadata[key] for key in AVAILABLE_TRUE)
            and metadata.get("interactable") is not False)
    elif kind=="official-tool-activation-trial":
        valid_metadata=(set(metadata)=={"tooltip","requiresHandle","canBeDropped","enabled",
                "manualActivationOnly"}
            and isinstance(metadata.get("tooltip"),str) and len(metadata["tooltip"])<=120
            and all(ord(character)>=32 and ord(character)!=127 for character in metadata["tooltip"])
            and all(type(metadata.get(key)) is bool for key in
                ("requiresHandle","canBeDropped","enabled","manualActivationOnly"))
            and metadata.get("enabled") is True)
    else:
        allowed={"actionText","objectText","enabled","holdDuration","maxActivationDistance",
            "keyboardKeyCode","gamepadKeyCode","anchorPath","anchorPosition"}
        valid_metadata=not set(metadata)-allowed
        for key in ("actionText","objectText","keyboardKeyCode","gamepadKeyCode","anchorPath"):
            valid_metadata=valid_metadata and (key not in metadata or isinstance(metadata[key],str))
        valid_metadata=valid_metadata and ("enabled" not in metadata or type(metadata["enabled"]) is bool)
        valid_metadata=valid_metadata and metadata.get("enabled") is True
        valid_metadata=valid_metadata and _text(metadata.get("anchorPath"),400)
        valid_metadata=valid_metadata and type(metadata.get("maxActivationDistance")) in (int,float)
        for key in ("holdDuration","maxActivationDistance"):
            valid_metadata=valid_metadata and (key not in metadata or type(metadata[key]) in (int,float)
                and math.isfinite(metadata[key]) and metadata[key]>=0)
        position=metadata.get("anchorPosition")
        valid_metadata=valid_metadata and (isinstance(position,dict)
            and set(position)=={"x","y","z"} and all(type(position[key]) in (int,float)
                and math.isfinite(position[key]) for key in ("x","y","z")))
    state_identity=outcome.get("stateIdentity") if isinstance(outcome,dict) else None
    change=outcome.get("change") if isinstance(outcome,dict) else None
    outcome_key=outcome.get("key") if isinstance(outcome,dict) else None
    observed_before=outcome.get("observedBefore") if isinstance(outcome,dict) else None
    entry=value.get("entryStatePrerequisite")
    entry_valid=(entry is None or isinstance(entry,dict)
        and set(entry)=={"key","value","stateIdentity","classification","causalityProven"}
        and entry.get("key")==outcome_key and entry.get("value")==observed_before
        and entry.get("stateIdentity")==state_identity and _scalar(entry.get("value"))
        and entry.get("classification")=="exact-observed-entry-state"
        and entry.get("causalityProven") is False)
    if (not valid_metadata or not entry_valid or not isinstance(outcome,dict)
            or not _text(outcome.get("key"),200)
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
        linkage=item.get("linkageSource","observed-shared-transaction")
        transaction=item.get("transactionId")
        if (linkage not in ("observed-shared-transaction","explicit-user-armed-recording")
                or str(transaction).startswith("user-recorded-") !=
                    (linkage=="explicit-user-armed-recording")):
            raise ValueError("Malformed guided workflow linkage source")
        if (not _text(item.get("id"),80) or not _text(transaction,128)
                or not isinstance(steps,list) or not 1<=len(steps)<=64
                or item.get("stepCount")!=len(steps) or item.get("unmappedLinkedEvents")!=0
                or item.get("exactOrderObserved") is not True
                or item.get("allStepsGenerationReady") is not True
                or item.get("operatorStartRequired") is not True
                or item.get("runtimeVerified") is not False
                or item.get("gameplayVerified") is not False or item.get("causalityProven") is not False):
            raise ValueError("Malformed guided workflow candidate")
        normalized=[_step(step) for step in steps]
        manual_gui=any(step["manualActivationRequired"] for step in normalized)
        execution_mode=item.get("executionMode")
        if execution_mode is None:
            if (not all(step["kind"]=="guided-gui-activation-trial" for step in normalized)
                    or item.get("manualGuiActivationRequired") is not True
                    or item.get("automaticallyExecutable") is not False
                    or item.get("executionReady") is not False):
                raise ValueError("Malformed legacy guided workflow candidate")
        elif (execution_mode!=("mixed-guided" if manual_gui else "bounded-automatic")
                or item.get("manualGuiActivationRequired") is not manual_gui
                or item.get("automaticallyExecutable") is not (not manual_gui)
                or item.get("executionReady") is not True):
            raise ValueError("Malformed guided workflow execution mode")
        selection=item.get("selection")
        if selection is not None:
            if (not isinstance(selection,dict)
                    or set(selection)!={"requestAligned","requestScore","matchedTerms","requestedTerms"}
                    or type(selection.get("requestAligned")) is not bool
                    or type(selection.get("requestScore")) is not int
                    or not 0<=selection["requestScore"]<=10_000
                    or not isinstance(selection.get("matchedTerms"),list)
                    or not isinstance(selection.get("requestedTerms"),list)
                    or len(selection["matchedTerms"])>128 or len(selection["requestedTerms"])>128
                    or any(not _text(term,80) or re.fullmatch(r"[a-z0-9]+",term) is None
                        for term in selection["matchedTerms"]+selection["requestedTerms"])
                    or selection["matchedTerms"]!=sorted(set(selection["matchedTerms"]))
                    or selection["requestedTerms"]!=sorted(set(selection["requestedTerms"]))
                    or selection!=_selection(normalized,selection["requestedTerms"])):
                raise ValueError("Malformed guided workflow selection")
        expected_order=list(range(1,len(normalized)+1))
        observed=[step["observedSequence"] for step in normalized]
        if ([step["sequence"] for step in normalized]!=expected_order
                or [step["transactionOrder"] for step in normalized]!=expected_order
                or observed!=sorted(observed) or len(set(observed))!=len(observed)):
            raise ValueError("Malformed guided workflow step order")
        eligible.append(item)
    eligible.sort(key=lambda item:(-item.get("selection",{}).get("requestScore",0),
        not item.get("executionReady",False),not item.get("automaticallyExecutable",False),
        item["transactionId"],item["id"]))
    return eligible

def _lua(value):
    return json.dumps(value,ensure_ascii=False).replace("\\/","/")

def _identity_lua(value):
    return "{"+",".join("{name="+_lua(item["name"])+",className="+_lua(item["className"])
        +",ordinal="+str(item["ordinal"])+"}" for item in value)+"}"

def _metadata_lua(metadata):
    fields=[]
    for key in sorted(metadata):
        value=metadata[key]
        if type(value) is bool:rendered=str(value).lower()
        elif type(value) in (int,float):rendered=repr(value)
        elif isinstance(value,str):rendered=_lua(value)
        elif isinstance(value,dict) and set(value)=={"x","y","z"}:
            rendered="{x="+repr(value["x"])+",y="+repr(value["y"])+",z="+repr(value["z"])+"}"
        else:raise ValueError("Unsupported workflow prerequisite metadata")
        fields.append(key+"="+rendered)
    return "{"+",".join(fields)+"}"


def _step_lua(step):
    metadata=step["prerequisiteMetadata"];outcome=step["selectedOutcome"]
    activation_mode=step.get("activationMode") or {
        "guided-gui-activation-trial":"normal-user-gui-activation",
        "official-tool-activation-trial":"official-tool-activate",
        "proximity-prompt-trial":"executor-fireproximityprompt"}[step["kind"]]
    return ("{label="+_lua(step["targetLabel"])+",path="+_lua(step["targetPath"])
        +",kind="+_lua(step["kind"])+",activationMode="+_lua(activation_mode)
        +",identity="+_identity_lua(step["pathIdentity"])+",metadata="+_metadata_lua(metadata)
        +",outcome={key="+_lua(outcome["key"])+",change="+_lua(outcome["change"])
        +",requiredBefore="+_lua(outcome["observedBefore"])
        +",identity="+_identity_lua(outcome["stateIdentity"])+"}}")

def validate_source(source,place_id):
    if not isinstance(source,str) or not 1<=len(source)<=500_000:
        raise ValueError("Guided workflow source missing or oversized")
    required=(f"assert(game.PlaceId == {place_id}",
        "button.Activated:Connect(function() activated=true end)",
        "pcall(function() tool:Activate() end)",
        "type(fireproximityprompt)~=\"function\"",
        "pcall(function() fireproximityprompt(prompt) end)",
        "for index,step in ipairs(steps) do",
        "firstSequence and step.outcome.requiredBefore or continuity[state]",
        "before~=requiredBefore","continuity[state]=after",
        "runAttempts>=maxRunAttempts","local maxRunAttempts=5",
        "normal user activation",
        "No GUI event is synthesized","115.guided-workflow-feedback.1",
        "_G.LycolesGuidedWorkflowFeedback=feedback","recordFeedback(",
        "HttpService:JSONEncode(feedback)","actionOutcomesVerified=false")
    for token in required:
        if token not in source:raise ValueError("Missing guided workflow safeguard: "+token)
    banned=("firesignal","virtualinput","virtualuser","fireclickdetector",
        "mouse1click","mouse1press","FireServer(",
        "InvokeServer(","loadstring(","getrawmetatable(","hookmetamethod(",
        "setclipboard(","PostAsync(","RequestAsync(","http_request(","syn.request(")
    lowered=source.lower()
    for token in banned:
        if token.lower() in lowered:raise ValueError("Forbidden guided workflow operation: "+token)
    activate_receivers=re.findall(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*:Activate\s*\(",source)
    if any(receiver!="tool" for receiver in activate_receivers):
        raise ValueError("Forbidden guided workflow operation: :Activate(")
    return {"placeGuard":True,
        "manualActivationRequired":'kind="guided-gui-activation-trial"' in source,
        "automaticActivationFound":('kind="official-tool-activation-trial"' in source
            or 'kind="proximity-prompt-trial"' in source),"unsafeOperationsFound":False,
        "note":"Structural safety checks only; live Roblox runtime and gameplay are unverified"}

def render(document):
    candidates=validate(document)
    if not candidates:return None
    candidate=candidates[0]
    steps="{\n"+",\n".join("  "+_step_lua(step) for step in candidate["steps"])+"\n}"
    source=f'''-- Lycoles mixed-action workflow trial; static-generated, runtime/gameplay unverified.
-- Every GUI step requires normal user activation. Tool and Prompt steps are bounded attempts. No GUI event is synthesized.
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
local runAttempts=0
local maxRunAttempts=5
local repeatRequested=false
local activeConnection=nil
local activeStroke=nil
local status=nil
local activationTimeoutSeconds=15
local outcomeTimeoutSeconds=5
local stepActivationRetryLimit=2
local recoveryDelaySeconds=.2
local promptReturnCFrame=nil

local function clearActive()
  if activeConnection then activeConnection:Disconnect(); activeConnection=nil end
  if activeStroke then activeStroke:Destroy(); activeStroke=nil end
end
local function restorePromptPosition()
  local target=promptReturnCFrame
  promptReturnCFrame=nil
  if not target then return end
  local character=player.Character
  local root=character and character:FindFirstChild("HumanoidRootPart")
  if root then pcall(function() root.CFrame=target end) end
end
local function preflightReady()
  local playerGui=player and player:FindFirstChildOfClass("PlayerGui")
  if not playerGui then return false,"PlayerGui unavailable" end
  if type(steps)~="table" or #steps<1 then
    return false,"No execution-ready workflow steps are available"
  end
  return true,nil
end
local function resolveFrom(root,identity,startIndex)
  if not root then return nil end
  local current=root
  for index=startIndex,#identity do
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
local function resolveTarget(identity)
  local rootName=identity[1].name
  local root=rootName=="PlayerGui" and player:FindFirstChildOfClass("PlayerGui")
    or rootName=="LocalPlayer" and player or rootName=="Workspace" and workspace or nil
  return resolveFrom(root,identity,2)
end
local function resolveState(identity)
  return resolveFrom(player:FindFirstChild(identity[1].name),identity,2)
end
local function resolveTool(identity)
  local exact=resolveTarget(identity)
  if exact and exact:IsA("Tool") then return exact end
  local expected=identity[#identity]
  local matches={{}}
  local function collect(container)
    if not container then return end
    for _,child in ipairs(container:GetChildren()) do
      if child.Name==expected.name and child:IsA("Tool") then table.insert(matches,child) end
    end
  end
  collect(player:FindFirstChildOfClass("Backpack"));collect(player.Character)
  return #matches==1 and matches[1] or nil
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
local function toolMetadataMatches(tool,expected)
  return tool.ToolTip==expected.tooltip and tool.RequiresHandle==expected.requiresHandle
    and tool.CanBeDropped==expected.canBeDropped and tool.Enabled==expected.enabled
    and tool.ManualActivationOnly==expected.manualActivationOnly
end
local function promptAnchor(prompt)
  local node=prompt.Parent
  for _=1,5 do
    if not node then break end
    if node:IsA("BasePart") then return node end
    node=node.Parent
  end
  return nil
end
local function promptMetadataMatches(prompt,expected)
  if expected.actionText~=nil and prompt.ActionText~=expected.actionText then return false end
  if expected.objectText~=nil and prompt.ObjectText~=expected.objectText then return false end
  if expected.enabled~=nil and prompt.Enabled~=expected.enabled then return false end
  if expected.holdDuration~=nil and prompt.HoldDuration~=expected.holdDuration then return false end
  if expected.maxActivationDistance~=nil
      and prompt.MaxActivationDistance~=expected.maxActivationDistance then return false end
  if expected.keyboardKeyCode~=nil and prompt.KeyboardKeyCode.Name~=expected.keyboardKeyCode then return false end
  if expected.gamepadKeyCode~=nil and prompt.GamepadKeyCode.Name~=expected.gamepadKeyCode then return false end
  local anchor=promptAnchor(prompt)
  if not anchor or anchor:GetFullName()~=expected.anchorPath then return false end
  local expectedPosition=expected.anchorPosition
  if not expectedPosition or (anchor.Position-Vector3.new(
      expectedPosition.x,expectedPosition.y,expectedPosition.z)).Magnitude>12 then return false end
  return true
end
local function teleportToPrompt(prompt)
  local character=player.Character
  local root=character and character:FindFirstChild("HumanoidRootPart")
  if not root then return false,"Character root unavailable" end
  local anchor=promptAnchor(prompt)
  if not anchor then return false,"Prompt has no nearby BasePart" end
  promptReturnCFrame=root.CFrame
  root.CFrame=anchor.CFrame*CFrame.new(0,3,math.max(2,prompt.MaxActivationDistance*.4))
  task.wait(.25)
  return true,nil
end
local function activateStep(step,index,total)
  if step.kind=="guided-gui-activation-trial" then
    local button=resolveTarget(step.identity)
    if not button or not button:IsA("GuiButton") then
      return false,"control-or-state-unavailable","Exact GUI control identity unavailable"
    end
    if not sameMetadata(currentMetadata(button),step.metadata) then
      return false,"metadata-drift","GUI control prerequisite metadata changed"
    end
    activeStroke=Instance.new("UIStroke");activeStroke.Name="LycolesGuidedHighlight"
    activeStroke.Color=Color3.fromRGB(255,205,50);activeStroke.Thickness=3;activeStroke.Parent=button
    local activated=false
    activeConnection=button.Activated:Connect(function() activated=true end)
    status.Text="Step "..index.."/"..total..": activate highlighted "..step.label.." normally."
    local deadline=os.clock()+activationTimeoutSeconds
    while running and not activated and os.clock()<deadline do task.wait(.05) end
    clearActive()
    if not activated then
      return false,"activation-timeout","Normal user GUI activation was not observed within the bounded window"
    end
    return true,nil,nil
  elseif step.kind=="official-tool-activation-trial" then
    local tool=resolveTool(step.identity)
    if not tool then return false,"control-or-state-unavailable","Exact Tool identity unavailable" end
    if not toolMetadataMatches(tool,step.metadata) then
      return false,"metadata-drift","Tool activation prerequisite metadata changed"
    end
    local character=player.Character
    local humanoid=character and character:FindFirstChildOfClass("Humanoid")
    local backpack=player:FindFirstChildOfClass("Backpack")
    if not character or not humanoid then
      return false,"control-or-state-unavailable","Character humanoid unavailable for Tool equip"
    end
    if tool.Parent==backpack then
      local equipped=pcall(function() humanoid:EquipTool(tool) end)
      if not equipped then return false,"activation-timeout","Bounded Tool equip failed" end
      task.wait(.1)
    end
    if tool.Parent~=character or not tool.Enabled then
      return false,"activation-timeout","Tool is not uniquely equipped and enabled"
    end
    local activated=pcall(function() tool:Activate() end)
    if not activated then return false,"activation-timeout","Official Tool activation failed" end
    return true,nil,nil
  else
    local prompt=resolveTarget(step.identity)
    if not prompt or not prompt:IsA("ProximityPrompt") then
      return false,"control-or-state-unavailable","Exact ProximityPrompt identity unavailable"
    end
    if not promptMetadataMatches(prompt,step.metadata) then
      return false,"metadata-drift","Prompt activation prerequisite metadata changed"
    end
    if not prompt.Enabled or type(fireproximityprompt)~="function" then
      return false,"activation-timeout","Prompt activation mechanism unavailable"
    end
    local moved,message=teleportToPrompt(prompt)
    if not moved then return false,"activation-timeout",message end
    local activated=pcall(function() fireproximityprompt(prompt) end)
    if not activated then
      restorePromptPosition()
      return false,"activation-timeout","Prompt activation failed"
    end
    task.wait(.05)
    restorePromptPosition()
    return true,nil,nil
  end
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
local frame=Instance.new("Frame");frame.Size=UDim2.fromOffset(460,276);frame.Position=UDim2.new(.5,-230,.5,-138)
frame.BackgroundColor3=Color3.fromRGB(18,22,32);frame.Active=true;frame.Draggable=true;frame.Parent=gui
local title=Instance.new("TextLabel");title.Size=UDim2.new(1,-20,0,34);title.Position=UDim2.fromOffset(10,8)
title.BackgroundTransparency=1;title.TextColor3=Color3.fromRGB(235,240,255);title.Text={_lua("Guided workflow ("+candidate["id"]+")")};title.Parent=frame
status=Instance.new("TextLabel");status.Size=UDim2.new(1,-20,0,96);status.Position=UDim2.fromOffset(10,44)
status.BackgroundTransparency=1;status.TextWrapped=true;status.TextColor3=Color3.fromRGB(205,214,235)
status.Text="Ready. The first sequence requires exact observed entry state. Optional repeat uses only observed continuity.";status.Parent=frame
local function makeButton(name,text,x)
  local button=Instance.new("TextButton");button.Name=name;button.Size=UDim2.fromOffset(102,38)
  button.Position=UDim2.fromOffset(x,158);button.Text=text;button.Parent=frame;return button
end
local startButton=makeButton("StartGuidedWorkflow","START",10)
local repeatButton=makeButton("RepeatGuidedWorkflow","REPEAT: OFF",122)
local stopButton=makeButton("StopGuidedWorkflow","STOP",234)
local closeButton=makeButton("CloseGuidedWorkflow","CLOSE",346)
local feedbackButton=Instance.new("TextButton");feedbackButton.Name="ExportGuidedWorkflowFeedback"
feedbackButton.Size=UDim2.new(1,-20,0,34);feedbackButton.Position=UDim2.fromOffset(10,222)
feedbackButton.Text="PRINT DIGEST-BOUND FEEDBACK JSON";feedbackButton.Parent=frame
feedbackButton.Activated:Connect(function()
  local ok,payload=pcall(function() return HttpService:JSONEncode(feedback) end)
  if ok then print("LYCOLES_GUIDED_WORKFLOW_FEEDBACK|"..payload)
    status.Text="Feedback JSON printed locally; all verification claims remain false."
  else status.Text="Feedback JSON encoding failed; no data was sent." end
end)
local function finish(message)
  running=false;clearActive();restorePromptPosition();status.Text=message
end
local function runWorkflow()
  if running then return end
  local ready,reason=preflightReady()
  if not ready then
    finish("Stopped: "..reason)
    return
  end
  if runAttempts>=maxRunAttempts then
    finish("Stopped: bounded retry limit reached for this session.");return
  end
  running=true
  local continuity={{}}
  local firstSequence=true
  while running do
    if runAttempts>=maxRunAttempts then
      finish("Stopped at the bounded five-sequence limit; causality and gameplay remain unverified.")
      return
    end
    if #feedback.entries+#steps>400 then
      finish("Stopped: feedback record limit reached; export before rerunning.");return
    end
    runAttempts=runAttempts+1
    runId=runId+1;local thisRun=runId
    for index,step in ipairs(steps) do
      if not running or runId~=thisRun then return end
      local state=resolveState(step.outcome.identity)
      if not state then
        recordFeedback(thisRun,index,step,nil,nil,false,false,"control-or-state-unavailable",
          "Exact selected state identity unavailable")
        finish("Stopped: selected state identity unavailable at step "..index);return
      end
      local ok,before=pcall(function() return state.Value end)
      if not ok or type(before)~="number" and type(before)~="string" and type(before)~="boolean" then
        recordFeedback(thisRun,index,step,nil,nil,false,false,"state-unreadable",
          "Selected client-visible state is not readable scalar")
        finish("Stopped: selected state is not readable scalar at step "..index);return
      end
      local requiredBefore=firstSequence and step.outcome.requiredBefore or continuity[state]
      if requiredBefore==nil or before~=requiredBefore then
        recordFeedback(thisRun,index,step,nil,nil,false,false,"metadata-drift",
          firstSequence and "Selected entry-state prerequisite changed"
            or "Selected state no longer matches the previous observed outcome")
        finish("Stopped: state prerequisite drifted at step "..index);return
      end
      local activated,failureStatus,failureMessage=false,nil,nil
      local activationAttempts=(step.kind=="guided-gui-activation-trial") and 1 or stepActivationRetryLimit
      for attempt=1,activationAttempts do
        activated,failureStatus,failureMessage=activateStep(step,index,#steps)
        if not running or runId~=thisRun then return end
        if activated then break end
        local retryable=failureStatus=="activation-timeout"
        if not retryable or attempt>=activationAttempts then break end
        status.Text="Step "..index..": activation retry "..(attempt+1).."/"..activationAttempts
        task.wait(recoveryDelaySeconds)
      end
      if not activated then
        local sampled=failureStatus=="activation-timeout"
        recordFeedback(thisRun,index,step,sampled and before or nil,sampled and before or nil,
          false,false,failureStatus,failureMessage)
        if failureStatus=="metadata-drift" then
          finish("Stopped: control prerequisites drifted at step "..index)
        else
          local suffix=activationAttempts>1 and " after bounded retries" or ""
          finish("Stopped at step "..index..": "..tostring(failureMessage or "activation failed")..suffix)
        end
        return
      end
      status.Text="Sequence "..runAttempts..", step "..index
        ..": activation attempted; watching selected client-visible outcome."
      local observed=false;local after=before;local deadline=os.clock()+outcomeTimeoutSeconds
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
      continuity[state]=after
      recordFeedback(thisRun,index,step,before,after,true,true,"expected-change-observed",
        "Selected client-visible direction observed after the bounded step activation")
    end
    firstSequence=false
    if not repeatRequested then
      finish("Candidate completed with client-visible observations; causality and gameplay remain unverified.")
      return
    end
    status.Text="Sequence "..runAttempts.." observed; continuing bounded repeat with state continuity."
    task.wait(.4)
  end
end
startButton.Activated:Connect(function() task.spawn(runWorkflow) end)
repeatButton.Activated:Connect(function()
  if running then return end
  repeatRequested=not repeatRequested
  repeatButton.Text=repeatRequested and "REPEAT: ON" or "REPEAT: OFF"
  status.Text=repeatRequested and "Bounded repeat armed: at most five sequences; STOP cancels immediately."
    or "Single-sequence mode armed; exact observed entry state remains required."
end)
stopButton.Activated:Connect(function() runId=runId+1;finish("Stopped by user; no verification claim.") end)
closeButton.Activated:Connect(function() runId=runId+1;running=false;clearActive();restorePromptPosition();gui:Destroy() end)
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
