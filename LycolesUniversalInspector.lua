
-- Lycoles Universal Inspector v30.6.33
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
local VERSION = "30.6.33"

local endpoint = ""
local autoSend = true
local last = nil
local pendingParts = nil
local pendingManifest = nil
local MAX_PART_BYTES = 105000
local running = false
local uploading = false
local uploadGeneration = 0
local pendingAcknowledged = {}
local uploadState = {
    attempted=false,status="not-attempted",acknowledgedParts=0,
    expectedParts=0,lastError=nil
}
local function uploadAttemptStage()
    if uploadState.status=="configuration-error" then
        return uploadState.attempted and "attempted-previously-currently-blocked"
            or "blocked-before-attempt"
    end
    if uploadState.status=="cancelled" then
        return uploadState.attempted and "attempted-cancelled" or "cancelled-before-attempt"
    end
    if uploadState.attempted then return "attempted" end
    return "not-attempted"
end
local function receiverReportStatus()
    if uploadState.expectedParts>0
        and uploadState.acknowledgedParts==uploadState.expectedParts then
        return "acknowledged-awaiting-integrity"
    end
    if uploadState.status=="uploading" then return "upload-in-progress" end
    if uploadState.status=="cancelled" and uploadState.acknowledgedParts==0 then
        return "upload-cancelled"
    end
    if uploadState.acknowledgedParts>0 then return "partially-acknowledged" end
    if uploadState.status=="failed" or uploadState.status=="incomplete" then
        return "upload-incomplete"
    end
    if uploadState.status=="configuration-error" then return "configuration-blocked" end
    return "unavailable"
end

