
-- Lycoles Universal Inspector v4.4.1
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
local VERSION = "4.4.1"

local endpoint = ""
local autoSend = true
local last = nil
local pendingParts = nil
local MAX_PART_BYTES = 105000
local running = false
local uploading = false
local uploadGeneration = 0
local pendingAcknowledged = {}
local MAX_UPLOAD_ATTEMPTS = 3
local MAX_CONCURRENT_UPLOADS = 3
local SCAN_YIELD_BUDGET_SECONDS = 0.012
local UPLOAD_RETRY_DELAYS = {1, 3, 6}
local alive = true
local watchEnabled = true
local watchConnections = {}
local watchQueue = {}
local watchCount = 0
local watchBusy = false
local lastGameName = nil
local WATCH_INTERVAL = 30
local watchSeen = {}
local watchSkippedCharacters = 0
local watchUploaded = 0
local changeQueue = {}
local changeCount = 0
local observed = setmetatable({}, {__mode = "k"})
local changeUploaded = 0
local WATCH_BATCH = 1500
local interactionObserveEnabled = false
local interactionObserved = setmetatable({}, {__mode = "k"})
local interactionObservedCount = 0
local interactionEventCount = 0
local sessionId = HttpService:GenerateGUID(false)
local snapshotId = nil
local observationSequence = 0
local FEATURE_TERMS = {
 training={"training","gym","strength","agility"},
 rebirth={"rebirth"}, pets={"pet","hatch","egg"},
 shops={"shop","purchase"}, travel={"teleport","portal"},
 bosses={"boss","arena"}, quests={"quest","mission"},
 combat={"combat","attack"}, inventory={"inventory","equip"},
 rewards={"reward","claim"}
}
local function buildFeatureEvidence(objects)
 local features = {}
 for name in pairs(FEATURE_TERMS) do
  features[name]={counts={controllers=0,remotes=0,gui=0,values=0,world=0},examples={},
   status="not-discovered",confidence="path-name-only",serverVerified=false,
   missingEvidence={"Observed normal interaction","Before/after state verification","Authorised implementation test"}}
 end
 for _,obj in ipairs(objects) do
  local path=tostring(obj.path or "")
  local lower=string.lower(path)
  local class=tostring(obj.class or "")
  local kind="world"
  if class=="ModuleScript" or class=="LocalScript" then kind="controllers"
  elseif class=="RemoteEvent" or class=="RemoteFunction" or class=="UnreliableRemoteEvent" then kind="remotes"
  elseif class=="TextButton" or class=="ImageButton" or class=="ProximityPrompt" or class=="ClickDetector" then kind="gui"
  elseif class=="IntValue" or class=="NumberValue" or class=="BoolValue" or class=="StringValue" then kind="values" end
  for name,terms in pairs(FEATURE_TERMS) do
   for _,term in ipairs(terms) do
    if string.find(lower,term,1,true) then
     local item=features[name]
     item.counts[kind]=item.counts[kind]+1
     item.status="candidate-needs-verification"
     if #item.examples<12 then item.examples[#item.examples+1]={path=path:sub(1,300),class=class,kind=kind} end
     break
    end
   end
  end
 end
 return features
end
local ROOT_LABELS = {"ReplicatedStorage", "ReplicatedFirst", "Workspace", "PlayerGui", "LocalPlayer", "Character", "Lighting", "Teams", "SoundService"}

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
    Size = UDim2.fromOffset(510, 460),
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

-- Draggable panel and compact minimised launcher.
local UserInputService = game:GetService("UserInputService")
local dragging = false
local dragStart, panelStart
local header = panel:FindFirstChildOfClass("TextLabel")
local dragInput = nil
if header then
    header.Active = true
    header.InputChanged:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then
            dragInput = input
        end
    end)
    header.InputBegan:Connect(function(input)
        if input.UserInputType == Enum.UserInputType.MouseButton1
            or input.UserInputType == Enum.UserInputType.Touch then
            dragging = true
            dragStart = input.Position
            panelStart = panel.Position
        end
    end)
end
local dragEndConnection = UserInputService.InputEnded:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1
        or input.UserInputType == Enum.UserInputType.Touch then
        dragging = false
    end
end)
local dragMoveConnection = UserInputService.InputChanged:Connect(function(input)
    if not dragging or not dragStart then return end
    if input ~= dragInput and input.UserInputType ~= Enum.UserInputType.Touch then return end
    if input.UserInputType ~= Enum.UserInputType.MouseMovement
        and input.UserInputType ~= Enum.UserInputType.Touch then return end
    local delta = input.Position - dragStart
    panel.Position = UDim2.new(
        panelStart.X.Scale, panelStart.X.Offset + delta.X,
        panelStart.Y.Scale, panelStart.Y.Offset + delta.Y
    )
end)
local minimise = create("TextButton", {
    Name = "Minimise", Text = "_",
    Size = UDim2.fromOffset(36, 30),
    Position = UDim2.new(1, -42, 0, 9),
    BackgroundColor3 = Color3.fromRGB(100, 100, 100),
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 20, ZIndex = 3
}, panel)
local mini = create("TextButton", {
    Name = "RestoreInspector",
    Text = "Lycoles +",
    Size = UDim2.fromOffset(115, 36),
    Position = UDim2.new(0, 15, 0, 100),
    BackgroundColor3 = Color3.fromRGB(55, 55, 55),
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 14,
    Visible = false,
    Active = true
}, gui)
minimise.MouseButton1Click:Connect(function()
    panel.Visible = false
    mini.Visible = true
end)
mini.MouseButton1Click:Connect(function()
    mini.Visible = false
    panel.Visible = true
end)

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

local interactionToggle = create("TextButton", {
    Text = "INTERACT: OFF", Size = UDim2.fromOffset(116, 26),
    Position = UDim2.fromOffset(384, 136),
    BackgroundColor3 = Color3.fromRGB(85, 85, 105),
    TextColor3 = Color3.new(1, 1, 1), TextSize = 11
}, panel)

local status = create("TextLabel", {
    Text = "Ready",
    Size = UDim2.fromOffset(365, 54),
    Position = UDim2.fromOffset(12, 101),
    BackgroundTransparency = 1,
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 14,
    TextWrapped = true,
    TextXAlignment = Enum.TextXAlignment.Left
}, panel)

