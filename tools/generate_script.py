#!/usr/bin/env python3
"""Lycoles v9: deterministic, fail-closed Roblox client utility generator.

Usage:
  python3 tools/generate_script.py build/capability-plan.json --output build/generated
Only generates features backed by safe Roblox client APIs; does not synthesize
remote invocations or claim to replay server-controlled gameplay actions.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys
import unicodedata

ALLOWED_FEATURES = ("live_stats", "ui_catalog", "prompt_catalog", "performance")
def validate(plan):
    if not isinstance(plan,dict): raise ValueError("Plan must be an object")
    integrity=plan.get("integrity")
    if not isinstance(integrity,dict) or integrity.get("scanComplete") is not True:
        raise ValueError("A complete validated scan is required")
    place=integrity.get("placeId")
    if type(place) is not int or not 1<=place<=2**53:
        raise ValueError("Invalid place ID")
    if not isinstance(plan.get("features"),list): raise ValueError("Missing feature inventory")
    if len(plan["features"])>5000: raise ValueError("Unreasonably large feature inventory")
    for feature in plan["features"]:
        if not isinstance(feature,dict) or not isinstance(feature.get("feature"),str):
            raise ValueError("Malformed feature")
    request=plan.get("requestedCapability")
    if request is not None and (not isinstance(request,str) or not request
            or len(request.encode("utf-8"))>240 or request!=request.strip()
            or any(unicodedata.category(character)=="Cc" for character in request)):
        raise ValueError("Malformed requested capability")
    return place

def source_provenance_lines(plan):
    provenance=plan.get("sourceProvenance")
    if provenance is None:
        return ["Baseline input: local multipart","Receiver payload digests: unavailable",
                "Receiver retrieval integrity: unavailable",
                "Inspector ACK digest equivalence: not established",
                "Resume checkpoint authentication: unavailable",
                "Response authenticity: unverified",
                "Original local payload equivalence: unverified",
                "Gameplay outcomes: unverified"]
    if not isinstance(provenance,dict):
        raise ValueError("Malformed source provenance")
    mode=provenance.get("inputMode")
    receiver=mode=="receiver-import"
    if mode not in ("local-multipart","receiver-import"):
        raise ValueError("Unsupported source provenance mode")
    false_claims=("resumeCheckpointAuthenticated","receiverResponseAuthenticityVerified",
                  "localPayloadEquivalent","sourceAuthenticityVerified","causalityProven",
                  "serverAuthorityVerified","replayable","gameplayVerified",
                  "actionOutcomesVerified")
    if any(provenance.get(field) is not False for field in false_claims):
        raise ValueError("Source provenance claims unsupported verification")
    digest_verified=provenance.get("receiverStoredPayloadDigestsVerified")
    integrity_verified=provenance.get("receiverIntegrityVerified")
    acknowledgement_equivalent=provenance.get("receiverAcknowledgementDigestEquivalent")
    revalidated=provenance.get("receiverStoredPayloadDigestsRevalidatedThisRun")
    if (type(digest_verified) is not bool or type(integrity_verified) is not bool
            or type(acknowledgement_equivalent) is not bool or type(revalidated) is not bool
            or digest_verified is not receiver or integrity_verified is not receiver
            or (not receiver and (acknowledgement_equivalent or revalidated))):
        raise ValueError("Inconsistent source provenance")
    return [
        "Baseline input: "+("receiver import" if receiver else "local multipart"),
        "Receiver payload digests: "+("verified" if digest_verified else "unavailable"),
        "Receiver retrieval integrity: "+("verified" if integrity_verified else "unavailable"),
        "Inspector ACK digest equivalence: "+(
            "verified" if acknowledgement_equivalent else "not established"),
        "Receiver digests rechecked this run: "+(
            "yes" if revalidated else "no (cached checkpoint used)" if receiver else "not applicable"),
        "Resume checkpoint authentication: unavailable",
        "Response authenticity: unverified",
        "Original local payload equivalence: unverified",
        "Gameplay outcomes: unverified",
    ]


def lua_quote(value):
    return json.dumps(str(value),ensure_ascii=True)

def render(plan):
    place=validate(plan)
    names=sorted({f["feature"] for f in plan["features"]})
    feature_list="\n".join("    "+lua_quote(name)+"," for name in names)
    provenance_list="\n".join(
        "    "+lua_quote(line)+"," for line in source_provenance_lines(plan))
    request=plan.get("requestedCapability")
    request_lines=(["Requested capability: "+request,
                    "Request status: evidence review only; gameplay is unverified"]
                   if request else ["Requested capability: none supplied"])
    request_list="\n".join("    "+lua_quote(line)+"," for line in request_lines)
    return """-- Generated by Lycoles v9 from validated client-visible scan evidence.
