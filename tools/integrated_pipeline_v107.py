#!/usr/bin/env python3
"""Deterministic identity-aware inspection-to-Luau observer pipeline."""
import argparse
import hashlib
import json
import re
from pathlib import Path

from artifact_contract_v107 import validate_source_semantics
from feature_planner_v107 import plan, validate_feature_plan
from feature_quality_v107 import assess
from inspection_diagnostics_v107 import analyze
from luau_contract_v107 import validate_source
from path_identity_v107 import (
    PATH_SCHEMA_VERSION,
    REPORT_SCHEMA_VERSION,
    build,
    migrate_v104_report,
    validate_report,
)
from release_pipeline_v104 import canonical

SCRIPT = "LycolesFunctionalObserver.client.lua"
PLAN = "feature-plan.json"
MANIFEST = "manifest.json"
REPORT = "inspection-report.json"
QUALITY = "quality-report.json"
DIAGNOSTICS = "inspection-diagnostics.json"
ARTIFACTS = (REPORT, PLAN, QUALITY, DIAGNOSTICS, SCRIPT)


def _identity_luau(path_identity):
    if path_identity is None:
        return "nil"
    segments = []
    for segment in path_identity:
        segments.append("{name=%s,className=%s,ordinal=%d}" % (
            json.dumps(segment["name"]),
            json.dumps(segment["className"]),
            segment["ordinal"],
        ))
    return "{" + ",".join(segments) + "}"


