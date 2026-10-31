#!/usr/bin/env python3
"""Static validation for generated reviewed-actions GUI wiring."""
import re

def validate(source, actions):
    if not isinstance(source,str) or not isinstance(actions,list):
        raise ValueError("Invalid generated GUI")
    required=("local ACTION_NAMES = {","for _, name in ipairs(ACTION_NAMES) do",
              "MouseButton1Click:Connect","pcall(actions[name])",
              "LycolesActionsClose","gui:Destroy()",
              "HttpService:JSONEncode","Export audit JSON","record(name,")
    missing=[token for token in required if token not in source]
    if missing:raise ValueError("Missing GUI wiring: "+", ".join(missing))
    if "ACTION_LIST" in source or "ACTION_NAMES = ACTION_NAMES" in source:
        raise ValueError("Unresolved action list")
    if len(set(actions))!=len(actions):raise ValueError("Duplicate actions")
    for action in actions:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,79}",action):
            raise ValueError("Invalid action name")
        if ('["'+action+'"] = '+action) not in source:
            raise ValueError("Action missing from dispatch table: "+action)
    banned=("FireServer(","InvokeServer(","hookmetamethod(","getrawmetatable(")
    if any(token.lower() in source.lower() for token in banned):
        raise ValueError("Unexpected server or hook operation")
    return {"guiWiringValidated":True,"actionCount":len(actions),
            "runtimeVerified":False,"note":"Static structural checks only"}
