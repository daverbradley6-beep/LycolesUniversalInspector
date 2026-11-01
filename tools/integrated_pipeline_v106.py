#!/usr/bin/env python3
"""Integrated, reproducible inspection-to-functional-client-GUI pipeline.

Supported actions are explicitly scoped to reading client-visible state.
No gameplay authority or third-party executor compatibility is implied.
"""
import argparse
import hashlib
import json
from pathlib import Path

from release_pipeline_v104 import build, canonical
from feature_planner_v106 import plan
from luau_contract_v106 import validate_source
from feature_quality_v106 import assess

SCRIPT = "LycolesFunctionalObserver.client.lua"
PLAN = "feature-plan.json"
MANIFEST = "manifest.json"
REPORT = "inspection-report.json"
QUALITY = "quality-report.json"

def emit_luau(feature_plan):
    place = feature_plan["placeId"]
    if type(place) is not int or place <= 0:
        raise ValueError("invalid place ID")
    entries = []
    for feature in feature_plan["features"]:
        if feature["kind"] != "read_property" or feature["status"] != "implemented_not_runtime_verified":
            raise ValueError("unsupported feature")
        path = feature["path"]
        if not isinstance(path, list) or len(path) < 2 or len(path) > 12 or path[0] not in {'Workspace', 'PlayerGui', 'ReplicatedStorage', 'Players'} or any(not isinstance(p, str) or not p or len(p) > 80 for p in path):
            raise ValueError("invalid path")
        if feature['property'] not in {'Text', 'Value', 'Visible', 'Enabled', 'Name'}:
            raise ValueError('unsupported property')
        entries.append("  {id=%s,label=%s,path=%s,property=%s}," % (
            json.dumps(feature["id"]), json.dumps(feature["label"]),
            "{" + ",".join(json.dumps(p) for p in path) + "}",
            json.dumps(feature["property"])))
    header = [
        "-- Lycoles integrated functional client observer",
        "local Players = game:GetService('Players')",
        "local player = Players.LocalPlayer",
        "if not player or game.PlaceId ~= " + str(place) + " then return end",
        "local playerGui = player:WaitForChild('PlayerGui')",
        "local previous = playerGui:FindFirstChild('LycolesFunctionalObserver')",
        "if previous then previous:Destroy() end",
        "local gui = Instance.new('ScreenGui')",
        "gui.Name = 'LycolesFunctionalObserver'",
        "gui.ResetOnSpawn = false",
        "gui.Parent = playerGui",
        "local panel = Instance.new('ScrollingFrame')",
        "panel.Size = UDim2.fromOffset(440,350)",
        "panel.Position = UDim2.fromScale(0.04,0.16)",
        "panel.CanvasSize = UDim2.fromOffset(0,0)",
        "panel.Parent = gui",
        "local layout = Instance.new('UIListLayout')",
        "layout.Padding = UDim.new(0,4)",
        "layout.Parent = panel",
        "local function button(title,callback)",
        " local b = Instance.new('TextButton')",
        " b.Size = UDim2.new(1,-12,0,34)",
        " b.Text = title",
        " b.Parent = panel",
        " b.Activated:Connect(callback)",
        " return b",
        "end",
        "local roots = {Workspace=workspace,PlayerGui=playerGui,ReplicatedStorage=game:GetService('ReplicatedStorage'),Players=Players}",
        "local features = {",
        *entries,
        "}",
        "local status = Instance.new('TextButton')",
        "status.Size = UDim2.new(1,-12,0,34)",
        "status.Text = 'Refresh all observations'",
        "status.Parent = panel",
        "local search = Instance.new('TextBox')",
        "search.Name = 'Filter'",
        "search.PlaceholderText = 'Filter observations by name'",
        "search.Text = ''",
        "search.Size = UDim2.new(1,-12,0,34)",
        "search.Parent = panel",
        "local rows = {}",
        "local function readFeature(feature)",
        " local node = roots[feature.path[1]]",
        " for i=2,#feature.path do",
        "  if not node then return 'missing object' end",
        "  node = node:FindFirstChild(feature.path[i])",
        " end",
        " if not node then return 'missing object' end",
        " local ok,result = pcall(function() return node[feature.property] end)",
        " return ok and tostring(result) or 'property unavailable'",
        "end",
        "local function refresh(feature,row)",
        " row.Text = feature.label .. ': ' .. readFeature(feature)",
        "end",
        "for _,feature in ipairs(features) do",
        " local row",
        " row = button(feature.label .. ': not read',function() refresh(feature,row) end)",
        " rows[#rows+1] = row",
        "end",
        "local function applyFilter()",
        " local needle = string.lower(search.Text)",
        " for i,feature in ipairs(features) do",
        "  rows[i].Visible = needle == '' or string.find(string.lower(feature.label),needle,1,true) ~= nil",
        " end",
        "end",
        "search:GetPropertyChangedSignal('Text'):Connect(applyFilter)",
        "local function refreshAll()",
        " for i,feature in ipairs(features) do refresh(feature,rows[i]) end",
        " status.Text = 'Refresh all (' .. tostring(#features) .. ' observations)'",
        " panel.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+12)",
        "end",
        "status.Activated:Connect(refreshAll)",
        "local autoRefresh = false",
        "local autoButton",
        "autoButton = button('Auto refresh: OFF',function()",
        " autoRefresh = not autoRefresh",
        " autoButton.Text = autoRefresh and 'Auto refresh: ON' or 'Auto refresh: OFF'",
        "end)",
        "button('Unload',function() gui:Destroy() end)",
        "refreshAll()",
        "task.spawn(function()",
        " while gui.Parent do",
        "  if autoRefresh then refreshAll() end",
        "  task.wait(2)",
        " end",
        "end)",
        "layout:GetPropertyChangedSignal('AbsoluteContentSize'):Connect(function()",
        " panel.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+12)",
        "end)",
    ]
    return "\n".join(header) + "\n"

