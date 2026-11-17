-- Lycoles Bubble Gum Simulator INFINITY utility (real inspection derived)
-- Scan source: AC79D385-BCB0-4928-85D5-6C3D960C44AE
-- Client-side only: no server-authority claims or fabricated remotes.

assert(game.PlaceId == 85896571713843, "Wrong place for Bubble Gum utility")

if type(_G.LycolesBubbleClose) == "function" then
    pcall(_G.LycolesBubbleClose)
end

local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")
local RunService = game:GetService("RunService")

local player = Players.LocalPlayer
assert(player, "LocalPlayer unavailable")

local TARGETS = {
    inventoryOpen = "LocalPlayer.PlayerGui.ScreenGui.HUD.Right.Inventory.Button",
    petsTab = "LocalPlayer.PlayerGui.ScreenGui.Inventory.Frame.Sidebar.Buttons.Pets.Button",
    itemsTab = "LocalPlayer.PlayerGui.ScreenGui.Inventory.Frame.Sidebar.Buttons.Items.Button",
    gumTray = "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Tray.Gum.Button",
    gumAction = "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Selected.Action.Button",
    lemonGum = "LocalPlayer.PlayerGui.ScreenGui.GumShop.Frame.Items.Inner.List.Lemon.Button",
    rewardsOpen = "LocalPlayer.PlayerGui.ScreenGui.HUD.Left.Buttons.DailyRewards.Button",
    rewardsPlaytime = "LocalPlayer.PlayerGui.ScreenGui.DailyRewards.Frame.Playtime.Main.1.Button",
    questsPlaytimeCandidate = "LocalPlayer.PlayerGui.ScreenGui.Quests.Frame.Main.Prizes.Tabs.Playtime.Button",
    enchantReroll = "LocalPlayer.PlayerGui.ScreenGui.Enchants.Frame.Inner.Details.Main.Enchants.Enchant1.Reroll.Button",
    showmanPrompt = "Workspace.Rendered.Chunker.Showman Egg.Prompt.ProximityPrompt",
}

local alive = true
local autoPrompt = false
local autoInterval = 1.2
local autoElapsed = 0
local connections = {}
local highlights = {}
local stats = {attempts = 0, successes = 0, failures = 0}

