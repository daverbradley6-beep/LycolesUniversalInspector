#!/usr/bin/env python3
"""Merge independently verified dynamic observation plans with a full baseline.

This is an evidence overlay, not object reconstruction or gameplay execution.
"""
import copy
import json
import math
import re


_UNVERIFIED_PROVENANCE=("resumeCheckpointAuthenticated","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","sourceAuthenticityVerified","causalityProven",
    "serverAuthorityVerified","replayable","gameplayVerified","actionOutcomesVerified")


def _valid_local_digests(provenance):
    if provenance.get("schemaVersion")=="30.2.source-provenance.1":
        return True
    count=provenance.get("partCount")
    entries=provenance.get("partContentDigests")
    if (provenance.get("schemaVersion")!="30.2.source-provenance.2"
            or provenance.get("inputMode")!="local-multipart"
            or type(count) is not int or not 1<=count<=2000
            or provenance.get("localPartContentDigestsComputed") is not True
            or not isinstance(entries,list) or len(entries)!=count):
        return False
    indexes=set()
    for entry in entries:
        if (not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}
                or type(entry.get("partIndex")) is not int or not 1<=entry["partIndex"]<=count
                or not isinstance(entry.get("sha256"),str)
                or re.fullmatch(r"[a-f0-9]{64}",entry["sha256"]) is None
                or entry["partIndex"] in indexes):
            return False
        indexes.add(entry["partIndex"])
    return indexes==set(range(1,count+1))


def _observation_provenance(observation,integrity):
    provenance=observation.get("sourceProvenance")
    mode=provenance.get("inputMode") if isinstance(provenance,dict) else None
    receiver=mode in ("receiver-import","receiver-import-legacy-v11")
    digest_receiver=mode=="receiver-import"
    digest_verified=provenance.get("receiverStoredPayloadDigestsVerified") if provenance else None
    integrity_verified=provenance.get("receiverIntegrityVerified") if provenance else None
    acknowledgement=provenance.get("receiverAcknowledgementDigestEquivalent") if provenance else None
    revalidated=provenance.get("receiverStoredPayloadDigestsRevalidatedThisRun") if provenance else None
    if (not isinstance(provenance,dict)
            or provenance.get("schemaVersion") not in
                ("30.2.source-provenance.1","30.2.source-provenance.2")
            or not _valid_local_digests(provenance)
            or mode not in ("local-multipart","receiver-import","receiver-import-legacy-v11")
            or provenance.get("scanId")!=integrity.get("scanId")
            or provenance.get("placeId")!=integrity.get("placeId")
            or provenance.get("partCount")!=integrity.get("parts")
            or any(provenance.get(field) is not False for field in _UNVERIFIED_PROVENANCE)
            or type(digest_verified) is not bool or digest_verified is not digest_receiver
            or type(integrity_verified) is not bool or integrity_verified is not receiver
            or type(acknowledgement) is not bool or type(revalidated) is not bool
            or (mode!="receiver-import" and revalidated)
            or (not receiver and acknowledgement)):
        raise ValueError("Invalid observation source provenance")
    return copy.deepcopy(provenance)


def _event_signature(event):
    if not isinstance(event,dict):
        return None
    try:
        return json.dumps(event,sort_keys=True,separators=(",",":"),ensure_ascii=False)
    except (TypeError,ValueError):
        return None


def _interaction_events_from_observation(observation):
    diagnostics=observation.get("interactionDiagnostics")
    if isinstance(diagnostics,dict) and isinstance(diagnostics.get("recentInteractions"),list):
        return [event for event in diagnostics["recentInteractions"] if isinstance(event,dict)]
    history=observation.get("observedInteractionHistory")
    if isinstance(history,list):
        return [event for event in history if isinstance(event,dict)]
    return []


def _non_negative_int(value,default=0):
    return value if type(value) is int and value>=0 else default


_BASELINE_FIELDS=("baselineSource","baselineTiming","baselineAgeSeconds","preActivationBaselineAvailable")
_BASELINE_SOURCES={"GuiButton.InputBegan","ProximityPrompt.PromptButtonHoldBegan",
    "Tool.Equipped","activation-callback-fallback"}


