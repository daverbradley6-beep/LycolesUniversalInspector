#!/usr/bin/env python3
"""Run generated Admin Commands in bounded Roblox client stubs.

Successful execution is deterministic simulation evidence, not live Roblox verification.
"""
import json
from pathlib import Path

from controlled_luau_v108 import ControlledExecutionError, run_bounded_program
from generate_admin_commands import render

SCHEMA_VERSION="110.controlled-admin-commands.1"

STUBS=r'''
local _G={}
local function signal()
    local value={callbacks={}}
    function value:Connect(callback)
        table.insert(self.callbacks,callback)
        local connected=true
        return {Disconnect=function()
            if not connected then return end
            connected=false
            for index,item in ipairs(value.callbacks) do
                if item==callback then table.remove(value.callbacks,index) break end
            end
        end}
    end
    function value:Fire(...)
        for _,callback in ipairs(table.clone(self.callbacks)) do callback(...) end
    end
    return value
end
local vectorMeta={}
function vectorMeta.__index(self,key)
    if key=="Magnitude" then return math.sqrt(self.X*self.X+self.Y*self.Y+self.Z*self.Z) end
    if key=="Unit" then
        local magnitude=self.Magnitude
        if magnitude==0 then return setmetatable({X=0,Y=0,Z=0},vectorMeta) end
        return setmetatable({X=self.X/magnitude,Y=self.Y/magnitude,Z=self.Z/magnitude},vectorMeta)
    end
end
function vectorMeta.__add(a,b) return setmetatable({X=a.X+b.X,Y=a.Y+b.Y,Z=a.Z+b.Z},vectorMeta) end
function vectorMeta.__sub(a,b) return setmetatable({X=a.X-b.X,Y=a.Y-b.Y,Z=a.Z-b.Z},vectorMeta) end
function vectorMeta.__mul(a,b)
    if type(a)=="number" then a,b=b,a end
    return setmetatable({X=a.X*b,Y=a.Y*b,Z=a.Z*b},vectorMeta)
end
Vector3={new=function(x,y,z) return setmetatable({X=x,Y=y,Z=z},vectorMeta) end}
Vector3.zero=Vector3.new(0,0,0);Vector3.yAxis=Vector3.new(0,1,0)
Vector2={new=function(x,y) return {X=x,Y=y} end}
local cframeMeta={__mul=function(_,other) return other end}
CFrame={new=function(a,b,c)
    local position=type(a)=="table" and a or Vector3.new(a or 0,b or 0,c or 0)
    return setmetatable({Position=position,LookVector=Vector3.new(0,0,-1),RightVector=Vector3.new(1,0,0)},cframeMeta)
end}
UDim={new=function(scale,offset) return {Scale=scale,Offset=offset} end}
UDim2={new=function(xs,xo,ys,yo) return {X={Scale=xs,Offset=xo},Y={Scale=ys,Offset=yo}} end,
       fromOffset=function(x,y) return {X={Scale=0,Offset=x},Y={Scale=0,Offset=y}} end}
Color3={fromRGB=function(r,g,b) return {R=r,G=g,B=b} end,new=function(r,g,b) return {R=r,G=g,B=b} end}
Enum={KeyCode={},UserInputType={},TextXAlignment={Left="Left"},TextYAlignment={Top="Top"},
      Font={GothamBold="GothamBold"},AutomaticSize={Y="Y"},
      HumanoidStateType={Jumping="Jumping"}}
for _,name in ipairs({"RightBracket","Semicolon","W","A","S","D","Space","LeftControl","Escape","Up","Down"}) do Enum.KeyCode[name]=name end
Enum.UserInputType.MouseButton1="MouseButton1";Enum.UserInputType.MouseMovement="MouseMovement";Enum.UserInputType.Keyboard="Keyboard"
local methods={}
local meta={}
local function attach(child,parent)
    local old=rawget(child,"Parent")
    if old then for index,value in ipairs(old.__children) do if value==child then table.remove(old.__children,index) break end end end
    rawset(child,"Parent",parent)
    if parent then table.insert(parent.__children,child) end
end
function meta.__newindex(self,key,value)
    if key=="Parent" then attach(self,value) else rawset(self,key,value) end
end
function meta.__index(self,key) return methods[key] end
local function newInstance(className,name)
    local object=setmetatable({ClassName=className,Name=name or className,__children={},__destroyed=false,__propertySignals={}},meta)
    object.InputBegan=signal();object.InputEnded=signal();object.InputChanged=signal()
    if className=="TextButton" then object.MouseButton1Click=signal() end
    if className=="TextBox" then object.FocusLost=signal() end
    if className=="Humanoid" then object.StateChanged=signal() end
    if className=="UIListLayout" then object.AbsoluteContentSize=Vector2.new(0,0) end
    return object
end
function methods:IsA(className)
    if className=="BasePart" then return self.ClassName=="Part" or self.ClassName=="HumanoidRootPart" end
    return self.ClassName==className
end
function methods:GetChildren() return table.clone(self.__children) end
function methods:GetDescendants()
    local output={}
    local function walk(parent) for _,child in ipairs(parent.__children) do table.insert(output,child);walk(child) end end
    walk(self);return output
end
function methods:FindFirstChild(name)
    for _,child in ipairs(self.__children) do if child.Name==name then return child end end
end
function methods:FindFirstChildOfClass(className)
    for _,child in ipairs(self.__children) do if child.ClassName==className then return child end end
end
function methods:WaitForChild(name)
    local child=self:FindFirstChild(name);if not child then error("missing child "..name) end;return child
end
function methods:Destroy() attach(self,nil);self.__destroyed=true end
function methods:GetFullName()
    local names={self.Name};local parent=self.Parent
    while parent do table.insert(names,1,parent.Name);parent=parent.Parent end
    return table.concat(names,".")
end
function methods:GetPropertyChangedSignal(name)
    if not self.__propertySignals[name] then self.__propertySignals[name]=signal() end
    return self.__propertySignals[name]
end

function methods:CaptureFocus() self.__focused=true end
function methods:ReleaseFocus() self.__focused=false end
function methods:ChangeState(state) self.__state=state end
Instance={new=function(className) return newInstance(className,className) end}
local function character(name)
    local model=newInstance("Model",name)
    local root=newInstance("HumanoidRootPart","HumanoidRootPart");root.CanCollide=true;root.CFrame=CFrame.new(0,5,0);root.AssemblyLinearVelocity=Vector3.new(0,0,0);root.Parent=model
    local limb=newInstance("Part","UpperTorso");limb.CanCollide=true;limb.Parent=model
    local humanoid=newInstance("Humanoid","Humanoid");humanoid.WalkSpeed=16;humanoid.JumpPower=50;humanoid.JumpHeight=7.2;humanoid.UseJumpPower=true;humanoid.Health=100;humanoid.Parent=model
    model.PrimaryPart=root
    return model
end
local player=newInstance("Player","LocalPlayer");player.UserId=1;player.Chatted=signal();player.CharacterAdded=signal();player.CharacterRemoving=signal()
local playerGui=newInstance("PlayerGui","PlayerGui");playerGui.Parent=player
player.Character=character("CharacterOne")
local players={LocalPlayer=player}
function players:GetPlayers() return {player} end
function players:GetPlayerByUserId(id) if id==player.UserId then return player end end
local runService={Heartbeat=signal()}
local inputService={InputBegan=signal(),InputEnded=signal(),InputChanged=signal()}
function inputService:IsKeyDown(_) return false end
local teleportService={calls=0}
function teleportService:Teleport(...) self.calls+=1 end
function teleportService:TeleportToPlaceInstance(...) self.calls+=1 end
local starterGui={messages={}}
function starterGui:SetCore(_,payload) table.insert(self.messages,payload) end
local camera={CFrame=CFrame.new(0,5,0)}
workspace={CurrentCamera=camera}
local services={Players=players,RunService=runService,UserInputService=inputService,TeleportService=teleportService,StarterGui=starterGui}
game={PlaceId=__RUNTIME_PLACE,JobId="job"}
function game:GetService(name) local service=services[name];if not service then error("unsupported service "..name) end;return service end
task={wait=function() return 0 end,defer=function(callback) callback() end,delay=function(_,callback) callback() end}
function settings() return {Network={IncomingReplicationLag=0}} end
function warn(...) end
_G.__adminTest={player=player,playerGui=playerGui,runService=runService,newCharacter=character,teleportService=teleportService,starterGui=starterGui}
'''

