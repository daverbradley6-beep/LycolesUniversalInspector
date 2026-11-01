#!/usr/bin/env python3
"""v63 universal offline release builder.

Creates a read-only, game-specific GUI from v62 evidence and a machine-readable
verification backlog. No remote calls, inferred server permissions, or fake actions.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from evidence_pipeline_v62 import import_console, catalog, MAX_FILE

MAX_ITEMS = 300
SAFE_KINDS = {"observable_value", "gui_control", "standard_tool",
              "proximity_prompt", "click_detector", "remote_observed", "bindable_observed"}
def luau_string(value):
    return json.dumps(str(value), ensure_ascii=True)

def make_release(console, place_id, max_items=MAX_ITEMS):
    if not isinstance(place_id, int) or place_id <= 0:
        raise ValueError("Invalid place ID")
    if not 1 <= max_items <= MAX_ITEMS:
        raise ValueError("Invalid item cap")
    evidence = import_console(console)
    if evidence["placeId"] is not None and evidence["placeId"] != place_id:
        raise ValueError("Place ID mismatch")
    cat = catalog(evidence)
    ranked = sorted((c for c in cat["capabilities"] if c["kind"] in SAFE_KINDS),
                    key=lambda c: (0 if c["kind"] == "observable_value" and c["valueChanged"] else
                                   1 if c["kind"] in ("standard_tool", "proximity_prompt", "gui_control") else 2,
                                   c["path"]))
    selected = ranked[:max_items]
    backlog = []
    for i, item in enumerate(selected, 1):
        backlog.append({"id": f"candidate-{i:04}", "kind": item["kind"],
                        "path": item["path"], "className": item["className"],
                        "observedSamples": item["samplesObserved"],
                        "state": "read_only" if item["kind"] == "observable_value" else "needs_authorized_contract",
                        "actionVerified": False, "serverOutcomeVerified": False,
                        "requiredEvidence": ["explicit authorization", "documented action contract",
                                             "independent outcome verification"]
                            if item["kind"] != "observable_value" else ["read-only value observation"]})
    data = [{"path": c["path"], "kind": c["kind"], "className": c["className"],
             "changed": c["valueChanged"], "value": c["valuesPreview"][-1] if c["valuesPreview"] else ""}
            for c in selected]
    table = "{" + ",".join("{path=" + luau_string(x["path"]) +
        ",kind=" + luau_string(x["kind"]) +
        ",className=" + luau_string(x["className"]) +
        ",changed=" + ("true" if x["changed"] else "false") +
        ",value=" + luau_string(x["value"]) + "}" for x in data) + "}"
    lua = '''-- Lycoles v63: read-only evidence browser. No gameplay mutation or remote invocation.
local Players=game:GetService("Players")
if game.PlaceId~=__PLACE__ then warn("Lycoles v63: place mismatch") return end
local player=Players.LocalPlayer
if not player then return end
local pg=player:WaitForChild("PlayerGui")
local old=pg:FindFirstChild("LycolesV63")
if old then old:Destroy() end
local gui=Instance.new("ScreenGui")
gui.Name="LycolesV63" gui.ResetOnSpawn=false gui.Parent=pg
local panel=Instance.new("Frame")
panel.Size=UDim2.fromOffset(610,470) panel.Position=UDim2.fromScale(.06,.16)
panel.BackgroundColor3=Color3.fromRGB(24,29,39) panel.Parent=gui
local title=Instance.new("TextLabel")
title.Size=UDim2.new(1,-52,0,46) title.Position=UDim2.fromOffset(8,0)
title.TextColor3=Color3.new(1,1,1) title.BackgroundTransparency=1
title.TextXAlignment=Enum.TextXAlignment.Left
title.Text="Lycoles v63 | Evidence browser (actions unverified)" title.Parent=panel
local close=Instance.new("TextButton")
close.Size=UDim2.fromOffset(42,40) close.Position=UDim2.new(1,-44,0,2)
close.Text="X" close.Parent=panel
close.MouseButton1Click:Connect(function() gui:Destroy() end)
local search=Instance.new("TextBox")
search.Size=UDim2.new(1,-16,0,40) search.Position=UDim2.fromOffset(8,48)
search.PlaceholderText="Search evidence paths, classes, types"
search.Text="" search.ClearTextOnFocus=false search.Parent=panel
local scroller=Instance.new("ScrollingFrame")
scroller.Size=UDim2.new(1,-16,1,-100) scroller.Position=UDim2.fromOffset(8,94)
scroller.CanvasSize=UDim2.fromOffset(0,0) scroller.Parent=panel
local layout=Instance.new("UIListLayout") layout.Padding=UDim.new(0,3) layout.Parent=scroller
local items=__ITEMS__
local function render()
 for _,child in ipairs(scroller:GetChildren()) do
  if child:IsA("TextLabel") then child:Destroy() end
 end
 local term=string.lower(search.Text)
 local count=0
 for _,item in ipairs(items) do
  local labelText=item.kind.." | "..item.className.." | "..item.path
  if term=="" or string.find(string.lower(labelText),term,1,true) then
   count+=1
   local row=Instance.new("TextLabel")
   row.Size=UDim2.new(1,-12,0,48) row.BackgroundTransparency=.5
   row.TextColor3=Color3.new(1,1,1) row.TextWrapped=true
   row.TextXAlignment=Enum.TextXAlignment.Left
   row.Text=(item.changed and "[CHANGED] " or "[SEEN] ")..labelText..
      (item.value~="" and (" | "..item.value) or "")
   row.Parent=scroller
  end
 end
 scroller.CanvasSize=UDim2.fromOffset(0,count*51)
end
search:GetPropertyChangedSignal("Text"):Connect(render)
render()
'''
    lua = lua.replace("__PLACE__", str(place_id)).replace("__ITEMS__", table)
    manifest = {"schemaVersion": "63.release", "placeId": place_id,
                "sourceComplete": cat["sourceComplete"], "sourceSampleCount": len(evidence["samples"]),
                "completeSamples": evidence["completeSamples"], "capabilityCount": len(cat["capabilities"]),
                "includedInGui": len(selected), "unverifiedActionCount": sum(
                    x["state"] == "needs_authorized_contract" for x in backlog),
                "automaticallyExecutableActions": 0, "serverOutcomeVerified": False,
                "sourceSha256": hashlib.sha256(console.encode("utf-8")).hexdigest()}
    return {"manifest": manifest, "catalog": cat, "backlog": backlog, "luau": lua}

def build(console, place_id, out, max_items=MAX_ITEMS):
    release = make_release(console, place_id, max_items)
    out.mkdir(parents=True, exist_ok=True)
    for filename, key in (("release-manifest-v63.json", "manifest"),
                          ("capability-catalog-v63.json", "catalog"),
                          ("verification-backlog-v63.json", "backlog")):
        (out / filename).write_text(json.dumps(release[key], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "evidence-browser-v63.luau").write_text(release["luau"], encoding="utf-8")
    return release["manifest"]

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--console", type=Path, required=True)
    p.add_argument("--place-id", type=int, required=True)
    p.add_argument("--output", type=Path, default=Path("build/release-v63"))
    p.add_argument("--max-items", type=int, default=MAX_ITEMS)
    a = p.parse_args()
    if a.console.stat().st_size > MAX_FILE:
        p.error("Console exceeds size limit")
    manifest = build(a.console.read_text(encoding="utf-8-sig", errors="replace"),
                     a.place_id, a.output, a.max_items)
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
