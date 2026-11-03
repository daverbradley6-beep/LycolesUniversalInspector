#!/usr/bin/env python3
"""Generate a reusable local Roblox command bar and Admin Commands GUI."""
import argparse
import json
import pathlib

COMMANDS=("fly","unfly","noclip","clip","tp","goto","speed","jump",
          "coords","systems","readiness","reset","rejoin","cmds","help","stopall","hidegui")


def evidence_summaries(document):
    unavailable=("System candidates: no v110 gameplay-understanding artifact supplied",
                 "Request readiness: no v110 gameplay-understanding artifact supplied")
    if not isinstance(document,dict) or document.get("schemaVersion")!="110.gameplay-understanding.1":
        return unavailable
    raw_systems=document.get("systems")
    if not isinstance(raw_systems,list):raise ValueError("Invalid gameplay systems")
    systems=[]
    for item in raw_systems[:6]:
        if not isinstance(item,dict):raise ValueError("Invalid gameplay system")
        label=item.get("label");tier=item.get("evidenceTier")
        if not isinstance(label,str) or not 1<=len(label)<=160:raise ValueError("Invalid system label")
        if not isinstance(tier,str) or not 1<=len(tier)<=80:raise ValueError("Invalid evidence tier")
        systems.append(label+" ["+tier+"]")
    systems_text="System candidates (unverified): "+(", ".join(systems) if systems else "none")
    request=document.get("requestedCapabilityAssessment")
    if request is None:return systems_text,"Request readiness: no capability requested"
    if not isinstance(request,dict):raise ValueError("Invalid capability assessment")
    status=request.get("status")
    if not isinstance(status,str) or not 1<=len(status)<=100:raise ValueError("Invalid readiness status")
    raw_blockers=request.get("blockers")
    if not isinstance(raw_blockers,list):raise ValueError("Invalid readiness blockers")
    blockers=[]
    for value in raw_blockers[:8]:
        if not isinstance(value,str) or not 1<=len(value)<=120:raise ValueError("Invalid readiness blocker")
        blockers.append(value)
    request_text="Request readiness: "+status+"; implementation ready: false"
    if blockers:request_text+="; blockers: "+", ".join(blockers)
    return systems_text,request_text