DRIVER=r'''
local test=_G.__adminTest
local function command(text) test.player.Chatted:Fire(";"..text) end
local gui=test.playerGui:FindFirstChild("LycolesAdminCommands")
assert(gui~=nil,"admin GUI missing")
local humanoid=test.player.Character:FindFirstChildOfClass("Humanoid")
local root=test.player.Character:FindFirstChild("HumanoidRootPart")
command("speed 40");assert(humanoid.WalkSpeed==40,"speed command failed")
command("jump 85");assert(humanoid.JumpPower==85,"jump command failed")
command("noclip");test.runService.Heartbeat:Fire()
local collisionDisabled=true
for _,item in ipairs(test.player.Character:GetDescendants()) do if item:IsA("BasePart") and item.CanCollide~=false then collisionDisabled=false end end
assert(collisionDisabled,"noclip state failed")
command("stopall")
assert(humanoid.WalkSpeed==16 and humanoid.JumpPower==50,"humanoid cleanup failed")
local collisionRestored=true
for _,item in ipairs(test.player.Character:GetDescendants()) do if item:IsA("BasePart") and item.CanCollide~=true then collisionRestored=false end end
assert(collisionRestored,"collision cleanup failed")
command("fly");test.runService.Heartbeat:Fire()
assert(root:FindFirstChild("LycolesFlyVelocity")~=nil and root:FindFirstChild("LycolesFlyGyro")~=nil,"fly setup failed")
local replacement=test.newCharacter("CharacterTwo")
test.player.Character=replacement;test.player.CharacterAdded:Fire(replacement);test.runService.Heartbeat:Fire()
local replacementRoot=replacement:FindFirstChild("HumanoidRootPart")
assert(root:FindFirstChild("LycolesFlyVelocity")==nil,"old fly body not removed")
assert(replacementRoot:FindFirstChild("LycolesFlyVelocity")~=nil,"fly did not resume after respawn")
command("unfly");assert(replacementRoot:FindFirstChild("LycolesFlyVelocity")==nil,"unfly cleanup failed")
local guiToggleWorked=false
for _,item in ipairs(gui:GetDescendants()) do
    if item:IsA("TextButton") and item.Name=="noclip" then
        item.MouseButton1Click:Fire()
        for _,field in ipairs(gui:GetDescendants()) do
            if field:IsA("TextBox") and string.find(field.Text or "",";noclip",1,true)==1 then field.FocusLost:Fire(true) break end
        end
        test.runService.Heartbeat:Fire();guiToggleWorked=string.find(item.Text or "","State: on",1,true)~=nil;break
    end
end
assert(guiToggleWorked,"GUI command control failed")
_G.LycolesAdminClose()
assert(test.playerGui:FindFirstChild("LycolesAdminCommands")==nil,"GUI close failed")
for _,item in ipairs(replacement:GetDescendants()) do if item:IsA("BasePart") then assert(item.CanCollide==true,"close collision cleanup failed") end end
print("LYCOLES_ADMIN|PASS|1|1|1|1|1")
'''


