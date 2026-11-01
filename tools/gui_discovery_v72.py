#!/usr/bin/env python3
"""v72 paginated Roblox GUI discovery with partial-export recovery."""
import argparse,json
from pathlib import Path
from collections import Counter
LUA=r'''-- Lycoles v72: read-only GUI discovery
local Players=game:GetService("Players")
local Http=game:GetService("HttpService")
local player=Players.LocalPlayer
if game.PlaceId~=__PLACE__ then warn("v72: wrong place") return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV72")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV72" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(650,440)
panel.Position=UDim2.new(.08,0,.13,0) panel.BackgroundColor3=Color3.fromRGB(24,32,48) panel.Parent=gui
local function button(name,text,x,y,w)
 local b=Instance.new("TextButton") b.Name=name b.Text=text
 b.Size=UDim2.fromOffset(w,30) b.Position=UDim2.fromOffset(x,y) b.Parent=panel return b
end
local scan=button("Scan","Scan",8,5,95)
local export=button("Export","Export all",110,5,110)
local prev=button("Previous","Previous",227,5,95)
local nextPage=button("Next","Next",329,5,95)
local close=button("Close","X",600,5,40)
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local search=Instance.new("TextBox") search.Size=UDim2.new(1,-16,0,34)
search.Position=UDim2.fromOffset(8,41) search.PlaceholderText="Filter paths / labels"
search.Text="" search.ClearTextOnFocus=false search.Parent=panel
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-16,0,25)
status.Position=UDim2.fromOffset(8,77) status.BackgroundTransparency=1
status.TextColor3=Color3.new(1,1,1) status.Parent=panel
local scroll=Instance.new("ScrollingFrame") scroll.Size=UDim2.new(1,-16,1,-110)
scroll.Position=UDim2.fromOffset(8,105) scroll.ScrollBarThickness=5 scroll.Parent=panel
local layout=Instance.new("UIListLayout") layout.Parent=scroll
layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
 scroll.CanvasSize=UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+8)
end)
local records={} local page=1 local PAGE=100
local function pathFor(node)
 local path={} local segments={}
 while node and node~=pg do
  table.insert(path,1,node.Name)
  local ordinal=1
  if node.Parent then
   for _,other in ipairs(node.Parent:GetChildren()) do
    if other==node then break end
    if other.Name==node.Name and other.ClassName==node.ClassName then ordinal+=1 end
   end
  end
  table.insert(segments,1,{name=node.Name,className=node.ClassName,ordinal=ordinal})
  node=node.Parent
 end
 if node~=pg then return nil,nil end
 return path,segments
end
local function effectiveVisible(node)
 while node and node~=pg do
  if node:IsA("GuiObject") and not node.Visible then return false end
  if node:IsA("ScreenGui") and not node.Enabled then return false end
  node=node.Parent
 end
 return true
end
local function render()
 for _,child in ipairs(scroll:GetChildren()) do if child:IsA("TextLabel") then child:Destroy() end end
 local filtered={} local q=search.Text:lower()
 for _,r in ipairs(records) do
  local label=r.className.." | "..table.concat(r.path," / ").." | "..r.text
  if q=="" or label:lower():find(q,1,true) then table.insert(filtered,{record=r,label=label}) end
 end
 local pages=math.max(1,math.ceil(#filtered/PAGE))
 page=math.clamp(page,1,pages)
 for i=(page-1)*PAGE+1,math.min(page*PAGE,#filtered) do
  local e=filtered[i]
  local line=Instance.new("TextLabel") line.Size=UDim2.new(1,-8,0,27)
  line.BackgroundColor3=Color3.fromRGB(40,52,73)
  line.TextColor3=Color3.new(1,1,1) line.TextXAlignment=Enum.TextXAlignment.Left
  line.TextTruncate=Enum.TextTruncate.AtEnd
  line.Text=(e.record.effectiveVisible and "[shown] " or "[hidden] ")..e.label
  line.Parent=scroll
 end
 status.Text=#records.." discovered | "..#filtered.." matched | page "..page.."/"..pages
end
local function gather()
 records={}
 for _,node in ipairs(pg:GetDescendants()) do
  if #records>=__LIMIT__ then break end
  if (node:IsA("TextButton") or node:IsA("ImageButton")) and not node:IsDescendantOf(gui) then
   local path,segments=pathFor(node)
   if path then table.insert(records,{className=node.ClassName,path=path,uniquePath=segments,
    text=node:IsA("TextButton") and node.Text or "",visible=node.Visible,
    active=node.Active,effectiveVisible=effectiveVisible(node)}) end
  end
 end
 page=1 render()
end
scan.MouseButton1Click:Connect(gather)
search:GetPropertyChangedSignal("Text"):Connect(function() page=1 render() end)
prev.MouseButton1Click:Connect(function() page-=1 render() end)
nextPage.MouseButton1Click:Connect(function() page+=1 render() end)
export.MouseButton1Click:Connect(function()
 local count=#records local pages=math.ceil(count/PAGE)
 print("LYCOLES_V72_BEGIN "..Http:JSONEncode({schemaVersion="72.gui",placeId=game.PlaceId,count=count,pageSize=PAGE,pages=pages}))
 for p=1,pages do
  print("LYCOLES_V72_PAGE_BEGIN "..p)
  for i=(p-1)*PAGE+1,math.min(p*PAGE,count) do
   print("LYCOLES_V72_ITEM "..i.." "..Http:JSONEncode(records[i]))
  end
  print("LYCOLES_V72_PAGE_END "..p)
 end
 print("LYCOLES_V72_END "..count)
end)
gather()
'''
def script(place_id,limit=20000):
    if type(place_id) is not int or place_id<=0: raise ValueError("invalid place ID")
    if type(limit) is not int or not 1<=limit<=20000: raise ValueError("invalid limit")
    return LUA.replace("__PLACE__",str(place_id)).replace("__LIMIT__",str(limit))
