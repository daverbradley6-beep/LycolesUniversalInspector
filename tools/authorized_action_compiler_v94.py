#!/usr/bin/env python3
"""v94 authorized Roblox Studio action compiler.

Compiles a strict declarative action specification into a LocalScript and a
server Script for games you own. Server actions are allowlisted, rate limited,
and validated; there is no arbitrary remote invocation or executor support.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

IDENT=re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,39}$")
SUPPORTED={"increment_stat","set_attribute","teleport_to_part"}
def validate(spec):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="94.actions":
        raise ValueError("expected schemaVersion 94.actions")
    place=spec.get("placeId")
    if type(place)!=int or place<=0:
        raise ValueError("placeId must be positive integer")
    actions=spec.get("actions")
    if not isinstance(actions,list) or not 1<=len(actions)<=50:
        raise ValueError("actions must contain 1-50 entries")
    seen=set()
    for a in actions:
        if not isinstance(a,dict) or not IDENT.fullmatch(str(a.get("id",""))):
            raise ValueError("invalid action id")
        if a["id"] in seen:
            raise ValueError("duplicate action id")
        seen.add(a["id"])
        kind=a.get("kind")
        if kind not in SUPPORTED:
            raise ValueError("unsupported action kind")
        if type(a.get("cooldownSeconds",1)) not in (int,float) or not .25<=a.get("cooldownSeconds",1)<=120:
            raise ValueError("cooldownSeconds must be 0.25-120")
        if kind=="increment_stat":
            if not IDENT.fullmatch(str(a.get("stat",""))) or type(a.get("amount"))!=int or not 1<=a["amount"]<=100:
                raise ValueError("invalid stat increment")
        elif kind=="set_attribute":
            if not IDENT.fullmatch(str(a.get("attribute",""))) or type(a.get("value")) not in (str,int,float,bool):
                raise ValueError("invalid attribute")
            if type(a["value"])==str and len(a["value"])>120:
                raise ValueError("attribute value too long")
        else:
            if not IDENT.fullmatch(str(a.get("part",""))):
                raise ValueError("invalid destination part")
    return spec

def lua_string(value):
    return json.dumps(value,ensure_ascii=False)

def literal(value):
    if value is True:return "true"
    if value is False:return "false"
    if type(value)==str:return lua_string(value)
    if type(value) in (int,float) and abs(value)<=1e12:return repr(value)
    raise ValueError("invalid Lua literal")

def compile_server(spec):
    validate(spec)
    lines=[
        "-- v94: install as ServerScriptService/LycolesActions.server.lua in YOUR game",
        "local ReplicatedStorage = game:GetService('ReplicatedStorage')",
        "local Players = game:GetService('Players')",
        "if game.PlaceId ~= "+str(spec["placeId"])+" then return end",
        "local remote = ReplicatedStorage:FindFirstChild('LycolesAuthorizedActions')",
        "if remote and not remote:IsA('RemoteEvent') then error('Remote name collision') end",
        "if not remote then",
        " remote = Instance.new('RemoteEvent')",
        " remote.Name = 'LycolesAuthorizedActions'",
        " remote.Parent = ReplicatedStorage",
        "end",
        "local lastUsed = {}",
        "Players.PlayerRemoving:Connect(function(player) lastUsed[player] = nil end)",
        "local handlers = {}",
    ]
    for a in spec["actions"]:
        id=lua_string(a["id"]);cool=a.get("cooldownSeconds",1)
        lines += ["handlers["+id+"] = { cooldown = "+str(cool)+", run = function(player)"]
        if a["kind"]=="increment_stat":
            lines += [
                " local stats = player:FindFirstChild('leaderstats')",
                " local value = stats and stats:FindFirstChild("+lua_string(a["stat"])+")",
                " if not value or not value:IsA('IntValue') then return end",
                " value.Value = math.min(2147483647, value.Value + "+str(a["amount"])+")",
            ]
        elif a["kind"]=="set_attribute":
            lines += [" player:SetAttribute("+lua_string(a["attribute"])+", "+literal(a["value"])+")"]
        else:
            lines += [
                " local part = workspace:FindFirstChild("+lua_string(a["part"])+")",
                " if not part or not part:IsA('BasePart') then return end",
                " local character = player.Character",
                " local root = character and character:FindFirstChild('HumanoidRootPart')",
                " if not root then return end",
                " root.CFrame = part.CFrame + Vector3.new(0,4,0)",
            ]
        lines += ["end }"]
    lines += [
        "remote.OnServerEvent:Connect(function(player, actionId)",
        " if type(actionId) ~= 'string' then return end",
        " local handler = handlers[actionId]",
        " if not handler then return end",
        " local state = lastUsed[player]",
        " if not state then state = {} lastUsed[player] = state end",
        " local now = os.clock()",
        " if state[actionId] and now - state[actionId] < handler.cooldown then return end",
        " state[actionId] = now",
        " handler.run(player)",
        "end)",
    ]
    return "\n".join(lines)+"\n"

def compile_client(spec):
    validate(spec)
    lines=[
        "-- v94: install as StarterPlayerScripts/LycolesActions.client.lua in YOUR game",
        "local Players = game:GetService('Players')",
        "local ReplicatedStorage = game:GetService('ReplicatedStorage')",
        "if game.PlaceId ~= "+str(spec["placeId"])+" then return end",
        "local player = Players.LocalPlayer",
        "local gui = Instance.new('ScreenGui')",
        "gui.Name = 'LycolesAuthorizedActionsV94'",
        "gui.ResetOnSpawn = false",
        "gui.Parent = player:WaitForChild('PlayerGui')",
        "local frame = Instance.new('ScrollingFrame')",
        "frame.Size = UDim2.fromOffset(300,280)",
        "frame.Position = UDim2.fromScale(0.05,0.2)",
        "frame.CanvasSize = UDim2.fromOffset(0,0)",
        "frame.Parent = gui",
        "local layout = Instance.new('UIListLayout')",
        "layout.Parent = frame",
        "local function addButton(label, actionId)",
        " local button = Instance.new('TextButton')",
        " button.Size = UDim2.new(1,-10,0,38)",
        " button.Text = label",
        " button.Parent = frame",
        " button.Activated:Connect(function()",
        "  if actionId == nil then gui:Destroy() return end",
        "  local remote = ReplicatedStorage:FindFirstChild('LycolesAuthorizedActions')",
        "  if remote and remote:IsA('RemoteEvent') then remote:FireServer(actionId) end",
        " end)",
        "end",
        "addButton('Close',nil)",
    ]
    for a in spec["actions"]:
        lines.append("addButton("+lua_string(a["id"])+","+lua_string(a["id"])+")")
    lines.append("frame.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y + 12)")
    return "\n".join(lines)+"\n"

def generate(spec,out):
    validate(spec)
    root=Path(out);root.mkdir(parents=True,exist_ok=True)
    artifacts={
        "LycolesActions.server.lua":compile_server(spec).encode("utf-8"),
        "LycolesActions.client.lua":compile_client(spec).encode("utf-8"),
        "actions-v94.json":json.dumps(spec,sort_keys=True,ensure_ascii=False,indent=2).encode("utf-8"),
    }
    hashes={}
    for name,data in artifacts.items():
        (root/name).write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    manifest={"schemaVersion":"94.manifest","placeId":spec["placeId"],
              "files":hashes,"requiresStudioInstallation":True,
              "verifiedInGame":False,"actions":len(spec["actions"])}
    (root/"manifest-v94.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v94"))
    args=p.parse_args()
    spec=json.loads(args.spec.read_text(encoding="utf-8-sig"))
    print(json.dumps(generate(spec,args.output)))
if __name__=="__main__":main()
