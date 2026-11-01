"""Static contract checks for generated Lycoles client observation Luau.

This is source verification, not execution or gameplay verification.
"""
import re

REQUIRED = (
    "game.PlaceId",
    "Activated:Connect(refreshAll)",
    "local function readFeature(feature)",
    "local function refresh(feature,row)",
    "gui:Destroy()",
    "pcall(function() return node[feature.property] end)",
    "local previous = playerGui:FindFirstChild(",
)
FORBIDDEN = (
    "loadstring(", "HttpGet(", "FireServer(", "InvokeServer(",
    "getrawmetatable(", "hookmetamethod(", "setreadonly(",
    "getgenv(", "getgc(", "debug.getupvalue(",
)

def validate_source(script: str, expected_features: int) -> dict:
    if not isinstance(script, str) or type(expected_features) is not int or expected_features < 0:
        raise ValueError("invalid source or feature count")
    errors = []
    for fragment in REQUIRED:
        if fragment not in script:
            errors.append("missing:" + fragment)
    for fragment in FORBIDDEN:
        if re.search(re.escape(fragment), script, re.IGNORECASE):
            errors.append("forbidden:" + fragment)
    actual = len(re.findall(r"^  \{id=", script, re.MULTILINE))
    if actual != expected_features:
        errors.append("feature_count_mismatch")
    if script.count("Activated:Connect(function() refresh(feature,row) end)") != 1:
        errors.append("missing_per_feature_callback_template")
    return {"ok": not errors, "issues": sorted(errors), "features": actual, "runtimeVerified": False}