def execute(place_id,luau_binary,runtime_place_id=None,timeout_seconds=2.0):
    if type(place_id) is not int or place_id<=0:
        raise ValueError("invalid place ID")
    if runtime_place_id is None:
        runtime_place_id=place_id
    if type(runtime_place_id) is not int or runtime_place_id<=0:
        raise ValueError("invalid runtime place ID")
    source=STUBS.replace("__RUNTIME_PLACE",str(runtime_place_id),1)+"\n"+render(place_id)
    if runtime_place_id==place_id:
        source+="\n"+DRIVER
    else:
        source+='\nassert(_G.__adminTest.playerGui:FindFirstChild("LycolesAdminCommands")==nil,"place guard failed")\nprint("LYCOLES_ADMIN|PLACE_GUARD")\n'
    try:
        stdout=run_bounded_program(source,Path(luau_binary),timeout_seconds=timeout_seconds)
    except ControlledExecutionError as exc:
        if runtime_place_id==place_id or "Incorrect Roblox place" not in str(exc):
            raise
        stdout="LYCOLES_ADMIN|PLACE_GUARD\n"
    expected="LYCOLES_ADMIN|PASS|1|1|1|1|1" if runtime_place_id==place_id else "LYCOLES_ADMIN|PLACE_GUARD"
    if stdout.strip()!=expected:
        raise ControlledExecutionError("invalid admin command transcript")
    return {"schemaVersion":SCHEMA_VERSION,"placeId":place_id,
            "runtimePlaceId":runtime_place_id,"luauExecuted":True,
            "simulatedEnvironment":True,"commandStateVerified":runtime_place_id==place_id,
            "cleanupVerified":runtime_place_id==place_id,"respawnVerified":runtime_place_id==place_id,
            "placeGuardVerified":True,"robloxRuntimeVerified":False,
            "liveGameVerified":False,"serverAuthorityVerified":False,
            "gameplayVerified":False,"transcript":stdout.strip()}


def canonical(result):
    return json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n"