def generate(source, place_id, output):
    report = build(source, place_id)
    feature_plan = plan(report)
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    files = {
        REPORT: canonical(report),
        PLAN: canonical(feature_plan),
        QUALITY: canonical(assess(report, feature_plan)),
        SCRIPT: emit_luau(feature_plan).encode("utf-8"),
    }
    for name, payload in files.items():
        path = root / name
        if path.is_symlink():
            raise ValueError("symlink output forbidden")
        path.write_bytes(payload)
    manifest = {
        "schemaVersion": "106.integrated-manifest",
        "placeId": place_id,
        "readOnly": True,
        "runtimeVerified": False,
        "gameplayVerified": False,
        "functionalControlsGenerated": len(feature_plan["features"]) + 3,
        "files": {name: hashlib.sha256(payload).hexdigest() for name, payload in sorted(files.items())},
    }
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError("symlink output forbidden")
    manifest_path.write_bytes(canonical(manifest))
    return verify(root)

def verify(output):
    root = Path(output)
    try:
        names = (REPORT, PLAN, QUALITY, SCRIPT)
        paths = [root / name for name in (*names, MANIFEST)]
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise ValueError("missing or symlinked file")
        manifest = json.loads((root / MANIFEST).read_bytes())
        report = json.loads((root / REPORT).read_bytes())
        feature_plan = json.loads((root / PLAN).read_bytes())
        quality = json.loads((root / QUALITY).read_bytes())
        if manifest.get("schemaVersion") != "106.integrated-manifest" or set(manifest.get("files", {})) != set(names):
            raise ValueError("invalid manifest")
        if manifest.get("readOnly") is not True or manifest.get("runtimeVerified") is not False or manifest.get("gameplayVerified") is not False:
            raise ValueError("invalid verification claim")
        if manifest.get("placeId") != report.get("placeId"):
            raise ValueError("place mismatch")
        if feature_plan != plan(report) or quality != assess(report, feature_plan):
            raise ValueError("feature plan mismatch")
        if manifest.get("functionalControlsGenerated") != len(feature_plan["features"]) + 3:
            raise ValueError("control count mismatch")
        expected = {REPORT: canonical(report), PLAN: canonical(feature_plan), QUALITY: canonical(quality), SCRIPT: emit_luau(feature_plan).encode("utf-8")}
        contract = validate_source(expected[SCRIPT].decode('utf-8'), len(feature_plan['features']))
        if not contract['ok']:
            raise ValueError('Luau contract: ' + ','.join(contract['issues']))
        for name, data in expected.items():
            if (root / name).read_bytes() != data or manifest["files"][name] != hashlib.sha256(data).hexdigest():
                raise ValueError("artifact mismatch: " + name)
        return {"ok": True, "features": len(feature_plan["features"]), "runtimeVerified": False}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return {"ok": False, "error": str(exc), "runtimeVerified": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspection", type=Path)
    parser.add_argument("--place-id", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        result = verify(args.output)
    else:
        if args.inspection is None or args.place_id is None:
            parser.error("--inspection and --place-id are required")
        result = generate(json.loads(args.inspection.read_text(encoding="utf-8-sig")), args.place_id, args.output)
    print(json.dumps(result, sort_keys=True))
    if not result["ok"]:
        raise SystemExit(1)

if __name__ == "__main__":
    main()
