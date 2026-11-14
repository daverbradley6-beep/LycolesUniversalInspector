#!/usr/bin/env python3
"""Lycoles v8 offline scan compiler: multipart integrity -> feature evidence -> release plan.
No third-party packages, Roblox credentials, or game-specific hardcoding required.
Usage: python3 tools/compile_scan.py scan-parts-dir --output build
"""
import argparse, collections, hashlib, json, math, pathlib, sys, unicodedata

def fail(message):
    raise ValueError(message)

_CORRELATION_CLASSIFICATION="feature-consistent-observable-change"
_CORRELATION_STATUS="candidate-needs-causal-validation"

def _false_claims(document,server_key):
    required=("sourceAuthenticityVerified","causalityProven",server_key,"gameplayVerified")
    aliases=("serverVerified","serverAuthorityVerified","outcomeVerified",
             "runtimeVerified","liveGameVerified","replayable")
    return (all(document.get(key) is False for key in required)
            and not any(document.get(key) is True for key in aliases))

def _correlation_evidence(event):
    feature=event.get("featureCandidate")
    state=event.get("featureStateEvidence")
    gui=event.get("featureGuiEvidence")
    candidate=event.get("observableOutcomeCandidate")
    kinds=[]
    for field,value,server_key,detail_key,kind in (
        ("featureStateEvidence",state,"serverVerified","matchedKeys","state-change"),
        ("featureGuiEvidence",gui,"serverVerified","matchedPaths","gui-change")):
        if value is None:
            continue
        if not isinstance(value,dict):
            fail(f"Malformed {field}")
        if value.get("classification")!=_CORRELATION_CLASSIFICATION:
            continue
        details=value.get(detail_key)
        if (value.get("feature")!=feature or value.get("status")!=_CORRELATION_STATUS
                or not isinstance(details,list) or not details
                or any(not isinstance(item,str) or not item for item in details)
                or not _false_claims(value,server_key)):
            fail("Feature correlation evidence claims verification or is malformed")
        kinds.append(kind)
    if candidate is None:
        if kinds:
            fail("Feature correlation evidence lacks observable outcome candidate")
        return {"candidate":False,"state":False,"gui":False}
    if not isinstance(candidate,dict):
        fail("Malformed observable outcome candidate")
    evidence_kinds=candidate.get("evidenceKinds")
    if (candidate.get("feature")!=feature
            or candidate.get("classification")!=_CORRELATION_CLASSIFICATION
            or not isinstance(evidence_kinds,list) or not evidence_kinds
            or any(kind not in ("state-change","gui-change") for kind in evidence_kinds)
            or len(set(evidence_kinds))!=len(evidence_kinds)
            or set(evidence_kinds)!=set(kinds)
            or type(candidate.get("overlappingInteractionsPossible")) is not bool
            or not _false_claims(candidate,"serverAuthorityVerified")
            or event.get("outcomeVerified") is not False):
        fail("Observable outcome candidate evidence claims verification or is malformed")
    return {"candidate":True,"state":"state-change" in kinds,"gui":"gui-change" in kinds}

_BASELINE_SOURCES={"GuiButton.InputBegan","ProximityPrompt.PromptButtonHoldBegan",
    "Tool.Equipped","activation-callback-fallback","input-event-callback"}


def _baseline_evidence(event):
    fields=("baselineSource","baselineTiming","baselineAgeSeconds",
        "preActivationBaselineAvailable")
    if not any(field in event for field in fields):
        return {"timing":"unknown","preActivationBaselineAvailable":False}
    source=event.get("baselineSource");timing=event.get("baselineTiming")
    available=event.get("preActivationBaselineAvailable");age=event.get("baselineAgeSeconds")
    if source=="activation-callback-fallback":
        expected_timing="activation-callback";expected_available=False
    elif source=="input-event-callback":
        expected_timing="input-event-callback";expected_available=False
    else:
        expected_timing="pre-activation";expected_available=True
    if (source not in _BASELINE_SOURCES or timing!=expected_timing
            or type(available) is not bool or available is not expected_available
            or (age is not None and (type(age) not in (int,float) or type(age) is bool
                or not 0<=age<=3600))):
        fail("Malformed interaction baseline timing")
    normalized_timing=("activation-callback"
        if source in {"activation-callback-fallback","input-event-callback"}
        else "pre-activation")
    return {"timing":normalized_timing,"preActivationBaselineAvailable":available}

def _session_timing(event,expected_session):
    fields=("sessionId","sessionElapsedSeconds")
    if not any(field in event for field in fields):return None
    session=event.get("sessionId");elapsed=event.get("sessionElapsedSeconds")
    if (not isinstance(session,str) or not 1<=len(session)<=80
            or expected_session is not None and session!=expected_session
            or type(elapsed) not in (int,float) or type(elapsed) is bool
            or not math.isfinite(elapsed) or not 0<=elapsed<=604_800):
        fail("Malformed interaction session timing")
    return {"sessionId":session,"sessionElapsedSeconds":elapsed}


def _interaction_observation_summary(diagnostics):
    if diagnostics in (None,{}):
        return {"available":False,"evidenceLossPossible":None,
            "limitations":["interaction baseline/window accounting unavailable in this report version"]}
    if not isinstance(diagnostics,dict):fail("Malformed interaction diagnostics")
    marker_fields=("observationWindowsExpected","preActivationCaptures",
        "baselineTimingPolicy")
    if not any(field in diagnostics for field in marker_fields):
        return {"available":False,"evidenceLossPossible":None,
            "limitations":["interaction baseline/window accounting unavailable in this report version"]}
    count_fields=("callbacksFired","preActivationListenersAttached","preActivationCaptures",
        "preActivationBaselinesUsed","callbackBaselinesUsed","stalePreActivationCaptures",
        "preActivationCaptureFailures","pendingObservationEvents","observationWindowsExpected",
        "observationWindowsCompleted","observationWindowsFailed")
    if any(type(diagnostics.get(field)) is not int or not 0<=diagnostics[field]<=10_000_000
            for field in count_fields):
        fail("Malformed interaction observation counts")
    expected=diagnostics["observationWindowsExpected"]
    windows=diagnostics.get("observationWindowsSeconds")
    if windows!=[0.35,1.25,3.0] or expected!=diagnostics["callbacksFired"]*len(windows):
        fail("Inconsistent interaction observation window schedule")
    accounted=diagnostics["observationWindowsCompleted"]+diagnostics[
        "observationWindowsFailed"]+diagnostics["pendingObservationEvents"]
    actual_accounting=accounted==expected
    unattributed_callbacks=(diagnostics["callbacksFired"]
        -(diagnostics["preActivationBaselinesUsed"]+diagnostics["callbackBaselinesUsed"]))
    actual_loss=(diagnostics["pendingObservationEvents"]>0
        or diagnostics["observationWindowsFailed"]>0
        or diagnostics["preActivationCaptureFailures"]>0
        or diagnostics["callbackBaselinesUsed"]>0
        or unattributed_callbacks>0)
    legacy_unattributed_callbacks=(unattributed_callbacks>0
        and diagnostics["preActivationCaptures"]==0
        and diagnostics["preActivationBaselinesUsed"]==0
        and diagnostics["callbackBaselinesUsed"]==0
        and diagnostics["observationWindowsCompleted"]<expected
        and diagnostics["observationWindowsFailed"]==0
        and diagnostics["pendingObservationEvents"]==0
        and diagnostics.get("observationWindowAccountingValid") is False)
    baseline_usage_consistent=(diagnostics["preActivationBaselinesUsed"]
        +diagnostics["callbackBaselinesUsed"]==diagnostics["callbacksFired"]
        or legacy_unattributed_callbacks)
    evidence_loss_flag_consistent=(diagnostics.get("evidenceLossPossible") is actual_loss
        or (legacy_unattributed_callbacks and diagnostics.get("evidenceLossPossible") is False))
    if (not baseline_usage_consistent
            or diagnostics["preActivationBaselinesUsed"]>diagnostics["preActivationCaptures"]
            or diagnostics["stalePreActivationCaptures"]>diagnostics["callbackBaselinesUsed"]
            or (diagnostics["preActivationCaptures"]>0
                and diagnostics["preActivationListenersAttached"]==0)
            or diagnostics.get("observationWindowAccountingValid") is not actual_accounting
            or not evidence_loss_flag_consistent
            or diagnostics.get("baselineTimingPolicy")!=
                "pre-activation when a bounded supported signal is fresh; otherwise explicit activation-callback fallback"):
        fail("Inconsistent interaction observation diagnostics")
    limitations=[]
    if diagnostics["callbackBaselinesUsed"]:limitations.append(
        "callback-time baselines may miss synchronous activation changes")
    if unattributed_callbacks>0:limitations.append(
        "one or more callbacks had no attributed baseline at export time")
    if diagnostics["preActivationCaptureFailures"]:limitations.append(
        "one or more pre-activation captures failed")
    if diagnostics["observationWindowsFailed"]:limitations.append(
        "one or more delayed observation windows failed")
    if diagnostics["pendingObservationEvents"]:limitations.append(
        "one or more delayed observation windows were pending at export")
    return {"available":True,"callbacksFired":diagnostics["callbacksFired"],
        "preActivationBaselinesUsed":diagnostics["preActivationBaselinesUsed"],
        "callbackBaselinesUsed":diagnostics["callbackBaselinesUsed"],
        "preActivationCaptureFailures":diagnostics["preActivationCaptureFailures"],
        "pendingObservationEvents":diagnostics["pendingObservationEvents"],
        "observationWindowsExpected":expected,
        "observationWindowsCompleted":diagnostics["observationWindowsCompleted"],
        "observationWindowsFailed":diagnostics["observationWindowsFailed"],
        "observationWindowAccountingValid":actual_accounting,
        "evidenceLossPossible":actual_loss,"limitations":limitations}


