#!/usr/bin/env python3
"""Build a universal, evidence-bounded gameplay intelligence model from a capability plan.

The model remains read-only and explicitly non-causal. It summarizes world entities,
interactions, economy/progression signals, action context, and reusable workflow
candidates without assuming any game-specific mechanic taxonomy.
"""
import argparse
import hashlib
import json
import pathlib
import re
import sys

SCHEMA_VERSION="111.universal-gameplay-intelligence.1"
MAX_EVENTS=2000
MAX_CHANGES=32
MAX_INTERACTABLES=500
MAX_REGIONS=120
MAX_SIGNALS=600
MAX_ACTION_RECORDS=800
MAX_WORKFLOWS=120



def _safe_text(value,limit=400):
    return isinstance(value,str) and 0<len(value)<=limit and all(ord(char)>=32 for char in value)



def _safe_scalar(value):
    return type(value) in (int,float,str,bool) and len(str(value))<=160



def _number(value):
    return value if type(value) in (int,float) and type(value) is not bool else None



def _tokens(value):
    if not isinstance(value,str):
        return set()
    values={item.casefold() for item in re.findall(r"[^\W_]+",value,flags=re.UNICODE)}
    values.update(item[:-3] for item in list(values) if len(item)>5 and item.endswith("ing"))
    return values



def _changes(event):
    values=[]
    raw=event.get("stateChanges")
    if isinstance(raw,list):
        values.extend(raw)
    windows=event.get("observationWindows")
    if isinstance(windows,list):
        for window in windows:
            if isinstance(window,dict) and isinstance(window.get("stateChanges"),list):
                values.extend(window["stateChanges"])
    result=[]
    seen=set()
    for item in values:
        if not isinstance(item,dict):
            continue
        key=item.get("key") or item.get("path")
        before,after=item.get("before"),item.get("after")
        if not (_safe_text(key,220) and _safe_scalar(before) and _safe_scalar(after)):
            continue
        identity=(key,type(before).__name__,str(before),type(after).__name__,str(after))
        if identity in seen:
            continue
        seen.add(identity)
        result.append({"key":key,"before":before,"after":after,
            "stateIdentity":item.get("stateIdentity") if isinstance(item.get("stateIdentity"),list) else None,
            "stateIdentityStatus":item.get("stateIdentityStatus") if _safe_text(item.get("stateIdentityStatus"),60) else None})
        if len(result)>=MAX_CHANGES:
            break
    return result



def _action(event):
    workflow=event.get("workflow")
    value=workflow.get("action") if isinstance(workflow,dict) else None
    if _safe_text(value,80):
        return value.casefold()
    value=event.get("actionKind")
    return value.casefold() if _safe_text(value,80) else None



def _action_source(control_type,metadata):
    control=control_type.casefold() if _safe_text(control_type,120) else ""
    source=str(metadata.get("source","")).casefold() if isinstance(metadata,dict) else ""
    if control.startswith("inputbegan") or control.startswith("inputchanged") or "userinputservice" in source:
        return "user-input"
    if control.startswith("tool."):
        return "tool"
    if control.startswith("humanoid."):
        return "humanoid"
    if control.startswith("proximityprompt"):
        return "proximity-prompt"
    if control.startswith("guibutton"):
        return "gui-button"
    if control.startswith("clickdetector"):
        return "click-detector"
    return "interaction-control"



def _bounded_metadata(metadata):
    if not isinstance(metadata,dict):
        return None
    result={}
    for key in ("source","inputType","keyCode","userInputState","stage"):
        value=metadata.get(key)
        if _safe_text(value,120):
            result[key]=value
    for key in ("equippedToolCount",):
        value=metadata.get(key)
        if type(value) is int and 0<=value<=64:
            result[key]=value
    if metadata.get("combatToolContext") is True:
        result["combatToolContext"]=True
    return result or None



def _validate_plan(plan):
    if not isinstance(plan,dict):
        raise ValueError("plan must be an object")
    integrity=plan.get("integrity")
    if (not isinstance(integrity,dict) or integrity.get("scanComplete") is not True
            or type(integrity.get("placeId")) is not int or integrity["placeId"]<=0
            or not _safe_text(integrity.get("scanId"),120)):
        raise ValueError("complete validated scan required")
    history=plan.get("observedInteractionHistory",[])
    if not isinstance(history,list) or len(history)>MAX_EVENTS:
        raise ValueError("invalid interaction history")
    for event in history:
        if not isinstance(event,dict):
            raise ValueError("malformed interaction history event")
        if event.get("outcomeVerified") is True:
            raise ValueError("passive event claims verified outcome")
    discovery=plan.get("universalDiscovery")
    if discovery is not None and not isinstance(discovery,dict):
        raise ValueError("malformed universal discovery")
    return integrity,history,discovery if isinstance(discovery,dict) else {}



