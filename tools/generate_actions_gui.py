#!/usr/bin/env python3
"""Build a standalone working GUI for explicitly reviewed read-only client actions."""
import json
import importlib.util
import pathlib

ROOT=pathlib.Path(__file__).resolve().parent
def actions_module():
    spec=importlib.util.spec_from_file_location("lycoles_actions",ROOT/"generate_client_actions.py")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def render(document):
    module=actions_module()
    source=module.render(document)
    if not document["contracts"]:
        raise ValueError("No reviewed actions to display")
    # Reuse the exact reviewed function implementations, not placeholders.
    source=source[:source.rfind("return {")]
    names=sorted({c["action"] for c in document["contracts"]})
    lines=[source,
'''if type(_G.LycolesActionsClose) == "function" then pcall(_G.LycolesActionsClose) end
local player = Players.LocalPlayer
assert(player, "LocalPlayer unavailable")
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesReviewedActions"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")
local frame = Instance.new("Frame")
frame.Size = UDim2.fromOffset(480, 370)
frame.Position = UDim2.new(0.5, -240, 0.5, -185)
frame.BackgroundColor3 = Color3.fromRGB(25, 30, 39)
frame.Parent = gui
local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, -50, 0, 36)
title.Position = UDim2.fromOffset(12, 8)
title.BackgroundTransparency = 1
title.TextColor3 = Color3.new(1, 1, 1)
title.TextXAlignment = Enum.TextXAlignment.Left
title.Text = "Lycoles | Reviewed client actions"
title.Parent = frame
local output = Instance.new("TextLabel")
output.Position = UDim2.fromOffset(12, 54)
output.Size = UDim2.new(1, -24, 0, 218)
output.BackgroundColor3 = Color3.fromRGB(34, 39, 48)
output.TextColor3 = Color3.new(1, 1, 1)
output.TextXAlignment = Enum.TextXAlignment.Left
output.TextYAlignment = Enum.TextYAlignment.Top
output.TextWrapped = true
output.Text = "Choose a reviewed read-only action."
output.Parent = frame
local bar = Instance.new("ScrollingFrame")
bar.Position = UDim2.fromOffset(12, 284)
bar.Size = UDim2.new(1, -24, 0, 70)
bar.ScrollBarThickness = 5
bar.BackgroundTransparency = 1
bar.Parent = frame
local layout = Instance.new("UIListLayout")
layout.FillDirection = Enum.FillDirection.Horizontal
layout.Padding = UDim.new(0, 6)
layout.Parent = bar
local connections = {}
local alive = true
local function display(name, result, err)
    if not alive then return end
    if err then output.Text = name .. ": " .. tostring(err); return end
    local lines = {}
    if type(result) == "table" then
        for key, value in pairs(result) do
            table.insert(lines, tostring(key) .. ": " .. tostring(value))
            if #lines >= 30 then break end
        end
        table.sort(lines)
    else
        lines[1] = tostring(result)
    end
    output.Text = name .. "\\n" .. (#lines > 0 and table.concat(lines, "\\n") or "No entries found.")
end
local actions = {
''']
    for name in names:lines.append("    ["+json.dumps(name)+"] = "+name+",")
    lines.append('''}
local ACTION_NAMES = ACTION_LIST
for _, name in ipairs(ACTION_NAMES) do
    local button = Instance.new("TextButton")
    button.Size = UDim2.fromOffset(145, 45)
    button.TextSize = 12
    button.TextWrapped = true
    button.Text = name
    button.BackgroundColor3 = Color3.fromRGB(50, 90, 122)
    button.TextColor3 = Color3.new(1, 1, 1)
    button.Parent = bar
    table.insert(connections, button.MouseButton1Click:Connect(function()
        local ok, result, err = pcall(actions[name])
        if ok then display(name, result, err) else display(name, nil, result) end
    end))
end
bar.CanvasSize = UDim2.fromOffset(#ACTION_NAMES * 151, 0)
local close = Instance.new("TextButton")
close.Text = "X"
close.Size = UDim2.fromOffset(34, 28)
close.Position = UDim2.new(1, -40, 0, 8)
close.Parent = frame
_G.LycolesActionsClose = function()
    if not alive then return end
    alive = false
    for _, connection in ipairs(connections) do connection:Disconnect() end
    gui:Destroy()
    _G.LycolesActionsClose = nil
end
table.insert(connections, close.MouseButton1Click:Connect(_G.LycolesActionsClose))
'''.replace("ACTION_LIST","{"+",".join(json.dumps(n) for n in names)+"}"))
    return "\n".join(lines)+"\n"