MAX_DISCOVERY_REGIONS=256
MAX_DISCOVERY_INTERACTABLES=1600
MAX_DISCOVERY_ECONOMY_SIGNALS=1200
MAX_DISCOVERY_STATE_SIGNALS=800
MAX_DISCOVERY_PATTERNS=256
MAX_DISCOVERY_PATH_LENGTH=400
_ACTIONABLE_CLASSES={"ProximityPrompt","ClickDetector","TextButton","ImageButton","Tool"}

def _safe_text(value,limit=MAX_DISCOVERY_PATH_LENGTH):
    return (isinstance(value,str) and 1<=len(value)<=limit
        and all(unicodedata.category(character)!="Cc" for character in value))

def _safe_scalar(value):
    return type(value) in (int,float,str,bool) and len(str(value))<=120

def _safe_number(value):
    return type(value) in (int,float) and type(value) is not bool and math.isfinite(value)

def _safe_vec3(value):
    if not isinstance(value,dict):return None
    x,y,z=value.get("x"),value.get("y"),value.get("z")
    if not (_safe_number(x) and _safe_number(y) and _safe_number(z)):return None
    if any(abs(component)>10_000_000 for component in (x,y,z)):return None
    return {"x":round(float(x),3),"y":round(float(y),3),"z":round(float(z),3)}

def _path_tokens(value):
    if not isinstance(value,str):return set()
    tokens=set()
    for token in value.lower().replace("[",".").replace("]",".").replace("/",".").split("."):
        token=token.strip()
        if token and len(token)<=80:tokens.add(token)
    return tokens

def _terminal_name(path):
    if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH):return None
    return path.rsplit(".",1)[-1][:120]

def _economy_classification(path,key):
    tokens=_path_tokens(path)|_path_tokens(key)
    if not tokens:return None
    if tokens&{"cost","price","priced","costs","requirement","required","requires",
            "unlock","unlocks","levelreq","levelrequirement"}:
        return "requirement_or_cost_signal"
    if tokens&{"coin","coins","gem","gems","cash","currency","currencies",
            "token","tokens","gold","money","credit","credits"}:
        return "currency_signal"
    if tokens&{"reward","rewards","quest","quests","xp","experience","exp",
            "rebirth","rebirths","level","levels","progress","milestone"}:
        return "progression_signal"
    if tokens&{"inventory","capacity","slot","slots","item","items"}:
        return "inventory_signal"
    return None

def _canonical_region(path):
    if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH) or not path.startswith("Workspace."):
        return None
    segments=path.split(".")
    if len(segments)<3:return "Workspace"
    depth=4 if len(segments)>=4 and segments[1].lower() in (
        "worlds","areas","islands","zones","region","regions") else 3
    return ".".join(segments[:min(len(segments),depth)])

def _interaction_mechanism(entry_class,control_type):
    if entry_class=="ProximityPrompt" or control_type=="ProximityPrompt.Triggered":
        return "proximity_prompt"
    if entry_class=="ClickDetector" or control_type=="ClickDetector.MouseClick":
        return "click_detector"
    if entry_class=="Tool" or control_type=="Tool.Activated":
        return "tool_activation"
    if entry_class in {"TextButton","ImageButton"} or control_type=="GuiButton.Activated":
        return "gui_button"
    return "observed_control"

def _nearest_position(path,positions):
    if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH):return None,None
    segments=path.split(".")
    for index in range(len(segments),0,-1):
        prefix=".".join(segments[:index])
        if prefix in positions:return positions[prefix],prefix
    return None,None