def render(place_id,gameplay_understanding=None):
    if type(place_id) is not int or not 1<=place_id<=2**53:
        raise ValueError("Invalid place ID")
    systems_summary,readiness_summary=evidence_summaries(gameplay_understanding)
    tokens=("__LYCOLES_SYSTEMS_SUMMARY_110__","__LYCOLES_READINESS_SUMMARY_110__")
    if any(token in systems_summary or token in readiness_summary for token in tokens):
        raise ValueError("Invalid gameplay summary text")
    return r'''-- Lycoles universal local utility commands; not server administrator privileges.
do
assert(game.PlaceId == PLACE_ID, "Incorrect Roblox place")
local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")
local TeleportService = game:GetService("TeleportService")
local player = Players.LocalPlayer
assert(player, "LocalPlayer unavailable")
if type(_G.LycolesAdminClose) == "function" then pcall(_G.LycolesAdminClose) end
local PREFIX = ";"
local connections = {}
local SYSTEMS_SUMMARY=__LYCOLES_SYSTEMS_SUMMARY_110__
local READINESS_SUMMARY=__LYCOLES_READINESS_SUMMARY_110__

local alive = true
local featureState = {fly=false,noclip=false,speed=nil,jump=nil,hidden=false}
local originalCollision = setmetatable({}, {__mode="k"})
local humanoidOriginals = setmetatable({}, {__mode="k"})
local flyVelocity,flyGyro = nil,nil
local commands,commandNames = {},{}
local commandHistory = {}
local historyIndex = 1
local refreshCommandRows = function() end
local function characterParts()
    local character = player.Character
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    local root = character and character:FindFirstChild("HumanoidRootPart")
    return character,humanoid,root
end
local function rememberHumanoid(humanoid)
    if humanoid and not humanoidOriginals[humanoid] then
        humanoidOriginals[humanoid]={WalkSpeed=humanoid.WalkSpeed,
            JumpPower=humanoid.JumpPower,JumpHeight=humanoid.JumpHeight}
    end
end
local function restoreHumanoid()
    for humanoid,original in pairs(humanoidOriginals) do
        pcall(function()
            humanoid.WalkSpeed=original.WalkSpeed
            humanoid.JumpPower=original.JumpPower
            humanoid.JumpHeight=original.JumpHeight
        end)
    end
    humanoidOriginals=setmetatable({}, {__mode="k"})
    featureState.speed=nil featureState.jump=nil
end
local function clearFlyMovers()
    if flyVelocity then flyVelocity:Destroy() flyVelocity=nil end
    if flyGyro then flyGyro:Destroy() flyGyro=nil end
end
local function setFlyEnabled(enabled)
    featureState.fly=enabled==true
    if not featureState.fly then clearFlyMovers() end
    refreshCommandRows()
end
local function restoreCollision()
    for part,original in pairs(originalCollision) do
        pcall(function() part.CanCollide = original end)
    end
    originalCollision=setmetatable({}, {__mode="k"})
end
local function setNoclipEnabled(enabled)
    featureState.noclip=enabled==true
    if not featureState.noclip then restoreCollision() end
    refreshCommandRows()
end
local function stopAll()
    setFlyEnabled(false)
    setNoclipEnabled(false)
    restoreHumanoid()
    refreshCommandRows()
end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesAdminCommands"
gui.ResetOnSpawn=false
gui.Parent=player:WaitForChild("PlayerGui")
local commandBar=Instance.new("Frame")
commandBar.Name="CommandBar"
commandBar.AnchorPoint=Vector2.new(.5,0)
commandBar.Position = UDim2.new(0.5,0,0,14)
commandBar.Size=UDim2.fromOffset(540,66)
commandBar.BackgroundColor3=Color3.fromRGB(23,27,35)
commandBar.Visible=false
commandBar.Parent=gui
local commandInput=Instance.new("TextBox")
commandInput.Size=UDim2.new(1,-20,0,32)
commandInput.Position=UDim2.fromOffset(10,7)
commandInput.BackgroundColor3=Color3.fromRGB(38,45,57)
commandInput.TextColor3=Color3.new(1,1,1)
commandInput.PlaceholderText=";command [arguments]  •  RightBracket toggles"
commandInput.ClearTextOnFocus=false
commandInput.TextXAlignment=Enum.TextXAlignment.Left
commandInput.Parent=commandBar
local suggestion=Instance.new("TextLabel")
suggestion.Size=UDim2.new(1,-20,0,18)
suggestion.Position=UDim2.fromOffset(10,43)
suggestion.BackgroundTransparency=1
suggestion.TextColor3=Color3.fromRGB(156,185,210)
suggestion.TextXAlignment=Enum.TextXAlignment.Left
suggestion.Text="Type ;cmds for available local commands"
suggestion.Parent=commandBar
local panel=Instance.new("Frame")
panel.Name="AdminCommands"
panel.Size=UDim2.fromOffset(520,500)
panel.Position=UDim2.new(1,-540,.5,-250)
panel.BackgroundColor3=Color3.fromRGB(25,30,39)
panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-55,0,40)
title.Position=UDim2.fromOffset(12,5)
title.BackgroundTransparency=1
title.Text="Admin Commands | local utilities"
title.TextColor3=Color3.new(1,1,1)
title.TextXAlignment=Enum.TextXAlignment.Left
title.Parent=panel
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(34,28)
close.Position=UDim2.new(1,-42,0,8)
close.Text="X"
close.Parent=panel
local feedback=Instance.new("TextLabel")
feedback.Size=UDim2.new(1,-24,0,54)
feedback.Position=UDim2.fromOffset(12,48)
feedback.BackgroundColor3=Color3.fromRGB(34,40,50)
feedback.TextColor3=Color3.fromRGB(230,236,242)
feedback.TextWrapped=true
feedback.Text="Commands affect this client only and may be overridden by game restrictions."
feedback.Parent=panel
local commandList=Instance.new("ScrollingFrame")
commandList.Position=UDim2.fromOffset(12,112)
commandList.Size=UDim2.new(1,-24,1,-124)
commandList.BackgroundTransparency=1
commandList.ScrollBarThickness=6
commandList.AutomaticCanvasSize=Enum.AutomaticSize.Y
commandList.CanvasSize=UDim2.new()
commandList.Parent=panel
local listLayout=Instance.new("UIListLayout")
listLayout.Padding=UDim.new(0,6)
listLayout.Parent=commandList
local rows={}
local function setFeedback(ok,message)
    feedback.TextColor3=ok and Color3.fromRGB(157,235,177) or Color3.fromRGB(255,171,171)
    feedback.Text=tostring(message)
end
local function register(name,definition)
    if commands[name] then error("Duplicate command "..name) end
    commands[name]=definition
    table.insert(commandNames,name)
end
local function available()
    return true,"available"
end
local function currentState(name)
    if name=="fly" or name=="unfly" then return featureState.fly and "on" or "off" end
    if name=="noclip" or name=="clip" then return featureState.noclip and "on" or "off" end
    if name=="speed" then return featureState.speed and tostring(featureState.speed) or "default" end
    if name=="jump" then return featureState.jump and tostring(featureState.jump) or "default" end
    if name=="hidegui" then return featureState.hidden and "hidden" or "visible" end
    return "ready"
end
local function numeric(value,minimum,maximum)
    local result=tonumber(value)
    if not result or result<minimum or result>maximum then return nil end
    return result
end
register("fly",{category="Movement",description="Enable local directional flight",arguments="",availability=available,
    run=function() setFlyEnabled(true) return true,"Fly enabled" end})
register("unfly",{category="Movement",description="Disable local flight",arguments="",availability=available,
    run=function() setFlyEnabled(false) return true,"Fly disabled" end})
register("noclip",{category="Movement",description="Disable local character collisions while active",arguments="",availability=available,
    run=function() setNoclipEnabled(true) return true,"Noclip enabled" end})
register("clip",{category="Movement",description="Restore recorded collision states",arguments="",availability=available,
    run=function() setNoclipEnabled(false) return true,"Collision restored" end})
register("speed",{category="Movement",description="Set local humanoid walk speed",arguments="[0-250]",availability=available,
    run=function(args)
        local value=numeric(args[1],0,250)
        if not value then return false,"Usage: ;speed [0-250]" end
        local _,humanoid=characterParts()
        if not humanoid then return false,"Humanoid unavailable" end
        rememberHumanoid(humanoid) humanoid.WalkSpeed=value featureState.speed=value
        refreshCommandRows() return true,"WalkSpeed set to "..tostring(value)
    end})
register("jump",{category="Movement",description="Set local humanoid jump value",arguments="[0-300]",availability=available,
    run=function(args)
        local value=numeric(args[1],0,300)
        if not value then return false,"Usage: ;jump [0-300]" end
        local _,humanoid=characterParts()
        if not humanoid then return false,"Humanoid unavailable" end
        rememberHumanoid(humanoid)
        if humanoid.UseJumpPower then humanoid.JumpPower=value else humanoid.JumpHeight=value end
        featureState.jump=value refreshCommandRows()
        return true,"Jump value set to "..tostring(value)
    end})
register("tp",{category="Movement",description="Move local character to coordinates",arguments="[x] [y] [z]",availability=available,
    run=function(args)
        local x,y,z=tonumber(args[1]),tonumber(args[2]),tonumber(args[3])
        if not x or not y or not z or math.abs(x)>1e7 or math.abs(y)>1e7 or math.abs(z)>1e7 then
            return false,"Usage: ;tp [x] [y] [z]" end
        local _,_,root=characterParts()
        if not root then return false,"HumanoidRootPart unavailable" end
        root.CFrame=CFrame.new(x,y,z)
        return true,"Moved local character to coordinates"
    end})
register("goto",{category="Movement",description="Move local character to an unambiguous player",arguments="[player]",availability=available,
    run=function(args)
        local query=table.concat(args," "):lower()
        if query=="" then return false,"Usage: ;goto [player]" end
        local matches={}
        for _,candidate in ipairs(Players:GetPlayers()) do
            if candidate~=player and (candidate.Name:lower():sub(1,#query)==query
                or candidate.DisplayName:lower():sub(1,#query)==query) then table.insert(matches,candidate) end
        end
        if #matches~=1 then return false,#matches==0 and "Player not found" or "Player name is ambiguous" end
        local _,_,root=characterParts()
        local target=matches[1].Character and matches[1].Character:FindFirstChild("HumanoidRootPart")
        if not root or not target then return false,"Character root unavailable" end
        root.CFrame=target.CFrame*CFrame.new(0,0,3)
        return true,"Moved to "..matches[1].Name
    end})
register("coords",{category="Information",description="Show local character coordinates",arguments="",availability=available,
    run=function()
        local _,_,root=characterParts()
        if not root then return false,"HumanoidRootPart unavailable" end
        local p=root.Position
        return true,string.format("X %.2f  Y %.2f  Z %.2f",p.X,p.Y,p.Z)
    end})
register("systems",{category="Information",description="Show unverified client-evidence system candidates",arguments="",availability=available,
    run=function() return true,SYSTEMS_SUMMARY end})
register("readiness",{category="Information",description="Show fail-closed requested-capability readiness",arguments="",availability=available,
    run=function() return true,READINESS_SUMMARY end})
register("reset",{category="Session",description="Request local character reset",arguments="",availability=available,
    run=function()
        local _,humanoid=characterParts()
        if not humanoid then return false,"Humanoid unavailable" end
        humanoid.Health=0 return true,"Reset requested; server rules may override it"
    end})
register("rejoin",{category="Session",description="Request rejoin of this place",arguments="",availability=available,
    run=function()
        local ok,err=pcall(function() TeleportService:Teleport(game.PlaceId,player) end)
        return ok,ok and "Rejoin requested" or ("Rejoin failed: "..tostring(err))
    end})
register("cmds",{category="Information",description="List available local commands",arguments="",availability=available,
    run=function() return true,table.concat(commandNames,", ") end})
register("help",{category="Information",description="Show command description and arguments",arguments="[command]",availability=available,
    run=function(args)
        local name=(args[1] or ""):lower()
        local command=commands[name]
        if not command then return false,"Usage: ;help [command]" end
        return true,PREFIX..name.." "..command.arguments.." — "..command.description
    end})
register("stopall",{category="Session",description="Stop Lycoles movement utilities and restore state",arguments="",availability=available,
    run=function() stopAll() return true,"Lycoles local utilities stopped" end})
register("hidegui",{category="Interface",description="Toggle generated utility panels; command bar remains available",arguments="",availability=available,
    run=function()
        featureState.hidden=not featureState.hidden
        panel.Visible=not featureState.hidden
        for _,name in ipairs({"LycolesGeneratedUtility","LycolesReviewedActions"}) do
            local generated=player.PlayerGui:FindFirstChild(name)
            if generated then generated.Enabled=not featureState.hidden end
        end
        refreshCommandRows()
        return true,featureState.hidden and "Generated GUI hidden" or "Generated GUI visible"
    end})
table.sort(commandNames)
local function execute(raw)
    raw=tostring(raw or ""):match("^%s*(.-)%s*$")
    if raw:sub(1,1)==PREFIX then raw=raw:sub(2) end
    local words={}
    for word in raw:gmatch("%S+") do table.insert(words,word) end
    local name=table.remove(words,1)
    if not name then return false,"Enter a command" end
    name=name:lower()
    local command=commands[name]
    if not command then return false,"Unknown command ;"..name..". Use ;cmds" end
    local okAvailable,reason=command.availability()
    if not okAvailable then return false,reason or "Command unavailable" end
    local ok,success,message=pcall(command.run,words)
    if not ok then return false,"Command failed: "..tostring(success) end
    refreshCommandRows()
    return success==true,message or (success and "Command completed" or "Command failed")
end
local function submit(raw)
    if not raw or raw:match("^%s*$") then return end
    table.insert(commandHistory,raw)
    if #commandHistory>50 then table.remove(commandHistory,1) end
    historyIndex=#commandHistory+1
    local ok,message=execute(raw)
    setFeedback(ok,message)
    commandInput.Text=""
end
local function updateAutocomplete()
    local raw=commandInput.Text or ""
    local prefix=raw:match("^%s*;?([%w_]*)") or ""
    if prefix=="" then suggestion.Text="Type ;cmds for available local commands" return end
    local matches={}
    for _,name in ipairs(commandNames) do
        if name:sub(1,#prefix:lower())==prefix:lower() then table.insert(matches,";"..name) end
        if #matches>=6 then break end
    end
    suggestion.Text=#matches>0 and table.concat(matches,"   ") or "No matching command"
end
refreshCommandRows=function()
    for name,row in pairs(rows) do
        local command=commands[name]
        local ok,reason=command.availability()
        row.Text=PREFIX..name..(command.arguments~="" and " "..command.arguments or "")
            .."\n"..command.description.."\nAvailability: "..(ok and "available" or tostring(reason))
            .."  •  State: "..currentState(name)
        row.BackgroundColor3=ok and Color3.fromRGB(45,65,82) or Color3.fromRGB(74,49,52)
    end
end
local categories={Movement={},Information={},Session={},Interface={}}
for _,name in ipairs(commandNames) do table.insert(categories[commands[name].category],name) end
for _,category in ipairs({"Movement","Information","Session","Interface"}) do
    local header=Instance.new("TextLabel")
    header.Size=UDim2.new(1,-8,0,30)
    header.BackgroundColor3=Color3.fromRGB(38,46,58)
    header.TextColor3=Color3.fromRGB(155,204,238)
    header.TextXAlignment=Enum.TextXAlignment.Left
    header.Text="  "..category
    header.Parent=commandList
    for _,name in ipairs(categories[category]) do
        local row=Instance.new("TextButton")
        row.Name=name
        row.Size=UDim2.new(1,-8,0,68)
        row.TextWrapped=true
        row.TextXAlignment=Enum.TextXAlignment.Left
        row.TextColor3=Color3.new(1,1,1)
        row.Parent=commandList
        rows[name]=row
        table.insert(connections,row.MouseButton1Click:Connect(function()
            commandBar.Visible=true commandInput.Text=PREFIX..name.." " commandInput:CaptureFocus()
        end))
    end
end
refreshCommandRows()
table.insert(connections,commandInput:GetPropertyChangedSignal("Text"):Connect(updateAutocomplete))
table.insert(connections,commandInput.FocusLost:Connect(function(enterPressed)
    if enterPressed then submit(commandInput.Text) end
end))
table.insert(connections,UserInputService.InputBegan:Connect(function(input,processed)
    if input.KeyCode==Enum.KeyCode.RightBracket and not processed then
        commandBar.Visible=not commandBar.Visible
        if commandBar.Visible then commandInput:CaptureFocus() else commandInput:ReleaseFocus() end
    elseif commandInput:IsFocused() and input.KeyCode==Enum.KeyCode.Up then
        historyIndex=math.max(1,historyIndex-1)
        commandInput.Text=commandHistory[historyIndex] or commandInput.Text
        commandInput.CursorPosition=#commandInput.Text+1
    elseif commandInput:IsFocused() and input.KeyCode==Enum.KeyCode.Down then
        historyIndex=math.min(#commandHistory+1,historyIndex+1)
        commandInput.Text=commandHistory[historyIndex] or ""
        commandInput.CursorPosition=#commandInput.Text+1
    end
end))
table.insert(connections,player.Chatted:Connect(function(message)
    if message:sub(1,1)==PREFIX then submit(message) end
end))
table.insert(connections,RunService.Heartbeat:Connect(function()
    if not alive then return end
    local character,humanoid,root=characterParts()
    if humanoid then
        if featureState.speed then rememberHumanoid(humanoid) humanoid.WalkSpeed=featureState.speed end
        if featureState.jump then
            rememberHumanoid(humanoid)
            if humanoid.UseJumpPower then humanoid.JumpPower=featureState.jump else humanoid.JumpHeight=featureState.jump end
        end
    end
    if featureState.noclip and character then
        for _,part in ipairs(character:GetDescendants()) do
            if part:IsA("BasePart") then
                if originalCollision[part]==nil then originalCollision[part]=part.CanCollide end
                part.CanCollide=false
            end
        end
    end
    if featureState.fly and root then
        if not flyVelocity or flyVelocity.Parent~=root then
            clearFlyMovers()
            flyVelocity=Instance.new("BodyVelocity")
            flyVelocity.Name="LycolesFlyVelocity"
            flyVelocity.MaxForce=Vector3.new(1e6,1e6,1e6)
            flyVelocity.Parent=root
            flyGyro=Instance.new("BodyGyro")
            flyGyro.Name="LycolesFlyGyro"
            flyGyro.MaxTorque=Vector3.new(1e6,1e6,1e6)
            flyGyro.P=9000
            flyGyro.Parent=root
        end
        local camera=workspace.CurrentCamera
        local direction=Vector3.zero
        if camera then
            if UserInputService:IsKeyDown(Enum.KeyCode.W) then direction+=camera.CFrame.LookVector end
            if UserInputService:IsKeyDown(Enum.KeyCode.S) then direction-=camera.CFrame.LookVector end
            if UserInputService:IsKeyDown(Enum.KeyCode.D) then direction+=camera.CFrame.RightVector end
            if UserInputService:IsKeyDown(Enum.KeyCode.A) then direction-=camera.CFrame.RightVector end
            if UserInputService:IsKeyDown(Enum.KeyCode.Space) then direction+=Vector3.yAxis end
            if UserInputService:IsKeyDown(Enum.KeyCode.LeftControl) then direction-=Vector3.yAxis end
            flyGyro.CFrame=camera.CFrame
        end
        flyVelocity.Velocity=direction.Magnitude>0 and direction.Unit*70 or Vector3.zero
    elseif flyVelocity or flyGyro then clearFlyMovers() end
end))
_G.LycolesAdminClose=function()
    if not alive then return end
    alive=false
    stopAll()
    for _,connection in ipairs(connections) do pcall(function() connection:Disconnect() end) end
    gui:Destroy()
    _G.LycolesAdminClose=nil
end
table.insert(connections,close.MouseButton1Click:Connect(_G.LycolesAdminClose))
setFeedback(true,"Ready. Press RightBracket or use ;cmds in chat where supported.")
end
'''.replace("PLACE_ID",str(place_id)).replace(
        "__LYCOLES_SYSTEMS_SUMMARY_110__",json.dumps(systems_summary,ensure_ascii=True)).replace(
        "__LYCOLES_READINESS_SUMMARY_110__",json.dumps(readiness_summary,ensure_ascii=True))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--place-id",type=int,required=True)
    parser.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/LycolesAdminCommands.lua"))
    args=parser.parse_args()
    source=render(args.place_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(source,encoding="utf-8")


if __name__=="__main__":main()
