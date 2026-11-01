#!/usr/bin/env python3
"""v55 evidence-to-interface compiler: auditable read-only client controls."""
import argparse,json,re
from pathlib import Path
from balanced_discovery_v54 import analyze

MAX_FEATURES=120
SERVICE_ROOTS={"Workspace","Players","ReplicatedStorage","ReplicatedFirst","Lighting","StarterGui","StarterPack","StarterPlayer","SoundService","Teams"}
CATEGORIES=(("Training",("strength","weight","lift","treadmill","machine","training","gym")),
 ("Progress",("leaderstats","rebirth","rank","level","wins","kills","coins","currency")),
 ("Pets",("pet","egg","hatch","enchant")),
 ("World",("portal","teleport","chest","boss","quest","event")),
 ("Interface",("gui","button","menu","prompt","text")),
 ("Other",()))
def classify(path,cls):
    s=(path+" "+cls).lower()
    for category,terms in CATEGORIES:
        if terms and any(t in s for t in terms):return category
    return "Other"
def parse_path(path):
    if not isinstance(path,str):return None
    root,sep,tail=path.partition("/")
    if root not in SERVICE_ROOTS:return None
    if not sep:return [root]
    segments=[root]
    for segment in tail.split("/"):
        m=re.fullmatch(r'("(?:[^"\\]|\\.)*")#([1-9][0-9]*)@([A-Za-z][A-Za-z0-9]*)',segment)
        if not m:return None
        name=json.loads(m.group(1))
        if not isinstance(name,str) or len(name)>250:return None
        segments.append({"name":name,"ordinal":int(m.group(2)),"className":m.group(3)})
    return segments
def compile_features(report):
    if report.get("schemaVersion")!="54.analysis":raise ValueError("Expected v54 analysis")
    if type(report.get("placeId")) is not int or report["placeId"]<=0:raise ValueError("Invalid place")
    features=[]
    for row in report.get("paths",[]):
        if not isinstance(row,dict):continue
        path=row.get("path")
        if not isinstance(path,str):continue
        resolved=parse_path(path)
        if resolved is None:continue
        if len(resolved)<2:continue
        cls=row.get("className","")
        if not isinstance(cls,str):continue
        category=classify(path,cls)
        interesting=row.get("valueChanged") or row.get("priority") or cls in ("RemoteEvent","RemoteFunction","ProximityPrompt","TextButton","ImageButton","Tool","IntValue","NumberValue","BoolValue","StringValue")
        if not interesting:continue
        features.append({"id":"inspect-"+str(len(features)+1),"category":category,
                         "path":path,"segments":resolved,"className":cls,
                         "observedSamples":row.get("observedSamples",0),
                         "changed":bool(row.get("valueChanged")),
                         "mode":"inspect","serverOutcomeVerified":False,
                         "gameplayActionVerified":False,
                         "evidence":"observed-client-instance"})
        if len(features)>=MAX_FEATURES:break
    return {"schemaVersion":"55.0","placeId":report["placeId"],"features":features,
            "capabilities":{"liveInspection":True,"remoteInvocation":False,
                            "automaticGameplayActions":False,"antiCheatBypass":False},
            "limitations":["Only client-visible instances are inspected",
                           "Sibling ordinals can change as instances spawn or disappear",
                           "Observed value changes do not establish causality"]}
