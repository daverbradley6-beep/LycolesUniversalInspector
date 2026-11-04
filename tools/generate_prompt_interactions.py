#!/usr/bin/env python3
"""Generate place-bound ProximityPrompt trials from correlated observable evidence."""
import hashlib
import json
import math


def _quote(value):
    return json.dumps(str(value),ensure_ascii=False)


def _identity_lua(value,expected_class="ProximityPrompt"):
    if value is None:return "nil"
    if not isinstance(value,list) or not 2<=len(value)<=21:raise ValueError("Malformed correlated prompt target")
    segments=[]
    for segment in value:
        if not isinstance(segment,dict):raise ValueError("Malformed correlated prompt target")
        name=segment.get("name");class_name=segment.get("className");ordinal=segment.get("ordinal")
        if (not isinstance(name,str) or not 1<=len(name)<=100 or not isinstance(class_name,str)
                or not 1<=len(class_name)<=100 or type(ordinal) is not int or not 1<=ordinal<=10000):
            raise ValueError("Malformed correlated prompt target")
        segments.append("{name="+_quote(name)+",className="+_quote(class_name)+",ordinal="+str(ordinal)+"}")
    if value[0]["name"] not in ("Workspace","LocalPlayer","ReplicatedStorage","Players"):
        raise ValueError("Malformed correlated prompt target")
    if value[-1]["className"]!=expected_class:raise ValueError("Malformed correlated interaction target")
    return "{"+",".join(segments)+"}"

def _state_identity_lua(value):
    if value is None:return "nil"
    if not isinstance(value,list) or not 2<=len(value)<=7:raise ValueError("Malformed correlated prompt target")
    segments=[]
    for segment in value:
        if not isinstance(segment,dict):raise ValueError("Malformed correlated prompt target")
        name=segment.get("name");class_name=segment.get("className");ordinal=segment.get("ordinal")
        if (not isinstance(name,str) or not 1<=len(name)<=100 or not isinstance(class_name,str)
                or not 1<=len(class_name)<=100 or type(ordinal) is not int or not 1<=ordinal<=10000):
            raise ValueError("Malformed correlated prompt target")
        segments.append("{name="+_quote(name)+",className="+_quote(class_name)+",ordinal="+str(ordinal)+"}")
    if value[0]["name"] not in ("leaderstats","Data") or value[-1]["className"] not in (
            "IntValue","NumberValue","BoolValue","StringValue"):
        raise ValueError("Malformed correlated prompt target")
    return "{"+",".join(segments)+"}"


def _prompt_snapshot(value):
    if not isinstance(value,dict):raise ValueError("Malformed prompt prerequisite evidence")
    allowed={"actionText","objectText","enabled","holdDuration","maxActivationDistance",
        "keyboardKeyCode","gamepadKeyCode","anchorPath","anchorPosition"}
    if any(key not in allowed for key in value):raise ValueError("Malformed prompt prerequisite evidence")
    for key in ("actionText","objectText","keyboardKeyCode","gamepadKeyCode","anchorPath"):
        if key in value and not isinstance(value[key],str):
            raise ValueError("Malformed prompt prerequisite evidence")
    if "enabled" in value and type(value["enabled"]) is not bool:
        raise ValueError("Malformed prompt prerequisite evidence")
    for key in ("holdDuration","maxActivationDistance"):
        if key in value and (type(value[key]) not in (int,float)
                or not math.isfinite(value[key]) or value[key]<0):
            raise ValueError("Malformed prompt prerequisite evidence")
    position=value.get("anchorPosition")
    if position is not None and (not isinstance(position,dict) or set(position)!={"x","y","z"}
            or any(type(position[key]) not in (int,float) or not math.isfinite(position[key])
                for key in ("x","y","z"))):
        raise ValueError("Malformed prompt prerequisite evidence")
    return value