def _universal_discovery(objects,actionable,history):
    positions={}
    region_stats={}
    root_counts=collections.Counter()
    for obj in objects:
        path=obj.get("path")
        if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH):
            continue
        root_counts[path.split(".",1)[0]]+=1
        position=_safe_vec3(obj.get("position"))
        if position is None:
            continue
        positions[path]=position
        region=_canonical_region(path)
        if not region:
            continue
        stats=region_stats.setdefault(region,{"positioned":0,"total":0,
            "sumX":0.0,"sumY":0.0,"sumZ":0.0,
            "minX":position["x"],"minY":position["y"],"minZ":position["z"],
            "maxX":position["x"],"maxY":position["y"],"maxZ":position["z"]})
        stats["positioned"]+=1
        stats["sumX"]+=position["x"];stats["sumY"]+=position["y"];stats["sumZ"]+=position["z"]
        stats["minX"]=min(stats["minX"],position["x"]);stats["maxX"]=max(stats["maxX"],position["x"])
        stats["minY"]=min(stats["minY"],position["y"]);stats["maxY"]=max(stats["maxY"],position["y"])
        stats["minZ"]=min(stats["minZ"],position["z"]);stats["maxZ"]=max(stats["maxZ"],position["z"])
    for obj in objects:
        region=_canonical_region(obj.get("path"))
        if region in region_stats:region_stats[region]["total"]+=1

    history_by_path={}
    for event in history:
        path=event.get("path")
        if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH):continue
        item=history_by_path.setdefault(path,{"observedInteractions":0,"controlTypes":set(),"features":set()})
        item["observedInteractions"]+=1
        if _safe_text(event.get("controlType"),120):item["controlTypes"].add(event["controlType"])
        if _safe_text(event.get("featureCandidate"),120):item["features"].add(event["featureCandidate"])

    interactables=[]
    seen_paths=set()
    for item in actionable:
        path=item.get("path")
        entry_class=item.get("class")
        if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH) or not _safe_text(entry_class,80):continue
        seen_paths.add(path)
        control_type=("ProximityPrompt.Triggered" if entry_class=="ProximityPrompt"
            else "ClickDetector.MouseClick" if entry_class=="ClickDetector"
            else "Tool.Activated" if entry_class=="Tool" else "GuiButton.Activated")
        mechanism=_interaction_mechanism(entry_class,control_type)
        interaction=item.get("interaction") if isinstance(item.get("interaction"),dict) else {}
        position=_safe_vec3(interaction.get("anchorPosition"))
        position_source_path=interaction.get("anchorPath") if position is not None else None
        source="interaction-anchor"
        if position is None:
            position,position_source_path=_nearest_position(path,positions)
            source="nearest-object-position" if position is not None else "unavailable"
        history_details=history_by_path.get(path,{})
        interactables.append({
            "id":"interactable_"+hashlib.sha256((path+"\n"+entry_class).encode("utf-8")).hexdigest()[:16],
            "path":path,"class":entry_class,
            "scope":path.split(".",1)[0].lower(),
            "mechanism":mechanism,
            "position":position,
            "positionSource":source,
            "positionSourcePath":position_source_path if _safe_text(position_source_path,MAX_DISCOVERY_PATH_LENGTH) else None,
            "observedInteractions":history_details.get("observedInteractions",0),
            "observedControlTypes":sorted(history_details.get("controlTypes",set())),
            "relatedFeatures":sorted(history_details.get("features",set())),
            "actionText":(interaction.get("actionText") if _safe_text(interaction.get("actionText"),120) else None),
            "objectText":(interaction.get("objectText") if _safe_text(interaction.get("objectText"),120) else None),
            "sharedPatternKey":mechanism+":"+path.split(".",1)[0].lower(),
            "confidence":"structural-with-observation" if history_details else "structural-only",
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
        })

    for path,details in history_by_path.items():
        if path in seen_paths:
            continue
        control_type=next(iter(sorted(details["controlTypes"])),"Unknown")
        mechanism=_interaction_mechanism(None,control_type)
        position,position_source_path=_nearest_position(path,positions)
        interactables.append({
            "id":"interactable_"+hashlib.sha256((path+"\n"+control_type).encode("utf-8")).hexdigest()[:16],
            "path":path,"class":control_type.split(".",1)[0],
            "scope":path.split(".",1)[0].lower(),
            "mechanism":mechanism,
            "position":position,
            "positionSource":"nearest-object-position" if position is not None else "unavailable",
            "positionSourcePath":position_source_path,
            "observedInteractions":details["observedInteractions"],
            "observedControlTypes":sorted(details["controlTypes"]),
            "relatedFeatures":sorted(details["features"]),
            "actionText":None,"objectText":None,
            "sharedPatternKey":mechanism+":"+path.split(".",1)[0].lower(),
            "confidence":"observation-only",
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
        })

    interactables.sort(key=lambda item:(
        -(item["observedInteractions"]),
        item["position"] is None,
        item["path"],item["class"]))
    if len(interactables)>MAX_DISCOVERY_INTERACTABLES:
        interactables=interactables[:MAX_DISCOVERY_INTERACTABLES]

    economy=[];economy_seen=set()
    def add_economy(path,key,value,source,scope):
        if not (_safe_text(path,MAX_DISCOVERY_PATH_LENGTH) and _safe_text(key,120) and _safe_scalar(value)):
            return
        classification=_economy_classification(path,key)
        if classification is None:return
        identity=(path,key,source)
        if identity in economy_seen:return
        economy_seen.add(identity)
        economy.append({"id":"econ_"+hashlib.sha256((path+"\n"+key+"\n"+source).encode("utf-8")).hexdigest()[:16],
            "path":path,"key":key,"value":value,"source":source,
            "scope":scope,"classification":classification,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})

    for obj in objects:
        path=obj.get("path")
        if not _safe_text(path,MAX_DISCOVERY_PATH_LENGTH):continue
        scope=path.split(".",1)[0].lower()
        attrs=obj.get("attributes")
        if isinstance(attrs,dict):
            for key,value in attrs.items():
                if len(economy)>=MAX_DISCOVERY_ECONOMY_SIGNALS:break
                add_economy(path,str(key)[:120],value,"object-attribute",scope)
        if len(economy)>=MAX_DISCOVERY_ECONOMY_SIGNALS:break
        if "value" in obj:
            key=_terminal_name(path) or "value"
            add_economy(path,key,obj.get("value"),"value-object",scope)

    state_signals={}
    for event in history:
        feature=event.get("featureCandidate") if _safe_text(event.get("featureCandidate"),120) else None
        changes=[]
        if isinstance(event.get("stateChanges"),list):changes.extend(event["stateChanges"])
        windows=event.get("observationWindows")
        if isinstance(windows,list):
            for window in windows:
                if isinstance(window,dict) and isinstance(window.get("stateChanges"),list):
                    changes.extend(window["stateChanges"])
        for change in changes:
            if not isinstance(change,dict):continue
            key=change.get("key") or change.get("path")
            before,after=change.get("before"),change.get("after")
            if not (_safe_text(key,200) and _safe_scalar(before) and _safe_scalar(after)):
                continue
            classification=_economy_classification(key,key) or "state_transition_signal"
            signal=state_signals.setdefault(key,{"id":"state_"+hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                "key":key,"classification":classification,
                "increaseEvents":0,"decreaseEvents":0,"changedEvents":0,
                "sourceFeatures":set(),"lastBefore":before,"lastAfter":after,
                "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})
            signal["changedEvents"]+=1
            signal["lastBefore"]=before;signal["lastAfter"]=after
            if type(before) in (int,float) and type(after) in (int,float):
                if after>before:signal["increaseEvents"]+=1
                elif after<before:signal["decreaseEvents"]+=1
            if feature:signal["sourceFeatures"].add(feature)

    state_signal_items=sorted(({
        **item,
        "sourceFeatures":sorted(item["sourceFeatures"]),
    } for item in state_signals.values()),key=lambda item:(
        -(item["changedEvents"]),item["key"]))
    if len(state_signal_items)>MAX_DISCOVERY_STATE_SIGNALS:
        state_signal_items=state_signal_items[:MAX_DISCOVERY_STATE_SIGNALS]

    region_items=[]
    for region,stats in sorted(region_stats.items(),key=lambda item:(
            -item[1]["positioned"],-item[1]["total"],item[0]))[:MAX_DISCOVERY_REGIONS]:
        region_items.append({"id":"region_"+hashlib.sha256(region.encode("utf-8")).hexdigest()[:16],
            "path":region,
            "positionedObjectCount":stats["positioned"],
            "totalObjectCount":stats["total"],
            "centroid":{
                "x":round(stats["sumX"]/stats["positioned"],3),
                "y":round(stats["sumY"]/stats["positioned"],3),
                "z":round(stats["sumZ"]/stats["positioned"],3)},
            "bounds":{
                "x":[round(stats["minX"],3),round(stats["maxX"],3)],
                "y":[round(stats["minY"],3),round(stats["maxY"],3)],
                "z":[round(stats["minZ"],3),round(stats["maxZ"],3)]},
            "runtimeVerified":False,"gameplayVerified":False})

    pattern_counts={}
    for item in interactables:
        key=item["sharedPatternKey"]
        pattern=pattern_counts.setdefault(key,{"mechanism":item["mechanism"],
            "scope":item["scope"],"memberCount":0,"observedInteractions":0,
            "samplePaths":[]})
        pattern["memberCount"]+=1
        pattern["observedInteractions"]+=item["observedInteractions"]
        if len(pattern["samplePaths"])<5:pattern["samplePaths"].append(item["path"])
    patterns=[]
    for key,data in sorted(pattern_counts.items(),key=lambda item:(
            -item[1]["memberCount"],-item[1]["observedInteractions"],item[0]))[:MAX_DISCOVERY_PATTERNS]:
        patterns.append({"id":"pattern_"+hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
            "key":key,"mechanism":data["mechanism"],"scope":data["scope"],
            "memberCount":data["memberCount"],
            "observedInteractions":data["observedInteractions"],
            "samplePaths":data["samplePaths"],
            "runtimeVerified":False,"gameplayVerified":False})

    economy.sort(key=lambda item:(item["classification"],item["path"],item["key"],item["source"]))
    if len(economy)>MAX_DISCOVERY_ECONOMY_SIGNALS:
        economy=economy[:MAX_DISCOVERY_ECONOMY_SIGNALS]

    return {"schemaVersion":"30.7.universal-discovery.1",
        "regions":region_items,
        "interactables":interactables,
        "economySignals":economy,
        "stateChangeSignals":state_signal_items,
        "interactionPatterns":patterns,
        "summary":{
            "rootObjectGroups":dict(sorted(root_counts.items())),
            "regions":len(region_items),
            "interactables":len(interactables),
            "worldPositionedInteractables":sum(item["position"] is not None for item in interactables),
            "observedInteractablePaths":sum(item["observedInteractions"]>0 for item in interactables),
            "economySignals":len(economy),
            "stateChangeSignals":len(state_signal_items),
            "interactionPatterns":len(patterns)},
        "claims":{"runtimeVerified":False,"gameplayVerified":False,
            "causalityProven":False,"sourceAuthenticityVerified":False}}



_RECEIVER_PROVENANCE_FIELDS={
    "schemaVersion","scanId","placeId","partCount","expectedParts","objectCount",
    "metadata","receiverIntegrity","receiverPartContentDigests",
    "resumableRetrievalEnabled","resumedPartCount","downloadedPartCount",
    "resumeCheckpointAuthenticated","receiverStoredPayloadDigestsRevalidatedThisRun",
    "receiverStoredPayloadDigestsVerified","receiverAcknowledgementDigestEquivalent",
    "receiverIntegrityVerified","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","note",
}
_LEGACY_RECEIVER_PROVENANCE_FIELDS={
    "schemaVersion","scanId","placeId","partCount","expectedParts","objectCount",
    "metadata","receiverIntegrity","receiverReportedIntegrity",
    "retrievedPartContentDigests","resumableRetrievalEnabled","resumedPartCount",
    "downloadedPartCount","resumeCheckpointAuthenticated",
    "receiverStoredPayloadDigestsRevalidatedThisRun",
    "receiverStoredPayloadDigestsVerified","receiverAcknowledgementDigestEquivalent",
    "receiverIntegrityVerified","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","note",
}
_LEGACY_REPORT_RECEIVER_PROVENANCE_FIELDS={
    "schemaVersion","scanId","placeId","partCount","expectedParts","objectCount",
    "metadata","receiverIntegrity","retrievedPartContentDigests",
    "resumableRetrievalEnabled","resumedPartCount","downloadedPartCount",
    "resumeCheckpointAuthenticated","receiverStoredPayloadDigestsRevalidatedThisRun",
    "receiverStoredPayloadDigestsVerified","receiverAcknowledgementDigestEquivalent",
    "receiverIntegrityVerified","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","receiverReportedIntegrityUnavailable",
    "legacyReportPagesScanned","legacyReportRecordsMatched","note",
}

_RECEIVER_MARKERS={
    "receiverIntegrity","receiverPartContentDigests",
    "receiverStoredPayloadDigestsVerified","receiverIntegrityVerified",
    "receiverResponseAuthenticityVerified","localPayloadEquivalent",
}

def bounded_path_identity(value):
    if not isinstance(value,list) or not 1<=len(value)<=21:return None
    result=[]
    for segment in value:
        if not isinstance(segment,dict):return None
        name=segment.get("name");class_name=segment.get("className");ordinal=segment.get("ordinal")
        if (not isinstance(name,str) or not 1<=len(name)<=100 or not isinstance(class_name,str)
                or not 1<=len(class_name)<=100 or type(ordinal) is not int or not 1<=ordinal<=10000):return None
        result.append({"name":name,"className":class_name,"ordinal":ordinal})
    return result



def _base_source_provenance(scan_id,place_id,part_count):
    return {
        "schemaVersion":"30.2.source-provenance.1","inputMode":"local-multipart",
        "scanId":scan_id,"placeId":place_id,"partCount":part_count,
        "partContentDigests":[],"receiverStoredPayloadDigestsVerified":False,
        "receiverStoredPayloadDigestsRevalidatedThisRun":False,
        "receiverAcknowledgementDigestEquivalent":False,
        "receiverIntegrityVerified":False,"resumableRetrievalEnabled":False,
        "resumedPartCount":0,"downloadedPartCount":0,
        "resumeCheckpointAuthenticated":False,
        "receiverResponseAuthenticityVerified":False,"localPayloadEquivalent":False,
        "sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"replayable":False,
        "gameplayVerified":False,"actionOutcomesVerified":False,
    }


def _local_source_provenance(scan_id,place_id,part_count,digests):
    if set(digests)!=set(range(1,part_count+1)):
        fail("Incomplete local part digest coverage")
    result=_base_source_provenance(scan_id,place_id,part_count)
    result.update({
        "schemaVersion":"30.2.source-provenance.2",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "localPartContentDigestsComputed":True,
    })
    return result


def _receiver_source_provenance(manifest,scan_id,place_id,part_count,
                                object_count,actual_digests):
    if set(manifest)!=_RECEIVER_PROVENANCE_FIELDS:
        fail("Invalid receiver provenance schema")
    if (manifest.get("schemaVersion")!="30.2.receiver-import.2"
            or manifest.get("scanId")!=scan_id or manifest.get("placeId")!=place_id
            or manifest.get("partCount")!=part_count
            or manifest.get("expectedParts")!=part_count
            or manifest.get("objectCount")!=object_count):
        fail("Invalid receiver provenance identity")
    metadata=manifest.get("metadata")
    if (not isinstance(metadata,dict) or metadata.get("scanId")!=scan_id
            or metadata.get("placeId")!=place_id or metadata.get("partCount")!=part_count):
        fail("Invalid receiver provenance metadata")
    integrity=manifest.get("receiverIntegrity")
    if (not isinstance(integrity,dict) or integrity.get("scanId")!=scan_id
            or integrity.get("placeId")!=place_id
            or integrity.get("partCount")!=part_count
            or integrity.get("receivedParts")!=part_count
            or integrity.get("missingParts")!=[]
            or integrity.get("indexedObjects")!=object_count
            or integrity.get("uniqueObjectKeys")!=object_count
            or integrity.get("duplicateObjectKeys")!=0
            or integrity.get("identityErrors")!=[]
            or integrity.get("expectedObjects")!=object_count
            or integrity.get("complete") is not True
            or integrity.get("integrityStatus")!="verified-after-retrieval"):
        fail("Invalid receiver provenance integrity")
    entries=manifest.get("receiverPartContentDigests")
    if not isinstance(entries,list) or len(entries)!=part_count:
        fail("Invalid receiver provenance digests")
    digests={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}:
            fail("Invalid receiver provenance digest")
        index=entry.get("partIndex"); digest=entry.get("sha256")
        if (type(index) is not int or not 1<=index<=part_count or index in digests
                or not isinstance(digest,str) or len(digest)!=64
                or any(character not in "0123456789abcdef" for character in digest)
                or actual_digests.get(index)!=digest):
            fail("Invalid receiver provenance digest")
        digests[index]=digest
    resumed=manifest.get("resumedPartCount")
    downloaded=manifest.get("downloadedPartCount")
    if (type(resumed) is not int or type(downloaded) is not int
            or resumed<0 or downloaded<0 or resumed+downloaded!=part_count
            or type(manifest.get("resumableRetrievalEnabled")) is not bool
            or (resumed>0 and manifest.get("resumableRetrievalEnabled") is not True)
            or manifest.get("resumeCheckpointAuthenticated") is not False
            or manifest.get("receiverStoredPayloadDigestsRevalidatedThisRun") is not (resumed==0)
            or manifest.get("receiverStoredPayloadDigestsVerified") is not True
            or type(manifest.get("receiverAcknowledgementDigestEquivalent")) is not bool
            or manifest.get("receiverIntegrityVerified") is not True
            or manifest.get("receiverResponseAuthenticityVerified") is not False
            or manifest.get("localPayloadEquivalent") is not False
            or not isinstance(manifest.get("note"),str)):
        fail("Invalid receiver provenance claims")
    result=_base_source_provenance(scan_id,place_id,part_count)
    result.update({
        "inputMode":"receiver-import",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "receiverStoredPayloadDigestsVerified":True,
        "receiverStoredPayloadDigestsRevalidatedThisRun":resumed==0,
        "receiverAcknowledgementDigestEquivalent":manifest["receiverAcknowledgementDigestEquivalent"],
        "receiverIntegrityVerified":True,
        "resumableRetrievalEnabled":manifest["resumableRetrievalEnabled"],
        "resumedPartCount":resumed,"downloadedPartCount":downloaded,
    })
    return result


def _legacy_receiver_source_provenance(manifest,scan_id,place_id,part_count,
                                       object_count,actual_digests):
    if set(manifest)!=_LEGACY_RECEIVER_PROVENANCE_FIELDS:
        fail("Invalid legacy receiver provenance schema")
    if (manifest.get("schemaVersion")!="30.2.receiver-import-legacy.1"
            or manifest.get("scanId")!=scan_id or manifest.get("placeId")!=place_id
            or manifest.get("partCount")!=part_count
            or manifest.get("expectedParts")!=part_count
            or manifest.get("objectCount")!=object_count):
        fail("Invalid legacy receiver provenance identity")
    metadata=manifest.get("metadata")
    if (not isinstance(metadata,dict) or metadata.get("scanId")!=scan_id
            or metadata.get("placeId")!=place_id or metadata.get("partCount")!=part_count):
        fail("Invalid legacy receiver provenance metadata")
    for field,status in (("receiverIntegrity","verified-after-retrieval"),
                         ("receiverReportedIntegrity","verified")):
        integrity=manifest.get(field)
        if (not isinstance(integrity,dict) or integrity.get("scanId")!=scan_id
                or integrity.get("placeId")!=place_id
                or integrity.get("partCount")!=part_count
                or integrity.get("receivedParts")!=part_count
                or integrity.get("missingParts")!=[]
                or integrity.get("indexedObjects")!=object_count
                or integrity.get("uniqueObjectKeys")!=object_count
                or integrity.get("duplicateObjectKeys")!=0
                or integrity.get("identityErrors")!=[]
                or integrity.get("expectedObjects")!=object_count
                or integrity.get("complete") is not True
                or integrity.get("integrityStatus")!=status):
            fail("Invalid legacy receiver provenance integrity")
    entries=manifest.get("retrievedPartContentDigests")
    if not isinstance(entries,list) or len(entries)!=part_count:
        fail("Invalid legacy receiver provenance digests")
    digests={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}:
            fail("Invalid legacy receiver provenance digest")
        index=entry.get("partIndex");digest=entry.get("sha256")
        if (type(index) is not int or not 1<=index<=part_count or index in digests
                or not isinstance(digest,str) or len(digest)!=64
                or any(character not in "0123456789abcdef" for character in digest)
                or actual_digests.get(index)!=digest):
            fail("Invalid legacy receiver provenance digest")
        digests[index]=digest
    acknowledgement=manifest.get("receiverAcknowledgementDigestEquivalent")
    if (manifest.get("resumableRetrievalEnabled") is not False
            or manifest.get("resumedPartCount")!=0
            or manifest.get("downloadedPartCount")!=part_count
            or manifest.get("resumeCheckpointAuthenticated") is not False
            or manifest.get("receiverStoredPayloadDigestsRevalidatedThisRun") is not False
            or manifest.get("receiverStoredPayloadDigestsVerified") is not False
            or type(acknowledgement) is not bool
            or manifest.get("receiverIntegrityVerified") is not True
            or manifest.get("receiverResponseAuthenticityVerified") is not False
            or manifest.get("localPayloadEquivalent") is not False
            or not isinstance(manifest.get("note"),str)):
        fail("Invalid legacy receiver provenance claims")
    result=_base_source_provenance(scan_id,place_id,part_count)
    result.update({
        "inputMode":"receiver-import-legacy-v11",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "receiverAcknowledgementDigestEquivalent":acknowledgement,
        "receiverIntegrityVerified":True,
        "downloadedPartCount":part_count,
    })
    return result


def _legacy_report_receiver_source_provenance(manifest,scan_id,place_id,part_count,
                                              object_count,actual_digests):
    if set(manifest)!=_LEGACY_REPORT_RECEIVER_PROVENANCE_FIELDS:
        fail("Invalid legacy report receiver provenance schema")
    if (manifest.get("schemaVersion")!="30.2.receiver-import-legacy-reports.1"
            or manifest.get("scanId")!=scan_id or manifest.get("placeId")!=place_id
            or manifest.get("partCount")!=part_count
            or manifest.get("expectedParts")!=part_count
            or manifest.get("objectCount")!=object_count):
        fail("Invalid legacy report receiver provenance identity")
    metadata=manifest.get("metadata")
    if (not isinstance(metadata,dict) or metadata.get("scanId")!=scan_id
            or metadata.get("placeId")!=place_id or metadata.get("partCount")!=part_count):
        fail("Invalid legacy report receiver provenance metadata")
    integrity=manifest.get("receiverIntegrity")
    if (not isinstance(integrity,dict) or integrity.get("scanId")!=scan_id
            or integrity.get("placeId")!=place_id
            or integrity.get("partCount")!=part_count
            or integrity.get("receivedParts")!=part_count
            or integrity.get("missingParts")!=[]
            or integrity.get("indexedObjects")!=object_count
            or integrity.get("uniqueObjectKeys")!=object_count
            or integrity.get("duplicateObjectKeys")!=0
            or integrity.get("identityErrors")!=[]
            or integrity.get("expectedObjects")!=object_count
            or integrity.get("complete") is not True
            or integrity.get("integrityStatus")!="verified-after-retrieval"):
        fail("Invalid legacy report receiver provenance integrity")
    entries=manifest.get("retrievedPartContentDigests")
    if not isinstance(entries,list) or len(entries)!=part_count:
        fail("Invalid legacy report receiver provenance digests")
    digests={}
    for entry in entries:
        if not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}:
            fail("Invalid legacy report receiver provenance digest")
        index=entry.get("partIndex");digest=entry.get("sha256")
        if (type(index) is not int or not 1<=index<=part_count or index in digests
                or not isinstance(digest,str) or len(digest)!=64
                or any(character not in "0123456789abcdef" for character in digest)
                or actual_digests.get(index)!=digest):
            fail("Invalid legacy report receiver provenance digest")
        digests[index]=digest
    pages=manifest.get("legacyReportPagesScanned")
    records=manifest.get("legacyReportRecordsMatched")
    acknowledgement=manifest.get("receiverAcknowledgementDigestEquivalent")
    if (manifest.get("resumableRetrievalEnabled") is not False
            or manifest.get("resumedPartCount")!=0
            or manifest.get("downloadedPartCount")!=part_count
            or manifest.get("resumeCheckpointAuthenticated") is not False
            or manifest.get("receiverStoredPayloadDigestsRevalidatedThisRun") is not False
            or manifest.get("receiverStoredPayloadDigestsVerified") is not False
            or type(acknowledgement) is not bool
            or manifest.get("receiverIntegrityVerified") is not True
            or manifest.get("receiverResponseAuthenticityVerified") is not False
            or manifest.get("localPayloadEquivalent") is not False
            or manifest.get("receiverReportedIntegrityUnavailable") is not True
            or type(pages) is not int or pages<=0
            or type(records) is not int or records<=0
            or not isinstance(manifest.get("note"),str)):
        fail("Invalid legacy report receiver provenance claims")
    result=_base_source_provenance(scan_id,place_id,part_count)
    result.update({
        "inputMode":"receiver-import-legacy-reports",
        "partContentDigests":[{"partIndex":index,"sha256":digests[index]}
                              for index in range(1,part_count+1)],
        "receiverAcknowledgementDigestEquivalent":acknowledgement,
        "receiverIntegrityVerified":True,
        "downloadedPartCount":part_count,
    })
    return result


def compile_scan(directory):
    files=sorted(pathlib.Path(directory).glob("*.json"))
    if not files: fail("No JSON scan parts found")
    parts=[]
    part_file_digests=[]
    local_manifests=[]
    receiver_manifests=[]
    for file in files:
        raw=file.read_bytes()
        if len(raw)>3_000_000: fail(f"Part too large: {file.name}")
        data=json.loads(raw)
        if not isinstance(data,dict) or not isinstance(data.get("objects"),list):
            if isinstance(data,dict) and "partIndex" not in data and _RECEIVER_MARKERS & set(data):
                receiver_manifests.append(data)
                continue
            if isinstance(data,dict) and "partIndex" not in data and ("objectCount" in data or "metadata" in data):
                local_manifests.append(data)
                continue
            fail(f"Invalid part: {file.name}")
        parts.append(data)
        part_file_digests.append(hashlib.sha256(raw).hexdigest())
    if not parts: fail("No multipart payloads found")
    first=parts[0]
    scan_id=first.get("scanId"); place_id=first.get("placeId")
    count=first.get("partCount")
    if not isinstance(scan_id,str) or not isinstance(place_id,int) or not isinstance(count,int) or count<1 or count>2000:
        fail("Invalid scan identity")
    if len(receiver_manifests)>1:
        fail("Multiple receiver provenance manifests")

    for manifest in local_manifests:
        if ((manifest.get("scanId") is not None and manifest.get("scanId")!=scan_id)
                or (manifest.get("placeId") is not None and manifest.get("placeId")!=place_id)
                or (manifest.get("partCount") is not None and manifest.get("partCount")!=count)
                or (manifest.get("expectedParts") is not None and manifest.get("expectedParts")!=count)):
            fail("Local manifest identity mismatch")

    by_index={}
    for part,raw_digest in zip(parts,part_file_digests):
        index=part.get("partIndex")
        if part.get("scanId")!=scan_id or part.get("placeId")!=place_id or part.get("partCount")!=count:
            fail("Mixed scan IDs, place IDs, or part counts")
        if not isinstance(index,int) or not 1<=index<=count: fail("Invalid part index")
        fingerprint=hashlib.sha256(json.dumps(part,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        if index in by_index:
            if by_index[index][0]!=fingerprint: fail(f"Conflicting duplicate part {index}")
            if by_index[index][2]!=raw_digest:
                fail(f"Conflicting duplicate part bytes {index}")
            continue
        by_index[index]=(fingerprint,part,raw_digest)
    missing=[i for i in range(1,count+1) if i not in by_index]
    if missing: fail(f"Missing parts: {missing[:30]} (total {len(missing)})")
    ordered=[by_index[i][1] for i in range(1,count+1)]
    actual_part_digests={i:by_index[i][2] for i in range(1,count+1)}
    if any(not isinstance(o,dict) for p in ordered for o in p["objects"]):
        fail("Malformed object record")
    objects=[o for p in ordered for o in p["objects"]]
    if len(objects)>2_000_000: fail("Object count exceeds safety limit")

    metadata=next((p for p in ordered if isinstance(p.get("scanStats"),dict)),None)
    if metadata is None: fail("Missing scan metadata")
    requested_capability=metadata.get("featureRequest")
    if requested_capability is not None:
        if (not isinstance(requested_capability,str) or not requested_capability
                or len(requested_capability.encode("utf-8"))>240
                or requested_capability!=requested_capability.strip()
                or any(unicodedata.category(character)=="Cc"
                       for character in requested_capability)):
            fail("Invalid feature request")

    expected=metadata["scanStats"].get("recorded")
    if expected is None: expected=metadata["scanStats"].get("recordedObjects")
    if expected is not None and expected!=len(objects):
        fail(f"Object count mismatch: expected {expected}, received {len(objects)}")
    if any(manifest.get("objectCount") is not None
           and manifest.get("objectCount")!=len(objects) for manifest in local_manifests):
        fail("Local manifest object count mismatch")
    interaction_diagnostics=metadata.get("interactionDiagnostics") if isinstance(metadata.get("interactionDiagnostics"),dict) else {}
    diagnostics_chunks: dict[str, list[tuple[int, list[dict]]]] = {}
    for p in ordered:
        chunk=p.get("interactionDiagnosticsChunk")
        if chunk is None:
            continue
        if not isinstance(chunk,list):
            fail("Malformed interaction diagnostics chunk")
        chunk_key=p.get("interactionDiagnosticsChunkKey")
        chunk_start=p.get("interactionDiagnosticsChunkStart")
        if not isinstance(chunk_key,str) or not chunk_key:
            fail("Malformed interaction diagnostics chunk key")
        if type(chunk_start) is not int or chunk_start<1:
            fail("Malformed interaction diagnostics chunk start")
        if any(not isinstance(item,dict) for item in chunk):
            fail("Malformed interaction diagnostics chunk item")
        diagnostics_chunks.setdefault(chunk_key,[]).append((chunk_start,chunk))

    ITEM_FRAGMENT_SCHEMA="30.6.interaction-diagnostics-item-fragment.1"
    HISTORY_FRAGMENT_SCHEMA="30.6.interaction-history-fragment.1"

    def _decode_hex_utf8_json_fragment(hex_payload, context):
        if (not isinstance(hex_payload,str) or not hex_payload
                or len(hex_payload)%2!=0):
            fail(f"Malformed {context} hex payload")
        try:
            payload=bytes.fromhex(hex_payload)
        except ValueError:
            fail(f"Corrupt {context} hex payload")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError:
            fail(f"Invalid UTF-8 in {context} hex payload")

    def _reconstruct_fragmented_diagnostic_items(chunk_key, merged):
        rebuilt=[]
        pointer=0
        seen_record_ids=set()
        while pointer<len(merged):
            item=merged[pointer]
            if not (isinstance(item,dict) and item.get("schemaVersion")==ITEM_FRAGMENT_SCHEMA):
                rebuilt.append(item)
                pointer+=1
                continue

            record_id=item.get("recordId")
            if not isinstance(record_id,str) or not record_id:
                fail(f"Malformed diagnostic fragment record id for {chunk_key}")
            if record_id in seen_record_ids:
                fail(f"Duplicate diagnostic fragment record id for {chunk_key}: {record_id}")
            seen_record_ids.add(record_id)

            expected_fragment_count=item.get("fragmentCount")
            expected_encoded_length=item.get("encodedLength")
            if (type(expected_fragment_count) is not int or expected_fragment_count<1
                    or type(expected_encoded_length) is not int or expected_encoded_length<0):
                fail(f"Malformed diagnostic fragment header for {chunk_key}")

            expected_index=1
            pieces=[]
            while pointer<len(merged):
                fragment=merged[pointer]
                if not (isinstance(fragment,dict)
                        and fragment.get("schemaVersion")==ITEM_FRAGMENT_SCHEMA
                        and fragment.get("recordId")==record_id):
                    break
                fragment_index=fragment.get("fragmentIndex")
                fragment_count=fragment.get("fragmentCount")
                fragment_encoding=fragment.get("fragmentEncoding")
                fragment_hex=fragment.get("fragmentHex")
                fragment_hex_length=fragment.get("fragmentHexLength")
                if (type(fragment_index) is not int or fragment_index!=expected_index
                        or fragment_count!=expected_fragment_count
                        or fragment_encoding not in {None,"hex-utf8-json"}
                        or not isinstance(fragment_hex,str)
                        or (fragment_hex_length is not None
                            and (type(fragment_hex_length) is not int
                                 or fragment_hex_length!=len(fragment_hex)))):
                    fail(f"Malformed diagnostic fragment sequence for {chunk_key}")
                pieces.append(fragment_hex)
                expected_index+=1
                pointer+=1

            if expected_index-1!=expected_fragment_count:
                fail(f"Missing diagnostic fragments for {chunk_key}")

            encoded_json=_decode_hex_utf8_json_fragment(
                "".join(pieces), f"diagnostic item for {chunk_key}")
            if len(encoded_json)!=expected_encoded_length:
                fail(f"Diagnostic fragment length mismatch for {chunk_key}")
            try:
                reconstructed=json.loads(encoded_json)
            except json.JSONDecodeError:
                fail(f"Diagnostic fragment decode failed for {chunk_key}")
            if not isinstance(reconstructed,dict):
                fail(f"Diagnostic fragment decoded non-object for {chunk_key}")
            rebuilt.append(reconstructed)
        return rebuilt

    def _reconstruct_fragmented_history(history_items):
        rebuilt=[]
        pointer=0
        seen_record_ids=set()
        while pointer<len(history_items):
            item=history_items[pointer]
            if not (isinstance(item,dict) and item.get("schemaVersion")==HISTORY_FRAGMENT_SCHEMA):
                rebuilt.append(item)
                pointer+=1
                continue

            record_id=item.get("recordId")
            if not isinstance(record_id,str) or not record_id:
                fail("Malformed history fragment record id")
            if record_id in seen_record_ids:
                fail(f"Duplicate history fragment record id: {record_id}")
            seen_record_ids.add(record_id)

            expected_fragment_count=item.get("fragmentCount")
            expected_encoded_length=item.get("encodedLength")
            if (type(expected_fragment_count) is not int or expected_fragment_count<1
                    or type(expected_encoded_length) is not int or expected_encoded_length<0):
                fail("Malformed history fragment header")

            expected_index=1
            pieces=[]
            while pointer<len(history_items):
                fragment=history_items[pointer]
                if not (isinstance(fragment,dict)
                        and fragment.get("schemaVersion")==HISTORY_FRAGMENT_SCHEMA
                        and fragment.get("recordId")==record_id):
                    break
                fragment_index=fragment.get("fragmentIndex")
                fragment_count=fragment.get("fragmentCount")
                fragment_encoding=fragment.get("fragmentEncoding")
                fragment_hex=fragment.get("fragmentHex")
                fragment_hex_length=fragment.get("fragmentHexLength")
                if (type(fragment_index) is not int or fragment_index!=expected_index
                        or fragment_count!=expected_fragment_count
                        or fragment_encoding not in {None,"hex-utf8-json"}
                        or not isinstance(fragment_hex,str)
                        or (fragment_hex_length is not None
                            and (type(fragment_hex_length) is not int
                                 or fragment_hex_length!=len(fragment_hex)))):
                    fail("Malformed history fragment sequence")
                pieces.append(fragment_hex)
                expected_index+=1
                pointer+=1

            if expected_index-1!=expected_fragment_count:
                fail("Missing history fragments")

            encoded_json=_decode_hex_utf8_json_fragment(
                "".join(pieces), "history item")
            if len(encoded_json)!=expected_encoded_length:
                fail("History fragment length mismatch")
            try:
                reconstructed=json.loads(encoded_json)
            except json.JSONDecodeError:
                fail("History fragment decode failed")
            if not isinstance(reconstructed,dict):
                fail("History fragment decoded non-object")
            rebuilt.append(reconstructed)
        return rebuilt

    for chunk_key,segments in diagnostics_chunks.items():
        segments.sort(key=lambda entry: entry[0])
        expected_start=1
        merged: list[dict] = []
        for start,items in segments:
            if start!=expected_start:
                fail(f"Interaction diagnostics chunk sequence mismatch for {chunk_key}")
            merged.extend(items)
            expected_start += len(items)
        rebuilt=_reconstruct_fragmented_diagnostic_items(chunk_key, merged)
        declared_total=interaction_diagnostics.get(f"{chunk_key}Total")
        if declared_total is not None and (type(declared_total) is not int or declared_total<0
                                          or declared_total!=len(rebuilt)):
            fail(f"Interaction diagnostics chunk total mismatch for {chunk_key}")
        interaction_diagnostics[chunk_key]=rebuilt

    summary_chunk_fields=interaction_diagnostics.get("chunkedInteractionDiagnosticSummaryFields")
    if summary_chunk_fields is not None:
        if not isinstance(summary_chunk_fields,list):
            fail("Malformed chunked interaction summary descriptor")
        for descriptor in summary_chunk_fields:
            if not isinstance(descriptor,dict):
                fail("Malformed chunked interaction summary descriptor")
            field=descriptor.get("field")
            fragment_chunk_key=descriptor.get("chunkKey")
            chunk_kind=descriptor.get("chunkKind")
            chunk_encoding=descriptor.get("chunkEncoding")
            if (not isinstance(field,str) or not field
                    or not isinstance(fragment_chunk_key,str) or not fragment_chunk_key):
                fail("Malformed chunked interaction summary descriptor")
            if chunk_kind not in {None,"json-fragment"}:
                fail(f"Unsupported interaction summary chunk kind for {field}")
            if chunk_encoding not in {None,"hex-utf8-json"}:
                fail(f"Unsupported interaction summary chunk encoding for {field}")
            fragments=interaction_diagnostics.get(fragment_chunk_key)
            if not isinstance(fragments,list):
                fail(f"Missing interaction summary fragments for {field}")
            declared_fragment_count=descriptor.get("fragmentCount")
            if declared_fragment_count is not None and (type(declared_fragment_count) is not int
                                                        or declared_fragment_count<1
                                                        or declared_fragment_count!=len(fragments)):
                fail(f"Interaction summary fragment count mismatch for {field}")

            expected_index=1
            pieces=[]
            mode=None
            for fragment in fragments:
                if not isinstance(fragment,dict):
                    fail(f"Malformed interaction summary fragment for {field}")
                fragment_index=fragment.get("fragmentIndex")
                if type(fragment_index) is not int or fragment_index!=expected_index:
                    fail(f"Malformed interaction summary fragment sequence for {field}")
                if isinstance(fragment.get("fragmentHex"),str):
                    if mode is None:
                        mode="hex"
                    if mode!="hex":
                        fail(f"Mixed interaction summary fragment encodings for {field}")
                    fragment_hex=fragment.get("fragmentHex")
                    fragment_hex_length=fragment.get("fragmentHexLength")
                    if (fragment.get("fragmentEncoding") not in {None,"hex-utf8-json"}
                            or (fragment_hex_length is not None
                                and (type(fragment_hex_length) is not int
                                     or fragment_hex_length!=len(fragment_hex)))):
                        fail(f"Malformed interaction summary hex fragment for {field}")
                    pieces.append(fragment_hex)
                else:
                    if mode is None:
                        mode="raw"
                    if mode!="raw":
                        fail(f"Mixed interaction summary fragment encodings for {field}")
                    fragment_text=fragment.get("fragment")
                    fragment_length=fragment.get("fragmentLength")
                    if (not isinstance(fragment_text,str)
                            or (fragment_length is not None and
                                (type(fragment_length) is not int or fragment_length!=len(fragment_text)))):
                        fail(f"Malformed interaction summary fragment sequence for {field}")
                    pieces.append(fragment_text)
                expected_index+=1

            if mode=="hex":
                encoded=_decode_hex_utf8_json_fragment(
                    "".join(pieces), f"interaction summary for {field}")
            else:
                encoded="".join(pieces)

            declared_length=descriptor.get("encodedLength")
            if declared_length is not None and (type(declared_length) is not int
                                                or declared_length!=len(encoded)):
                fail(f"Interaction summary fragment length mismatch for {field}")
            try:
                interaction_diagnostics[field]=json.loads(encoded)
            except json.JSONDecodeError:
                fail(f"Interaction summary fragment decode failed for {field}")

    interaction_observation_summary=_interaction_observation_summary(interaction_diagnostics)
    history=[]
    for p in ordered:
        history.extend(p.get("interactionHistoryChunk") or [])
    if not history:
        history=interaction_diagnostics.get("recentInteractions") or []
    history=_reconstruct_fragmented_history(history)
    if len(history)>2000: fail("Interaction history exceeds 2000 events; refusing silent truncation")
    if any(not isinstance(event,dict) for event in history): fail("Malformed interaction history event")
    expected_session=metadata.get("sessionId")
    if expected_session is not None and not isinstance(expected_session,str):
        fail("Malformed scan session identity")
    timed_interactions=0
    for event in history:
        if _session_timing(event,expected_session) is not None:timed_interactions+=1
        if "pathIdentity" in event:
            identity=bounded_path_identity(event["pathIdentity"])
            if (identity is None or not isinstance(event.get("path"),str)
                    or ".".join(segment["name"] for segment in identity)!=event["path"]):
                event.pop("pathIdentity",None)
                continue
            event["pathIdentity"]=identity
    history_evidence=[]
    for event in history:
        evidence=_correlation_evidence(event);evidence.update(_baseline_evidence(event))
        history_evidence.append((event,evidence))
    feature_evidence=metadata.get("featureEvidence") or {}
    readiness=metadata.get("featureReadiness") or {}
    # Evidence is descriptive, never an authorization to invoke arbitrary remotes.
    feature_names=set()
    for source in (feature_evidence,readiness):
        if isinstance(source,dict): feature_names.update(str(k) for k in source.keys())
    for item in history:
        if isinstance(item,dict) and item.get("featureCandidate"):
            feature_names.add(str(item["featureCandidate"]))
    counts=collections.Counter(str(o.get("class","Unknown")) for o in objects)
    paths=collections.Counter((str(o.get("path","")),str(o.get("scanOrdinal",""))) for o in objects)
    if any(not o.get("path") for o in objects): fail("Object missing path")
    actionable_classes={"ProximityPrompt","ClickDetector","TextButton","ImageButton","Tool"}
    actionable=[]
    actionable_total=0
    for obj in objects:
        if obj.get("class") not in actionable_classes:continue
        actionable_total+=1
        if len(actionable)>=20_000:continue
        actionable.append({key:obj[key] for key in (
            "path","class","scanOrdinal","interaction","guiControl","position","size","tool")
            if key in obj})
    duplicate_count=sum(v-1 for v in paths.values())
    if duplicate_count:
        fail(f"Duplicate object identities: {duplicate_count}")
    if receiver_manifests:
        receiver_manifest=receiver_manifests[0]
        if receiver_manifest.get("schemaVersion")=="30.2.receiver-import-legacy.1":
            source_provenance=_legacy_receiver_source_provenance(
                receiver_manifest,scan_id,place_id,count,len(objects),actual_part_digests)
        elif receiver_manifest.get("schemaVersion")=="30.2.receiver-import-legacy-reports.1":
            source_provenance=_legacy_report_receiver_source_provenance(
                receiver_manifest,scan_id,place_id,count,len(objects),actual_part_digests)
        else:
            source_provenance=_receiver_source_provenance(
                receiver_manifest,scan_id,place_id,count,len(objects),actual_part_digests)
    else:
        source_provenance=_local_source_provenance(
            scan_id,place_id,count,actual_part_digests)

    features=[]
    for name in sorted(feature_names):
        event_records=[record for record in history_evidence if record[0].get("featureCandidate")==name]
        events=[record[0] for record in event_records]
        correlations=[record[1] for record in event_records]
        observed=sum(1 for e in events if e.get("evidenceLevel"))
        corroborated=sum(1 for e in events if e.get("clientStateCorroborated") is True
            or (isinstance(e.get("featureStateEvidence"),dict)
                and e["featureStateEvidence"].get("status")=="client-state-consistent"))
        transitions=sum(1 for e in events if e.get("stateChanges") or e.get("guiStateChanges"))
        outcomes=sum(1 for e in events if e.get("outcomeVerified") is True)
        candidates=sum(item["candidate"] for item in correlations)
        state_correlations=sum(item["state"] for item in correlations)
        gui_correlations=sum(item["gui"] for item in correlations)
        pre_activation=sum(item["timing"]=="pre-activation" for item in correlations)
        callback_baselines=sum(item["timing"]=="activation-callback" for item in correlations)
        unknown_baselines=sum(item["timing"]=="unknown" for item in correlations)
        features.append({
            "feature":name,"interactionEvents":len(events),
            "observedEvents":observed,"verifiedClientOutcomes":outcomes,
            "clientCorroboratedEvents":corroborated,"temporalTransitionEvents":transitions,
            "observableOutcomeCandidates":candidates,
            "featureStateCorrelations":state_correlations,"featureGuiCorrelations":gui_correlations,
            "preActivationBaselineEvents":pre_activation,
            "activationCallbackBaselineEvents":callback_baselines,
            "unknownBaselineTimingEvents":unknown_baselines,
            "status":"client-outcome-observed" if outcomes else
                ("observable-outcome-candidate-unverified" if candidates else
                 ("interaction-observed" if observed else "discovered")),
            "implementationReady":False,
            "reason":"No verified, permitted reproducible implementation contract in passive scan",
            "evidence":feature_evidence.get(name) if isinstance(feature_evidence,dict) else None,
            "readiness":readiness.get(name) if isinstance(readiness,dict) else None,
        })
    source_diagnostics=metadata.get("diagnostics") or {}
    if source_diagnostics and source_diagnostics.get("complete") is False:
        fail("Source diagnostics indicate incomplete scan")
    integrity={"scanId":scan_id,"placeId":place_id,"parts":count,"objects":len(objects),
               "uniqueObjectIdentities":len(paths),"interactionEvents":len(history),
               "scanComplete":bool(metadata["scanStats"].get("complete"))}
    if not integrity["scanComplete"]: fail("Source scan reports incomplete root coverage")
    universal_discovery=_universal_discovery(objects,actionable,history)
    plan={"schemaVersion":"20.0","integrity":integrity,"featureCount":len(features),
          "features":features,"classCounts":dict(counts),
          "requestedCapability":requested_capability,
          "sourceProvenance":source_provenance,
          "sourceDiagnostics":{"omittedObjects":metadata["scanStats"].get("omitted"),
              "rootAccountingValid":source_diagnostics.get("rootAccountingValid"),
              "scanMode":metadata["scanStats"].get("mode"),
              "snapshotId":metadata.get("snapshotId"),
              "sessionTimedInteractionEvents":timed_interactions,
              "sessionTimingComplete":bool(history) and timed_interactions==len(history)},
          "interactionDiagnostics":interaction_diagnostics,
          "interactionObservationSummary":interaction_observation_summary,
          "observedInteractionHistory":history,
          "actionableObjects":actionable,"actionableObjectCount":actionable_total,
          "universalDiscovery":universal_discovery,
          "actionableObjectsTruncated":actionable_total>len(actionable),
          "releaseGate":{"gameplayAutomationApproved":False,
                         "reason":"Passive inspection cannot establish replayable server-authoritative actions",
                         "nextStep":"Review feature contracts and validate supported operations in a permitted environment"}}
    return plan

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parts_dir");parser.add_argument("--output",default="build")
    args=parser.parse_args()
    try: plan=compile_scan(args.parts_dir)
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        print("INTEGRITY FAILURE:",exc,file=sys.stderr);return 2
    out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
    (out/"capability-plan.json").write_text(json.dumps(plan,indent=2,ensure_ascii=False)+"\n")
    lines=[f"# Scan capability plan — {plan['integrity']['placeId']}","",
           f"Verified parts: {plan['integrity']['parts']}; objects: {plan['integrity']['objects']}; interactions: {plan['integrity']['interactionEvents']}.","",
           "| Feature | Events | Client outcomes | Status |","|---|---:|---:|---|"]
    for f in plan["features"]:
        lines.append(f"| {f['feature'].replace('|','/')} | {f['interactionEvents']} | {f['verifiedClientOutcomes']} | {f['status']} |")
    lines+=["","**Gameplay automation is not automatically approved.** A scan proves observation, not a replayable API."]
    (out/"capability-plan.md").write_text("\n".join(lines)+"\n")
    print(f"PASS: {len(plan['features'])} feature candidates, {plan['integrity']['objects']} objects; outputs in {out}")
    return 0

if __name__=="__main__": sys.exit(main())