-- Client diagnostics only. No remote invocation, anticheat bypass or fabricated gameplay.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local player = Players.LocalPlayer
assert(game.PlaceId == PLACE_ID, "Wrong Roblox place for generated utility")
if type(_G.LycolesGeneratedClose) == "function" then pcall(_G.LycolesGeneratedClose) end
local connections, alive = {}, true
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesGeneratedUtility"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")
local frame = Instance.new("Frame")
frame.Name = "Panel"
frame.Size = UDim2.fromOffset(440, 420)
frame.Position = UDim2.new(0.5,-220,0.5,-210)
frame.BackgroundColor3 = Color3.fromRGB(26,29,35)
frame.Parent = gui
local corner=Instance.new("UICorner",frame)
corner.CornerRadius=UDim.new(0,10)
local stroke=Instance.new("UIStroke",frame)
stroke.Color=Color3.fromRGB(98,190,240)
local heading=Instance.new("TextLabel",frame)
heading.Size=UDim2.new(1,-60,0,40)
heading.Position=UDim2.fromOffset(12,5)
heading.BackgroundTransparency=1
heading.Text="Lycoles | Client Utility"
heading.TextXAlignment=Enum.TextXAlignment.Left
heading.TextColor3=Color3.new(1,1,1)
heading.TextSize=18
local close=Instance.new("TextButton",frame)
close.Size=UDim2.fromOffset(34,30)
close.Position=UDim2.new(1,-40,0,8)
close.Text="X"
close.TextColor3=Color3.new(1,1,1)
close.BackgroundColor3=Color3.fromRGB(75,79,87)
local output=Instance.new("TextLabel",frame)
output.Position=UDim2.fromOffset(12,54)
output.Size=UDim2.new(1,-24,1,-108)
output.BackgroundColor3=Color3.fromRGB(34,38,45)
output.TextColor3=Color3.fromRGB(226,234,240)
output.TextXAlignment=Enum.TextXAlignment.Left
output.TextYAlignment=Enum.TextYAlignment.Top
output.TextWrapped=true
output.TextSize=13
output.Text="Select a client diagnostic."
local tabs=Instance.new("Frame",frame)
tabs.BackgroundTransparency=1
tabs.Position=UDim2.new(0,12,1,-46)
tabs.Size=UDim2.new(1,-24,0,38)
local layout=Instance.new("UIListLayout",tabs)
layout.FillDirection=Enum.FillDirection.Horizontal
layout.Padding=UDim.new(0,4)
local function show(title,lines)
    if not alive then return end
    output.Text=title.."\\n\\n"..table.concat(lines,"\\n")
end
local function button(name,callback)
    local b=Instance.new("TextButton",tabs)
    b.Size=UDim2.new(0.25,-4,1,0)
    b.Text=name
    b.TextSize=12
    b.BackgroundColor3=Color3.fromRGB(48,78,103)
    b.TextColor3=Color3.new(1,1,1)
    table.insert(connections,b.MouseButton1Click:Connect(function()
        local ok,err=pcall(callback)
        if not ok then show(name.." failed",{tostring(err)}) end
    end))
