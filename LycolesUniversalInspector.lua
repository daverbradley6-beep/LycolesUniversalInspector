
-- Lycoles Universal Inspector v3.1
-- Universal read-only Roblox inspector.
-- Receiver URL is stored locally, never in the public repository.

local Players = game:GetService("Players")
local HttpService = game:GetService("HttpService")
local player = Players.LocalPlayer
assert(player, "LocalPlayer unavailable")

if type(_G.LycolesInspectorClose) == "function" then
    pcall(_G.LycolesInspectorClose)
end

local CONFIG_FILE = "LycolesInspectorReceiver.txt"
local VERSION = "3.1"

local endpoint = ""
local autoSend = true
local last = nil
local pendingParts = nil
local MAX_PART_BYTES = 105000
local running = false
local alive = true
local watchEnabled = true
local watchConnections = {}
local watchQueue = {}
local watchCount = 0
local watchBusy = false
local lastGameName = nil
local WATCH_INTERVAL = 60
local WATCH_BATCH = 1500

local function trim(value)
    return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function validEndpoint(value)
    if type(value) ~= "string" then return false end
    local host, path = value:match("^https://([^/]+)(/.*)$")
    return host ~= nil
        and path ~= nil
        and path:match("^/ingest/[^/]+/?$") ~= nil
end

local function loadEndpoint()
    if type(readfile) ~= "function" then return end
    local ok, value = pcall(readfile, CONFIG_FILE)
    if ok and validEndpoint(trim(value)) then
        endpoint = trim(value)
    end
end

local function saveEndpoint()
    if not validEndpoint(endpoint) then return false end
    if type(writefile) ~= "function" then return false end
    return pcall(writefile, CONFIG_FILE, endpoint)
end

loadEndpoint()

local gui = Instance.new("ScreenGui")
gui.Name = "LycolesUniversalInspector"
gui.ResetOnSpawn = false
gui.DisplayOrder = 999999
gui.Parent = player:WaitForChild("PlayerGui")

local function create(className, properties, parent)
    local item = Instance.new(className)
    for key, value in pairs(properties) do
        item[key] = value
    end
    item.Parent = parent
    return item
end

local panel = create("Frame", {
    Size = UDim2.fromOffset(510, 440),
    Position = UDim2.new(0.5, -255, 0.5, -220),
    BackgroundColor3 = Color3.fromRGB(55, 55, 55),
    BorderColor3 = Color3.new(0, 0, 0),
    BorderSizePixel = 3,
    Active = true
}, gui)

create("TextLabel", {
    Text = "Lycoles Universal Inspector v" .. VERSION,
    Size = UDim2.new(1, 0, 0, 48),
    BackgroundColor3 = Color3.fromRGB(80, 80, 80),
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 18,
    Font = Enum.Font.GothamBold
}, panel)

local function button(label, x)
    return create("TextButton", {
        Text = label,
        Size = UDim2.fromOffset(116, 40),
        Position = UDim2.fromOffset(x, 56),
        BackgroundColor3 = Color3.fromRGB(105, 105, 105),
        BorderColor3 = Color3.new(0, 0, 0),
        BorderSizePixel = 2,
        TextColor3 = Color3.new(1, 1, 1),
        TextSize = 14,
        Active = true
    }, panel)
end

local scan = button("SCAN", 12)
local copy = button("COPY JSON", 136)
local save = button("SAVE JSON", 260)
local close = button("CLOSE", 384)
local watchToggle = create("TextButton", {
    Text = "WATCH: ON", Size = UDim2.fromOffset(116, 28),
    Position = UDim2.fromOffset(384, 104),
    BackgroundColor3 = Color3.fromRGB(85, 105, 85),
    TextColor3 = Color3.new(1, 1, 1), TextSize = 12
}, panel)

local status = create("TextLabel", {
    Text = "Ready",
    Size = UDim2.fromOffset(484, 40),
    Position = UDim2.fromOffset(12, 105),
    BackgroundTransparency = 1,
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 14,
    TextWrapped = true,
    TextXAlignment = Enum.TextXAlignment.Left
}, panel)

local output = create("TextBox", {
    Text = "",
    Size = UDim2.fromOffset(484, 178),
    Position = UDim2.fromOffset(12, 150),
    BackgroundColor3 = Color3.fromRGB(35, 35, 35),
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 13,
    Font = Enum.Font.Code,
    MultiLine = true,
    TextWrapped = true,
    TextEditable = false,
    TextXAlignment = Enum.TextXAlignment.Left,
    TextYAlignment = Enum.TextYAlignment.Top
}, panel)

