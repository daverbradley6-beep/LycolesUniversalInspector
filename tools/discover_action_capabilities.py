#!/usr/bin/env python3
"""Discover evidence-bounded executable client action candidates from a compiled scan."""
import copy
import json
import math
import re

SCHEMA="111.action-capabilities.1"
SAFE_PATH=re.compile(r"^[^\x00-\x1f]{1,400}$")


def _increased(change):
    return (isinstance(change,dict) and type(change.get("before")) in (int,float)
            and type(change.get("after")) in (int,float)
            and change["after"]>change["before"])


def _event_changes(event):
    result=[];seen=set();collections=[event.get("stateChanges") or []]
    windows=event.get("observationWindows") or []
    if not isinstance(windows,list) or len(windows)>10:raise ValueError("Malformed observation windows")
    for window in windows:
        if not isinstance(window,dict):raise ValueError("Malformed observation windows")
        collections.append(window.get("stateChanges") or [])
    if any(not isinstance(values,list) or len(values)>100 for values in collections):
        raise ValueError("Malformed state transition evidence")
    for values in collections:
        for change in values:
            if not isinstance(change,dict):raise ValueError("Malformed state transition evidence")
            identity=json.dumps(change,sort_keys=True,ensure_ascii=False)
            if identity not in seen:seen.add(identity);result.append(change)
            if len(result)>200:raise ValueError("Excessive state transition evidence")
    return result

def _event_gui_changes(event):
    result=[];seen=set();collections=[event.get("guiStateChanges") or []]
    windows=event.get("observationWindows") or []
    if not isinstance(windows,list) or len(windows)>10:raise ValueError("Malformed observation windows")
    for window in windows:
        if not isinstance(window,dict):raise ValueError("Malformed observation windows")
        collections.append(window.get("guiChanges") or [])
    if any(not isinstance(values,list) or len(values)>100 for values in collections):
        raise ValueError("Malformed GUI transition evidence")
    for values in collections:
        for change in values:
            if not isinstance(change,dict):raise ValueError("Malformed GUI transition evidence")
            path=change.get("path")
            if not isinstance(path,str) or not SAFE_PATH.fullmatch(path):
                raise ValueError("Malformed GUI transition evidence")
            identity=json.dumps(change,sort_keys=True,ensure_ascii=False)
            if identity not in seen:seen.add(identity);result.append(change)
            if len(result)>200:raise ValueError("Excessive GUI transition evidence")
    return result


def _evidence_tier(state_changes,gui_changes):
    if state_changes and gui_changes:return "interaction-with-temporal-state-and-gui-change"
    if state_changes:return "interaction-with-temporal-state-change"
    if gui_changes:return "interaction-with-temporal-gui-change"
    return "interaction-observed"


_BASELINE_SOURCES={"GuiButton.InputBegan","ProximityPrompt.PromptButtonHoldBegan",
    "Tool.Equipped","activation-callback-fallback"}

def _baseline_evidence(event):
    fields=("baselineSource","baselineTiming","baselineAgeSeconds",
        "preActivationBaselineAvailable")
    if not any(field in event for field in fields):
        return {"timing":"unknown","source":None,"preActivationBaselineAvailable":False,
            "possibleSynchronousLoss":True}
    source=event.get("baselineSource");timing=event.get("baselineTiming")
    available=event.get("preActivationBaselineAvailable");age=event.get("baselineAgeSeconds")
    expected="activation-callback" if source=="activation-callback-fallback" else "pre-activation"
    if (source not in _BASELINE_SOURCES or timing!=expected or type(available) is not bool
            or available!=(timing=="pre-activation") or (age is not None and
            (type(age) not in (int,float) or type(age) is bool or not math.isfinite(age)
                or not 0<=age<=3600))):
        raise ValueError("Malformed interaction baseline timing")
    return {"timing":timing,"source":source,"preActivationBaselineAvailable":available,
        "possibleSynchronousLoss":not available}

def _baseline_summary():
    return {"events":0,"preActivationEvents":0,"activationCallbackEvents":0,
        "unknownTimingEvents":0,"possibleSynchronousLoss":False}

def _record_baseline(summary,evidence):
    summary["events"]+=1
    field={"pre-activation":"preActivationEvents",
        "activation-callback":"activationCallbackEvents"}.get(
            evidence["timing"],"unknownTimingEvents")
    summary[field]+=1
    summary["possibleSynchronousLoss"]=summary["possibleSynchronousLoss"] or evidence[
        "possibleSynchronousLoss"]


def _path_identity(value):
    if not isinstance(value,list) or not 1<=len(value)<=21:return None
    result=[]
    for segment in value:
        if not isinstance(segment,dict):return None
        name=segment.get("name");class_name=segment.get("className");ordinal=segment.get("ordinal")
        if (not isinstance(name,str) or not 1<=len(name)<=100 or not isinstance(class_name,str)
                or not 1<=len(class_name)<=100 or type(ordinal) is not int or not 1<=ordinal<=10000):return None
        result.append({"name":name,"className":class_name,"ordinal":ordinal})
    return result


def _state_identity(change):
    status=change.get("stateIdentityStatus");value=change.get("stateIdentity")
    if status is None and value is None:return None
    identity=_path_identity(value)
    if (status!="component-resolved" or identity is None
            or identity[0]["name"] not in ("leaderstats","Data")
            or not isinstance(change.get("key"),str)
            or ".".join(segment["name"] for segment in identity)!=change["key"]):
        if status=="unavailable" and value is None:return False
        raise ValueError("Malformed state path identity")
    return identity


