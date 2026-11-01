#!/usr/bin/env python3
"""v92: verified artifact builder for observation-driven Roblox development.

Generates a non-executable Luau diagnostic dashboard and an explicit action
implementation backlog. Never invokes remotes, sends inputs, or claims a bypass.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from temporal_attribution_v91 import release
from evidence_release_v90 import read_events, canonical

def luau_quote(value):
    # Encode as ASCII-only JSON string; valid Luau string syntax for these values.
    return json.dumps(value,ensure_ascii=True)

def safe_identifier(value):
    return re.sub(r"[^A-Za-z0-9_]+","_",value)[:64]

def build_dashboard(report):
    if type(report.get("placeId")) is not int or report["placeId"]<=0:
        raise ValueError("invalid report place ID")
    candidates=report.get("candidates")
    if not isinstance(candidates,list):
        raise ValueError("invalid candidates")
    lines=[
        "-- Lycoles v92: read-only diagnostic dashboard",
        "-- Does not perform gameplay actions or remote calls.",
        "local Players = game:GetService('Players')",
        "if game.PlaceId ~= "+str(report["placeId"])+" then warn('Lycoles v92: wrong place') return end",
        "local player = Players.LocalPlayer",
        "if not player then return end",
        "local pg = player:WaitForChild('PlayerGui')",
        "local previous = pg:FindFirstChild('LycolesV92Diagnostics')",
        "if previous then previous:Destroy() end",
        "local screen = Instance.new('ScreenGui')",
        "screen.Name = 'LycolesV92Diagnostics'",
        "screen.ResetOnSpawn = false",
        "screen.Parent = pg",
        "local frame = Instance.new('Frame')",
        "frame.Name = 'Panel'",
        "frame.Size = UDim2.fromOffset(520,320)",
        "frame.Position = UDim2.fromScale(0.1,0.12)",
        "frame.BackgroundColor3 = Color3.fromRGB(24,31,45)",
        "frame.Parent = screen",
        "local heading = Instance.new('TextLabel')",
        "heading.Size = UDim2.new(1,-16,0,40)",
        "heading.Position = UDim2.fromOffset(8,4)",
        "heading.BackgroundTransparency = 1",
        "heading.TextColor3 = Color3.new(1,1,1)",
        "heading.TextXAlignment = Enum.TextXAlignment.Left",
        "heading.Text = 'Lycoles v92 | evidence review (not executable)'",
        "heading.Parent = frame",
        "local scrolling = Instance.new('ScrollingFrame')",
        "scrolling.Size = UDim2.new(1,-16,1,-92)",
        "scrolling.Position = UDim2.fromOffset(8,44)",
        "scrolling.CanvasSize = UDim2.fromOffset(0,0)",
        "scrolling.ScrollBarThickness = 7",
        "scrolling.Parent = frame",
        "local layout = Instance.new('UIListLayout')",
        "layout.Padding = UDim.new(0,4)",
        "layout.Parent = scrolling",
        "local function addLine(message)",
        " local label = Instance.new('TextLabel')",
        " label.Size = UDim2.new(1,-8,0,48)",
        " label.TextWrapped = true",
        " label.TextXAlignment = Enum.TextXAlignment.Left",
        " label.TextColor3 = Color3.new(1,1,1)",
        " label.BackgroundColor3 = Color3.fromRGB(39,49,65)",
        " label.Text = message",
        " label.Parent = scrolling",
        "end",
    ]
    for c in candidates[:200]:
        if not isinstance(c,dict):
            raise ValueError("malformed candidate")
        outcome=c.get("outcome") or {}
        message=(str(c.get("status","unknown"))+" | "+
                 str(c.get("input","unknown"))+" | "+
                 str(outcome.get("stat","unknown"))+" "+
                 str(outcome.get("operator","unknown"))+
                 " | evidence only; no execution adapter")
        if len(message)>1200:
            message=message[:1200]
        lines.append("addLine("+luau_quote(message)+")")
    lines += [
        "scrolling.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y + 8)",
        "local close = Instance.new('TextButton')",
        "close.Name = 'Close'",
        "close.Size = UDim2.fromOffset(100,32)",
        "close.Position = UDim2.new(1,-108,1,-38)",
        "close.Text = 'Close'",
        "close.Parent = frame",
        "close.Activated:Connect(function() screen:Destroy() end)",
    ]
    return "\n".join(lines)+"\n"

def build_backlog(report):
    items=[]
    for c in report["candidates"]:
        if c["status"]!="review_candidate":
            continue
        items.append({
            "candidateId":c["id"],
            "observedInput":c["input"],
            "expectedOutcome":c["outcome"],
            "requirements":[
                "Identify a supported and authorized game-specific API or Studio implementation",
                "Implement the action in the game owner's development environment",
                "Add precondition and postcondition checks",
                "Test the action in an authorized test place",
                "Record independent results and obtain explicit review approval"
            ],
            "implementationStatus":"not_implemented",
            "executionEnabled":False,
            "verifiedInGame":False
        })
    return {"schemaVersion":"92.backlog","placeId":report["placeId"],
            "items":items,"automaticallyGeneratedExecutableActions":0}

def generate(events,place_id,output):
    report=release(events,place_id)
    backlog=build_backlog(report)
    script=build_dashboard(report).encode("utf-8")
    artifacts={
        "review-v92.json":canonical(report),
        "implementation-backlog-v92.json":canonical(backlog),
        "diagnostics-v92.luau":script
    }
    output=Path(output)
    output.mkdir(parents=True,exist_ok=True)
    hashes={}
    for filename,payload in artifacts.items():
        (output/filename).write_bytes(payload)
        hashes[filename]=hashlib.sha256(payload).hexdigest()
        if hashlib.sha256((output/filename).read_bytes()).hexdigest()!=hashes[filename]:
            raise RuntimeError("integrity mismatch: "+filename)
    manifest={"schemaVersion":"92.manifest","placeId":place_id,
              "files":hashes,"verifiedInGame":False,
              "automaticallyGeneratedExecutableActions":0}
    (output/"manifest-v92.json").write_bytes(canonical(manifest))
    return {"events":len(events),"candidates":len(report["candidates"]),
            "reviewCandidates":len(backlog["items"]),
            "quarantined":report["temporalAttribution"]["quarantined"],
            "files":list(artifacts),"verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--event-log",type=Path,action="append",required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v92"))
    a=p.parse_args()
    events,sources,warnings=read_events(a.event_log,a.place_id)
    summary=generate(events,a.place_id,a.output)
    summary["warnings"]=warnings
    summary["sourceCount"]=len(sources)
    print(json.dumps(summary,ensure_ascii=False))
if __name__=="__main__":
    main()