def _world(discovery,history):
    regions=[]
    for item in (discovery.get("regions") or [])[:MAX_REGIONS]:
        if not isinstance(item,dict) or not _safe_text(item.get("id"),120) or not _safe_text(item.get("path"),400):
            continue
        centroid=item.get("centroid") if isinstance(item.get("centroid"),dict) else None
        if centroid and not all(type(centroid.get(axis)) in (int,float) for axis in ("x","y","z")):
            centroid=None
        regions.append({"id":item["id"],"path":item["path"],
            "positionedObjectCount":item.get("positionedObjectCount",0),
            "totalObjectCount":item.get("totalObjectCount",0),
            "centroid":centroid,
            "bounds":item.get("bounds") if isinstance(item.get("bounds"),dict) else None,
            "runtimeVerified":False,"gameplayVerified":False})

    interactables=[]
    for item in (discovery.get("interactables") or [])[:MAX_INTERACTABLES]:
        if (not isinstance(item,dict) or not _safe_text(item.get("id"),120)
                or not _safe_text(item.get("path"),400) or not _safe_text(item.get("mechanism"),80)):
            continue
        interactables.append({"id":item["id"],"path":item["path"],
            "class":item.get("class") if _safe_text(item.get("class"),80) else None,
            "scope":item.get("scope") if _safe_text(item.get("scope"),40) else None,
            "mechanism":item["mechanism"],
            "position":item.get("position") if isinstance(item.get("position"),dict) else None,
            "positionSource":item.get("positionSource") if _safe_text(item.get("positionSource"),80) else None,
            "actionText":item.get("actionText") if _safe_text(item.get("actionText"),120) else None,
            "objectText":item.get("objectText") if _safe_text(item.get("objectText"),120) else None,
            "observedInteractions":item.get("observedInteractions",0),
            "relatedFeatures":item.get("relatedFeatures") if isinstance(item.get("relatedFeatures"),list) else [],
            "confidence":item.get("confidence") if _safe_text(item.get("confidence"),80) else "structural-only",
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})

    if not interactables:
        seen=set()
        for event in history:
            path=event.get("path")
            if not _safe_text(path,400) or path in seen:
                continue
            seen.add(path)
            control=event.get("controlType") if _safe_text(event.get("controlType"),120) else "Unknown"
            interactables.append({"id":"interactable_"+hashlib.sha256(path.encode("utf-8")).hexdigest()[:16],
                "path":path,"class":control.split(".",1)[0],"scope":path.split(".",1)[0].lower(),
                "mechanism":control.casefold(),"position":None,"positionSource":"unavailable",
                "actionText":None,"objectText":None,"observedInteractions":1,
                "relatedFeatures":[event["featureCandidate"]] if _safe_text(event.get("featureCandidate"),120) else [],
                "confidence":"observation-only","runtimeVerified":False,
                "gameplayVerified":False,"causalityProven":False})
            if len(interactables)>=MAX_INTERACTABLES:
                break

    patterns=[]
    for item in discovery.get("interactionPatterns") or []:
        if (not isinstance(item,dict) or not _safe_text(item.get("id"),120)
                or not _safe_text(item.get("key"),120)):
            continue
        patterns.append({"id":item["id"],"key":item["key"],
            "mechanism":item.get("mechanism") if _safe_text(item.get("mechanism"),80) else None,
            "scope":item.get("scope") if _safe_text(item.get("scope"),40) else None,
            "memberCount":item.get("memberCount",0),
            "observedInteractions":item.get("observedInteractions",0),
            "samplePaths":item.get("samplePaths") if isinstance(item.get("samplePaths"),list) else [],
            "runtimeVerified":False,"gameplayVerified":False})

    return {"regions":regions,"interactables":interactables,"interactionPatterns":patterns,
        "summary":{"regions":len(regions),"interactables":len(interactables),
            "positionedInteractables":sum(1 for item in interactables if isinstance(item.get("position"),dict)),
            "observedInteractables":sum(1 for item in interactables if item.get("observedInteractions",0)>0),
            "interactionPatterns":len(patterns)}}