_STOPWORDS={"a","an","and","auto","automatic","automatically","for","game","in","mode",
    "of","on","selected","the","to","use","with"}
_USEFUL_TERMS=("buy","claim","collect","egg","hatch","quest","rebirth","reward","sell",
    "teleport","travel","upgrade")
_NAVIGATION_TERMS=("back","close","menu","next","open","page","previous","settings","tab")


def _tokens(value):
    return {token for token in re.findall(r"[a-z0-9]+",str(value).lower())
        if len(token)>2 and token not in _STOPWORDS}


def _prompt_objective(path,feature,action,label,request,state_signals):
    evidence=" ".join(str(value or "") for value in (path,feature,action,label))
    evidence_tokens=_tokens(evidence);request_tokens=_tokens(request or "")
    matched=sorted(evidence_tokens & request_tokens)
    lower=evidence.lower();score=3 if state_signals else 0
    if feature and feature!="other":score+=2
    if action:score+=2
    score+=min(6,len(matched)*3)
    score+=2*sum(term in lower for term in _USEFUL_TERMS)
    score-=3*sum(term in lower for term in _NAVIGATION_TERMS)
    return {"score":score,"requestMatchedTerms":matched,
        "requestAligned":bool(request_tokens and matched),
        "classification":"gameplay-objective-candidate" if score>=5 else "interaction-candidate",
        "objectiveVerified":False}


def _rank_outcomes(signals,request,context):
    request_tokens=_tokens(request or "");context_tokens=_tokens(context)
    ranked=[]
    for source in signals:
        signal=dict(source);key=signal["key"];key_tokens=_tokens(key);lower=key.lower()
        request_matches=sorted(key_tokens & request_tokens)
        context_matches=sorted(key_tokens & context_tokens)
        score=min(9,len(request_matches)*3)+min(3,len(context_matches))
        score+=2*sum(term in lower for term in _USEFUL_TERMS)
        score-=3*sum(term in lower for term in _NAVIGATION_TERMS)
        score+={"increased":2,"changed":1,"decreased":0}.get(signal["change"],0)
        signal["selection"]={"score":score,"requestMatchedTerms":request_matches,
            "contextMatchedTerms":context_matches,"selectedForTrial":False,
            "outcomeVerified":False}
        ranked.append(signal)
    ranked.sort(key=lambda item:(-item["selection"]["score"],item["key"],item["change"]))
    if ranked:ranked[0]["selection"]["selectedForTrial"]=True
    return ranked



def _state_signals(changes_with_identity):
    state_signals=[]
    for change,state_identity in changes_with_identity:
        key=change.get("key")
        if not isinstance(key,str) or not SAFE_PATH.fullmatch(key):
            raise ValueError("Malformed state transition evidence")
        direction=change.get("transition") or ("increased" if _increased(change) else
            "decreased" if type(change.get("before")) in (int,float)
                and type(change.get("after")) in (int,float) and change["after"]<change["before"]
            else "changed")
        state_signals.append({"key":key,"change":direction,
            "stateIdentity":state_identity if isinstance(state_identity,list) else None,
            "generationResolvable":state_identity is not False})
    return state_signals


def _linked_transaction_signals(history):
    linked={}
    for event in history:
        path=event.get("path");control=event.get("controlType")
        transaction=event.get("transactionId");sequence=event.get("sequence")
        if (not isinstance(path,str) or not SAFE_PATH.fullmatch(path)
                or not isinstance(control,str)
                or type(transaction) not in (int,str)
                or type(sequence) is not int):
            continue
        changes=_event_changes(event)
        changes_with_identity=[(change,_state_identity(change)) for change in changes]
        signals=_state_signals(changes_with_identity)
        if not signals:
            continue
        linked.setdefault(str(transaction),[]).append({
            "sequence":sequence,
            "path":path,
            "signals":signals,
        })
    for values in linked.values():
        values.sort(key=lambda item:item["sequence"])
    return linked



def _prompt_metadata(value):
    if not isinstance(value,dict):return {}
    allowed={"actionText","objectText","enabled","holdDuration","maxActivationDistance",
        "keyboardKeyCode","gamepadKeyCode","anchorPath","anchorPosition"}
    if any(key not in allowed for key in value):
        raise ValueError("Malformed prompt prerequisite metadata")
    result={}
    for key in ("actionText","objectText","keyboardKeyCode","gamepadKeyCode","anchorPath"):
        item=value.get(key)
        if item is not None:
            if not isinstance(item,str) or not SAFE_PATH.fullmatch(item):
                raise ValueError("Malformed prompt prerequisite metadata")
            result[key]=item
    enabled=value.get("enabled")
    if enabled is not None:
        if type(enabled) is not bool:raise ValueError("Malformed prompt prerequisite metadata")
        result["enabled"]=enabled
    for key in ("holdDuration","maxActivationDistance"):
        item=value.get(key)
        if item is not None:
            if type(item) not in (int,float) or not math.isfinite(item) or item<0:
                raise ValueError("Malformed prompt prerequisite metadata")
            result[key]=item
    position=value.get("anchorPosition")
    if position is not None:
        if (not isinstance(position,dict) or set(position)!={"x","y","z"}
                or any(type(position[key]) not in (int,float) or not math.isfinite(position[key])
                    for key in ("x","y","z"))):
            raise ValueError("Malformed prompt prerequisite metadata")
        result["anchorPosition"]={key:position[key] for key in ("x","y","z")}
    return result


