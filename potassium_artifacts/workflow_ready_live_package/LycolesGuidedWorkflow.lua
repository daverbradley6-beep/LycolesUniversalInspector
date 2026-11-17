-- Lycoles mixed-action workflow trial; static-generated, runtime/gameplay unverified.
-- Every GUI step requires normal user activation. Tool and Prompt steps are bounded attempts. No GUI event is synthesized.
assert(game.PlaceId == 3623096087, "Wrong place for generated workflow trial")
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
local player=Players.LocalPlayer
local steps={
  {label="Select",path="PlayerGui.HUD.Shop.Select",kind="guided-gui-activation-trial",activationMode="normal-user-gui-activation",identity={{name="PlayerGui",className="PlayerGui",ordinal=1},{name="HUD",className="ScreenGui",ordinal=1},{name="Shop",className="Frame",ordinal=1},{name="Select",className="TextButton",ordinal=1}},metadata={active=true,ancestorVisible=true,autoButtonColor=true,controlClass="TextButton",effectiveVisible=true,interactable=true,screenEnabled=true,selectable=true,text="Select",visible=true,withinScrollingBounds=true},outcome={key="Data.ShopStage",change="increased",requiredBefore=2,identity={{name="Data",className="Folder",ordinal=1},{name="ShopStage",className="IntValue",ordinal=1}}}},
  {label="Confirm",path="PlayerGui.HUD.Shop.Confirm",kind="guided-gui-activation-trial",activationMode="normal-user-gui-activation",identity={{name="PlayerGui",className="PlayerGui",ordinal=1},{name="HUD",className="ScreenGui",ordinal=1},{name="Shop",className="Frame",ordinal=1},{name="Confirm",className="TextButton",ordinal=1}},metadata={active=true,ancestorVisible=true,autoButtonColor=true,controlClass="TextButton",effectiveVisible=true,interactable=true,screenEnabled=true,selectable=true,text="Confirm",visible=true,withinScrollingBounds=true},outcome={key="Data.ShopStage",change="increased",requiredBefore=3,identity={{name="Data",className="Folder",ordinal=1},{name="ShopStage",className="IntValue",ordinal=1}}}}
}
local feedbackSequence=0
local feedback={schemaVersion="115.guided-workflow-feedback.1",placeId=3623096087,
  scanId="workflow_ready_live_package",workflowPlanSHA256="5011e09228dd0ae0c716d529bf4f71e98175fbb9167e6e9280af251a499115a1",
  candidateId="e0207a259f6fae8ed60a",sessionId=HttpService:GenerateGUID(false),entries={},
  claims={sourceAuthenticityVerified=false,causalityProven=false,serverAuthorityVerified=false,
    runtimeVerified=false,gameplayVerified=false,actionOutcomesVerified=false}}
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
  local matches={}
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
  return {controlClass=button.ClassName,text=button:IsA("TextButton") and button.Text or "",
    visible=button.Visible,active=button.Active,selectable=button.Selectable,
    autoButtonColor=button.AutoButtonColor,interactable=interactable,
    ancestorVisible=ancestorVisible,screenEnabled=screenEnabled,
    withinScrollingBounds=withinScrollingBounds,
    effectiveVisible=visible and ancestorVisible and screenEnabled}
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
  table.insert(feedback.entries,{sequence=feedbackSequence,runId=thisRun,stepSequence=index,
    targetPath=step.path,outcomeKey=step.outcome.key,expected=step.outcome.change,
    before=before,after=after,activationObserved=activated==true,
    observedExpectedChange=observed==true,status=resultStatus,
    message=tostring(message or ""):sub(1,240),observedAtUnix=os.time()})
end

local gui=Instance.new("ScreenGui");gui.Name="LycolesGuidedWorkflow";gui.ResetOnSpawn=false
gui.Parent=player:WaitForChild("PlayerGui")
local frame=Instance.new("Frame");frame.Size=UDim2.fromOffset(460,276);frame.Position=UDim2.new(.5,-230,.5,-138)
frame.BackgroundColor3=Color3.fromRGB(18,22,32);frame.Active=true;frame.Draggable=true;frame.Parent=gui
local title=Instance.new("TextLabel");title.Size=UDim2.new(1,-20,0,34);title.Position=UDim2.fromOffset(10,8)
title.BackgroundTransparency=1;title.TextColor3=Color3.fromRGB(235,240,255);title.Text="Guided workflow (e0207a259f6fae8ed60a)";title.Parent=frame
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
  local continuity={}
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