def _action_records(history):
    records=[]
    for event in history[:MAX_ACTION_RECORDS]:
        path=event.get("path")
        if not _safe_text(path,400):
            continue
        workflow=event.get("workflow") if isinstance(event.get("workflow"),dict) else {}
        metadata=_bounded_metadata(event.get("controlMetadata"))
        control_type=event.get("controlType") if _safe_text(event.get("controlType"),120) else None
        changes=_changes(event)
        windows=[]
        for window in (event.get("observationWindows") or []):
            if not isinstance(window,dict):
                continue
            windows.append({"seconds":window.get("seconds") if type(window.get("seconds")) in (int,float) else None,
                "stateChangeCount":window.get("stateChangeCount") if type(window.get("stateChangeCount")) is int else 0,
                "guiChangeCount":window.get("guiChangeCount") if type(window.get("guiChangeCount")) is int else 0,
                "travelDistanceStuds":window.get("travelDistanceStuds") if type(window.get("travelDistanceStuds")) in (int,float) else None,
                "clientStateCorroborated":(window.get("actionEvidence") or {}).get("clientStateCorroborated") is True})
        gui_changes=[item for item in (event.get("guiStateChanges") or []) if isinstance(item,dict)][:MAX_CHANGES]
        records.append({"id":"action_record_"+hashlib.sha256(
                (str(event.get("sequence"))+"\n"+path+"\n"+str(event.get("observedAt"))).encode("utf-8")
            ).hexdigest()[:16],
            "sequence":event.get("sequence") if type(event.get("sequence")) is int else None,
            "sessionId":event.get("sessionId") if _safe_text(event.get("sessionId"),80) else None,
            "sessionElapsedSeconds":event.get("sessionElapsedSeconds") if type(event.get("sessionElapsedSeconds")) in (int,float) else None,
            "transactionId":str(event.get("transactionId")) if type(event.get("transactionId")) in (int,str) else None,
            "before":{"baselineSource":event.get("baselineSource") if _safe_text(event.get("baselineSource"),80) else None,
                "baselineTiming":event.get("baselineTiming") if _safe_text(event.get("baselineTiming"),80) else None,
                "preActivationBaselineAvailable":event.get("preActivationBaselineAvailable") is True,
                "baselineAgeSeconds":event.get("baselineAgeSeconds") if type(event.get("baselineAgeSeconds")) in (int,float) else None,
                "guiContext":event.get("guiContext") if isinstance(event.get("guiContext"),dict) else None},
            "during":{"path":path,
                "controlType":control_type,
                "actionSource":_action_source(control_type,metadata),
                "featureCandidate":event.get("featureCandidate") if _safe_text(event.get("featureCandidate"),120) else None,
                "actionCandidate":_action(event),
                "workflowPhase":workflow.get("phase") if _safe_text(workflow.get("phase"),80) else None,
                "workflowConfidence":workflow.get("confidence") if _safe_text(workflow.get("confidence"),80) else None,
                "controlMetadata":metadata},
            "after":{"stateChanges":changes,"stateChangeCount":len(changes),
                "guiStateChanges":gui_changes,"guiStateChangeCount":len(gui_changes),
                "observationWindows":windows,
                "unchangedObservationWindows":sum(1 for window in windows
                    if window["stateChangeCount"]==0 and window["guiChangeCount"]==0)},
            "outcomeVerified":False,"causalityProven":False,
            "runtimeVerified":False,"gameplayVerified":False})
    return records