def _tool_metadata(value):
    if value is None:return None
    if not isinstance(value,dict):raise ValueError("Malformed Tool prerequisite metadata")
    allowed={"tooltip","requiresHandle","canBeDropped","enabled","manualActivationOnly"}
    if set(value)!=allowed:raise ValueError("Malformed Tool prerequisite metadata")
    tooltip=value.get("tooltip")
    if (not isinstance(tooltip,str) or len(tooltip)>120
            or any(ord(character)<32 or ord(character)==127 for character in tooltip)):
        raise ValueError("Malformed Tool prerequisite metadata")
    for key in ("requiresHandle","canBeDropped","enabled","manualActivationOnly"):
        if type(value.get(key)) is not bool:raise ValueError("Malformed Tool prerequisite metadata")
    return {key:value[key] for key in ("tooltip","requiresHandle","canBeDropped",
        "enabled","manualActivationOnly")}


def _gui_metadata(value):
    if value is None:return None
    if not isinstance(value,dict):raise ValueError("Malformed GUI prerequisite metadata")
    allowed={"controlClass","text","visible","active","selectable","autoButtonColor",
        "interactable","ancestorVisible","screenEnabled","withinScrollingBounds",
        "effectiveVisible"}
    if any(key not in allowed for key in value):
        raise ValueError("Malformed GUI prerequisite metadata")
    result={}
    control_class=value.get("controlClass")
    if control_class is not None:
        if control_class not in ("TextButton","ImageButton"):
            raise ValueError("Malformed GUI prerequisite metadata")
        result["controlClass"]=control_class
    text=value.get("text")
    if text is not None:
        if (not isinstance(text,str) or len(text)>100
                or any(ord(character)<32 or ord(character)==127 for character in text)):
            raise ValueError("Malformed GUI prerequisite metadata")
        result["text"]=text
    for key in allowed-{"controlClass","text"}:
        item=value.get(key)
        if item is not None:
            if type(item) is not bool:raise ValueError("Malformed GUI prerequisite metadata")
            result[key]=item
    return result



def _label(path,metadata):
    interaction=metadata.get("interaction") if isinstance(metadata,dict) else None
    if isinstance(interaction,dict):
        value=interaction.get("objectText") or interaction.get("actionText")
        if isinstance(value,str) and value.strip():return value.strip()[:120]
    parts=path.split(".")
    return next((value for value in reversed(parts[:-1]) if value.lower() not in
                 {"prompt","proximityprompt","button"}),parts[-1])[:120]


