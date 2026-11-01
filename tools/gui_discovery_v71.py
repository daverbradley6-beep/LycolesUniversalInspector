#!/usr/bin/env python3
"""v71 Roblox UI discovery and local-action contract candidate generator.

Outputs are suggestions, not verified action contracts. No remote calls.
"""
import argparse
import json
import re
from pathlib import Path

MAX_ITEMS=500
MAX_BYTES=10_000_000
ID=re.compile(r"[^a-z0-9_]+")
LUA=r'''-- Lycoles v71 | Local GUI control discovery
local Players=game:GetService("Players")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("Lycoles v71: wrong place") return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV71")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV71" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(590,400) panel.Position=UDim2.new(0.08,0,0.15,0)
panel.BackgroundColor3=Color3.fromRGB(24,32,47) panel.Parent=gui
local heading=Instance.new("TextLabel")
heading.Size=UDim2.new(1,-120,0,36) heading.BackgroundTransparency=1
heading.TextColor3=Color3.new(1,1,1) heading.Text="  Lycoles v71 | UI discovery"
heading.TextXAlignment=Enum.TextXAlignment.Left heading.Parent=panel
local scan=Instance.new("TextButton")
scan.Size=UDim2.fromOffset(90,32) scan.Position=UDim2.new(1,-132,0,3)
scan.Text="Scan" scan.Parent=panel
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(36,32) close.Position=UDim2.new(1,-38,0,3)
close.Text="X" close.Parent=panel
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local export=Instance.new("TextButton")
export.Size=UDim2.fromOffset(90,32) export.Position=UDim2.fromOffset(8,40)
export.Text="Export" export.Parent=panel
local search=Instance.new("TextBox")
search.Size=UDim2.new(1,-110,0,32) search.Position=UDim2.fromOffset(106,40)
search.PlaceholderText="Filter controls" search.Text="" search.ClearTextOnFocus=false search.Parent=panel
local scroller=Instance.new("ScrollingFrame")
scroller.Size=UDim2.new(1,-16,1,-84) scroller.Position=UDim2.fromOffset(8,78)
scroller.ScrollBarThickness=5 scroller.Parent=panel
local layout=Instance.new("UIListLayout")
layout.Parent=scroller
layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
 scroller.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+6)
end)
local HttpService=game:GetService("HttpService")
local records={}
local function pathFor(object)
 local result={}
 local node=object
 while node and node~=pg do
  table.insert(result,1,node.Name)
  node=node.Parent
 end
 if node~=pg then return nil end
 return result
end
local function display()
 for _,child in ipairs(scroller:GetChildren()) do
  if child:IsA("TextLabel") then child:Destroy() end
 end
 local q=search.Text:lower()
 for _,r in ipairs(records) do
  local text=r.className.." | "..table.concat(r.path," / ").." | "..r.text
  if q=="" or text:lower():find(q,1,true) then
   local l=Instance.new("TextLabel")
   l.Size=UDim2.new(1,-8,0,28)
   l.TextXAlignment=Enum.TextXAlignment.Left l.TextTruncate=Enum.TextTruncate.AtEnd
   l.TextColor3=Color3.new(1,1,1)
   l.BackgroundColor3=Color3.fromRGB(40,52,72)
   l.Text="  "..text l.Parent=scroller
  end
 end
end
local function gather()
 records={}
 for _,node in ipairs(pg:GetDescendants()) do
  if #records>=__LIMIT__ then break end
  if node:IsA("TextButton") or node:IsA("ImageButton") then
   if not node:IsDescendantOf(gui) then
    local path=pathFor(node)
    if path then
     local txt=""
     if node:IsA("TextButton") then txt=node.Text end
     table.insert(records,{className=node.ClassName,path=path,text=txt,
      visible=node.Visible,active=node.Active})
    end
   end
  end
 end
 display()
end
scan.MouseButton1Click:Connect(gather)
search:GetPropertyChangedSignal("Text"):Connect(display)
export.MouseButton1Click:Connect(function()
 local payload={schemaVersion="71.gui",placeId=game.PlaceId,controls=records}
 print("LYCOLES_V71_GUI_BEGIN "..HttpService:JSONEncode({placeId=game.PlaceId,count=#records}))
 for i,r in ipairs(records) do
  print("LYCOLES_V71_GUI_ITEM "..i.." "..HttpService:JSONEncode(r))
 end
 print("LYCOLES_V71_GUI_END "..#records)
end)
gather()
'''
def script(place_id,limit=MAX_ITEMS):
    if type(place_id) is not int or place_id<=0: raise ValueError("invalid place ID")
    if type(limit) is not int or not 1<=limit<=MAX_ITEMS: raise ValueError("invalid limit")
    return LUA.replace("__PLACE__",str(place_id)).replace("__LIMIT__",str(limit))