def _economy(discovery,records):
    signals=[]
    for item in (discovery.get("economySignals") or [])[:MAX_SIGNALS]:
        if (not isinstance(item,dict) or not _safe_text(item.get("id"),120)
                or not _safe_text(item.get("path"),400) or not _safe_text(item.get("key"),120)):
            continue
        signals.append({"id":item["id"],"path":item["path"],"key":item["key"],
            "value":item.get("value"),"source":item.get("source") if _safe_text(item.get("source"),80) else None,
            "scope":item.get("scope") if _safe_text(item.get("scope"),40) else None,
            "classification":item.get("classification") if _safe_text(item.get("classification"),80) else "unclassified",
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})

    state_signals={} 
    for item in (discovery.get("stateChangeSignals") or [])[:MAX_SIGNALS]:
        if not isinstance(item,dict) or not _safe_text(item.get("id"),120) or not _safe_text(item.get("key"),220):
            continue
        state_signals[item["key"]]={"id":item["id"],"key":item["key"],
            "classification":item.get("classification") if _safe_text(item.get("classification"),80) else "state_transition_signal",
            "increaseEvents":item.get("increaseEvents",0),"decreaseEvents":item.get("decreaseEvents",0),
            "changedEvents":item.get("changedEvents",0),"lastBefore":item.get("lastBefore"),
            "lastAfter":item.get("lastAfter"),
            "sourceFeatures":item.get("sourceFeatures") if isinstance(item.get("sourceFeatures"),list) else [],
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False}

    for record in records:
        feature=record["during"]["featureCandidate"]
        for change in record["after"]["stateChanges"]:
            key=change["key"]
            signal=state_signals.setdefault(key,{"id":"state_"+hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
                "key":key,"classification":"state_transition_signal",
                "increaseEvents":0,"decreaseEvents":0,"changedEvents":0,
                "lastBefore":change["before"],"lastAfter":change["after"],
                "sourceFeatures":[],"runtimeVerified":False,
                "gameplayVerified":False,"causalityProven":False})
            signal["changedEvents"]+=1
            signal["lastBefore"]=change["before"];signal["lastAfter"]=change["after"]
            before,after=_number(change["before"]),_number(change["after"])
            if before is not None and after is not None:
                if after>before:signal["increaseEvents"]+=1
                elif after<before:signal["decreaseEvents"]+=1
            if feature and feature not in signal["sourceFeatures"]:
                signal["sourceFeatures"].append(feature)

    state_signal_items=sorted(state_signals.values(),key=lambda item:(-item["changedEvents"],item["key"]))[:MAX_SIGNALS]

    balances={}
    for signal in state_signal_items:
        amount=_number(signal["lastAfter"])
        if amount is not None:
            balances[signal["key"]]=amount

    affordability=[]
    for signal in signals:
        if signal["classification"]!="requirement_or_cost_signal":
            continue
        cost=_number(signal["value"])
        signal_tokens=_tokens(signal["path"]+" "+signal["key"])
        best_balance_key=None
        best_balance_value=None
        for key,value in balances.items():
            if _tokens(key)&signal_tokens:
                best_balance_key=key
                best_balance_value=value
                break
        affordability.append({"costSignalId":signal["id"],"estimatedCost":cost,
            "balanceSourceKey":best_balance_key,"estimatedBalance":best_balance_value,
            "estimatedShortfall":(cost-best_balance_value if cost is not None and best_balance_value is not None and cost>best_balance_value
                else 0 if cost is not None and best_balance_value is not None else None),
            "status":"balance-estimated" if cost is not None and best_balance_value is not None else "balance-unavailable",
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})

    return {"signals":signals,"stateSignals":state_signal_items,
        "affordability":affordability,
        "summary":{"signals":len(signals),"stateSignals":len(state_signal_items),
            "affordability":len(affordability)}}



def _workflows(records):
    grouped={}
    for record in records:
        key=record["transactionId"] or f"singleton-{record.get('sequence')}"
        grouped.setdefault(key,[]).append(record)

    values=[]
    seen=set()

    def add(source,steps):
        if len(steps)<2:
            return
        sequences=tuple(step.get("sequence") for step in steps)
        if sequences in seen:
            return
        seen.add(sequences)
        decreases=[];increases=[]
        for step in steps:
            for change in step["after"]["stateChanges"]:
                before,after=_number(change["before"]),_number(change["after"])
                if before is None or after is None or before==after:
                    continue
                target=increases if after>before else decreases
                if change["key"] not in target:
                    target.append(change["key"])
        actions=[step["during"]["actionCandidate"] for step in steps if step["during"]["actionCandidate"]]
        values.append({"id":"workflow_"+hashlib.sha256(
                (source+"\n"+"|".join(str(seq) for seq in sequences)).encode("utf-8")
            ).hexdigest()[:16],
            "source":source,
            "objective":" -> ".join(actions[:3]) if actions else "multi-step observed interaction sequence",
            "stepCount":len(steps),
            "steps":[{"sequence":step.get("sequence"),"path":step["during"]["path"],
                "controlType":step["during"]["controlType"],
                "featureCandidate":step["during"]["featureCandidate"],
                "actionCandidate":step["during"]["actionCandidate"],
                "stateChanges":step["after"]["stateChanges"],
                "guiStateChangeCount":step["after"]["guiStateChangeCount"]}
                for step in steps],
            "prerequisiteStateSignals":sorted(decreases),
            "resultStateSignals":sorted(increases),
            "status":"candidate_with_observed_transitions" if increases or decreases
                else "interaction_sequence_without_state_transition",
            "repeatable":False,"causalityProven":False,
            "runtimeVerified":False,"gameplayVerified":False})

    for key in sorted(grouped):
        steps=sorted(grouped[key],key=lambda step:(step.get("sequence") or 0,step["during"]["path"]))
        add("shared-transaction" if key and not key.startswith("singleton-") else "singletons",steps)

    timed=[record for record in records if record.get("sessionId") and type(record.get("sessionElapsedSeconds")) in (int,float)]
    timed.sort(key=lambda step:(step["sessionId"],step["sessionElapsedSeconds"],step.get("sequence") or 0))
    if timed:
        chain=[timed[0]]
        for item in timed[1:]:
            prev=chain[-1]
            gap=item["sessionElapsedSeconds"]-prev["sessionElapsedSeconds"]
            if item["sessionId"]==prev["sessionId"] and 0<=gap<=8:
                chain.append(item)
            else:
                add("temporal-adjacency",chain)
                chain=[item]
        add("temporal-adjacency",chain)

    values.sort(key=lambda item:(-item["stepCount"],item["id"]))
    return values[:MAX_WORKFLOWS]