def import_log(text,place_id,strict=False):
    sessions=[]; current=None
    for line in text.splitlines():
        if "LYCOLES_V72_BEGIN " in line:
            if current: sessions.append(current)
            current={"header":json.loads(line.split("LYCOLES_V72_BEGIN ",1)[1]),"items":{},"pages":set(),"end":None}
        elif current and "LYCOLES_V72_ITEM " in line:
            raw=line.split("LYCOLES_V72_ITEM ",1)[1]
            index,sep,value=raw.partition(" ")
            if sep and index.isdecimal():
                try: record=json.loads(value)
                except json.JSONDecodeError: continue
                i=int(index)
                if i in current["items"] and current["items"][i]!=record: raise ValueError("conflicting duplicate item")
                current["items"][i]=record
        elif current and "LYCOLES_V72_PAGE_END " in line:
            value=line.split("LYCOLES_V72_PAGE_END ",1)[1].strip()
            if value.isdecimal(): current["pages"].add(int(value))
        elif current and "LYCOLES_V72_END " in line:
            value=line.split("LYCOLES_V72_END ",1)[1].strip()
            if value.isdecimal(): current["end"]=int(value)
    if current: sessions.append(current)
    valid=[]
    for s in sessions:
        h=s["header"]
        if not isinstance(h,dict) or h.get("schemaVersion")!="72.gui" or h.get("placeId")!=place_id: continue
        count=h.get("count"); pages=h.get("pages"); size=h.get("pageSize")
        if type(count) is not int or not 0<=count<=20000 or type(size) is not int or not 1<=size<=250 or type(pages) is not int or pages!=(count+size-1)//size: continue
        for i,r in s["items"].items():
            if not 1<=i<=count or not isinstance(r,dict) or r.get("className") not in ("TextButton","ImageButton"): raise ValueError("invalid item")
            path=r.get("path")
            if not isinstance(path,list) or not 1<=len(path)<=30 or any(not isinstance(x,str) or not x or len(x)>200 or any(ord(c)<32 for c in x) for x in path): raise ValueError("invalid path")
            up=r.get("uniquePath")
            if up is not None and (not isinstance(up,list) or len(up)!=len(path) or any(not isinstance(seg,dict) or seg.get("name")!=name or not isinstance(seg.get("className"),str) or type(seg.get("ordinal")) is not int or not 1<=seg["ordinal"]<=100000 for seg,name in zip(up,path))): raise ValueError("invalid unique path")
        missing=[i for i in range(1,count+1) if i not in s["items"]]
        complete=not missing and s["end"]==count and len(s["pages"])==pages
        valid.append((complete,s,missing))
    if not valid: raise ValueError("no valid v72 session for place")
    complete,s,missing=next((x for x in reversed(valid) if x[0]),valid[-1])
    if strict and not complete: raise ValueError("incomplete export")
    controls=[]
    for i,r in sorted(s["items"].items()):
        controls.append({"index":i,"className":r["className"],"path":r["path"],
                         "uniquePath":r.get("uniquePath"),"text":str(r.get("text",""))[:200],
                         "visible":r.get("visible") is True,"active":r.get("active") is True,
                         "effectiveVisible":r.get("effectiveVisible") is True})
    paths=Counter(tuple(r["path"]) for r in controls)
    for r in controls: r["ambiguousPath"]=paths[tuple(r["path"])]>1
    return {"schemaVersion":"72.import","placeId":place_id,"complete":complete,"expected":s["header"]["count"],
            "recovered":len(controls),"missingIndices":missing,
            "missingPages":sorted(set(range(1,s["header"]["pages"]+1))-s["pages"]),
            "duplicatePathCount":sum(n-1 for n in paths.values() if n>1),
            "verifiedActions":0,"controls":controls}
def candidates(data):
    return {"schemaVersion":"72.candidates","placeId":data["placeId"],"sourceComplete":data["complete"],
            "verifiedActions":0,"candidates":[{"id":f"ui_{r['index']}","label":r["text"] or r["path"][-1],
            "action":{"type":"local_gui_activate","className":r["className"],"path":r["path"],"uniquePath":r["uniquePath"]},
            "outcome":None,"status":"unverified_requires_outcome",
            "ambiguousPath":r["ambiguousPath"],"effectiveVisible":r["effectiveVisible"]} for r in data["controls"]]}
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--gui-log",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/release-v72"))
    p.add_argument("--strict",action="store_true")
    p.add_argument("--limit",type=int,default=20000)
    a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    target=a.output/"gui-discovery-v72.luau"
    target.write_text(script(a.place_id,a.limit),encoding="utf-8")
    print("Generated",target)
    if a.gui_log:
        if not a.gui_log.is_file() or a.gui_log.stat().st_size>50_000_000: p.error("GUI log missing or too large")
        data=import_log(a.gui_log.read_text(encoding="utf-8-sig",errors="replace"),a.place_id,a.strict)
        for filename,object_ in [("gui-import-v72.json",data),("gui-candidates-v72.json",candidates(data))]:
            dest=a.output/filename
            dest.write_text(json.dumps(object_,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            print("Generated",dest)
        print(f"Recovered {data['recovered']}/{data['expected']}; complete={data['complete']}; duplicate paths={data['duplicatePathCount']}")
if __name__=="__main__": main()
