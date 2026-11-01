#!/usr/bin/env python3
"""v81 offline compiler: manually approved GUI contracts to bounded local-only Luau."""
import argparse,json,re
from pathlib import Path
MAX_ACTIONS=100
ALLOWED={"TextButton","ImageButton"}
def validate(doc,place):
 if not isinstance(doc,dict) or not isinstance(doc.get("contracts"),list):raise ValueError("contracts array required")
 if len(doc["contracts"])>MAX_ACTIONS:raise ValueError("too many contracts")
 if doc.get("placeId")!=place:raise ValueError("place mismatch")
 valid=[];ids=set()
 for c in doc["contracts"]:
  if not isinstance(c,dict) or c.get("approved") is not True:continue
  if c.get("executionEnabled") is True:raise ValueError("input contract cannot pre-enable execution")
  ident=c.get("id")
  if not isinstance(ident,str) or not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_-]{0,39}",ident):raise ValueError("invalid id")
  if ident in ids:raise ValueError("duplicate id")
  ids.add(ident)
  action=c.get("input")
  if not isinstance(action,list) or len(action)!=2 or action[0]!="gui":raise ValueError("only approved GUI actions supported")
  path=action[1]
  if isinstance(path,str):
   try:path=json.loads(path)
   except json.JSONDecodeError:raise ValueError("invalid GUI path")
  if not isinstance(path,list) or not 1<=len(path)<=30:raise ValueError("invalid GUI path")
  for segment in path:
   if not isinstance(segment,dict) or not isinstance(segment.get("name"),str) or not isinstance(segment.get("className"),str) or type(segment.get("ordinal")) is not int:raise ValueError("invalid segment")
   if not 1<=segment["ordinal"]<=1000 or len(segment["name"])>120 or len(segment["className"])>80:raise ValueError("segment bounds")
  if path[-1]["className"] not in ALLOWED:raise ValueError("not a GUI button")
  valid.append({"id":ident,"path":path})
 return valid
def compile_luau(contracts,place):
 payload=json.dumps(contracts,ensure_ascii=True,separators=(",",":"))
 # JSON encoded again as a Lua string literal to avoid injecting Luau through names.
 literal=json.dumps(payload,ensure_ascii=True)
 return '''-- Lycoles v81: explicit approval required. Local GUI only; no remotes.
local Players=game:GetService("Players")
local Http=game:GetService("HttpService")
if game.PlaceId~='''+str(place)+''' then warn("Lycoles: wrong place") return end
local player=Players.LocalPlayer
local pg=player:WaitForChild("PlayerGui")
local contracts=Http:JSONDecode('''+literal+''')
local function find(path)
 local current=pg
 for _,seg in ipairs(path) do
  local ordinal=0 local chosen=nil
  for _,child in ipairs(current:GetChildren()) do
   if child.Name==seg.name and child.ClassName==seg.className then
    ordinal+=1
    if ordinal==seg.ordinal then chosen=child break end
   end
  end
  if not chosen then return nil,"missing segment: "..seg.name end
  current=chosen
 end
 if not (current:IsA("TextButton") or current:IsA("ImageButton")) then return nil,"not a button" end
 return current
end
local actions={}
for _,contract in ipairs(contracts) do
 actions[contract.id]=function()
  local button,err=find(contract.path)
  if not button then return false,err end
  if not button:IsDescendantOf(pg) or not button.Visible or not button.Active then return false,"button unavailable" end
  return false,"unsupported: GuiButton has no public Activate() method; use real UI interaction"
 end
end
-- Expose only locally in this script's environment, not as a global.
-- To run an approved action, call actions["approved_id"]() from this script.
print("Lycoles v81: "..tostring(#contracts).." approved GUI contracts loaded; no actions auto-run")
'''
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",type=int,required=True)
 p.add_argument("--contracts",type=Path,required=True)
 p.add_argument("--output",type=Path,default=Path("build/release-v81"))
 a=p.parse_args()
 if a.place_id<=0:p.error("invalid place")
 doc=json.loads(a.contracts.read_text(encoding="utf-8-sig"))
 contracts=validate(doc,a.place_id)
 a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"approved-gui-v81.luau").write_text(compile_luau(contracts,a.place_id),encoding="utf-8")
 (a.output/"compile-report-v81.json").write_text(json.dumps({"schemaVersion":"81.compile","placeId":a.place_id,"approvedActions":len(contracts),"automaticallyExecuted":0,"verified":False},indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"approvedActions":len(contracts),"automaticallyExecuted":0,"verified":False}))
if __name__=="__main__":main()