def luau_quote(value):return json.dumps(value,ensure_ascii=True)
def render(contract):
    if contract.get("schemaVersion")!="55.0":raise ValueError("Invalid contract")
    place=contract["placeId"]
    if type(place)!=int or place<=0:raise ValueError("Invalid place")
    rows=[]
    for f in contract["features"]:
        if f.get("mode")!="inspect" or f.get("gameplayActionVerified") is not False:raise ValueError("Unsafe feature")
        if parse_path(f["path"])!=f["segments"]:raise ValueError("Path mismatch")
        parts=[luau_quote(f["segments"][0])]
        for part in f["segments"][1:]:
            parts.append('{name='+luau_quote(part["name"])+',ordinal='+str(part["ordinal"])+',className='+luau_quote(part["className"])+'}')
        rows.append('{category='+luau_quote(f["category"])+',className='+luau_quote(f["className"])+',path='+luau_quote(f["path"])+',segments={'+','.join(parts)+'},changed='+str(f["changed"]).lower()+'}')
    template=r'''-- Lycoles v55: read-only live evidence explorer, no gameplay actions.
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if not player or game.PlaceId~=PLACE_ID then return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV55")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV55" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(630,490) panel.Position=UDim2.fromScale(.06,.18)
panel.BackgroundColor3=Color3.fromRGB(25,30,38) panel.Parent=gui
local function text(parent,y,h,value)
 local t=Instance.new("TextLabel")
 t.Position=UDim2.fromOffset(10,y) t.Size=UDim2.new(1,-20,0,h)
 t.BackgroundTransparency=1 t.TextColor3=Color3.fromRGB(240,240,240)
 t.TextXAlignment=Enum.TextXAlignment.Left t.TextWrapped=true t.Text=value
 t.Parent=parent return t
end
text(panel,8,30,"Lycoles v55 | Evidence Explorer (inspection only)")
local status=text(panel,40,50,"Select an observed item to inspect its current client state.")
local filter=Instance.new("TextBox")
filter.Position=UDim2.fromOffset(10,95) filter.Size=UDim2.new(1,-20,0,34)
filter.PlaceholderText="Filter by category, class or path" filter.Text=""
filter.Parent=panel
local scroll=Instance.new("ScrollingFrame")
scroll.Position=UDim2.fromOffset(10,135) scroll.Size=UDim2.new(1,-20,1,-180)
scroll.CanvasSize=UDim2.fromOffset(0,0) scroll.ScrollBarThickness=8
scroll.Parent=panel
local layout=Instance.new("UIListLayout") layout.Padding=UDim.new(0,4) layout.Parent=scroll
local footer=text(panel,452,26,"Client-visible evidence is not proof of server-side gameplay effects.")
local rows=ROWS
local function resolve(parts)
 local root=parts[1]
 local obj
 if root=="Workspace" then obj=workspace
 else
  local ok,res=pcall(function() return game:GetService(root) end)
  if not ok then return nil,"Missing service" end
  obj=res
 end
 for i=2,#parts do
  local step=parts[i]
  local matches={}
  local ok,children=pcall(function() return obj:GetChildren() end)
  if not ok then return nil,"Cannot read children" end
  for _,child in ipairs(children) do
   if child.Name==step.name and child.ClassName==step.className then
    table.insert(matches,child)
   end
  end
  if #matches<step.ordinal then return nil,"Object absent or moved" end
  obj=matches[step.ordinal]
 end
 return obj,nil
end
local function inspect(row)
 local obj,err=resolve(row.segments)
 if not obj then status.Text="Unavailable: "..err return end
 local value="No safe scalar value"
 local ok,res=pcall(function()
  if obj:IsA("ValueBase") then return tostring(obj.Value) end
  if obj:IsA("TextLabel") or obj:IsA("TextButton") then return obj.Text end
  if obj:IsA("ProximityPrompt") then return tostring(obj.Enabled) end
  return nil
 end)
 if ok and res~=nil then value=tostring(res):sub(1,160) end
 status.Text=row.category.." | "..obj.ClassName.." | "..value
end
local function refresh()
 for _,child in ipairs(scroll:GetChildren()) do
  if child:IsA("TextButton") then child:Destroy() end
 end
 local query=string.lower(filter.Text)
 local count=0
 for _,row in ipairs(rows) do
  local hay=string.lower(row.category.." "..row.className.." "..row.path)
  if query=="" or string.find(hay,query,1,true) then
   local btn=Instance.new("TextButton")
   btn.Size=UDim2.new(1,-12,0,36)
   btn.BackgroundColor3=Color3.fromRGB(43,51,63)
   btn.TextColor3=Color3.fromRGB(245,245,245)
   btn.TextXAlignment=Enum.TextXAlignment.Left
   btn.Text=" ["..row.category.."] "..row.className.." | "..string.sub(row.path,1,70)
   btn.Parent=scroll
   btn.MouseButton1Click:Connect(function() inspect(row) end)
   count+=1
  end
 end
 scroll.CanvasSize=UDim2.fromOffset(0,count*40)
 footer.Text=tostring(count).." inspected candidates | read-only, no remote calls"
end
filter:GetPropertyChangedSignal("Text"):Connect(refresh)
refresh()
'''
    return template.replace("PLACE_ID",str(place)).replace("ROWS","{"+",".join(rows)+"}")
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v55"))
    a=p.parse_args()
    if a.receipt.stat().st_size>50_000_000:raise ValueError("Receipt exceeds 50 MB")
    report=analyze(a.receipt.read_text(encoding="utf-8-sig"),a.place_id)
    contract=compile_features(report)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"feature-contract-v55.json").write_text(json.dumps(contract,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (a.output/"evidence-explorer-v55.luau").write_text(render(contract),encoding="utf-8")
    (a.output/"evidence-analysis-v55.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("v55 compiled",len(contract["features"]),"read-only inspection controls; no gameplay actions verified")
if __name__=="__main__":main()
