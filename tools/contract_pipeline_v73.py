#!/usr/bin/env python3
"""v73: compile explicitly configured v72 GUI candidates into local action runners."""
import argparse,json,re
from pathlib import Path
ID=re.compile(r"^[a-z][a-z0-9_]{0,47}$")
def validate(c):
 a,o=c["action"],c["outcome"]
 if not ID.fullmatch(c["id"]): raise ValueError("invalid id")
 if not isinstance(c["label"],str) or not 0<len(c["label"])<=160: raise ValueError("invalid label")
 if a["type"]!="local_gui_activate" or a["className"] not in ("TextButton","ImageButton"): raise ValueError("unsupported action")
 path=a["path"]
 if not isinstance(path,list) or not 1<=len(path)<=20 or any(not isinstance(x,str) or not 0<len(x)<=160 or any(ord(y)<32 for y in x) for x in path): raise ValueError("invalid path")
 unique=a.get("uniquePath")
 if unique is not None:
  if not isinstance(unique,list) or len(unique)!=len(path): raise ValueError("invalid uniquePath length")
  for seg,name in zip(unique,path):
   if not isinstance(seg,dict) or seg.get("name")!=name or not isinstance(seg.get("className"),str) or type(seg.get("ordinal")) is not int or not 1<=seg["ordinal"]<=100000: raise ValueError("invalid uniquePath segment")
  if unique[-1]["className"]!=a["className"]: raise ValueError("uniquePath class mismatch")
 if not isinstance(o,dict) or set(o)!={"type","stat","operator","target","timeoutSeconds"} or o["type"]!="leaderstat": raise ValueError("invalid outcome")
 if not isinstance(o["stat"],str) or not 0<len(o["stat"])<=160: raise ValueError("invalid stat")
 if o["operator"] not in ("changed","increased","decreased","equals"): raise ValueError("invalid operator")
 if o["operator"]=="equals":
  if not isinstance(o["target"],str) or not o["target"]: raise ValueError("invalid target")
 elif o["target"] is not None: raise ValueError("target must be null")
 if type(o["timeoutSeconds"]) not in (int,float) or not .5<=o["timeoutSeconds"]<=30: raise ValueError("invalid timeout")
def compile_contracts(catalog,outcomes,place_id):
 if not isinstance(catalog,dict) or catalog.get("schemaVersion")!="72.candidates": raise ValueError("expected v72 candidates")
 if not isinstance(outcomes,dict) or outcomes.get("schemaVersion")!="73.outcomes": raise ValueError("expected v73 outcomes")
 if type(place_id) is not int or place_id<=0 or catalog.get("placeId")!=place_id or outcomes.get("placeId")!=place_id: raise ValueError("place ID mismatch")
 if type(catalog.get("sourceComplete")) is not bool: raise ValueError("missing provenance")
 if not isinstance(catalog.get("candidates"),list) or not isinstance(outcomes.get("outcomes"),dict): raise ValueError("invalid inputs")
 by_id={}
 for c in catalog["candidates"]:
  if not isinstance(c,dict) or not isinstance(c.get("id"),str) or c["id"] in by_id: raise ValueError("invalid or duplicate candidate")
  by_id[c["id"]]=c
 contracts=[]; rejected=[]
 for key,outcome in outcomes["outcomes"].items():
  c=by_id.get(key)
  if c is None: rejected.append({"id":key,"reason":"unknown candidate"});continue
  action=c.get("action")
  if not isinstance(action,dict): rejected.append({"id":key,"reason":"invalid action"});continue
  if c.get("ambiguousPath") and not action.get("uniquePath"):
   rejected.append({"id":key,"reason":"ambiguous path without uniquePath"});continue
  contract={"id":key,"label":c.get("label"),"action":action,"outcome":outcome}
  try: validate(contract)
  except (ValueError,KeyError,TypeError) as exc: rejected.append({"id":key,"reason":str(exc)});continue
  contracts.append(contract)
 if len(contracts)>60: raise ValueError("maximum 60 contracts")
 return {"schemaVersion":"73.contracts","placeId":place_id,"contracts":contracts,"rejected":rejected,
         "sourceComplete":catalog["sourceComplete"],"actionContractsVerified":False}
def lua(value):
 if value is None:return "nil"
 if isinstance(value,str):return json.dumps(value,ensure_ascii=False)
 if isinstance(value,bool):return "true" if value else "false"
 if isinstance(value,(int,float)):return str(value)
 if isinstance(value,list):return "{"+",".join(lua(v) for v in value)+"}"
 if isinstance(value,dict):return "{"+",".join("["+lua(k)+"]="+lua(v) for k,v in value.items())+"}"
 raise ValueError("unsupported value")
