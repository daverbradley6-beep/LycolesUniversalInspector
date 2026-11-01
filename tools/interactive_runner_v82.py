#!/usr/bin/env python3
"""v82 interactive local GUI test harness generator."""
import argparse,json
from pathlib import Path
from gui_contract_compiler_v81 import validate
LUA=r'''local P=game:GetService("Players").LocalPlayer
local H=game:GetService("HttpService")
if game.PlaceId~=__PLACE__ then warn("v82: wrong place") return end
local pg=P:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV82") if old then old:Destroy() end
local contracts=H:JSONDecode(__PAYLOAD__)
local captureId=H:GenerateGUID(false)
local attemptIndex=0
local gui=Instance.new("ScreenGui") gui.Name="LycolesV82" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(460,math.min(560,130+#contracts*46)) panel.Position=UDim2.fromScale(.1,.12) panel.Parent=gui
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-20,0,65) status.Position=UDim2.fromOffset(10,5) status.TextWrapped=true status.Text="v82: Click to test approved local GUI actions" status.Parent=panel
local close=Instance.new("TextButton") close.Text="Close" close.Size=UDim2.fromOffset(90,30) close.Position=UDim2.new(1,-95,0,5) close.Parent=panel
close.Activated:Connect(function() gui:Destroy() end)
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-20,1,-82) scroll.Position=UDim2.fromOffset(10,75) scroll.CanvasSize=UDim2.fromOffset(0,#contracts*46) scroll.Parent=panel
local function snapshot()
 local out={} local stats=P:FindFirstChild("leaderstats")
 if stats then for _,v in ipairs(stats:GetChildren()) do
  if v:IsA("ValueBase") then local x=v.Value
   if type(x)=="number" or type(x)=="string" or type(x)=="boolean" then out[v.Name]=x end
  end
 end end
 return out
end
local function find(path)
 local node=pg
 for _,s in ipairs(path) do
  local count=0 local found=nil
  for _,child in ipairs(node:GetChildren()) do
   if child.Name==s.name and child.ClassName==s.className then
    count+=1 if count==s.ordinal then found=child break end
   end
  end
  if not found then return nil,"missing "..s.name end
  node=found
 end
 if not (node:IsA("TextButton") or node:IsA("ImageButton")) then return nil,"not a button" end
 return node
end
local function available(node)
 if not node.Active then return false end
 local current=node
 while current and current~=pg do
  if current:IsA("GuiObject") and not current.Visible then return false end
  if current:IsA("ScreenGui") and not current.Enabled then return false end
  current=current.Parent
 end
 return current==pg
end
local busy=false
for i,c in ipairs(contracts) do
 local b=Instance.new("TextButton") b.Text="Test "..c.id b.Size=UDim2.new(1,-8,0,38) b.Position=UDim2.fromOffset(0,(i-1)*46) b.Parent=scroll
 b.Activated:Connect(function()
  if busy then return end
  busy=true
  attemptIndex+=1
  local testIndex=attemptIndex
  local target,err=find(c.path)
  if not target or not available(target) then
   local reason=err or "hidden/disabled"
   status.Text="Unavailable: "..reason
   print("LYCOLES_V82_RESULT "..H:JSONEncode({schemaVersion="82.result",placeId=game.PlaceId,captureId=captureId,index=testIndex,id=c.id,requested=false,reason=reason,observedChanges={},verified=false}))
   busy=false return
  end
  local before=snapshot()
  local ok,msg=pcall(function() target:Activate() end)
  if not ok then
   status.Text="Activation error: "..tostring(msg)
   print("LYCOLES_V82_RESULT "..H:JSONEncode({schemaVersion="82.result",placeId=game.PlaceId,captureId=captureId,index=testIndex,id=c.id,requested=false,reason=tostring(msg),observedChanges={},verified=false}))
   busy=false return
  end
  status.Text="Activation requested: "..c.id.." (awaiting snapshot)"
  task.delay(1.5,function()
   if not gui.Parent then busy=false return end
   local after=snapshot() local changed={}
   for key,x in pairs(before) do
    if after[key]~=nil and after[key]~=x then table.insert(changed,{stat=key,before=x,after=after[key]}) end
   end
   print("LYCOLES_V82_RESULT "..H:JSONEncode({schemaVersion="82.result",placeId=game.PlaceId,captureId=captureId,index=testIndex,id=c.id,requested=true,observedChanges=changed,verified=false}))
   status.Text=c.id..": "..#changed.." leaderstat changes (not verified)"
   busy=false
  end)
 end)
end
print("Lycoles v82: "..#contracts.." manual test buttons ready; nothing auto-executed")
'''
def generate(document,place):
 contracts=validate(document,place)
 payload=json.dumps(contracts,ensure_ascii=True,separators=(',',':'))
 return LUA.replace('__PLACE__',str(place)).replace('__PAYLOAD__',json.dumps(payload,ensure_ascii=True)),len(contracts)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--place-id',type=int,required=True);p.add_argument('--contracts',type=Path,required=True)
 p.add_argument('--output',type=Path,default=Path('build/release-v82'))
 a=p.parse_args()
 if a.place_id<=0:p.error('invalid place ID')
 doc=json.loads(a.contracts.read_text(encoding='utf-8-sig'))
 script,n=generate(doc,a.place_id);a.output.mkdir(parents=True,exist_ok=True)
 (a.output/'interactive-runner-v82.luau').write_text(script,encoding='utf-8')
 (a.output/'build-report-v82.json').write_text(json.dumps({'schemaVersion':'82.build','placeId':a.place_id,'testButtons':n,'automaticallyExecuted':0,'verified':False},indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'testButtons':n,'automaticallyExecuted':0,'verified':False}))
if __name__=='__main__':main()