local queueLabel = create("TextLabel", {
    Text = "New: 0 | Changed: 0 | Sent: 0 | Skipped: 0",
    Size = UDim2.fromOffset(484, 18),
    Position = UDim2.fromOffset(12, 328),
    BackgroundTransparency = 1,
    TextColor3 = Color3.fromRGB(190, 230, 190),
    TextSize = 12,
    TextXAlignment = Enum.TextXAlignment.Left
}, panel)

local function refreshQueue()
    queueLabel.Text = "New: " .. watchCount .. " | Changed: " .. changeCount
        .. " | Sent: " .. (watchUploaded + changeUploaded)
        .. " | Skipped: " .. watchSkippedCharacters
end

local output = create("TextBox", {
    Text = "",
    Size = UDim2.fromOffset(484, 164),
    Position = UDim2.fromOffset(12, 164),
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
    Position = UDim2.fromOffset(0, 352),
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
    uploadGeneration = uploadGeneration + 1
    for _, connection in ipairs(watchConnections) do connection:Disconnect() end
    dragEndConnection:Disconnect()
    dragMoveConnection:Disconnect()
    gui:Destroy()
end

-- Return a verified acknowledgement; never log the secret-bearing endpoint.
local function uploadPart(requestFn, receiver, body, scanId, partIndex, partCount)
    local lastError = "request not attempted"
    for attempt = 1, MAX_UPLOAD_ATTEMPTS do
        if not alive then return false, "inspector closed" end
        local ok, response = pcall(requestFn, {
            Url = receiver, Method = "POST",
            Headers = {["Content-Type"] = "application/json"},
            Body = body
        })
        local code = ok and response and tonumber(response.StatusCode)
        if code == 200 or code == 201 then
            local decodedOk, ack = pcall(function()
                return HttpService:JSONDecode(response.Body or "")
            end)
            if decodedOk and type(ack) == "table" and ack.ok == true
                and ack.scanId == scanId and ack.partIndex == partIndex
                and ack.partCount == partCount and type(ack.id) == "string" then
                return true, ack.id
            end
            lastError = "invalid acknowledgement"
        else
            lastError = "HTTP " .. tostring(code or "request error")
        end
        warn("Lycoles upload attempt failed", partIndex, attempt, lastError)
        if attempt < MAX_UPLOAD_ATTEMPTS then
            task.wait(UPLOAD_RETRY_DELAYS[attempt])
        end
    end
    return false, lastError
end

local function transmit()
    if uploading then
        status.Text = "Upload already running"
        return
    end
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
    local first = HttpService:JSONDecode(parts[1])
    local scanId = first.scanId
    local partCount = #parts
    uploading = true
    uploadGeneration = uploadGeneration + 1
    local generation = uploadGeneration
    task.spawn(function()
        local started = os.clock()
        local succeeded, failed, nextIndex, active = 0, nil, 1, 0
        for i = 1, partCount do
            if pendingAcknowledged[i] then succeeded = succeeded + 1 end
        end
        local workers = math.min(MAX_CONCURRENT_UPLOADS, partCount)
        for _ = 1, workers do
            active = active + 1
            task.spawn(function()
                while alive and generation == uploadGeneration and not failed do
                    local i = nextIndex
                    nextIndex = nextIndex + 1
                    if i > partCount then break end
                    if not pendingAcknowledged[i] then
                        local ok, message = uploadPart(requestFn, receiver, parts[i], scanId, i, partCount)
                        if not ok then
                            failed = "Part " .. i .. "/" .. partCount .. " failed (" .. tostring(message) .. ")"
                            break
                        end
                        pendingAcknowledged[i] = message
                        succeeded = succeeded + 1
                        status.Text = "Verified " .. succeeded .. "/" .. partCount .. " parts"
                    end
                end
                active = active - 1
            end)
        end
        while active > 0 and alive and generation == uploadGeneration do task.wait(0.1) end
        uploading = false
        if not alive or generation ~= uploadGeneration then return end
        local elapsed = math.floor((os.clock()-started)*100)/100
        if failed then
            status.Text = failed .. "; SEND JSON to retry"
        elseif succeeded == partCount then
            status.Text = "Upload complete: " .. succeeded .. "/" .. partCount
                .. " acknowledged in " .. tostring(elapsed) .. "s"
        else
            status.Text = "Upload incomplete: " .. succeeded .. "/" .. partCount .. "; retry SEND JSON"
        end
    end)
end

-- Convert inspection data to JSON-safe primitives without circular references.
local function jsonSafe(value, active, depth)
    local kind = typeof(value)
    if kind == "nil" then return nil end
    if kind == "string" then return value end
    if kind == "boolean" then return value end
    if kind == "number" then
        if value ~= value or value == math.huge or value == -math.huge then return nil end
        return value
    end
    if kind == "Vector3" then return {x=value.X,y=value.Y,z=value.Z} end
    if kind == "Vector2" then return {x=value.X,y=value.Y} end
    if kind == "Color3" then return {r=value.R,g=value.G,b=value.B} end
    if kind == "UDim" then return {scale=value.Scale,offset=value.Offset} end
    if kind == "UDim2" then return {x=jsonSafe(value.X,active,depth+1),y=jsonSafe(value.Y,active,depth+1)} end
    if kind == "EnumItem" then return tostring(value) end
    if kind == "Instance" then return value.ClassName end
    if kind ~= "table" then return tostring(value) end
    if depth >= 24 then return "[max-depth]" end
    if active[value] then return "[circular-reference]" end
    active[value] = true
    local output = {}
    for key, child in pairs(value) do
        local keyKind = typeof(key)
        if keyKind == "string" or keyKind == "number" then
            local safeChild = jsonSafe(child, active, depth+1)
            if safeChild ~= nil then output[key] = safeChild end
        end
    end
    active[value] = nil
    return output
end

local function encodeStage(stage, value)
    local ok, encoded = pcall(function()
        return HttpService:JSONEncode(jsonSafe(value, {}, 0))
    end)
    if not ok then error(stage .. ": " .. tostring(encoded), 2) end
    return encoded
end

local function prepareParts(report)
    local prepareStarted = os.clock()
    local scanId = HttpService:GenerateGUID(false)
    local objects = report.objects
    local chunks = {}
    local chunk = {}
    local function encodedSize(items)
        return #encodeStage('part-size', {
            version = report.version, placeId = report.placeId,
            gameId = report.gameId, placeVersion = report.placeVersion,
            inspectedAt = report.inspectedAt, gameName = report.gameName,
            scanId = scanId, partIndex = 99999, partCount = 99999,
            counts = report.counts, groups = report.groups,
            scanStats = report.scanStats, sessionId = report.sessionId, snapshotId = report.snapshotId, parentSnapshotId = report.parentSnapshotId, featureEvidence = report.featureEvidence, objects = items
        })
    end
    -- Linear-time batching; repeated JSON-encoding of growing chunks
    -- becomes prohibitively slow for universal scans.
    local chunkBytes = 0
    for _, entry in ipairs(objects) do
        local okEntry, encodedEntry = pcall(function()
            return encodeStage('object ' .. tostring(entry.path), entry)
        end)
        local cleanEntry = entry
        if not okEntry then
            -- Preserve the object's identity even when its optional metadata
            -- cannot be serialized. Never abort a whole scan for one object.
            cleanEntry = {
                path = tostring(entry.path or "unknown"):sub(1,400),
                class = tostring(entry.class or "Instance"),
                category = tostring(entry.category or "other"),
                serializationFallback = true
            }
            local okFallback, fallbackJson = pcall(function()
                return encodeStage('fallback-object', cleanEntry)
            end)
            if okFallback then
                encodedEntry = fallbackJson
            else
                cleanEntry = {path = "unserializable-object", class = "Unknown",
                    category = "other", serializationFallback = true}
                encodedEntry = '{"path":"unserializable-object","class":"Unknown","category":"other","serializationFallback":true}'
            end
        end
        local entryBytes = #encodedEntry + 2
        if chunkBytes + entryBytes > 85000 and #chunk > 0 then
            table.insert(chunks, chunk)
            chunk = {}
            chunkBytes = 0
        end
        table.insert(chunk, cleanEntry)
        chunkBytes = chunkBytes + entryBytes
    end
    if #chunk > 0 or #chunks == 0 then table.insert(chunks, chunk) end
    -- Exact-size multipart packing. Shared evidence is sent once (part 1),
    -- rather than copied into every chunk. Never truncate or drop an object.
    local function makePart(items, index, total)
        return {
            version = report.version, placeId = report.placeId,
            gameId = report.gameId, placeVersion = report.placeVersion,
            inspectedAt = report.inspectedAt, gameName = report.gameName,
            scanId = scanId, partIndex = index, partCount = total,
            counts = index == 1 and report.counts or nil,
            groups = index == 1 and report.groups or nil,
            scanStats = index == 1 and report.scanStats or nil,
            sessionId = report.sessionId, snapshotId = report.snapshotId,
            parentSnapshotId = report.parentSnapshotId,
            featureEvidence = index == 1 and report.featureEvidence or nil,
            objects = items
        }
    end
    local limit = math.min(MAX_PART_BYTES, 140000)
    local changed = true
    while changed do
        changed = false
        local total = #chunks
        for i = 1, total do
            local body = encodeStage('size-check-' .. i, makePart(chunks[i], i, total))
            if #body > limit then
                if #chunks[i] <= 1 then
                    error("Single object or shared scan metadata exceeds receiver payload limit")
                end
                local source = chunks[i]
                local half = math.floor(#source / 2)
                local left, right = {}, {}
                for j, entry in ipairs(source) do
                    if j <= half then left[#left + 1] = entry
                    else right[#right + 1] = entry end
                end
                chunks[i] = left
                table.insert(chunks, i + 1, right)
                changed = true
                break
            end
        end
    end
    local parts = {}
    for i, items in ipairs(chunks) do
        local body = encodeStage('part-' .. i, makePart(items, i, #chunks))
        if #body > limit then error("Unexpected oversized part") end
        parts[#parts + 1] = body
    end
    report.localPerformance = report.localPerformance or {}
    report.localPerformance.serializationSeconds = math.floor((os.clock()-prepareStarted)*1000+0.5)/1000
    report.localPerformance.uploadParts = #parts
    local bytes = 0
    for _, body in ipairs(parts) do bytes = bytes + #body end
    report.localPerformance.uploadBytes = bytes
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

local function isCharacterDescendant(obj)
    local current = obj
    while current and current ~= workspace do
        if current:IsA("Model") and Players:GetPlayerFromCharacter(current) then
            return true
        end
        current = current.Parent
    end
    return false
end


-- v4.0: bounded, read-only metadata. Never inspect script source or private player text.
local siblingContextCache = nil
local function enrichEntry(entry, obj)
    local function privateKey(k)
        k = string.lower(tostring(k))
        return k:find("password",1,true) or k:find("token",1,true)
            or k:find("secret",1,true) or k:find("auth",1,true)
            or k:find("webhook",1,true) or k:find("userid",1,true)
            or k:find("chat",1,true) or k:find("message",1,true)
    end
    local function scalar(v)
        local t = typeof(v)
        if t == "boolean" then return v end
        if t == "number" and v == v and math.abs(v) <= 1e12 then return v end
        if t == "string" then return v:sub(1,100):gsub("[%c]"," ") end
        return nil
    end
    local ok, attrs = pcall(function() return obj:GetAttributes() end)
    if ok and type(attrs) == "table" then
        local safe, n = {}, 0
        for k,v in pairs(attrs) do
            if n >= 24 then break end
            if not privateKey(k) then
                local value = scalar(v)
                if value ~= nil then safe[tostring(k):sub(1,60)] = value; n = n + 1 end
            end
        end
        if n > 0 then entry.attributes = safe end
    end
    local isQuestCurrency =
        obj.Name == "Tokens"
        and obj:IsA("NumberValue")
        and obj.Parent ~= nil
        and (obj.Parent.Name == "rewards" or obj.Parent.Name == "requirements")
        and obj.Parent.Parent ~= nil
        and obj.Parent.Parent.Parent ~= nil
        and obj.Parent.Parent.Parent.Name == "Quests"
        and obj.Parent.Parent.Parent.Parent ~= nil
        and obj.Parent.Parent.Parent.Parent.Name == "Battle Legends"
        and obj.Parent.Parent.Parent.Parent.Parent ~= nil
        and obj.Parent.Parent.Parent.Parent.Parent.Name == "Story Quests"

    if obj:IsA("ValueBase") and (isQuestCurrency or not privateKey(obj.Name)) then
        local success, value = pcall(function() return obj.Value end)
        if success then entry.value = scalar(value) end
    end
    -- GUI metadata is limited to control labels and structural properties.
    -- TextLabel contents are deliberately excluded because they may contain private/player text.
    if obj:IsA("GuiObject") then
        entry.gui = {
            visible = obj.Visible,
            active = obj.Active,
            selectable = obj.Selectable,
            size = {xScale=obj.Size.X.Scale, xOffset=obj.Size.X.Offset,
                yScale=obj.Size.Y.Scale, yOffset=obj.Size.Y.Offset},
            position = {xScale=obj.Position.X.Scale, xOffset=obj.Position.X.Offset,
                yScale=obj.Position.Y.Scale, yOffset=obj.Position.Y.Offset},
            zIndex = obj.ZIndex,
            layoutOrder = obj.LayoutOrder
        }
    end
    if obj:IsA("GuiButton") then
        local buttonText = ""
        pcall(function() buttonText = obj.Text end)
        local interactable = nil
        pcall(function() interactable = obj.Interactable end)
        entry.guiControl = {
            text = tostring(buttonText):sub(1,100):gsub("[%c]", " "),
            autoButtonColor = obj.AutoButtonColor,
            enabled = interactable
        }
    elseif obj:IsA("TextBox") then
        entry.guiControl = {placeholder = tostring(obj.PlaceholderText):sub(1,100)}
    end
    if obj:IsA("ModuleScript") then
        entry.moduleMetadata = {name=obj.Name, class="ModuleScript", sourceAccessible=false,
            note="Module source is not read; dependencies are not inferred from names alone"}
    elseif obj:IsA("LocalScript") or obj:IsA("Script") then
        local enabled = nil
        pcall(function() enabled = obj.Enabled end)
        entry.scriptMetadata = {name=obj.Name, class=obj.ClassName, enabled=enabled,
            sourceAccessible=false, note="Script source is not read"}
    end
    if obj:IsA("Humanoid") then
        entry.health, entry.maxHealth, entry.walkSpeed = obj.Health, obj.MaxHealth, obj.WalkSpeed
    elseif obj:IsA("Tool") then
        entry.tool = {requiresHandle=obj.RequiresHandle,canBeDropped=obj.CanBeDropped,tooltip=obj.ToolTip:sub(1,120)}
    elseif obj:IsA("ProximityPrompt") then
        entry.interaction = {actionText=obj.ActionText:sub(1,120),objectText=obj.ObjectText:sub(1,120),
            enabled=obj.Enabled,holdDuration=obj.HoldDuration,maxActivationDistance=obj.MaxActivationDistance}
    elseif obj:IsA("ClickDetector") then
        entry.interaction = {maxActivationDistance=obj.MaxActivationDistance}
    end
    -- Multi-label, evidence-labelled system classification.
    local parent = obj.Parent
    local parentName = parent and string.lower(parent.Name) or ""
    local objectName = string.lower(obj.Name)
    local lower = string.lower(entry.path)
    local haystack = lower .. " " .. objectName .. " " .. parentName
    local groups = {
        training={"train","training","gym","strength","agility","durability","rep","machine"},
        progression={"level","xp","experience","rebirth","ascension","prestige","unlock","requirement"},
        quests={"quest","mission","objective","daily","weekly","task"},
        pets={"pet","companion","egg","hatch","enchant","evolve"},
        economy={"shop","store","vendor","price","cost","cash","gold","gem","currency","purchase"},
        rewards={"reward","claim","chest","crate","gift","spin","drop"},
        bosses={"boss","raid","elite","arena"},
        travel={"teleport","portal","spawn","vehicle","mount","area"},
        combat={"weapon","damage","attack","fight","combat","brawl","health"},
        inventory={"inventory","backpack","item","equipment","tool"},
        crafting={"craft","recipe","forge","upgrade"},
        clans={"clan","guild","competition"},
        social={"chat","friend","trade","trading","party"},
        passes={"gamepass","pass","product","developerproduct"},
        interface={"gui","menu","button","frame","screen"}
    }
    local tags = {}
    for category, names in pairs(groups) do
        for _, name in ipairs(names) do
            if haystack:find(name, 1, true) then
                tags[#tags + 1] = category
                break
            end
        end
    end
    table.sort(tags)
    if #tags > 0 then
        entry.inferredCategories = tags
        entry.evidence = "multi-label-name-path-parent-inference"
    end

    -- Parent/ancestor context gives the analysis service hierarchy evidence.
    if parent then
        local parentPath = entry.path:match("^(.*)%.[^%.]+$")
        entry.parentContext = {
            name = tostring(parent.Name):sub(1,100),
            class = parent.ClassName,
            path = parentPath
        }
        local ancestors, current = {}, parent
        for depth = 1, 4 do
            if not current then break end
            local fullName = nil
            pcall(function() fullName = current:GetFullName() end)
            ancestors[#ancestors + 1] = {
                name = tostring(current.Name):sub(1,100),
                class = current.ClassName,
                path = fullName
            }
            current = current.Parent
        end
        if #ancestors > 0 then entry.ancestorContext = ancestors end
    end

    -- Bounded sibling ValueBase context supports cross-system relationship mapping.
    if obj:IsA("ValueBase") and parent then
        local cached = siblingContextCache and siblingContextCache[parent]
        if not cached then
            local related, total = {}, 0
            for _, sibling in ipairs(parent:GetChildren()) do
                if sibling:IsA("ValueBase") and not privateKey(sibling.Name) then
                    total = total + 1
                    if #related < 9 then
                        local okValue, siblingValue = pcall(function() return sibling.Value end)
                        if okValue then
                            local safeValue = scalar(siblingValue)
                            if safeValue ~= nil then
                                related[#related + 1] = {
                                    name = tostring(sibling.Name):sub(1,100),
                                    class = sibling.ClassName,
                                    value = safeValue
                                }
                            end
                        end
                    end
                end
            end
            cached = {total = total, values = related}
            if siblingContextCache then siblingContextCache[parent] = cached end
        end
        local siblings = {}
        for _, item in ipairs(cached.values) do
            if item.name ~= tostring(obj.Name) and #siblings < 8 then
                siblings[#siblings + 1] = item
            end
        end
        entry.valueContext = {
            parentPath = entry.parentContext and entry.parentContext.path,
            siblingValueCount = math.max(0,cached.total - 1),
            siblingsTruncated = cached.total - 1 > #siblings,
            siblingValues = siblings
        }
        local key = objectName
        local roles = {
            requirement={"requirement","required","needed","unlock"},
            reward={"reward","gain","bonus","drop"},
            economy={"price","cost","currency","cash","gold","gem"},
            multiplier={"multiplier","percent","boost","rate"},
            timing={"time","duration","cooldown","interval"},
            quantity={"amount","count","capacity","slots","limit"},
            stat={"strength","durability","agility","damage","health","level","experience","rebirth"}
        }
        local valueRoles = {}
        for role, words in pairs(roles) do
            for _, word in ipairs(words) do
                if key:find(word,1,true) then
                    valueRoles[#valueRoles + 1] = role
                    break
                end
            end
        end
        table.sort(valueRoles)
        if #valueRoles > 0 then entry.valueRoles = valueRoles end
    end

    -- Controller/service candidates are explicitly heuristic; source is never read.
    if obj:IsA("ModuleScript") or obj:IsA("LocalScript") or obj:IsA("Script") then
        local n = objectName
        local role = n:find("controller",1,true) and "controller"
            or (n:find("manager",1,true) and "manager"
            or (n:find("service",1,true) and "service"
            or (n:find("handler",1,true) and "handler"
            or (n:find("component",1,true) and "component" or nil))))
        if role then
            entry.controllerCandidate = true
            entry.controllerEvidence = "name-based-candidate-only"
            entry.controllerRole = role
        end
    end

    -- Capture UI control structure only. Never collect text entered into TextBoxes.
    if obj:IsA("GuiButton") then
        local buttonText = ""
        pcall(function() buttonText = obj.Text end) -- ImageButton has no Text property.
        entry.controlMetadata = {
            controlType = obj.ClassName,
            text = tostring(buttonText or ""):sub(1,100):gsub("[%c]"," "),
            visible = obj.Visible,
            active = obj.Active,
            selectable = obj.Selectable
        }
        local okInteractable, interactable = pcall(function() return obj.Interactable end)
        if okInteractable then entry.controlMetadata.interactable = interactable end
    elseif obj:IsA("TextBox") then
        entry.controlMetadata = {
            controlType = "TextBox",
            placeholder = tostring(obj.PlaceholderText or ""):sub(1,100):gsub("[%c]"," "),
            clearTextOnFocus = obj.ClearTextOnFocus,
            multiLine = obj.MultiLine,
            textEditable = obj.TextEditable,
            visible = obj.Visible,
            active = obj.Active
        }
    end

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
    enrichEntry(entry, obj)
    return entry
end

-- Track selected client-replicated state changes without reading private text.
local function observeObject(obj, root, label)
    if observed[obj] then return end
    if label == "Workspace" and isCharacterDescendant(obj) then return end
    local property
    if obj:IsA("BoolValue") or obj:IsA("IntValue") or obj:IsA("NumberValue") then
        property = "Value"
    elseif obj:IsA("ProximityPrompt") then
        property = "Enabled"
    elseif obj:IsA("GuiObject") then
        property = "Visible"
    end
    if not property then return end
    local path = watchPath(obj, root, label)
    if not path or path:find("LycolesUniversalInspector", 1, true) then return end
    observed[obj] = true
    local ok, signal = pcall(function() return obj:GetPropertyChangedSignal(property) end)
    if not ok then return end
    local connection = signal:Connect(function()
        if not alive or not watchEnabled then return end
        local valid, value = pcall(function() return obj[property] end)
        if not valid or (type(value) ~= "boolean" and type(value) ~= "number") then return end
        if type(value) == "number" and (value ~= value or math.abs(value) > 1e12) then return end
        local currentPath = watchPath(obj, root, label)
        if not currentPath then return end
        -- Preserve every transition instead of overwriting earlier values.
        changeCount = changeCount + 1
        changeQueue[#changeQueue + 1] = {
            path = currentPath:sub(1, 400), class = obj.ClassName,
            category = "state-change", property = property, value = value
        }
    end)
    table.insert(watchConnections, connection)
end

-- Passive observation only: records controls the user activates normally while enabled.
-- It never fires controls, invokes remotes, blocks input, or reads private text.
local function observeInteractionObject(obj, root, label)
    if interactionObserved[obj] then return end
    local path = watchPath(obj, root, label)
    if not path or path:find("LycolesUniversalInspector", 1, true) then return end
    local signal, controlType
    if obj:IsA("GuiButton") then
        signal, controlType = obj.Activated, "GuiButton.Activated"
    elseif obj:IsA("ProximityPrompt") then
        signal, controlType = obj.Triggered, "ProximityPrompt.Triggered"
    elseif obj:IsA("ClickDetector") then
        signal, controlType = obj.MouseClick, "ClickDetector.MouseClick"
    end
    if not signal then return end
    interactionObserved[obj] = true
    interactionObservedCount = interactionObservedCount + 1
    local connection = signal:Connect(function()
        if not alive or not interactionObserveEnabled then return end
        interactionEventCount = interactionEventCount + 1
        observationSequence = observationSequence + 1
        changeCount = changeCount + 1
        changeQueue[#changeQueue + 1] = {
            path = path:sub(1,400), class = obj.ClassName,
            category = "user-interaction", controlType = controlType,
            action = "user-activated", observedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            evidence = "manual-user-interaction", sessionId = sessionId, snapshotId = snapshotId, sequence = observationSequence
        }
    end)
    table.insert(watchConnections, connection)
end

local function flushWatch()
    if watchBusy or not watchEnabled or (watchCount == 0 and changeCount == 0) or running or uploading then return end
    if not autoSend or not validEndpoint(endpoint) then return end
    local requestFn = (syn and syn.request) or http_request or request
    if type(requestFn) ~= "function" then return end
    watchBusy = true
    local batch = {}
    local changesInBatch = 0
    local take = math.min(changeCount, WATCH_BATCH)
    for i = 1, take do
        batch[#batch + 1] = changeQueue[i]
    end
    for i = take + 1, changeCount do
        changeQueue[i - take] = changeQueue[i]
    end
    for i = changeCount - take + 1, changeCount do
        changeQueue[i] = nil
    end
    changeCount = changeCount - take
    changesInBatch = take
    if #batch < WATCH_BATCH then for path, entry in pairs(watchQueue) do
        batch[#batch + 1] = entry
        watchQueue[path] = nil
        watchCount = watchCount - 1
        if #batch >= WATCH_BATCH then break end
    end end
    task.spawn(function()
        local report = {
            version = VERSION, placeId = game.PlaceId, gameId = game.GameId,
            placeVersion = game.PlaceVersion, gameName = lastGameName,
            inspectedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            objects = batch, counts = {}, groups = {},
            sessionId = sessionId, parentSnapshotId = snapshotId,
            featureEvidence = buildFeatureEvidence(batch),
            scanStats = {
                mode = changesInBatch > 0 and "dynamic-observations" or "dynamic-additions", scanned = #batch,
                eligible = #batch, recorded = #batch, omitted = 0,
                byCategory = {}
            }
        }
        local ok, parts = pcall(prepareParts, report)
        if not ok then
            local retryChanges = {}
            for _, entry in ipairs(batch) do
                if entry.category == "state-change" then
                    -- Restore failed events in their original order.
                    retryChanges[#retryChanges + 1] = entry
                elseif not watchQueue[entry.path] then
                    watchQueue[entry.path] = entry; watchCount = watchCount + 1
                end
            end
            if #retryChanges > 0 then
                local queued = changeQueue
                changeQueue = retryChanges
                for _, entry in ipairs(queued) do
                    changeQueue[#changeQueue + 1] = entry
                end
                changeCount = #changeQueue
            end
            watchBusy = false
            return
        end
        local success = true
        for _, body in ipairs(parts) do
            if not alive then success = false break end
            local part = HttpService:JSONDecode(body)
            local sent = uploadPart(requestFn, endpoint, body,
                part.scanId, part.partIndex, part.partCount)
            if not sent then success = false break end
            task.wait(0.15)
        end
        if not success then
            local retryChanges = {}
            for _, entry in ipairs(batch) do
                if entry.category == "state-change" then
                    -- Restore failed events in their original order.
                    retryChanges[#retryChanges + 1] = entry
                elseif not watchQueue[entry.path] then
                    watchQueue[entry.path] = entry; watchCount = watchCount + 1
                end
            end
            if #retryChanges > 0 then
                local queued = changeQueue
                changeQueue = retryChanges
                for _, entry in ipairs(queued) do
                    changeQueue[#changeQueue + 1] = entry
                end
                changeCount = #changeQueue
            end
            status.Text = "Dynamic upload failed; queued for retry"
        elseif alive then
            watchUploaded = watchUploaded + (#batch - changesInBatch)
            changeUploaded = changeUploaded + changesInBatch
            status.Text = "Dynamic update sent: " .. #batch .. " objects"
        end
        refreshQueue()
        watchBusy = false
    end)
end

local function startWatching()
    local roots = {
        {root = game:GetService("ReplicatedStorage"), label = "ReplicatedStorage"},
        {root = game:GetService("ReplicatedFirst"), label = "ReplicatedFirst"},
        {root = workspace, label = "Workspace"},
        {root = player, label = "LocalPlayer"},
        {root = player.Character, label = "Character"},
        {root = game:GetService("Lighting"), label = "Lighting"},
        {root = game:GetService("Teams"), label = "Teams"},
        {root = game:GetService("SoundService"), label = "SoundService"}
    }
    for _, spec in ipairs(roots) do
        if spec.root then
            table.insert(watchConnections, spec.root.DescendantAdded:Connect(function(obj)
                if not alive or not watchEnabled then return end
                task.defer(function()
                    if not alive or not watchEnabled then return end
                    if spec.label == "Workspace" and isCharacterDescendant(obj) then
                        watchSkippedCharacters = watchSkippedCharacters + 1
                        return
                    end
                    observeObject(obj, spec.root, spec.label)
                    observeInteractionObject(obj, spec.root, spec.label)
                    local ok, entry = pcall(watchEntry, obj, spec.root, spec.label)
                    if ok and entry and not watchQueue[entry.path] and not watchSeen[entry.path] then
                        watchSeen[entry.path] = true
                        watchQueue[entry.path] = entry
                        watchCount = watchCount + 1
                    end
                end)
            end))
        end
        if spec.root then
            task.spawn(function()
                local descendants = spec.root:GetDescendants()
                for i, obj in ipairs(descendants) do
                    if not alive then return end
                    observeObject(obj, spec.root, spec.label)
                    observeInteractionObject(obj, spec.root, spec.label)
                    if i % 500 == 0 then task.wait() end
                end
            end)
        end
    end
    -- Rebind the local-character observer after respawns without rescanning other players.
    table.insert(watchConnections, player.CharacterAdded:Connect(function(character)
        if not alive then return end
        local label = "Character"
        task.defer(function()
            if not alive then return end
            local ok, descendants = pcall(function() return character:GetDescendants() end)
            if ok then
                for i, obj in ipairs(descendants) do
                    if not alive then return end
                    observeObject(obj, character, label)
                    observeInteractionObject(obj, character, label)
                    if i % 300 == 0 then task.wait() end
                end
            end
            local connection = character.DescendantAdded:Connect(function(obj)
                if not alive or not watchEnabled then return end
                task.defer(function()
                    if not alive or not watchEnabled then return end
                    observeObject(obj, character, label)
                    observeInteractionObject(obj, character, label)
                    local good, entry = pcall(watchEntry, obj, character, label)
                    if good and entry and not watchQueue[entry.path] and not watchSeen[entry.path] then
                        watchSeen[entry.path] = true
                        watchQueue[entry.path] = entry
                        watchCount = watchCount + 1
                    end
                end)
            end)
            table.insert(watchConnections, connection)
        end)
    end))

    task.spawn(function()
        while alive do
            task.wait(WATCH_INTERVAL)
            if alive then
                refreshQueue()
                flushWatch()
            end
        end
    end)
end

watchToggle.MouseButton1Click:Connect(function()
    watchEnabled = not watchEnabled
    watchToggle.Text = watchEnabled and "WATCH: ON" or "WATCH: OFF"
    status.Text = watchEnabled and "Dynamic discovery enabled" or "Dynamic discovery paused"
end)

interactionToggle.MouseButton1Click:Connect(function()
    interactionObserveEnabled = not interactionObserveEnabled
    interactionToggle.Text = interactionObserveEnabled and "INTERACT: ON" or "INTERACT: OFF"
    interactionToggle.BackgroundColor3 = interactionObserveEnabled
        and Color3.fromRGB(65, 105, 85) or Color3.fromRGB(85, 85, 105)
    status.Text = interactionObserveEnabled
        and "Manual interaction observation enabled; use game controls normally"
        or "Manual interaction observation paused"
end)

local function inspect()
    if running or uploading then
        status.Text = "Wait for current scan/upload to finish"
        return
    end
    if pendingParts and #pendingParts > 0 then
        for i = 1, #pendingParts do
            if not pendingAcknowledged[i] then
                status.Text = "Unsent parts remain; press SEND JSON to retry before rescanning"
                return
            end
        end
    end

    running = true
    siblingContextCache = setmetatable({}, {__mode="k"})
    status.Text = "Scanning..."

    task.spawn(function()
        local scanStarted = os.clock()
        local ok, result = pcall(function()
            local report = {
                version = VERSION,
                sessionId = sessionId, snapshotId = HttpService:GenerateGUID(false),
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
                {instance = game:GetService("ReplicatedFirst"), label = "ReplicatedFirst"},
                {instance = workspace, label = "Workspace"},
                {instance = player:FindFirstChild("PlayerGui"), label = "PlayerGui"},
                {instance = player, label = "LocalPlayer"},
                {instance = player.Character, label = "Character"},
                {instance = game:GetService("Lighting"), label = "Lighting"},
                {instance = game:GetService("Teams"), label = "Teams"},
                {instance = game:GetService("SoundService"), label = "SoundService"}
            }
            report.scanStats = {
                scanned = 0, eligible = 0, recorded = 0, omitted = 0,
                mode = "universal-snapshot-v4.1", byCategory = {}, byRoot = {},
                rootCoverage = {}, byClass = {},
                valueBase = {scanned = 0, recorded = 0, byClass = {}},
                guiControls = {buttons = 0, textBoxes = 0, prompts = 0, clickDetectors = 0},
                scriptCandidates = {modules = 0, localScripts = 0, scripts = 0, controllers = 0},
                omissions = {overlappingRoots = 0, invalidPath = 0, inspectorSelf = 0},
                performance = {rootSeconds = {}, yieldCount = 0, scanSeconds = 0},
                pathCollisionsResolved = 0,
                siblingContextLimit = 8,
                limitations = {scriptSource="not-read", serverState="not-visible", remotePayloads="not-collected"}
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
            report.scanStats.rootAvailability = {}
            local requiredRoots = {ReplicatedStorage=true, Workspace=true, PlayerGui=true, LocalPlayer=true}
            local scanAborted = false
            local pathOccurrences = {}
            local scanInstanceIds = setmetatable({}, {__mode="k"})
            local nextInstanceId = 0
            for _, spec in ipairs(roots) do
                local rootStarted = os.clock()
                local yieldDeadline = os.clock() + SCAN_YIELD_BUDGET_SECONDS
                local root = spec.instance
                local coverage = {
                    available = root ~= nil, required = requiredRoots[spec.label] == true,
                    success = false, scanned = 0, recorded = 0, omitted = 0
                }
                report.scanStats.rootCoverage[spec.label] = coverage
                report.scanStats.rootAvailability[spec.label] = root ~= nil
                if root then
                    local okDescendants, descendants = pcall(function() return root:GetDescendants() end)
                    if okDescendants and type(descendants) == "table" then
                        coverage.success = true
                        for i, obj in ipairs(descendants) do
                        if not alive then break end
                        report.scanStats.scanned = report.scanStats.scanned + 1
                        coverage.scanned = coverage.scanned + 1
                        report.scanStats.byRoot[spec.label] = (report.scanStats.byRoot[spec.label] or 0) + 1
                        report.counts[obj.ClassName] = (report.counts[obj.ClassName] or 0) + 1
                        report.scanStats.byClass[obj.ClassName] = (report.scanStats.byClass[obj.ClassName] or 0) + 1
                        if obj:IsA("ValueBase") then
                            report.scanStats.valueBase.scanned = report.scanStats.valueBase.scanned + 1
                            report.scanStats.valueBase.byClass[obj.ClassName] =
                                (report.scanStats.valueBase.byClass[obj.ClassName] or 0) + 1
                        end
                        if obj:IsA("GuiButton") then report.scanStats.guiControls.buttons = report.scanStats.guiControls.buttons + 1 end
                        if obj:IsA("TextBox") then report.scanStats.guiControls.textBoxes = report.scanStats.guiControls.textBoxes + 1 end
                        if obj:IsA("ProximityPrompt") then report.scanStats.guiControls.prompts = report.scanStats.guiControls.prompts + 1 end
                        if obj:IsA("ClickDetector") then report.scanStats.guiControls.clickDetectors = report.scanStats.guiControls.clickDetectors + 1 end
                        if obj:IsA("ModuleScript") then report.scanStats.scriptCandidates.modules = report.scanStats.scriptCandidates.modules + 1 end
                        if obj:IsA("LocalScript") then report.scanStats.scriptCandidates.localScripts = report.scanStats.scriptCandidates.localScripts + 1 end
                        if obj:IsA("Script") then report.scanStats.scriptCandidates.scripts = report.scanStats.scriptCandidates.scripts + 1 end
                        local path = stablePath(obj, root, spec.label)
                        if spec.label == "LocalPlayer" and path and
                            (path:find("^LocalPlayer%.PlayerGui") or path:find("^LocalPlayer%.Character")) then
                            path = nil -- Dedicated roots prevent duplicate PlayerGui/Character captures.
                            report.scanStats.omissions.overlappingRoots = report.scanStats.omissions.overlappingRoots + 1
                        end
                        if spec.label == "Workspace" and isCharacterDescendant(obj) then
                            path = nil
                            report.scanStats.omissions.overlappingRoots = report.scanStats.omissions.overlappingRoots + 1
                        end
                        if path and string.find(path, "LycolesUniversalInspector", 1, true) then
                            path = nil
                            report.scanStats.omissions.inspectorSelf = report.scanStats.omissions.inspectorSelf + 1
                        end
                        if path then
                            -- Roblox permits identically named siblings. Preserve each object
                            -- with an unambiguous scan-local occurrence suffix.
                            local count = (pathOccurrences[path] or 0) + 1
                            pathOccurrences[path] = count
                            if count > 1 then
                                path = path:sub(1, 380) .. "[occurrence:" .. tostring(count) .. "]"
                                report.scanStats.pathCollisionsResolved =
                                    (report.scanStats.pathCollisionsResolved or 0) + 1
                            end
                            nextInstanceId = nextInstanceId + 1
                            scanInstanceIds[obj] = nextInstanceId
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
                            enrichEntry(entry, obj)
                            if obj:IsA("ModuleScript") or obj:IsA("LocalScript") or obj:IsA("Script") then
                                local n = string.lower(obj.Name)
                                if n:find("controller",1,true) or n:find("manager",1,true)
                                    or n:find("service",1,true) or n:find("handler",1,true) then
                                    entry.controllerCandidate = true
                                    entry.controllerEvidence = "name-based-candidate-only"
                                end
                            end
                            local tagOk, tags = pcall(function()
                                return game:GetService("CollectionService"):GetTags(obj)
                            end)
                            if tagOk and type(tags) == "table" and #tags > 0 then
                                entry.tags = {}
                                for ti = 1, math.min(#tags, 20) do
                                    entry.tags[ti] = tostring(tags[ti]):sub(1,80)
                                end
                            end
                            table.insert(report.objects, entry)
                            report.scanStats.eligible = report.scanStats.eligible + 1
                            coverage.recorded = coverage.recorded + 1
                            if obj:IsA("ValueBase") and entry.value ~= nil then
                                report.scanStats.valueBase.recorded = report.scanStats.valueBase.recorded + 1
                            end
                            if entry.controllerCandidate then
                                report.scanStats.scriptCandidates.controllers =
                                    report.scanStats.scriptCandidates.controllers + 1
                            end
                            local cat = report.scanStats.byCategory[category]
                            if not cat then
                                cat = {eligible = 0, recorded = 0, omitted = 0}
                                report.scanStats.byCategory[category] = cat
                            end
                            cat.eligible = cat.eligible + 1
                            cat.recorded = cat.recorded + 1
                        else
                            report.scanStats.omitted = report.scanStats.omitted + 1
                            coverage.omitted = coverage.omitted + 1
                            if not path then report.scanStats.omissions.invalidPath = report.scanStats.omissions.invalidPath + 1 end
                        end
                        if os.clock() >= yieldDeadline then
                            status.Text = "Scanning " .. report.scanStats.scanned .. " objects..."
                            report.scanStats.performance.yieldCount = report.scanStats.performance.yieldCount + 1
                            task.wait()
                            yieldDeadline = os.clock() + SCAN_YIELD_BUDGET_SECONDS
                        end
                        end
                    else
                        coverage.error = tostring(descendants)
                        scanAborted = true
                    end
                else
                    coverage.error = "root unavailable"
                end
                if coverage.required and not coverage.success then scanAborted = true end
                report.scanStats.performance.rootSeconds[spec.label] = math.floor((os.clock()-rootStarted)*1000+0.5)/1000
            end
            report.scanStats.performance.scanSeconds = math.floor((os.clock()-scanStarted)*1000+0.5)/1000
            report.scanStats.recorded = #report.objects
            local rootAccountingValid = true
            for _, coverage in pairs(report.scanStats.rootCoverage) do
                if coverage.scanned ~= coverage.recorded + coverage.omitted then
                    rootAccountingValid = false
                end
            end
            local requiredRootsPresent = true
            for rootName, required in pairs(requiredRoots) do
                if required and (not report.scanStats.rootCoverage[rootName]
                    or not report.scanStats.rootCoverage[rootName].success) then
                    requiredRootsPresent = false
                end
            end
            local scanComplete = not scanAborted and requiredRootsPresent
                and rootAccountingValid
                and report.scanStats.scanned == report.scanStats.recorded + report.scanStats.omitted
            report.scanStats.complete = scanComplete
            report.featureEvidence = buildFeatureEvidence(report.objects)
            report.diagnostics = {
                complete = scanComplete,
                completenessBasis = "required-root-success-and-object-accounting",
                requiredRootsPresent = requiredRootsPresent,
                rootAccountingValid = rootAccountingValid,
                scannedObjects = report.scanStats.scanned,
                recordedObjects = report.scanStats.recorded,
                omittedObjects = report.scanStats.omitted,
                completeButLimitedToClientVisibleRoots = true,
                scanMode = "client-visible-read-only",
                rootsScanned = report.scanStats.byRoot,
                rootAvailability = report.scanStats.rootAvailability,
                classCounts = report.counts,
                evidenceRules = {
                    controllerCandidates = "Name-based candidates only; no source inspection",
                    guiControls = "Visible client-side GUI hierarchy and button labels",
                    interactions = "Manual interaction observer must be enabled separately",
                    configuration = "Replicated ValueBase objects and safe attributes only",
                    serverLogic = "Not observable from this client scan"
                },
                knownLimitations = {
                    "No server-side state or implementation access",
                    "No script source or module source collection",
                    "No remote payload capture or invocation",
                    "No guarantee that client-visible values are authoritative",
                    "Only supported client-visible roots are scanned",
                    "Root completeness does not imply full server or game completeness",
                    "System tags and controller roles are name/path-based candidates",
                    "Sibling value context is hierarchy evidence, not a verified gameplay formula"
                }
            }

            return report
        end)

        if not alive then return end

        if not ok then
            status.Text = "Scan error: " .. tostring(result)
            siblingContextCache = nil
        running = false
            return
        end

        local encoded, resultData = pcall(function()
            -- Large universal scans must never be encoded as one JSON document.
            -- The receiver accepts bounded parts; keep only a small clipboard manifest.
            local parts = prepareParts(result)
            local manifest = encodeStage('scan-manifest', {
                version = VERSION, gameName = result.gameName,
                sessionId = result.sessionId, snapshotId = result.snapshotId,
                featureEvidence = result.featureEvidence,
                placeId = result.placeId, inspectedAt = result.inspectedAt,
                objectCount = #result.objects, partCount = #parts,
                expectedParts = #parts, uploadedParts = 0,
                scanStats = result.scanStats, diagnostics = result.diagnostics,
                note = "Full inspection is uploaded in numbered parts; manifest includes coverage diagnostics"
            })
            return {json = manifest, parts = parts}
        end)
        if encoded then
            snapshotId = result.snapshotId
            last = resultData.json
            pendingParts = resultData.parts
            pendingAcknowledged = {}
            status.Text = (result.diagnostics.complete and "Scan complete - " or "PARTIAL SCAN - ")
                .. #result.objects .. " entries in " .. #pendingParts .. " part(s)"
            output.Text =
                "Game: " .. tostring(result.gameName or "Unknown")
                .. "\\nPlaceId: " .. tostring(result.placeId)
                .. "\\nEntries: " .. #result.objects
                .. "\\nRemotes: "
                .. tostring(result.counts.RemoteEvent or 0) .. " events, "
                .. tostring(result.counts.RemoteFunction or 0) .. " functions"
                .. "\\nParts: " .. #pendingParts
                .. "\\nRoots: " .. tostring(result.scanStats and result.scanStats.byRoot and #ROOT_LABELS or 0)
                .. "\\nInteraction observer: " .. (interactionObserveEnabled and "ON" or "OFF")
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