end
button("Stats",function()
    local lines={}
    local stats=player:FindFirstChild("leaderstats")
    if stats then
        for _,v in ipairs(stats:GetChildren()) do
            if v:IsA("ValueBase") and (type(v.Value)=="number" or type(v.Value)=="boolean") then
                lines[#lines+1]=v.Name..": "..tostring(v.Value)
            end
        end
    end
    if #lines==0 then lines={"No replicated numeric stats found."} end
    show("Replicated stats",lines)
end)
button("Menus",function()
    local lines={}
    for _,v in ipairs(player.PlayerGui:GetDescendants()) do
        if v:IsA("ScreenGui") then lines[#lines+1]=v.Name..": "..tostring(v.Enabled) end
        if #lines>=22 then break end
    end
    if #lines==0 then lines={"No menus found."} end
    show("Available UI (read-only)",lines)
end)
button("Prompts",function()
    local lines={}
    for _,v in ipairs(workspace:GetDescendants()) do
        if v:IsA("ProximityPrompt") then
            lines[#lines+1]=v.Name.." ["..tostring(v.Enabled).."]"
        end
        if #lines>=22 then break end
    end
    if #lines==0 then lines={"No proximity prompts found."} end
    show("World prompts (read-only)",lines)
end)
button("Features",function()
    local candidates=FEATURE_NAMES
    local provenance=SOURCE_PROVENANCE_LINES
    local request=REQUEST_STATUS_LINES
    local lines={"Discovered: "..tostring(#candidates),"These are candidates, not implemented gameplay actions.",""}
    for _,line in ipairs(request) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for _,line in ipairs(provenance) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for i=1,math.min(12,#candidates) do lines[#lines+1]=candidates[i] end
    show("Inspection inventory and source status",lines)
end)
local dragging,dragInput,dragStart,startPos=false,nil,nil,nil
table.insert(connections,heading.InputBegan:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 then
        dragging=true;dragStart=input.Position;startPos=frame.Position
    end
end))
table.insert(connections,heading.InputEnded:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 then dragging=false end
end))
table.insert(connections,game:GetService("UserInputService").InputChanged:Connect(function(input)
    if dragging and input.UserInputType==Enum.UserInputType.MouseMovement then
        local d=input.Position-dragStart
        frame.Position=UDim2.new(startPos.X.Scale,startPos.X.Offset+d.X,startPos.Y.Scale,startPos.Y.Offset+d.Y)
    end
end))
_G.LycolesGeneratedClose=function()
    if not alive then return end
    alive=false
    for _,c in ipairs(connections) do pcall(function() c:Disconnect() end) end
    gui:Destroy()
    _G.LycolesGeneratedClose=nil
end
table.insert(connections,close.MouseButton1Click:Connect(_G.LycolesGeneratedClose))
show("Ready",{"Validated scan inventory loaded.","Client diagnostic features only.","Gameplay automation has not been verified."})
""".replace("PLACE_ID",str(place)).replace(
        "FEATURE_NAMES", "{\n"+feature_list+"\n}").replace(
        "SOURCE_PROVENANCE_LINES", "{\n"+provenance_list+"\n}").replace(
        "REQUEST_STATUS_LINES", "{\n"+request_list+"\n}")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("--output",default="build/generated")
    args=parser.parse_args()
    try:
        raw=pathlib.Path(args.plan).read_bytes()
        if len(raw)>5_000_000: raise ValueError("Plan too large")
        plan=json.loads(raw)
        lua=render(plan)
        out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
        script=out/"LycolesGeneratedUtility.lua"
        script.write_text(lua,encoding="utf-8")
        manifest={"schemaVersion":"9.0","placeId":plan["integrity"]["placeId"],
          "sourcePlanSHA256":hashlib.sha256(raw).hexdigest(),
          "generatedLuaSHA256":hashlib.sha256(lua.encode()).hexdigest(),
          "implementedFeatures":list(ALLOWED_FEATURES),
          "gameplayFeaturesImplemented":[],"liveTested":False,
          "sourceFeatureCandidates":len(plan["features"]),
          "releaseStatus":"CLIENT_DIAGNOSTIC_ONLY_UNTESTED"}
        (out/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print("Generated:",script)
        return 0
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print("GENERATION BLOCKED:",exc,file=sys.stderr);return 2
if __name__=="__main__":sys.exit(main())