def emit_luau(feature_plan):
    validate_feature_plan(feature_plan)
    place_id = feature_plan["placeId"]
    entries = []
    for feature in feature_plan["features"]:
        path = "{" + ",".join(json.dumps(part) for part in feature["path"]) + "}"
        entries.append(
            "  {id=%s,label=%s,path=%s,pathIdentity=%s,pathResolution=%s,className=%s,property=%s}," % (
                json.dumps(feature["id"]),
                json.dumps(feature["label"]),
                path,
                _identity_luau(feature["pathIdentity"]),
                json.dumps(feature["pathResolution"]),
                json.dumps(feature["className"]),
                json.dumps(feature["property"]),
            )
        )
    lines = [
        "-- Lycoles v107 identity-aware read-only client observer",
        "local Players = game:GetService('Players')",
        "local player = Players.LocalPlayer",
        "if not player or game.PlaceId ~= " + str(place_id) + " then return end",
        "local playerGui = player:WaitForChild('PlayerGui')",
        "local previous = playerGui:FindFirstChild('LycolesFunctionalObserverV107')",
        "if previous then previous:Destroy() end",
        "local gui = Instance.new('ScreenGui')",
        "gui.Name = 'LycolesFunctionalObserverV107'",
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
        " local result = Instance.new('TextButton')",
        " result.Size = UDim2.new(1,-12,0,34)",
        " result.Text = title",
        " result.Parent = panel",
        " result.Activated:Connect(callback)",
        " return result",
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
        "local function identityChild(parent,step)",
        " local count = 0",
        " local chosen = nil",
        " for _, child in ipairs(parent:GetChildren()) do",
        "  if child.Name == step.name and child.ClassName == step.className then",
        "   count += 1",
        "   if count == step.ordinal then chosen = child break end",
        "  end",
        " end",
        " return chosen",
        "end",
        "local function legacyChild(parent,name,className)",
        " local count = 0",
        " local chosen = nil",
        " for _, child in ipairs(parent:GetChildren()) do",
        "  if child.Name == name and (className == nil or child.ClassName == className) then",
        "   count += 1",
        "   chosen = child",
        "  end",
        " end",
        " if count ~= 1 then return nil end",
        " return chosen",
        "end",
        "local function readFeature(feature)",
        " local node = nil",
        " if feature.pathResolution == 'full_identity' then",
        "  node = roots[feature.pathIdentity[1].name]",
        "  for i=2,#feature.pathIdentity do",
        "   if not node then return 'missing identity segment' end",
        "   node = identityChild(node,feature.pathIdentity[i])",
        "  end",
        " elseif feature.pathResolution == 'legacy_terminal_identity' then",
        "  node = roots[feature.path[1]]",
        "  for i=2,#feature.path-1 do",
        "   if not node then return 'missing or ambiguous legacy path segment' end",
        "   node = legacyChild(node,feature.path[i],nil)",
        "  end",
        "  if not node then return 'missing or ambiguous legacy path segment' end",
        "  node = legacyChild(node,feature.path[#feature.path],feature.className)",
        " else",
        "  return 'unsupported path resolution'",
        " end",
        " if not node then return 'missing object or identity mismatch' end",
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
    return "\n".join(lines) + "\n"


def _coerce_report(source, place_id):
    if isinstance(source, dict) and source.get("schemaVersion") == REPORT_SCHEMA_VERSION:
        validate_report(source)
        report = source
    elif isinstance(source, dict) and source.get("schemaVersion") == "104.release":
        report = migrate_v104_report(source)
    else:
        report = build(source, place_id)
    if report["placeId"] != place_id:
        raise ValueError("place mismatch")
    validate_report(report)
    return report


def _resolution_counts(feature_plan):
    full = sum(feature["pathResolution"] == "full_identity" for feature in feature_plan["features"])
    legacy = sum(feature["pathResolution"] == "legacy_terminal_identity" for feature in feature_plan["features"])
    return full, legacy


def generate(source, place_id, output):
    if type(place_id) is not int or place_id <= 0:
        raise ValueError("invalid place ID")
    report = _coerce_report(source, place_id)
    feature_plan = plan(report)
    quality = assess(report, feature_plan)
    diagnostics = analyze(report, feature_plan)
    script = emit_luau(feature_plan).encode("utf-8")
    root = Path(output)
    root.mkdir(parents=True, exist_ok=True)
    files = {
        REPORT: canonical(report),
        PLAN: canonical(feature_plan),
        QUALITY: canonical(quality),
        DIAGNOSTICS: canonical(diagnostics),
        SCRIPT: script,
    }
    for name, payload in files.items():
        path = root / name
        if path.is_symlink():
            raise ValueError("symlink output forbidden")
        path.write_bytes(payload)
    full, legacy = _resolution_counts(feature_plan)
    manifest = {
        "schemaVersion": "107.integrated-manifest",
        "pathIdentityVersion": PATH_SCHEMA_VERSION,
        "placeId": place_id,
        "readOnly": True,
        "runtimeVerified": False,
        "gameplayVerified": False,
        "functionalControlsGenerated": len(feature_plan["features"]) + 3,
        "fullIdentityFeatures": full,
        "legacyFeatures": legacy,
        "files": {
            name: hashlib.sha256(payload).hexdigest()
            for name, payload in sorted(files.items())
        },
    }
    manifest_path = root / MANIFEST
    if manifest_path.is_symlink():
        raise ValueError("symlink output forbidden")
    manifest_path.write_bytes(canonical(manifest))
    return verify(root)


def verify(output):
    root = Path(output)
    try:
        expected_names = set((*ARTIFACTS, MANIFEST))
        if root.is_symlink() or not root.is_dir():
            raise ValueError("invalid artifact directory")
        if {entry.name for entry in root.iterdir()} != expected_names:
            raise ValueError("unexpected artifact set")
        paths = [root / name for name in expected_names]
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise ValueError("missing or symlinked file")
        manifest_bytes = (root / MANIFEST).read_bytes()
        manifest = json.loads(manifest_bytes)
        report = json.loads((root / REPORT).read_bytes())
        feature_plan = json.loads((root / PLAN).read_bytes())
        quality = json.loads((root / QUALITY).read_bytes())
        diagnostics = json.loads((root / DIAGNOSTICS).read_bytes())
        validate_report(report)
        validate_feature_plan(feature_plan)
        manifest_fields = {
            "schemaVersion", "pathIdentityVersion", "placeId", "readOnly",
            "runtimeVerified", "gameplayVerified", "functionalControlsGenerated",
            "fullIdentityFeatures", "legacyFeatures", "files",
        }
        files = manifest.get("files")
        if set(manifest) != manifest_fields or manifest.get("schemaVersion") != "107.integrated-manifest":
            raise ValueError("invalid manifest")
        if not isinstance(files, dict) or set(files) != set(ARTIFACTS):
            raise ValueError("invalid manifest files")
        if any(not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None for value in files.values()):
            raise ValueError("invalid manifest hash")
        if manifest_bytes != canonical(manifest):
            raise ValueError("non-canonical manifest")
        if manifest.get("pathIdentityVersion") != PATH_SCHEMA_VERSION:
            raise ValueError("invalid identity claim")
        if manifest.get("readOnly") is not True or manifest.get("runtimeVerified") is not False or manifest.get("gameplayVerified") is not False:
            raise ValueError("invalid verification claim")
        if manifest.get("placeId") != report["placeId"] or feature_plan["placeId"] != report["placeId"]:
            raise ValueError("place mismatch")
        expected_plan = plan(report)
        if feature_plan != expected_plan or quality != assess(report, feature_plan) or diagnostics != analyze(report, feature_plan):
            raise ValueError("derived artifact mismatch")
        full, legacy = _resolution_counts(feature_plan)
        if manifest.get("functionalControlsGenerated") != len(feature_plan["features"]) + 3:
            raise ValueError("control count mismatch")
        if manifest.get("fullIdentityFeatures") != full or manifest.get("legacyFeatures") != legacy:
            raise ValueError("resolution count mismatch")
        expected = {
            REPORT: canonical(report),
            PLAN: canonical(feature_plan),
            QUALITY: canonical(quality),
            DIAGNOSTICS: canonical(diagnostics),
            SCRIPT: emit_luau(feature_plan).encode("utf-8"),
        }
        actual_source = (root / SCRIPT).read_bytes().decode("utf-8")
        contract = validate_source(actual_source, len(feature_plan["features"]))
        if not contract["ok"]:
            raise ValueError("Luau contract: " + ",".join(contract["issues"]))
        semantics = validate_source_semantics(actual_source, feature_plan)
        if not semantics["ok"]:
            raise ValueError("Luau semantics: " + ",".join(semantics["issues"]))
        for name, payload in expected.items():
            if (root / name).read_bytes() != payload:
                raise ValueError("artifact mismatch: " + name)
            if manifest["files"].get(name) != hashlib.sha256(payload).hexdigest():
                raise ValueError("hash mismatch: " + name)
        return {
            "ok": True,
            "features": len(feature_plan["features"]),
            "fullIdentityFeatures": full,
            "legacyFeatures": legacy,
            "runtimeVerified": False,
        }
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
        source = json.loads(args.inspection.read_text(encoding="utf-8-sig"))
        result = generate(source, args.place_id, args.output)
    print(json.dumps(result, sort_keys=True))
    if not result["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