local config = create("Frame", {
    Name = "Delivery",
    Size = UDim2.fromOffset(510, 92),
    Position = UDim2.fromOffset(0, 340),
    BackgroundColor3 = Color3.fromRGB(55, 55, 55),
    BorderColor3 = Color3.new(0, 0, 0),
    BorderSizePixel = 2
}, panel)

local url = create("TextBox", {
    Size = UDim2.fromOffset(484, 30),
    Position = UDim2.fromOffset(12, 7),
    PlaceholderText = "HTTPS receiver URL ending /ingest/KEY",
    Text = endpoint,
    ClearTextOnFocus = false,
    TextSize = 13,
    TextColor3 = Color3.new(1, 1, 1),
    BackgroundColor3 = Color3.fromRGB(35, 35, 35)
}, config)

local send = create("TextButton", {
    Size = UDim2.fromOffset(180, 38),
    Position = UDim2.fromOffset(12, 45),
    Text = "SEND JSON",
    TextColor3 = Color3.new(1, 1, 1),
    BackgroundColor3 = Color3.fromRGB(90, 90, 90),
    BorderSizePixel = 2
}, config)

local automatic = create("TextButton", {
    Size = UDim2.fromOffset(290, 38),
    Position = UDim2.fromOffset(208, 45),
    Text = "AUTO-SEND: ON",
    TextColor3 = Color3.new(1, 1, 1),
    BackgroundColor3 = Color3.fromRGB(90, 90, 90),
    BorderSizePixel = 2
}, config)

_G.LycolesInspectorClose = function()
    alive = false
    for _, connection in ipairs(watchConnections) do connection:Disconnect() end
    gui:Destroy()
end

local function transmit()
    if not pendingParts or #pendingParts == 0 then
        status.Text = "Scan not finished"
        return
    end
    endpoint = trim(url.Text)
    if not validEndpoint(endpoint) then
        status.Text = "Use https://HOST/ingest/KEY"
        return
    end
    local requestFn = (syn and syn.request) or http_request or request
    if type(requestFn) ~= "function" then
        status.Text = "HTTP requests unavailable"
        return
    end
    saveEndpoint()
    local receiver = endpoint
    local parts = pendingParts
    status.Text = "Sending 0/" .. #parts .. " parts..."
    task.spawn(function()
        for i, body in ipairs(parts) do
            if not alive then return end
            local ok, response = pcall(requestFn, {
                Url = receiver, Method = "POST",
                Headers = {["Content-Type"] = "application/json"},
                Body = body
            })
            local code = ok and response and tonumber(response.StatusCode)
            if code ~= 200 and code ~= 201 then
                local msg = ok and response and tostring(response.Body or "") or tostring(response)
                status.Text = "Part " .. i .. "/" .. #parts .. " failed: "
                    .. tostring(code or "request error")
                warn("Lycoles upload failed", i, msg)
                return
            end
            status.Text = "Sending " .. i .. "/" .. #parts .. " parts..."
            task.wait(0.15)
        end
        if alive then status.Text = "Report sent (" .. #parts .. "/" .. #parts .. " parts)" end
    end)
end

local function prepareParts(report)
    local scanId = HttpService:GenerateGUID(false)
    local objects = report.objects
    local chunks = {}
    local chunk = {}
    local function encodedSize(items)
        return #HttpService:JSONEncode({
            version = report.version, placeId = report.placeId,
            gameId = report.gameId, placeVersion = report.placeVersion,
            inspectedAt = report.inspectedAt, gameName = report.gameName,
            scanId = scanId, partIndex = 99999, partCount = 99999,
            counts = report.counts, groups = report.groups,
            scanStats = report.scanStats, objects = items
        })
    end
    -- Linear-time batching; repeated JSON-encoding of growing chunks
    -- becomes prohibitively slow for universal scans.
    local chunkBytes = 0
    for _, entry in ipairs(objects) do
        local entryBytes = #HttpService:JSONEncode(entry) + 2
        if chunkBytes + entryBytes > 85000 and #chunk > 0 then
            table.insert(chunks, chunk)
            chunk = {}
            chunkBytes = 0
        end
        table.insert(chunk, entry)
        chunkBytes = chunkBytes + entryBytes
    end
    if #chunk > 0 or #chunks == 0 then table.insert(chunks, chunk) end
    local parts = {}
    for i, items in ipairs(chunks) do
        local part = {
            version = report.version, placeId = report.placeId,
            gameId = report.gameId, placeVersion = report.placeVersion,
            inspectedAt = report.inspectedAt, gameName = report.gameName,
            scanId = scanId, partIndex = i, partCount = #chunks,
            counts = report.counts, groups = report.groups,
            scanStats = report.scanStats, objects = items
        }
        local body = HttpService:JSONEncode(part)
        if #body > 145000 then error("Part exceeds receiver limit") end
        table.insert(parts, body)
    end
    return parts
