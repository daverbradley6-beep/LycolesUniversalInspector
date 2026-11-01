#!/usr/bin/env python3
"""v100 client-observable Roblox inspection report -> safe Luau GUI.

Produces a read-only LocalScript for games not owned by the user.
No server requests, input automation, hooking, bypasses or arbitrary execution.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

NAME=re.compile(r"^[A-Za-z0-9_ .:-]{1,80}$")
ALLOWED={"PlayerGui","Workspace","ReplicatedStorage","Players"}
MAX_ITEMS=150

def validate(report):
    if not isinstance(report,dict) or report.get("schemaVersion")!="100.client-observations":
        raise ValueError("invalid schema")
    place=report.get("placeId")
    if type(place)!=int or place<=0:raise ValueError("invalid place ID")
    items=report.get("observations")
    if not isinstance(items,list) or not 1<=len(items)<=MAX_ITEMS:
        raise ValueError("expected 1-150 observations")
    ids=set()
    for item in items:
        if not isinstance(item,dict):raise ValueError("observation must be object")
        ident=item.get("id")
        if not isinstance(ident,str) or not NAME.fullmatch(ident) or ident in ids:
            raise ValueError("invalid or duplicate observation ID")
        ids.add(ident)
        path=item.get("path")
        if not isinstance(path,list) or not 2<=len(path)<=12:
            raise ValueError("invalid path")
        if path[0] not in ALLOWED:
            raise ValueError("unsupported root")
        if any(not isinstance(p,str) or not NAME.fullmatch(p) for p in path):
            raise ValueError("invalid path component")
        if item.get("property") not in ("Name","ClassName","Visible","Text","Value","Enabled"):
            raise ValueError("unsupported property")
        if item.get("label") is not None and (
            not isinstance(item["label"],str) or len(item["label"])>100):
            raise ValueError("invalid label")
    return report

def lua(value):
    return json.dumps(value,ensure_ascii=True)

def compile_gui(report):
    validate(report)
    lines=[
        "-- Lycoles v100 read-only client observer; no server or input actions",
        "local Players = game:GetService('Players')",
        "local ReplicatedStorage = game:GetService('ReplicatedStorage')",
        "local player = Players.LocalPlayer",
        "if game.PlaceId ~= "+str(report["placeId"])+" then return end",
        "local roots = { PlayerGui = player:WaitForChild('PlayerGui'),",
        " Workspace = workspace, ReplicatedStorage = ReplicatedStorage, Players = Players }",
        "local gui = Instance.new('ScreenGui')",
        "gui.Name = 'LycolesObserverV100'",
        "gui.ResetOnSpawn = false",
        "gui.Parent = roots.PlayerGui",
        "local frame = Instance.new('ScrollingFrame')",
        "frame.Size = UDim2.fromOffset(390,320)",
        "frame.Position = UDim2.fromScale(0.05,0.2)",
        "frame.CanvasSize = UDim2.fromOffset(0,0)",
        "frame.Parent = gui",
        "local layout = Instance.new('UIListLayout')",
        "layout.Parent = frame",
        "local function label(text)",
        " local t = Instance.new('TextLabel')",
        " t.Size = UDim2.new(1,-12,0,36)",
        " t.TextScaled = true",
        " t.Text = text",
        " t.Parent = frame",
        " return t",
        "end",
        "local close = Instance.new('TextButton')",
        "close.Size = UDim2.new(1,-12,0,36)",
        "close.Text = 'Close'",
        "close.Parent = frame",
        "close.Activated:Connect(function() gui:Destroy() end)",
        "local function lookup(path)",
        " local node = roots[path[1]]",
        " if not node then return nil end",
        " for i = 2,#path do",
        "  node = node:FindFirstChild(path[i])",
        "  if not node then return nil end",
        " end",
        " return node",
        "end",
        "local observations = {",
    ]
    for item in report["observations"]:
        path="{"+",".join(lua(p) for p in item["path"])+"}"
        lines.append(" { id = "+lua(item["id"])+", path = "+path+
                     ", property = "+lua(item["property"])+
                     ", label = "+lua(item.get("label",item["id"]))+" },")
    lines += [
        "}",
        "local active = true",
        "gui.Destroying:Connect(function() active = false end)",
        "local rows = {}",
        "for _, item in ipairs(observations) do rows[item.id] = label(item.label .. ': waiting') end",
        "task.spawn(function()",
        " while active and gui.Parent do",
        "  for _, item in ipairs(observations) do",
        "   local node = lookup(item.path)",
        "   local text = 'not found'",
        "   if node then",
        "    local ok, value = pcall(function() return node[item.property] end)",
        "    text = ok and tostring(value) or 'unavailable'",
        "   end",
        "   local row = rows[item.id]",
        "   if row then row.Text = item.label .. ': ' .. text end",
        "  end",
        "  frame.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y + 12)",
        "  task.wait(1)",
        " end",
        "end)",
    ]
    return "\n".join(lines)+"\n"

def generate(report,out):
    validate(report)
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    data=compile_gui(report).encode("utf-8")
    spec=(json.dumps(report,sort_keys=True,indent=2,ensure_ascii=False)+"\n").encode("utf-8")
    files={"LycolesObserverV100.client.lua":data,"observations-v100.json":spec}
    hashes={}
    for name,content in files.items():
        (out/name).write_bytes(content)
        hashes[name]=hashlib.sha256(content).hexdigest()
    manifest={"schemaVersion":"100.manifest","placeId":report["placeId"],
              "files":hashes,"readOnly":True,"verifiedInGame":False}
    (out/"manifest-v100.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    return manifest

def audit(out):
    root=Path(out)
    issues=[]
    try:
        manifest=json.loads((root/"manifest-v100.json").read_text(encoding="utf-8"))
        if manifest.get("schemaVersion")!="100.manifest" or manifest.get("readOnly") is not True or manifest.get("verifiedInGame") is not False:
            issues.append("invalid_manifest")
        expected={"LycolesObserverV100.client.lua","observations-v100.json"}
        hashes=manifest.get("files")
        if not isinstance(hashes,dict) or set(hashes)!=expected:
            issues.append("invalid_file_set")
        else:
            for name in expected:
                path=root/name
                if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[name]:
                    issues.append("hash_mismatch:"+name)
            if not issues:
                report=json.loads((root/"observations-v100.json").read_text(encoding="utf-8"))
                if (root/"LycolesObserverV100.client.lua").read_text(encoding="utf-8")!=compile_gui(report):
                    issues.append("not_reproducible")
                if report["placeId"]!=manifest["placeId"]:
                    issues.append("place_mismatch")
    except (OSError,ValueError,KeyError,TypeError) as exc:
        issues.append("audit_error:"+type(exc).__name__)
    return {"schemaVersion":"100.audit","ok":not issues,"issues":sorted(issues),"verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--report",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/release-v100"))
    p.add_argument("--audit-only",action="store_true")
    a=p.parse_args()
    if not a.audit_only:
        if not a.report:p.error("--report required unless --audit-only")
        report=json.loads(a.report.read_text(encoding="utf-8-sig"))
        print(json.dumps(generate(report,a.output)))
    result=audit(a.output)
    print(json.dumps(result))
    if not result["ok"]:raise SystemExit(1)
if __name__=="__main__":main()
