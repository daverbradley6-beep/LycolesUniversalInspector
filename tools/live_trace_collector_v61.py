#!/usr/bin/env python3
"""v61 generate a bounded, place-scoped live Tool outcome trace collector.

A client-observed stat delta is NOT server-side proof. Trace output can be
replayed by v60; execution requires explicit developer authorization.
"""
import argparse,json,hashlib
from pathlib import Path
from gameplay_workflows_v58 import validate as validate_contract
from gameplay_contracts_v57 import lua

def generate(contract):
    validate_contract(contract)
    rows=[]
    for a in contract["actions"]:
        m=a["expectedValue"]
        rows.append("{id="+lua(a["id"])+",tool="+lua(a["toolName"])+
                    ",metric="+lua(m["name"])+",delta="+str(m["minimumDelta"])+
                    ",timeout="+str(a.get("timeoutSeconds",5))+
                    ",repeats="+str(a.get("repeatCount",1))+
                    ",cooldown="+str(a.get("cooldownSeconds",0.5))+"}")
    template=r'''-- Lycoles v61 live observational trace recorder.
-- Runs standard Tool:Activate() in an owner-authorized place only.
local HttpService=game:GetService("HttpService")
local Players=game:GetService("Players")
if game.PlaceId~=__PLACE__ then return end
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local previous=pg:FindFirstChild("LycolesV61")
if previous then previous:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV61" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("ScrollingFrame")
panel.Size=UDim2.fromOffset(560,430)
panel.Position=UDim2.fromScale(.04,.12)
panel.BackgroundColor3=Color3.fromRGB(28,34,45)
panel.ScrollBarThickness=6
panel.AutomaticCanvasSize=Enum.AutomaticSize.Y
panel.CanvasSize=UDim2.fromOffset(0,0)
panel.Parent=gui
local padding=Instance.new("UIPadding")
padding.PaddingLeft=UDim.new(0,8) padding.PaddingRight=UDim.new(0,8)
padding.Parent=panel
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,5) layout.Parent=panel
local function label(message,height)
 local t=Instance.new("TextLabel")
 t.Size=UDim2.new(1,0,0,height)
 t.BackgroundTransparency=1 t.TextWrapped=true
 t.TextColor3=Color3.fromRGB(255,255,255)
 t.Text=message t.Parent=panel return t
end
local function button(message)
 local b=Instance.new("TextButton")
 b.Size=UDim2.new(1,0,0,35)
 b.BackgroundColor3=Color3.fromRGB(58,74,95)
 b.TextColor3=Color3.fromRGB(255,255,255)
 b.Text=message b.Parent=panel return b
end
label("Lycoles v61 | Observational trace collector",32)
local status=label("Idle. Each test records before/after numeric values.",52)
local actions=__ACTIONS__
local events={}
local running=false
local cancelled=false
local MAX_EVENTS=10000
local function emit(actionId,kind,value)
 if #events>=MAX_EVENTS then return false end
 table.insert(events,{time=math.floor(os.clock()*1000)/1000,
  actionId=actionId,kind=kind,value=value})
 return true
end
local function metricSnapshot(action)
 local stats=player:FindFirstChild("leaderstats")
 local metric=stats and stats:FindFirstChild(action.metric)
 if not metric or not metric:IsA("ValueBase") then return nil end
 local ok,value=pcall(function() return metric.Value end)
 if not ok or type(value)~="number" or value~=value or value==math.huge or value==-math.huge then
  return nil
 end
 return {object=metric,value=value}
end
local function activate(action)
 local character=player.Character
 local humanoid=character and character:FindFirstChildOfClass("Humanoid")
 local backpack=player:FindFirstChildOfClass("Backpack")
 local tool=(character and character:FindFirstChild(action.tool)) or
            (backpack and backpack:FindFirstChild(action.tool))
 if not humanoid or not tool or not tool:IsA("Tool") then return false end
 if tool.Parent~=character then
  local ok=pcall(function() humanoid:EquipTool(tool) end)
  if not ok or tool.Parent~=character then return false end
 end
 return pcall(function() tool:Activate() end)
end
local function run(action)
 if running then return end
 running=true cancelled=false
 for i=1,action.repeats do
  if cancelled or not gui.Parent then break end
  if #events+2>MAX_EVENTS then status.Text="Trace limit reached" break end
  local before=metricSnapshot(action)
  if not before then status.Text="Missing numeric metric: "..action.metric break end
  emit(action.id,"before",before.value)
  local ok=activate(action)
  if not ok then
   emit(action.id,"error",before.value)
   status.Text=action.id.." | Activation failed"
   break
  end
  local start=os.clock()
  local changed=false
  local latest=before.value
  repeat
   if cancelled or not gui.Parent then break end
   local current=metricSnapshot(action)
   if not current or current.object~=before.object then break end
   latest=current.value
   if latest-before.value>=action.delta then changed=true break end
   task.wait(.1)
  until os.clock()-start>=action.timeout
  emit(action.id,"after",latest)
  status.Text=action.id.." | attempt "..i.."/"..action.repeats..
   (changed and " observed" or " unverified")
  if cancelled or not changed then break end
  if i<action.repeats then task.wait(action.cooldown) end
 end
 running=false
end
button("STOP current action").MouseButton1Click:Connect(function()
 cancelled=true
end)
for _,action in ipairs(actions) do
 button("Record "..action.id.." ("..action.repeats.." attempts)").MouseButton1Click:Connect(function()
  if not running then task.spawn(run,action) end
 end)
end
local export=Instance.new("TextBox")
export.Size=UDim2.new(1,0,0,100)
export.MultiLine=true export.ClearTextOnFocus=false
export.TextEditable=true export.TextWrapped=true
export.Text="Trace JSON appears here after Export"
export.Parent=panel
button("Export trace JSON").MouseButton1Click:Connect(function()
 if running then status.Text="Stop recording before export" return end
 local normalized={}
 if #events==0 then status.Text="No events recorded" return end
 local origin=events[1].time
 for _,e in ipairs(events) do
  table.insert(normalized,{time=math.max(0,e.time-origin),
   actionId=e.actionId,kind=e.kind,value=e.value})
 end
 export.Text=HttpService:JSONEncode({schemaVersion="60.trace",
  placeId=game.PlaceId,events=normalized})
 status.Text="Select and copy JSON. This is client-observed, not server-verified."
end)
label("Use in an authorized test place. No remotes, hooks or bypasses.",44)
'''
    return template.replace("__PLACE__",str(contract["placeId"])).replace("__ACTIONS__","{"+",".join(rows)+"}")
def build(contract,out):
    source=generate(contract)
    out.mkdir(parents=True,exist_ok=True)
    (out/"live-trace-collector-v61.luau").write_text(source,encoding="utf-8")
    manifest={"schemaVersion":"61.release","placeId":contract["placeId"],
              "actions":[a["id"] for a in contract["actions"]],
              "traceSchema":"60.trace","serverVerified":False,
              "sha256":hashlib.sha256(source.encode()).hexdigest()}
    (out/"collector-manifest-v61.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--contract",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v61"))
    a=p.parse_args()
    spec=json.loads(a.contract.read_text(encoding="utf-8-sig"))
    print(json.dumps(build(spec,a.output),indent=2))
if __name__=="__main__":main()