end

-- Dynamic discovery records newly replicated instances without accessing script source.
-- Changes are uploaded as independent, searchable delta scans.
local function watchPath(obj, root, label)
    local names, current = {}, obj
    while current and current ~= root do
        table.insert(names, 1, current.Name)
        current = current.Parent
    end
    if current ~= root then return nil end
    return label .. "." .. table.concat(names, ".")
end

local function watchVec(v)
    return {x = math.floor(v.X * 100) / 100,
        y = math.floor(v.Y * 100) / 100,
        z = math.floor(v.Z * 100) / 100}
end

local function watchEntry(obj, root, label)
    local path = watchPath(obj, root, label)
    if not path or path:find("LycolesUniversalInspector", 1, true) then return nil end
    local category = "other"
    if obj:IsA("RemoteEvent") or obj:IsA("RemoteFunction") then
        category = "networking"
    elseif obj:IsA("ProximityPrompt") or obj:IsA("ClickDetector") then
        category = "interactions"
    elseif obj:IsA("LuaSourceContainer") then
        category = "scripts"
    elseif obj:IsA("GuiBase2d") or obj:IsA("GuiObject") then
        category = "interface"
    end
    local entry = {path = path:sub(1, 400), class = obj.ClassName, category = category}
    if obj:IsA("BasePart") then
        entry.position, entry.size = watchVec(obj.Position), watchVec(obj.Size)
    elseif obj:IsA("Model") then
        local ok, pivot = pcall(function() return obj:GetPivot() end)
        if ok then entry.position = watchVec(pivot.Position) end
    elseif obj:IsA("Attachment") then
        entry.position = watchVec(obj.WorldPosition)
    elseif obj:IsA("ProximityPrompt") then
        entry.maxActivationDistance = obj.MaxActivationDistance
        entry.holdDuration = obj.HoldDuration
    elseif obj:IsA("ClickDetector") then
        entry.maxActivationDistance = obj.MaxActivationDistance
    elseif obj:IsA("GuiObject") then
        entry.visible = obj.Visible
    end
    return entry
end

