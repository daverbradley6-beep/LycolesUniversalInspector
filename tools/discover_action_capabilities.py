#!/usr/bin/env python3
"""Discover evidence-bounded executable client action candidates from a compiled scan."""
import json
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
    observed_actions=[];egg_targets={}
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
        gui_signals=[{"path":change["path"],"change":change.get("transition") or
            ("visibility-changed" if change.get("beforeVisible")!=change.get("afterVisible")
                else "active-changed")} for change in gui_changes]
        tier=_evidence_tier(state_signals,gui_signals)
        observed_actions.append({"path":path,"pathIdentity":identity,"controlType":control,
            "featureCandidate":event.get("featureCandidate"),
            "actionCandidate":(event.get("workflow") or {}).get("action")
                if isinstance(event.get("workflow"),dict) else None,
            "evidenceTier":tier,"observableOutcomeCandidate":bool(state_signals or gui_signals),
            "stateChanges":changes,"stateOutcomeSignals":state_signals,
            "guiOutcomeSignals":gui_signals,"replayContractAvailable":False,
            "causalityProven":False,"outcomeVerified":False})
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
        "teleportTargetDerivable":bool(correlated),"blockers":blockers,
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
        "observedActions":observed_actions,"genericCapabilities":generic,"eggHatching":egg,
        "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"runtimeVerified":False,
            "gameplayVerified":False,"actionOutcomesVerified":False}}
