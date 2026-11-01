#!/usr/bin/env python3
"""v58 contract compiler: explicit, bounded, testable Roblox Tool workflows."""
import argparse,json,hashlib
from pathlib import Path
from gameplay_contracts_v57 import validate as validate_v57, lua

MAX_REPEATS=20
def validate(spec):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="58.0":
        raise ValueError("Expected v58.0")
    # Validate a projection without mutating the original.
    projection={"schemaVersion":"57.0","placeId":spec.get("placeId"),
                "ownerAuthorized":spec.get("ownerAuthorized"),
                "actions":[{k:v for k,v in a.items() if k not in ("repeatCount","cooldownSeconds")}
                           for a in spec.get("actions",[])]}
    validate_v57(projection)
    if set(spec)-{"schemaVersion","placeId","ownerAuthorized","actions"}:
        raise ValueError("Unexpected spec fields")
    for action in spec["actions"]:
        count=action.get("repeatCount",1)
        delay=action.get("cooldownSeconds",0.5)
        if type(count)!=int or not 1<=count<=MAX_REPEATS:raise ValueError("Invalid repeatCount")
        if type(delay) not in (int,float) or not 0.2<=delay<=10:raise ValueError("Invalid cooldownSeconds")
    return spec

def generate(spec):
    validate(spec)
    records=[]
    for a in spec["actions"]:
        m=a["expectedValue"]
        records.append("{id="+lua(a["id"])+",tool="+lua(a["toolName"])+
                       ",metric="+lua(m["name"])+",delta="+str(m["minimumDelta"])+
                       ",timeout="+str(a.get("timeoutSeconds",5))+
                       ",repeats="+str(a.get("repeatCount",1))+
                       ",cooldown="+str(a.get("cooldownSeconds",0.5))+"}")
    template=r'''-- Lycoles v58: bounded owner-authorized gameplay Tool workflow.
local Players=game:GetService("Players")
if game.PlaceId~=PLACE_ID then return end
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV58")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV58" gui.ResetOnSpawn=false gui.Parent=pg
local frame=Instance.new("Frame")
frame.Size=UDim2.fromOffset(530,460)
frame.Position=UDim2.fromScale(.04,.15)
frame.BackgroundColor3=Color3.fromRGB(28,34,45) frame.Parent=gui
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,5) layout.Parent=frame
local function text(message,height)
 local x=Instance.new("TextLabel")
 x.Size=UDim2.new(1,-16,0,height)
 x.TextWrapped=true x.BackgroundTransparency=1
 x.TextColor3=Color3.fromRGB(250,250,250)
 x.Text=message x.Parent=frame return x
end
text("Lycoles v58 | Gameplay verification",34)
local status=text("Ready. Actions are not verified until tested.",62)
local progress=text("0 completed",32)
local actions=ACTIONS
local active=false
local cancelled=false
local function snapshot(a)
 local stats=player:FindFirstChild("leaderstats")
 local metric=stats and stats:FindFirstChild(a.metric)
 if not metric or not metric:IsA("ValueBase") then return nil,"Missing metric" end
 local ok,v=pcall(function() return metric.Value end)
 if not ok or type(v)~="number" then return nil,"Metric not numeric" end
 return {instance=metric,value=v},nil
end
local function activate(a)
 local character=player.Character
 local humanoid=character and character:FindFirstChildOfClass("Humanoid")
 local backpack=player:FindFirstChildOfClass("Backpack")
 local tool=(character and character:FindFirstChild(a.tool)) or
            (backpack and backpack:FindFirstChild(a.tool))
 if not humanoid or not tool or not tool:IsA("Tool") then
  return false,"Missing Tool or Humanoid"
 end
 if tool.Parent~=character then
  local ok=pcall(function() humanoid:EquipTool(tool) end)
  if not ok or tool.Parent~=character then return false,"Equip failed" end
 end
 local ok,err=pcall(function() tool:Activate() end)
 if not ok then return false,tostring(err):sub(1,80) end
 return true,nil
end
local function run(a)
 if active then return end
 active=true cancelled=false
 local completed=0
 local baseline,reason=snapshot(a)
 if not baseline then
  status.Text=a.id.." | UNSUPPORTED: "..reason
  active=false return
 end
 for n=1,a.repeats do
  if cancelled or not gui.Parent then break end
  local before,why=snapshot(a)
  if not before or before.instance~=baseline.instance then
   status.Text=a.id.." | FAILED: metric replaced or absent" break
  end
  local ok,err=activate(a)
  if not ok then status.Text=a.id.." | FAILED: "..err break end
  local started=os.clock()
  local passed=false
  repeat
   if cancelled or not gui.Parent then break end
   local now,reasonNow=snapshot(a)
   if not now or now.instance~=before.instance then break end
   if now.value-before.value>=a.delta then passed=true break end
   task.wait(.1)
  until os.clock()-started>=a.timeout
  if not passed then
   status.Text=a.id.." | UNVERIFIED: expected change not observed" break
  end
  completed+=1
  progress.Text=tostring(completed).."/"..tostring(a.repeats).." observed outcomes"
  status.Text=a.id.." | observed change; causality not established"
  if n<a.repeats then task.wait(a.cooldown) end
 end
 if cancelled then status.Text=a.id.." | STOPPED" end
 active=false
end
local stop=Instance.new("TextButton")
stop.Size=UDim2.new(1,-16,0,36)
stop.Text="Stop current action"
stop.Parent=frame
stop.MouseButton1Click:Connect(function() cancelled=true end)
for _,a in ipairs(actions) do
 local btn=Instance.new("TextButton")
 btn.Size=UDim2.new(1,-16,0,38)
 btn.Text="Run "..a.id.." ("..a.repeats.." attempts)"
 btn.Parent=frame
 btn.MouseButton1Click:Connect(function()
  if not active then task.spawn(run,a) end
 end)
end
text("Normal Tool activation only. No remote invocation or bypass.",40)
'''
    return template.replace("PLACE_ID",str(spec["placeId"])).replace("ACTIONS","{"+",".join(records)+"}")
def build(spec,out):
    source=generate(spec)
    out.mkdir(parents=True,exist_ok=True)
    (out/"gameplay-runner-v58.luau").write_text(source,encoding="utf-8")
    summary={"schemaVersion":"58.release","placeId":spec["placeId"],
             "actionCount":len(spec["actions"]),"outcomesVerified":False,
             "sha256":hashlib.sha256(source.encode()).hexdigest(),
             "limitations":["Outcome observations are not proof of causality",
                            "Only standard Tool activation is supported",
                            "No server-side verification without developer instrumentation"]}
    (out/"gameplay-manifest-v58.json").write_text(json.dumps(summary,indent=2)+"\n",encoding="utf-8")
    return summary
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--spec",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v58"))
    a=p.parse_args()
    print(json.dumps(build(json.loads(a.spec.read_text(encoding="utf-8-sig")),a.output),indent=2))
if __name__=="__main__":main()