local function flushWatch()
    if watchBusy or not watchEnabled or watchCount == 0 or running then return end
    if not autoSend or not validEndpoint(endpoint) then return end
    local requestFn = (syn and syn.request) or http_request or request
    if type(requestFn) ~= "function" then return end
    watchBusy = true
    local batch = {}
    for path, entry in pairs(watchQueue) do
        batch[#batch + 1] = entry
        watchQueue[path] = nil
        watchCount = watchCount - 1
        if #batch >= WATCH_BATCH then break end
    end
    task.spawn(function()
        local report = {
            version = VERSION, placeId = game.PlaceId, gameId = game.GameId,
            placeVersion = game.PlaceVersion, gameName = lastGameName,
            inspectedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            objects = batch, counts = {}, groups = {},
            scanStats = {
                mode = "dynamic-additions", scanned = #batch,
                eligible = #batch, recorded = #batch, omitted = 0,
                byCategory = {}
            }
        }
        local ok, parts = pcall(prepareParts, report)
        if not ok then
            for _, entry in ipairs(batch) do
                if not watchQueue[entry.path] then
                    watchQueue[entry.path] = entry
                    watchCount = watchCount + 1
                end
            end
            watchBusy = false
            return
        end
        local success = true
        for _, body in ipairs(parts) do
            if not alive then success = false break end
            local sent, response = pcall(requestFn, {
                Url = endpoint, Method = "POST",
                Headers = {["Content-Type"] = "application/json"},
                Body = body
            })
            local code = sent and response and tonumber(response.StatusCode)
            if code ~= 200 and code ~= 201 then success = false break end
            task.wait(0.15)
        end
        if not success then
            for _, entry in ipairs(batch) do
                if not watchQueue[entry.path] then
                    watchQueue[entry.path] = entry
                    watchCount = watchCount + 1
                end
            end
            status.Text = "Dynamic upload failed; queued for retry"
        elseif alive then
            status.Text = "Dynamic update sent: " .. #batch .. " objects"
        end
        watchBusy = false
    end)
end

local function startWatching()
    local roots = {
        {root = game:GetService("ReplicatedStorage"), label = "ReplicatedStorage"},
        {root = workspace, label = "Workspace"},
        {root = player:FindFirstChild("PlayerGui"), label = "PlayerGui"}
    }
    for _, spec in ipairs(roots) do
        if spec.root then
            table.insert(watchConnections, spec.root.DescendantAdded:Connect(function(obj)
                if not alive or not watchEnabled then return end
                task.defer(function()
                    if not alive or not watchEnabled then return end
                    local ok, entry = pcall(watchEntry, obj, spec.root, spec.label)
                    if ok and entry and not watchQueue[entry.path] then
                        watchQueue[entry.path] = entry
                        watchCount = watchCount + 1
                    end
                end)
            end))
        end
    end
    task.spawn(function()
        while alive do
            task.wait(WATCH_INTERVAL)
            if alive then flushWatch() end
        end
    end)
end

watchToggle.MouseButton1Click:Connect(function()
    watchEnabled = not watchEnabled
    watchToggle.Text = watchEnabled and "WATCH: ON" or "WATCH: OFF"
    status.Text = watchEnabled and "Dynamic discovery enabled" or "Dynamic discovery paused"
end)

local function inspect()
    if running then return end

    running = true
    status.Text = "Scanning..."

    task.spawn(function()
        local ok, result = pcall(function()
            local report = {
                version = VERSION,
                placeId = game.PlaceId,
                gameId = game.GameId,
                placeVersion = game.PlaceVersion,
                inspectedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
                gameName = nil,
                objects = {},
                counts = {},
                groups = {}
            }

            local okName, info = pcall(function()
                return game:GetService("MarketplaceService"):GetProductInfo(game.PlaceId)
            end)
            if okName and type(info) == "table" and type(info.Name) == "string" then
                report.gameName = info.Name
                lastGameName = info.Name
            end


            -- Universal snapshot: collect every instance in the three client-visible roots.
            -- Names, hierarchy, spatial data, and interaction metadata only.
            -- Never collect chat text, player identifiers, script source, or remote payloads.
            local roots = {
                {instance = game:GetService("ReplicatedStorage"), label = "ReplicatedStorage"},
                {instance = workspace, label = "Workspace"},
                {instance = player:FindFirstChild("PlayerGui"), label = "PlayerGui"}
            }
            report.scanStats = {
                scanned = 0, eligible = 0, recorded = 0, omitted = 0,
                mode = "universal-snapshot", byCategory = {}
            }
            local function categoryOf(obj)
                if obj:IsA("RemoteEvent") or obj:IsA("RemoteFunction")
                    or obj:IsA("UnreliableRemoteEvent") then
                    return "networking"
                elseif obj:IsA("ProximityPrompt") or obj:IsA("ClickDetector") then
                    return "interactions"
                elseif obj:IsA("LuaSourceContainer") then
                    return "scripts"
                elseif obj:IsA("GuiBase2d") or obj:IsA("GuiObject") then
                    return "interface"
                else
                    return "other"
                end
            end
            local function stablePath(obj, root, label)
                local names = {}
                local current = obj
                while current and current ~= root do
                    table.insert(names, 1, current.Name)
                    current = current.Parent
                end
                if current ~= root then return nil end
                return label .. "." .. table.concat(names, ".")
            end
            local function vec3(v)
                return {x = math.floor(v.X * 100) / 100,
                    y = math.floor(v.Y * 100) / 100,
                    z = math.floor(v.Z * 100) / 100}
            end
            for _, spec in ipairs(roots) do
                local root = spec.instance
                if root then
                    local descendants = root:GetDescendants()
                    for i, obj in ipairs(descendants) do
                        if not alive then break end
                        report.scanStats.scanned = report.scanStats.scanned + 1
                        report.counts[obj.ClassName] =
                            (report.counts[obj.ClassName] or 0) + 1
                        local path = stablePath(obj, root, spec.label)
                        if path and not string.find(path, "LycolesUniversalInspector", 1, true) then
                            local category = categoryOf(obj)
                            local entry = {
                                path = string.sub(path, 1, 400),
                                class = obj.ClassName,
                                category = category
                            }
                            -- Position/size help locate objects with generic names.
                            if obj:IsA("BasePart") then
                                entry.position = vec3(obj.Position)
                                entry.size = vec3(obj.Size)
                            elseif obj:IsA("Model") then
                                local okPivot, pivot = pcall(function()
                                    return obj:GetPivot()
                                end)
                                if okPivot then entry.position = vec3(pivot.Position) end
                            elseif obj:IsA("Attachment") then
                                entry.position = vec3(obj.WorldPosition)
                            end
                            if obj:IsA("ProximityPrompt") then
                                entry.maxActivationDistance = obj.MaxActivationDistance
                                entry.holdDuration = obj.HoldDuration
                            elseif obj:IsA("ClickDetector") then
                                entry.maxActivationDistance = obj.MaxActivationDistance
                            elseif obj:IsA("GuiObject") then
                                entry.visible = obj.Visible
                            end
                            if obj:IsA("ModuleScript") then
                                local group = string.match(path,
                                    "ReplicatedStorage%.([%w_]+)") or "other"
                                report.groups[group] = (report.groups[group] or 0) + 1
                            end
                            table.insert(report.objects, entry)
                            report.scanStats.eligible = report.scanStats.eligible + 1
                            local cat = report.scanStats.byCategory[category]
                            if not cat then
                                cat = {eligible = 0, recorded = 0, omitted = 0}
                                report.scanStats.byCategory[category] = cat
                            end
                            cat.eligible = cat.eligible + 1
                            cat.recorded = cat.recorded + 1
                        end
                        if i % 500 == 0 then
                            status.Text = "Scanning " .. report.scanStats.scanned .. " objects..."
                            task.wait()
                        end
                    end
                end
            end
            report.scanStats.recorded = #report.objects
            report.scanStats.omitted = 0

            return report
        end)

        if not alive then return end

        if not ok then
            status.Text = "Scan error: " .. tostring(result)
            running = false
            return
        end

        local encoded, resultData = pcall(function()
            local json = HttpService:JSONEncode(result)
            local parts = prepareParts(result)
            return {json = json, parts = parts}
        end)
        if encoded then
            last = resultData.json
            pendingParts = resultData.parts
            status.Text = "Scan complete - " .. #result.objects
                .. " entries in " .. #pendingParts .. " part(s)"
            output.Text =
                "Game: " .. tostring(result.gameName or "Unknown")
                .. "\\nPlaceId: " .. tostring(result.placeId)
                .. "\\nEntries: " .. #result.objects
                .. "\\nRemotes: "
                .. tostring(result.counts.RemoteEvent or 0) .. " events, "
                .. tostring(result.counts.RemoteFunction or 0) .. " functions"
                .. "\\nParts: " .. #pendingParts
                .. "\\nAUTO-SEND: " .. (autoSend and "ON" or "OFF")
            if autoSend and validEndpoint(endpoint) then transmit() end
        else
            status.Text = "JSON error: " .. tostring(resultData)
        end
        running = false
    end)
end

scan.MouseButton1Click:Connect(inspect)

copy.MouseButton1Click:Connect(function()
    if not last then
        status.Text = "Scan not finished"
        return
    end

    if type(setclipboard) ~= "function" then
        status.Text = "Clipboard unavailable"
        return
    end

    local ok = pcall(setclipboard, last)
    status.Text = ok and "Copied JSON" or "Copy failed"
end)

save.MouseButton1Click:Connect(function()
    if not last then
        status.Text = "Scan not finished"
        return
    end

    if type(writefile) ~= "function" then
        status.Text = "File saving unavailable"
        return
    end

    local ok = pcall(
        writefile,
        "Lycoles_" .. tostring(game.PlaceId) .. ".json",
        last
    )

    status.Text = ok and "Saved JSON" or "Save failed"
end)

close.MouseButton1Click:Connect(_G.LycolesInspectorClose)

url.FocusLost:Connect(function()
    endpoint = trim(url.Text)

    if endpoint == "" then
        status.Text = "Enter receiver URL"
        return
    end

    if not validEndpoint(endpoint) then
        status.Text = "Invalid receiver URL"
        return
    end

    local saved = saveEndpoint()

    status.Text = saved
        and "Receiver URL saved locally"
        or "Receiver ready (local save unavailable)"

    if autoSend and last then
        transmit()
    end
end)

send.MouseButton1Click:Connect(function()
    endpoint = trim(url.Text)
    transmit()
end)

automatic.MouseButton1Click:Connect(function()
    autoSend = not autoSend

    automatic.Text = autoSend
        and "AUTO-SEND: ON"
        or "AUTO-SEND: OFF"

    status.Text = autoSend
        and "Automatic uploads enabled"
        or "Automatic uploads disabled"
end)

if endpoint ~= "" then
    status.Text = "Saved receiver loaded"
else
    status.Text = "Enter receiver URL once"
end

startWatching()
inspect()