def analyze(plan):
    integrity=plan.get("integrity") if isinstance(plan,dict) else None
    if (not isinstance(integrity,dict) or integrity.get("scanComplete") is not True
            or type(integrity.get("placeId")) is not int):
        raise ValueError("Complete compiled scan required")
    objects=plan.get("actionableObjects",[])
    history=plan.get("observedInteractionHistory",[])
    if (not isinstance(objects,list) or len(objects)>20_000
            or not isinstance(history,list) or len(history)>2_000):
        raise ValueError("Malformed actionable evidence")
    by_path={}
    class_counts={}
    for item in objects:
        if not isinstance(item,dict):raise ValueError("Malformed actionable object")
        path=item.get("path");kind=item.get("class")
        if not isinstance(path,str) or not SAFE_PATH.fullmatch(path) or not isinstance(kind,str):
            raise ValueError("Malformed actionable object identity")
        by_path.setdefault(path,item)
        class_counts[kind]=class_counts.get(kind,0)+1
    request=plan.get("requestedCapability")
    if request is not None and (not isinstance(request,str) or len(request)>500):
        raise ValueError("Malformed requested capability")
    linked_transaction_signals=_linked_transaction_signals(history)
    observed_actions=[];egg_targets={};prompt_targets={};tool_targets={};gui_targets={}
    for event in history:
        if not isinstance(event,dict):raise ValueError("Malformed interaction event")
        path=event.get("path");control=event.get("controlType")
        if not isinstance(path,str) or not SAFE_PATH.fullmatch(path) or not isinstance(control,str):continue
        identity=_path_identity(event.get("pathIdentity")) if "pathIdentity" in event else None
        if ("pathIdentity" in event and (identity is None
                or ".".join(segment["name"] for segment in identity)!=path)):
            raise ValueError("Malformed interaction path identity")
        changes=_event_changes(event);gui_changes=_event_gui_changes(event)
        changes_with_identity=[(change,_state_identity(change)) for change in changes]
        direct_state_signals=_state_signals(changes_with_identity)
        inherited_state_signals=[]
        transaction=event.get("transactionId");sequence=event.get("sequence")
        if (not direct_state_signals and type(transaction) in (int,str)
                and type(sequence) is int):
            inherited_seen=set()
            for linked in linked_transaction_signals.get(str(transaction),[]):
                if linked["sequence"]<sequence or linked["path"]==path:
                    continue
                for signal in linked["signals"]:
                    marker=(signal["key"],signal["change"])
                    if marker in inherited_seen:
                        continue
                    inherited_seen.add(marker)
                    inherited_state_signals.append({**signal,
                        "inheritedFromLinkedTransaction":True,
                        "sourcePath":linked["path"],
                        "sourceSequence":linked["sequence"]})
        state_signals=direct_state_signals or inherited_state_signals
        gui_signals=[{"path":change["path"],"change":change.get("transition") or
            ("visibility-changed" if change.get("beforeVisible")!=change.get("afterVisible")
                else "active-changed")} for change in gui_changes]
        tier=_evidence_tier(state_signals,gui_signals)
        baseline=_baseline_evidence(event)
        observed_actions.append({"path":path,"pathIdentity":identity,"controlType":control,
            "featureCandidate":event.get("featureCandidate"),
            "actionCandidate":(event.get("workflow") or {}).get("action")
                if isinstance(event.get("workflow"),dict) else None,
            "evidenceTier":tier,"observableOutcomeCandidate":bool(state_signals or gui_signals),
            "stateChanges":changes,"stateOutcomeSignals":state_signals,
            "linkedTransactionOutcomeSignals":inherited_state_signals,
            "outcomeEvidenceSource":"direct-event" if direct_state_signals
                else "linked-transaction-followup" if inherited_state_signals else "none",
            "guiOutcomeSignals":gui_signals,"baselineEvidence":baseline,
            "replayContractAvailable":False,
            "causalityProven":False,"outcomeVerified":False})
        if control=="ProximityPrompt.Triggered":
            raw_metadata=event.get("controlMetadata")
            event_metadata=_prompt_metadata(raw_metadata) if isinstance(raw_metadata,dict) else {}
            label=_label(path,{"interaction":event_metadata} if event_metadata else by_path.get(path,{}))
            target=prompt_targets.setdefault(path,{"path":path,"label":label,"controlType":control,
                "pathIdentity":identity,"identityMode":"component" if identity else "legacy-flat-path",
                "featureCandidate":event.get("featureCandidate"),
                "actionCandidate":(event.get("workflow") or {}).get("action")
                    if isinstance(event.get("workflow"),dict) else None,
                "observedTriggers":0,"outcomeSignals":[],"guiOutcomeSignals":[],
                "baselineEvidence":_baseline_summary(),
                "evidenceTier":"interaction-observed","trialGenerationReady":False,
                "prerequisites":{"executorFireProximityPrompt":True,"characterRoot":True,
                    "targetAnchor":True,"promptEnabledAtRuntime":True},
                "prerequisiteEvidence":{"metadataSnapshots":[],"metadataDriftObserved":False},
                "temporalCorrelationOnly":True,"causalityProven":False,
                "runtimeVerified":False,"gameplayVerified":False})
            if identity:target["pathIdentity"]=identity;target["identityMode"]="component"
            _record_baseline(target["baselineEvidence"],baseline)
            if event_metadata:
                snapshots=target["prerequisiteEvidence"]["metadataSnapshots"]
                if event_metadata not in snapshots:
                    if len(snapshots)>=8:raise ValueError("Excessive prompt prerequisite metadata drift")
                    snapshots.append(event_metadata)
                target["prerequisiteEvidence"]["metadataDriftObserved"]=len(snapshots)>1
                target["promptMetadata"]=copy.deepcopy(snapshots[0])
            target["observedTriggers"]+=1
            target["evidenceTier"]=tier
            seen_outcomes={(item["key"],item["change"]) for item in target["outcomeSignals"]}
            for signal in state_signals:
                marker=(signal["key"],signal["change"])
                if signal["generationResolvable"] and marker not in seen_outcomes:
                    target["outcomeSignals"].append(signal);seen_outcomes.add(marker)
            seen_gui={(item["path"],item["change"]) for item in target["guiOutcomeSignals"]}
            for signal in gui_signals:
                marker=(signal["path"],signal["change"])
                if marker not in seen_gui:target["guiOutcomeSignals"].append(signal);seen_gui.add(marker)
            target["trialGenerationReady"]=bool(target["outcomeSignals"])
        if control=="Tool.Activated":
            raw_metadata=event.get("controlMetadata")
            event_metadata=_tool_metadata(raw_metadata)
            label=identity[-1]["name"] if identity else path.rsplit(".",1)[-1]
            target=tool_targets.setdefault(path,{"path":path,"label":label,
                "controlType":control,"pathIdentity":identity,"identityAmbiguous":False,
                "identityMode":"component" if identity else "unresolved",
                "featureCandidate":event.get("featureCandidate"),
                "actionCandidate":(event.get("workflow") or {}).get("action")
                    if isinstance(event.get("workflow"),dict) else None,
                "observedActivations":0,"outcomeSignals":[],"guiOutcomeSignals":[],
                "baselineEvidence":_baseline_summary(),
                "evidenceTier":"interaction-observed","activationContractReady":False,
                "trialGenerationReady":False,
                "prerequisites":{"officialToolActivate":True,"humanoidEquipTool":True,
                    "toolEnabledAtRuntime":True,"uniqueToolIdentityAtRuntime":True},
                "prerequisiteEvidence":{"metadataSnapshots":[],"metadataDriftObserved":False},
                "temporalCorrelationOnly":True,"causalityProven":False,
                "runtimeVerified":False,"gameplayVerified":False})
            if identity:
                if target.get("pathIdentity") not in (None,identity):target["identityAmbiguous"]=True
                elif target.get("pathIdentity") is None:
                    target["pathIdentity"]=identity;target["identityMode"]="component"
            _record_baseline(target["baselineEvidence"],baseline)
            if event_metadata:
                snapshots=target["prerequisiteEvidence"]["metadataSnapshots"]
                if event_metadata not in snapshots:
                    if len(snapshots)>=8:raise ValueError("Excessive Tool prerequisite metadata drift")
                    snapshots.append(event_metadata)
                target["prerequisiteEvidence"]["metadataDriftObserved"]=len(snapshots)>1
                target["toolMetadata"]=copy.deepcopy(snapshots[0])
            target["observedActivations"]+=1
            target["evidenceTier"]=tier
            seen_outcomes={(item["key"],item["change"]) for item in target["outcomeSignals"]}
            for signal in state_signals:
                marker=(signal["key"],signal["change"])
                if signal["generationResolvable"] and marker not in seen_outcomes:
                    target["outcomeSignals"].append(signal);seen_outcomes.add(marker)
            seen_gui={(item["path"],item["change"]) for item in target["guiOutcomeSignals"]}
            for signal in gui_signals:
                marker=(signal["path"],signal["change"])
                if marker not in seen_gui:target["guiOutcomeSignals"].append(signal);seen_gui.add(marker)
        if control=="GuiButton.Activated":
            event_metadata=_gui_metadata(event.get("controlMetadata"))
            label=(event_metadata or {}).get("text") or (identity[-1]["name"] if identity else path.rsplit(".",1)[-1])
            target=gui_targets.setdefault(path,{"path":path,"label":label,
                "controlType":control,"pathIdentity":identity,"identityAmbiguous":False,
                "identityMode":"component" if identity else "unresolved",
                "featureCandidate":event.get("featureCandidate"),
                "actionCandidate":(event.get("workflow") or {}).get("action")
                    if isinstance(event.get("workflow"),dict) else None,
                "observedActivations":0,"outcomeSignals":[],"guiOutcomeSignals":[],
                "baselineEvidence":_baseline_summary(),
                "evidenceTier":"interaction-observed","guidedActivationContractReady":False,
                "trialGenerationReady":False,"automaticActivationAvailable":False,
                "prerequisites":{"officialActivatedObservation":True,
                    "manualUserActivation":True,"uniqueControlIdentityAtRuntime":True,
                    "controlAvailableAtRuntime":True},
                "prerequisiteEvidence":{"metadataSnapshots":[],"metadataDriftObserved":False},
                "temporalCorrelationOnly":True,"causalityProven":False,
                "runtimeVerified":False,"gameplayVerified":False})
            if identity:
                if target.get("pathIdentity") not in (None,identity):target["identityAmbiguous"]=True
                elif target.get("pathIdentity") is None:
                    target["pathIdentity"]=identity;target["identityMode"]="component"
            _record_baseline(target["baselineEvidence"],baseline)
            if event_metadata:
                snapshots=target["prerequisiteEvidence"]["metadataSnapshots"]
                if event_metadata not in snapshots:
                    if len(snapshots)>=8:raise ValueError("Excessive GUI prerequisite metadata drift")
                    snapshots.append(event_metadata)
                target["prerequisiteEvidence"]["metadataDriftObserved"]=len(snapshots)>1
                target["guiMetadata"]=copy.deepcopy(snapshots[0])
            target["observedActivations"]+=1
            target["evidenceTier"]=tier
            seen_outcomes={(item["key"],item["change"]) for item in target["outcomeSignals"]}
            for signal in state_signals:
                marker=(signal["key"],signal["change"])
                if signal["generationResolvable"] and marker not in seen_outcomes:
                    target["outcomeSignals"].append(signal);seen_outcomes.add(marker)
            seen_gui={(item["path"],item["change"]) for item in target["guiOutcomeSignals"]}
            for signal in gui_signals:
                marker=(signal["path"],signal["change"])
                if marker not in seen_gui:target["guiOutcomeSignals"].append(signal);seen_gui.add(marker)



        lower=path.lower()
        hatch_changes=[(change,state_identity) for change,state_identity in changes_with_identity
            if state_identity is not False and isinstance(change.get("key"),str)
            and ("hatch" in change["key"].lower() or "egg" in change["key"].lower())
            and _increased(change)]
        if control=="ProximityPrompt.Triggered" and ("egg" in lower or "hatch" in lower):
            event_metadata=event.get("controlMetadata") if isinstance(event.get("controlMetadata"),dict) else {}
            target=egg_targets.setdefault(path,{"path":path,
                "label":_label(path,{"interaction":event_metadata} if event_metadata else by_path.get(path,{})),
                "controlType":control,"observedTriggers":0,"incrementObservations":0,
                "outcomeKeys":[],"outcomeIdentities":{},"evidenceTier":"interaction-observed",
                "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False})
            if event_metadata:target["promptMetadata"]=event_metadata
            if identity:target["pathIdentity"]=identity
            target["observedTriggers"]+=1
            if hatch_changes:
                target["incrementObservations"]+=1
                target["evidenceTier"]="temporal-state-increment-observed"
                target["outcomeKeys"]=sorted(set(target["outcomeKeys"]+
                    [change["key"] for change,_ in hatch_changes]))
                for change,state_identity in hatch_changes:
                    if state_identity:target["outcomeIdentities"][change["key"]]=state_identity
    prompt_list=[]
    for target in prompt_targets.values():
        context=" ".join(str(value or "") for value in (target["path"],
            target.get("featureCandidate"),target.get("actionCandidate"),target["label"]))
        target["outcomeSignals"]=_rank_outcomes(target["outcomeSignals"],request,context)
        target["selectedOutcome"]=target["outcomeSignals"][0] if target["outcomeSignals"] else None
        target["guiOutcomeSignals"].sort(key=lambda item:(item["path"],item["change"]))
        target["objective"]=_prompt_objective(target["path"],target.get("featureCandidate"),
            target.get("actionCandidate"),target["label"],request,target["outcomeSignals"])
        blockers=[]
        if not target["outcomeSignals"]:blockers.append("no resolvable scalar outcome change observed")
        blockers.extend(["temporal correlation does not prove causality",
            "live Roblox prompt activation and outcome remain unverified"])
        target["blockers"]=blockers
        prompt_list.append(target)
    prompt_list.sort(key=lambda item:(-item["objective"]["requestAligned"],
        -item["objective"]["score"],item["label"].lower(),item["path"]))
    prompt_ready=[item for item in prompt_list if item["trialGenerationReady"]]
    prompt_interactions={"targets":prompt_list,"trialReadyTargets":len(prompt_ready),
        "selectedTargetPath":prompt_ready[0]["path"] if prompt_ready else None,
        "automaticMovementSupported":bool(prompt_ready),
        "executionMechanism":"executor-provided fireproximityprompt; availability checked at runtime",
        "selectionPolicy":"request alignment, objective usefulness, label, path",
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False,
        "blockers":[] if prompt_ready else ["no observed prompt has a resolvable scalar outcome change"]}

    tool_list=[]
    for target in tool_targets.values():
        context=" ".join(str(value or "") for value in (target["path"],
            target.get("featureCandidate"),target.get("actionCandidate"),target["label"]))
        target["outcomeSignals"]=_rank_outcomes(target["outcomeSignals"],request,context)
        target["selectedOutcome"]=target["outcomeSignals"][0] if target["outcomeSignals"] else None
        target["guiOutcomeSignals"].sort(key=lambda item:(item["path"],item["change"]))
        target["objective"]=_prompt_objective(target["path"],target.get("featureCandidate"),
            target.get("actionCandidate"),target["label"],request,target["outcomeSignals"])
        identity=target.get("pathIdentity")
        identity_ready=(isinstance(identity,list) and identity[0]["name"]=="LocalPlayer"
            and identity[-1]["className"]=="Tool" and target["identityAmbiguous"] is False)
        metadata_snapshots=target["prerequisiteEvidence"]["metadataSnapshots"]
        metadata_ready=(len(metadata_snapshots)==1 and metadata_snapshots[0]["enabled"] is True)
        outcome_ready=bool(target["outcomeSignals"])
        target["activationContractReady"]=identity_ready and metadata_ready and outcome_ready
        target["trialGenerationReady"]=target["activationContractReady"]
        target["replayContractAvailable"]=target["activationContractReady"]
        blockers=[]
        if not identity_ready:blockers.append("no exact LocalPlayer Tool component identity was observed")
        if not metadata_snapshots:
            blockers.append("no complete Tool activation prerequisite snapshot was observed")
        elif len(metadata_snapshots)>1:
            blockers.append("Tool activation prerequisite metadata drift was observed")
        elif metadata_snapshots[0]["enabled"] is not True:
            blockers.append("Tool was not observed enabled for activation")
        if not outcome_ready:blockers.append("no resolvable scalar outcome change was observed")
        blockers.extend(["temporal correlation does not prove causality",
            "live Roblox Tool activation and outcome remain unverified"])
        target["blockers"]=blockers
        tool_list.append(target)
    tool_list.sort(key=lambda item:(-item["objective"]["requestAligned"],
        -item["objective"]["score"],item["label"].lower(),item["path"]))
    contract_ready=[item for item in tool_list if item["activationContractReady"]]
    tool_interactions={"targets":tool_list,
        "activationContractReadyTargets":len(contract_ready),
        "selectedTargetPath":contract_ready[0]["path"] if contract_ready else None,
        "executionMechanism":"official Tool:Activate() after bounded equip",
        "generatorIntegrated":True,"generationReadyTargets":len(contract_ready),
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False,
        "blockers":[] if contract_ready else
            ["no observed Tool has identity, prerequisites, and a resolvable scalar outcome"]}

    gui_list=[]
    required_gui_metadata={"controlClass","text","visible","active","selectable",
        "autoButtonColor","ancestorVisible","screenEnabled","withinScrollingBounds",
        "effectiveVisible"}
    for target in gui_targets.values():
        context=" ".join(str(value or "") for value in (target["path"],
            target.get("featureCandidate"),target.get("actionCandidate"),target["label"]))
        target["outcomeSignals"]=_rank_outcomes(target["outcomeSignals"],request,context)
        target["selectedOutcome"]=target["outcomeSignals"][0] if target["outcomeSignals"] else None
        target["guiOutcomeSignals"].sort(key=lambda item:(item["path"],item["change"]))
        target["objective"]=_prompt_objective(target["path"],target.get("featureCandidate"),
            target.get("actionCandidate"),target["label"],request,target["outcomeSignals"])
        identity=target.get("pathIdentity")
        identity_ready=(isinstance(identity,list) and identity[0]["name"]=="PlayerGui"
            and identity[0]["className"]=="PlayerGui"
            and identity[-1]["className"] in ("TextButton","ImageButton")
            and target["identityAmbiguous"] is False)
        metadata_snapshots=target["prerequisiteEvidence"]["metadataSnapshots"]
        complete_snapshots=[snapshot for snapshot in metadata_snapshots
            if required_gui_metadata.issubset(snapshot)]
        text_drift_only=False
        if len(complete_snapshots)>1:
            base={key:complete_snapshots[0].get(key) for key in
                required_gui_metadata|{"interactable"} if key!="text"}
            text_drift_only=all({key:snapshot.get(key) for key in
                required_gui_metadata|{"interactable"} if key!="text"}==base
                for snapshot in complete_snapshots[1:])
        selected_snapshot=complete_snapshots[0] if complete_snapshots else None
        if selected_snapshot is not None:
            target["guiMetadata"]=copy.deepcopy(selected_snapshot)
        target["guiMetadataTextDynamic"]=bool(text_drift_only and len(complete_snapshots)>1)
        metadata_complete=bool(selected_snapshot)
        metadata_available=(metadata_complete
            and all(selected_snapshot[key] is True for key in
                ("visible","active","ancestorVisible","screenEnabled",
                    "withinScrollingBounds","effectiveVisible"))
            and selected_snapshot.get("interactable") is not False)
        drift_problematic=(len(metadata_snapshots)>1 and not target["guiMetadataTextDynamic"])
        outcome_ready=bool(target["outcomeSignals"])
        gui_only_outcome=(not outcome_ready and bool(target["guiOutcomeSignals"]))
        target["observableOutcomeEvidenceKind"]=("resolvable-scalar" if outcome_ready
            else "gui-transition-only" if gui_only_outcome else "none")
        target["reviewOnlyTemporalOutcomeCandidate"]=gui_only_outcome
        target["guidedActivationContractReady"]=(identity_ready and metadata_available
            and outcome_ready and not drift_problematic)
        target["trialGenerationReady"]=target["guidedActivationContractReady"]
        target["replayContractAvailable"]=False
        blockers=[]
        if not identity_ready:blockers.append("no exact unambiguous PlayerGui component identity was observed")
        if not metadata_snapshots:
            blockers.append("no GUI activation prerequisite snapshot was observed")
        elif len(complete_snapshots)!=len(metadata_snapshots):
            blockers.append("GUI activation prerequisite snapshot lacks hierarchy or availability fields")
        elif drift_problematic:
            blockers.append("GUI activation prerequisite metadata drift was observed")
        elif not metadata_available:
            blockers.append("GUI control was not observed visible, enabled, and within scrolling bounds")
        if not outcome_ready:
            if gui_only_outcome:
                blockers.append("only GUI transition outcome evidence was observed; no resolvable scalar outcome change was observed")
            else:
                blockers.append("no resolvable scalar outcome change was observed")
        blockers.extend(["GuiButton exposes an Activated event but no public automatic Activate method",
            "generated trial requires the user to activate the highlighted game control",
            "temporal correlation does not prove causality",
            "live Roblox GUI activation and outcome remain unverified"])
        target["blockers"]=blockers
        gui_list.append(target)
    gui_list.sort(key=lambda item:(-item["objective"]["requestAligned"],
        -item["objective"]["score"],item["label"].lower(),item["path"]))
    guided_ready=[item for item in gui_list if item["guidedActivationContractReady"]]
    review_only=[item for item in gui_list if item.get("reviewOnlyTemporalOutcomeCandidate")]
    gui_interactions={"targets":gui_list,"guidedTrialReadyTargets":len(guided_ready),
        "selectedTargetPath":guided_ready[0]["path"] if guided_ready else None,
        "executionMechanism":"guided exact-control highlighting plus official Activated observation; user activation required",
        "automaticActivationSupported":False,"generatorIntegrated":True,
        "generationReadyTargets":len(guided_ready),
        "reviewOnlyTemporalOutcomeCandidates":len(review_only),
        "reviewOnlyTargetPaths":[item["path"] for item in review_only][:20],
        "causalityProven":False,"runtimeVerified":False,
        "gameplayVerified":False,"blockers":[] if guided_ready else
            (["no observed GUI control has a resolvable scalar outcome; review-only GUI transition outcome candidates were observed"]
                if review_only else
                ["no observed GUI control has stable identity, availability prerequisites, and a resolvable scalar outcome"])}



    for path,item in by_path.items():
        lower=path.lower()
        if item.get("class")=="ProximityPrompt" and ("egg" in lower or "hatch" in lower):
            target=egg_targets.setdefault(path,{"path":path,"label":_label(path,item),
                "controlType":"ProximityPrompt","observedTriggers":0,"incrementObservations":0,
                "outcomeKeys":[],"outcomeIdentities":{},"evidenceTier":"object-discovered",
                "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False})
            interaction=item.get("interaction")
            if isinstance(interaction,dict):target["promptMetadata"]=interaction
    mode_controls=[];mode_paths=set()
    def add_mode(path,text,observed):
        haystack=(path+" "+text).lower()
        if path in mode_paths or not (("egg" in haystack or "hatch" in haystack)
                and ("auto" in haystack or "multi" in haystack)):return
        mode_paths.add(path)
        mode_controls.append({"path":path,"text":text[:100],
            "mode":"multi" if "multi" in haystack else "auto",
            "observedActivation":observed,"executable":False,
            "reason":"GUI presence/activation does not establish a permitted replay operation"})
    for path,item in by_path.items():
        if item.get("class") not in ("TextButton","ImageButton"):continue
        control=item.get("guiControl") if isinstance(item.get("guiControl"),dict) else {}
        text=control.get("text") if isinstance(control.get("text"),str) else ""
        add_mode(path,text,any(event.get("path")==path for event in history))
    for event in history:
        if event.get("controlType")!="GuiButton.Activated" or not isinstance(event.get("path"),str):continue
        metadata=event.get("controlMetadata") if isinstance(event.get("controlMetadata"),dict) else {}
        text=metadata.get("text") if isinstance(metadata.get("text"),str) else ""
        add_mode(event["path"],text,True)
    mode_controls.sort(key=lambda item:(item["mode"],item["path"]))
    targets=sorted(egg_targets.values(),key=lambda item:(item["label"].lower(),item["path"]))
    correlated=[item for item in targets if item["incrementObservations"]>0]
    multi_targets=[item for item in correlated if any(token in
        (item["label"]+" "+json.dumps(item.get("promptMetadata",{}))).lower()
        for token in ("multi","triple","x3","3 egg","three"))]
    blockers=[]
    if not correlated:blockers.append("no egg prompt has a temporally observed hatch/egg counter increment")
    if not mode_controls:blockers.append("no Auto/Multi egg GUI control metadata discovered")
    if not multi_targets:blockers.append("no distinct multi-hatch prompt has an observed counter increment")
    egg={"targets":targets,"correlatedTargets":len(correlated),"modeControls":mode_controls,
        "automaticSingleTrialReady":bool(correlated),"multiHatchTrialReady":bool(multi_targets),
        "autoGameModeExecutable":False,"multiGameModeExecutable":False,
        "teleportTargetDerivable":bool(correlated),"blockers":blockers,
        "modeExecutionBlockers":{
            "auto":["observed Auto GUI activation has no validated client replay primitive",
                "no observable Auto-enabled state transition was captured",
                "no unattended hatch outcome was observed after Auto activation"],
            "multi":["no distinct multi-hatch ProximityPrompt has a resolved outcome identity",
                "observed Multi/Auto GUI controls have no validated client replay primitive",
                "no single activation produced an observed hatch-count delta greater than one"]},
        "minimumLiveObservations":{
            "auto":["activate the Auto control once while the inspector records its component identity",
                "capture a persistent observable Auto-enabled value/attribute before and after activation",
                "observe a later hatch-counter increment with no manual prompt activation",
                "identify and validate a permitted client-side replay primitive for that exact control"],
            "multi":["perform one multi-hatch activation while recording the exact prompt/control identity",
                "capture hatch counter and relevant cost/currency values before and after activation",
                "observe a hatch-count delta greater than one in the linked observation window",
                "if GUI-controlled, identify and validate a permitted client-side replay primitive"]},
        "executionMechanism":"executor-provided fireproximityprompt; availability checked at runtime",
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False}
    family_for={"ProximityPrompt":"world-interaction","ClickDetector":"world-interaction",
        "TextButton":"gui-control","ImageButton":"gui-control","Tool":"tool-action"}
    families={name:{"discovered":0,"observed":0,"observedWithTemporalOutcomeCandidate":0,
        "examples":[]} for name in ("world-interaction","gui-control","tool-action")}
    observed_paths={item["path"] for item in observed_actions}
    outcome_candidate_paths={item["path"] for item in observed_actions
        if item["observableOutcomeCandidate"]}
    combat_candidates=[]
    combat_terms=("weapon","gun","ammo","reload","shoot","rifle","pistol","sniper")
    for path,item in sorted(by_path.items()):
        family=family_for.get(item.get("class"))
        if not family:continue
        summary=families[family];summary["discovered"]+=1
        if path in observed_paths:summary["observed"]+=1
        if path in outcome_candidate_paths:summary["observedWithTemporalOutcomeCandidate"]+=1
        if len(summary["examples"])<50:
            summary["examples"].append({"path":path,"class":item["class"],
                "evidenceTier":"interaction-observed" if path in observed_paths else "object-discovered"})
        if len(combat_candidates)<100 and any(term in path.lower() for term in combat_terms):
            combat_candidates.append({"path":path,"class":item["class"],
                "evidenceTier":"interaction-observed" if path in observed_paths else "name-based-candidate-only",
                "replayContractAvailable":False})
    state_signal_keys=sorted({signal["key"] for item in observed_actions
        for signal in item["stateOutcomeSignals"]})
    relationships=[{"path":item["path"],"controlType":item["controlType"],
        "featureCandidate":item["featureCandidate"],"actionCandidate":item["actionCandidate"],
        "evidenceTier":item["evidenceTier"],"stateSignals":item["stateOutcomeSignals"],
        "guiSignals":item["guiOutcomeSignals"],"temporalCorrelationOnly":True,
        "causalityProven":False,"replayContractAvailable":False}
        for item in observed_actions if item["observableOutcomeCandidate"]]
    relationships.sort(key=lambda item:(item["path"],item["controlType"],
        json.dumps(item["stateSignals"],sort_keys=True,ensure_ascii=False),
        json.dumps(item["guiSignals"],sort_keys=True,ensure_ascii=False)))
    candidate_count=len(relationships)
    generic={"families":families,"stateSignalKeys":state_signal_keys[:500],
        "stateSignalKeysTruncated":len(state_signal_keys)>500,"combatCandidates":combat_candidates,
        "temporalActionOutcomeCandidates":relationships[:500],
        "temporalActionOutcomeCandidatesTruncated":candidate_count>500,
        "generationReadiness":{"temporalCandidateCount":candidate_count,
            "replayContractCount":0,"generationReadyCount":0,
            "blockers":["temporal correlation does not establish causality",
                "no generic replay contract has been validated"] if candidate_count else
                ["no temporal action/outcome candidates observed"]},
        "note":"Action surfaces are composable candidates; names and temporal changes do not establish semantics or replay permission."}

    return {"schemaVersion":SCHEMA,"placeId":integrity["placeId"],
        "scanId":integrity.get("scanId"),"actionableObjectCounts":dict(sorted(class_counts.items())),
        "actionableObjectsTruncated":plan.get("actionableObjectsTruncated") is True,
        "observedActions":observed_actions,"genericCapabilities":generic,
        "promptInteractions":prompt_interactions,"toolInteractions":tool_interactions,
        "guiInteractions":gui_interactions,"eggHatching":egg,
        "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"runtimeVerified":False,
            "gameplayVerified":False,"actionOutcomesVerified":False}}
