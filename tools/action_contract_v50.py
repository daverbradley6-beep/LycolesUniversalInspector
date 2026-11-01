#!/usr/bin/env python3
"""v50: explicit developer-authorized local GUI action compiler."""
import argparse,json,re
from pathlib import Path
KINDS={"read-value","set-local-text","toggle-local-visibility"}
def validate(spec):
 if not isinstance(spec,dict) or spec.get("schemaVersion")!="50.0":raise ValueError("Invalid schema")
 if type(spec.get("placeId")) is not int or spec["placeId"]<=0:raise ValueError("Invalid place")
 actions=spec.get("actions")
 if not isinstance(actions,list) or not 1<=len(actions)<=64:raise ValueError("Invalid actions")
 seen=set();out=[]
 for a in actions:
  if not isinstance(a,dict):raise ValueError("Invalid action")
  aid,kind,path=a.get("id"),a.get("kind"),a.get("path")
  if not isinstance(aid,str) or not re.fullmatch(r"[a-z][a-z0-9-]{1,63}",aid) or aid in seen:raise ValueError("Invalid ID")
  if kind not in KINDS:raise ValueError("Unsupported action")
  if not isinstance(path,str) or len(path)>256 or not path.startswith("Players.LocalPlayer."):raise ValueError("Only local player paths allowed")
  if any(not part or len(part)>80 for part in path.split(".")):raise ValueError("Invalid path")
  if kind=="set-local-text":
   if not isinstance(a.get("value"),str) or len(a["value"])>120:raise ValueError("Invalid text")
  elif "value" in a:raise ValueError("Unexpected value")
  seen.add(aid)
  out.append({"id":aid,"kind":kind,"path":path,**({"value":a["value"]} if kind=="set-local-text" else {})})
 return {"schemaVersion":"50.0","placeId":spec["placeId"],"actions":sorted(out,key=lambda x:x["id"])}
def generate(spec):
 cfg=json.dumps(validate(spec),sort_keys=True,ensure_ascii=True)
 delim="="
 while "]"+delim+"]" in cfg:delim+="="
 script=r'''-- Lycoles v50: local UI actions explicitly defined by game developer.
-- Does not infer or execute arbitrary gameplay remotes.
local Players=game:GetService("Players")
local HttpService=game:GetService("HttpService")
local player=Players.LocalPlayer
if not player then return end
local cfg=HttpService:JSONDecode(CONFIG_LITERAL)
if game.PlaceId~=cfg.placeId then warn("Lycoles v50: place mismatch") return end
local pg=player:WaitForChild("PlayerGui")
local prior=pg:FindFirstChild("LycolesV50")
if prior then prior:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV50"
gui.ResetOnSpawn=false
local frame=Instance.new("Frame")
frame.Size=UDim2.fromOffset(420,400)
frame.Position=UDim2.fromScale(.05,.12)
frame.Parent=gui
local list=Instance.new("ScrollingFrame")
list.Size=UDim2.new(1,-12,1,-12)
list.Position=UDim2.fromOffset(6,6)
list.AutomaticCanvasSize=Enum.AutomaticSize.Y
list.CanvasSize=UDim2.fromOffset(0,0)
list.Parent=frame
local layout=Instance.new("UIListLayout")
layout.Padding=UDim.new(0,5)
layout.Parent=list
local function resolve(path)
 local parts=string.split(path,".")
 if parts[1]~="Players" or parts[2]~="LocalPlayer" then return nil end
 local obj=player
 for i=3,#parts do
  if obj==player and parts[i]=="PlayerGui" then obj=pg
  else obj=obj:FindFirstChild(parts[i]) end
  if not obj then return nil end
 end
 return obj
end
local function perform(action)
 local obj=resolve(action.path)
 if not obj then return false,"not visible" end
 if action.kind=="read-value" then
  if obj:IsA("ValueBase") then return true,tostring(obj.Value):sub(1,120) end
  if obj:IsA("TextLabel") or obj:IsA("TextButton") then return true,obj.Text:sub(1,120) end
  return false,"unsupported class"
 elseif action.kind=="set-local-text" then
  if not (obj:IsA("TextLabel") or obj:IsA("TextButton")) then return false,"not text UI" end
  obj.Text=action.value
  return true,"text updated locally"
 elseif action.kind=="toggle-local-visibility" then
  if not obj:IsA("GuiObject") then return false,"not GUI" end
  obj.Visible=not obj.Visible
  return true,"visibility toggled locally"
 end
 return false,"unsupported action"
end
for _,action in ipairs(cfg.actions) do
 local button=Instance.new("TextButton")
 button.Size=UDim2.new(1,-10,0,44)
 button.Text=action.id.." | Run"
 button.Parent=list
 button.Activated:Connect(function()
  local ok,success,message=pcall(perform,action)
  if not ok then button.Text=action.id.." | Error"
  else button.Text=action.id.." | "..(success and "OK: " or "Unavailable: ")..tostring(message) end
 end)
end
gui.Parent=pg
'''
 return script.replace("CONFIG_LITERAL","["+delim+"["+cfg+"]"+delim+"]")
def main():
 p=argparse.ArgumentParser()
 p.add_argument("contract",type=Path)
 p.add_argument("--output",type=Path,default=Path("build/authorized-actions-v50.luau"))
 a=p.parse_args()
 if a.contract.stat().st_size>200000:raise ValueError("Oversized contract")
 spec=json.loads(a.contract.read_text(encoding="utf-8-sig"))
 result=generate(spec)
 a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(result,encoding="utf-8")
 print("Generated",len(validate(spec)["actions"]),"local action controls:",a.output)
if __name__=="__main__":main()