def parse(text,place_id):
    begin=None; items={}; end=None
    for line in text.splitlines():
        if "LYCOLES_V71_GUI_BEGIN " in line:
            if begin is not None: raise ValueError("multiple exports; provide one complete export")
            begin=json.loads(line.split("LYCOLES_V71_GUI_BEGIN ",1)[1])
        elif "LYCOLES_V71_GUI_ITEM " in line:
            raw=line.split("LYCOLES_V71_GUI_ITEM ",1)[1]
            index,sep,body=raw.partition(" ")
            if not sep or not index.isdecimal(): raise ValueError("invalid item")
            i=int(index); candidate=json.loads(body)
            if i in items and items[i]!=candidate: raise ValueError("conflicting item")
            items[i]=candidate
        elif "LYCOLES_V71_GUI_END " in line:
            value=line.split("LYCOLES_V71_GUI_END ",1)[1].strip()
            if not value.isdecimal(): raise ValueError("invalid end")
            end=int(value)
    if not isinstance(begin,dict) or begin.get("placeId")!=place_id: raise ValueError("missing header or place mismatch")
    count=begin.get("count")
    if type(count) is not int or not 0<=count<=MAX_ITEMS: raise ValueError("invalid count")
    if end!=count or set(items)!=set(range(1,count+1)): raise ValueError("incomplete GUI export")
    output=[]
    for i in range(1,count+1):
        r=items[i]
        if not isinstance(r,dict) or r.get("className") not in ("TextButton","ImageButton"):
            raise ValueError("invalid control class")
        path=r.get("path")
        if not isinstance(path,list) or not 1<=len(path)<=20:
            raise ValueError("invalid control path")
        if any(not isinstance(p,str) or not p or len(p)>160 or any(ord(c)<32 for c in p) for p in path):
            raise ValueError("invalid control name")
        output.append({"className":r["className"],"path":path,
                       "text":str(r.get("text",""))[:160],
                       "visible":r.get("visible") is True,"active":r.get("active") is True})
    return output

def make_candidates(controls,place_id):
    # Do not guess leaderstats or infer successful action from control labels.
    rows=[]; used=set()
    for index,r in enumerate(controls,1):
        slug=ID.sub("_",r["path"][-1].casefold()).strip("_")[:30] or "control"
        identifier=f"ui_{index}_{slug}"
        if identifier in used: raise ValueError("duplicate generated id")
        used.add(identifier)
        rows.append({"id":identifier,"label":(r["text"] or r["path"][-1])[:160],
            "action":{"type":"local_gui_activate","className":r["className"],"path":r["path"]},
            "outcome":None,"status":"requires_outcome_and_runtime_validation",
            "observedVisible":r["visible"],"observedActive":r["active"]})
    return {"schemaVersion":"71.candidates","placeId":place_id,"candidates":rows,
            "actionContractsVerified":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v71"))
    p.add_argument("--gui-log",type=Path)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    path=a.output/"gui-discovery-v71.luau"
    path.write_text(script(a.place_id),encoding="utf-8")
    print("Generated",path)
    if a.gui_log:
        if not a.gui_log.is_file(): p.error("GUI log not found")
        if a.gui_log.stat().st_size>MAX_BYTES: p.error("GUI log too large")
        controls=parse(a.gui_log.read_text(encoding="utf-8-sig",errors="replace"),a.place_id)
        result=make_candidates(controls,a.place_id)
        out=a.output/"gui-candidates-v71.json"
        out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print("Generated",out,"with",len(controls),"unverified controls")
if __name__=="__main__": main()