def _tool_snapshot(value):
    if not isinstance(value,dict) or set(value)!={"tooltip","requiresHandle","canBeDropped",
            "enabled","manualActivationOnly"}:
        raise ValueError("Malformed Tool prerequisite evidence")
    tooltip=value.get("tooltip")
    if (not isinstance(tooltip,str) or len(tooltip)>120
            or any(ord(character)<32 or ord(character)==127 for character in tooltip)):
        raise ValueError("Malformed Tool prerequisite evidence")
    if any(type(value.get(key)) is not bool for key in
            ("requiresHandle","canBeDropped","enabled","manualActivationOnly")):
        raise ValueError("Malformed Tool prerequisite evidence")
    return value

def _tool_metadata_lua(value):
    value=_tool_snapshot(value)
    boolean=lambda item:"true" if item else "false"
    return "{tooltip="+_quote(value["tooltip"])+",requiresHandle="+boolean(value["requiresHandle"])+\
        ",canBeDropped="+boolean(value["canBeDropped"])+",enabled="+boolean(value["enabled"])+\
        ",manualActivationOnly="+boolean(value["manualActivationOnly"])+"}"



def render(discovery):
    if not isinstance(discovery,dict) or discovery.get("schemaVersion")!="111.action-capabilities.1":
        raise ValueError("Action capability discovery required")
    place=discovery.get("placeId");egg=discovery.get("eggHatching");claims=discovery.get("claims")
    prompt_contract=discovery.get("promptInteractions")
    if type(place) is not int or not isinstance(egg,dict) or not isinstance(claims,dict):
        raise ValueError("Malformed action capability discovery")
    if any(claims.get(key) is not False for key in ("sourceAuthenticityVerified","causalityProven",
            "serverAuthorityVerified","runtimeVerified","gameplayVerified","actionOutcomesVerified")):
        raise ValueError("Action capability discovery claims unsupported verification")
    targets=[]
    if isinstance(prompt_contract,dict):
        if any(prompt_contract.get(key) is not False for key in
                ("causalityProven","runtimeVerified","gameplayVerified")):
            raise ValueError("Prompt contract claims unsupported verification")
        for item in prompt_contract.get("targets",[]):
            if not isinstance(item,dict) or item.get("trialGenerationReady") is not True:continue
            path=item.get("path");label=item.get("label");signals=item.get("outcomeSignals")
            signal=item.get("selectedOutcome")
            if (not isinstance(path,str) or not isinstance(label,str) or not isinstance(signals,list)
                    or not signals or not isinstance(signal,dict) or signal not in signals
                    or item.get("controlType")!="ProximityPrompt.Triggered"
                    or type(item.get("observedTriggers")) is not int or item["observedTriggers"]<1
                    or item.get("temporalCorrelationOnly") is not True
                    or any(item.get(key) is not False for key in
                        ("causalityProven","runtimeVerified","gameplayVerified"))):
                raise ValueError("Malformed correlated prompt target")
            selection=signal.get("selection")
            if (not isinstance(signal.get("key"),str)
                    or signal.get("change") not in ("increased","decreased","changed")
                    or signal.get("generationResolvable") is not True
                    or not isinstance(selection,dict) or selection.get("selectedForTrial") is not True):
                raise ValueError("Malformed correlated prompt outcome")
            prerequisite_evidence=item.get("prerequisiteEvidence")
            if not isinstance(prerequisite_evidence,dict):
                raise ValueError("Malformed prompt prerequisite evidence")
            snapshots=prerequisite_evidence.get("metadataSnapshots")
            drift=prerequisite_evidence.get("metadataDriftObserved")
            if (not isinstance(snapshots,list) or len(snapshots)>8 or type(drift) is not bool
                    or drift!=(len(snapshots)>1)
                    or len({json.dumps(snapshot,sort_keys=True,ensure_ascii=False)
                        for snapshot in snapshots})!=len(snapshots)):
                raise ValueError("Malformed prompt prerequisite evidence")
            for snapshot in snapshots:_prompt_snapshot(snapshot)
            if ((snapshots and item.get("promptMetadata")!=snapshots[0])
                    or (not snapshots and "promptMetadata" in item)):
                raise ValueError("Malformed prompt prerequisite evidence")

            metadata=json.dumps(item.get("promptMetadata",{}),ensure_ascii=False).lower()
            haystack=(label+" "+path+" "+metadata).lower()
            is_egg="egg" in haystack or "hatch" in haystack

            multi=is_egg and any(token in haystack for token in ("multi","triple","x3","3 egg","three"))
            objective=item.get("objective") if isinstance(item.get("objective"),dict) else {}
            score=objective.get("score",0)
            if type(score) is not int:raise ValueError("Malformed prompt objective")
            targets.append((label,path,signal["key"],signal["change"],multi,is_egg,
                str(item.get("featureCandidate") or "other")[:80],score,
                _identity_lua(item.get("pathIdentity")),_state_identity_lua(signal.get("stateIdentity")),
                "prompt","nil"))
    elif egg.get("automaticSingleTrialReady") is True:
        for item in egg.get("targets",[]):
            if not isinstance(item,dict) or item.get("incrementObservations",0)<1:continue
            path=item.get("path");label=item.get("label");keys=item.get("outcomeKeys")
            if not isinstance(path,str) or not isinstance(label,str) or not isinstance(keys,list) or not keys:continue
            identities=item.get("outcomeIdentities",{})
            metadata=json.dumps(item.get("promptMetadata",{}),ensure_ascii=False).lower()
            multi=any(token in (label+" "+metadata).lower() for token in ("multi","triple","x3","3 egg","three"))
            targets.append((label,path,keys[0],"increased",multi,True,"pets",0,
                _identity_lua(item.get("pathIdentity")),_state_identity_lua(identities.get(keys[0])),
                "prompt","nil"))
    tool_contract=discovery.get("toolInteractions")
    if isinstance(tool_contract,dict):
        if (tool_contract.get("generatorIntegrated") is not True
                or any(tool_contract.get(key) is not False for key in
                    ("causalityProven","runtimeVerified","gameplayVerified"))):
            raise ValueError("Malformed Tool interaction contract")
        for item in tool_contract.get("targets",[]):
            if not isinstance(item,dict) or item.get("trialGenerationReady") is not True:continue
            path=item.get("path");label=item.get("label");signals=item.get("outcomeSignals")
            signal=item.get("selectedOutcome")
            if (not isinstance(path,str) or not isinstance(label,str) or not isinstance(signals,list)
                    or not signals or not isinstance(signal,dict) or signal not in signals
                    or item.get("activationContractReady") is not True
                    or item.get("controlType")!="Tool.Activated"
                    or type(item.get("observedActivations")) is not int
                    or item["observedActivations"]<1 or item.get("temporalCorrelationOnly") is not True
                    or any(item.get(key) is not False for key in
                        ("causalityProven","runtimeVerified","gameplayVerified"))):
                raise ValueError("Malformed correlated Tool target")
            selection=signal.get("selection")
            if (not isinstance(signal.get("key"),str)
                    or signal.get("change") not in ("increased","decreased","changed")
                    or signal.get("generationResolvable") is not True
                    or not isinstance(selection,dict) or selection.get("selectedForTrial") is not True):
                raise ValueError("Malformed correlated Tool outcome")
            evidence=item.get("prerequisiteEvidence")
            if not isinstance(evidence,dict):raise ValueError("Malformed Tool prerequisite evidence")
            snapshots=evidence.get("metadataSnapshots");drift=evidence.get("metadataDriftObserved")
            if (not isinstance(snapshots,list) or len(snapshots)!=1
                    or type(drift) is not bool or drift is not False
                    or len({json.dumps(snapshot,sort_keys=True,ensure_ascii=False)
                        for snapshot in snapshots})!=len(snapshots)):
                raise ValueError("Malformed Tool prerequisite evidence")
            for snapshot in snapshots:_tool_snapshot(snapshot)
            if snapshots[0]["enabled"] is not True or item.get("toolMetadata")!=snapshots[0]:
                raise ValueError("Malformed Tool prerequisite evidence")
            objective=item.get("objective") if isinstance(item.get("objective"),dict) else {}
            score=objective.get("score",0)
            if type(score) is not int:raise ValueError("Malformed Tool objective")
            targets.append((label,path,signal["key"],signal["change"],False,False,
                str(item.get("featureCandidate") or "other")[:80],score,
                _identity_lua(item.get("pathIdentity"),"Tool"),
                _state_identity_lua(signal.get("stateIdentity")),"tool",
                _tool_metadata_lua(snapshots[0])))

    if not targets:return None
    targets.sort(key=lambda item:(-item[7],item[0].lower(),item[1]))
    target_rows="\n".join("    {label="+_quote(label)+",path="+_quote(path)+
        ",outcome="+_quote(outcome)+",expected="+_quote(expected)+
        ",multi="+("true" if multi else "false")+",egg="+("true" if is_egg else "false")+
        ",feature="+_quote(feature)+",objectiveScore="+str(score)+",kind="+_quote(kind)+
        ",identity="+identity+",outcomeIdentity="+outcome_identity+",toolMetadata="+tool_metadata+"},"
        for label,path,outcome,expected,multi,is_egg,feature,score,identity,outcome_identity,kind,tool_metadata in targets)
    scan_id=discovery.get("scanId")
    if scan_id is None:
        scan_id="UNAVAILABLE"
    elif not isinstance(scan_id,str) or not 1<=len(scan_id)<=128:
        raise ValueError("Malformed action capability scan identity")
    discovery_digest=hashlib.sha256(json.dumps(
        discovery,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()

    source=r'''-- Evidence-bounded interaction trials; outcome changes are observed, not causal proof.
do
assert(game.PlaceId == __PLACE_ID__, "Incorrect Roblox place")
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
local player=Players.LocalPlayer
assert(player,"LocalPlayer unavailable")
if type(_G.LycolesPromptClose)=="function" then pcall(_G.LycolesPromptClose)
elseif type(_G.LycolesEggClose)=="function" then pcall(_G.LycolesEggClose) end
local targets={
__TARGETS__
}
local alive,running=true,false
local selected=1
local mode="auto"
local failures=0
local attempts=0
local connections={}
local sharedState={running=false,selectedIndex=1,selectedLabel="",mode="auto",failures=0,attempts=0}
_G.LycolesPromptState=sharedState
local feedbackSequence=0
local feedback={schemaVersion="112.prompt-trial-feedback.1",placeId=__PLACE_ID__,scanId=__SCAN_ID__,
    discoverySHA256=__DISCOVERY_DIGEST__,sessionId=HttpService:GenerateGUID(false),entries={},
    claims={sourceAuthenticityVerified=false,causalityProven=false,serverAuthorityVerified=false,
        runtimeVerified=false,gameplayVerified=false,actionOutcomesVerified=false}}
_G.LycolesPromptTrialFeedback=feedback
local function recordFeedback(target,before,after,observed,resultStatus,message)
    feedbackSequence=feedbackSequence+1
    table.insert(feedback.entries,{sequence=feedbackSequence,targetPath=target and target.path or "",
        outcomeKey=target and target.outcome or "",expected=target and target.expected or "changed",
        before=before,after=after,observedExpectedChange=observed==true,status=resultStatus,
        message=tostring(message or ""):sub(1,240),observedAtUnix=os.time()})
    if #feedback.entries>100 then table.remove(feedback.entries,1) end
end

local gui=Instance.new("ScreenGui")
gui.Name="LycolesPromptInteractions"
gui.ResetOnSpawn=false
gui.Parent=player:WaitForChild("PlayerGui")
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(400,360)
panel.Position=UDim2.new(.5,-200,.5,-180)
panel.BackgroundColor3=Color3.fromRGB(24,30,39)
panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-20,0,32) title.Position=UDim2.fromOffset(10,6)
title.BackgroundTransparency=1 title.TextColor3=Color3.new(1,1,1)
title.Text="Prompt Interactions | evidence-bounded trial" title.Parent=panel
local targetButton=Instance.new("TextButton")
targetButton.Size=UDim2.new(1,-20,0,38) targetButton.Position=UDim2.fromOffset(10,45)
targetButton.Parent=panel
local targetDropdown=Instance.new("ScrollingFrame")
targetDropdown.Name="TargetDropdown"
targetDropdown.Size=UDim2.new(1,-20,0,120) targetDropdown.Position=UDim2.fromOffset(10,88)
targetDropdown.BackgroundColor3=Color3.fromRGB(31,38,49)
targetDropdown.AutomaticCanvasSize=Enum.AutomaticSize.Y targetDropdown.CanvasSize=UDim2.new()
targetDropdown.ScrollBarThickness=6 targetDropdown.Visible=false targetDropdown.Parent=panel
local targetLayout=Instance.new("UIListLayout")
targetLayout.Padding=UDim.new(0,4) targetLayout.Parent=targetDropdown
local targetRows={}

local modeButton=Instance.new("TextButton")
modeButton.Size=UDim2.new(.5,-15,0,38) modeButton.Position=UDim2.fromOffset(10,216)
modeButton.Parent=panel
local toggle=Instance.new("TextButton")
toggle.Size=UDim2.new(.5,-15,0,38) toggle.Position=UDim2.new(.5,5,0,216)
toggle.Parent=panel
local status=Instance.new("TextLabel")
status.Size=UDim2.new(1,-20,0,88) status.Position=UDim2.fromOffset(10,262)
status.BackgroundColor3=Color3.fromRGB(34,41,52) status.TextColor3=Color3.fromRGB(220,228,236)
status.TextWrapped=true status.Text="Stopped. Runtime and gameplay remain unverified." status.Parent=panel
local function split(path)
    local result={} for value in string.gmatch(path,"[^%.]+") do table.insert(result,value) end return result
end
local function resolve(target)
    local roots={Workspace=workspace,LocalPlayer=player,
        ReplicatedStorage=game:GetService("ReplicatedStorage"),Players=Players}
    if target.identity then
        local current=roots[target.identity[1].name]
        if not current then return nil,"Unsupported root "..tostring(target.identity[1].name) end
        for index=2,#target.identity do
            local expected=target.identity[index] local count=0 local found=nil
            for _,child in ipairs(current:GetChildren()) do
                if child.Name==expected.name and child.ClassName==expected.className then
                    count=count+1 if count==expected.ordinal then found=child break end
                end
            end
            if not found then return nil,"Missing identity segment "..expected.name end
            current=found
        end
        return current,nil
    end
    local parts=split(target.path)
    local current=roots[parts[1]]
    if not current then return nil,"Unsupported root "..tostring(parts[1]) end
    for index=2,#parts do
        current=current:FindFirstChild(parts[index])
        if not current then return nil,"Missing path segment "..parts[index] end
    end
    return current,nil
end
local function resolveTool(target)
    local exact,exactError=resolve(target)
    if exact and exact:IsA("Tool") then return exact,nil end
    local expected=target.identity and target.identity[#target.identity]
    if not expected then return nil,exactError or "Tool identity unavailable" end
    local matches={}
    local function collect(container)
        if not container then return end
        for _,child in ipairs(container:GetChildren()) do
            if child.Name==expected.name and child.ClassName=="Tool" then table.insert(matches,child) end
        end
    end
    collect(player:FindFirstChildOfClass("Backpack")) collect(player.Character)
    if #matches~=1 then return nil,"Expected one mobile Tool match, found "..tostring(#matches) end
    return matches[1],nil
end
local function readOutcome(target)
    local current=nil
    if target.outcomeIdentity then
        current=player:FindFirstChild(target.outcomeIdentity[1].name)
        for index=2,#target.outcomeIdentity do
            if not current then return nil end
            local expected=target.outcomeIdentity[index] local count=0 local found=nil
            for _,child in ipairs(current:GetChildren()) do
                if child.Name==expected.name and child.ClassName==expected.className then
                    count=count+1 if count==expected.ordinal then found=child break end
                end
            end
            current=found
        end
    else
        local parts=split(target.outcome)
        current=parts[1]=="leaderstats" and player:FindFirstChild("leaderstats")
            or parts[1]=="Data" and player:FindFirstChild("Data") or nil
        if not current then return nil end
        for index=2,#parts do current=current:FindFirstChild(parts[index]) if not current then return nil end end
    end
    if not current or not current:IsA("ValueBase") then return nil end
    local ok,value=pcall(function() return current.Value end)
    return ok and value or nil
end
local function teleportTo(prompt)
    local _,_,root=(function()
        local character=player.Character
        return character,character and character:FindFirstChildOfClass("Humanoid"),
            character and character:FindFirstChild("HumanoidRootPart")
    end)()
    if not root then return false,"Character root unavailable" end
    local node=prompt.Parent
    local anchor=nil
    for _=1,5 do
        if not node then break end
        if node:IsA("BasePart") then anchor=node break end
        anchor=node:FindFirstChildWhichIsA("BasePart",true)
        if anchor then break end
        node=node.Parent
    end
    if not anchor then return false,"Prompt has no nearby BasePart" end
    root.CFrame=anchor.CFrame*CFrame.new(0,3,math.max(2,tonumber(prompt.MaxActivationDistance) and prompt.MaxActivationDistance*.4 or 3))
    task.wait(.25)
    return true,nil
end
local function currentTarget()
    if mode=="multi" then
        for _,target in ipairs(targets) do if target.multi then return target end end
    end
    return targets[selected]
end
local function update()
    local target=currentTarget() or targets[selected]
    targetButton.Text="Interaction: "..target.label.." ["..target.feature.."]  ▾"
    if target.egg then modeButton.Text=mode=="multi" and "Mode: MULTI" or "Mode: AUTO SINGLE"
    else modeButton.Text="Mode: REPEAT TRIAL" end
    toggle.Text=running and "STOP" or "START"
    if running then targetDropdown.Visible=false end
    sharedState.running=running sharedState.selectedIndex=selected
    sharedState.selectedLabel=target.label sharedState.mode=mode
    sharedState.failures=failures sharedState.attempts=attempts
    for index,row in pairs(targetRows) do
        row.BackgroundColor3=index==selected and Color3.fromRGB(61,107,139) or Color3.fromRGB(42,51,64)
    end
    if type(_G.LycolesGameStateChanged)=="function" then pcall(_G.LycolesGameStateChanged) end
end
for index,target in ipairs(targets) do
    local row=Instance.new("TextButton")
    row.Name="Target"..tostring(index) row.Size=UDim2.new(1,-8,0,34)
    row.Text=target.label.." ["..target.feature.."]"
    row.TextColor3=Color3.new(1,1,1) row.TextXAlignment=Enum.TextXAlignment.Left
    row.Parent=targetDropdown targetRows[index]=row
    table.insert(connections,row.MouseButton1Click:Connect(function()
        if running then return end selected=index mode="auto" targetDropdown.Visible=false update()
        status.Text="Selected "..target.label..". Runtime and gameplay remain unverified."
    end))
end

local function stop(reason)
    running=false update()
    if reason then status.Text=reason end
end
local function activateOnce()
    local target=currentTarget()
    if not target then return false,"No evidence-backed target for mode" end
    local function failed(resultStatus,message,before,after)
        recordFeedback(target,before,after,false,resultStatus,message)
        return false,message
    end
    local before=nil
    if target.kind=="tool" then
        local tool,err=resolveTool(target)
        if not tool then return failed("target-unresolved",err or "Tool target unresolved") end
        local metadata=target.toolMetadata
        if not metadata or tool.ToolTip~=metadata.tooltip or tool.RequiresHandle~=metadata.requiresHandle
            or tool.CanBeDropped~=metadata.canBeDropped
            or tool.ManualActivationOnly~=metadata.manualActivationOnly then
            return failed("tool-metadata-drift","Tool activation prerequisite metadata changed")
        end
        local character=player.Character
        local humanoid=character and character:FindFirstChildOfClass("Humanoid")
        local backpack=player:FindFirstChildOfClass("Backpack")
        if not character or not humanoid then return failed("tool-equip-failed","Character humanoid unavailable") end
        if tool.Parent==backpack then
            local equipped,equipError=pcall(function() humanoid:EquipTool(tool) end)
            if not equipped then return failed("tool-equip-failed","Tool equip failed: "..tostring(equipError)) end
            task.wait(.1)
        end
        if tool.Parent~=character then return failed("tool-equip-failed","Tool is not uniquely equipped") end
        if not tool.Enabled then return failed("tool-disabled","Observed Tool is currently disabled") end
        before=readOutcome(target)
        local ok,activateError=pcall(function() tool:Activate() end)
        if not ok then return failed("activation-failed","Tool activation failed: "..tostring(activateError),before) end
    else
        local prompt,err=resolve(target)
        if not prompt or not prompt:IsA("ProximityPrompt") then
            return failed("target-unresolved",err or "Target is not a ProximityPrompt")
        end
        if not prompt.Enabled then return failed("prompt-disabled","Observed prompt is currently disabled") end
        if type(fireproximityprompt)~="function" then
            return failed("activation-unavailable","fireproximityprompt unavailable in this environment")
        end
        local moved,moveError=teleportTo(prompt)
        if not moved then return failed("teleport-failed",moveError) end
        before=readOutcome(target)
        local ok,fireError=pcall(function() fireproximityprompt(prompt) end)
        if not ok then return failed("activation-failed","Prompt activation failed: "..tostring(fireError),before) end
    end
    task.wait(1.5)
    local after=readOutcome(target)
    local observed=target.expected=="increased" and type(before)=="number" and type(after)=="number" and after>before
        or target.expected=="decreased" and type(before)=="number" and type(after)=="number" and after<before
        or target.expected=="changed" and before~=nil and after~=nil and after~=before
    if observed then
        failures=0 update()
        recordFeedback(target,before,after,true,"expected-change-observed","Observed bounded scalar direction")
        status.Text="Observed "..target.outcome.." "..target.expected.." "..tostring(before).." → "..tostring(after)
            ..". This is runtime correlation, not server-authority or causal proof."
        return true,nil
    end
    return failed("expected-change-not-observed","No expected "..target.expected.." outcome observed",before,after)
end
local function start()
    if running then return true,"Interaction trial already running" end
    local target=currentTarget()
    if target and target.kind=="prompt" and type(fireproximityprompt)~="function" then
        return false,"fireproximityprompt unavailable in this environment"
    end
    if mode=="multi" and not target then return false,"No observed multi-hatch target" end
    running=true failures=0 attempts=0 update()
    task.spawn(function()
        while alive and running do
            attempts=attempts+1 update()
            local ok,message=activateOnce()
            if not ok then
                failures=failures+1 update()
                status.Text=message.." (failure "..tostring(failures).."/3)"
                if failures>=3 then stop("Stopped after 3 uncorroborated attempts. "..message) break end
            end
            if attempts>=25 then stop("Stopped at the bounded 25-attempt trial limit") break end
            task.wait(.4)
        end
    end)
    return true,"Interaction trial started"
end
local function hasMulti()
    for _,target in ipairs(targets) do if target.multi then return true end end return false
end
table.insert(connections,targetButton.MouseButton1Click:Connect(function()
    if running then return end targetDropdown.Visible=not targetDropdown.Visible update()
end))
table.insert(connections,modeButton.MouseButton1Click:Connect(function()
    if running then return end
    if not targets[selected].egg then status.Text="Modes apply only to observed egg interactions." return end
    if not hasMulti() then status.Text="Multi unavailable: no distinct observed multi-hatch prompt." return end
    mode=mode=="multi" and "auto" or "multi" update()
end))
table.insert(connections,toggle.MouseButton1Click:Connect(function()
    if running then stop("Stopped by user") else local ok,message=start() status.Text=message end
end))
local function listTargets(eggsOnly)
    local names={} for _,target in ipairs(targets) do if not eggsOnly or target.egg then
        table.insert(names,target.label.." ["..target.feature.."]") end end
    return #names>0 and table.concat(names,", ") or "No matching evidence-backed targets"
end
local function selectTarget(words,eggsOnly,usage)
    local query=table.concat(words," "):lower() if query=="" then return false,usage end
    for index,target in ipairs(targets) do
        if (not eggsOnly or target.egg) and target.label:lower():find(query,1,true) then
            selected=index mode="auto" update() return true,"Selected "..target.label
        end
    end
    return false,eggsOnly and "Egg target not found" or "Interaction target not found"
end
local function commandState()
    local target=currentTarget() or targets[selected]
    return (running and "running" or "stopped").." | "..target.label.." | "..mode
        .." | failures "..tostring(failures).."/3"
end
local function activationAvailable()
    local target=currentTarget() or targets[selected]
    if target.kind=="tool" then return true,"official Tool activation available" end
    return type(fireproximityprompt)=="function","fireproximityprompt unavailable"
end
_G.LycolesGameCommands={
    interactions={category="Game: Interactions",description="List evidence-backed interaction targets",arguments="",availability=function() return true,"available" end,state=commandState,
        run=function() return true,listTargets(false) end},
    interaction={category="Game: Interactions",description="Select an evidence-backed interaction target",arguments="[name]",availability=function() return not running,running and "stop interaction trial first" or "available" end,state=commandState,
        run=function(words) return selectTarget(words,false,"Usage: ;interaction [name]") end},
    interactionstart={category="Game: Interactions",description="Start selected interaction trial",arguments="",availability=activationAvailable,state=commandState,run=function() return start() end},
    interactionstop={category="Game: Interactions",description="Stop interaction trial",arguments="",availability=function() return true,"available" end,state=commandState,
        run=function() stop("Stopped by command") return true,"Interaction trial stopped" end},
    interactionfeedback={category="Game: Interactions",description="Export bounded interaction trial feedback JSON",arguments="",availability=function() return true,"available" end,state=commandState,
        run=function() local ok,payload=pcall(function() return HttpService:JSONEncode(feedback) end) return ok,ok and payload or "Feedback JSON encoding failed" end},

    eggs={category="Game: Eggs",description="List evidence-backed egg targets",arguments="",availability=function() return true,"available" end,state=commandState,
        run=function() return true,listTargets(true) end},
    egg={category="Game: Eggs",description="Select an evidence-backed egg",arguments="[name]",availability=function() return not running,running and "stop prompt trial first" or "available" end,state=commandState,
        run=function(words) return selectTarget(words,true,"Usage: ;egg [name]") end},
    eggmode={category="Game: Eggs",description="Select auto-single or observed multi target",arguments="[auto|multi]",availability=function() return not running,running and "stop prompt trial first" or "available" end,state=commandState,
        run=function(words) local value=(words[1] or ""):lower() if value~="auto" and value~="multi" then return false,"Usage: ;eggmode [auto|multi]" end if not targets[selected].egg then return false,"Selected target is not an egg interaction" end if value=="multi" and not hasMulti() then return false,"No observed multi-hatch target" end mode=value update() return true,"Egg mode "..value end},
    eggstart={category="Game: Eggs",description="Start selected egg prompt trial",arguments="",availability=function() return targets[selected].egg and type(fireproximityprompt)=="function",targets[selected].egg and "fireproximityprompt unavailable" or "select an egg target" end,state=commandState,run=function() return start() end},
    eggstop={category="Game: Eggs",description="Stop prompt trial",arguments="",availability=function() return true,"available" end,state=commandState,
        run=function() stop("Stopped by command") return true,"Prompt trial stopped" end},
}
_G.LycolesGameStopAll=function() stop("Stopped by ;stopall") end
_G.LycolesPromptClose=function()
    alive=false running=false
    for _,connection in ipairs(connections) do pcall(function() connection:Disconnect() end) end
    if gui then gui:Destroy() end
    _G.LycolesGameCommands=nil _G.LycolesGameStopAll=nil _G.LycolesPromptTrialFeedback=nil
    _G.LycolesPromptState=nil
    if type(_G.LycolesGameStateChanged)=="function" then pcall(_G.LycolesGameStateChanged) end
    _G.LycolesPromptClose=nil _G.LycolesEggClose=nil
end
_G.LycolesEggClose=_G.LycolesPromptClose
update()
end
'''
    return (source.replace("__PLACE_ID__",str(place)).replace("__TARGETS__",target_rows)
        .replace("__SCAN_ID__",_quote(scan_id)).replace("__DISCOVERY_DIGEST__",_quote(discovery_digest)))
