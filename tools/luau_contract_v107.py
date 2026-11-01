"""Static safety and identity-resolution checks for generated v107 Luau."""
import re

REQUIRED = (
    "game.PlaceId",
    "Activated:Connect(refreshAll)",
    "local function readFeature(feature)",
    "pathResolution=",
    "pathIdentity=",
    "if feature.pathResolution == 'full_identity' then",
    "for i=2,#feature.pathIdentity do",
    "child.Name == step.name and child.ClassName == step.className",
    "if count == step.ordinal then chosen = child",
    "feature.pathResolution == 'legacy_terminal_identity'",
    "local function legacyChild(parent,name,className)",
    "if count ~= 1 then return nil end",
    "node = legacyChild(node,feature.path[i],nil)",
    "node = legacyChild(node,feature.path[#feature.path],feature.className)",
    "pcall(function() return node[feature.property] end)",
    "if not ok or result == nil then return 'property unavailable' end",
    "search:GetPropertyChangedSignal('Text'):Connect(applyFilter)",
    "autoButton = button('Auto refresh: OFF'",
    "while gui.Parent do",
    "gui:Destroy()",
)
FORBIDDEN = (
    "loadstring(", "HttpGet(", "FireServer(", "InvokeServer(",
    "getrawmetatable(", "hookmetamethod(", "setreadonly(",
    "getgenv(", "getgc(", "debug.getupvalue(",
)


def validate_source(script: str, expected_features: int) -> dict:
    if not isinstance(script, str) or type(expected_features) is not int or expected_features < 0:
        raise ValueError("invalid source or feature count")
    issues = []
    for fragment in REQUIRED:
        if fragment not in script:
            issues.append("missing:" + fragment)
    for fragment in FORBIDDEN:
        if re.search(re.escape(fragment), script, re.IGNORECASE):
            issues.append("forbidden:" + fragment)
    actual = len(re.findall(r"^  \{id=", script, re.MULTILINE))
    if actual != expected_features:
        issues.append("feature_count_mismatch")
    if script.count("function() refresh(feature,row) end") != 1:
        issues.append("missing_per_feature_callback_template")
    return {
        "ok": not issues,
        "issues": sorted(issues),
        "features": actual,
        "runtimeVerified": False,
    }
