#!/usr/bin/env python3
"""v57 opt-in, place-scoped gameplay action contracts with outcome verification.

Only explicit author-provided contracts can generate actions. Discovery never grants
permission or invents remote signatures. Generated actions are local Roblox Tool
activation, and results must be checked against an observable ValueBase.
"""
import argparse,json,re,hashlib
from pathlib import Path

OPERATIONS={"activate_equipped_tool"}
NAME=re.compile(r"^[A-Za-z0-9 _.'-]{1,80}$")
MAX_ACTIONS=30
def validate(spec):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="57.0":
        raise ValueError("Expected v57.0 specification")
    place=spec.get("placeId")
    if type(place)!=int or place<=0:raise ValueError("Invalid place")
    if spec.get("ownerAuthorized") is not True:raise ValueError("Owner authorization must be explicit")
    actions=spec.get("actions")
    if not isinstance(actions,list) or not 1<=len(actions)<=MAX_ACTIONS:
        raise ValueError("Require 1-30 actions")
    ids=set()
    for action in actions:
        if not isinstance(action,dict):raise ValueError("Invalid action")
        identifier=action.get("id")
        if not isinstance(identifier,str) or not NAME.fullmatch(identifier) or identifier in ids:
            raise ValueError("Invalid or duplicate action ID")
        ids.add(identifier)
        if action.get("operation") not in OPERATIONS:raise ValueError("Unsupported operation")
        tool=action.get("toolName")
        if not isinstance(tool,str) or not NAME.fullmatch(tool):raise ValueError("Invalid tool name")
        metric=action.get("expectedValue")
        if not isinstance(metric,dict) or set(metric)!={"container","name","minimumDelta"}:
            raise ValueError("Expected value contract required")
        if metric["container"]!="leaderstats":raise ValueError("Only local leaderstats observation supported")
        if not isinstance(metric["name"],str) or not NAME.fullmatch(metric["name"]):
            raise ValueError("Invalid metric name")
        delta=metric["minimumDelta"]
        if type(delta) not in (int,float) or not 0<delta<=1000000:raise ValueError("Invalid delta")
        timeout=action.get("timeoutSeconds",5)
        if type(timeout) not in (int,float) or not 1<=timeout<=20:raise ValueError("Invalid timeout")
        if set(action)-{"id","operation","toolName","expectedValue","timeoutSeconds"}:
            raise ValueError("Unknown action fields")
    if set(spec)-{"schemaVersion","placeId","ownerAuthorized","actions"}:
        raise ValueError("Unknown specification fields")
    return spec

def lua(value):return json.dumps(value,ensure_ascii=True)
def generate(spec):
    validate(spec)
    records=[]
    for a in spec["actions"]:
        m=a["expectedValue"]
        records.append("{id="+lua(a["id"])+",tool="+lua(a["toolName"])+
                       ",metric="+lua(m["name"])+",delta="+str(m["minimumDelta"])+
                       ",timeout="+str(a.get("timeoutSeconds",5))+"}")
    template=r'''-- Lycoles v57 authorized test-place gameplay contract runner.
-- Tool:Activate() uses normal Roblox client APIs. No arbitrary remote calls.
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player or game.PlaceId~=PLACE then return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV57")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV57" gui.ResetOnSpawn=false gui.Parent=pg
local frame=Instance.new("Frame")
frame.Size=UDim2.fromOffset(510,390) frame.Position=UDim2.fromScale(.04,.18)
frame.BackgroundColor3=Color3.fromRGB(25,32,43) frame.Parent=gui
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,6) layout.Parent=frame
local function label(text,height)
 local t=Instance.new("TextLabel")
 t.Size=UDim2.new(1,-16,0,height) t.BackgroundTransparency=1
 t.TextColor3=Color3.fromRGB(245,245,245)
 t.TextWrapped=true t.Text=text t.Parent=frame return t
end
label("Lycoles v57 | Authorized action verification",34)
local status=label("Select an action. Results are checked, not assumed.",55)
local actions=ACTIONS
local busy=false
local function execute(action)
 if busy then return end
 busy=true
 status.Text=action.id.." | checking prerequisites"
 local char=player.Character
 local humanoid=char and char:FindFirstChildOfClass("Humanoid")
 local backpack=player:FindFirstChildOfClass("Backpack")
 local stats=player:FindFirstChild("leaderstats")
 local metric=stats and stats:FindFirstChild(action.metric)
 local tool=(char and char:FindFirstChild(action.tool)) or (backpack and backpack:FindFirstChild(action.tool))
 if not humanoid or not tool or not tool:IsA("Tool") or not metric or not metric:IsA("ValueBase") then
  status.Text=action.id.." | UNSUPPORTED: missing tool, humanoid or metric"
  busy=false return
 end
 local okBefore,before=pcall(function() return metric.Value end)
 if not okBefore or type(before)~="number" then
  status.Text=action.id.." | UNSUPPORTED: nonnumeric metric"
  busy=false return
 end
 if tool.Parent~=char then
  local okEquip=pcall(function() humanoid:EquipTool(tool) end)
  if not okEquip or tool.Parent~=char then
   status.Text=action.id.." | FAILED: tool could not be equipped"
   busy=false return
  end
 end
 local okActivate,err=pcall(function() tool:Activate() end)
 if not okActivate then
  status.Text=action.id.." | FAILED: activation error "..tostring(err):sub(1,80)
  busy=false return
 end
 local started=os.clock()
 local passed=false
 repeat
  if not gui.Parent then break end
  local okNow,current=pcall(function() return metric.Value end)
  if okNow and type(current)=="number" and current-before>=action.delta then
   passed=true break
  end
  task.wait(.1)
 until os.clock()-started>=action.timeout
 if gui.Parent then
  status.Text=action.id..(passed and " | OBSERVED: expected metric increased" or " | UNVERIFIED: no expected metric increase")
 end
 busy=false
end
for _,action in ipairs(actions) do
 local button=Instance.new("TextButton")
 button.Size=UDim2.new(1,-16,0,36)
 button.BackgroundColor3=Color3.fromRGB(48,61,78)
 button.TextColor3=Color3.fromRGB(255,255,255)
 button.Text="Test "..action.id button.Parent=frame
 button.MouseButton1Click:Connect(function() task.spawn(execute,action) end)
end
label("Observed changes may be unrelated to this action; use isolated test conditions.",52)
'''
    return template.replace("PLACE",str(spec["placeId"])).replace("ACTIONS","{"+",".join(records)+"}")
def compile_release(spec,out):
    validate(spec)
    source=generate(spec)
    out.mkdir(parents=True,exist_ok=True)
    (out/"authorized-actions-v57.luau").write_text(source,encoding="utf-8")
    summary={"schemaVersion":"57.release","placeId":spec["placeId"],
             "actions":[{"id":a["id"],"operation":a["operation"],"status":"requires_live_verification"} for a in spec["actions"]],
             "remoteCallsGenerated":False,"serverOutcomeVerified":False,
             "sha256":hashlib.sha256(source.encode()).hexdigest()}
    (out/"action-manifest-v57.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v57"))
    a=p.parse_args()
    spec=json.loads(a.spec.read_text(encoding="utf-8-sig"))
    print(json.dumps(compile_release(spec,a.output),indent=2))
if __name__=="__main__":main()
