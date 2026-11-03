#!/usr/bin/env python3
"""Generate place-bound ProximityPrompt trials from correlated observable evidence."""
import json


def _quote(value):
    return json.dumps(str(value),ensure_ascii=False)


def _identity_lua(value):
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
    if value[-1]["className"]!="ProximityPrompt":raise ValueError("Malformed correlated prompt target")
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
            metadata=json.dumps(item.get("promptMetadata",{}),ensure_ascii=False).lower()
            haystack=(label+" "+path+" "+metadata).lower()
            is_egg="egg" in haystack or "hatch" in haystack
            multi=is_egg and any(token in haystack for token in ("multi","triple","x3","3 egg","three"))
            objective=item.get("objective") if isinstance(item.get("objective"),dict) else {}
            score=objective.get("score",0)
            if type(score) is not int:raise ValueError("Malformed prompt objective")
            targets.append((label,path,signal["key"],signal["change"],multi,is_egg,
                str(item.get("featureCandidate") or "other")[:80],score,
                _identity_lua(item.get("pathIdentity")),_state_identity_lua(signal.get("stateIdentity"))))
    elif egg.get("automaticSingleTrialReady") is True:
        for item in egg.get("targets",[]):
            if not isinstance(item,dict) or item.get("incrementObservations",0)<1:continue
            path=item.get("path");label=item.get("label");keys=item.get("outcomeKeys")
            if not isinstance(path,str) or not isinstance(label,str) or not isinstance(keys,list) or not keys:continue
            identities=item.get("outcomeIdentities",{})
            metadata=json.dumps(item.get("promptMetadata",{}),ensure_ascii=False).lower()
            multi=any(token in (label+" "+metadata).lower() for token in ("multi","triple","x3","3 egg","three"))
            targets.append((label,path,keys[0],"increased",multi,True,"pets",0,
                _identity_lua(item.get("pathIdentity")),_state_identity_lua(identities.get(keys[0]))))
    if not targets:return None
    targets.sort(key=lambda item:(-item[7],item[0].lower(),item[1]))
    target_rows="\n".join("    {label="+_quote(label)+",path="+_quote(path)+
        ",outcome="+_quote(outcome)+",expected="+_quote(expected)+
        ",multi="+("true" if multi else "false")+",egg="+("true" if is_egg else "false")+
        ",feature="+_quote(feature)+",objectiveScore="+str(score)+
        ",identity="+identity+",outcomeIdentity="+outcome_identity+"},"
        for label,path,outcome,expected,multi,is_egg,feature,score,identity,outcome_identity in targets)
    source=r'''-- Evidence-bounded ProximityPrompt trials; outcome changes are observed, not causal proof.
do
assert(game.PlaceId == __PLACE_ID__, "Incorrect Roblox place")
local Players=game:GetService("Players")
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
local connections={}
local gui=Instance.new("ScreenGui")
gui.Name="LycolesPromptInteractions"
gui.ResetOnSpawn=false
gui.Parent=player:WaitForChild("PlayerGui")
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(360,220)
panel.Position=UDim2.new(.5,-180,.5,-110)
panel.BackgroundColor3=Color3.fromRGB(24,30,39)
panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-20,0,32) title.Position=UDim2.fromOffset(10,6)
title.BackgroundTransparency=1 title.TextColor3=Color3.new(1,1,1)
title.Text="Prompt Interactions | evidence-bounded trial" title.Parent=panel
local targetButton=Instance.new("TextButton")
targetButton.Size=UDim2.new(1,-20,0,38) targetButton.Position=UDim2.fromOffset(10,45)
targetButton.Parent=panel
local modeButton=Instance.new("TextButton")
modeButton.Size=UDim2.new(.5,-15,0,38) modeButton.Position=UDim2.fromOffset(10,90)
modeButton.Parent=panel
local toggle=Instance.new("TextButton")
toggle.Size=UDim2.new(.5,-15,0,38) toggle.Position=UDim2.new(.5,5,0,90)
toggle.Parent=panel
local status=Instance.new("TextLabel")
status.Size=UDim2.new(1,-20,0,76) status.Position=UDim2.fromOffset(10,136)
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
    targetButton.Text="Interaction: "..target.label.." ["..target.feature.."]  (click to change)"
    if target.egg then modeButton.Text=mode=="multi" and "Mode: MULTI" or "Mode: AUTO SINGLE"
    else modeButton.Text="Mode: REPEAT TRIAL" end
    toggle.Text=running and "STOP" or "START"
end
local function stop(reason)
    running=false update()
    if reason then status.Text=reason end
end
local function activateOnce()
    local target=currentTarget()
    if not target then return false,"No evidence-backed target for mode" end
    local prompt,err=resolve(target)
    if not prompt or not prompt:IsA("ProximityPrompt") then return false,err or "Target is not a ProximityPrompt" end
    if not prompt.Enabled then return false,"Observed prompt is currently disabled" end
    if type(fireproximityprompt)~="function" then return false,"fireproximityprompt unavailable in this environment" end
    local moved,moveError=teleportTo(prompt)
    if not moved then return false,moveError end
    local before=readOutcome(target)
    local ok,fireError=pcall(function() fireproximityprompt(prompt) end)
    if not ok then return false,"Prompt activation failed: "..tostring(fireError) end
    task.wait(1.5)
    local after=readOutcome(target)
    local observed=target.expected=="increased" and type(before)=="number" and type(after)=="number" and after>before
        or target.expected=="decreased" and type(before)=="number" and type(after)=="number" and after<before
        or target.expected=="changed" and before~=nil and after~=nil and after~=before
    if observed then
        failures=0
        status.Text="Observed "..target.outcome.." "..target.expected.." "..tostring(before).." → "..tostring(after)
            ..". This is runtime correlation, not server-authority or causal proof."
        return true,nil
    end
    return false,"No expected "..target.expected.." outcome observed"
end
local function start()
    if running then return true,"Prompt trial already running" end
    if type(fireproximityprompt)~="function" then return false,"fireproximityprompt unavailable in this environment" end
    if mode=="multi" and not currentTarget() then return false,"No observed multi-hatch target" end
    running=true failures=0 update()
    task.spawn(function()
        while alive and running do
            local ok,message=activateOnce()
            if not ok then
                failures=failures+1 status.Text=message.." (attempt "..tostring(failures).."/3)"
                if failures>=3 then stop("Stopped after 3 uncorroborated attempts. "..message) break end
            end
            task.wait(.4)
        end
    end)
    return true,"Prompt interaction trial started"
end
local function hasMulti()
    for _,target in ipairs(targets) do if target.multi then return true end end return false
end
table.insert(connections,targetButton.MouseButton1Click:Connect(function()
    if running then return end selected=selected%#targets+1 mode="auto" update()
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
_G.LycolesGameCommands={
    interactions={category="Game: Interactions",description="List evidence-backed prompt targets",arguments="",availability=function() return true,"available" end,
        run=function() return true,listTargets(false) end},
    interaction={category="Game: Interactions",description="Select an evidence-backed prompt target",arguments="[name]",availability=function() return not running,running and "stop prompt trial first" or "available" end,
        run=function(words) return selectTarget(words,false,"Usage: ;interaction [name]") end},
    interactionstart={category="Game: Interactions",description="Start selected prompt trial",arguments="",availability=function() return type(fireproximityprompt)=="function","fireproximityprompt unavailable" end,run=function() return start() end},
    interactionstop={category="Game: Interactions",description="Stop prompt trial",arguments="",availability=function() return true,"available" end,
        run=function() stop("Stopped by command") return true,"Prompt trial stopped" end},
    eggs={category="Game: Eggs",description="List evidence-backed egg targets",arguments="",availability=function() return true,"available" end,
        run=function() return true,listTargets(true) end},
    egg={category="Game: Eggs",description="Select an evidence-backed egg",arguments="[name]",availability=function() return not running,running and "stop prompt trial first" or "available" end,
        run=function(words) return selectTarget(words,true,"Usage: ;egg [name]") end},
    eggmode={category="Game: Eggs",description="Select auto-single or observed multi target",arguments="[auto|multi]",availability=function() return not running,running and "stop prompt trial first" or "available" end,
        run=function(words) local value=(words[1] or ""):lower() if value~="auto" and value~="multi" then return false,"Usage: ;eggmode [auto|multi]" end if not targets[selected].egg then return false,"Selected target is not an egg interaction" end if value=="multi" and not hasMulti() then return false,"No observed multi-hatch target" end mode=value update() return true,"Egg mode "..value end},
    eggstart={category="Game: Eggs",description="Start selected egg prompt trial",arguments="",availability=function() return targets[selected].egg and type(fireproximityprompt)=="function",targets[selected].egg and "fireproximityprompt unavailable" or "select an egg target" end,run=function() return start() end},
    eggstop={category="Game: Eggs",description="Stop prompt trial",arguments="",availability=function() return true,"available" end,
        run=function() stop("Stopped by command") return true,"Prompt trial stopped" end},
}
_G.LycolesGameStopAll=function() stop("Stopped by ;stopall") end
_G.LycolesPromptClose=function()
    alive=false running=false
    for _,connection in ipairs(connections) do pcall(function() connection:Disconnect() end) end
    if gui then gui:Destroy() end
    _G.LycolesGameCommands=nil _G.LycolesGameStopAll=nil _G.LycolesPromptClose=nil _G.LycolesEggClose=nil
end
_G.LycolesEggClose=_G.LycolesPromptClose
update()
end
'''
    return source.replace("__PLACE_ID__",str(place)).replace("__TARGETS__",target_rows)
