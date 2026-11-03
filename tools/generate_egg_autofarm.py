#!/usr/bin/env python3
"""Generate a place-bound egg autofarm trial from correlated prompt evidence."""
import json


def _quote(value):
    return json.dumps(str(value),ensure_ascii=False)


def render(discovery):
    if not isinstance(discovery,dict) or discovery.get("schemaVersion")!="111.action-capabilities.1":
        raise ValueError("Action capability discovery required")
    place=discovery.get("placeId");egg=discovery.get("eggHatching");claims=discovery.get("claims")
    if type(place) is not int or not isinstance(egg,dict) or not isinstance(claims,dict):
        raise ValueError("Malformed action capability discovery")
    if any(claims.get(key) is not False for key in ("sourceAuthenticityVerified","causalityProven",
            "serverAuthorityVerified","runtimeVerified","gameplayVerified","actionOutcomesVerified")):
        raise ValueError("Action capability discovery claims unsupported verification")
    if egg.get("automaticSingleTrialReady") is not True:return None
    targets=[]
    for item in egg.get("targets",[]):
        if not isinstance(item,dict) or item.get("incrementObservations",0)<1:continue
        path=item.get("path");label=item.get("label");keys=item.get("outcomeKeys")
        if (not isinstance(path,str) or not isinstance(label,str) or not isinstance(keys,list)
                or not keys or not all(isinstance(key,str) for key in keys)
                or item.get("controlType")!="ProximityPrompt.Triggered"
                or item.get("evidenceTier")!="temporal-state-increment-observed"
                or type(item.get("observedTriggers")) is not int or item["observedTriggers"]<1
                or any(item.get(key) is not False for key in
                    ("causalityProven","runtimeVerified","gameplayVerified"))):
            raise ValueError("Malformed correlated egg target")
        metadata=json.dumps(item.get("promptMetadata",{}),ensure_ascii=False).lower()
        multi=any(token in (label+" "+metadata).lower() for token in ("multi","triple","x3","3 egg","three"))
        targets.append((label,path,keys[0],multi))
    if not targets:return None
    target_rows="\n".join("    {label="+_quote(label)+",path="+_quote(path)+
        ",outcome="+_quote(outcome)+",multi="+("true" if multi else "false")+"},"
        for label,path,outcome,multi in targets)
    source=r'''-- Evidence-bounded egg autofarm trial; counter changes are observed, not causal proof.
do
assert(game.PlaceId == __PLACE_ID__, "Incorrect Roblox place")
local Players=game:GetService("Players")
local player=Players.LocalPlayer
assert(player,"LocalPlayer unavailable")
if type(_G.LycolesEggClose)=="function" then pcall(_G.LycolesEggClose) end
local targets={
__TARGETS__
}
local alive,running=true,false
local selected=1
local mode="auto"
local failures=0
local connections={}
local gui=Instance.new("ScreenGui")
gui.Name="LycolesEggAutofarm"
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
title.Text="Egg Autofarm | evidence-bounded trial" title.Parent=panel
local eggButton=Instance.new("TextButton")
eggButton.Size=UDim2.new(1,-20,0,38) eggButton.Position=UDim2.fromOffset(10,45)
eggButton.Parent=panel
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
local function resolve(path)
    local parts=split(path)
    local roots={Workspace=workspace,LocalPlayer=player,
        ReplicatedStorage=game:GetService("ReplicatedStorage"),Players=Players}
    local current=roots[parts[1]]
    if not current then return nil,"Unsupported root "..tostring(parts[1]) end
    for index=2,#parts do
        current=current:FindFirstChild(parts[index])
        if not current then return nil,"Missing path segment "..parts[index] end
    end
    return current,nil
end
local function readOutcome(key)
    local parts=split(key)
    local current=parts[1]=="leaderstats" and player:FindFirstChild("leaderstats")
        or parts[1]=="Data" and player:FindFirstChild("Data") or nil
    if not current then return nil end
    for index=2,#parts do current=current:FindFirstChild(parts[index]) if not current then return nil end end
    if not current:IsA("ValueBase") then return nil end
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
    if not anchor then return false,"Egg prompt has no nearby BasePart" end
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
    eggButton.Text="Egg: "..target.label.."  (click to change)"
    modeButton.Text=mode=="multi" and "Mode: MULTI" or "Mode: AUTO SINGLE"
    toggle.Text=running and "STOP" or "START"
end
local function stop(reason)
    running=false update()
    if reason then status.Text=reason end
end
local function activateOnce()
    local target=currentTarget()
    if not target then return false,"No evidence-backed target for mode" end
    local prompt,err=resolve(target.path)
    if not prompt or not prompt:IsA("ProximityPrompt") then return false,err or "Target is not a ProximityPrompt" end
    if type(fireproximityprompt)~="function" then return false,"fireproximityprompt unavailable in this environment" end
    local moved,moveError=teleportTo(prompt)
    if not moved then return false,moveError end
    local before=readOutcome(target.outcome)
    local ok,fireError=pcall(function() fireproximityprompt(prompt) end)
    if not ok then return false,"Prompt activation failed: "..tostring(fireError) end
    task.wait(1.5)
    local after=readOutcome(target.outcome)
    if type(before)=="number" and type(after)=="number" and after>before then
        failures=0
        status.Text="Observed "..target.outcome.." increase "..tostring(before).." → "..tostring(after)
            ..". This is runtime correlation, not server-authority or causal proof."
        return true,nil
    end
    return false,"No expected counter increase observed"
end
local function start()
    if running then return true,"Egg autofarm already running" end
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
    return true,"Egg autofarm trial started"
end
local function hasMulti()
    for _,target in ipairs(targets) do if target.multi then return true end end return false
end
table.insert(connections,eggButton.MouseButton1Click:Connect(function()
    if running then return end selected=selected%#targets+1 update()
end))
table.insert(connections,modeButton.MouseButton1Click:Connect(function()
    if running then return end
    if not hasMulti() then status.Text="Multi unavailable: no distinct observed multi-hatch prompt." return end
    mode=mode=="multi" and "auto" or "multi" update()
end))
table.insert(connections,toggle.MouseButton1Click:Connect(function()
    if running then stop("Stopped by user") else local ok,message=start() status.Text=message end
end))
_G.LycolesGameCommands={
    eggs={category="Game: Eggs",description="List evidence-backed egg targets",arguments="",availability=function() return true,"available" end,
        run=function() local names={} for _,target in ipairs(targets) do table.insert(names,target.label) end return true,table.concat(names,", ") end},
    egg={category="Game: Eggs",description="Select an evidence-backed egg",arguments="[name]",availability=function() return not running,running and "stop autofarm first" or "available" end,
        run=function(words) local query=table.concat(words," "):lower() if query=="" then return false,"Usage: ;egg [name]" end for index,target in ipairs(targets) do if target.label:lower():find(query,1,true) then selected=index mode="auto" update() return true,"Selected "..target.label end end return false,"Egg target not found" end},
    eggmode={category="Game: Eggs",description="Select auto-single or observed multi target",arguments="[auto|multi]",availability=function() return not running,running and "stop autofarm first" or "available" end,
        run=function(words) local value=(words[1] or ""):lower() if value~="auto" and value~="multi" then return false,"Usage: ;eggmode [auto|multi]" end if value=="multi" and not hasMulti() then return false,"No observed multi-hatch target" end mode=value update() return true,"Egg mode "..value end},
    eggstart={category="Game: Eggs",description="Start evidence-backed prompt loop",arguments="",availability=function() return type(fireproximityprompt)=="function","fireproximityprompt unavailable" end,run=function() return start() end},
    eggstop={category="Game: Eggs",description="Stop egg prompt loop",arguments="",availability=function() return true,"available" end,run=function() stop("Stopped by command") return true,"Egg autofarm stopped" end},
}
_G.LycolesGameStopAll=function() stop("Stopped by ;stopall") end
_G.LycolesEggClose=function()
    alive=false running=false
    for _,connection in ipairs(connections) do pcall(function() connection:Disconnect() end) end
    if gui then gui:Destroy() end
    _G.LycolesGameCommands=nil _G.LycolesGameStopAll=nil _G.LycolesEggClose=nil
end
update()
end
'''
    return source.replace("__PLACE_ID__",str(place)).replace("__TARGETS__",target_rows)