local function split(path)
    local out = {}
    for part in string.gmatch(path, "[^%.]+") do
        out[#out + 1] = part
    end
    return out
end

local function resolve(path)
    if type(path) ~= "string" or path == "" then
        return nil, "invalid path"
    end

    local parts = split(path)
    if #parts == 0 then
        return nil, "empty path"
    end

    local root = nil
    local start = 2
    if parts[1] == "LocalPlayer" then
        root = player
    elseif parts[1] == "Workspace" then
        root = workspace
    elseif parts[1] == "PlayerGui" then
        root = player:FindFirstChild("PlayerGui")
    else
        root = player:FindFirstChild("PlayerGui")
        start = 1
    end

    if not root then
        return nil, "missing root"
    end

    local current = root
    for i = start, #parts do
        current = current:FindFirstChild(parts[i])
        if not current then
            return nil, "missing segment: " .. parts[i]
        end
    end

    return current, nil
end

local function clearHighlights()
    for _, obj in ipairs(highlights) do
        pcall(function() obj:Destroy() end)
    end
    table.clear(highlights)
end

local function highlight(path)
    clearHighlights()
    local obj = resolve(path)
    if not obj then
        return false
    end

    if obj:IsA("GuiObject") then
        local stroke = Instance.new("UIStroke")
        stroke.Color = Color3.fromRGB(255, 205, 60)
        stroke.Thickness = 3
        stroke.Parent = obj
        highlights[#highlights + 1] = stroke
        return true
    end

    local adornee = obj
    if obj:IsA("ProximityPrompt") then
        adornee = obj.Parent
    end
    if adornee and adornee:IsA("BasePart") then
        local marker = Instance.new("SelectionBox")
        marker.LineThickness = 0.06
        marker.Color3 = Color3.fromRGB(255, 205, 60)
        marker.Adornee = adornee
        marker.Parent = workspace
        highlights[#highlights + 1] = marker
        return true
    end

    return false
end

local function trySignal(signal)
    if type(firesignal) == "function" then
        local ok = pcall(function() firesignal(signal) end)
        if ok then
            return true, "firesignal"
        end
    end
    return false, "no signal invoker"
end

local function tryVirtualClick(button)
    local okService, vim = pcall(function() return game:GetService("VirtualInputManager") end)
    if not okService or not vim then
        return false, "VirtualInputManager unavailable"
    end

    local size = button.AbsoluteSize
    local pos = button.AbsolutePosition
    if size.X <= 1 or size.Y <= 1 then
        return false, "zero clickable area"
    end

    local x = pos.X + math.floor(size.X / 2)
    local y = pos.Y + math.floor(size.Y / 2)
    local ok = pcall(function()
        vim:SendMouseMoveEvent(x, y, game)
        vim:SendMouseButtonEvent(x, y, 0, true, game, 1)
        vim:SendMouseButtonEvent(x, y, 0, false, game, 1)
    end)

    if ok then
        return true, "virtual click"
    end
    return false, "virtual click failed"
end

local function activateGui(path)
    stats.attempts += 1

    local obj, err = resolve(path)
    if not obj or not obj:IsA("GuiButton") then
        stats.failures += 1
        return false, "resolve failed: " .. tostring(err or "not GuiButton")
    end

    local ok, mode = trySignal(obj.Activated)
    if not ok and obj.MouseButton1Click then
        ok, mode = trySignal(obj.MouseButton1Click)
    end
    if not ok then
        ok, mode = tryVirtualClick(obj)
    end

    if ok then
        stats.successes += 1
        return true, "activated via " .. mode
    end

    stats.failures += 1
    return false, "activation unavailable"
end

local function activatePrompt(path)
    stats.attempts += 1

    local prompt, err = resolve(path)
    if not prompt or not prompt:IsA("ProximityPrompt") then
        stats.failures += 1
        return false, "resolve failed: " .. tostring(err or "not ProximityPrompt")
    end
    if type(fireproximityprompt) ~= "function" then
        stats.failures += 1
        return false, "fireproximityprompt unavailable"
    end

    local ok, e = pcall(function() fireproximityprompt(prompt) end)
    if ok then
        stats.successes += 1
        return true, "prompt fired"
    end

    stats.failures += 1
    return false, "prompt activation failed: " .. tostring(e)
end

local gui = Instance.new("ScreenGui")
gui.Name = "LycolesBubbleGumUtility"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")

local frame = Instance.new("Frame")
frame.Size = UDim2.fromOffset(560, 460)
frame.Position = UDim2.new(0.5, -280, 0.5, -230)
frame.BackgroundColor3 = Color3.fromRGB(26, 30, 36)
frame.Parent = gui
Instance.new("UICorner", frame).CornerRadius = UDim.new(0, 10)
Instance.new("UIStroke", frame).Color = Color3.fromRGB(96, 176, 240)

local title = Instance.new("TextLabel", frame)
title.Size = UDim2.new(1, -56, 0, 34)
title.Position = UDim2.fromOffset(10, 6)
title.BackgroundTransparency = 1
title.TextXAlignment = Enum.TextXAlignment.Left
title.TextSize = 17
title.TextColor3 = Color3.fromRGB(241, 245, 250)
title.Text = "Lycoles Bubble Utility | real inspection controls"

local close = Instance.new("TextButton", frame)
close.Size = UDim2.fromOffset(34, 26)
close.Position = UDim2.new(1, -40, 0, 8)
close.Text = "X"
close.TextColor3 = Color3.fromRGB(245, 248, 252)
close.BackgroundColor3 = Color3.fromRGB(85, 90, 98)

local status = Instance.new("TextLabel", frame)
status.Size = UDim2.new(1, -20, 0, 96)
status.Position = UDim2.fromOffset(10, 44)
status.BackgroundColor3 = Color3.fromRGB(34, 39, 47)
status.TextColor3 = Color3.fromRGB(221, 232, 242)
status.TextXAlignment = Enum.TextXAlignment.Left
status.TextYAlignment = Enum.TextYAlignment.Top
status.TextWrapped = true
status.TextSize = 14
status.Text = "Ready."
Instance.new("UICorner", status).CornerRadius = UDim.new(0, 8)

local list = Instance.new("ScrollingFrame", frame)
list.Size = UDim2.new(1, -20, 1, -150)
list.Position = UDim2.fromOffset(10, 146)
list.BackgroundColor3 = Color3.fromRGB(31, 36, 43)
list.ScrollBarThickness = 8
Instance.new("UICorner", list).CornerRadius = UDim.new(0, 8)

local layout = Instance.new("UIListLayout", list)
layout.Padding = UDim.new(0, 6)

local function updateStatus(message)
    status.Text = table.concat({
        message,
        "",
        "Attempts: " .. stats.attempts .. " | Successes: " .. stats.successes .. " | Failures: " .. stats.failures,
        "Auto Showman Prompt: " .. (autoPrompt and "ON" or "OFF") .. " @ " .. string.format("%.2fs", autoInterval),
        "",
        "Safety: client-only interactions; runtime/gameplay outcomes remain unverified.",
    }, "\n")
end

local function addButton(name, fn)
    local b = Instance.new("TextButton", list)
    b.Size = UDim2.new(1, -10, 0, 34)
    b.TextSize = 13
    b.TextColor3 = Color3.fromRGB(245, 248, 252)
    b.BackgroundColor3 = Color3.fromRGB(57, 92, 121)
    b.Text = name
    Instance.new("UIStroke", b).Color = Color3.fromRGB(96, 162, 210)

    table.insert(connections, b.MouseButton1Click:Connect(function()
        local ok, msg = pcall(fn)
        if ok then updateStatus(tostring(msg)) else updateStatus("Action error: " .. tostring(msg)) end
    end))
end

addButton("Scan targets", function()
    local names = {
        {"Inventory", TARGETS.inventoryOpen}, {"Pets", TARGETS.petsTab}, {"Items", TARGETS.itemsTab},
        {"Gum Tray", TARGETS.gumTray}, {"Gum Action", TARGETS.gumAction}, {"Lemon", TARGETS.lemonGum},
        {"Rewards Open", TARGETS.rewardsOpen}, {"Playtime Reward", TARGETS.rewardsPlaytime},
        {"Quests Candidate", TARGETS.questsPlaytimeCandidate}, {"Enchant Reroll", TARGETS.enchantReroll},
        {"Showman Prompt", TARGETS.showmanPrompt},
    }
    local lines = {}
    for _, item in ipairs(names) do
        local found = resolve(item[2]) ~= nil
        lines[#lines + 1] = item[1] .. ": " .. (found and "FOUND" or "MISSING")
    end
    highlight(TARGETS.gumAction)
    return table.concat(lines, "\n")
end)

addButton("Inventory open", function() local ok,msg=activateGui(TARGETS.inventoryOpen);highlight(TARGETS.inventoryOpen);return tostring(ok).." | "..msg end)
addButton("Pets tab", function() local ok,msg=activateGui(TARGETS.petsTab);highlight(TARGETS.petsTab);return tostring(ok).." | "..msg end)
addButton("Items tab", function() local ok,msg=activateGui(TARGETS.itemsTab);highlight(TARGETS.itemsTab);return tostring(ok).." | "..msg end)
addButton("Gum tray", function() local ok,msg=activateGui(TARGETS.gumTray);highlight(TARGETS.gumTray);return tostring(ok).." | "..msg end)
addButton("Gum selected action", function() local ok,msg=activateGui(TARGETS.gumAction);highlight(TARGETS.gumAction);return tostring(ok).." | "..msg end)
addButton("Lemon gum", function() local ok,msg=activateGui(TARGETS.lemonGum);highlight(TARGETS.lemonGum);return tostring(ok).." | "..msg end)
addButton("Open daily rewards", function() local ok,msg=activateGui(TARGETS.rewardsOpen);highlight(TARGETS.rewardsOpen);return tostring(ok).." | "..msg end)
addButton("Claim playtime reward", function() local ok,msg=activateGui(TARGETS.rewardsPlaytime);highlight(TARGETS.rewardsPlaytime);return tostring(ok).." | "..msg end)
addButton("Quests playtime candidate", function() local ok,msg=activateGui(TARGETS.questsPlaytimeCandidate);highlight(TARGETS.questsPlaytimeCandidate);return tostring(ok).." | "..msg end)
addButton("Enchant reroll", function() local ok,msg=activateGui(TARGETS.enchantReroll);highlight(TARGETS.enchantReroll);return tostring(ok).." | "..msg end)
addButton("Showman prompt once", function() local ok,msg=activatePrompt(TARGETS.showmanPrompt);highlight(TARGETS.showmanPrompt);return tostring(ok).." | "..msg end)
addButton("Toggle auto Showman prompt", function() autoPrompt=not autoPrompt;highlight(TARGETS.showmanPrompt);return "Auto prompt: "..(autoPrompt and "ON" or "OFF") end)
addButton("Prompt interval +0.2s", function() autoInterval=math.min(5.0, autoInterval+0.2);return string.format("Interval %.2fs", autoInterval) end)
addButton("Prompt interval -0.2s", function() autoInterval=math.max(0.4, autoInterval-0.2);return string.format("Interval %.2fs", autoInterval) end)
addButton("Stop all", function() autoPrompt=false;clearHighlights();return "Stopped and cleared highlights" end)

layout:GetPropertyChangedSignal("AbsoluteContentSize"):Connect(function()
    list.CanvasSize = UDim2.fromOffset(0, layout.AbsoluteContentSize.Y + 8)
end)
list.CanvasSize = UDim2.fromOffset(0, layout.AbsoluteContentSize.Y + 8)

local dragging = false
local dragStart, startPos

table.insert(connections, title.InputBegan:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging = true
        dragStart = input.Position
        startPos = frame.Position
    end
end))

table.insert(connections, title.InputEnded:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 then
        dragging = false
    end
end))

table.insert(connections, UserInputService.InputChanged:Connect(function(input)
    if dragging and input.UserInputType == Enum.UserInputType.MouseMovement then
        local delta = input.Position - dragStart
        frame.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)
    end
end))

table.insert(connections, RunService.Heartbeat:Connect(function(dt)
    if not alive or not autoPrompt then
        return
    end
    autoElapsed += dt
    if autoElapsed < autoInterval then
        return
    end
    autoElapsed = 0
    local ok, msg = activatePrompt(TARGETS.showmanPrompt)
    updateStatus("Auto prompt tick: " .. tostring(ok) .. " | " .. tostring(msg))
end))

_G.LycolesBubbleClose = function()
    if not alive then
        return
    end
    alive = false
    autoPrompt = false
    clearHighlights()
    for _, c in ipairs(connections) do
        pcall(function() c:Disconnect() end)
    end
    gui:Destroy()
    _G.LycolesBubbleClose = nil
end

table.insert(connections, close.MouseButton1Click:Connect(_G.LycolesBubbleClose))
updateStatus("Ready. Use Scan targets before activating controls.")
