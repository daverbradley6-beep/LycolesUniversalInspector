#!/usr/bin/env python3
"""Lycoles v74: lossless page-oriented GUI capture and merging.

Use v74 scanner in Roblox; copy each PAGE_BEGIN...PAGE_END chunk separately.
No remotes or game state mutation.
"""
import argparse,json,re,hashlib
from pathlib import Path
from collections import Counter
PAGE=100
LUA=r'''-- Lycoles v74 | Paginated GUI export
local Players=game:GetService("Players")
local Http=game:GetService("HttpService")
local pg=Players.LocalPlayer:WaitForChild("PlayerGui")
if game.PlaceId~=__PLACE__ then warn("Lycoles v74: place mismatch") return end
local old=pg:FindFirstChild("LycolesV74") if old then old:Destroy() end
local gui=Instance.new("ScreenGui") gui.Name="LycolesV74" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame") panel.Size=UDim2.fromOffset(590,210)
panel.Position=UDim2.new(.12,0,.18,0) panel.BackgroundColor3=Color3.fromRGB(23,31,48) panel.Parent=gui
local function button(text,x,y,w)
 local b=Instance.new("TextButton") b.Text=text b.Size=UDim2.fromOffset(w,34)
 b.Position=UDim2.fromOffset(x,y) b.Parent=panel return b
end
local scan=button("Rescan",8,8,105)
local prev=button("Previous",120,8,105)
local nextB=button("Next",232,8,105)
local export=button("Export page",344,8,130)
local close=button("X",536,8,46)
local status=Instance.new("TextLabel") status.Size=UDim2.new(1,-16,0,140)
status.Position=UDim2.fromOffset(8,52) status.BackgroundTransparency=1
status.TextColor3=Color3.new(1,1,1) status.TextWrapped=true status.Parent=panel
local records={} local current=1 local session=""
local function path(node)
 local names={} local segments={}
 while node and node~=pg do
  table.insert(names,1,node.Name)
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
 return names,segments
end
local function visible(node)
 while node and node~=pg do
  if node:IsA("GuiObject") and not node.Visible then return false end
  if node:IsA("ScreenGui") and not node.Enabled then return false end
  node=node.Parent
 end
 return true
end
local function pages() return math.max(1,math.ceil(#records/__PAGE__)) end
local function render()
 current=math.clamp(current,1,pages())
 local first=(current-1)*__PAGE__+1
 local last=math.min(current*__PAGE__,#records)
 status.Text="Lycoles v74 | "..#records.." controls\nCapture ID: "..session..
 "\nPage "..current.."/"..pages().." ("..first.."-"..last..")"..
 "\nClick Export page, copy the console block into a text file."..
 "\nThen click Next. Do not rescan between pages."
end
local function gather()
 records={}
 for _,node in ipairs(pg:GetDescendants()) do
  if #records>=__LIMIT__ then break end
  if (node:IsA("TextButton") or node:IsA("ImageButton")) and not node:IsDescendantOf(gui) then
   local names,segments=path(node)
   if names then
    table.insert(records,{className=node.ClassName,path=names,uniquePath=segments,
      text=node:IsA("TextButton") and node.Text or "",
      active=node.Active,visible=node.Visible,effectiveVisible=visible(node)})
   end
  end
 end
 session=Http:GenerateGUID(false) current=1 render()
end
scan.MouseButton1Click:Connect(gather)
prev.MouseButton1Click:Connect(function() current-=1 render() end)
nextB.MouseButton1Click:Connect(function() current+=1 render() end)
close.MouseButton1Click:Connect(function() gui:Destroy() end)
export.MouseButton1Click:Connect(function()
 local total=#records
 local first=(current-1)*__PAGE__+1
 local last=math.min(current*__PAGE__,total)
 print("LYCOLES_V74_PAGE_BEGIN "..Http:JSONEncode({schemaVersion="74.page",placeId=game.PlaceId,
  captureId=session,page=current,pageSize=__PAGE__,total=total,first=first,last=last}))
 for i=first,last do print("LYCOLES_V74_ITEM "..i.." "..Http:JSONEncode(records[i])) end
 print("LYCOLES_V74_PAGE_END "..Http:JSONEncode({captureId=session,page=current,first=first,last=last}))
end)
gather()
'''
def script(place_id,limit=20000,page_size=100):
 if type(place_id) is not int or place_id<=0: raise ValueError("invalid place")
 if type(limit) is not int or not 1<=limit<=20000: raise ValueError("invalid limit")
 if type(page_size) is not int or not 1<=page_size<=200: raise ValueError("invalid page size")
 return LUA.replace("__PLACE__",str(place_id)).replace("__LIMIT__",str(limit)).replace("__PAGE__",str(page_size))
def parse_page(text):
 pages=[]; cur=None
 for line in text.splitlines():
  if "LYCOLES_V74_PAGE_BEGIN " in line:
   if cur: pages.append(cur)
   try: head=json.loads(line.split("LYCOLES_V74_PAGE_BEGIN ",1)[1])
   except json.JSONDecodeError: cur=None;continue
   cur={"header":head,"items":{},"end":None}
  elif cur and "LYCOLES_V74_ITEM " in line:
   raw=line.split("LYCOLES_V74_ITEM ",1)[1]
   i,sep,body=raw.partition(" ")
   if not sep or not i.isdecimal():continue
   try: r=json.loads(body)
   except json.JSONDecodeError:continue
   index=int(i)
   if index in cur["items"] and cur["items"][index]!=r:raise ValueError("conflicting item")
   cur["items"][index]=r
  elif cur and "LYCOLES_V74_PAGE_END " in line:
   try:cur["end"]=json.loads(line.split("LYCOLES_V74_PAGE_END ",1)[1])
   except json.JSONDecodeError:pass
 if cur:pages.append(cur)
 return pages