local refreshLocalManifest = nil
local function uploadSnapshot(phase)
    local digests = {}
    for partIndex,ack in pairs(pendingAcknowledged) do
        if type(partIndex)=="number" and type(ack)=="table"
            and type(ack.sha256)=="string" and ack.sha256:match("^[a-f0-9]+$")
            and #ack.sha256==64 then
            digests[#digests+1]={partIndex=partIndex,sha256=ack.sha256}
        end
    end
    table.sort(digests,function(a,b) return a.partIndex < b.partIndex end)
    return {
        reportGenerated = pendingParts ~= nil or uploadState.expectedParts > 0,
        manifestSnapshotPhase = phase,
        uploadAttempted = uploadState.attempted,
        uploadAttemptStatus = uploadAttemptStage(),
        uploadStatus = uploadState.status,
        receiverReportStatus = receiverReportStatus(),
        downstreamAvailabilityStatus = "not-validated",
        acknowledgedParts = uploadState.acknowledgedParts,
        expectedParts = uploadState.expectedParts,
        acknowledgedPartDigests = digests,
        acknowledgedDigestParts = #digests,
        lastError = uploadState.lastError,
        receiverIntegrityVerified = false,
        downstreamReportAvailable = false,
        note = "Receiver acknowledgements require separate integrity verification before downstream use"
    }
end
local MAX_UPLOAD_ATTEMPTS = 3
local MAX_CONCURRENT_UPLOADS = 1
local SCAN_YIELD_BUDGET_SECONDS = 0.012
local UPLOAD_RETRY_DELAYS = {1, 3, 6}
local alive = true
local watchEnabled = true
local watchConnections = {}
local watchQueue = {}
local watchCount = 0
local watchBusy = false
local lastGameName = nil
local ROOT_LABELS = {"ReplicatedStorage", "ReplicatedFirst", "Workspace", "PlayerGui", "LocalPlayer", "Character", "Lighting", "Teams", "SoundService"}
local QUICK_ROOT_LABELS = {"ReplicatedStorage", "Workspace", "PlayerGui", "LocalPlayer", "Character"}

local WATCH_INTERVAL = 30
local watchSeen = {}
local watchSkippedCharacters = 0
local watchUploaded = 0
local changeQueue = {}
local changeCount = 0
local pendingObservationEvents = 0
local observed = setmetatable({}, {__mode = "k"})
local stateSnapshotCandidates = {}
local stateSnapshotCandidateSeen = setmetatable({}, {__mode = "k"})
local MAX_STATE_SNAPSHOT_CANDIDATES = 1000
local changeUploaded = 0
local WATCH_BATCH = 1500
local interactionObserveEnabled = true
local AUTO_EVIDENCE_ENABLED = true
local OBSERVATION_IDLE_OPTIONS = {8, 12, 20, 30}
local observationIdleIndex = 2
local SCAN_PROFILES = {
    full = {
        label = "FULL", scanMode = "universal-snapshot-v4.1", rootLabels = ROOT_LABELS,
        requiredRoots = {ReplicatedStorage=true, Workspace=true, PlayerGui=true, LocalPlayer=true},
        maxAutomaticRescans = 4, defaultObservationSeconds = 12, quickTargeted = false,
        recordingPolicy = "full-client-visible-root-inventory"
    },
    quick = {
        label = "QUICK", scanMode = "quick-targeted-snapshot-v1", rootLabels = QUICK_ROOT_LABELS,
        requiredRoots = {ReplicatedStorage=true, Workspace=true, PlayerGui=true, LocalPlayer=true},
        maxAutomaticRescans = 1, defaultObservationSeconds = 8, quickTargeted = true,
        recordingPolicy = "targeted-client-visible-evidence-not-full-inventory"
    }
}
local activeScanProfileId = "full"
local AUTO_EVIDENCE_IDLE_SECONDS = OBSERVATION_IDLE_OPTIONS[observationIdleIndex]
local AUTO_EVIDENCE_COOLDOWN_SECONDS = 45
local AUTO_EVIDENCE_MAX_RESCANS = SCAN_PROFILES[activeScanProfileId].maxAutomaticRescans
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
local pendingGuiReveals = {}
local MAX_PENDING_GUI_REVEALS = 100
local GUI_REVEAL_FOLLOWUP_SECONDS = 15
local FOLLOWUP_LINK_MAX_AGE_SECONDS = 6
local FOLLOWUP_LINK_MIN_CONTEXT_OVERLAP = 3
local workflowStats = {linkedConfirmations=0, linkedFollowups=0, cancelled=0, expired=0, completedCandidates=0, backfilledOutcomeCandidates=0, guiTransitions=0, observationFailures=0, classifiedByContext=0, actionOutcomesCorroborated=0, multiWindowSamples=0, uniqueStateEvents=0, uniqueGuiEvents=0, travelCandidates=0, rewardClaimGuiCandidates=0, guiRevealCandidates=0, guiRevealFollowups=0, guiRevealCandidatesExpired=0, guiRevealCandidatesDropped=0}
local sessionId = HttpService:GenerateGUID(false)
local sessionStartedClock = os.clock()
local WORKFLOW_RECORDING_SECONDS = 60
local MAX_WORKFLOW_RECORDING_EVENTS = 8
local workflowRecording = {active=false,id=nil,startedClock=nil,startedElapsed=nil,eventCount=0}
local workflowRecordingStats = {started=0,stopped=0,durationExpired=0,capacityReached=0,
    recordedEvents=0,lastRecordedEventCount=0,lastStopReason=nil}
local refreshWorkflowRecorder = nil
local refreshEvidenceControls = nil
local scanGeneration = 0

local function stopWorkflowRecording(reason)
    if not workflowRecording.active then return end
    workflowRecording.active=false
    workflowRecording.id=nil
    workflowRecording.startedClock=nil
    workflowRecording.startedElapsed=nil
    workflowRecordingStats.lastRecordedEventCount=workflowRecording.eventCount
    workflowRecording.eventCount=0
    workflowRecordingStats.stopped=workflowRecordingStats.stopped+1
    workflowRecordingStats.lastStopReason=reason
    if reason=="duration-limit" then
        workflowRecordingStats.durationExpired=workflowRecordingStats.durationExpired+1
    elseif reason=="event-limit" then
        workflowRecordingStats.capacityReached=workflowRecordingStats.capacityReached+1
    end
    if refreshWorkflowRecorder then refreshWorkflowRecorder(reason) end
end
local function startWorkflowRecording()
    if workflowRecording.active then return false end
    local startedClock=os.clock()
    workflowRecording.active=true
    workflowRecording.id="user-recorded-"..HttpService:GenerateGUID(false)
    workflowRecording.startedClock=startedClock
    workflowRecording.startedElapsed=math.floor((startedClock-sessionStartedClock)*1000+0.5)/1000
    workflowRecording.eventCount=0
    workflowRecordingStats.started=workflowRecordingStats.started+1
    local recordingId=workflowRecording.id
    task.delay(WORKFLOW_RECORDING_SECONDS,function()
        if alive and workflowRecording.active and workflowRecording.id==recordingId then
            stopWorkflowRecording("duration-limit")
        end
    end)
    if refreshWorkflowRecorder then refreshWorkflowRecorder("started") end
    return true
end
local function recordWorkflowInteraction(activationClock,sessionElapsedSeconds)
    if not workflowRecording.active then return nil end
    if activationClock-workflowRecording.startedClock>WORKFLOW_RECORDING_SECONDS then
        stopWorkflowRecording("duration-limit")
        return nil
    end
    workflowRecording.eventCount=workflowRecording.eventCount+1
    workflowRecordingStats.recordedEvents=workflowRecordingStats.recordedEvents+1
    local result={recordingId=workflowRecording.id,order=workflowRecording.eventCount,
        startedElapsedSeconds=workflowRecording.startedElapsed,
        maxDurationSeconds=WORKFLOW_RECORDING_SECONDS,
        maxEvents=MAX_WORKFLOW_RECORDING_EVENTS,
        linkageSource="explicit-user-armed-recording",explicitUserArmed=true,
        establishesOrdering=true,causalityProven=false,runtimeVerified=false,gameplayVerified=false}
    if workflowRecording.eventCount>=MAX_WORKFLOW_RECORDING_EVENTS then
        stopWorkflowRecording("event-limit")
    elseif refreshWorkflowRecorder then
        refreshWorkflowRecorder("event-recorded")
    end
    return result
end

local scanInvocationCount = 0
local scanRequestType = "startup-baseline"
local observerStats = {listenersAttached=0, callbacksFired=0, stateDeltaEvents=0, bindingErrors=0, sweepCompleted=false, sweepScanned=0, lastEventPath=nil, activationCount=0, deactivationCount=0, lastEnabledAt=nil,lastDisabledAt=nil,lastDisabledReason=nil,lastSweepError=nil,sweepStartedAt=nil,sweepFinishedAt=nil,lastCallbackAt=nil,preActivationListenersAttached=0,preActivationCaptures=0,preActivationBaselinesUsed=0,callbackBaselinesUsed=0,stalePreActivationCaptures=0,preActivationCaptureFailures=0}
local snapshotId = nil
local observationSequence = 0
-- Feature candidates are based on the final object name, not arbitrary ancestor
-- paths. This prevents 'LiveRequest' being classified as a quest.
local FEATURE_TERMS = {
 training={"training","gym","strength","agility","treadmill"},
 progression={"progression","bubble","capacity","blow","farm"},
 rebirth={"rebirth"}, pets={"pet","hatch","egg"},
 shops={"shop","purchase","store","sell","upgrade"}, travel={"teleport","portal"},
 bosses={"boss","arena"}, quests={"quest","mission"},
 combat={"combat","attack","damage","weapon","gun","ammo","reload","shoot"}, inventory={"inventory","equip"},
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

local function guiControlSnapshot(obj)
    local text,interactable="",nil
    pcall(function() text=obj.Text end)
    pcall(function() interactable=obj.Interactable end)
    local ancestorVisible,screenEnabled,withinScrollingBounds=true,true,true
    local current=obj.Parent
    while current do
        if current:IsA("GuiObject") then
            if not current.Visible then ancestorVisible=false end
            if current:IsA("ScrollingFrame") then
                local targetPosition,targetSize=obj.AbsolutePosition,obj.AbsoluteSize
                local framePosition,frameSize=current.AbsolutePosition,current.AbsoluteSize
                local intersects=targetPosition.X+targetSize.X>framePosition.X
                    and targetPosition.Y+targetSize.Y>framePosition.Y
                    and targetPosition.X<framePosition.X+frameSize.X
                    and targetPosition.Y<framePosition.Y+frameSize.Y
                if not intersects then withinScrollingBounds=false end
            end
        elseif current:IsA("ScreenGui") and not current.Enabled then
            screenEnabled=false
        end
        if current:IsA("PlayerGui") then break end
        current=current.Parent
    end
    local visible=obj.Visible and ancestorVisible and screenEnabled
    return {controlClass=obj.ClassName,text=tostring(text or ""):sub(1,100):gsub("[%c]"," "),
        visible=obj.Visible,active=obj.Active,selectable=obj.Selectable,
        autoButtonColor=obj.AutoButtonColor,interactable=interactable,
        ancestorVisible=ancestorVisible,screenEnabled=screenEnabled,
        withinScrollingBounds=withinScrollingBounds,effectiveVisible=visible}
end

local function interactionPathIdentity(obj,root,label)
    local identity,current={},obj
    while current and current~=root and #identity<20 do
        local ordinal=1
        local parent=current.Parent
        if parent then
            for _,sibling in ipairs(parent:GetChildren()) do
                if sibling==current then break end
                if sibling.Name==current.Name and sibling.ClassName==current.ClassName then ordinal=ordinal+1 end
            end
        end
        local currentName=tostring(current.Name) local currentClass=tostring(current.ClassName)
        if #currentName>100 or #currentClass>100 then return nil end
        table.insert(identity,1,{name=currentName,className=currentClass,ordinal=ordinal})
        current=parent
    end
    local rootName=tostring(label) local rootClass=tostring(root.ClassName)
    if current~=root or #rootName>100 or #rootClass>100 then return nil end
    table.insert(identity,1,{name=rootName,className=rootClass,ordinal=1})
    local names={} for _,segment in ipairs(identity) do names[#names+1]=segment.name end
    if #table.concat(names,".")>400 then return nil end
    return identity
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
                result[key] = {visible=node.Visible,node=node}
                if node:IsA("GuiButton") then
                    result[key].active=node.Active
                end
                count=count+1
            end
        end
    end
    return result
end
local function guiTransitionIdentity(sample,fallbackPath)
    local node=sample and sample.node
    local guiRoot=player:FindFirstChildOfClass("PlayerGui")
    if not node or not guiRoot then return fallbackPath,nil end
    local pathIdentity=interactionPathIdentity(node,guiRoot,"PlayerGui")
    if not pathIdentity then return fallbackPath,nil end
    local names={}
    for _,segment in ipairs(pathIdentity) do names[#names+1]=segment.name end
    local path=table.concat(names,".")
    if path:lower():find("password",1,true) then return fallbackPath,nil end
    return path,pathIdentity
end

local function guiChangeLess(a,b)
    if a.path~=b.path then return a.path<b.path end
    local left,right=a.pathIdentity or {},b.pathIdentity or {}
    for index=1,math.min(#left,#right) do
        if left[index].className~=right[index].className then
            return left[index].className<right[index].className
        end
        if left[index].ordinal~=right[index].ordinal then
            return left[index].ordinal<right[index].ordinal
        end
    end
    return #left<#right
end

local function compareNearbyGuiState(before, after)
    local changes={}
    for key, value in pairs(before) do
        local nextValue=after[key]
        if nextValue and (value.visible ~= nextValue.visible or value.active ~= nextValue.active) then
            local path,pathIdentity=guiTransitionIdentity(nextValue,key)
            changes[#changes+1]={path=path,pathIdentity=pathIdentity,
                beforeVisible=value.visible,afterVisible=nextValue.visible,
                beforeActive=value.active,afterActive=nextValue.active}
        end
    end
    for key, value in pairs(after) do
        if not before[key] then
            local path,pathIdentity=guiTransitionIdentity(value,key)
            changes[#changes+1]={path=path,pathIdentity=pathIdentity,
                transition="appeared",afterVisible=value.visible,afterActive=value.active}
        end
    end
    for key, value in pairs(before) do
        if not after[key] then
            local path,pathIdentity=guiTransitionIdentity(value,key)
            changes[#changes+1]={path=path,pathIdentity=pathIdentity,
                transition="disappeared",beforeVisible=value.visible,beforeActive=value.active}
        end
    end
    table.sort(changes,guiChangeLess)
    while #changes>MAX_GUI_CHANGES do table.remove(changes) end
    return changes
end
local function stateValueIdentity(obj,root)
    local identity,current={},obj
    while current and current~=root and #identity<6 do
        local ordinal=1 local parent=current.Parent
        if parent then
            for _,sibling in ipairs(parent:GetChildren()) do
                if sibling==current then break end
                if sibling.Name==current.Name and sibling.ClassName==current.ClassName then ordinal=ordinal+1 end
            end
        end
        local currentName=tostring(current.Name) local currentClass=tostring(current.ClassName)
        if #currentName>100 or #currentClass>100 then return nil end
        table.insert(identity,1,{name=currentName,className=currentClass,ordinal=ordinal})
        current=parent
    end
    local rootName=tostring(root.Name) local rootClass=tostring(root.ClassName)
    if current~=root or #rootName>100 or #rootClass>100 then return nil end
    table.insert(identity,1,{name=rootName,className=rootClass,ordinal=1})
    local names={} for _,segment in ipairs(identity) do names[#names+1]=segment.name end
    if #table.concat(names,".")>180 then return nil end
    return identity
end

local function safeInteractionState()
    local state,identities,count = {},{},0
    local roots = {}
    for _, name in ipairs({"leaderstats", "Data"}) do
        local root = player:FindFirstChild(name)
        if root then roots[#roots+1] = root end
    end
    for _, root in ipairs(roots) do
        if root then
            local items = root:GetDescendants()
            for _, obj in ipairs(items) do
                if count >= MAX_STATE_SNAPSHOT_CANDIDATES then break end
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
                            if state[key]==nil then
                                state[key]=v identities[key]=stateValueIdentity(obj,root) count=count+1
                            else
                                identities[key]=nil
                            end
                        end
                    end
                end
            end
        end
    end
    for _,candidate in ipairs(stateSnapshotCandidates) do
        if count>=MAX_STATE_SNAPSHOT_CANDIDATES then break end
        local obj=candidate.object
        local ok,value=pcall(function() return obj.Value end)
        if ok and (type(value)=="boolean" or (type(value)=="number"
            and value==value and math.abs(value)<=1e12)) then
            if state[candidate.path]==nil then state[candidate.path]=value count=count+1 end
            identities[candidate.path]=nil
        end
    end
    return state,identities
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
            temporalStateChanges = featureInteractions[feature] and featureInteractions[feature].temporalStateChanges or 0,
            observableOutcomeCandidates = featureInteractions[feature] and featureInteractions[feature].outcomeCandidates or 0,
            interactionEvidence = featureInteractions[feature],
            implemented = false,
            tested = false,
            readiness = not discovered and "not-discovered"
                or (featureInteractions[feature] and featureInteractions[feature].outcomeCandidates > 0 and "observable-outcome-candidate-needs-causal-validation")
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
            note = "Only feature-consistent observable changes become candidates; temporal correlation is not causation or verification",
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
local function trim(value)
    return (value:gsub("^%s+", ""):gsub("%s+$", ""))
end
local QUICK_PROFILE_PATH_TERMS = {
    "egg", "hatch", "pet", "shop", "sell", "quest", "reward", "rebirth",
    "portal", "teleport", "travel", "inventory", "equip", "upgrade", "currency",
    "coins", "gems", "gold", "bubble", "capacity", "train", "index"
}

local function activeScanProfile()
    return SCAN_PROFILES[activeScanProfileId] or SCAN_PROFILES.full
end

local function setObservationIdleSeconds(seconds)
    for i, value in ipairs(OBSERVATION_IDLE_OPTIONS) do
        if value == seconds then
            observationIdleIndex = i
            break
        end
    end
    AUTO_EVIDENCE_IDLE_SECONDS = OBSERVATION_IDLE_OPTIONS[observationIdleIndex]
end

local function applyScanProfile(profileId)
    activeScanProfileId = profileId == "quick" and "quick" or "full"
    local profile = activeScanProfile()
    AUTO_EVIDENCE_MAX_RESCANS = profile.maxAutomaticRescans
    setObservationIdleSeconds(profile.defaultObservationSeconds)
    autoEvidenceRescans = 0
    autoEvidenceLastFailure = nil
    autoEvidenceLastScan = 0
    if refreshEvidenceControls then refreshEvidenceControls("profile-changed") end
end

local function cycleObservationIdleSeconds()
    observationIdleIndex = (observationIdleIndex % #OBSERVATION_IDLE_OPTIONS) + 1
    AUTO_EVIDENCE_IDLE_SECONDS = OBSERVATION_IDLE_OPTIONS[observationIdleIndex]
    if refreshEvidenceControls then refreshEvidenceControls("observation-seconds") end
end

local function quickPathHint(path)
    local lower = string.lower(path)
    for _, token in ipairs(QUICK_PROFILE_PATH_TERMS) do
        if lower:find(token, 1, true) then return true end
    end
    return false
end

local function shouldRecordObjectForProfile(profile, obj, path, label)
    if not profile or profile.quickTargeted ~= true then return true end
    if obj:IsA("RemoteEvent") or obj:IsA("RemoteFunction") or obj:IsA("UnreliableRemoteEvent")
        or obj:IsA("ProximityPrompt") or obj:IsA("ClickDetector")
        or obj:IsA("Tool") or obj:IsA("ValueBase")
        or obj:IsA("ModuleScript") or obj:IsA("LocalScript") or obj:IsA("Script") then
        return true
    end
    if label == "PlayerGui" and (obj:IsA("LayerCollector") or obj:IsA("GuiObject")) then
        return true
    end
    return quickPathHint(path)
end

applyScanProfile(activeScanProfileId)



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

create("Frame", {
    Name = "HeaderBackground", Size = UDim2.new(1, 0, 0, 48),
    BackgroundColor3 = Color3.fromRGB(80, 80, 80), BorderSizePixel = 0
}, panel)
create("TextLabel", {
    Text = "Lycoles Universal Inspector v" .. VERSION,
    Size = UDim2.fromOffset(260, 48), BackgroundTransparency = 1,
    TextXAlignment = Enum.TextXAlignment.Left,
    TextTruncate = Enum.TextTruncate.AtEnd,
    TextColor3 = Color3.new(1, 1, 1),
    TextSize = 18,
    Font = Enum.Font.GothamBold,
    ZIndex = 2
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

local inspectorTab = create("TextButton", {
    Name = "InspectorTab", Text = "Inspector",
    Size = UDim2.fromOffset(78, 28), Position = UDim2.fromOffset(270, 10),
    BackgroundColor3 = Color3.fromRGB(48, 116, 150),
    TextColor3 = Color3.new(1, 1, 1), TextSize = 11, ZIndex = 5
}, panel)
local generatedScriptTab = create("TextButton", {
    Name = "GeneratedScriptTab", Text = "Generated Script",
    Size = UDim2.fromOffset(112, 28), Position = UDim2.fromOffset(352, 10),
    BackgroundColor3 = Color3.fromRGB(95, 95, 95),
    TextColor3 = Color3.new(1, 1, 1), TextSize = 11, ZIndex = 5
}, panel)

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
local save = button("SAVE REPORT", 260)
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

local generatedScriptPane = create("Frame", {
    Name = "GeneratedScriptPane", Size = UDim2.fromOffset(510, 396),
    Position = UDim2.fromOffset(0, 48), BackgroundColor3 = Color3.fromRGB(45, 48, 54),
    BorderSizePixel = 0, Visible = false, ZIndex = 7
}, panel)
create("TextLabel", {
    Text = "Request an evidence-grounded client utility",
    Size = UDim2.fromOffset(486, 30), Position = UDim2.fromOffset(12, 10),
    BackgroundTransparency = 1, TextColor3 = Color3.new(1, 1, 1),
    TextXAlignment = Enum.TextXAlignment.Left, TextSize = 15, ZIndex = 8
}, generatedScriptPane)
local featureRequestInput = create("TextBox", {
    Name = "FeatureRequest", Text = "",
    PlaceholderText = "Describe the client-visible capability to generate",
    Size = UDim2.fromOffset(486, 72), Position = UDim2.fromOffset(12, 46),
    BackgroundColor3 = Color3.fromRGB(30, 33, 39), TextColor3 = Color3.new(1, 1, 1),
    PlaceholderColor3 = Color3.fromRGB(165, 172, 180), TextSize = 13,
    TextWrapped = true, MultiLine = true, ClearTextOnFocus = false,
    TextXAlignment = Enum.TextXAlignment.Left, TextYAlignment = Enum.TextYAlignment.Top,
    ZIndex = 8
}, generatedScriptPane)
local produceScript = create("TextButton", {
    Name = "ProduceScript", Text = "PRODUCE SCRIPT",
    Size = UDim2.fromOffset(180, 38), Position = UDim2.fromOffset(12, 128),
    BackgroundColor3 = Color3.fromRGB(48, 116, 150), TextColor3 = Color3.new(1, 1, 1),
    TextSize = 13, ZIndex = 8
}, generatedScriptPane)
local loadGeneratedResult = create("TextButton", {
    Name = "LoadGeneratedResult", Text = "LOAD RESULT",
    Size = UDim2.fromOffset(180, 38), Position = UDim2.fromOffset(204, 128),
    BackgroundColor3 = Color3.fromRGB(72, 92, 116), TextColor3 = Color3.new(1, 1, 1),
    TextSize = 13, ZIndex = 8
}, generatedScriptPane)

local generatedStatus = create("TextLabel", {
    Name = "GenerationStatus",
    Text = "No generated script is loaded. Enter a request to capture it with the next full scan.\n\nGeneration and static validation run offline from complete numbered parts. Gameplay remains unverified.",
    Size = UDim2.fromOffset(486, 112), Position = UDim2.fromOffset(12, 176),
    BackgroundTransparency = 1, TextColor3 = Color3.fromRGB(215, 224, 232),
    TextWrapped = true, TextXAlignment = Enum.TextXAlignment.Left,
    TextYAlignment = Enum.TextYAlignment.Top, TextSize = 13, ZIndex = 8
}, generatedScriptPane)
local generatedCodeOutput = create("TextBox", {
    Name = "GeneratedCodeOutput", Text = "-- Generated Luau becomes available only after offline compilation and validation.",
    Size = UDim2.fromOffset(486, 78), Position = UDim2.fromOffset(12, 302),
    BackgroundColor3 = Color3.fromRGB(30, 33, 39), TextColor3 = Color3.fromRGB(180, 190, 198),
    TextSize = 11, Font = Enum.Font.Code, TextWrapped = true, MultiLine = true,
    TextEditable = false, TextXAlignment = Enum.TextXAlignment.Left,
    TextYAlignment = Enum.TextYAlignment.Top, ZIndex = 8
}, generatedScriptPane)
local function showGeneratedScriptPane(visible)
    generatedScriptPane.Visible = visible
    inspectorTab.BackgroundColor3 = visible and Color3.fromRGB(95, 95, 95) or Color3.fromRGB(48, 116, 150)
    generatedScriptTab.BackgroundColor3 = visible and Color3.fromRGB(48, 116, 150) or Color3.fromRGB(95, 95, 95)
end
inspectorTab.MouseButton1Click:Connect(function() showGeneratedScriptPane(false) end)
generatedScriptTab.MouseButton1Click:Connect(function() showGeneratedScriptPane(true) end)
local function refreshGeneratedHandoff(phase)
    if not pendingManifest then return end
    local requestText=pendingManifest.featureRequest
    local requestLine="Request (not evidence): none"
    if type(requestText)=="string" and requestText~="" then
        requestLine="Request (not evidence): "..requestText:sub(1,96)
    end
    local exported=pendingManifest.localExport
    local exportLine="Local export: not attempted"
    if type(exported)=="table" then
        local manifestState=exported.manifestSaved==true and "saved"
            or (exported.manifestSaved==false and "not saved" or "unknown")
        exportLine="Local export: "..tostring(exported.status).." "
            ..tostring(exported.exportedParts or 0).."/"..tostring(exported.expectedParts or 0)
            .." parts; manifest "..manifestState
    end
    local attemptLine="Upload: "..uploadAttemptStage()
    if uploadState.attempted then
        attemptLine=attemptLine.."; status "..tostring(uploadState.status)
    elseif uploadState.status=="configuration-error" then
        attemptLine=attemptLine.."; "..tostring(uploadState.lastError or "configuration unavailable")
    end
    local downstreamLine="Downstream: not validated; save complete local parts or upload"
    if type(exported)=="table" and exported.status=="complete"
        and exported.manifestSaved==true then
        downstreamLine="Downstream: local files claimed complete; import and validate offline"
    elseif receiverReportStatus()=="acknowledged-awaiting-integrity" then
        downstreamLine="Downstream: receiver integrity verification required"
    end
    local snapshotLine = "Snapshot: pending"
    local profileLine = "Scan profile: unknown"
    if type(pendingManifest.scanStats)=="table" then
        snapshotLine = "Snapshot: "..(pendingManifest.scanStats.complete==true and "complete" or "partial")
        profileLine = "Scan profile: "..tostring(pendingManifest.scanStats.profile or "unknown")
    end
    generatedStatus.Text=tostring(phase or "Evidence handoff").."\n"..requestLine
        .."\n"..profileLine
        .."\n"..snapshotLine
        .."\nEvidence: scan "..tostring(pendingManifest.scanId).."; "
        ..tostring(uploadState.expectedParts).." numbered parts"
        .."\n"..exportLine
        .."\n"..attemptLine
        .."\nReceiver: "..receiverReportStatus().."; ACK "
        ..tostring(uploadState.acknowledgedParts).."/"..tostring(uploadState.expectedParts)
        .."; integrity unverified"
        .."\n"..downstreamLine
        .."\nGeneration: offline compilation/validation pending; gameplay unverified"
end
local function boundedResultText(value,limit)
    return type(value)=="string" and #value>=1 and #value<=limit
        and value:find("[%c]")==nil
end
local function boundedResultInteger(value,maximum)
    return type(value)=="number" and value>=0 and value<=maximum and value%1==0
end
local function falseResultClaims(claims)
    return type(claims)=="table" and claims.sourceAuthenticityVerified==false
        and claims.causalityProven==false and claims.serverAuthorityVerified==false
        and claims.runtimeVerified==false and claims.gameplayVerified==false
        and claims.actionOutcomesVerified==false
end
local function validateWorkflowSelection(selection)
    if type(selection)~="table" or type(selection.available)~="boolean"
        or type(selection.candidates)~="table" or #selection.candidates>20
        or not boundedResultInteger(selection.totalCandidates,1000000)
        or not boundedResultInteger(selection.shownCandidates,20)
        or not boundedResultInteger(selection.omittedCandidates,1000000)
        or selection.shownCandidates~=#selection.candidates
        or selection.totalCandidates~=#selection.candidates+selection.omittedCandidates then
        return false
    end
    local diagnostics=selection.planningDiagnostics
    if diagnostics~=nil then
        local fields={"transactionGroups","linkedTransactions","singletonTransactions",
            "multiEventTransactions","transactionsWithInsufficientGenerationReadySteps",
            "partiallyMappedTransactions","transactionsOverStepBound","workflowCandidates",
            "unlinkedEvents","executionReadyWorkflows"}
        local statuses={
            ["execution-ready-candidates"]=true,["review-only-candidates"]=true,
            ["no-multi-step-generation-ready-contract"]=true,
            ["singleton-transactions-only"]=true,["no-explicit-linkage"]=true,
            ["no-interaction-events"]=true}
        if type(diagnostics)~="table" or statuses[diagnostics.status]~=true
            or diagnostics.readinessImpact~="limitations-only"
            or diagnostics.causalityProven~=false or diagnostics.runtimeVerified~=false
            or diagnostics.gameplayVerified~=false then return false end
        for _,field in ipairs(fields) do
            if not boundedResultInteger(diagnostics[field],10000000) then return false end
        end
        if diagnostics.transactionGroups~=diagnostics.singletonTransactions
                +diagnostics.multiEventTransactions
            or diagnostics.linkedTransactions~=diagnostics.multiEventTransactions
            or diagnostics.workflowCandidates~=selection.totalCandidates
            or diagnostics.transactionsWithInsufficientGenerationReadySteps
                >diagnostics.multiEventTransactions
            or diagnostics.partiallyMappedTransactions>diagnostics.workflowCandidates
            or diagnostics.transactionsOverStepBound>diagnostics.workflowCandidates
            or diagnostics.executionReadyWorkflows>diagnostics.workflowCandidates then return false end
        local expected
        if diagnostics.executionReadyWorkflows>0 then expected="execution-ready-candidates"
        elseif diagnostics.workflowCandidates>0 then expected="review-only-candidates"
        elseif diagnostics.multiEventTransactions>0 then
            expected="no-multi-step-generation-ready-contract"
        elseif diagnostics.singletonTransactions>0 then expected="singleton-transactions-only"
        elseif diagnostics.unlinkedEvents>0 then expected="no-explicit-linkage"
        else expected="no-interaction-events" end
        if diagnostics.status~=expected then return false end
    end

    local selectedId=selection.selectedCandidateId
    if selectedId~=nil and not boundedResultText(selectedId,120) then return false end
    local validReason={
        ["selected-highest-ranked-execution-ready-candidate"]=true,
        ["not-execution-ready"]=true,["lower-request-evidence-score"]=true,
        ["more-user-involvement-tiebreak"]=true,["stable-identity-tiebreak"]=true
    }
    local validMode={["review-only"]=true,["mixed-guided"]=true,["bounded-automatic"]=true}
    local selectedCount=0
    for _,item in ipairs(selection.candidates) do
        if type(item)~="table" or not boundedResultText(item.candidateId,120)
            or not boundedResultInteger(item.requestScore,10000)
            or type(item.matchedTerms)~="table" or #item.matchedTerms>128
            or validMode[item.executionMode]~=true or type(item.executionReady)~="boolean"
            or type(item.selected)~="boolean" or validReason[item.selectionReason]~=true then
            return false
        end
        local previous=nil
        for _,term in ipairs(item.matchedTerms) do
            if not boundedResultText(term,80) or term:match("^[a-z0-9]+$")==nil
                or previous~=nil and term<=previous then return false end
            previous=term
        end
        if (item.requestScore>0)~=(#item.matchedTerms>0) then return false end
        if item.selected then
            selectedCount=selectedCount+1
            if item.candidateId~=selectedId
                or item.selectionReason~="selected-highest-ranked-execution-ready-candidate" then
                return false
            end
        end
    end
    if selectedCount~=(selectedId~=nil and 1 or 0) then return false end
    if selection.available==false and (selection.totalCandidates~=0 or selectedId~=nil) then
        return false
    end
    return true
end
local function validateGuidedFeedbackCorrelation(correlation,selectedWorkflowId)
    if correlation==nil then return true end
    if type(correlation)~="table" or type(correlation.available)~="boolean"
        or not falseResultClaims(correlation.claims) then return false end
    if correlation.available==false then
        return correlation.readinessImpact=="none" and boundedResultText(correlation.reason,160)
    end
    if correlation.schemaVersion~="116.guided-workflow-feedback-aggregate.1"
        or correlation.readinessImpact~="informational-only"
        or correlation.candidateId~=selectedWorkflowId
        or not boundedResultText(correlation.candidateId,160)
        or type(correlation.workflowPlanSHA256)~="string"
        or #correlation.workflowPlanSHA256~=64
        or correlation.workflowPlanSHA256:match("^[a-f0-9]+$")==nil
        or type(correlation.completeSequenceRecurrenceObserved)~="boolean"
        or type(correlation.summary)~="table" or type(correlation.steps)~="table"
        or #correlation.steps<1 or #correlation.steps>64 then return false end
    local summary=correlation.summary
    local summaryFields={"sessions","runs","submittedEntries","activationEventsObserved",
        "expectedChangesObserved","completeClientObservationSequences",
        "sessionsWithCompleteClientObservationSequence","stepsWithStatusConflict"}
    for _,field in ipairs(summaryFields) do
        if not boundedResultInteger(summary[field],1000000) then return false end
    end
    if correlation.completeSequenceRecurrenceObserved
            ~=(summary.sessionsWithCompleteClientObservationSequence>=2)
        or summary.sessions<1
        or summary.sessionsWithCompleteClientObservationSequence>summary.sessions
        or summary.completeClientObservationSequences>summary.runs
        or summary.expectedChangesObserved>summary.activationEventsObserved
        or summary.activationEventsObserved>summary.submittedEntries then return false end
    local validStatus={["expected-change-observed"]=true,["outcome-not-observed"]=true,
        ["activation-timeout"]=true,["control-or-state-unavailable"]=true,
        ["metadata-drift"]=true,["state-unreadable"]=true}
    local validExpected={increased=true,decreased=true,changed=true}
    local validScalar={boolean=true,number=true,string=true}
    local totalAttempts,totalActivations,totalChanges,totalConflicts=0,0,0,0
    for index,step in ipairs(correlation.steps) do
        if type(step)~="table" or step.stepSequence~=index
            or not boundedResultText(step.targetPath,512)
            or not boundedResultText(step.outcomeKey,256)
            or validExpected[step.expected]~=true or type(step.statuses)~="table"
            or type(step.observedScalarTypes)~="table"
            or type(step.statusConflictObserved)~="boolean"
            or type(step.statusConflictAcrossSessions)~="boolean"
            or type(step.scalarTypeConflictObserved)~="boolean"
            or type(step.expectedDirectionAcrossMultipleSessions)~="boolean" then return false end
        local countFields={"attempts","sessionsObserved","activationEventsObserved",
            "expectedChangesObserved","sessionsWithExpectedChange"}
        for _,field in ipairs(countFields) do
            if not boundedResultInteger(step[field],1000000) then return false end
        end
        local statusKinds,statusCount=0,0
        for statusValue,count in pairs(step.statuses) do
            if validStatus[statusValue]~=true or not boundedResultInteger(count,1000000)
                or count<1 then return false end
            statusKinds=statusKinds+1;statusCount=statusCount+count
        end
        local previous=nil
        for _,scalarType in ipairs(step.observedScalarTypes) do
            if validScalar[scalarType]~=true or previous~=nil and scalarType<=previous then return false end
            previous=scalarType
        end
        if statusCount~=step.attempts
            or step.expectedChangesObserved>step.activationEventsObserved
            or step.activationEventsObserved>step.attempts
            or step.sessionsWithExpectedChange>step.sessionsObserved
            or step.statusConflictObserved~=(statusKinds>1)
            or step.scalarTypeConflictObserved~=(#step.observedScalarTypes>1)
            or step.expectedDirectionAcrossMultipleSessions~=(step.sessionsWithExpectedChange>=2) then
            return false
        end
        totalAttempts=totalAttempts+step.attempts
        totalActivations=totalActivations+step.activationEventsObserved
        totalChanges=totalChanges+step.expectedChangesObserved
        if step.statusConflictObserved then totalConflicts=totalConflicts+1 end
    end
    return totalAttempts==summary.submittedEntries
        and totalActivations==summary.activationEventsObserved
        and totalChanges==summary.expectedChangesObserved
        and totalConflicts==summary.stepsWithStatusConflict
end

local function validateGeneratedObservationBaseline(value,workflow)
    if value==nil then return true end
    if type(value)~="table" or value.readinessImpact~="limitations-only"
        or value.causalityProven~=false or value.runtimeVerified~=false
        or value.gameplayVerified~=false or type(value.possibleSynchronousLoss)~="boolean" then
        return false
    end
    local total=workflow and value.steps or value.events
    local pre=workflow and value.preActivationSteps or value.preActivationEvents
    local callback=workflow and value.activationCallbackSteps or value.activationCallbackEvents
    local unknown=workflow and value.unknownTimingSteps or value.unknownTimingEvents
    if not boundedResultInteger(total,2000) or total<1
        or not boundedResultInteger(pre,2000) or not boundedResultInteger(callback,2000)
        or not boundedResultInteger(unknown,2000) or total~=pre+callback+unknown
        or value.possibleSynchronousLoss~=(callback>0 or unknown>0) then return false end
    local expected=unknown>0 and "timing-unknown" or callback>0 and "callback-fallback-present"
        or workflow and "pre-activation-baseline-available-for-all-steps"
        or "pre-activation-baseline-available-for-all-observations"
    return value.classification==expected
end

local function validateInteractionObservationCoverage(value)
    if value==nil then return true end
    if type(value)~="table" or type(value.available)~="boolean"
        or value.readinessImpact~="limitations-only" or value.causalityProven~=false
        or value.runtimeVerified~=false or value.gameplayVerified~=false
        or type(value.limitations)~="table" or #value.limitations>8 then return false end
    for _,item in ipairs(value.limitations) do if not boundedResultText(item,160) then return false end end
    if value.available==false then
        return value.classification=="unavailable-legacy" and value.evidenceLossPossible==nil
    end
    local counts={value.callbacksFired,value.preActivationBaselinesUsed,value.callbackBaselinesUsed,
        value.pendingObservationEvents,value.observationWindowsExpected,
        value.observationWindowsCompleted,value.observationWindowsFailed}
    for _,count in ipairs(counts) do if not boundedResultInteger(count,10000000) then return false end end
    if value.preActivationCaptureFailures~=nil
        and not boundedResultInteger(value.preActivationCaptureFailures,10000000) then return false end
    if value.observationWindowAccountingValid~=true
        or type(value.evidenceLossPossible)~="boolean"
        or value.preActivationBaselinesUsed+value.callbackBaselinesUsed~=value.callbacksFired
        or value.observationWindowsCompleted+value.observationWindowsFailed
            +value.pendingObservationEvents~=value.observationWindowsExpected then return false end
    local knownPossible=value.callbackBaselinesUsed>0 or value.pendingObservationEvents>0
        or value.observationWindowsFailed>0
    local possible=value.evidenceLossPossible
    if value.preActivationCaptureFailures~=nil then
        possible=knownPossible or value.preActivationCaptureFailures>0
    end
    if knownPossible and value.evidenceLossPossible~=true then return false end
    local expected=possible and "possible-evidence-loss"
        or value.callbacksFired==0 and "accounted-no-interactions"
        or "accounted-pre-activation-observation"
    return value.evidenceLossPossible==possible and value.classification==expected
end


local function validateGeneratedReadiness(result)
    if result.schemaVersion=="110.generated-result.1" then return true,nil end
    if result.schemaVersion~="113.generated-result.1" then return false,nil end
    local readiness=result.generationReadiness
    if type(readiness)~="table" or readiness.schemaVersion~="113.generation-readiness.1"
        or readiness.placeId~=result.placeId or readiness.scanId~=result.scanId then
        return false,nil
    end
    local claims=readiness.claims
    if type(claims)~="table" or claims.sourceAuthenticityVerified~=false
        or claims.causalityProven~=false or claims.serverAuthorityVerified~=false
        or claims.runtimeVerified~=false or claims.gameplayVerified~=false
        or claims.actionOutcomesVerified~=false then
        return false,nil
    end
    local workflowSelection=readiness.workflowSelection
    if not validateWorkflowSelection(workflowSelection)
        or not validateGuidedFeedbackCorrelation(readiness.guidedWorkflowFeedbackCorrelation,
            workflowSelection.selectedCandidateId)
        or not validateInteractionObservationCoverage(readiness.interactionObservationCoverage) then
        return false,nil
    end
    local request=readiness.request
    local validStatus={
        ["no-capability-requested"]=true,["generated-bounded-subset"]=true,
        ["evidence-only-no-replay-contract"]=true,["unsupported-by-current-evidence"]=true
    }
    if type(request)~="table" or request.request~=result.requestedCapability
        or validStatus[request.status]~=true
        or request.fullRequestImplemented~=false or request.implementationReady~=false
        or request.runtimeVerified~=false or request.gameplayVerified~=false
        or request.causalityProven~=false or request.actionOutcomesVerified~=false
        or type(request.generatedSubsetAvailable)~="boolean"
        or type(request.supportedSubset)~="table" or #request.supportedSubset>16
        or type(request.matchedGeneratedCapabilityIds)~="table"
        or #request.matchedGeneratedCapabilityIds>64 then
        return false,nil
    end
    for _,item in ipairs(request.supportedSubset) do
        if not boundedResultText(item,160) then return false,nil end
    end
    local matchedSeen={}
    for _,item in ipairs(request.matchedGeneratedCapabilityIds) do
        if not boundedResultText(item,80) or matchedSeen[item] then return false,nil end
        matchedSeen[item]=true
    end
    local generated=readiness.generatedCapabilities
    local unavailable=readiness.unavailableRequestedBehavior
    local discovery=readiness.discoveryOnlyCapabilities
    if type(generated)~="table" or #generated>64 or type(unavailable)~="table"
        or #unavailable>16 or type(discovery)~="table" or #discovery>16 then
        return false,nil
    end
    local generatedSeen={}
    local workflowCapabilityId=nil
    local validStepKind={["guided-gui-activation-trial"]=true,
        ["official-tool-activation-trial"]=true,["proximity-prompt-trial"]=true}
    for _,item in ipairs(generated) do
        if type(item)~="table" or not boundedResultText(item.id,80) or generatedSeen[item.id]
            or item.runtimeVerified~=false or item.gameplayVerified~=false
            or item.causalityProven~=false or item.actionOutcomeVerified~=false then
            return false,nil
        end
        local workflowKind=item.kind=="mixed-action-workflow-trial"
        if not validateGeneratedObservationBaseline(item.observationBaseline,workflowKind) then
            return false,nil
        end
        if workflowKind then
            local expectedMode=item.manualGuiActivationRequired and "mixed-guided" or "bounded-automatic"
            if workflowCapabilityId~=nil or not boundedResultText(item.candidateId,120)
                or not boundedResultText(item.transactionId,200)
                or item.executionMode~=expectedMode
                or not boundedResultInteger(item.stepCount,64) or item.stepCount<2
                or item.observationBaseline~=nil and item.observationBaseline.steps~=item.stepCount
                or type(item.stepKinds)~="table" or #item.stepKinds~=item.stepCount
                or type(item.targetPaths)~="table" or #item.targetPaths~=item.stepCount
                or type(item.requestMatchedTerms)~="table" or #item.requestMatchedTerms>128
                or not boundedResultInteger(item.requestMatchScore,10000)
                or type(item.manualGuiActivationRequired)~="boolean"
                or item.automaticallyExecutable~=(not item.manualGuiActivationRequired)
                or item.operatorStartRequired~=true or item.stopOnFirstUnobservedOutcome~=true then
                return false,nil
            end
            for index,stepKind in ipairs(item.stepKinds) do
                if validStepKind[stepKind]~=true
                    or not boundedResultText(item.targetPaths[index],500) then return false,nil end
            end
            local previous=nil
            for _,term in ipairs(item.requestMatchedTerms) do
                if not boundedResultText(term,80) or term:match("^[a-z0-9]+$")==nil
                    or previous~=nil and term<=previous then return false,nil end
                previous=term
            end
            if (item.requestMatchScore>0)~=(#item.requestMatchedTerms>0) then return false,nil end
            workflowCapabilityId=item.candidateId
        else
            if validStepKind[item.kind]~=true
                or item.kind=="guided-gui-activation-trial" and
                    (item.automaticActivation~=false or item.manualActivationRequired~=true
                        or item.exactControlHighlighting~=true)
                or not boundedResultText(item.targetLabel,120)
                or not boundedResultText(item.selectedOutcomeKey,200)
                or (item.expectedChange~="increased" and item.expectedChange~="decreased"
                    and item.expectedChange~="changed") then return false,nil end
        end
        generatedSeen[item.id]=true
    end
    if workflowCapabilityId~=workflowSelection.selectedCandidateId then return false,nil end
    local generatedStatus=request.status=="generated-bounded-subset"
    if ((result.requestedCapability==nil)~=(request.status=="no-capability-requested"))
        or generatedStatus~=request.generatedSubsetAvailable
        or generatedStatus~=(#request.matchedGeneratedCapabilityIds>0)
        or generatedStatus~=(#request.supportedSubset>0) then return false,nil end
    for identifier in pairs(matchedSeen) do
        if not generatedSeen[identifier] then return false,nil end
    end

    for _,item in ipairs(unavailable) do
        if type(item)~="table" or not boundedResultText(item.id,80)
            or item.status~="unavailable" then return false,nil end
    end
    for _,item in ipairs(discovery) do
        if type(item)~="table" or not boundedResultText(item.family,80)
            or type(item.candidateCount)~="number" or item.candidateCount<0
            or item.candidateCount>1000000 or item.candidateCount%1~=0
            or type(item.observedCount)~="number" or item.observedCount<0
            or item.observedCount>item.candidateCount or item.observedCount%1~=0
            or item.replayContractAvailable~=false then return false,nil end
    end
    return true,readiness
end

loadGeneratedResult.MouseButton1Click:Connect(function()
    if type(readfile)~="function" then
        generatedStatus.Text="Result loading unavailable: readfile is not supported."
        return
    end
    local filename="Lycoles-"..tostring(game.PlaceId).."-generated-result.json"
    local readOk,raw=pcall(readfile,filename)
    if not readOk or type(raw)~="string" or #raw>1200000 then
        generatedStatus.Text="Result load failed: expected bounded file "..filename
        return
    end
    local decodeOk,result=pcall(function() return HttpService:JSONDecode(raw) end)
    local code=decodeOk and type(result)=="table" and result.generatedCode or nil
    local schemaValid=decodeOk and type(result)=="table" and
        (result.schemaVersion=="110.generated-result.1"
            or result.schemaVersion=="113.generated-result.1")
    local readinessValid,readiness=false,nil
    if schemaValid then readinessValid,readiness=validateGeneratedReadiness(result) end
    local valid=schemaValid and readinessValid
        and result.placeId==game.PlaceId and type(result.scanId)=="string"
        and result.staticValidationPassed==true and result.packageAuthenticityVerified==false
        and result.runtimeVerified==false and result.gameplayVerified==false
        and result.executionAuthorized==false and type(code)=="string" and #code<=1000000
        and code:find("assert(game.PlaceId == "..tostring(game.PlaceId),1,true)~=nil
    if not valid then
        generatedStatus.Text="Result rejected: schema, place guard, readiness, or verification claims are invalid."
        return
    end
    generatedCodeOutput.Text=code
    if readiness then
        local generated=readiness.generatedCapabilities
        local unavailable={}
        for index,item in ipairs(readiness.unavailableRequestedBehavior) do
            if index>4 then break end unavailable[#unavailable+1]=item.id
        end
        local details={"Loaded display-only result for scan "..result.scanId,
            "Readiness: "..readiness.request.status,
            "Generated bounded capabilities: "..tostring(#generated),
            "Full request implemented: false | Runtime/gameplay verified: false"}
        local coverage=readiness.interactionObservationCoverage
        if type(coverage)=="table" then
            if coverage.available then
                details[#details+1]="Observation coverage: "..coverage.classification.." | pre="
                    ..tostring(coverage.preActivationBaselinesUsed).." callback="
                    ..tostring(coverage.callbackBaselinesUsed).." | causality unproven"
            else
                details[#details+1]="Observation coverage: unavailable for legacy evidence"
            end
        end
        local planning=readiness.workflowSelection.planningDiagnostics
        if type(planning)=="table" then
            details[#details+1]="Workflow planning: "..planning.status.." | shared="
                ..tostring(planning.multiEventTransactions).." singleton="
                ..tostring(planning.singletonTransactions).." unlinked="
                ..tostring(planning.unlinkedEvents).." | limitations only"
        end

        local workflowCapability=nil
        local singleCapability=nil
        for _,item in ipairs(generated) do
            if item.kind=="mixed-action-workflow-trial" then workflowCapability=item
            elseif singleCapability==nil then singleCapability=item end
        end
        if workflowCapability then
            details[#details+1]="Workflow: "..workflowCapability.candidateId.." | "
                ..workflowCapability.executionMode.." | "..tostring(workflowCapability.stepCount).." steps"
        elseif singleCapability then
            details[#details+1]="Evidence: "..singleCapability.targetLabel.." -> "
                ..singleCapability.selectedOutcomeKey.." "..singleCapability.expectedChange
        else
            details[#details+1]="Evidence: no generated replay capability"
        end
        local selectedCapability=workflowCapability or singleCapability
        local selectedBaseline=selectedCapability and selectedCapability.observationBaseline or nil
        if type(selectedBaseline)=="table" then
            details[#details+1]="Selected evidence baseline: "..selectedBaseline.classification
                .." | limitations only; not causal proof"
        end

        local correlation=readiness.guidedWorkflowFeedbackCorrelation
        if type(correlation)=="table" and correlation.available then
            local summary=correlation.summary
            details[#details+1]="Workflow feedback: "..tostring(summary.sessions).." sessions | "
                ..tostring(summary.completeClientObservationSequences)
                .." complete client-observation sequences | informational only"
            local statusOrder={"expected-change-observed","outcome-not-observed",
                "activation-timeout","control-or-state-unavailable","metadata-drift","state-unreadable"}
            for index,step in ipairs(correlation.steps) do
                if index>4 then break end
                local statuses={}
                for _,statusValue in ipairs(statusOrder) do
                    local count=step.statuses[statusValue]
                    if type(count)=="number" and count>0 then
                        statuses[#statuses+1]=statusValue.."="..tostring(count)
                    end
                end
                local path=step.targetPath
                if #path>72 then path=path:sub(1,69).."..." end
                details[#details+1]="Step "..tostring(index).." "..path..": "
                    ..(#statuses>0 and table.concat(statuses,", ") or "not observed")
                    .." | expected changes "..tostring(step.expectedChangesObserved)
                    .."/"..tostring(step.attempts)
            end
            if #correlation.steps>4 then
                details[#details+1]="Workflow feedback: "..tostring(#correlation.steps-4)
                    .." additional steps omitted from this display"
            end
        elseif type(correlation)=="table" then
            details[#details+1]="Workflow feedback: unavailable ("..correlation.reason..")"
        end
        details[#details+1]="Unsupported: "
            ..(#unavailable>0 and table.concat(unavailable,", ") or "see packaged limitations")
        details[#details+1]="Static validation is package-reported; package authenticity, runtime, execution, and gameplay remain unverified."
        generatedStatus.TextSize=11
        generatedStatus.Text=table.concat(details,"\n")
    else
        generatedStatus.Text="Loaded legacy display-only offline result for scan "..result.scanId
            ..". Static validation is package-reported; package authenticity, runtime, execution, and gameplay remain unverified."
    end
    showGeneratedScriptPane(true)
end)



_G.LycolesInspectorClose = function()
    stopWorkflowRecording("inspector-closed")
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
                and ack.partCount == partCount and type(ack.id) == "string"
                and type(ack.sha256) == "string" and #ack.sha256 == 64
                and ack.sha256:match("^[a-f0-9]+$") then
                return true, {id=ack.id,sha256=ack.sha256}
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
        uploadState.status="configuration-error"
        uploadState.lastError="invalid receiver endpoint"
        refreshLocalManifest("upload-blocked")
        refreshGeneratedHandoff("Upload blocked")
        status.Text = "Use https://HOST/ingest/KEY"
        return
    end
    local requestFn = (syn and syn.request) or http_request or request
    if type(requestFn) ~= "function" then
        uploadState.status="configuration-error"
        uploadState.lastError="HTTP requests unavailable"
        refreshLocalManifest("upload-blocked")
        refreshGeneratedHandoff("Upload blocked")
        status.Text = "HTTP requests unavailable"
        return
    end
    saveEndpoint()
    local receiver = endpoint
    local parts = pendingParts
    local firstOk, first = pcall(function() return HttpService:JSONDecode(parts[1]) end)
    if not firstOk or type(first)~="table" then
        uploadState.status="configuration-error"
        uploadState.lastError="malformed first part"
        refreshLocalManifest("upload-blocked")
        refreshGeneratedHandoff("Upload blocked")
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
            uploadState.status="configuration-error"
            uploadState.lastError="inconsistent part "..tostring(i)
            refreshLocalManifest("upload-blocked")
        refreshGeneratedHandoff("Upload blocked")
            status.Text="Upload blocked: inconsistent part "..tostring(i)
            return
        end
    end
    local acknowledgedBefore=0
    for i=1,partCount do
        if pendingAcknowledged[i] then acknowledgedBefore=acknowledgedBefore+1 end
    end
    uploadState.attempted=true
    uploadState.status="uploading"
    uploadState.acknowledgedParts=acknowledgedBefore
    uploadState.expectedParts=partCount
    uploadState.lastError=nil
    refreshLocalManifest("upload-started")
    refreshGeneratedHandoff("Upload started")
    uploading = true
    uploadGeneration = uploadGeneration + 1
    local generation = uploadGeneration
    task.spawn(function()
        local started = os.clock()
        local succeeded, failed, nextIndex, active = 0, nil, 1, 0
        for i = 1, partCount do
            if pendingAcknowledged[i] then succeeded = succeeded + 1 end
        end
        uploadState.acknowledgedParts=succeeded
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
                        uploadState.acknowledgedParts=succeeded
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
        uploadState.acknowledgedParts=succeeded
        if failed then
            uploadState.status="failed"
            uploadState.lastError=failed
            status.Text = "ACK " .. succeeded .. "/" .. partCount .. ": " .. failed .. "; retry SEND JSON"
        elseif succeeded == partCount then
            uploadState.status="acknowledged"
            uploadState.lastError=nil
            status.Text = "Upload acknowledged: " .. succeeded .. "/" .. partCount
                .. " parts in " .. tostring(elapsed) .. "s; verify receiver integrity separately"
        else
            uploadState.status="incomplete"
            uploadState.lastError="not all parts acknowledged"
            status.Text = "Upload incomplete: " .. succeeded .. "/" .. partCount .. "; retry SEND JSON"
        end
        refreshLocalManifest("post-upload")
        refreshGeneratedHandoff("Upload finished")
    end)
end

local function cancelActiveOperation()
    if running then
        scanGeneration = scanGeneration + 1
        running = false
        status.Text = "Scan cancelled; start a new snapshot when ready"
        refreshGeneratedHandoff("Scan cancelled")
        return true
    end
    if uploading then
        uploadGeneration = uploadGeneration + 1
        uploading = false
        uploadState.status = "cancelled"
        uploadState.lastError = "operator cancelled"
        refreshLocalManifest("upload-cancelled")
        refreshGeneratedHandoff("Upload cancelled")
        status.Text = "Upload cancelled; SEND JSON to resume from acknowledged parts"
        return true
    end
    status.Text = "No active scan or upload to cancel"
    return false
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

refreshLocalManifest = function(phase)
    if not pendingManifest then return false end
    pendingManifest.uploadedParts = uploadState.acknowledgedParts
    pendingManifest.reportTransport = uploadSnapshot(phase)
    local ok, encoded = pcall(function()
        return encodeStage("scan-manifest-refresh", pendingManifest)
    end)
    if ok then last=encoded end
    return ok
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
            featureRequest=meta and report.featureRequest or nil,
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
    return parts, scanId
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
local function enrichEntry(entry, obj, profile)
    local quick = profile and profile.quickTargeted == true
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
    if not quick then
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
        entry.guiControl = guiControlSnapshot(obj)
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
        entry.tool = {requiresHandle=obj.RequiresHandle,canBeDropped=obj.CanBeDropped,
            enabled=obj.Enabled,manualActivationOnly=obj.ManualActivationOnly,
            tooltip=obj.ToolTip:sub(1,120):gsub("[%c]"," ")}
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
        progression={"level","xp","experience","rebirth","ascension","prestige","unlock","requirement","bubble","capacity","blow"},
        quests={"quest","mission","objective","daily","weekly","task"},
        pets={"pet","companion","egg","hatch","enchant","evolve"},
        economy={"shop","store","vendor","price","cost","cash","gold","gem","currency","purchase","sell","upgrade"},
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
        if not quick then
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
    end

    -- Bounded sibling ValueBase context supports cross-system relationship mapping.
    if not quick and obj:IsA("ValueBase") and parent then
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
        entry.controlMetadata = guiControlSnapshot(obj)
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
    if property=="Value" and label=="LocalPlayer"
        and not stateSnapshotCandidateSeen[obj]
        and #stateSnapshotCandidates<MAX_STATE_SNAPSHOT_CANDIDATES then
        local top=obj
        while top.Parent and top.Parent~=player do top=top.Parent end
        local low=path:lower()
        local primary=top.Name=="Data" or top.Name=="leaderstats"
        local private=low:find("token",1,true) or low:find("secret",1,true)
            or low:find("auth",1,true) or low:find("password",1,true)
            or low:find("userid",1,true)
        if not primary and not private then
            stateSnapshotCandidateSeen[obj]=true
            stateSnapshotCandidates[#stateSnapshotCandidates+1]={object=obj,path=path:sub(1,180)}
        end
    end
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
    freegiftsgui="rewards", freegiftsnewmenu="rewards", season="rewards",
    dailyperks="rewards", shadowleviathan="bosses",
    shopnewmenu="shops", bossnewmenu="bosses", teleportnewmenu="travel",
    travelareanewmenu="travel", petsrightbase="pets", petsbutton="pets",
    confirmSellNewMenu="inventory", confirmsellnewmenu="inventory",
    fortunewheelmenugui="rewards", fortuneothermenusgui="rewards",
    robuxshop="shops", buyspinsmenu="shops",
    runecrafting="progression", enchants="progression", gemgenie="progression",
    powerups="progression", boxcondenser="progression", potions="progression"
}
local CONTEXT_TOKEN_IGNORES = {
    button=true, frame=true, main=true, inner=true, top=true, bottom=true,
    left=true, right=true, close=true, template=true, item=true, items=true,
    hud=true, players=true, playergui=true, screengui=true, localplayer=true,
    scrollingframe=true, screen=true, gui=true, label=true, text=true,
    image=true, content=true, action=true, buttons=true
}
local function contextTokensForNames(names)
    local seen,tokens={},{}
    if type(names)~="table" then return tokens end
    for _,name in ipairs(names) do
        for token in tostring(name):lower():gmatch("[%a%d]+") do
            if #token>=3 and not CONTEXT_TOKEN_IGNORES[token] and not seen[token] then
                seen[token]=true
                tokens[#tokens+1]=token
            end
        end
    end
    table.sort(tokens)
    return tokens
end
local function contextTokenOverlap(left,right)
    if type(left)~="table" or type(right)~="table" then return 0 end
    local seen,score={},0
    for _,token in ipairs(left) do seen[token]=true end
    for _,token in ipairs(right) do if seen[token] then score=score+1 end end
    return score
end
local function scoredFeatureFromInteractionContext(obj,path)
    local scores={}
    local function add(feature,weight)
        if feature then scores[feature]=(scores[feature] or 0)+weight end
    end
    local function scan(value,weight)
        local text=tostring(value)
        local hint=MENU_FEATURE_HINTS[text:lower()]
        if hint then add(hint,weight+1) end
        local feature=featureForName(text)
        if feature then add(feature,weight) end
    end
    scan(obj.Name,2)
    if obj:IsA("GuiButton") then
        local ok,text=pcall(function() return obj.Text end)
        if ok and type(text)=="string" and #text>0 then scan(text:sub(1,80),2) end
    end
    local node=obj.Parent
    for depth=1,9 do
        if not node then break end
        scan(node.Name,1)
        if node:IsA("ScreenGui") then break end
        node=node.Parent
    end
    for segment in tostring(path or ""):gmatch("[^%.]+") do scan(segment,1) end
    local ranked={}
    for feature,score in pairs(scores) do ranked[#ranked+1]={feature=feature,score=score} end
    table.sort(ranked,function(a,b)
        return a.score==b.score and a.feature<b.feature or a.score>b.score
    end)
    if #ranked==0 then return nil,0,nil end
    local first,second=ranked[1],ranked[2]
    if first.score>=3 and (not second or first.score>=second.score+2) then
        return first.feature,#ranked,"context-score-heuristic"
    end
    return nil,#ranked,nil
end
local function featureConsistentStateEvidence(feature, changes)
    if not feature then return nil end
    local matched={}
    local strengthReset=false
    for _,change in ipairs(changes) do
        local key=change.key:lower()
        local relevant=(feature=="rebirth" and key:find("rebirth",1,true))
            or (feature=="training" and (key:find("strength",1,true) or key:find("agility",1,true)))
            or (feature=="progression" and (key:find("bubble",1,true) or key:find("capacity",1,true)))
            or (feature=="shops" and (key:find("coin",1,true) or key:find("gem",1,true)
                or key:find("currency",1,true) or key:find("cash",1,true)))
            or (feature=="pets" and (key:find("pet",1,true) or key:find("hatch",1,true) or key:find("egg",1,true)))
            or (feature=="inventory" and (key:find("inventory",1,true) or key:find("equip",1,true)))
            or (feature=="quests" and (key:find("quest",1,true) or key:find("mission",1,true)))
            or (feature=="rewards" and (key:find("reward",1,true) or key:find("claim",1,true)))
        if relevant and change.before~=change.after then
            matched[#matched+1]=change.key
        end
        if feature=="rebirth" and key:find("strength",1,true)
            and type(change.before)=="number" and type(change.after)=="number"
            and change.after<change.before then strengthReset=true end
    end
    if #matched==0 then return nil end
    table.sort(matched)
    return {rule="feature-key-changed",feature=feature,matchedKeys=matched,
        corroboratingStrengthReset=strengthReset,
        classification="feature-consistent-observable-change",
        status="candidate-needs-causal-validation",sourceAuthenticityVerified=false,
        causalityProven=false,serverVerified=false,gameplayVerified=false}
end
local function featureConsistentGuiEvidence(feature, changes)
    if feature~="rewards" then return nil end
    local matched={}
    for _,change in ipairs(changes) do
        local path=change.path:lower()
        if change.afterVisible==true and (path:find("claimed",1,true)
            or path:find("completed",1,true)) then
            matched[#matched+1]=change.path
        end
    end
    if #matched==0 then return nil end
    table.sort(matched)
    return {rule="reward-status-became-visible",feature=feature,matchedPaths=matched,
        classification="feature-consistent-observable-change",
        status="candidate-needs-causal-validation",sourceAuthenticityVerified=false,
        causalityProven=false,serverVerified=false,gameplayVerified=false}
end

local function collectOutcomeChanges(historyItem, primaryKey, windowKey)
    local merged={}
    local function append(list)
        if type(list)~="table" then return end
        for _,item in ipairs(list) do
            if type(item)=="table" then merged[#merged+1]=item end
        end
    end
    append(historyItem and historyItem[primaryKey])
    local windows=historyItem and historyItem.observationWindows
    if type(windows)=="table" then
        for _,window in ipairs(windows) do
            if type(window)=="table" then append(window[windowKey]) end
        end
    end
    return merged
end

local function backfillObservableOutcomeCandidates(history)
    local recovered=0
    if type(history)~="table" then return recovered end
    for _,historyItem in ipairs(history) do
        local feature=historyItem and historyItem.featureCandidate
        if type(historyItem)=="table" and not historyItem.observableOutcomeCandidate
            and type(feature)=="string" and feature~="" then
            local mergedState=collectOutcomeChanges(historyItem,"stateChanges","stateChanges")
            local mergedGui=collectOutcomeChanges(historyItem,"guiStateChanges","guiChanges")
            local stateEvidence=featureConsistentStateEvidence(feature,mergedState)
            local guiEvidence=featureConsistentGuiEvidence(feature,mergedGui)
            if stateEvidence or guiEvidence then
                if stateEvidence then historyItem.featureStateEvidence=stateEvidence end
                if guiEvidence then historyItem.featureGuiEvidence=guiEvidence end
                historyItem.observableOutcomeCandidate={feature=feature,
                    classification="feature-consistent-observable-change",
                    evidenceKinds={stateEvidence and "state-change" or "gui-change",
                        stateEvidence and guiEvidence and "gui-change" or nil},
                    overlappingInteractionsPossible=true,sourceAuthenticityVerified=false,
                    causalityProven=false,serverAuthorityVerified=false,gameplayVerified=false}
                historyItem.outcomeVerified=false
                recovered=recovered+1
                workflowStats.backfilledOutcomeCandidates=workflowStats.backfilledOutcomeCandidates+1
                workflowStats.completedCandidates=workflowStats.completedCandidates+1
                local item=featureInteractions[feature]
                if item then item.outcomeCandidates=(item.outcomeCandidates or 0)+1 end
            end
        end
    end
    return recovered
end

local function actionKind(name)
    local n=name:lower()
    if n:find("unequipall",1,true) then return "unequip-all" end
    if n:find("unequip",1,true) then return "unequip" end
    if n:find("blow",1,true) or n=="bubble" or n=="bubbles" then return "blow" end
    if n:find("sell",1,true) then return "sell" end
    if n:find("equip",1,true) then return "equip" end
    if n:find("craft",1,true) or n:find("fuse",1,true) then return "craft" end
    if n:find("claim",1,true) or n:find("reward",1,true) then return "claim" end
    if n:find("buy",1,true) or n:find("purchase",1,true) then return "purchase" end
    if n:find("hatch",1,true) or n=="egg" then return "hatch" end
    if n:find("rebirth",1,true) then return "rebirth" end
    if n:find("travel",1,true) or n:find("teleport",1,true) then return "travel" end
    return nil
end
local function semanticActionKind(obj, feature)
    local direct=actionKind(obj.Name)
    if direct then return direct,"control-name" end
    local parentName=obj.Parent and obj.Parent.Name:lower() or ""
    if obj.Name:lower():find("close",1,true) or parentName:find("close",1,true)
        or obj.Name:lower():find("cancel",1,true) or parentName:find("cancel",1,true) then
        return nil,nil
    end
    local generic=obj.Name:lower()=="button" or obj.Name:lower()=="action"
        or obj.Name:lower()=="template" or obj:IsA("ProximityPrompt")
    if not generic then return nil,nil end
    local node=obj.Parent
    for depth=1,7 do
        if not node or node:IsA("ScreenGui") then break end
        local lower=node.Name:lower()
        if feature=="pets" and (lower:find("hatch",1,true) or lower:find("egg",1,true)) then
            return "hatch","bounded-feature-ancestor-name"
        end
        local kind=actionKind(node.Name)
        if kind then return kind,"bounded-ancestor-name" end
        node=node.Parent
    end
    if feature=="shops" then return "purchase","bounded-feature-default-kind" end
    if feature=="rewards" or feature=="quests" then
        return "claim","bounded-feature-default-kind"
    end
    if feature=="rebirth" then return "rebirth","bounded-feature-default-kind" end
    if feature=="travel" then return "travel","bounded-feature-default-kind" end
    return nil,nil
end
local function defaultFeatureForActionKind(kind)
    if kind=="hatch" then return "pets" end
    if kind=="rebirth" then return "rebirth" end
    if kind=="travel" then return "travel" end
    if kind=="claim" then return "rewards" end
    if kind=="purchase" then return "shops" end
    if kind=="sell" then return "inventory" end
    if kind=="blow" or kind=="craft" then return "progression" end
    return nil
end
local function workflowContext(obj, feature, kind, actionSource)
    local names, node={},obj
    for i=1,9 do
        if not node then break end
        names[#names+1]=node.Name:sub(1,60)
        node=node.Parent
    end
    return {feature=feature, control=obj.Name:sub(1,80), ancestry=names,
        contextTokens=contextTokensForNames(names),
        kind=kind, actionSource=actionSource, clientOnly=true}
end
local function classifyInteraction(obj,path)
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
    local contextualFeature, contextualCount, contextualSource =
        scoredFeatureFromInteractionContext(obj,path)
    if contextualFeature then
        return contextualFeature,contextualCount,contextualSource
    end
    return nil,contextualCount or 0,"unattributed"
end
local function linkWorkflow(obj, feature, sequence)
    local name=obj.Name:lower()
    local isYes=name=="yesbutton" or name=="yes" or name=="confirmbutton"
        or name=="confimbutton" or name=="confirm" or name=="acceptbutton"
        or name=="accept" or name=="okbutton" or name=="ok"
    local isNo=name=="nobutton" or name=="no" or name=="cancelbutton"
        or name=="cancel" or name=="declinebutton" or name=="decline"
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
    local contextNames={}
    for i=1,9 do
        if not node then break end
        contextNames[#contextNames+1]=node.Name
        local n=node.Name:lower()
        if n:find("confirm",1,true) or n:find("confim",1,true)
            or n:find("choice",1,true) or n:find("prompt",1,true)
            or n:find("purchase",1,true) or n:find("unlock",1,true)
            or n=="travelareanewmenu" or n=="rebirthnewmenu" then
            dialog=true
            menuName=node.Name
        end
        node=node.Parent
    end
    if (isYes or isNo) and dialog then
        local bestIndex=nil
        local matchConfidence="context-and-time-heuristic"
        for i=#pendingActions,1,-1 do
            local pending=pendingActions[i]
            if (contextFeature and pending.feature==contextFeature)
                or (menuName and menuName:lower():find(pending.kind,1,true))
                or (pending.kind=="sell" and menuName and menuName:lower():find("sell",1,true)) then
                bestIndex=i
                break
            end
        end
        if not bestIndex then
            local contextTokens=contextTokensForNames(contextNames)
            local bestScore=0
            if #contextTokens>0 then
                for i=#pendingActions,1,-1 do
                    local pending=pendingActions[i]
                    local age=now-pending.clock
                    if age<=8 and (not contextFeature or not pending.feature or pending.feature==contextFeature) then
                        local overlap=contextTokenOverlap(contextTokens,pending.contextTokens)
                        if overlap>bestScore then
                            bestScore=overlap
                            bestIndex=i
                        end
                    end
                end
            end
            if bestIndex and bestScore>=2 then
                matchConfidence="context-token-overlap-heuristic"
            else
                bestIndex=nil
            end
        end
        if bestIndex then
            local previous=table.remove(pendingActions,bestIndex)
            if isNo then workflowStats.cancelled=workflowStats.cancelled+1
            else workflowStats.linkedConfirmations=workflowStats.linkedConfirmations+1 end
            return {phase=isNo and "cancelled" or "confirmed",linkedSequence=previous.sequence,
                inferredFeature=previous.feature,action=previous.kind,context=previous.context,
                dialog=menuName,confidence=matchConfidence,verified=false}
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
    local kind, actionSource = semanticActionKind(obj,feature)
    if kind then
        local inferredFeature=feature or defaultFeatureForActionKind(kind)
        local context=workflowContext(obj,inferredFeature,kind,actionSource)
        local bestPending=nil
        local bestOverlap=0
        for i=#pendingActions,1,-1 do
            local pending=pendingActions[i]
            local age=now-pending.clock
            if age>=0 and age<=FOLLOWUP_LINK_MAX_AGE_SECONDS and pending.sequence<sequence
                and (not inferredFeature or not pending.feature or pending.feature==inferredFeature) then
                local overlap=contextTokenOverlap(context.contextTokens,pending.contextTokens)
                if overlap>bestOverlap then
                    bestOverlap=overlap
                    bestPending=pending
                end
            end
        end
        pendingActions[#pendingActions+1]={clock=now,sequence=sequence,feature=inferredFeature,
            kind=kind,context=context,contextTokens=context.contextTokens}
        if #pendingActions>MAX_PENDING_ACTIONS then table.remove(pendingActions,1) end
        if bestPending and bestOverlap>=FOLLOWUP_LINK_MIN_CONTEXT_OVERLAP then
            workflowStats.linkedFollowups=workflowStats.linkedFollowups+1
            return {phase="followup-linked",linkedSequence=bestPending.sequence,
                linkedAction=bestPending.kind,action=kind,actionSource=actionSource,
                inferredFeature=bestPending.feature or inferredFeature,context=context,
                contextOverlap=bestOverlap,confidence="context-followup-heuristic",verified=false}
        end
        return {phase="initiated",action=kind,actionSource=actionSource,
            inferredFeature=inferredFeature,
            confidence="bounded-name-context-heuristic",verified=false}
    end
    return nil
end
local function identityIsPrefix(prefix,target)
    if type(prefix)~="table" or type(target)~="table" or #prefix>#target then return false end
    for index,segment in ipairs(prefix) do
        local candidate=target[index]
        if not candidate or segment.name~=candidate.name or segment.className~=candidate.className
            or segment.ordinal~=candidate.ordinal then return false end
    end
    return true
end
local function matchGuiRevealFollowup(targetIdentity,targetSequence,targetElapsed)
    for index=#pendingGuiReveals,1,-1 do
        local sourceAge=targetElapsed-pendingGuiReveals[index].sourceElapsed
        if sourceAge<0 or sourceAge>GUI_REVEAL_FOLLOWUP_SECONDS then
            table.remove(pendingGuiReveals,index)
            workflowStats.guiRevealCandidatesExpired=workflowStats.guiRevealCandidatesExpired+1
        end
    end
    if not targetIdentity then return nil end
    local best=nil
    for _,candidate in ipairs(pendingGuiReveals) do
        if candidate.sourceSequence<targetSequence
            and identityIsPrefix(candidate.revealedPathIdentity,targetIdentity)
            and (not best or #candidate.revealedPathIdentity>#best.revealedPathIdentity
                or (#candidate.revealedPathIdentity==#best.revealedPathIdentity
                    and candidate.observedClock>best.observedClock)) then
            best=candidate
        end
    end
    if not best then return nil end
    workflowStats.guiRevealFollowups=workflowStats.guiRevealFollowups+1
    return {sourceSequence=best.sourceSequence,sourcePath=best.sourcePath,
        sourcePathIdentity=best.sourcePathIdentity,revealedPath=best.revealedPath,
        revealedPathIdentity=best.revealedPathIdentity,
        sourceObservationWindowSeconds=best.observationWindowSeconds,
        elapsedSinceSourceSeconds=math.floor((targetElapsed-best.sourceElapsed)*1000+0.5)/1000,
        classification="observed-gui-reveal-descendant-followup",
        explicitlyLinked=false,temporalCorrelationOnly=true,causalityProven=false,
        runtimeVerified=false,gameplayVerified=false}
end
local function registerGuiRevealCandidates(changes,historyItem,observationWindowSeconds)
    for _,change in ipairs(changes) do
        if change.afterVisible==true and change.beforeVisible~=true and change.pathIdentity
            and historyItem.pathIdentity then
            pendingGuiReveals[#pendingGuiReveals+1]={observedClock=os.clock(),
                sourceSequence=historyItem.sequence,sourcePath=historyItem.path,
                sourcePathIdentity=historyItem.pathIdentity,sourceElapsed=historyItem.sessionElapsedSeconds,
                revealedPath=change.path,revealedPathIdentity=change.pathIdentity,
                observationWindowSeconds=observationWindowSeconds}
            workflowStats.guiRevealCandidates=workflowStats.guiRevealCandidates+1
            if #pendingGuiReveals>MAX_PENDING_GUI_REVEALS then
                table.remove(pendingGuiReveals,1)
                workflowStats.guiRevealCandidatesDropped=workflowStats.guiRevealCandidatesDropped+1
            end
        end
    end
end

local function relevantActionEvidence(feature, workflow, changes)
    local kind=workflow and workflow.action
    if not kind and feature=="rebirth" then kind="rebirth" end
    local signals={}
    for _,change in ipairs(changes) do
        local key=change.key:lower()
        if key:find("bubble",1,true) or key:find("capacity",1,true) then
            signals[#signals+1]="progression-resource-change"
        elseif key:find("strength",1,true) then
            signals[#signals+1]="strength-change"
        elseif key:find("rebirth",1,true) then
            signals[#signals+1]="rebirth-change"
        elseif key:find("hatch",1,true) or key:find("egg",1,true) then
            signals[#signals+1]="hatch-related-value-change"
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
    elseif kind=="blow" then
        for _,change in ipairs(changes) do
            local key=change.key:lower()
            if (key:find("bubble",1,true) or key:find("capacity",1,true))
                and type(change.before)=="number" and type(change.after)=="number"
                and change.after>change.before then corroborated=true end
        end
    elseif kind=="sell" then
        local resourceDecrease,currencyIncrease=false,false
        for _,change in ipairs(changes) do
            local key=change.key:lower()
            if type(change.before)=="number" and type(change.after)=="number" then
                if (key:find("bubble",1,true) or key:find("capacity",1,true))
                    and change.after<change.before then resourceDecrease=true end
                if (key:find("coin",1,true) or key:find("gem",1,true)
                    or key:find("currency",1,true) or key:find("cash",1,true))
                    and change.after>change.before then currencyIncrease=true end
            end
        end
        corroborated=resourceDecrease and currencyIncrease
    elseif kind=="equip" or kind=="unequip" or kind=="unequip-all" or kind=="craft" then
        for _,signal in ipairs(signals) do
            if signal=="inventory-related-value-change" then corroborated=true end
        end
    elseif kind=="hatch" then
        for _,signal in ipairs(signals) do
            if signal=="hatch-related-value-change" or signal=="inventory-related-value-change" then
                corroborated=true end
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

local function interactionDescriptor(obj,root,label)
    if obj:IsA("ProximityPrompt") then
        local anchor=obj.Parent
        for _=1,5 do
            if not anchor or anchor:IsA("BasePart") then break end
            anchor=anchor.Parent
        end
        return {actionText=tostring(obj.ActionText):sub(1,120),
            objectText=tostring(obj.ObjectText):sub(1,120),enabled=obj.Enabled,
            holdDuration=obj.HoldDuration,maxActivationDistance=obj.MaxActivationDistance,
            keyboardKeyCode=obj.KeyboardKeyCode.Name,gamepadKeyCode=obj.GamepadKeyCode.Name,
            anchorPath=anchor and watchPath(anchor,root,label) or nil,
            anchorPosition=anchor and anchor:IsA("BasePart") and watchVec(anchor.Position) or nil}
    end
    if obj:IsA("GuiButton") then
        return guiControlSnapshot(obj)
    end
    if obj:IsA("ClickDetector") then
        return {maxActivationDistance=obj.MaxActivationDistance}
    end
    if obj:IsA("Tool") then
        return {tooltip=tostring(obj.ToolTip):sub(1,120):gsub("[%c]"," "),
            requiresHandle=obj.RequiresHandle,canBeDropped=obj.CanBeDropped,
            enabled=obj.Enabled,manualActivationOnly=obj.ManualActivationOnly}
    end
    return nil
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
    elseif obj:IsA("Tool") then
        signal, controlType = obj.Activated, "Tool.Activated"
    end
    if not signal then return end
    interactionObserved[obj] = true
    interactionObservedCount = interactionObservedCount + 1
    observerStats.listenersAttached = observerStats.listenersAttached + 1
    local preActivationCapture=nil
    local function capturePreActivation(source,maxAge)
        local ok,state,identities,guiState,position=pcall(function()
            local values,valueIdentities=safeInteractionState()
            local rootPart=player.Character and player.Character:FindFirstChild("HumanoidRootPart")
            return values,valueIdentities,safeNearbyGuiState(obj),rootPart and rootPart.Position or nil
        end)
        if not ok then
            observerStats.preActivationCaptureFailures=observerStats.preActivationCaptureFailures+1
            return
        end
        preActivationCapture={clock=os.clock(),source=source,maxAge=maxAge,
            state=state,stateIdentities=identities,guiState=guiState,position=position}
        observerStats.preActivationCaptures=observerStats.preActivationCaptures+1
    end
    local function registerPreActivation(preSignal,source,maxAge,filter)
        local ok,preConnection=pcall(function()
            return preSignal:Connect(function(input)
                if not alive or not interactionObserveEnabled then return end
                if filter and not filter(input) then return end
                capturePreActivation(source,maxAge)
            end)
        end)
        if ok then
            table.insert(watchConnections,preConnection)
            observerStats.preActivationListenersAttached=
                observerStats.preActivationListenersAttached+1
        else observerStats.bindingErrors=observerStats.bindingErrors+1 end
    end
    if obj:IsA("GuiButton") then
        registerPreActivation(obj.InputBegan,"GuiButton.InputBegan",2,function(input)
            return input.UserInputType==Enum.UserInputType.MouseButton1
                or input.UserInputType==Enum.UserInputType.Touch
                or input.KeyCode==Enum.KeyCode.ButtonA
                or input.KeyCode==Enum.KeyCode.Return
                or input.KeyCode==Enum.KeyCode.Space
        end)
    elseif obj:IsA("ProximityPrompt") then
        registerPreActivation(obj.PromptButtonHoldBegan,"ProximityPrompt.PromptButtonHoldBegan",
            math.max(2,obj.HoldDuration+1))
    elseif obj:IsA("Tool") then
        registerPreActivation(obj.Equipped,"Tool.Equipped",5)
    end

    local connection = signal:Connect(function()
        if not alive or not interactionObserveEnabled then return end
        interactionEventCount = interactionEventCount + 1
        local activationClock=os.clock()
        local sessionElapsedSeconds=math.floor((activationClock-sessionStartedClock)*1000+0.5)/1000
        autoEvidenceLastInteraction = activationClock
        observerStats.callbacksFired = observerStats.callbacksFired + 1
        observerStats.lastCallbackAt = os.date("!%Y-%m-%dT%H:%M:%SZ")
        observerStats.lastEventPath = path:sub(1,180)
        local feature, matchCount, attributionSource = classifyInteraction(obj,path)
        if feature then
            attributedInteractionCount = attributedInteractionCount + 1
        else
            unattributedInteractionCount = unattributedInteractionCount + 1
        end
        local workflow = linkWorkflow(obj, feature, observationSequence + 1)
        if workflow and workflow.inferredFeature and not feature then
            feature=workflow.inferredFeature
            attributionSource=(workflow.phase=="followup-linked")
                and "linked-followup-heuristic" or "linked-confirmation-heuristic"
            unattributedInteractionCount=unattributedInteractionCount-1
            attributedInteractionCount=attributedInteractionCount+1
        end
        local captured=preActivationCapture
        preActivationCapture=nil
        local captureAge=captured and activationClock-captured.clock or nil
        local before,beforeStateIdentities,beforeGui,beforePosition,baselineSource
        if captured and captureAge>=0 and captureAge<=captured.maxAge then
            before=captured.state;beforeStateIdentities=captured.stateIdentities
            beforeGui=captured.guiState;beforePosition=captured.position
            baselineSource=captured.source
            observerStats.preActivationBaselinesUsed=observerStats.preActivationBaselinesUsed+1
        else
            if captured then
                observerStats.stalePreActivationCaptures=observerStats.stalePreActivationCaptures+1
            end
            before,beforeStateIdentities=safeInteractionState()
            beforeGui=safeNearbyGuiState(obj)
            local rootPart=player.Character and player.Character:FindFirstChild("HumanoidRootPart")
            beforePosition=rootPart and rootPart.Position or nil
            baselineSource="activation-callback-fallback"
            observerStats.callbackBaselinesUsed=observerStats.callbackBaselinesUsed+1
        end
        local targetPathIdentity=interactionPathIdentity(obj,root,label)
        local guiRevealFollowup=matchGuiRevealFollowup(targetPathIdentity,
            observationSequence+1,sessionElapsedSeconds)
        local explicitRecording=recordWorkflowInteraction(activationClock,sessionElapsedSeconds)
        local transactionId=explicitRecording and explicitRecording.recordingId
            or (workflow and workflow.linkedSequence) or (observationSequence+1)
        local transactionLinkSource=explicitRecording and explicitRecording.linkageSource
            or (workflow and workflow.linkedSequence and
                (workflow.phase=="followup-linked" and "observed-followup-link"
                    or "observed-confirmation-link")
                or "singleton-event")
        local historyItem = {
            path=path:sub(1,400), pathIdentity=targetPathIdentity,
            featureCandidate=feature, attribution=attributionSource, controlType=controlType,
            observedAt=observerStats.lastCallbackAt, sequence=observationSequence + 1,
            sessionId=sessionId,sessionElapsedSeconds=sessionElapsedSeconds,
            transactionId=transactionId,
            transactionOrder=explicitRecording and explicitRecording.order or nil,
            transactionLinkSource=transactionLinkSource,
            explicitWorkflowRecording=explicitRecording,
            stateChangeCount=0, guiContext=interactionGuiContext(obj), workflow=workflow,
            guiRevealFollowup=guiRevealFollowup,
            controlMetadata=interactionDescriptor(obj,root,label),baselineSource=baselineSource,
            baselineTiming=baselineSource=="activation-callback-fallback"
                and "activation-callback" or "pre-activation",
            baselineAgeSeconds=captureAge and math.floor(captureAge*1000+0.5)/1000 or nil,
            preActivationBaselineAvailable=baselineSource~="activation-callback-fallback",
            evidenceLevel="interaction-observed", outcomeVerified=false
        }
        interactionHistory[#interactionHistory+1] = historyItem
        if #interactionHistory > MAX_INTERACTION_HISTORY then table.remove(interactionHistory, 1) end
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
        if feature then
            local item = featureInteractions[feature] or {
                count=0,stateChanges=0,temporalStateChanges=0,outcomeCandidates=0}
            item.count = item.count + 1
            featureInteractions[feature] = item
        end
        observationSequence = observationSequence + 1
        changeCount = changeCount + 1
        changeQueue[#changeQueue + 1] = {
            path = path:sub(1,400), pathIdentity=historyItem.pathIdentity, class = obj.ClassName,
            featureCandidate = feature, featureMatchCount = matchCount,
            attribution = attributionSource,
            category = "user-interaction", controlType = controlType,
            controlMetadata=historyItem.controlMetadata,baselineSource=baselineSource,
            baselineTiming=historyItem.baselineTiming,
            preActivationBaselineAvailable=historyItem.preActivationBaselineAvailable,
            action = "user-activated", observedAt = os.date("!%Y-%m-%dT%H:%M:%SZ"),
            evidence = "manual-user-interaction", sessionId = sessionId,
            sessionElapsedSeconds=sessionElapsedSeconds,snapshotId = snapshotId, sequence = observationSequence,
            transactionId=transactionId,transactionOrder=historyItem.transactionOrder,
            transactionLinkSource=historyItem.transactionLinkSource
        }
        local seenStateKeys={}
        local seenGuiKeys={}
        for _,delaySeconds in ipairs(OBSERVATION_WINDOWS) do
            pendingObservationEvents=pendingObservationEvents+1
            task.delay(delaySeconds, function()
                pendingObservationEvents=math.max(0,pendingObservationEvents-1)
                if not alive then return end
                local ok,err=pcall(function()
                    local after,afterStateIdentities=safeInteractionState()
                    local guiChanges=compareNearbyGuiState(beforeGui,safeNearbyGuiState(obj))
                    local changes={}
                    for key,value in pairs(before) do
                        if after[key]~=nil and after[key]~=value and #changes<MAX_STATE_CHANGES then
                            local identity=afterStateIdentities[key]
                            changes[#changes+1]={key=key,before=value,after=after[key],stateIdentity=identity,
                                stateIdentityStatus=identity and "component-resolved" or "unavailable"}
                        end
                    end
                    for key,value in pairs(after) do
                        if before[key]==nil and #changes<MAX_STATE_CHANGES then
                            local identity=afterStateIdentities[key]
                            changes[#changes+1]={key=key,transition="added",after=value,stateIdentity=identity,
                                stateIdentityStatus=identity and "component-resolved" or "unavailable"}
                        end
                    end
                    for key,value in pairs(before) do
                        if after[key]==nil and #changes<MAX_STATE_CHANGES then
                            local identity=beforeStateIdentities[key]
                            changes[#changes+1]={key=key,transition="removed",before=value,stateIdentity=identity,
                                stateIdentityStatus=identity and "component-resolved" or "unavailable"}
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
                    registerGuiRevealCandidates(freshGui,historyItem,delaySeconds)
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
                    local featureStateEvidence=featureConsistentStateEvidence(feature,transactionFresh)
                    local featureGuiEvidence=featureConsistentGuiEvidence(feature,freshGui)
                    if feature=="travel" and distance and distance>100 and not historyItem.travelCandidate then
                        historyItem.travelCandidate=true
                        workflowStats.travelCandidates=workflowStats.travelCandidates+1
                    end
                    if featureGuiEvidence and not historyItem.rewardClaimGuiCandidate then
                        historyItem.rewardClaimGuiCandidate=true
                        workflowStats.rewardClaimGuiCandidates=workflowStats.rewardClaimGuiCandidates+1
                    end
                    if featureStateEvidence then historyItem.featureStateEvidence=featureStateEvidence end
                    if featureGuiEvidence then historyItem.featureGuiEvidence=featureGuiEvidence end
                    if (featureStateEvidence or featureGuiEvidence) and not historyItem.observableOutcomeCandidate then
                        historyItem.observableOutcomeCandidate={feature=feature,
                            classification="feature-consistent-observable-change",
                            evidenceKinds={featureStateEvidence and "state-change" or "gui-change",
                                featureStateEvidence and featureGuiEvidence and "gui-change" or nil},
                            overlappingInteractionsPossible=true,sourceAuthenticityVerified=false,
                            causalityProven=false,serverAuthorityVerified=false,gameplayVerified=false}
                        historyItem.outcomeVerified=false
                        workflowStats.completedCandidates=workflowStats.completedCandidates+1
                        local item=feature and featureInteractions[feature]
                        if item then item.outcomeCandidates=item.outcomeCandidates+1 end
                    end
                    local window={seconds=delaySeconds,stateChanges=freshState,
                        stateChangeCount=#freshState,guiChanges=freshGui,
                        guiChangeCount=#freshGui,travelDistanceStuds=distance,
                        baselineSource=baselineSource,baselineTiming=historyItem.baselineTiming,
                        preActivationBaselineAvailable=historyItem.preActivationBaselineAvailable,
                        featureStateEvidence=featureStateEvidence,
                        featureGuiEvidence=featureGuiEvidence,actionEvidence=evidence}
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
                        observerStats.stateDeltaEvents=observerStats.stateDeltaEvents+1
                        if feature then
                            local item=featureInteractions[feature]
                            if item then
                                item.temporalStateChanges=item.temporalStateChanges+1
                                if featureStateEvidence then item.stateChanges=item.stateChanges+1 end
                            end
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
                            baselineSource=baselineSource,baselineTiming=historyItem.baselineTiming,
                            preActivationBaselineAvailable=historyItem.preActivationBaselineAvailable,
                            observationWindowSeconds=delaySeconds,changes=transactionFresh,
                            guiChanges=freshGui,travelDistanceStuds=distance,
                            featureStateEvidence=featureStateEvidence,
                            featureGuiEvidence=featureGuiEvidence,
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
        stopWorkflowRecording("observer-disabled")
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


local function buildWorkflowGenerationDiagnostics(totalInteractions, attributedInteractions,
        unattributedInteractions)
    local blockers = {}
    local linkedWorkflowEvents = workflowStats.linkedConfirmations + workflowStats.linkedFollowups
    if totalInteractions <= 0 then
        blockers[#blockers+1] = "no-interaction-events-observed"
    else
        if attributedInteractions <= 0 then
            blockers[#blockers+1] = "no-feature-attributed-interactions"
        end
        if workflowRecordingStats.started <= 0 then
            blockers[#blockers+1] = "explicit-workflow-recording-not-armed"
        end
        if linkedWorkflowEvents <= 0 then
            blockers[#blockers+1] = "no-linked-confirmation-events"
        end
        if workflowStats.actionOutcomesCorroborated <= 0 then
            blockers[#blockers+1] = "no-corroborated-action-outcomes"
        end
        if workflowStats.completedCandidates <= 0 then
            blockers[#blockers+1] = "no-completed-workflow-candidates"
        end
        if workflowStats.multiWindowSamples <= 0 then
            blockers[#blockers+1] = "no-observation-window-samples"
        end
        if unattributedInteractions > 0 then
            blockers[#blockers+1] = "some-interactions-remain-unattributed"
        end
    end
    return {
        available = true,
        interactionEvents = totalInteractions,
        attributedInteractions = attributedInteractions,
        unattributedInteractions = unattributedInteractions,
        linkedConfirmations = workflowStats.linkedConfirmations,
        linkedFollowups = workflowStats.linkedFollowups,
        linkedWorkflowEvents = linkedWorkflowEvents,
        corroboratedActionOutcomes = workflowStats.actionOutcomesCorroborated,
        completedWorkflowCandidates = workflowStats.completedCandidates,
        explicitWorkflowRecordings = workflowRecordingStats.started,
        blockers = blockers,
        readinessImpact = "limitations-only",
        causalProof = false,
        runtimeVerified = false,
        gameplayVerified = false,
    }
end

local function inspect(requestType, featureRequest)
    if running or uploading then
        status.Text = "Wait for current scan/upload or press SCAN to cancel"
        return false
    end
    if pendingParts and #pendingParts > 0 then
        for i = 1, #pendingParts do
            if not pendingAcknowledged[i] then
                status.Text = "Unsent parts remain; press SEND JSON to retry before rescanning"
                return false
            end
        end
    end

    stopWorkflowRecording("scan-started")
    scanInvocationCount = scanInvocationCount + 1
    scanRequestType = requestType == "startup-baseline" and "startup-baseline"
        or (requestType == "auto-evidence" and "auto-evidence"
        or (requestType == "feature-request" and "feature-request" or "manual"))
    scanGeneration = scanGeneration + 1
    local generation = scanGeneration
    running = true
    siblingContextCache = setmetatable({}, {__mode="k"})
    local profile = activeScanProfile()
    status.Text = "Scanning (" .. profile.label .. ")..."

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
                featureRequest = featureRequest,
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


            local rootInstances = {
                ReplicatedStorage = game:GetService("ReplicatedStorage"),
                ReplicatedFirst = game:GetService("ReplicatedFirst"),
                Workspace = workspace,
                PlayerGui = player:FindFirstChild("PlayerGui"),
                LocalPlayer = player,
                Character = player.Character,
                Lighting = game:GetService("Lighting"),
                Teams = game:GetService("Teams"),
                SoundService = game:GetService("SoundService")
            }
            local roots = {}
            local plannedRoots = {}
            for _, label in ipairs(profile.rootLabels) do
                plannedRoots[#plannedRoots + 1] = label
                roots[#roots + 1] = {instance = rootInstances[label], label = label}
            end
            report.scanStats = {
                scanned = 0, eligible = 0, recorded = 0, omitted = 0,
                mode = profile.scanMode, profile = activeScanProfileId,
                quickTargeted = profile.quickTargeted == true,
                recordingPolicy = profile.recordingPolicy,
                plannedRoots = plannedRoots,
                byCategory = {}, byRoot = {},
                rootCoverage = {}, byClass = {},
                valueBase = {scanned = 0, recorded = 0, byClass = {}},
                guiControls = {buttons = 0, textBoxes = 0, prompts = 0, clickDetectors = 0},
                scriptCandidates = {modules = 0, localScripts = 0, scripts = 0, controllers = 0},
                omissions = {overlappingRoots = 0, invalidPath = 0, inspectorSelf = 0, profileFiltered = 0},
                performance = {rootSeconds = {}, yieldCount = 0, scanSeconds = 0},
                pathCollisionsResolved = 0,
                siblingContextLimit = profile.quickTargeted and 0 or 8,
                limitations = {
                    scriptSource = "not-read", serverState = "not-visible", remotePayloads = "not-collected",
                    coverage = profile.quickTargeted and "quick-targeted-not-full-object-inventory"
                        or "full-client-visible-root-inventory"
                }
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
            local requiredRoots = profile.requiredRoots
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
                        if not alive or generation ~= scanGeneration then break end
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
                            local includeByProfile = shouldRecordObjectForProfile(profile, obj, path, spec.label)
                            if not includeByProfile then
                                report.scanStats.omitted = report.scanStats.omitted + 1
                                coverage.omitted = coverage.omitted + 1
                                report.scanStats.omissions.profileFiltered =
                                    report.scanStats.omissions.profileFiltered + 1
                            else
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
                            enrichEntry(entry, obj, profile)
                            if obj:IsA("ModuleScript") or obj:IsA("LocalScript") or obj:IsA("Script") then
                                local n = string.lower(obj.Name)
                                if n:find("controller",1,true) or n:find("manager",1,true)
                                    or n:find("service",1,true) or n:find("handler",1,true) then
                                    entry.controllerCandidate = true
                                    entry.controllerEvidence = "name-based-candidate-only"
                                end
                            end
                            if not profile.quickTargeted then
                                local tagOk, tags = pcall(function()
                                    return game:GetService("CollectionService"):GetTags(obj)
                                end)
                                if tagOk and type(tags) == "table" and #tags > 0 then
                                    entry.tags = {}
                                    for ti = 1, math.min(#tags, 20) do
                                        entry.tags[ti] = tostring(tags[ti]):sub(1,80)
                                    end
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
                            end
                        else
                            report.scanStats.omitted = report.scanStats.omitted + 1
                            coverage.omitted = coverage.omitted + 1
                            if not path then report.scanStats.omissions.invalidPath = report.scanStats.omissions.invalidPath + 1 end
                        end
                        if os.clock() >= yieldDeadline then
                            status.Text = "Scanning " .. report.scanStats.scanned .. " objects (" .. profile.label .. ")..."
                            report.scanStats.performance.yieldCount = report.scanStats.performance.yieldCount + 1
                            task.wait()
                            yieldDeadline = os.clock() + SCAN_YIELD_BUDGET_SECONDS
                        end
                        end
                        if generation ~= scanGeneration then
                            coverage.error = "scan cancelled"
                            scanAborted = true
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
                if generation ~= scanGeneration then break end
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
            local scanCancelled = generation ~= scanGeneration
            if scanCancelled then scanAborted = true end
            local scanComplete = not scanAborted and requiredRootsPresent
                and rootAccountingValid
                and report.scanStats.scanned == report.scanStats.recorded + report.scanStats.omitted
            report.scanStats.complete = scanComplete
            report.featureEvidence = buildFeatureEvidence(report.objects)
            report.featureReadiness = buildReadiness(report.featureEvidence, interactionEventCount)
            local recoveredOutcomeCandidates=backfillObservableOutcomeCandidates(interactionHistory)
            report.interactionDiagnostics = {
                scanRequestType=scanRequestType, scanInvocationCount=scanInvocationCount,
                scanProfile=activeScanProfileId, scanMode=profile.scanMode,
                quickTargeted=profile.quickTargeted==true,
                profileFilteredObjects=report.scanStats.omissions.profileFiltered,
                observerReady=interactionObserveEnabled and observerStats.sweepCompleted,
                enabledAtScan=interactionObserveEnabled, listenersAttached=observerStats.listenersAttached,
                callbacksFired=observerStats.callbacksFired, stateDeltaEvents=observerStats.stateDeltaEvents,
                preActivationListenersAttached=observerStats.preActivationListenersAttached,
                preActivationCaptures=observerStats.preActivationCaptures,
                preActivationBaselinesUsed=observerStats.preActivationBaselinesUsed,
                callbackBaselinesUsed=observerStats.callbackBaselinesUsed,
                stalePreActivationCaptures=observerStats.stalePreActivationCaptures,
                preActivationCaptureFailures=observerStats.preActivationCaptureFailures,
                baselineTimingPolicy="pre-activation when a bounded supported signal is fresh; otherwise explicit activation-callback fallback",
                bindingErrors=observerStats.bindingErrors, sweepCompleted=observerStats.sweepCompleted,
                sweepScanned=observerStats.sweepScanned, lastEventPath=observerStats.lastEventPath,
                pendingObservationEvents=pendingObservationEvents,
                observationWindowsExpected=interactionEventCount*#OBSERVATION_WINDOWS,
                observationWindowsCompleted=workflowStats.multiWindowSamples,
                observationWindowsFailed=workflowStats.observationFailures,
                observationWindowAccountingValid=
                    workflowStats.multiWindowSamples+workflowStats.observationFailures
                        +pendingObservationEvents==interactionEventCount*#OBSERVATION_WINDOWS,
                evidenceLossPossible=pendingObservationEvents>0
                    or workflowStats.observationFailures>0
                    or observerStats.preActivationCaptureFailures>0
                    or observerStats.callbackBaselinesUsed>0,
                cumulativeChangeEvents=changeCount, totalInteractionEvents=interactionEventCount,
                attributedEvents=attributedInteractionCount, unattributedEvents=unattributedInteractionCount,
                recentInteractions=interactionHistory, interactionHistoryLimit=MAX_INTERACTION_HISTORY,
                workflowStats=workflowStats,
                backfilledOutcomeCandidates=recoveredOutcomeCandidates,
                workflowGenerationDiagnostics=buildWorkflowGenerationDiagnostics(
                    interactionEventCount, attributedInteractionCount, unattributedInteractionCount),
                pendingWorkflowCount=#pendingActions,
                pendingGuiRevealCount=#pendingGuiReveals,
                workflowRecordingActive=workflowRecording.active,
                workflowRecordingStats=workflowRecordingStats,
                workflowRecordingLimits={maxDurationSeconds=WORKFLOW_RECORDING_SECONDS,
                    maxEvents=MAX_WORKFLOW_RECORDING_EVENTS},
                workflowRecordingPolicy="explicit-user-armed-ordering-only-not-causal-proof",
                verificationPolicy="read-only-client-corroboration-not-server-proof",
                transactionDeduplication="linked-workflow-sequence",
                guiRevealFollowupPolicy="visible-transition-plus-exact-descendant-identity-within-15-seconds-review-only",
                inventoryDiscovery="candidate-first-gui-sampling-parent-aware-pagination",
                evidenceLevels={"interaction-observed","temporal-state-change-observed",
                    "feature-consistent-observable-change","gameplay-outcome-verified"},
                gameplayOutcomesVerified=0,
                completedCandidateDefinition="feature-consistent observable change; causality and gameplay remain unverified",
                actionOutcomeDefinition="bounded client-state correlation; not server or causal proof",
                stateSnapshotScope={"leaderstats","Data","bounded non-private LocalPlayer ValueBase candidates"},
                stateSnapshotCandidateCount=#stateSnapshotCandidates,
                stateSnapshotMaxValues=MAX_STATE_SNAPSHOT_CANDIDATES,
                observationWindowsSeconds=OBSERVATION_WINDOWS,
                observationIdleSeconds=AUTO_EVIDENCE_IDLE_SECONDS,
                scanCancelled=scanCancelled,
                stateChangeLimit=MAX_STATE_CHANGES,
                featureEvidenceRules={"feature-key-changed","reward-status-became-visible",
                    "post-capture-window-evidence-backfill"},
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
                scanProfile=activeScanProfileId, quickTargeted=profile.quickTargeted==true,
                coveragePolicy=profile.recordingPolicy,
                automaticRescans=autoEvidenceRescans, lastFailure=autoEvidenceLastFailure,
                capturedInteractionCount=interactionEventCount,
                indexIntegrityWarning="Use receiver GET /reports/READ_KEY/SCAN_ID/integrity to verify object indexing",
                limitations={"Read-only client observation","No script source or server authority","No proof of replayable gameplay actions"}
            }
            report.diagnostics = {
                complete = scanComplete,
                scanCancelled = scanCancelled,
                completenessBasis = "required-root-success-and-object-accounting",
                requiredRootsPresent = requiredRootsPresent,
                rootAccountingValid = rootAccountingValid,
                scannedObjects = report.scanStats.scanned,
                recordedObjects = report.scanStats.recorded,
                omittedObjects = report.scanStats.omitted,
                profileFilteredObjects = report.scanStats.omissions.profileFiltered,
                scanProfile = activeScanProfileId,
                targetedCoverage = profile.quickTargeted == true,
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

        if not alive or generation ~= scanGeneration then return end

        if not ok then
            status.Text = "Scan error: " .. tostring(result)
            siblingContextCache = nil
            running = false
            return
        end
        if result and result.diagnostics and result.diagnostics.scanCancelled then
            status.Text = "Scan cancelled"
            siblingContextCache = nil
            running = false
            return
        end

        local encoded, resultData = pcall(function()
            -- Large universal scans must never be encoded as one JSON document.
            -- The receiver accepts bounded parts; keep only a small clipboard manifest.
            local parts, reportScanId = prepareParts(result)
            uploadState={attempted=false,status="not-attempted",acknowledgedParts=0,
                expectedParts=#parts,lastError=nil}
            local manifestData = {
                version = VERSION, gameName = result.gameName,
                scanId = reportScanId,
                sessionId = result.sessionId, snapshotId = result.snapshotId,
                featureEvidence = result.featureEvidence,
                featureReadiness = result.featureReadiness,
                interactionDiagnostics = result.interactionDiagnostics,
                automationDiagnostics = result.automationDiagnostics,
                featureSnapshotDelta = result.featureSnapshotDelta,
                placeId = result.placeId, inspectedAt = result.inspectedAt,
                featureRequest = result.featureRequest,
                objectCount = #result.objects, partCount = #parts,
                expectedParts = #parts, uploadedParts = 0,
                reportTransport = uploadSnapshot("pre-upload"),
                localExport = {attempted=false,status="not-attempted",exportedParts=0,
                    expectedParts=#parts,manifestSaved=false,manifestWriteAttempts=0,
                    localPartContentDigestsComputed=false},
                localPerformance = result.localPerformance,
                scanStats = result.scanStats, diagnostics = result.diagnostics,
                note = "Inspection snapshot is uploaded in numbered parts; manifest includes scan profile and coverage diagnostics"
            }
            local manifest = encodeStage("scan-manifest", manifestData)
            return {json=manifest,parts=parts,manifest=manifestData,scanId=reportScanId}
        end)
        if generation ~= scanGeneration then
            running = false
            return
        end
        if encoded then
            snapshotId = result.snapshotId
            last = resultData.json
            pendingParts = resultData.parts
            pendingManifest = resultData.manifest
            pendingAcknowledged = {}
            local scanSeconds = result.scanStats and result.scanStats.performance
                and result.scanStats.performance.scanSeconds or 0
            local packageSeconds = result.localPerformance and result.localPerformance.serializationSeconds or 0
            local plannedRootCount = result.scanStats and type(result.scanStats.plannedRoots)=="table"
                and #result.scanStats.plannedRoots or #ROOT_LABELS
            status.Text = (result.diagnostics.complete and "Snapshot complete - " or "SNAPSHOT PARTIAL - ")
                .. #result.objects .. " entries in " .. #pendingParts .. " part(s); snapshot "
                .. tostring(scanSeconds) .. "s; packaging " .. tostring(packageSeconds)
                .. "s; upload " .. uploadAttemptStage()
            output.Text =
                "Game: " .. tostring(result.gameName or "Unknown")
                .. "\\nPlaceId: " .. tostring(result.placeId)
                .. "\\nScan ID: " .. tostring(resultData.scanId)
                .. "\\nScan profile: " .. tostring(result.scanStats and result.scanStats.profile or activeScanProfileId)
                .. "\\nEntries: " .. #result.objects
                .. "\\nRemotes: "
                .. tostring(result.counts.RemoteEvent or 0) .. " events, "
                .. tostring(result.counts.RemoteFunction or 0) .. " functions"
                .. "\\nParts: " .. #pendingParts
                .. "\\nRoots: " .. tostring(plannedRootCount)
                .. "\\nSnapshot stage: " .. (result.diagnostics.complete and "complete" or "partial")
                .. "\\nPackaging stage: prepared " .. #pendingParts .. " numbered parts"
                .. "\\nUpload stage: " .. uploadAttemptStage()
                .. "\\nInteraction observer: " .. (interactionObserveEnabled and "ON" or "OFF")
                .. "\\nObserver callbacks: " .. tostring(observerStats.callbacksFired)
                .. "\\nObserver sweep: " .. (observerStats.sweepCompleted and "COMPLETE" or "NOT COMPLETE")
                .. "\\nObserver activations: " .. tostring(observerStats.activationCount)
                .. "\\nScan type: " .. scanRequestType
                .. "\\nObserver ready: " .. tostring(interactionObserveEnabled and observerStats.sweepCompleted)
                .. "\\nAUTO-SEND: " .. (autoSend and "ON" or "OFF")
            refreshGeneratedHandoff("Scan complete")
            if autoSend and validEndpoint(endpoint) then transmit() end
        else
            status.Text = "JSON error: " .. tostring(resultData)
        end
        running = false
    end)
    return true
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
local workflowRecordToggle = create("TextButton", {
    Name="WorkflowRecordToggle",Text="RECORD FLOW: OFF",
    Size=UDim2.fromOffset(120,26),Position=UDim2.fromOffset(380,201),
    TextSize=10,TextColor3=Color3.fromRGB(245,245,245),
    BackgroundColor3=Color3.fromRGB(85,85,105),ZIndex=4
},panel)
refreshWorkflowRecorder=function(reason)
    if workflowRecording.active then
        workflowRecordToggle.Text="RECORD: "..workflowRecording.eventCount.."/"..MAX_WORKFLOW_RECORDING_EVENTS
        workflowRecordToggle.BackgroundColor3=Color3.fromRGB(145,90,45)
        if reason=="started" then
            status.Text="Workflow recording armed for 60 seconds or 8 interactions"
        end
    else
        workflowRecordToggle.Text="RECORD FLOW: OFF"
        workflowRecordToggle.BackgroundColor3=Color3.fromRGB(85,85,105)
        if reason=="operator-stopped" then
            status.Text="Workflow recording stopped; ordering recorded without causal proof"
        elseif reason=="event-limit" then
            status.Text="Workflow recording reached the 8-interaction limit"
        elseif reason=="duration-limit" then
            status.Text="Workflow recording reached the 60-second limit"
        end
    end
end
workflowRecordToggle.MouseButton1Click:Connect(function()
    if workflowRecording.active then
        stopWorkflowRecording("operator-stopped")
    elseif not interactionObserveEnabled or not observerStats.sweepCompleted then
        status.Text="Workflow recording unavailable until interaction observer is ready"
    else
        startWorkflowRecording()
    end
end)

local scanModeToggle = create("TextButton", {
    Name = "ScanModeToggle", Text = "SCAN MODE: FULL",
    Size = UDim2.fromOffset(120, 26), Position = UDim2.fromOffset(380, 232),
    TextSize = 10, TextColor3 = Color3.fromRGB(245,245,245),
    BackgroundColor3 = Color3.fromRGB(85,85,105), ZIndex = 4
}, panel)
local observationToggle = create("TextButton", {
    Name = "ObservationWindowToggle", Text = "OBSERVE: 12s",
    Size = UDim2.fromOffset(120, 26), Position = UDim2.fromOffset(380, 263),
    TextSize = 10, TextColor3 = Color3.fromRGB(245,245,245),
    BackgroundColor3 = Color3.fromRGB(85,85,105), ZIndex = 4
}, panel)
local evidenceHint = create("TextLabel", {
    Name = "EvidenceHint",
    Text = "Auto rescans: 0/4",
    Position = UDim2.fromOffset(379, 294),
    Size = UDim2.fromOffset(121, 36),
    BackgroundTransparency = 1,
    TextColor3 = Color3.fromRGB(205, 215, 220),
    TextSize = 10,
    TextWrapped = true,
    TextYAlignment = Enum.TextYAlignment.Top
}, panel)
local uploadHint = create("TextLabel", {
    Name = "UploadHint",
    Text = "Receiver ACK is not full integrity proof.",
    Position = UDim2.fromOffset(379, 332),
    Size = UDim2.fromOffset(121, 18),
    BackgroundTransparency = 1,
    TextColor3 = Color3.fromRGB(205, 215, 220),
    TextSize = 10,
    TextWrapped = true,
    TextYAlignment = Enum.TextYAlignment.Top
}, panel)

refreshEvidenceControls = function(reason)
    local profile = activeScanProfile()
    autoEvidenceToggle.Text = AUTO_EVIDENCE_ENABLED and "EVIDENCE: ON" or "EVIDENCE: OFF"
    autoEvidenceToggle.BackgroundColor3 = AUTO_EVIDENCE_ENABLED
        and Color3.fromRGB(50,105,85) or Color3.fromRGB(85,85,105)
    scanModeToggle.Text = "SCAN MODE: " .. profile.label
    observationToggle.Text = "OBSERVE: " .. tostring(AUTO_EVIDENCE_IDLE_SECONDS) .. "s"
    evidenceHint.Text = "Auto rescans: " .. autoEvidenceRescans .. "/" .. AUTO_EVIDENCE_MAX_RESCANS
        .. "\nCoverage: " .. (profile.quickTargeted and "targeted" or "full")
    if reason=="profile-changed" then
        status.Text = "Scan mode " .. profile.label .. " | auto rescans "
            .. AUTO_EVIDENCE_MAX_RESCANS .. " | observation " .. AUTO_EVIDENCE_IDLE_SECONDS .. "s"
    end
end

autoEvidenceToggle.MouseButton1Click:Connect(function()
    AUTO_EVIDENCE_ENABLED = not AUTO_EVIDENCE_ENABLED
    refreshEvidenceControls("evidence-toggle")
    status.Text = AUTO_EVIDENCE_ENABLED and "Automatic evidence enabled" or "Automatic evidence paused"
end)
scanModeToggle.MouseButton1Click:Connect(function()
    local nextProfile = activeScanProfileId == "full" and "quick" or "full"
    applyScanProfile(nextProfile)
end)
observationToggle.MouseButton1Click:Connect(function()
    cycleObservationIdleSeconds()
    status.Text = "Observation window set to " .. AUTO_EVIDENCE_IDLE_SECONDS .. "s"
end)
refreshEvidenceControls("initial")

-- Existing observer already captures pre/post state and GUI transitions. This
-- scheduler consolidates those records into profile-selected reports after activity settles.
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
                refreshEvidenceControls("auto-rescan")
                inspect("auto-evidence")
            else
                autoEvidenceLastFailure="Previous scan parts not acknowledged"
                refreshEvidenceControls("auto-rescan-blocked")
            end
        end
    end
end)
produceScript.MouseButton1Click:Connect(function()
    local request = trim(featureRequestInput.Text:gsub("[%c]+", " "))
    if request == "" then
        generatedStatus.Text = "Enter a client-visible capability request first."
        return
    end
    if #request > 240 then
        generatedStatus.Text = "Request is too long; use 240 bytes or fewer."
        return
    end
    featureRequestInput.Text = request
    if activeScanProfileId ~= "full" then
        applyScanProfile("full")
        status.Text = "Feature request capture switched to FULL scan for complete evidence"
    end
    if inspect("feature-request", request) then
        generatedStatus.Text = "Capturing a complete evidence package for offline generation.\n\nNo gameplay implementation or outcome is verified in-game."
    else
        generatedStatus.Text = "Evidence capture not started:\n" .. status.Text
    end
end)

scan.MouseButton1Click:Connect(function()
    if running or uploading then
        cancelActiveOperation()
    else
        inspect("manual")
    end
end)

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
    if not last or not pendingManifest or not pendingParts or #pendingParts==0 then
        status.Text = "Scan not finished"
        return
    end
    if type(writefile) ~= "function" then
        pendingManifest.localExport={attempted=true,status="failed",exportedParts=0,
            expectedParts=#pendingParts,manifestSaved=false,manifestWriteAttempts=0,
            localPartContentDigestsComputed=false,lastError="file writing unavailable"}
        refreshLocalManifest("local-export")
        refreshGeneratedHandoff("Local export finished")
        status.Text = "File saving unavailable"
        return
    end

    local safeScanId=tostring(pendingManifest.scanId or "unknown"):gsub("[^%w%-]","")
    local prefix="Lycoles_"..tostring(game.PlaceId).."_"..safeScanId
    local exported=0
    local firstError=nil
    for i,body in ipairs(pendingParts) do
        local ok,err=pcall(writefile,prefix.."_part-"..string.format("%04d",i)..".json",body)
        if ok then exported=exported+1 elseif not firstError then firstError=tostring(err) end
    end
    pendingManifest.localExport={
        attempted=true,status=exported==#pendingParts and "incomplete" or "failed",
        exportedParts=exported,expectedParts=#pendingParts,
        filenamePrefix=prefix,manifestSaved=false,manifestWriteAttempts=1,
        localPartContentDigestsComputed=false,
        lastError=exported==#pendingParts and "manifest finalization pending" or "one or more part writes failed",
        note="Raw numbered part bytes are preserved; compare offline SHA-256 with receiver acknowledgement digests when available"
    }
    refreshLocalManifest("local-export")
    local manifestOk,manifestError=pcall(writefile,prefix.."_manifest.json",last)
    if manifestOk and exported==#pendingParts then
        pendingManifest.localExport.status="complete"
        pendingManifest.localExport.manifestSaved=true
        pendingManifest.localExport.manifestWriteAttempts=2
        pendingManifest.localExport.lastError=nil
        refreshLocalManifest("local-export")
        local finalOk,finalError=pcall(writefile,prefix.."_manifest.json",last)
        if finalOk then
            status.Text="Saved complete report: "..exported.." part(s) + manifest"
        else
            manifestOk=false;manifestError=finalError
            pendingManifest.localExport.status="failed"
            pendingManifest.localExport.manifestSaved=false
            pendingManifest.localExport.lastError="final manifest write failed"
            refreshLocalManifest("local-export")
        end
    end
    if not manifestOk or exported~=#pendingParts then
        if manifestOk then
            pendingManifest.localExport.status="incomplete"
            pendingManifest.localExport.manifestSaved=true
            pendingManifest.localExport.manifestWriteAttempts=2
            pendingManifest.localExport.lastError="one or more numbered parts were not saved"
            refreshLocalManifest("local-export")
            local partialOk,partialError=pcall(writefile,prefix.."_manifest.json",last)
            if not partialOk then
                manifestOk=false;manifestError=partialError
                pendingManifest.localExport.status="failed"
                pendingManifest.localExport.manifestSaved=false
                pendingManifest.localExport.lastError="final manifest write failed"
                refreshLocalManifest("local-export")
            end
        else
            pendingManifest.localExport.status="failed"
            pendingManifest.localExport.lastError="manifest write failed"
            refreshLocalManifest("local-export")
        end
        status.Text="Report save incomplete: "..exported.."/"..#pendingParts
        if firstError then warn("Lycoles local report export failed",firstError) end
        if manifestError then warn("Lycoles local manifest export failed",tostring(manifestError)) end
    end
    refreshGeneratedHandoff("Local export finished")
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