def _relationships(records,workflows,economy):
    edges=[]
    for record in records:
        feature=record["during"]["featureCandidate"]
        action=record["during"]["actionCandidate"]
        if feature and action:
            edges.append({"id":"rel_"+hashlib.sha256(
                    (record["id"]+"\n"+feature+"\n"+action).encode("utf-8")
                ).hexdigest()[:16],
                "sourceType":"action_record","sourceId":record["id"],
                "targetType":"feature_candidate","targetId":feature,
                "relationship":"action_observed_under_feature",
                "causalityProven":False})
    for workflow in workflows:
        for key in workflow["resultStateSignals"]:
            edges.append({"id":"rel_"+hashlib.sha256((workflow["id"]+"\n"+key).encode("utf-8")).hexdigest()[:16],
                "sourceType":"workflow_candidate","sourceId":workflow["id"],
                "targetType":"state_signal","targetId":key,
                "relationship":"temporally_followed_by_state_change",
                "causalityProven":False})
    for item in economy["affordability"]:
        if item["balanceSourceKey"] is None:
            continue
        edges.append({"id":"rel_"+hashlib.sha256(
                (item["costSignalId"]+"\n"+item["balanceSourceKey"]).encode("utf-8")
            ).hexdigest()[:16],
            "sourceType":"cost_signal","sourceId":item["costSignalId"],
            "targetType":"state_signal","targetId":item["balanceSourceKey"],
            "relationship":"affordability_estimate_candidate",
            "causalityProven":False})
    return edges



def analyze(plan):
    integrity,history,discovery=_validate_plan(plan)
    world=_world(discovery,history)
    actions=_action_records(history)
    economy=_economy(discovery,actions)
    workflows=_workflows(actions)
    relationships=_relationships(actions,workflows,economy)
    source_counts={}
    input_records=0
    for item in actions:
        source=item.get("during",{}).get("actionSource") if isinstance(item.get("during"),dict) else None
        if _safe_text(source,60):
            source_counts[source]=source_counts.get(source,0)+1
            if source in {"user-input","tool","humanoid"}:
                input_records+=1
    return {"schemaVersion":SCHEMA_VERSION,
        "placeId":integrity["placeId"],"scanId":integrity["scanId"],
        "world":world,"economy":economy,"actions":actions,
        "workflows":workflows,"relationships":relationships,
        "summary":{"regions":world["summary"]["regions"],
            "interactables":world["summary"]["interactables"],
            "economySignals":economy["summary"]["signals"],
            "stateSignals":economy["summary"]["stateSignals"],
            "actionRecords":len(actions),"inputActionRecords":input_records,
            "actionSourceBreakdown":dict(sorted(source_counts.items())),
            "workflowCandidates":len(workflows),
            "relationships":len(relationships)},
        "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"runtimeVerified":False,
            "gameplayVerified":False,"actionOutcomesVerified":False},
        "limitations":["Client-visible evidence only",
            "Temporal correlations do not prove causality",
            "No server-only state or remote payload inference",
            "Workflow candidates are review-only and non-authoritative"]}



def validate(document,plan):
    expected=analyze(plan)
    if document!=expected:
        raise ValueError("universal gameplay intelligence does not match source plan")
    return document



def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan")
    parser.add_argument("--output",default="build/universal-gameplay-intelligence.json")
    args=parser.parse_args()
    try:
        raw=pathlib.Path(args.plan).read_bytes()
        if len(raw)>20_000_000:
            raise ValueError("source plan too large")
        result=analyze(json.loads(raw))
        target=pathlib.Path(args.output)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
            encoding="utf-8")
        print("Universal gameplay intelligence:",target)
        return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print("UNIVERSAL GAMEPLAY INTELLIGENCE BLOCKED:",exc,file=sys.stderr)
        return 2


if __name__=="__main__":
    sys.exit(main())