def _normalize_event_baseline_timing(event):
    if not isinstance(event,dict):
        return event

    if event.get("transactionLinkSource")=="explicit-user-armed-recording":
        event.pop("transactionLinkSource",None)
    event.pop("explicitWorkflowRecording",None)
    transaction=event.get("transactionId")
    if isinstance(transaction,str) and transaction.startswith("user-recorded-"):
        suffix=transaction[len("user-recorded-"):] or "recording"
        event["transactionId"]=("overlay-recorded-"+suffix)[:80]

    if not any(field in event for field in _BASELINE_FIELDS):
        return event
    source=event.get("baselineSource")
    if source not in _BASELINE_SOURCES:
        for field in _BASELINE_FIELDS:
            event.pop(field,None)
        return event
    timing="activation-callback" if source=="activation-callback-fallback" else "pre-activation"
    event["baselineSource"]=source
    event["baselineTiming"]=timing
    event["preActivationBaselineAvailable"]=(timing=="pre-activation")
    age=event.get("baselineAgeSeconds")
    if not (type(age) in (int,float) and type(age) is not bool and math.isfinite(age) and 0<=age<=3600):
        event.pop("baselineAgeSeconds",None)
    return event


def merge_evidence(baseline, observations):
    base=baseline.get("integrity") or {}
    if base.get("scanComplete") is not True or type(base.get("placeId")) is not int:
        raise ValueError("Complete baseline required")
    if (baseline.get("sourceDiagnostics") or {}).get("scanMode")=="dynamic-observations":
        raise ValueError("Dynamic observations cannot be a baseline")
    if not isinstance(observations,list) or len(observations)>64:
        raise ValueError("Invalid observation list")
    result=copy.deepcopy(baseline)
    by_name={x["feature"]:x for x in result.get("features",[])}
    seen={base.get("scanId")}
    overlays=[]
    keys=("interactionEvents","observedEvents","verifiedClientOutcomes",
          "clientCorroboratedEvents","temporalTransitionEvents")

    history=[event for event in result.get("observedInteractionHistory",[]) if isinstance(event,dict)]
    diagnostics=result.get("interactionDiagnostics")
    if not isinstance(diagnostics,dict):
        diagnostics={}
    recent=[event for event in diagnostics.get("recentInteractions",[]) if isinstance(event,dict)]
    signatures={signature for signature in (_event_signature(event) for event in history+recent) if signature is not None}

    state_delta_total=_non_negative_int(diagnostics.get("stateDeltaEvents"))
    gui_state=diagnostics.get("guiStateObservation")
    if not isinstance(gui_state,dict):
        gui_state={}
    gui_transition_total=_non_negative_int(gui_state.get("transitionsCaptured"))
    merged_interactions=0
    skipped_interactions=0

    for obs in observations:
        integrity=obs.get("integrity") or {}
        sid=integrity.get("scanId")
        if integrity.get("scanComplete") is not True or integrity.get("placeId")!=base["placeId"]:
            raise ValueError("Observation incomplete or different game")
        if not isinstance(sid,str) or not sid or sid in seen:
            raise ValueError("Duplicate or missing scan ID")
        seen.add(sid)
        if (obs.get("sourceDiagnostics") or {}).get("scanMode")!="dynamic-observations":
            raise ValueError("Only dynamic observations may be overlaid")
        provenance=_observation_provenance(obs,integrity)
        for feature in obs.get("features",[]):
            name=feature.get("feature")
            if not isinstance(name,str) or not name:
                raise ValueError("Invalid feature")
            if name not in by_name:
                by_name[name]={"feature":name,"status":"observation-only",
                               "implementationReady":False,
                               "reason":"Observation evidence is not a reproducible action contract",
                               "evidence":None,"readiness":None,
                               **{key:0 for key in keys}}
            target=by_name[name]
            for key in keys:
                value=feature.get(key,0)
                if type(value) is not int or value<0:
                    raise ValueError("Invalid evidence count")
                old=target.get(key,0)
                if type(old) is not int or old<0: raise ValueError("Invalid baseline count")
                target[key]=old+value
            target["implementationReady"]=False

        obs_events=_interaction_events_from_observation(obs)
        merged_for_overlay=0
        skipped_for_overlay=0
        for event in obs_events:
            signature=_event_signature(event)
            if signature is None:
                continue
            if signature in signatures:
                skipped_for_overlay+=1
                continue
            signatures.add(signature)
            cloned=_normalize_event_baseline_timing(copy.deepcopy(event))
            history.append(cloned)
            recent.append(cloned)
            merged_for_overlay+=1

        obs_diag=obs.get("interactionDiagnostics")
        if isinstance(obs_diag,dict):
            inferred_state_deltas=sum(
                len(event.get("stateChanges") or [])
                for event in obs_events
                if isinstance(event.get("stateChanges"),list)
            )
            state_delta_total+=_non_negative_int(obs_diag.get("stateDeltaEvents"),inferred_state_deltas)
            overlay_gui=obs_diag.get("guiStateObservation")
            if isinstance(overlay_gui,dict):
                gui_transition_total+=_non_negative_int(overlay_gui.get("transitionsCaptured"))
        merged_interactions+=merged_for_overlay
        skipped_interactions+=skipped_for_overlay

        overlays.append({
            "scanId":sid,
            "parts":integrity.get("parts"),
            "interactionEvents":integrity.get("interactionEvents",0),
            "mergedInteractionEvents":merged_for_overlay,
            "duplicateInteractionEventsSkipped":skipped_for_overlay,
            "sourceProvenance":provenance,
        })

    if len(history)>2000:
        overflow=len(history)-2000
        history=history[-2000:]
        recent=recent[-2000:]
        skipped_interactions+=overflow

    diagnostics["recentInteractions"]=recent
    diagnostics["historyTotal"]=len(history)
    diagnostics["stateDeltaEvents"]=state_delta_total
    gui_state["transitionsCaptured"]=gui_transition_total
    diagnostics["guiStateObservation"]=gui_state
    result["interactionDiagnostics"]=diagnostics

    summary=result.get("interactionObservationSummary")
    if not isinstance(summary,dict):
        summary={}
    callbacks=_non_negative_int(summary.get("callbacksFired"),len(history))
    pre_activation=_non_negative_int(summary.get("preActivationBaselinesUsed"),callbacks)
    callback_baselines=_non_negative_int(summary.get("callbackBaselinesUsed"),0)
    if pre_activation+callback_baselines!=callbacks:
        pre_activation=callbacks
        callback_baselines=0
    windows_expected=_non_negative_int(summary.get("observationWindowsExpected"),0)
    windows_completed=_non_negative_int(summary.get("observationWindowsCompleted"),0)
    windows_failed=_non_negative_int(summary.get("observationWindowsFailed"),0)
    pending_events=_non_negative_int(summary.get("pendingObservationEvents"),0)
    if windows_completed+windows_failed+pending_events!=windows_expected:
        windows_expected=windows_completed+windows_failed+pending_events
    capture_failures=_non_negative_int(summary.get("preActivationCaptureFailures"),0)
    known_possible=bool(callback_baselines or pending_events or windows_failed)
    evidence_loss_possible=bool(known_possible or capture_failures)

    summary.update({
        "available":len(history)>0,
        "callbacksFired":callbacks,
        "preActivationBaselinesUsed":pre_activation,
        "callbackBaselinesUsed":callback_baselines,
        "pendingObservationEvents":pending_events,
        "observationWindowsExpected":windows_expected,
        "observationWindowsCompleted":windows_completed,
        "observationWindowsFailed":windows_failed,
        "preActivationCaptureFailures":capture_failures,
        "observationWindowAccountingValid":True,
        "evidenceLossPossible":evidence_loss_possible,
        "mergedOverlayInteractionEvents":merged_interactions,
        "duplicateOverlayInteractionEventsSkipped":skipped_interactions,
    })
    result["interactionObservationSummary"]=summary
    result["observedInteractionHistory"]=history

    result["features"]=sorted(by_name.values(),key=lambda x:x["feature"])
    result["featureCount"]=len(result["features"])
    result["evidenceOverlays"]=overlays
    result["releaseGate"]={"gameplayAutomationApproved":False,
      "reason":"Correlated client observations do not establish executable server action contracts"}
    return result