LUA=r'''-- Lycoles v73 | Explicit local GUI contracts, no remote calls
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("Lycoles v73: wrong place") return end
local pg=player:WaitForChild("PlayerGui")
local previous=pg:FindFirstChild("LycolesV73")
if previous then previous:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV73" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(560,440)
panel.Position=UDim2.new(.1,0,.12,0) panel.BackgroundColor3=Color3.fromRGB(25,33,49) panel.Parent=gui
local title=Instance.new("TextLabel") title.Size=UDim2.new(1,-46,0,35)
title.BackgroundTransparency=1 title.TextColor3=Color3.new(1,1,1)
title.Text="Lycoles v73 | Contract runner" title.Parent=panel
local close=Instance.new("TextButton") close.Text="X" close.Size=UDim2.fromOffset(35,30)
close.Position=UDim2.new(1,-38,0,3) close.Parent=panel
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-12,1,-44)
scroll.Position=UDim2.fromOffset(6,38) scroll.ScrollBarThickness=5 scroll.Parent=panel
local layout=Instance.new("UIListLayout") layout.Padding=UDim.new(0,4) layout.Parent=scroll
layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
 scroll.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+8)
end)
local contracts=__CONTRACTS__
local function resolve(spec)
 local node=pg
 if spec.uniquePath then
  for _,seg in ipairs(spec.uniquePath) do
   local n=0 local found=nil
   for _,child in ipairs(node:GetChildren()) do
    if child.Name==seg.name and child.ClassName==seg.className then
     n+=1
     if n==seg.ordinal then found=child break end
    end
   end
   if not found then return nil end
   node=found
  end
 else
  for _,name in ipairs(spec.path) do
   node=node and node:FindFirstChild(name)
   if not node then return nil end
  end
 end
 return node
end
local function visible(node)
 while node and node~=pg do
  if node:IsA("GuiObject") and not node.Visible then return false end
  if node:IsA("ScreenGui") and not node.Enabled then return false end
  node=node.Parent
 end
 return true
end
local function stat(spec)
 local stats=player:FindFirstChild("leaderstats")
 local v=stats and stats:FindFirstChild(spec.stat)
 if not v or not v:IsA("ValueBase") then return nil end
 return v.Value
end
local function changed(spec,before,after)
 if before==nil or after==nil then return false end
 if spec.op=="changed" then return before~=after end
 if spec.op=="equals" then return tostring(after)==spec.target end
 if typeof(before)~="number" or typeof(after)~="number" then return false end
 if spec.op=="increased" then return after>before end
 if spec.op=="decreased" then return after<before end
 return false
end
local running=false
for _,spec in ipairs(contracts) do
 local b=Instance.new("TextButton") b.Size=UDim2.new(1,-10,0,42)
 b.Text=spec.label.." | ready" b.TextColor3=Color3.new(1,1,1)
 b.BackgroundColor3=Color3.fromRGB(48,62,87) b.Parent=scroll
 b.MouseButton1Click:Connect(function()
  if running then return end
  running=true b.Text=spec.label.." | checking..."
  task.spawn(function()
   local ok,err=pcall(function()
    local before=stat(spec)
    if before==nil then error("stat unavailable") end
    local target=resolve(spec)
    if not target or target.ClassName~=spec.className then error("UI control unavailable") end
    if not target.Active or not visible(target) then error("UI control inactive or hidden") end
    target:Activate()
    local passed=false local deadline=os.clock()+spec.timeout
    repeat
     task.wait(.15)
     passed=changed(spec,before,stat(spec))
    until passed or os.clock()>=deadline or not gui.Parent
    if not passed then error("outcome not observed before timeout") end
   end)
   if gui.Parent then b.Text=spec.label.." | "..(ok and "observed change" or ("failed: "..tostring(err))) end
   running=false
  end)
 end)
end
'''
def generate(data):
 if data.get("schemaVersion")!="73.contracts": raise ValueError("invalid contracts")
 rows=[]
 for c in data["contracts"]:
  a,o=c["action"],c["outcome"]
  rows.append({"label":c["label"],"path":a["path"],"uniquePath":a.get("uniquePath"),
               "className":a["className"],"stat":o["stat"],"op":o["operator"],
               "target":o["target"] or "","timeout":o["timeoutSeconds"]})
 return LUA.replace("__PLACE__",str(data["placeId"])).replace("__CONTRACTS__",lua(rows))
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--candidates",type=Path,required=True)
 p.add_argument("--outcomes",type=Path,required=True)
 p.add_argument("--place-id",type=int,required=True)
 p.add_argument("--output",type=Path,default=Path("build/release-v73"))
 a=p.parse_args()
 for path in (a.candidates,a.outcomes):
  if not path.is_file() or path.stat().st_size>50_000_000:p.error("missing or oversized input "+str(path))
 result=compile_contracts(json.loads(a.candidates.read_text(encoding="utf-8-sig")),
                          json.loads(a.outcomes.read_text(encoding="utf-8-sig")),a.place_id)
 a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"contracts-v73.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
 if result["contracts"]:(a.output/"contract-runner-v73.luau").write_text(generate(result),encoding="utf-8")
 print(json.dumps({"accepted":len(result["contracts"]),"rejected":result["rejected"],
                   "sourceComplete":result["sourceComplete"],"runnerGenerated":bool(result["contracts"])},ensure_ascii=False))
if __name__=="__main__":main()