def merge(texts,place_id,capture_id=None):
 allpages=[]
 for text in texts:allpages.extend(parse_page(text))
 eligible=[]
 for p in allpages:
  h=p["header"]
  if not isinstance(h,dict) or h.get("schemaVersion")!="74.page" or h.get("placeId")!=place_id:continue
  if not isinstance(h.get("captureId"),str) or not h["captureId"]:continue
  if capture_id and h["captureId"]!=capture_id:continue
  n=h.get("total");size=h.get("pageSize");number=h.get("page")
  if type(n) is not int or not 0<=n<=20000 or type(size) is not int or not 1<=size<=200 or type(number) is not int or not 1<=number<=max(1,(n+size-1)//size):continue
  first=(number-1)*size+1;last=min(number*size,n)
  if h.get("first")!=first or h.get("last")!=last:continue
  if p["end"]!={"captureId":h["captureId"],"page":number,"first":first,"last":last}:continue
  if set(p["items"])!=set(range(first,last+1)):continue
  eligible.append(p)
 if not eligible:raise ValueError("no complete valid page blocks")
 groups={}
 for p in eligible:
  h=p["header"];key=(h["captureId"],h["total"],h["pageSize"])
  groups.setdefault(key,{})
  number=h["page"]
  if number in groups[key] and groups[key][number]!=p["items"]:raise ValueError("conflicting page")
  groups[key][number]=p["items"]
 if capture_id:
  matches=[(k,v) for k,v in groups.items() if k[0]==capture_id]
  if len(matches)!=1:raise ValueError("ambiguous capture")
  key,selected=matches[0]
 else:
  if len(groups)!=1:raise ValueError("multiple capture sessions: pass --capture-id")
  key,selected=next(iter(groups.items()))
 session,total,size=key
 records=[]
 for number in sorted(selected):
  for index,r in sorted(selected[number].items()):
   if not isinstance(r,dict) or r.get("className") not in ("TextButton","ImageButton"):raise ValueError("invalid class")
   path=r.get("path");up=r.get("uniquePath")
   if not isinstance(path,list) or not 1<=len(path)<=30 or any(not isinstance(s,str) or not s or len(s)>200 for s in path):raise ValueError("invalid path")
   if not isinstance(up,list) or len(up)!=len(path):raise ValueError("missing uniquePath")
   for seg,name in zip(up,path):
    if not isinstance(seg,dict) or seg.get("name")!=name or not isinstance(seg.get("className"),str) or type(seg.get("ordinal")) is not int or not 1<=seg["ordinal"]<=100000:raise ValueError("invalid segment")
   records.append({"index":index,"className":r["className"],"path":path,"uniquePath":up,
    "text":str(r.get("text",""))[:160],"visible":r.get("visible") is True,
    "active":r.get("active") is True,"effectiveVisible":r.get("effectiveVisible") is True})
 counts=Counter(tuple(r["path"]) for r in records)
 for r in records:r["ambiguousPath"]=counts[tuple(r["path"])]>1
 missing=sorted(set(range(1,max(1,(total+size-1)//size)+1))-set(selected))
 return {"schemaVersion":"74.import","placeId":place_id,"captureId":session,"expected":total,
  "recovered":len(records),"complete":not missing,"missingPages":missing,
  "duplicatePathCount":sum(v-1 for v in counts.values() if v>1),"controls":records}
def candidates(data):
 return {"schemaVersion":"72.candidates","placeId":data["placeId"],"sourceComplete":data["complete"],
  "verifiedActions":0,"candidates":[{"id":f"ui_{r['index']}","label":r["text"] or r["path"][-1],
  "action":{"type":"local_gui_activate","className":r["className"],"path":r["path"],"uniquePath":r["uniquePath"]},
  "outcome":None,"status":"unverified_requires_outcome","ambiguousPath":r["ambiguousPath"],
  "effectiveVisible":r["effectiveVisible"]} for r in data["controls"]]}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument("--place-id",required=True,type=int)
 p.add_argument("--output",type=Path,default=Path("build/release-v74"))
 p.add_argument("--gui-log",type=Path,action="append",default=[])
 p.add_argument("--capture-id")
 p.add_argument("--page-size",type=int,default=100)
 a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 (a.output/"gui-discovery-v74.luau").write_text(script(a.place_id,page_size=a.page_size),encoding="utf-8")
 if a.gui_log:
  texts=[]
  for f in a.gui_log:
   if not f.is_file() or f.stat().st_size>30_000_000:p.error("missing or oversized log "+str(f))
   texts.append(f.read_text(encoding="utf-8-sig",errors="replace"))
  data=merge(texts,a.place_id,a.capture_id)
  for name,object_ in (("gui-import-v74.json",data),("gui-candidates-v74.json",candidates(data))):
   (a.output/name).write_text(json.dumps(object_,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
  print(json.dumps({"recovered":data["recovered"],"expected":data["expected"],"complete":data["complete"],"missingPages":data["missingPages"],"duplicatePaths":data["duplicatePathCount"]}))
if __name__=="__main__":main()
