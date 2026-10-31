
-- Lycoles Universal Inspector v23.0.0
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
local VERSION = "25.0.0"

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
local interactionObserveEnabled = true
local AUTO_EVIDENCE_ENABLED = true
local AUTO_EVIDENCE_IDLE_SECONDS = 12
local AUTO_EVIDENCE_COOLDOWN_SECONDS = 45
local AUTO_EVIDENCE_MAX_RESCANS = 4
local autoEvidenceLastInteraction = 0
local autoEvidenceLastScan = 0
local autoEvidenceLastSequence = 0
local autoEvidenceRescans = 0
local autoEvidenceLastFailure = nil
local interactionObserved = setmetatable({}, {__mode = "k"})
local interactionObservedCount = 0
local interactionEventCount = 0
local attributedInteractionCount = 0
local unattributedInteractionCount = 0
local interactionHistory = {}
local MAX_INTERACTION_HISTORY = 180
local MAX_PENDING_ACTIONS = 24
local OBSERVATION_WINDOWS = {0.35, 1.25, 3.0}
local MAX_STATE_CHANGES = 24
local MAX_GUI_CHANGES = 16
local transactionEvidenceSeen = {}
local transactionEvidenceCount = 0
local MAX_TRANSACTION_SIGNATURES = 2000
local pendingActions = {}
local workflowStats = {linkedConfirmations=0, cancelled=0, expired=0, completedCandidates=0, guiTransitions=0, observationFailures=0, classifiedByContext=0, actionOutcomesCorroborated=0, multiWindowSamples=0, uniqueStateEvents=0, uniqueGuiEvents=0, travelCandidates=0, rewardClaimGuiCandidates=0}
local scanInvocationCount = 0
local scanRequestType = "startup-baseline"
local observerStats = {listenersAttached=0, callbacksFired=0, stateDeltaEvents=0, bindingErrors=0, sweepCompleted=false, sweepScanned=0, lastEventPath=nil, activationCount=0, deactivationCount=0, lastEnabledAt=nil, lastDisabledAt=nil, lastDisabledReason=nil, lastSweepError=nil, sweepStartedAt=nil, sweepFinishedAt=nil, lastCallbackAt=nil}
local sessionId = HttpService:GenerateGUID(false)
local snapshotId = nil
local observationSequence = 0
-- Feature candidates are based on the final object name, not arbitrary ancestor
-- paths. This prevents 'LiveRequest' being classified as a quest.
local FEATURE_TERMS = {
 training={"training","gym","strength","agility","treadmill"},
 rebirth={"rebirth"}, pets={"pet","hatch","egg"},
 shops={"shop","purchase","store"}, travel={"teleport","portal"},
 bosses={"boss","arena"}, quests={"quest","mission"},
 combat={"combat","attack","damage"}, inventory={"inventory","equip"},
 rewards={"reward","claim"}
}
-- Readiness is evidence-based: discovery never implies a working feature.
-- Compare successive client-visible snapshots without treating changes as proof of cause.
local previousFeatureSnapshot = nil
local featureInteractions = {}
local function featureForName(name)
    local separated = tostring(name):gsub("(%l)(%u)", "%1 %2"):gsub("(%u)(%u%l)", "%1 %2")
    local tokens = {}
    for token in separated:lower():gmatch("[%a%d]+") do tokens[token] = true end
    local matches = {}
    for feature, terms in pairs(FEATURE_TERMS) do
        for _, term in ipairs(terms) do
            if tokens[term] or tokens[term.."s"] or (term=="rebirth" and tokens.rebirthing) then
                matches[#matches+1] = feature
                break
            end
        end
    end
    return #matches == 1 and matches[1] or nil, #matches
end
-- Local-only bounded snapshots. No player IDs, chat, text fields or server claims.
local function interactionGuiContext(obj)
    local context = {ancestors={}, visibleMenus={}}
    local node = obj.Parent
    for i=1,8 do
        if not node then break end
        context.ancestors[#context.ancestors+1] = node.Name:sub(1,80)
        if node:IsA("ScreenGui") then
            context.screenGui = node.Name
            context.screenEnabled = node.Enabled
        elseif node:IsA("GuiObject") and node.Visible and #context.visibleMenus < 4 then
            context.visibleMenus[#context.visibleMenus+1] = node.Name:sub(1,80)
        end
        node = node.Parent
    end
    return context
end
-- Capture nearby GUI state without collecting text, input contents or private data.
local function safeNearbyGuiState(obj)
    local result, count = {}, 0
    if not obj:IsA("GuiObject") then return result end
    local menu = obj.Parent
    while menu and not menu:IsA("ScreenGui") do
        if menu:IsA("GuiObject") and (menu.Name:lower():find("menu",1,true)
            or menu.Name:lower():find("base",1,true)) then break end
        menu = menu.Parent
    end
    if not menu or menu:IsA("ScreenGui") then menu = obj.Parent end
    if not menu then return result end
    local ok, descendants = pcall(function() return menu:GetDescendants() end)
    if not ok then return result end
    for _, node in ipairs(descendants) do
        if count >= 160 then break end
        if node:IsA("GuiObject") then
            local segments, parent = {}, node
            while parent and parent ~= menu and #segments < 7 do
                table.insert(segments,1,parent.Name)
                parent=parent.Parent
            end
            local key=table.concat(segments,"/"):sub(1,180)
            if key ~= "" and not key:lower():find("password",1,true) then
                result[key] = {visible=node.Visible}
                if node:IsA("GuiButton") then
                    result[key].active=node.Active
                end
                count=count+1
            end
        end
    end
    return result
end
local function compareNearbyGuiState(before, after)
    local changes={}
    for key, value in pairs(before) do
        local nextValue=after[key]
        if nextValue and (value.visible ~= nextValue.visible or value.active ~= nextValue.active) then
            changes[#changes+1]={path=key,beforeVisible=value.visible,afterVisible=nextValue.visible,
                beforeActive=value.active,afterActive=nextValue.active}
            if #changes >= 16 then break end
        end
    end
    for key, value in pairs(after) do
        if not before[key] and #changes < 16 then
            changes[#changes+1]={path=key,transition="appeared",afterVisible=value.visible,afterActive=value.active}
        end
    end
    for key, value in pairs(before) do
        if not after[key] and #changes < 16 then
            changes[#changes+1]={path=key,transition="disappeared",beforeVisible=value.visible,beforeActive=value.active}
        end
    end
    table.sort(changes,function(a,b) return a.path < b.path end)
    return changes
end
local function safeInteractionState()
    local state, count = {}, 0
    local roots = {}
    for _, name in ipairs({"leaderstats", "Data"}) do
        local root = player:FindFirstChild(name)
        if root then roots[#roots+1] = root end
    end
    for _, root in ipairs(roots) do
        if root then
            local items = root:GetDescendants()
            for _, obj in ipairs(items) do
                if count >= 1000 then break end
                if obj:IsA("IntValue") or obj:IsA("NumberValue") or obj:IsA("BoolValue") then
                    local segments = {}
                    local parent = obj
                    while parent and parent ~= root and #segments < 6 do
                        table.insert(segments, 1, parent.Name)
                        parent = parent.Parent
                    end
                    local key = (root.Name.."."..table.concat(segments,".")):sub(1,180)
                    local low = key:lower()
                    if not (low:find("token",1,true) or low:find("secret",1,true)
                        or low:find("auth",1,true) or low:find("password",1,true)
                        or low:find("userid",1,true)) then
                        local v = obj.Value
                        if type(v) == "boolean" or (type(v) == "number" and v == v and math.abs(v) <= 1e12) then
                            state[key] = v
                            count = count + 1
                        end
                    end
                end
            end
        end
    end
    return state
end
-- v5.5: stable, unique relative paths and change-only inventory evidence.
local function inventoryGuiPath(obj,gui)
    local parts={}
    local current=obj
    while current and current~=gui and #parts<18 do
        local parent=current.Parent
        local occurrence=1
        if parent then
            for _,sibling in ipairs(parent:GetChildren()) do
                if sibling==current then break end
                if sibling.Name==current.Name then occurrence=occurrence+1 end
            end
        end
        table.insert(parts,1,current.Name.."#"..occurrence)
        current=parent
    end
    return table.concat(parts,"/"):sub(1,260)
end
local function safeInventorySummary()
    local result={guiSlots=0,guiEquippedIndicators=0,guiIndicatorSamples={},
        guiSlotSamples={},sourceCoverage="client-visible-inventory-gui",
        authoritative=false,truncated=false}
    local gui=player:FindFirstChildOfClass("PlayerGui")
    if not gui then return result end
    local count=0
    -- Only derive expensive ancestry keys for actual slot/indicator candidates.
    for _,obj in ipairs(gui:GetDescendants()) do
        count=count+1
        if count>25000 then result.truncated=true break end
        if obj:IsA("GuiObject") then
            local name=obj.Name:lower()
            local isSlot=name:match("^slot%d+") or name:find("petslot",1,true)
            local isIndicator=name:find("equipped",1,true) or name:find("tickimage",1,true)
            if isSlot or isIndicator then
                local ancestor=obj.Parent
                local inInventory=false
                while ancestor and ancestor~=gui do
                    local ancestorName=ancestor.Name:lower()
                    if ancestorName=="itemsbg" or ancestorName=="itemsnewmenu" or
                        ancestorName:find("inventory",1,true) or
                        ancestorName=="petsrightbase" then
                        inInventory=true
                        break
                    end
                    ancestor=ancestor.Parent
                end
                if inInventory then
                local path=inventoryGuiPath(obj,gui)
                if isSlot then
                    result.guiSlots=result.guiSlots+1
                    if #result.guiSlotSamples<100 then
                        result.guiSlotSamples[#result.guiSlotSamples+1]={
                            key=path,visible=obj.Visible,class=obj.ClassName}
                    end
                elseif isIndicator then
                    result.guiEquippedIndicators=result.guiEquippedIndicators+1
                    if #result.guiIndicatorSamples<100 then
                        result.guiIndicatorSamples[#result.guiIndicatorSamples+1]={
                            key=path,visible=obj.Visible,class=obj.ClassName}
                    end
                end
                end
            end
        end
    end
    return result
end
local function compareInventoryGuiSamples(before,after)
    local result={indicatorChanges={},slotChanges={},
        sampledIndicators=#(after.guiIndicatorSamples or {}),
        sampledSlots=#(after.guiSlotSamples or {}),authoritative=false}
    local function compare(field,target)
        local old={}
        for _,entry in ipairs(before[field] or {}) do old[entry.key]=entry end
        for _,entry in ipairs(after[field] or {}) do
            local prior=old[entry.key]
            if prior and prior.visible~=entry.visible and #target<24 then
                target[#target+1]={key=entry.key,beforeVisible=prior.visible,
                    afterVisible=entry.visible}
            elseif not prior and #target<24 then
                target[#target+1]={key=entry.key,transition="appeared",
                    afterVisible=entry.visible}
            end
            old[entry.key]=nil
        end
        for _,entry in pairs(old) do
            if #target<24 then target[#target+1]={
                key=entry.key,transition="disappeared",beforeVisible=entry.visible} end
        end
        table.sort(target,function(x,y) return x.key<y.key end)
    end
    compare("guiIndicatorSamples",result.indicatorChanges)
    compare("guiSlotSamples",result.slotChanges)
    return result
end
local function compareFeatureSnapshots(current)
    local delta = {basis="successive-scan-feature-candidate-counts", causalVerification=false, features={}}
    if not previousFeatureSnapshot then
        delta.status="baseline-created"
    else
        delta.status="compared"
        for name, item in pairs(current) do
            local before=previousFeatureSnapshot[name]
            local counts={}
            for kind, count in pairs(item.counts) do
                counts[kind]=count-((before and before[kind]) or 0)
            end
            delta.features[name]=counts
        end
    end
    local nextSnapshot={}
    for name,item in pairs(current) do
        nextSnapshot[name]={}
        for kind,count in pairs(item.counts) do nextSnapshot[name][kind]=count end
    end
    previousFeatureSnapshot=nextSnapshot
    return delta
end

local function buildReadiness(evidence, observedCount)
    local result = {}
    for feature, item in pairs(evidence) do
        local discovered = item.status == "candidate-needs-verification"
        result[feature] = {
            discovered = discovered,
            observed = featureInteractions[feature] ~= nil and featureInteractions[feature].count > 0,
            observedStateChange = featureInteractions[feature] ~= nil and featureInteractions[feature].stateChanges > 0,
            interactionEvidence = featureInteractions[feature],
            implemented = false,
            tested = false,
            readiness = not discovered and "not-discovered"
                or (featureInteractions[feature] and featureInteractions[feature].stateChanges > 0 and "state-change-candidate-needs-validation")
                or (featureInteractions[feature] and featureInteractions[feature].count > 0 and "interaction-observed-needs-state-verification")
                or "needs-observed-interaction",
            controllerCandidates = item.counts.controllers,
            remoteCandidates = item.counts.remotes,
            guiCandidates = item.counts.gui,
            verificationRequired = {
                "Associate a normal interaction with this feature",
                "Confirm a relevant before/after state change",
                "Implement the feature in the game-specific script",
                "Execute and verify the implementation"
            },
            note = "Unattributed interaction count is not feature verification",
            unattributedInteractionEvents = unattributedInteractionCount or 0
        }
    end
    return result
end

local function buildFeatureEvidence(objects)
    local features = {}
    for name in pairs(FEATURE_TERMS) do
        features[name] = {
            counts={controllers=0,remotes=0,gui=0,values=0,world=0},
            examples={}, status="not-discovered",
            confidence="object-name-candidate-only", serverVerified=false,
            missingEvidence={"Observed normal interaction","Before/after state verification","Authorised implementation test"}
        }
    end
    for _,obj in ipairs(objects) do
        local path = tostring(obj.path or "")
        local leaf = path:match("([^%.]+)$") or path
        leaf = leaf:gsub("%[occurrence:%d+%]$", "")
        -- Split camelCase/PascalCase and punctuation into tokens. In particular,
        -- LiveRequest must NOT match the "quest" feature.
        local separated = leaf:gsub("(%l)(%u)", "%1 %2"):gsub("(%u)(%u%l)", "%1 %2")
        local tokens = {}
        for token in string.lower(separated):gmatch("[%a%d]+") do
            tokens[token] = true
        end
        local class = tostring(obj.class or "")
        local kind = "world"
        if class=="ModuleScript" or class=="LocalScript" then kind="controllers"
        elseif class=="RemoteEvent" or class=="RemoteFunction" or class=="UnreliableRemoteEvent" then kind="remotes"
        elseif class=="TextButton" or class=="ImageButton" or class=="ProximityPrompt" or class=="ClickDetector" then kind="gui"
        elseif class=="IntValue" or class=="NumberValue" or class=="BoolValue" or class=="StringValue" then kind="values" end
        for name,terms in pairs(FEATURE_TERMS) do
            for _,term in ipairs(terms) do
                if tokens[term] or tokens[term.."s"] or
                   (term=="rebirth" and tokens.rebirthing) then
                    local item=features[name]
                    item.counts[kind]=item.counts[kind]+1
                    item.status="candidate-needs-verification"
                    if #item.examples < 6 then
                        item.examples[#item.examples+1]={path=path:sub(1,220),class=class,kind=kind}
                    end
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
    Size = UDim2.new(1, -50, 0, 48),
    BackgroundColor3 = Color3.fromRGB(80, 80, 80),
    TextXAlignment = Enum.TextXAlignment.Left,
    TextTruncate = Enum.TextTruncate.AtEnd,
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
    Size = UDim2.fromOffset(360, 164),
    Position = UDim2.fromOffset(12, 164),
    BackgroundColor3 = Color3.fromRGB(35, 35, 35),
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 12,
    Font = Enum.Font.Code,
    MultiLine = true,
    TextWrapped = false,
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
    local firstOk, first = pcall(function() return HttpService:JSONDecode(parts[1]) end)
    if not firstOk or type(first)~="table" then
        status.Text = "Upload blocked: malformed first part"
        return
    end
    local scanId = first.scanId
    local partCount = #parts
    -- Reject mismatched parts before any upload; the receiver requires
    -- consistent scan identity, ordering and total count.
    for i, body in ipairs(parts) do
        local ok, item = pcall(function() return HttpService:JSONDecode(body) end)
        if not ok or type(item)~="table" or item.scanId~=scanId
            or item.partIndex~=i or item.partCount~=partCount
            or item.placeId~=game.PlaceId then
            status.Text="Upload blocked: inconsistent part "..tostring(i)
            return
        end
    end
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
                        status.Text = "Receiver ACK " .. succeeded .. "/" .. partCount .. " parts"
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
            status.Text = "ACK " .. succeeded .. "/" .. partCount .. ": " .. failed .. "; retry SEND JSON"
        elseif succeeded == partCount then
            status.Text = "Upload acknowledged: " .. succeeded .. "/" .. partCount
                .. " parts in " .. tostring(elapsed) .. "s; verify receiver integrity separately"
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
        if chunkBytes + entryBytes > 96500 and #chunk > 0 then
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
    -- Metadata and interaction history may each exceed one receiver part.
    -- Export diagnostics in bounded, independently sized parts; never
    -- attach the complete history to the object-bearing first part.
    local limit = math.min(MAX_PART_BYTES, 140000)
    local diagnostics = report.interactionDiagnostics or {}
    local history = diagnostics.recentInteractions or {}
    local summary = {}
    for k,v in pairs(diagnostics) do
        if k~="recentInteractions" then summary[k]=v end
    end
    summary.recentInteractions={}
    summary.historyExportMode="separate-bounded-parts"
    summary.historyTotal=#history
    local function makePart(items,index,total,meta,historyBatch,historyStart)
        return {
            version=report.version,placeId=report.placeId,gameId=report.gameId,
            placeVersion=report.placeVersion,inspectedAt=report.inspectedAt,
            gameName=report.gameName,scanId=scanId,partIndex=index,partCount=total,
            counts=meta and report.counts or nil,
            groups=meta and report.groups or nil,
            scanStats=meta and report.scanStats or nil,
            sessionId=report.sessionId,snapshotId=report.snapshotId,
            parentSnapshotId=report.parentSnapshotId,
            featureEvidence=meta and report.featureEvidence or nil,
            featureReadiness=meta and report.featureReadiness or nil,
            interactionDiagnostics=meta and summary or nil,
            featureSnapshotDelta=meta and report.featureSnapshotDelta or nil,
            automationDiagnostics=meta and report.automationDiagnostics or nil,
            diagnostics=meta and report.diagnostics or nil,
            interactionHistoryChunk=historyBatch,
            interactionHistoryStart=historyStart,
            objects=items
        }
    end
    -- Incremental history sizing: avoid repeatedly encoding a growing batch.
    -- Exact-size validation below still splits any unexpectedly large part.
    local historyBatches={}
    local currentHistory={}
    local currentStart=1
    local historyBytes=0
    for i,item in ipairs(history) do
        local encoded=encodeStage("history-item-"..i,item)
        local estimate=#encoded+2
        if historyBytes+estimate>limit-1500 and #currentHistory>0 then
            historyBatches[#historyBatches+1]={items=currentHistory,start=currentStart}
            currentHistory={}
            currentStart=i
            historyBytes=0
        end
        currentHistory[#currentHistory+1]=item
        historyBytes=historyBytes+estimate
    end
    if #currentHistory>0 then
        historyBatches[#historyBatches+1]={items=currentHistory,start=currentStart}
    end
    -- Reserve a dedicated metadata part, so object payloads cannot force
    -- large shared diagnostics into an oversized first object part.
    local payloads={{items={},meta=true}}
    for _,batch in ipairs(historyBatches) do
        payloads[#payloads+1]={items={},history=batch.items,start=batch.start}
    end
    for _,items in ipairs(chunks) do payloads[#payloads+1]={items=items} end
    local changed=true
    while changed do
        changed=false
        local total=#payloads
        for i=1,total do
            local entry=payloads[i]
            local body=encodeStage("size-check-"..i,
                makePart(entry.items,i,total,entry.meta,entry.history,entry.start))
            if #body>limit then
                if entry.meta then
                    error("Shared scan summary exceeds receiver limit without interaction history")
                elseif entry.history then
                    if #entry.history<=1 then
                        error("Single history event exceeds receiver limit")
                    end
                    local midpoint=math.floor(#entry.history/2)
                    local left,right={},{}
                    for j,v in ipairs(entry.history) do
                        if j<=midpoint then left[#left+1]=v else right[#right+1]=v end
                    end
                    payloads[i]={items={},history=left,start=entry.start}
                    table.insert(payloads,i+1,{items={},history=right,start=entry.start+midpoint})
                else
                    if #entry.items<=1 then
                        error("Single object exceeds receiver limit")
                    end
                    local midpoint=math.floor(#entry.items/2)
                    local left,right={},{}
                    for j,v in ipairs(entry.items) do
                        if j<=midpoint then left[#left+1]=v else right[#right+1]=v end
                    end
                    payloads[i]={items=left}
                    table.insert(payloads,i+1,{items=right})
                end
                changed=true
                break
            end
        end
    end
    local parts={}
    for i,entry in ipairs(payloads) do
        local body=encodeStage("part-"..i,
            makePart(entry.items,i,#payloads,entry.meta,entry.history,entry.start))
        if #body>limit then error("Unexpected oversized part "..i) end
        parts[#parts+1]=body
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
    local entry = {path = path:sub(1, 400), class = obj.ClassName, category = category, scanOrdinal = nextInstanceId}
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
local MENU_FEATURE_HINTS = {
    itemsnewmenu="inventory", petcraftinggui="pets", fusepets="pets",
    rebirthnewmenu="rebirth", questsgui="quests", questsnewmenu="quests",
    freegiftsgui="rewards", freegiftsnewmenu="rewards",
    shopnewmenu="shops", bossnewmenu="bosses", teleportnewmenu="travel",
    travelareanewmenu="travel", petsrightbase="pets", petsbutton="pets",
    confirmSellNewMenu="inventory", confirmsellnewmenu="inventory",
    fortunewheelmenugui="rewards", fortuneothermenusgui="rewards",
    buyspinsmenu="shops"
}
local function relevantStateEvidence(feature, changes)
    if not feature then return nil end
    if feature == "rebirth" then
        local rebirthIncreased, strengthReset = false, false
        for _, change in ipairs(changes) do
            local key = change.key:lower()
            if key:find("rebirth",1,true) and type(change.before)=="number"
                and type(change.after)=="number" and change.after > change.before then
                rebirthIncreased = true
            end
            if key:find("strength",1,true) and type(change.before)=="number"
                and type(change.after)=="number" and change.after < change.before then
                strengthReset = true
            end
        end
        if rebirthIncreased then
            return {rule="rebirth-counter-increased", corroboratingStrengthReset=strengthReset,
                status="client-state-consistent", serverVerified=false}
        end
    elseif feature == "training" then
        for _, change in ipairs(changes) do
            if change.key:lower():find("strength",1,true)
                and type(change.before)=="number" and type(change.after)=="number"
                and change.after > change.before then
                return {rule="strength-increased", status="client-state-consistent", serverVerified=false}
            end
        end
    end
    return nil
end
local function actionKind(name)
    local n=name:lower()
    if n:find("unequipall",1,true) then return "unequip-all" end
    if n:find("unequip",1,true) then return "unequip" end
    if n:find("sell",1,true) then return "sell" end
    if n:find("equip",1,true) then return "equip" end
    if n:find("craft",1,true) or n:find("fuse",1,true) then return "craft" end
    if n:find("claim",1,true) then return "claim" end
    if n:find("buy",1,true) or n:find("purchase",1,true) then return "purchase" end
    if n:find("rebirth",1,true) then return "rebirth" end
    if n:find("travel",1,true) or n:find("teleport",1,true) then return "travel" end
    return nil
end
local function workflowContext(obj, feature)
    local names, node={},obj
    for i=1,9 do
        if not node then break end
        names[#names+1]=node.Name:sub(1,60)
        node=node.Parent
    end
    return {feature=feature, control=obj.Name:sub(1,80), ancestry=names,
        kind=actionKind(obj.Name), clientOnly=true}
end
local function classifyInteraction(obj)
    -- Specific local menu context wins over generic controls like EquipButton.
    local node=obj.Parent
    local depth=0
    while node and depth < 10 do
        local lower=node.Name:lower()
        if lower=="petsrightbase" or lower=="petcraftinggui" or lower=="fusepets" then
            workflowStats.classifiedByContext=workflowStats.classifiedByContext+1
            return "pets",1,"specific-menu-context"
        end
        if lower=="travelareanewmenu" then return "travel",1,"specific-menu-context" end
        if lower=="confirmsellnewmenu" then
            return nil,0,"confirmation-awaiting-link"
        end
        node=node.Parent
        depth=depth+1
    end
    local feature,count=featureForName(obj.Name)
    if feature then return feature,count,"control-name" end
    node=obj.Parent
    depth=0
    while node and depth<8 do
        local hint=MENU_FEATURE_HINTS[node.Name:lower()]
        if hint then return hint,1,"menu-context-hint" end
        local candidate,matches=featureForName(node.Name)
        if candidate then return candidate,matches,"ancestor-name" end
        if node:IsA("ScreenGui") then break end
        node=node.Parent
        depth=depth+1
    end
    local lower=obj.Name:lower()
    if lower=="items" then return "inventory",1,"known-navigation-control" end
    if lower=="claim" then return "rewards",1,"known-navigation-control" end
    return nil,0,"unattributed"
end
local function linkWorkflow(obj, feature, sequence)
    local name=obj.Name:lower()
    local isYes=name=="yesbutton" or name=="confirmbutton" or name=="confimbutton"
        or name=="confirm" or name=="acceptbutton" or name=="okbutton"
    local isNo=name=="nobutton" or name=="cancelbutton" or name=="cancel"
        or name=="declinebutton"
    local now=os.clock()
    for i=#pendingActions,1,-1 do
        if now-pendingActions[i].clock > 15 then
            table.remove(pendingActions,i)
            workflowStats.expired=workflowStats.expired+1
        end
    end
    local node=obj
    local contextFeature=feature
    local dialog=false
    local menuName=nil
    for i=1,9 do
        if not node then break end
        local n=node.Name:lower()
        if n:find("confirm",1,true) or n:find("confim",1,true)
            or n:find("choice",1,true) or n=="travelareanewmenu"
            or n=="rebirthnewmenu" then
            dialog=true
            menuName=node.Name
        end
        node=node.Parent
    end
    if (isYes or isNo) and dialog then
        local bestIndex=nil
        for i=#pendingActions,1,-1 do
            local pending=pendingActions[i]
            if (contextFeature and pending.feature==contextFeature)
                or (menuName and menuName:lower():find(pending.kind,1,true))
                or (pending.kind=="sell" and menuName and menuName:lower():find("sell",1,true)) then
                bestIndex=i
                break
            end
        end
        if bestIndex then
            local previous=table.remove(pendingActions,bestIndex)
            if isNo then workflowStats.cancelled=workflowStats.cancelled+1
            else workflowStats.linkedConfirmations=workflowStats.linkedConfirmations+1 end
            return {phase=isNo and "cancelled" or "confirmed",linkedSequence=previous.sequence,
                inferredFeature=previous.feature,action=previous.kind,context=previous.context,
                dialog=menuName,confidence="context-and-time-heuristic",verified=false}
        end
        if contextFeature=="travel" and isYes then
            return {phase="travel-confirmed-unlinked",action="travel",
                dialog=menuName,confidence="menu-context-heuristic",verified=false}
        end
        return {phase=isNo and "unlinked-cancel" or "unlinked-confirm",
            dialog=menuName,confidence="no-matching-initiator",verified=false}
    end
    if isYes and feature=="travel" then
        return {phase="travel-confirmed",action="travel",confidence="menu-context-heuristic",verified=false}
    end
    local kind=actionKind(obj.Name)
    if kind then
        local context=workflowContext(obj,feature)
        pendingActions[#pendingActions+1]={clock=now,sequence=sequence,feature=feature,kind=kind,context=context}
        if #pendingActions>MAX_PENDING_ACTIONS then table.remove(pendingActions,1) end
        return {phase="initiated",action=kind,confidence="control-name-heuristic",verified=false}
    end
    return nil
end
local function relevantActionEvidence(feature, workflow, changes)
    local kind=workflow and workflow.action
    if not kind and feature=="rebirth" then kind="rebirth" end
    local signals={}
    for _,change in ipairs(changes) do
        local key=change.key:lower()
        if key:find("strength",1,true) then
            signals[#signals+1]="strength-change"
        elseif key:find("rebirth",1,true) then
            signals[#signals+1]="rebirth-change"
        elseif key:find("pet",1,true) or key:find("equip",1,true)
            or key:find("inventory",1,true) then
            signals[#signals+1]="inventory-related-value-change"
        elseif key:find("coin",1,true) or key:find("gem",1,true)
            or key:find("currency",1,true) then
            signals[#signals+1]="currency-related-value-change"
        elseif key:find("quest",1,true) or key:find("reward",1,true) then
            signals[#signals+1]="quest-or-reward-related-value-change"
        end
    end
    local corroborated=false
    if kind=="rebirth" then
        for _,change in ipairs(changes) do
            if change.key:lower():find("rebirth",1,true) and
                type(change.before)=="number" and type(change.after)=="number"
                and change.after>change.before then corroborated=true end
        end
    elseif kind=="equip" or kind=="unequip" or kind=="unequip-all" or kind=="sell" or kind=="craft" then
        for _,signal in ipairs(signals) do
            if signal=="inventory-related-value-change" then corroborated=true end
        end
    elseif kind=="purchase" or kind=="claim" then
        for _,signal in ipairs(signals) do
            if signal=="currency-related-value-change" or signal=="quest-or-reward-related-value-change"
                or signal=="inventory-related-value-change" then corroborated=true end
        end
    end
    return {action=kind,signals=signals,clientStateCorroborated=corroborated,
        serverVerified=false,causalVerification=false,confidence="temporal-observation"}
end

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
    observerStats.listenersAttached = observerStats.listenersAttached + 1
    local connection = signal:Connect(function()
        if not alive or not interactionObserveEnabled then return end
        interactionEventCount = interactionEventCount + 1
        autoEvidenceLastInteraction = os.clock()
        observerStats.callbacksFired = observerStats.callbacksFired + 1
        observerStats.lastCallbackAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
        observerStats.lastEventPath = path:sub(1,180)
        local feature, matchCount, attributionSource = classifyInteraction(obj)
        if feature then
            attributedInteractionCount = attributedInteractionCount + 1
        else
            unattributedInteractionCount = unattributedInteractionCount + 1
        end
        local workflow = linkWorkflow(obj, feature, observationSequence + 1)
        if workflow and workflow.inferredFeature and not feature then
            feature=workflow.inferredFeature
            attributionSource="linked-confirmation-heuristic"
            unattributedInteractionCount=unattributedInteractionCount-1
            attributedInteractionCount=attributedInteractionCount+1
        end
        local historyItem = {
            path=path:sub(1,400), featureCandidate=feature,
            attribution=attributionSource, controlType=controlType,
            observedAt=observerStats.lastCallbackAt, sequence=observationSequence + 1,
            stateChangeCount=0, guiContext=interactionGuiContext(obj), workflow=workflow,
            evidenceLevel="interaction-observed", outcomeVerified=false
        }
        interactionHistory[#interactionHistory+1] = historyItem
        if #interactionHistory > MAX_INTERACTION_HISTORY then table.remove(interactionHistory, 1) end
        local before = safeInteractionState()
        local beforeGui = safeNearbyGuiState(obj)
        local inventoryRelevant=feature=="inventory" or feature=="pets" or
            (workflow and (workflow.action=="equip" or workflow.action=="unequip" or
            workflow.action=="unequip-all" or workflow.action=="sell"))
        local inventoryAction=workflow and workflow.action or nil
        if not inventoryAction then
            local controlName=obj.Name:lower()
            local parentName=obj.Parent and obj.Parent.Name:lower() or ""
            if controlName:find("nextbutton",1,true) or controlName:find("previousbutton",1,true)
                or controlName:find("pagebutton",1,true)
                or parentName:find("nextbutton",1,true)
                or parentName:find("previousbutton",1,true)
                or parentName:find("pagebutton",1,true) then
                inventoryAction="pagination"
            elseif controlName:match("^slot%d+") or parentName:match("^slot%d+") then
                inventoryAction="selection"
            end
        end
        local inventorySummaryBefore=inventoryRelevant and safeInventorySummary() or nil
        local beforePosition = nil
        local rootPart = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
        if rootPart then beforePosition=rootPart.Position end
        if feature then
            local item = featureInteractions[feature] or {count=0,stateChanges=0}
            item.count = item.count + 1
            featureInteractions[feature] = item
        end
        observationSequence = observationSequence + 1
        changeCount = changeCount + 1
        changeQueue[#changeQueue + 1] = {
            path = path:sub(1,400), class = obj.ClassName,
            featureCandidate = feature, featureMatchCount = matchCount,
            attribution = attributionSource,
            category = "user-interaction", controlType = controlType,
            action = "user-activated", observedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            evidence = "manual-user-interaction", sessionId = sessionId, snapshotId = snapshotId, sequence = observationSequence
        }
        local interactionSequence = observationSequence
        local transactionId=(workflow and workflow.linkedSequence) or historyItem.sequence
        historyItem.transactionId=transactionId
        local seenStateKeys={}
        local seenGuiKeys={}
        for _,delaySeconds in ipairs(OBSERVATION_WINDOWS) do
            task.delay(delaySeconds, function()
                if not alive then return end
                local ok,err=pcall(function()
                    local after=safeInteractionState()
                    local guiChanges=compareNearbyGuiState(beforeGui,safeNearbyGuiState(obj))
                    local changes={}
                    for key,value in pairs(before) do
                        if after[key]~=nil and after[key]~=value and #changes<MAX_STATE_CHANGES then
                            changes[#changes+1]={key=key,before=value,after=after[key]}
                        end
                    end
                    for key,value in pairs(after) do
                        if before[key]==nil and #changes<MAX_STATE_CHANGES then
                            changes[#changes+1]={key=key,transition="added",after=value}
                        end
                    end
                    for key,value in pairs(before) do
                        if after[key]==nil and #changes<MAX_STATE_CHANGES then
                            changes[#changes+1]={key=key,transition="removed",before=value}
                        end
                    end
                    local distance=nil
                    local currentRoot=player.Character and player.Character:FindFirstChild("HumanoidRootPart")
                    if beforePosition and currentRoot then
                        distance=(currentRoot.Position-beforePosition).Magnitude
                        distance=math.floor(distance*10+0.5)/10
                    end
                    local evidence=relevantActionEvidence(feature,workflow,changes)
                    local freshState={}
                    for _,change in ipairs(changes) do
                        local identity=change.key.."|"..tostring(change.before).."|"..tostring(change.after).."|"..tostring(change.transition)
                        if not seenStateKeys[identity] then
                            seenStateKeys[identity]=true
                            freshState[#freshState+1]=change
                        end
                    end
                    local freshGui={}
                    for _,change in ipairs(guiChanges) do
                        local identity=change.path.."|"..tostring(change.beforeVisible).."|"..tostring(change.afterVisible).."|"..tostring(change.transition)
                        if not seenGuiKeys[identity] then
                            seenGuiKeys[identity]=true
                            freshGui[#freshGui+1]=change
                        end
                    end
                    -- Deduplicate across related initiation/confirmation interactions.
                    -- Retain per-interaction evidence, but count a shared transition once.
                    local transactionFresh={}
                    for _,change in ipairs(freshState) do
                        local identity=tostring(transactionId).."|"..change.key.."|"..
                            tostring(change.before).."|"..tostring(change.after).."|"..
                            tostring(change.transition)
                        if not transactionEvidenceSeen[identity] then
                            transactionEvidenceSeen[identity]=true
                            transactionEvidenceCount=transactionEvidenceCount+1
                            transactionFresh[#transactionFresh+1]=change
                        end
                    end
                    if transactionEvidenceCount>MAX_TRANSACTION_SIGNATURES then
                        transactionEvidenceSeen={}
                        transactionEvidenceCount=0
                    end
                    workflowStats.uniqueStateEvents=workflowStats.uniqueStateEvents+#transactionFresh
                    workflowStats.uniqueGuiEvents=workflowStats.uniqueGuiEvents+#freshGui
                    if feature=="travel" and distance and distance>100 and not historyItem.travelCandidate then
                        historyItem.travelCandidate=true
                        workflowStats.travelCandidates=workflowStats.travelCandidates+1
                    end
                    if feature=="rewards" and not historyItem.rewardClaimGuiCandidate then
                        for _,g in ipairs(guiChanges) do
                            if g.path:lower():find("claimed",1,true) and g.afterVisible==true then
                                historyItem.rewardClaimGuiCandidate=true
                                workflowStats.rewardClaimGuiCandidates=workflowStats.rewardClaimGuiCandidates+1
                                break
                            end
                        end
                    end
                    local window={seconds=delaySeconds,stateChanges=freshState,
                        stateChangeCount=#freshState,guiChanges=freshGui,
                        guiChangeCount=#freshGui,travelDistanceStuds=distance,
                        actionEvidence=evidence}
                    historyItem.observationWindows=historyItem.observationWindows or {}
                    historyItem.observationWindows[#historyItem.observationWindows+1]=window
                    if delaySeconds==3 and inventoryRelevant and inventorySummaryBefore then
                        local inventoryAfter=safeInventorySummary()
                        local guiEvidence=compareInventoryGuiSamples(
                            inventorySummaryBefore,inventoryAfter)
                        historyItem.inventoryObservationScope={
                            actionContext=inventoryAction,
                            guiEvidence=guiEvidence,
                            beforeCounts={slots=inventorySummaryBefore.guiSlots,
                                indicators=inventorySummaryBefore.guiEquippedIndicators},
                            afterCounts={slots=inventoryAfter.guiSlots,
                                indicators=inventoryAfter.guiEquippedIndicators},
                            sourceIsAuthoritative=false,
                            overlappingInteractionsPossible=true,
                            truncated=inventorySummaryBefore.truncated or inventoryAfter.truncated
                        }
                        historyItem.inventoryGuiCandidate=
                            inventoryAction~="pagination" and
                            (#guiEvidence.indicatorChanges>0 or #guiEvidence.slotChanges>0)
                        historyItem.inventoryPageChangeCandidate=
                            inventoryAction=="pagination" and #guiEvidence.slotChanges>0
                        historyItem.inventoryEvidenceKind=
                            (inventoryAction=="pagination" and
                                (#guiEvidence.slotChanges>0 or #guiEvidence.indicatorChanges>0))
                                and "page-visibility-ui-change"
                            or (#guiEvidence.indicatorChanges>0 and "equipped-indicator-ui-change")
                            or (#guiEvidence.slotChanges>0 and "slot-ui-change")
                            or "no-inventory-ui-change"
                        historyItem.inventoryOutcomeVerified=false
                    end
                    historyItem.guiStateChanges=historyItem.guiStateChanges or {}
                    for _,g in ipairs(freshGui) do historyItem.guiStateChanges[#historyItem.guiStateChanges+1]=g end
                    historyItem.guiStateChangeCount=#historyItem.guiStateChanges
                    historyItem.guiEvidenceStatus=#guiChanges>0 and "temporal-gui-transition-observed" or "none-observed"
                    workflowStats.guiTransitions=workflowStats.guiTransitions+#freshGui
                    workflowStats.multiWindowSamples=workflowStats.multiWindowSamples+1
                    if #transactionFresh>0 then
                        historyItem.evidenceLevel="temporal-state-change-observed"
                        historyItem.stateChangeCount=(historyItem.stateChangeCount or 0)+#transactionFresh
                        historyItem.stateChanges=historyItem.stateChanges or {}
                        for _,change in ipairs(transactionFresh) do historyItem.stateChanges[#historyItem.stateChanges+1]=change end
                        historyItem.featureStateEvidence=relevantStateEvidence(feature,transactionFresh)
                        observerStats.stateDeltaEvents=observerStats.stateDeltaEvents+1
                        if feature then
                            local item=featureInteractions[feature]
                            if item then item.stateChanges=item.stateChanges+1 end
                        end
                    end
                    if evidence.clientStateCorroborated and not historyItem.clientStateCorroborated then
                        historyItem.clientStateCorroborated=true
                        workflowStats.actionOutcomesCorroborated=workflowStats.actionOutcomesCorroborated+1
                    end
                    if #transactionFresh>0 or #freshGui>0 or (distance and distance>100 and feature=="travel") then
                        changeCount=changeCount+1
                        changeQueue[#changeQueue+1]={
                            path=path:sub(1,400),class=obj.ClassName,category="interaction-observation-window",
                            featureCandidate=feature,sequence=historyItem.sequence,
                            observationWindowSeconds=delaySeconds,changes=transactionFresh,
                            guiChanges=freshGui,travelDistanceStuds=distance,
                            actionEvidence=evidence,causalVerification=false,
                            sessionId=sessionId,snapshotId=snapshotId}
                    end
                end)
                if not ok then workflowStats.observationFailures=workflowStats.observationFailures+1 end
            end)
        end
    end)
    table.insert(watchConnections, connection)
end

local function sweepInteractionControls()
    observerStats.sweepCompleted = false
    observerStats.sweepStartedAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
    observerStats.lastSweepError = nil
    observerStats.sweepScanned = 0
    local gui = player:FindFirstChildOfClass("PlayerGui")
    if not gui then observerStats.lastSweepError = "PlayerGui unavailable"; return end
    local ok, descendants = pcall(function() return gui:GetDescendants() end)
    if not ok then observerStats.bindingErrors = observerStats.bindingErrors + 1; observerStats.lastSweepError = "GetDescendants failed"; return end
    for i, obj in ipairs(descendants) do
        if not alive then return end
        if obj:IsA("GuiButton") then
            local success = pcall(observeInteractionObject, obj, gui, "PlayerGui")
            if not success then observerStats.bindingErrors = observerStats.bindingErrors + 1 end
        end
        observerStats.sweepScanned = i
        if i % 400 == 0 then task.wait() end
    end
    observerStats.sweepCompleted = true
    observerStats.sweepFinishedAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
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
            featureReadiness = buildReadiness(buildFeatureEvidence(batch), interactionEventCount),
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
                if entry.category == "state-change" or entry.category == "user-interaction" or entry.category == "interaction-state-delta" then
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
    if interactionObserveEnabled then
        observerStats.activationCount = observerStats.activationCount + 1
        observerStats.lastEnabledAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
        task.spawn(function()
            local ok, err = pcall(sweepInteractionControls)
            if not ok then
                observerStats.bindingErrors = observerStats.bindingErrors + 1
                observerStats.lastSweepError = tostring(err):sub(1,250)
            end
        end)
    else
        observerStats.deactivationCount = observerStats.deactivationCount + 1
        observerStats.lastDisabledAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
        observerStats.lastDisabledReason = "manual-toggle"
    end
    interactionToggle.Text = interactionObserveEnabled
        and ("INTERACT: ON (" .. observerStats.activationCount .. ")")
        or ("INTERACT: OFF (" .. observerStats.activationCount .. ")")
    interactionToggle.BackgroundColor3 = interactionObserveEnabled
        and Color3.fromRGB(65, 105, 85) or Color3.fromRGB(85, 85, 105)
    status.Text = interactionObserveEnabled
        and "Observer ON; perform gameplay actions, then press SCAN for fresh evidence"
        or "Manual interaction observation paused"
end)

local function inspect(requestType)
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

    scanInvocationCount = scanInvocationCount + 1
    scanRequestType = requestType == "startup-baseline" and "startup-baseline" or (requestType == "auto-evidence" and "auto-evidence" or "manual")
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
            local stablePathCache = {}
            local function stablePath(obj, root, label)
                local cached = stablePathCache[obj]
                if cached then return cached end
                local pending = {}
                local current = obj
                while current and current ~= root do
                    local known = stablePathCache[current]
                    if known then
                        local path = known
                        for i = #pending, 1, -1 do
                            local node = pending[i]
                            path = path .. "." .. node.Name
                            stablePathCache[node] = path
                        end
                        return stablePathCache[obj]
                    end
                    pending[#pending + 1] = current
                    current = current.Parent
                end
                if current ~= root then return nil end
                local path = label
                for i = #pending, 1, -1 do
                    local node = pending[i]
                    path = path .. "." .. node.Name
                    stablePathCache[node] = path
                end
                return stablePathCache[obj]
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
            local nextInstanceId = 0
            for _, spec in ipairs(roots) do
                local rootStarted = os.clock()
                local yieldDeadline = os.clock() + SCAN_YIELD_BUDGET_SECONDS
                local root = spec.instance
                stablePathCache = {}
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
            report.featureReadiness = buildReadiness(report.featureEvidence, interactionEventCount)
            report.interactionDiagnostics = {
                scanRequestType=scanRequestType, scanInvocationCount=scanInvocationCount,
                observerReady=interactionObserveEnabled and observerStats.sweepCompleted,
                enabledAtScan=interactionObserveEnabled, listenersAttached=observerStats.listenersAttached,
                callbacksFired=observerStats.callbacksFired, stateDeltaEvents=observerStats.stateDeltaEvents,
                bindingErrors=observerStats.bindingErrors, sweepCompleted=observerStats.sweepCompleted,
                sweepScanned=observerStats.sweepScanned, lastEventPath=observerStats.lastEventPath,
                pendingObservationEvents=0, cumulativeChangeEvents=changeCount, totalInteractionEvents=interactionEventCount,
                attributedEvents=attributedInteractionCount, unattributedEvents=unattributedInteractionCount,
                recentInteractions=interactionHistory, interactionHistoryLimit=MAX_INTERACTION_HISTORY,
                workflowStats=workflowStats, pendingWorkflowCount=#pendingActions,
                verificationPolicy="read-only-client-corroboration-not-server-proof",
                transactionDeduplication="linked-workflow-sequence",
                inventoryDiscovery="candidate-first-gui-sampling-parent-aware-pagination",
                evidenceLevels={"interaction-observed","temporal-state-change-observed","gameplay-outcome-verified"},
                gameplayOutcomesVerified=0, stateSnapshotMaxValues=1000, observationWindowsSeconds=OBSERVATION_WINDOWS,
                stateChangeLimit=MAX_STATE_CHANGES,
                featureEvidenceRules={"rebirth-counter-increased","strength-increased"},
                contextualAttributionIsHeuristic=true, guiStateObservation="bounded-nearby-visibility-and-active-only",
                activationCount=observerStats.activationCount, deactivationCount=observerStats.deactivationCount,
                lastEnabledAt=observerStats.lastEnabledAt, lastDisabledAt=observerStats.lastDisabledAt,
                lastDisabledReason=observerStats.lastDisabledReason, lastCallbackAt=observerStats.lastCallbackAt,
                sweepStartedAt=observerStats.sweepStartedAt, sweepFinishedAt=observerStats.sweepFinishedAt,
                lastSweepError=observerStats.lastSweepError
            }
            report.featureSnapshotDelta = compareFeatureSnapshots(report.featureEvidence)
            report.automationDiagnostics = {
                enabled=AUTO_EVIDENCE_ENABLED, idleSeconds=AUTO_EVIDENCE_IDLE_SECONDS,
                cooldownSeconds=AUTO_EVIDENCE_COOLDOWN_SECONDS, maxAutomaticRescans=AUTO_EVIDENCE_MAX_RESCANS,
                automaticRescans=autoEvidenceRescans, lastFailure=autoEvidenceLastFailure,
                capturedInteractionCount=interactionEventCount,
                indexIntegrityWarning="Use receiver GET /reports/READ_KEY/SCAN_ID/integrity to verify object indexing",
                limitations={"Read-only client observation","No script source or server authority","No proof of replayable gameplay actions"}
            }
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
                featureReadiness = result.featureReadiness,
                interactionDiagnostics = result.interactionDiagnostics,
                automationDiagnostics = result.automationDiagnostics,
                featureSnapshotDelta = result.featureSnapshotDelta,
                placeId = result.placeId, inspectedAt = result.inspectedAt,
                objectCount = #result.objects, partCount = #parts,
                expectedParts = #parts, uploadedParts = 0,
                localPerformance = result.localPerformance,
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
                .. "\\nObserver callbacks: " .. tostring(observerStats.callbacksFired)
                .. "\\nObserver sweep: " .. (observerStats.sweepCompleted and "COMPLETE" or "NOT COMPLETE")
                .. "\\nObserver activations: " .. tostring(observerStats.activationCount)
                .. "\\nScan type: " .. scanRequestType
                .. "\\nObserver ready: " .. tostring(interactionObserveEnabled and observerStats.sweepCompleted)
                .. "\\nAUTO-SEND: " .. (autoSend and "ON" or "OFF")
            if autoSend and validEndpoint(endpoint) then transmit() end
        else
            status.Text = "JSON error: " .. tostring(resultData)
        end
        running = false
    end)
end

-- v6 automatic evidence collection: observe ordinary user gameplay without requiring
-- the user to perform a fresh manual scan after every interaction.
-- Bounded rescan budget avoids repeatedly uploading huge worlds.
local autoEvidenceToggle = Instance.new("TextButton")
autoEvidenceToggle.Name = "AutoEvidenceToggle"
autoEvidenceToggle.Size = UDim2.fromOffset(120, 26)
autoEvidenceToggle.Position = UDim2.fromOffset(380, 168)
autoEvidenceToggle.Text = "EVIDENCE: ON"
autoEvidenceToggle.TextSize = 10
autoEvidenceToggle.TextColor3 = Color3.fromRGB(245,245,245)
autoEvidenceToggle.BackgroundColor3 = Color3.fromRGB(50,105,85)
autoEvidenceToggle.Parent = panel
-- Keep evidence control below INTERACT and outside the report viewport.
autoEvidenceToggle.ZIndex = 4
local evidenceHint = create("TextLabel", {
    Name = "EvidenceHint",
    Text = "After interaction: up to 4 full rescans",
    Position = UDim2.fromOffset(379, 201),
    Size = UDim2.fromOffset(121, 55),
    BackgroundTransparency = 1,
    TextColor3 = Color3.fromRGB(205, 215, 220),
    TextSize = 10,
    TextWrapped = true,
    TextYAlignment = Enum.TextYAlignment.Top
}, panel)
local uploadHint = create("TextLabel", {
    Name = "UploadHint",
    Text = "Receiver ACK is not full integrity proof.",
    Position = UDim2.fromOffset(379, 263),
    Size = UDim2.fromOffset(121, 65),
    BackgroundTransparency = 1,
    TextColor3 = Color3.fromRGB(205, 215, 220),
    TextSize = 10,
    TextWrapped = true,
    TextYAlignment = Enum.TextYAlignment.Top
}, panel)

autoEvidenceToggle.MouseButton1Click:Connect(function()
    AUTO_EVIDENCE_ENABLED = not AUTO_EVIDENCE_ENABLED
    autoEvidenceToggle.Text = AUTO_EVIDENCE_ENABLED and "EVIDENCE: ON" or "EVIDENCE: OFF"
    autoEvidenceToggle.BackgroundColor3 = AUTO_EVIDENCE_ENABLED
        and Color3.fromRGB(50,105,85) or Color3.fromRGB(85,85,105)
    status.Text = AUTO_EVIDENCE_ENABLED and "Automatic evidence enabled" or "Automatic evidence paused"
end)

-- Existing observer already captures pre/post state and GUI transitions. This
-- scheduler consolidates those records into full reports after activity settles.
task.spawn(function()
    while alive do
        task.wait(3)
        if alive and AUTO_EVIDENCE_ENABLED and interactionObserveEnabled
            and observerStats.sweepCompleted and interactionEventCount > autoEvidenceLastSequence
            and autoEvidenceLastInteraction > 0
            and os.clock()-autoEvidenceLastInteraction >= AUTO_EVIDENCE_IDLE_SECONDS
            and os.clock()-autoEvidenceLastScan >= AUTO_EVIDENCE_COOLDOWN_SECONDS
            and autoEvidenceRescans < AUTO_EVIDENCE_MAX_RESCANS
            and not running and not uploading then
            local allSent = true
            if pendingParts then
                for i=1,#pendingParts do
                    if not pendingAcknowledged[i] then allSent=false break end
                end
            end
            if allSent then
                autoEvidenceLastSequence=interactionEventCount
                autoEvidenceLastScan=os.clock()
                autoEvidenceRescans=autoEvidenceRescans+1
                evidenceHint.Text = "Auto rescans: " .. autoEvidenceRescans .. "/" .. AUTO_EVIDENCE_MAX_RESCANS
                inspect("auto-evidence")
            else
                autoEvidenceLastFailure="Previous scan parts not acknowledged"
            end
        end
    end
end)
scan.MouseButton1Click:Connect(function() inspect("manual") end)

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
-- Automatically attach passive listeners; users do not need to toggle INTERACT manually.
observerStats.activationCount = observerStats.activationCount + 1
observerStats.lastEnabledAt = os.date('!%Y-%m-%dT%H:%M:%SZ')
interactionToggle.Text = 'INTERACT: ON (AUTO)'
task.spawn(function()
 local ok,err=pcall(sweepInteractionControls)
 if not ok then observerStats.bindingErrors=observerStats.bindingErrors+1; observerStats.lastSweepError=tostring(err):sub(1,250) end
end)
-- Startup scan is discovery-only; after enabling interaction recording, run SCAN again.
inspect("startup-baseline")