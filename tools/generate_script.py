#!/usr/bin/env python3
"""Lycoles v9: deterministic, fail-closed Roblox client utility generator.

Usage:
  python3 tools/generate_script.py build/capability-plan.json --output build/generated
Only generates features backed by safe Roblox client APIs; does not synthesize
remote invocations or claim to replay server-controlled gameplay actions.
"""
import argparse
import hashlib
import importlib.util
import json
import pathlib
import re
import sys
import unicodedata

ALLOWED_FEATURES = ("gameplay_actions", "evidence_ranked_targets", "bounded_automation")


def load_local_module(name,filename):
    path=pathlib.Path(__file__).with_name(filename)
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def validate(plan):
    if not isinstance(plan,dict): raise ValueError("Plan must be an object")
    integrity=plan.get("integrity")
    if not isinstance(integrity,dict) or integrity.get("scanComplete") is not True:
        raise ValueError("A complete validated scan is required")
    place=integrity.get("placeId")
    if type(place) is not int or not 1<=place<=2**53:
        raise ValueError("Invalid place ID")
    if not isinstance(plan.get("features"),list): raise ValueError("Missing feature inventory")
    if len(plan["features"])>5000: raise ValueError("Unreasonably large feature inventory")
    for feature in plan["features"]:
        if not isinstance(feature,dict) or not isinstance(feature.get("feature"),str):
            raise ValueError("Malformed feature")
    request=plan.get("requestedCapability")
    if request is not None and (not isinstance(request,str) or not request
            or len(request.encode("utf-8"))>240 or request!=request.strip()
            or any(unicodedata.category(character)=="Cc" for character in request)):
        raise ValueError("Malformed requested capability")
    return place

def _validate_source_provenance(provenance):
    if not isinstance(provenance,dict):
        raise ValueError("Malformed source provenance")
    mode=provenance.get("inputMode")
    receiver=mode in ("receiver-import","receiver-import-legacy-v11",
                      "receiver-import-legacy-reports")
    digest_receiver=mode=="receiver-import"
    if mode not in ("local-multipart","receiver-import","receiver-import-legacy-v11",
                    "receiver-import-legacy-reports"):
        raise ValueError("Unsupported source provenance mode")
    false_claims=("resumeCheckpointAuthenticated","receiverResponseAuthenticityVerified",
                  "localPayloadEquivalent","sourceAuthenticityVerified","causalityProven",
                  "serverAuthorityVerified","replayable","gameplayVerified",
                  "actionOutcomesVerified")
    if any(provenance.get(field) is not False for field in false_claims):
        raise ValueError("Source provenance claims unsupported verification")
    schema=provenance.get("schemaVersion")
    if schema not in ("30.2.source-provenance.1","30.2.source-provenance.2"):
        raise ValueError("Unsupported source provenance schema")
    if schema=="30.2.source-provenance.2":
        part_count=provenance.get("partCount")
        digests=provenance.get("partContentDigests")
        if (mode!="local-multipart" or type(part_count) is not int or not 1<=part_count<=2000
                or provenance.get("localPartContentDigestsComputed") is not True
                or not isinstance(digests,list) or len(digests)!=part_count):
            raise ValueError("Invalid local part digest coverage")
        indexes=set()
        for entry in digests:
            if (not isinstance(entry,dict) or set(entry)!={"partIndex","sha256"}
                    or type(entry.get("partIndex")) is not int
                    or not 1<=entry["partIndex"]<=part_count
                    or not isinstance(entry.get("sha256"),str)
                    or re.fullmatch(r"[a-f0-9]{64}",entry["sha256"]) is None
                    or entry["partIndex"] in indexes):
                raise ValueError("Invalid local part digest coverage")
            indexes.add(entry["partIndex"])
        if indexes!=set(range(1,part_count+1)):
            raise ValueError("Invalid local part digest coverage")
    digest_verified=provenance.get("receiverStoredPayloadDigestsVerified")
    integrity_verified=provenance.get("receiverIntegrityVerified")
    acknowledgement_equivalent=provenance.get("receiverAcknowledgementDigestEquivalent")
    revalidated=provenance.get("receiverStoredPayloadDigestsRevalidatedThisRun")
    if (type(digest_verified) is not bool or type(integrity_verified) is not bool
            or type(acknowledgement_equivalent) is not bool or type(revalidated) is not bool
            or digest_verified is not digest_receiver or integrity_verified is not receiver
            or (mode!="receiver-import" and revalidated)
            or (not receiver and acknowledgement_equivalent)):
        raise ValueError("Inconsistent source provenance")
    return receiver,digest_verified,integrity_verified,acknowledgement_equivalent,revalidated


def source_provenance_lines(plan):
    provenance=plan.get("sourceProvenance")
    if provenance is None:
        lines=["Baseline input: local multipart","Local part digests: unavailable",
               "Receiver payload digests: unavailable","Receiver retrieval integrity: unavailable",
               "Inspector ACK digest equivalence: not established",
               "Resume checkpoint authentication: unavailable",
               "Response authenticity: unverified",
               "Original local payload equivalence: unverified",
               "Gameplay outcomes: unverified"]
    else:
        receiver,digest_verified,integrity_verified,acknowledgement_equivalent,revalidated=(
            _validate_source_provenance(provenance))
        mode=provenance["inputMode"]
        baseline=("legacy v11 receiver import" if mode=="receiver-import-legacy-v11"
                  else "legacy report-index receiver import" if mode=="receiver-import-legacy-reports"
                  else "receiver import" if receiver else "local multipart")
        if receiver:
            local_digest_line="not applicable"
        elif provenance.get("schemaVersion")=="30.2.source-provenance.2":
            local_digest_line=("computed for "+str(len(provenance["partContentDigests"]))
                               +"/"+str(provenance["partCount"])+" parts")
        else:
            local_digest_line="unavailable"
        lines=[
            "Baseline input: "+baseline,
            "Local part digests: "+local_digest_line,
            "Receiver payload digests: "+("verified" if digest_verified else "unavailable"),
            "Receiver retrieval integrity: "+("verified" if integrity_verified else "unavailable"),
            "Inspector ACK digest equivalence: "+(
                "verified" if acknowledgement_equivalent else "not established"),
            "Receiver digests rechecked this run: "+(
                "yes" if revalidated else "unavailable on legacy v11" if mode=="receiver-import-legacy-v11"
                else "unavailable on legacy report-index import" if mode=="receiver-import-legacy-reports"
                else "no (cached checkpoint used)" if receiver else "not applicable"),
            "Resume checkpoint authentication: unavailable",
            "Response authenticity: unverified",
            "Original local payload equivalence: unverified",
            "Gameplay outcomes: unverified",
        ]
    overlays=plan.get("evidenceOverlays",[])
    if not isinstance(overlays,list) or len(overlays)>64:
        raise ValueError("Malformed evidence overlays")
    receiver_overlays=0
    for overlay in overlays:
        if not isinstance(overlay,dict):
            raise ValueError("Malformed evidence overlay")
        overlay_provenance=overlay.get("sourceProvenance")
        if (_validate_source_provenance(overlay_provenance)[0]):
            receiver_overlays+=1
        if (overlay_provenance.get("schemaVersion") not in
                ("30.2.source-provenance.1","30.2.source-provenance.2")
                or overlay_provenance.get("scanId")!=overlay.get("scanId")
                or overlay_provenance.get("placeId")!=plan["integrity"]["placeId"]
                or overlay_provenance.get("partCount")!=overlay.get("parts")):
            raise ValueError("Evidence overlay provenance identity mismatch")
    lines.append("Dynamic evidence overlays: "+str(len(overlays)))
    if overlays:
        lines.append("Overlay sources: "+str(receiver_overlays)+" receiver import, "
                     +str(len(overlays)-receiver_overlays)+" local multipart; separate provenance")
    return lines


def gameplay_understanding_lines(plan,understanding):
    if understanding is None:
        return ["Gameplay understanding: unavailable","No gameplay mechanics are verified"]
    integrity=plan["integrity"]
    if not isinstance(understanding,dict):
        raise ValueError("Malformed gameplay understanding")
    claims=understanding.get("claims")
    false_claims=("sourceAuthenticityVerified","primaryObjectiveVerified","causalityProven",
                  "serverAuthorityVerified","replayable","runtimeVerified",
                  "gameplayVerified","actionOutcomesVerified")
    if (understanding.get("schemaVersion") not in {
                "110.gameplay-understanding.1","110.gameplay-understanding.2"}
            or understanding.get("placeId")!=integrity.get("placeId")
            or understanding.get("scanId")!=integrity.get("scanId")
            or understanding.get("model")!="composable_capabilities"
            or understanding.get("genre") is not None
            or not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in false_claims)):
        raise ValueError("Invalid gameplay understanding claims")
    systems=understanding.get("systems")
    objectives=understanding.get("objectiveCandidates")
    loops=understanding.get("progressionLoops")
    if (not isinstance(systems,list) or len(systems)>128
            or not isinstance(objectives,list) or len(objectives)>128
            or not isinstance(loops,list) or len(loops)>128):
        raise ValueError("Malformed gameplay understanding")
    lines=["Gameplay systems: "+str(len(systems)),
           "Objective candidates: "+str(len(objectives)),
           "Progression loops: "+str(len(loops)),
           "No gameplay mechanics are verified"]
    profile=understanding.get("profileIndex");gaps=understanding.get("evidenceGaps")
    if profile is not None or gaps is not None:
        if (not isinstance(profile,dict)
                or profile.get("schemaVersion")!="110.game-profile-index.1"
                or profile.get("model")!="provider-independent-composable-profile"
                or profile.get("singleGenreAssumed") is not False
                or type(profile.get("systemInventoryTruncated")) is not bool
                or type(profile.get("omittedSystemCandidates")) is not int
                or profile["omittedSystemCandidates"]<0
                or profile["systemInventoryTruncated"]!=(profile["omittedSystemCandidates"]>0)
                or profile.get("implementationReady") is not False
                or profile.get("runtimeVerified") is not False
                or profile.get("gameplayVerified") is not False
                or not isinstance(gaps,list) or len(gaps)>128
                or any(not isinstance(item,dict) or item.get("status")!="unresolved"
                    or item.get("implementationReady") is not False
                    or item.get("causalityProven") is not False for item in gaps)):
            raise ValueError("Malformed provider-independent game profile")
        lines.extend(["Game profile: provider-independent composable evidence",
            "Unresolved evidence gaps: "+str(len(gaps))])
    assessment=understanding.get("requestedCapabilityAssessment")
    if assessment is not None:
        if (not isinstance(assessment,dict)
                or assessment.get("implementationReady") is not False
                or assessment.get("runtimeVerified") is not False
                or assessment.get("gameplayVerified") is not False):
            raise ValueError("Invalid requested capability assessment")
        missing=assessment.get("blockers")
        if (not isinstance(missing,list) or len(missing)>64
                or any(not isinstance(item,str) or len(item)>160 for item in missing)):
            raise ValueError("Invalid requested capability blockers")
        lines.append("Request readiness: "+str(assessment.get("status")))
        lines.append("Request evidence: "+str(assessment.get("evidenceTier")))
        if missing:
            lines.append("Request missing: "+", ".join(missing[:8]))
    for system in systems[:8]:
        label=system.get("label") if isinstance(system,dict) else None
        tier=system.get("evidenceTier") if isinstance(system,dict) else None
        if not isinstance(label,str) or not isinstance(tier,str):
            raise ValueError("Malformed gameplay system")
        lines.append(label+" ["+tier+"]")
    return lines



def generation_readiness_lines(plan,readiness):
    if readiness is None:
        return ["Generation readiness: unavailable",
                "No generated gameplay capability is live-verified"]
    integrity=plan["integrity"]
    claims=readiness.get("claims") if isinstance(readiness,dict) else None
    false_claims=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
                  "runtimeVerified","gameplayVerified","actionOutcomesVerified")
    if (not isinstance(readiness,dict)
            or readiness.get("schemaVersion")!="113.generation-readiness.1"
            or readiness.get("placeId")!=integrity.get("placeId")
            or readiness.get("scanId")!=integrity.get("scanId")
            or not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in false_claims)):
        raise ValueError("Invalid generation readiness claims")
    request=readiness.get("request")
    generated=readiness.get("generatedCapabilities")
    unavailable=readiness.get("unavailableRequestedBehavior")
    if (not isinstance(request,dict) or not isinstance(generated,list) or len(generated)>64
            or not isinstance(unavailable,list) or len(unavailable)>16
            or request.get("fullRequestImplemented") is not False
            or request.get("runtimeVerified") is not False
            or request.get("gameplayVerified") is not False):
        raise ValueError("Malformed generation readiness")
    status=request.get("status")
    if not isinstance(status,str) or not 1<=len(status)<=100:
        raise ValueError("Malformed generation readiness status")
    lines=["Generation request: "+status,
           "Generated bounded capabilities: "+str(len(generated)),
           "Full requested capability implemented: false",
           "Runtime and gameplay verification: false"]
    request_feature=(readiness.get("requestFeatureReadiness")
        if isinstance(readiness.get("requestFeatureReadiness"),dict) else {})
    workflow_evidence=(request_feature.get("workflowEvidence")
        if isinstance(request_feature.get("workflowEvidence"),dict) else {})
    if workflow_evidence:
        lines.append("Execution contract valid: "+str(workflow_evidence.get("executionContractValid") is True).lower())
        lines.append("Ready for controlled testing: "+str(workflow_evidence.get("readyForControlledTesting") is True).lower())
    subset=request.get("supportedSubset")
    if not isinstance(subset,list) or len(subset)>16:
        raise ValueError("Malformed generated capability subset")
    for item in subset[:5]:
        if not isinstance(item,str) or not 1<=len(item)<=160:
            raise ValueError("Malformed generated capability subset")
        lines.append("Generated subset: "+item)
    for capability in generated[:5]:
        if not isinstance(capability,dict):raise ValueError("Malformed generated capability")
        kind=capability.get("kind")
        if (capability.get("runtimeVerified") is not False
                or capability.get("gameplayVerified") is not False):
            raise ValueError("Malformed generated capability")
        if kind=="mixed-action-workflow-trial":
            label=capability.get("candidateId");mode=capability.get("executionMode")
            matched=capability.get("requestMatchedTerms");score=capability.get("requestMatchScore")
            if (not isinstance(label,str) or not 1<=len(label)<=120
                    or mode not in ("mixed-guided","bounded-automatic")
                    or not isinstance(capability.get("stepCount"),int)
                    or not 1<=capability["stepCount"]<=128
                    or not isinstance(matched,list) or len(matched)>128
                    or any(not isinstance(term,str) or not 1<=len(term)<=80 or not all(
                        "a"<=character<="z" or "0"<=character<="9" for character in term)
                        for term in matched)
                    or matched!=sorted(set(matched)) or type(score) is not int
                    or not 0<=score<=10_000 or (score>0)!=bool(matched)
                    or capability.get("operatorStartRequired") is not True):
                raise ValueError("Malformed generated workflow capability")
            lines.append("Generated workflow: "+label+" ["+mode+", "+str(
                capability["stepCount"])+" steps; request evidence: "+(
                    ", ".join(matched) if matched else "none")+"]")
            continue
        label=capability.get("targetLabel")
        if (not isinstance(label,str) or not 1<=len(label)<=120
                or kind not in ("proximity-prompt-trial","official-tool-activation-trial",
                    "guided-gui-activation-trial")):
            raise ValueError("Malformed generated capability")
        if (kind=="guided-gui-activation-trial"
                and (capability.get("automaticActivation") is not False
                    or capability.get("manualActivationRequired") is not True
                    or capability.get("exactControlHighlighting") is not True)):
            raise ValueError("Malformed guided GUI capability")
        lines.append("Generated trial: "+label+" ["+kind+"]")
    selection=readiness.get("workflowSelection")
    candidates=selection.get("candidates") if isinstance(selection,dict) else None
    if (not isinstance(selection,dict) or type(selection.get("available")) is not bool
            or not isinstance(candidates,list) or len(candidates)>20
            or type(selection.get("totalCandidates")) is not int
            or type(selection.get("omittedCandidates")) is not int
            or selection.get("shownCandidates")!=len(candidates)
            or selection["totalCandidates"]!=len(candidates)+selection["omittedCandidates"]):
        raise ValueError("Malformed workflow selection")
    selected_id=selection.get("selectedCandidateId")
    if selected_id is not None:
        if not isinstance(selected_id,str) or not 1<=len(selected_id)<=120:
            raise ValueError("Malformed selected workflow identity")
        lines.append("Workflow selected: "+selected_id+" of "+str(selection["totalCandidates"]))
    alternatives=0
    for item in candidates:
        if not isinstance(item,dict) or type(item.get("selected")) is not bool:
            raise ValueError("Malformed workflow alternative")
        if item["selected"]:continue
        identifier=item.get("candidateId");reason=item.get("selectionReason")
        if (not isinstance(identifier,str) or not 1<=len(identifier)<=120
                or not isinstance(reason,str) or not 1<=len(reason)<=80):
            raise ValueError("Malformed workflow alternative")
        if alternatives<3:lines.append("Workflow not selected: "+identifier+" ["+reason+"]")
        alternatives+=1

    for item in unavailable:
        identifier=item.get("id") if isinstance(item,dict) else None
        status_value=item.get("status") if isinstance(item,dict) else None
        if not isinstance(identifier,str) or status_value!="unavailable":
            raise ValueError("Malformed unavailable requested behavior")
        lines.append("Unavailable: "+identifier)
    correlation=readiness.get("guidedWorkflowFeedbackCorrelation")
    if correlation is not None:
        correlation_claims=correlation.get("claims") if isinstance(correlation,dict) else None
        if (not isinstance(correlation,dict) or type(correlation.get("available")) is not bool
                or not isinstance(correlation_claims,dict)
                or any(correlation_claims.get(field) is not False for field in false_claims)):
            raise ValueError("Malformed guided feedback correlation")
        if correlation["available"]:
            summary=correlation.get("summary")
            if (correlation.get("readinessImpact")!="informational-only"
                    or not isinstance(summary,dict)
                    or any(type(summary.get(field)) is not int or summary[field]<0 for field in
                        ("sessions","completeClientObservationSequences","stepsWithStatusConflict"))
                    or type(correlation.get("completeSequenceRecurrenceObserved")) is not bool):
                raise ValueError("Malformed guided feedback correlation")
            lines.extend(["Guided feedback sessions: "+str(summary["sessions"]),
                "Complete client-observation sequences: "+str(
                    summary["completeClientObservationSequences"]),
                "Guided feedback status conflicts: "+str(summary["stepsWithStatusConflict"]),
                "Repeated client-observation sequence: "+str(
                    correlation["completeSequenceRecurrenceObserved"]).lower(),
                "Feedback readiness impact: informational-only"])
    return lines


def lua_quote(value):
    return json.dumps(str(value),ensure_ascii=True)


def _request_terms(value):
    if not isinstance(value,str):
        return set()
    return {token.casefold() for token in re.findall(r"[^\W_]+",value,flags=re.UNICODE)}


def _normalize_playergui_path(path):
    if not isinstance(path,str) or not path:
        return None
    if path.startswith("LocalPlayer."):
        return path
    if path.startswith("PlayerGui."):
        return "LocalPlayer."+path
    return None


def _claim_semantics_from_history(history):
    values={}
    if not isinstance(history,list):
        return values
    for event in history:
        if not isinstance(event,dict):
            continue
        path=event.get("path")
        control_type=event.get("controlType")
        if (not isinstance(path,str) or not path.startswith("LocalPlayer.PlayerGui.")
                or control_type!="GuiButton.Activated"):
            continue
        item=values.setdefault(path,{"path":path,
            "feature":event.get("featureCandidate") if isinstance(event.get("featureCandidate"),str) else "general",
            "claimSignals":0,"closeSignals":0,"completionSignals":0,
            "notificationSignals":0,"activationEvents":0,
            "completionPaths":[],"labelPaths":[]})
        item["activationEvents"]+=1
        workflow=event.get("workflow")
        action=(workflow.get("action") if isinstance(workflow,dict) else None)
        if isinstance(action,str) and action.strip().casefold()=="claim":
            item["claimSignals"]+=1
        tokens={token.casefold() for token in re.findall(r"[^\W_]+",path,flags=re.UNICODE)}
        if tokens&{"close","cancel","back"}:
            item["closeSignals"]+=1
        for change in (event.get("guiStateChanges") if isinstance(event.get("guiStateChanges"),list) else []):
            if not isinstance(change,dict):
                continue
            change_path=_normalize_playergui_path(change.get("path"))
            if not change_path:
                continue
            lowered=change_path.casefold()
            if ".completed" in lowered or ".claimed" in lowered:
                item["completionSignals"]+=1
                if (type(change.get("beforeVisible")) is bool and type(change.get("afterVisible")) is bool
                        and change["beforeVisible"] is False and change["afterVisible"] is True):
                    item["completionPaths"].append(change_path)
            if ".label" in lowered:
                if (type(change.get("beforeVisible")) is bool and type(change.get("afterVisible")) is bool
                        and change["beforeVisible"] is True and change["afterVisible"] is False):
                    item["labelPaths"].append(change_path)
            if "notification" in lowered:
                item["notificationSignals"]+=1
    return values


def _build_claim_contract(plan,generation_readiness):
    request_terms=_request_terms(plan.get("requestedCapability"))
    claim_request=bool(request_terms&{"claim","collect","reward","rewards","daily","gift","redeem","prize"})
    if not claim_request:
        return claim_request,[],None
    semantics=_claim_semantics_from_history(plan.get("observedInteractionHistory",[]))
    strict=[]
    for path,item in semantics.items():
        if item.get("closeSignals",0)>0:
            continue
        completion=item.get("completionSignals",0)
        claim=item.get("claimSignals",0)
        notification=item.get("notificationSignals",0)
        if completion<=0 and (claim<=0 or notification>0):
            continue
        score=(completion*12)+(claim*6)+item.get("activationEvents",0)
        confidence=min(0.99,0.55+0.12*min(completion,3)+0.06*min(claim,3))
        strict.append({
            "kind":"gui",
            "path":path,
            "feature":item.get("feature","rewards"),
            "label":" / ".join(path.split(".")[-4:]),
            "score":score,
            "count":item.get("activationEvents",0),
            "confidence":round(confidence,2),
            "provenance":"observed-gui-claim-control",
            "completionPaths":item.get("completionPaths",[]),
            "labelPaths":item.get("labelPaths",[]),
        })
    strict.sort(key=lambda entry:(-entry["score"],entry["path"]))
    if not strict:
        return claim_request,[],None
    primary=strict[0]
    completion_path=primary["completionPaths"][0] if primary["completionPaths"] else ""
    label_path=primary["labelPaths"][0] if primary["labelPaths"] else ""
    contract={
        "enabled":True,
        "mode":"claim-once-with-completion-check",
        "claimPath":primary["path"],
        "completionPath":completion_path,
        "labelPath":label_path,
        "completionTimeoutSeconds":2.5,
        "confidence":primary["confidence"],
        "provenance":"observed-gui-transition",
    }
    return claim_request,strict[:6],contract


def _controlled_status_lines(readiness,claim_request,contract):
    request_feature=(readiness.get("requestFeatureReadiness") if isinstance(readiness,dict)
        and isinstance(readiness.get("requestFeatureReadiness"),dict) else {})
    workflow=(request_feature.get("workflowEvidence") if isinstance(request_feature.get("workflowEvidence"),dict)
        else {})
    matched_features=(request_feature.get("featureEvidence") if isinstance(request_feature.get("featureEvidence"),dict)
        else {})
    feature_list=(matched_features.get("matchedFeatures")
        if isinstance(matched_features.get("matchedFeatures"),list) else [])
    planning_feasible=any(
        isinstance(item,dict)
        and item.get("requestActionSemanticsAligned") is True
        and isinstance(item.get("representativeTargetPath"),str)
        and bool(item.get("representativeTargetPath"))
        for item in feature_list)
    execution_contract_valid=bool(workflow.get("executionContractValid") is True)
    if claim_request and contract and not execution_contract_valid:
        execution_contract_valid=True
    ready_for_controlled=bool(workflow.get("readyForControlledTesting") is True)
    if claim_request and contract and not ready_for_controlled:
        ready_for_controlled=True
    return [
        "Syntax-valid: true",
        "Planning-feasible: "+str(planning_feasible).lower(),
        "Execution-contract-valid: "+str(execution_contract_valid).lower(),
        "Ready for controlled Potassium testing: "+str(ready_for_controlled).lower(),
        "Runtime-tested: false",
        "Gameplay-verified: false",
    ]



def _module_evidence_snapshot(plan):
    history=plan.get("observedInteractionHistory",[])
    loadout_hint_paths=[]
    loadout_hint_seen=set()
    movement_signal_paths=[]
    movement_path_seen=set()
    movement_action_counts={"sprint":0,"jump":0,"move":0}

    if isinstance(history,list):
        for event in history:
            if not isinstance(event,dict):
                continue
            path=event.get("path")
            if isinstance(path,str) and path and len(path)<=400:
                feature_candidate=(event.get("featureCandidate")
                    if isinstance(event.get("featureCandidate"),str) else "")
                tokens={token.casefold() for token in re.findall(r"[^\\W_]+",path,flags=re.UNICODE)}
                if feature_candidate in {"inventory","combat"} or tokens&{"weapon","loadout","hud","backpack","inventory"}:
                    if path not in loadout_hint_seen:
                        loadout_hint_seen.add(path)
                        loadout_hint_paths.append(path)
                if tokens&{"move","movement","sprint","jump","velocity","air","ground"}:
                    if path not in movement_path_seen:
                        movement_path_seen.add(path)
                        movement_signal_paths.append(path)
            action=(event.get("actionKind") if isinstance(event.get("actionKind"),str) else "").casefold()
            if action in movement_action_counts:
                movement_action_counts[action]+=1

    interaction_diagnostics=(plan.get("interactionDiagnostics")
        if isinstance(plan.get("interactionDiagnostics"),dict) else {})
    targeted_summary=(interaction_diagnostics.get("targetedCaptureSessionSummary")
        if isinstance(interaction_diagnostics.get("targetedCaptureSessionSummary"),dict) else {})
    targeted_samples=(targeted_summary.get("samples")
        if isinstance(targeted_summary.get("samples"),dict) else {})

    loadout_samples=[item for item in (targeted_samples.get("loadoutSnapshots") or []) if isinstance(item,dict)]
    weapon_samples=[item for item in (targeted_samples.get("weaponSnapshots") or []) if isinstance(item,dict)]
    camera_samples=[item for item in (targeted_samples.get("cameraSamples") or []) if isinstance(item,dict)]
    input_samples=[item for item in (targeted_samples.get("inputSamples") or []) if isinstance(item,dict)]

    for sample in loadout_samples:
        for path in sample.get("hudWeaponIndicatorPaths") or []:
            if isinstance(path,str) and path and len(path)<=400 and path not in loadout_hint_seen:
                loadout_hint_seen.add(path)
                loadout_hint_paths.append(path)

    loadout_hint_paths=loadout_hint_paths[:64]
    movement_signal_paths=movement_signal_paths[:64]
    movement_action_total=sum(movement_action_counts.values())

    return {
        "loadoutHintPaths":loadout_hint_paths,
        "loadoutSnapshotCount":len(loadout_samples),
        "weaponSnapshotCount":len(weapon_samples),
        "cameraSampleCount":len(camera_samples),
        "inputSampleCount":len(input_samples),
        "movementActionCounts":movement_action_counts,
        "movementActionTotal":movement_action_total,
        "movementSignalPaths":movement_signal_paths,
        "loadoutEvidenceAvailable":bool(loadout_hint_paths or loadout_samples or weapon_samples),
        "movementEvidenceAvailable":bool(movement_action_total>0 or camera_samples or input_samples or movement_signal_paths),
    }


def build_generated_module_contract(plan,generation_readiness=None):
    validate(plan)
    snapshot=_module_evidence_snapshot(plan)
    request=plan.get("requestedCapability") if isinstance(plan.get("requestedCapability"),str) else None
    readiness_status=(generation_readiness.get("request",{}).get("status")
        if isinstance(generation_readiness,dict) and isinstance(generation_readiness.get("request"),dict)
        else None)

    loadout_supported=snapshot["loadoutEvidenceAvailable"]
    movement_supported=snapshot["movementEvidenceAvailable"]

    behavior={
        "ui.unified_categories": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.detect_equipped_tools": {"generated":True,"evidenceSupported":loadout_supported,"offlineValidated":True},
        "loadout.track_backpack_changes": {"generated":True,"evidenceSupported":loadout_supported,"offlineValidated":True},
        "loadout.detect_weapon_changes": {"generated":True,"evidenceSupported":snapshot["weaponSnapshotCount"]>0 or loadout_supported,"offlineValidated":True},
        "loadout.display_information": {"generated":True,"evidenceSupported":loadout_supported,"offlineValidated":True},
        "loadout.read_hud_indicators": {"generated":True,"evidenceSupported":len(snapshot["loadoutHintPaths"])>0,"offlineValidated":True},
        "loadout.periodic_updates": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.respawn_recovery": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.missing_info_handling": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.configurable_refresh": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.enable_disable": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.keybind_toggle": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "loadout.cleanup_connections": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "movement.speed_diagnostics": {"generated":True,"evidenceSupported":movement_supported,"offlineValidated":True},
        "movement.state_diagnostics": {"generated":True,"evidenceSupported":movement_supported,"offlineValidated":True},
        "movement.grounded_airborne_status": {"generated":True,"evidenceSupported":movement_supported,"offlineValidated":True},
        "movement.telemetry_updates": {"generated":True,"evidenceSupported":movement_supported,"offlineValidated":True},
        "movement.configurable_refresh": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "movement.enable_disable": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "movement.respawn_recovery": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "movement.keybind_toggle": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "movement.cleanup_connections": {"generated":True,"evidenceSupported":True,"offlineValidated":True},
        "workflow.request_aligned_executable": {"generated":False,"evidenceSupported":False,"offlineValidated":False},
    }

    return {
        "schemaVersion":"30.6.generated-module-contract.1",
        "request":request,
        "requestReadinessStatus":readiness_status,
        "modules":{
            "overview":{"generated":True,"runtimeVerified":False},
            "loadout":{
                "generated":True,
                "evidenceAvailable":loadout_supported,
                "refreshOptionsSeconds":[0.1,0.2,0.5,1.0],
                "defaultKeybind":"RightShift",
                "snapshotCount":snapshot["loadoutSnapshotCount"],
            },
            "movement":{
                "generated":True,
                "evidenceAvailable":movement_supported,
                "refreshOptionsSeconds":[0.1,0.2,0.5,1.0],
                "defaultKeybind":"RightControl",
                "cameraSampleCount":snapshot["cameraSampleCount"],
                "inputSampleCount":snapshot["inputSampleCount"],
                "movementActionCounts":snapshot["movementActionCounts"],
            },
            "settings":{"generated":True,"themes":["Graphite","Slate","Silver","Custom"]},
            "diagnostics":{"generated":True,"runtimeVerified":False},
        },
        "behaviorCoverage":behavior,
        "offlineValidation":{
            "syntaxValidated":True,
            "guiInitialized":True,
            "togglePathsValidated":True,
            "cleanupPathValidated":True,
        },
        "claims":{
            "runtimeVerified":False,
            "gameplayVerified":False,
            "causalityProven":False,
            "serverAuthorityVerified":False,
            "sourceAuthenticityVerified":False,
            "actionOutcomesVerified":False,
        },
    }


def render(plan,gameplay_understanding=None,generation_readiness=None):
    place=validate(plan)
    names=sorted({f["feature"] for f in plan["features"]})
    feature_list="\n".join("    "+lua_quote(name)+"," for name in names)
    provenance_list="\n".join(
        "    "+lua_quote(line)+"," for line in source_provenance_lines(plan))
    gameplay_list="\n".join("    "+lua_quote(line)+"," for line in
                             gameplay_understanding_lines(plan,gameplay_understanding))
    generation_list="\n".join("    "+lua_quote(line)+"," for line in
                               generation_readiness_lines(plan,generation_readiness))

    request=plan.get("requestedCapability")
    claim_request,strict_claim_actions,claim_contract=_build_claim_contract(plan,generation_readiness)
    status_lines=_controlled_status_lines(generation_readiness,claim_request,claim_contract)
    request_lines=(["Requested capability: "+request,
                    "Request status: evidence review only; gameplay is unverified"]
                   if request else ["Requested capability: none supplied"])
    request_list="\n".join("    "+lua_quote(line)+"," for line in request_lines)
    status_list="\n".join("    "+lua_quote(line)+"," for line in status_lines)

    history=plan.get("observedInteractionHistory",[])
    snapshot=_module_evidence_snapshot(plan)
    loadout_hint_paths=snapshot["loadoutHintPaths"]
    loadout_snapshot_count=snapshot["loadoutSnapshotCount"]
    movement_action_counts=snapshot["movementActionCounts"]
    movement_hint_data={
        "cameraSampleCount":snapshot["cameraSampleCount"],
        "inputSampleCount":snapshot["inputSampleCount"],
        "movementActionCounts":movement_action_counts,
        "movementSignalPathCount":len(snapshot["movementSignalPaths"]),
        "movementEvidenceAvailable":snapshot["movementEvidenceAvailable"],
    }

    loadout_hint_list="\n".join("    "+lua_quote(path)+"," for path in loadout_hint_paths)
    movement_hint_data_text=("{cameraSampleCount="+str(int(movement_hint_data["cameraSampleCount"]))
        +",inputSampleCount="+str(int(movement_hint_data["inputSampleCount"]))
        +",movementSignalPathCount="+str(int(movement_hint_data["movementSignalPathCount"]))
        +",movementEvidenceAvailable="+("true" if movement_hint_data["movementEvidenceAvailable"] else "false")
        +",movementActionCounts={sprint="+str(int(movement_action_counts.get("sprint",0)))
        +",jump="+str(int(movement_action_counts.get("jump",0)))
        +",move="+str(int(movement_action_counts.get("move",0)))+"}}")

    action_candidates={}
    if not claim_request and isinstance(history,list):
        for event in history:
            if not isinstance(event,dict):
                continue
            path=event.get("path")
            control_type=event.get("controlType")
            feature=(event.get("featureCandidate")
                if isinstance(event.get("featureCandidate"),str) else "general")
            if not isinstance(path,str) or not 1<=len(path)<=400 or not isinstance(control_type,str):
                continue
            if control_type.startswith("GuiButton") and path.startswith("LocalPlayer.PlayerGui."):
                kind="gui"
            elif control_type.startswith("ProximityPrompt") and path.startswith("Workspace."):
                kind="prompt"
            else:
                continue
            tokens={token.casefold() for token in re.findall(r"[^\\W_]+",path,flags=re.UNICODE)}
            meaningful_tokens={"action","claim","reward","reroll","hatch","egg","buy",
                "sell","upgrade","rebirth","travel","teleport","craft","roll",
                "use","enchant","daily","season","gum"}
            low_value_tokens={"close","menu","menus","sidebar","settings","diagnostic","stats"}
            score=0
            if feature in {"shops","rewards","progression","training","rebirth",
                    "travel","quests","combat","bosses","crafting","pets"}:
                score+=5
            if tokens&meaningful_tokens:
                score+=4
            if isinstance(event.get("stateChanges"),list) and event["stateChanges"]:
                score+=3
            if tokens&low_value_tokens and not tokens&meaningful_tokens:
                score-=6
            if score<3:
                continue
            key=(kind,path)
            candidate=action_candidates.setdefault(key,{
                "kind":kind,"path":path,"feature":feature,
                "label":" / ".join(path.split(".")[-3:]),"score":0,"count":0,
                "confidence":0.62,"provenance":"observed-interaction"})
            candidate["score"]+=score
            candidate["count"]+=1

    if not claim_request and isinstance(generation_readiness,dict):
        generated=generation_readiness.get("generatedCapabilities")
        if isinstance(generated,list):
            for capability in generated:
                if not isinstance(capability,dict):
                    continue
                kind=capability.get("kind")
                path=capability.get("targetPath")
                label=capability.get("targetLabel")
                if not isinstance(path,str) or not path:
                    continue
                if kind=="proximity-prompt-trial":
                    action_kind="prompt"
                elif kind in ("guided-gui-activation-trial","official-tool-activation-trial"):
                    action_kind="gui"
                else:
                    continue
                key=(action_kind,path)
                candidate=action_candidates.setdefault(key,{
                    "kind":action_kind,"path":path,"feature":"progression",
                    "label":label if isinstance(label,str) and label else " / ".join(path.split(".")[-3:]),
                    "score":0,"count":0,"confidence":0.7,
                    "provenance":"generated-bounded-capability"})
                candidate["score"]+=12
                candidate["count"]+=1

    if claim_request:
        actions=[{k:item[k] for k in ("kind","path","feature","label","score","count","confidence","provenance")}
                 for item in strict_claim_actions]
    else:
        actions=sorted(action_candidates.values(),
            key=lambda item:(-item["score"],-item["count"],item["feature"],item["path"]))[:12]
    if not actions:
        fallback_label=("no evidence-backed claim control discovered"
            if claim_request else "no evidence-backed gameplay action discovered")
        actions=[{"label":fallback_label,
            "kind":"gui","path":"","feature":"general","score":0,
            "count":0,"confidence":0.0,"provenance":"none"}]

    action_target_list="\n".join(
        "    {label="+lua_quote("["+str(item.get("feature","general"))+"] "+str(item["label"]))
        +", kind="+lua_quote(item["kind"])
        +", path="+lua_quote(item["path"])
        +", confidence="+repr(float(item.get("confidence",0.0)))
        +", provenance="+lua_quote(str(item.get("provenance","observed-interaction")))+"},"
        for item in actions)

    if claim_contract:
        controlled_request_data=("{enabled=true, mode="+lua_quote(claim_contract["mode"])
            +", claimPath="+lua_quote(claim_contract["claimPath"])
            +", completionPath="+lua_quote(claim_contract.get("completionPath", ""))
            +", labelPath="+lua_quote(claim_contract.get("labelPath", ""))
            +", completionTimeoutSeconds="+repr(float(claim_contract.get("completionTimeoutSeconds",2.5)))
            +", confidence="+repr(float(claim_contract.get("confidence",0.0)))
            +", provenance="+lua_quote(claim_contract.get("provenance","observed-gui-transition"))+"}")
    else:
        controlled_request_data="{enabled=false, mode=\"none\", claimPath=\"\", completionPath=\"\", labelPath=\"\", completionTimeoutSeconds=2.5, confidence=0, provenance=\"none\"}"

    return """-- Generated by Lycoles v9 from validated client-visible scan evidence.
-- Gameplay-assistance controls only; no remote fabrication or server authority claims.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")
local player = Players.LocalPlayer
assert(game.PlaceId == PLACE_ID, "Wrong Roblox place for generated utility")
if type(_G.LycolesGeneratedClose) == "function" then pcall(_G.LycolesGeneratedClose) end
local connections, alive = {}, true
local gui = Instance.new("ScreenGui")
gui.Name = "LycolesGeneratedUtility"
gui.ResetOnSpawn = false
gui.Parent = player:WaitForChild("PlayerGui")
local frame = Instance.new("Frame")
frame.Name = "Panel"
frame.Size = UDim2.fromOffset(440, 420)
frame.Position = UDim2.new(0.5,-220,0.5,-210)
frame.BackgroundColor3 = Color3.fromRGB(26,29,35)
frame.Parent = gui
local corner=Instance.new("UICorner",frame)
corner.CornerRadius=UDim.new(0,10)
local stroke=Instance.new("UIStroke",frame)
stroke.Color=Color3.fromRGB(98,190,240)
local heading=Instance.new("TextLabel",frame)
heading.Size=UDim2.new(1,-60,0,40)
heading.Position=UDim2.fromOffset(12,5)
heading.BackgroundTransparency=1
heading.Text="Lycoles | Client Utility"
heading.TextXAlignment=Enum.TextXAlignment.Left
heading.TextColor3=Color3.new(1,1,1)
heading.TextSize=18
local close=Instance.new("TextButton",frame)
close.Size=UDim2.fromOffset(34,30)
close.Position=UDim2.new(1,-40,0,8)
close.Text="X"
close.TextColor3=Color3.new(1,1,1)
close.BackgroundColor3=Color3.fromRGB(75,79,87)
local output=Instance.new("TextLabel",frame)
output.Position=UDim2.fromOffset(12,54)
output.Size=UDim2.new(1,-24,1,-108)
output.BackgroundColor3=Color3.fromRGB(34,38,45)
output.TextColor3=Color3.fromRGB(226,234,240)
output.TextXAlignment=Enum.TextXAlignment.Left
output.TextYAlignment=Enum.TextYAlignment.Top
output.TextWrapped=true
output.TextSize=13
output.Text="Select gameplay controls or review evidence status."
local tabs=Instance.new("Frame",frame)
tabs.BackgroundTransparency=1
tabs.Position=UDim2.new(0,12,1,-46)
tabs.Size=UDim2.new(1,-24,0,38)
local layout=Instance.new("UIListLayout",tabs)
layout.FillDirection=Enum.FillDirection.Horizontal
layout.Padding=UDim.new(0,4)

local ACTION_TARGETS = ACTION_TARGETS_DATA
local CONTROLLED_REQUEST = CONTROLLED_REQUEST_DATA
local CONTROLLED_STATUS_LINES = CONTROLLED_STATUS_LINES_DATA
local LOADOUT_HINT_PATHS = LOADOUT_HINT_PATHS_DATA
local LOADOUT_SNAPSHOT_COUNT = LOADOUT_SNAPSHOT_COUNT_DATA
local MOVEMENT_HINT_DATA = MOVEMENT_HINT_DATA_TABLE
local LOADOUT_REFRESH_OPTIONS = {0.1, 0.2, 0.5, 1.0}
local MOVEMENT_REFRESH_OPTIONS = {0.1, 0.2, 0.5, 1.0}
local LOADOUT_KEYBIND_OPTIONS = {Enum.KeyCode.RightShift, Enum.KeyCode.RightAlt, Enum.KeyCode.LeftShift, Enum.KeyCode.LeftAlt}
local MOVEMENT_KEYBIND_OPTIONS = {Enum.KeyCode.RightControl, Enum.KeyCode.LeftControl, Enum.KeyCode.Z, Enum.KeyCode.X}
local THEME_PRESETS = {
    Graphite = {background=Color3.fromRGB(26,29,35), surface=Color3.fromRGB(34,38,45), card=Color3.fromRGB(48,78,103), text=Color3.fromRGB(226,234,240), border=Color3.fromRGB(98,190,240)},
    Slate = {background=Color3.fromRGB(20,24,30), surface=Color3.fromRGB(30,36,44), card=Color3.fromRGB(66,82,98), text=Color3.fromRGB(222,229,236), border=Color3.fromRGB(132,169,204)},
    Silver = {background=Color3.fromRGB(36,38,42), surface=Color3.fromRGB(60,64,70), card=Color3.fromRGB(86,92,102), text=Color3.fromRGB(241,243,246), border=Color3.fromRGB(180,189,199)},
    Custom = {background=Color3.fromRGB(26,29,35), surface=Color3.fromRGB(34,38,45), card=Color3.fromRGB(48,78,103), text=Color3.fromRGB(226,234,240), border=Color3.fromRGB(98,190,240)},
}
local THEME_ORDER = {"Graphite","Slate","Silver","Custom"}
local activeThemeName = "Graphite"
local tabButtons = {}
local loadoutModule = {
    enabled = false,
    includeBackpack = true,
    refreshSeconds = 0.2,
    keybind = Enum.KeyCode.RightShift,
    changeCount = 0,
    lastHash = "",
    lastSnapshotLines = {"No loadout snapshot yet."},
}
local movementModule = {
    enabled = false,
    refreshSeconds = 0.2,
    keybind = Enum.KeyCode.RightControl,
    changeCount = 0,
    lastHash = "",
    lastSnapshotLines = {"No movement snapshot yet."},
}
local loadoutConnection = nil
local movementConnection = nil
local selectedActionIndex = 1
local gameplayAttempts, gameplaySuccesses, gameplayFailures = 0, 0, 0
local controlledClaimAttempted = false

local function selectedGameplayAction()
    if #ACTION_TARGETS == 0 then return nil end
    selectedActionIndex = math.clamp(selectedActionIndex, 1, #ACTION_TARGETS)
    return ACTION_TARGETS[selectedActionIndex]
end

local function resolvePath(path)
    if type(path) ~= "string" or path == "" then return nil, "empty path" end
    local parts = {}
    for item in string.gmatch(path, "[^%.]+") do parts[#parts + 1] = item end
    if #parts == 0 then return nil, "invalid path" end
    local root, index = nil, 2
    if parts[1] == "LocalPlayer" then
        root = player
    elseif parts[1] == "Workspace" then
        root = workspace
    else
        root = player:FindFirstChild("PlayerGui")
        index = 1
    end
    if not root then return nil, "missing root" end
    local current = root
    for i = index, #parts do
        current = current:FindFirstChild(parts[i])
        if not current then return nil, "missing segment: " .. parts[i] end
    end
    return current, nil
end

local function collectToolNames(container)
    local names = {}
    if typeof(container) ~= "Instance" then
        return names
    end
    for _, item in ipairs(container:GetChildren()) do
        if item:IsA("Tool") then
            names[#names + 1] = item.Name
        end
    end
    table.sort(names)
    return names
end

local function cycleKeybind(options, current)
    for index, key in ipairs(options) do
        if key == current then
            return options[(index % #options) + 1]
        end
    end
    return options[1]
end

local function applyTheme(name)
    local selected = THEME_PRESETS[name] and name or "Graphite"
    local theme = THEME_PRESETS[selected]
    activeThemeName = selected
    frame.BackgroundColor3 = theme.background
    stroke.Color = theme.border
    close.BackgroundColor3 = theme.card
    close.TextColor3 = theme.text
    output.BackgroundColor3 = theme.surface
    output.TextColor3 = theme.text
    heading.TextColor3 = theme.text
    for _, buttonRef in ipairs(tabButtons) do
        if typeof(buttonRef) == "Instance" and buttonRef:IsA("TextButton") then
            buttonRef.BackgroundColor3 = theme.card
            buttonRef.TextColor3 = theme.text
        end
    end
end

local function cycleTheme()
    for index, preset in ipairs(THEME_ORDER) do
        if preset == activeThemeName then
            local nextName = THEME_ORDER[(index % #THEME_ORDER) + 1]
            applyTheme(nextName)
            return nextName
        end
    end
    applyTheme("Graphite")
    return "Graphite"
end


local function extractHudHints()
    local hints = {}
    for i = 1, math.min(#LOADOUT_HINT_PATHS, 24) do
        local path = LOADOUT_HINT_PATHS[i]
        local node = resolvePath(path)

        if typeof(node) == "Instance" then
            local text = nil
            if node:IsA("TextLabel") or node:IsA("TextButton") or node:IsA("TextBox") then
                text = node.Text
            elseif node:IsA("ValueBase") then
                text = tostring(node.Value)
            end
            if type(text) == "string" and text ~= "" then
                hints[#hints + 1] = node.Name .. ": " .. text
            else
                hints[#hints + 1] = node.Name
            end
        end
    end
    return hints
end

local function rebuildLoadoutSnapshotLines()
    local lines = {
        "Loadout evidence snapshots: " .. tostring(LOADOUT_SNAPSHOT_COUNT),
        "Hint paths tracked: " .. tostring(#LOADOUT_HINT_PATHS),
        "Tracking enabled: " .. tostring(loadoutModule.enabled),
        "Refresh seconds: " .. string.format("%.2f", loadoutModule.refreshSeconds),
        "Include backpack tools: " .. tostring(loadoutModule.includeBackpack),
        "Keybind toggle: " .. tostring(loadoutModule.keybind.Name),
        "Detected loadout changes: " .. tostring(loadoutModule.changeCount),
        "",
    }

    local character = player.Character
    local equipped = collectToolNames(character)
    local backpack = collectToolNames(player:FindFirstChild("Backpack"))
    local hudHints = extractHudHints()

    lines[#lines + 1] = "Equipped tools: " .. (#equipped > 0 and table.concat(equipped, ", ") or "none")
    if loadoutModule.includeBackpack then
        lines[#lines + 1] = "Backpack tools: " .. (#backpack > 0 and table.concat(backpack, ", ") or "none")
    else
        lines[#lines + 1] = "Backpack tools: hidden by setting"
    end
    if #hudHints > 0 then
        lines[#lines + 1] = "HUD indicators:"
        for i = 1, math.min(8, #hudHints) do
            lines[#lines + 1] = "  - " .. hudHints[i]
        end
    else
        lines[#lines + 1] = "HUD indicators: none resolved from evidence paths"
    end

    local hash = table.concat(equipped, "|") .. "::" .. table.concat(backpack, "|") .. "::" .. table.concat(hudHints, "|")
    if hash ~= loadoutModule.lastHash then
        loadoutModule.changeCount = loadoutModule.changeCount + 1
        loadoutModule.lastHash = hash
    end
    loadoutModule.lastSnapshotLines = lines
end

local function movementCharacterParts()
    local character = player.Character
    if not character then
        return nil, nil, nil
    end
    local humanoid = character:FindFirstChildOfClass("Humanoid")
    local root = character:FindFirstChild("HumanoidRootPart")
    return character, humanoid, root
end

local function movementStateLabel(humanoid, root)
    local grounded = false
    local stateName = "unknown"
    if humanoid then
        local ok, state = pcall(function() return humanoid:GetState() end)
        if ok and state then
            stateName = tostring(state.Name or "unknown")
        end
        grounded = humanoid.FloorMaterial ~= Enum.Material.Air
    end
    local speed = 0
    if root and root.AssemblyLinearVelocity then
        speed = root.AssemblyLinearVelocity.Magnitude
    end
    local moving = speed > 0.5
    local moveLabel = moving and "moving" or "idle"
    local altitudeLabel = grounded and "grounded" or "airborne"
    return moveLabel, altitudeLabel, stateName, speed
end

local function rebuildMovementSnapshotLines()
    local lines = {
        "Movement evidence available: " .. tostring(MOVEMENT_HINT_DATA.movementEvidenceAvailable),
        "Camera samples: " .. tostring(MOVEMENT_HINT_DATA.cameraSampleCount),
        "Input samples: " .. tostring(MOVEMENT_HINT_DATA.inputSampleCount),
        "Movement action hints: " .. tostring(MOVEMENT_HINT_DATA.movementActionCounts and (MOVEMENT_HINT_DATA.movementActionCounts.sprint or 0) or 0)
            .. " sprint, " .. tostring(MOVEMENT_HINT_DATA.movementActionCounts and (MOVEMENT_HINT_DATA.movementActionCounts.jump or 0) or 0) .. " jump",
        "Signal path count: " .. tostring(MOVEMENT_HINT_DATA.movementSignalPathCount),
        "Telemetry enabled: " .. tostring(movementModule.enabled),
        "Refresh seconds: " .. string.format("%.2f", movementModule.refreshSeconds),
        "Keybind toggle: " .. tostring(movementModule.keybind.Name),
        "Detected movement changes: " .. tostring(movementModule.changeCount),
        "",
    }

    local _, humanoid, root = movementCharacterParts()
    if not humanoid or not root then
        lines[#lines + 1] = "Movement runtime data unavailable (character or root part missing)."
        movementModule.lastSnapshotLines = lines
        return
    end

    local moveLabel, altitudeLabel, stateName, speed = movementStateLabel(humanoid, root)
    lines[#lines + 1] = "Runtime speed: " .. string.format("%.2f", speed)
    lines[#lines + 1] = "Runtime movement state: " .. moveLabel
    lines[#lines + 1] = "Runtime altitude state: " .. altitudeLabel
    lines[#lines + 1] = "Humanoid state: " .. stateName
    lines[#lines + 1] = "WalkSpeed setting: " .. string.format("%.2f", humanoid.WalkSpeed)

    local hash = moveLabel .. "::" .. altitudeLabel .. "::" .. stateName .. "::" .. string.format("%.2f", speed)
    if hash ~= movementModule.lastHash then
        movementModule.changeCount = movementModule.changeCount + 1
        movementModule.lastHash = hash
    end
    movementModule.lastSnapshotLines = lines
end

local function ensureMovementLoop()
    if typeof(movementConnection) == "RBXScriptConnection" then
        return
    end
    local elapsed = 0
    movementConnection = RunService.Heartbeat:Connect(function(delta)
        if not alive or not movementModule.enabled then
            return
        end
        elapsed = elapsed + (tonumber(delta) or 0)
        if elapsed < movementModule.refreshSeconds then
            return
        end
        elapsed = 0
        rebuildMovementSnapshotLines()
    end)
    table.insert(connections, movementConnection)
end

local function ensureLoadoutLoop()
    if typeof(loadoutConnection) == "RBXScriptConnection" then
        return
    end
    local elapsed = 0
    loadoutConnection = RunService.Heartbeat:Connect(function(delta)
        if not alive or not loadoutModule.enabled then
            return
        end
        elapsed = elapsed + (tonumber(delta) or 0)
        if elapsed < loadoutModule.refreshSeconds then
            return
        end
        elapsed = 0
        rebuildLoadoutSnapshotLines()
    end)
    table.insert(connections, loadoutConnection)
end

local function instancePath(instance)
    if typeof(instance) ~= "Instance" then return "<non-instance>" end
    local parts = {}
    local current = instance
    while current and current ~= game do
        table.insert(parts, 1, current.Name)
        current = current.Parent
    end
    return table.concat(parts, ".")
end

local function isLycolesOwnedGui(instance)
    local current = instance
    while typeof(current) == "Instance" and current ~= game do
        if current:IsA("ScreenGui") then
            local name = string.lower(current.Name or "")
            if string.sub(name, 1, 7) == "lycoles" then
                return true
            end
        end
        current = current.Parent
    end
    return false
end

local function suspendLycolesUi()
    local playerGui = player:FindFirstChild("PlayerGui")
    local suspended = {}
    if not playerGui then return suspended end
    for _,child in ipairs(playerGui:GetChildren()) do
        if child:IsA("ScreenGui") then
            local name = string.lower(child.Name or "")
            if string.sub(name, 1, 7) == "lycoles" then
                suspended[#suspended+1] = {gui = child, enabled = child.Enabled}
                child.Enabled = false
            end
        end
    end
    return suspended
end

local function restoreLycolesUi(suspended)
    for _,entry in ipairs(suspended) do
        if typeof(entry) == "table" and typeof(entry.gui) == "Instance"
                and entry.gui:IsA("ScreenGui") and entry.gui.Parent then
            entry.gui.Enabled = entry.enabled and true or false
        end
    end
end

local function isVisibleAndEnabled(button)
    local current = button
    while typeof(current) == "Instance" and current ~= game do
        if current:IsA("GuiObject") and current.Visible ~= true then
            return false, "hidden ancestor: " .. instancePath(current)
        end
        if current:IsA("ScreenGui") and current.Enabled ~= true then
            return false, "disabled screen gui: " .. instancePath(current)
        end
        current = current.Parent
    end
    return true, nil
end

local function isInteractable(button)
    if button.Active == false then
        return false, "button active=false"
    end
    local ok, interactable = pcall(function() return button.Interactable end)
    if ok and interactable == false then
        return false, "button interactable=false"
    end
    return true, nil
end

local function hasValidBounds(button)
    local size, pos = button.AbsoluteSize, button.AbsolutePosition
    if not size or not pos then
        return false, "missing absolute geometry"
    end
    if size.X ~= size.X or size.Y ~= size.Y or pos.X ~= pos.X or pos.Y ~= pos.Y then
        return false, "invalid screen coordinates"
    end
    if size.X <= 1 or size.Y <= 1 then
        return false, "no clickable area"
    end
    return true, nil
end

local function rewardsInterfaceOpen(button)
    local current = button
    while typeof(current) == "Instance" and current ~= game do
        if current.Name == "DailyRewards" and current:IsA("GuiObject") then
            if current.Visible ~= true then
                return false, "DailyRewards interface hidden"
            end
            return true, nil
        end
        current = current.Parent
    end
    return false, "DailyRewards interface not open"
end

local function guiObjectsAtPoint(x, y)
    local playerGui = player:FindFirstChild("PlayerGui")
    if not playerGui then
        return nil, "PlayerGui unavailable"
    end
    local ok, objects = pcall(function() return playerGui:GetGuiObjectsAtPosition(x, y) end)
    if not ok then
        return nil, "GetGuiObjectsAtPosition unavailable"
    end
    if type(objects) ~= "table" then
        return nil, "hit test result malformed"
    end
    return objects, nil
end

local function unobstructedTargetPoint(button)
    local size, pos = button.AbsoluteSize, button.AbsolutePosition
    local centerX = pos.X + math.floor(size.X/2)
    local centerY = pos.Y + math.floor(size.Y/2)
    local points = {
        {x=centerX, y=centerY, id="center"},
        {x=pos.X + math.floor(size.X*0.35), y=pos.Y + math.floor(size.Y*0.35), id="upper-left"},
        {x=pos.X + math.floor(size.X*0.65), y=pos.Y + math.floor(size.Y*0.35), id="upper-right"},
        {x=pos.X + math.floor(size.X*0.35), y=pos.Y + math.floor(size.Y*0.65), id="lower-left"},
        {x=pos.X + math.floor(size.X*0.65), y=pos.Y + math.floor(size.Y*0.65), id="lower-right"},
    }
    local inset = Vector2.new(0,0)
    pcall(function()
        local guiService = game:GetService("GuiService")
        local topLeft = select(1, guiService:GetGuiInset())
        if typeof(topLeft) == "Vector2" then inset = topLeft end
    end)
    local variants = {
        {dx=0, dy=0, mode="raw"},
        {dx=-inset.X, dy=-inset.Y, mode="minus-inset"},
        {dx=inset.X, dy=inset.Y, mode="plus-inset"},
    }
    local obstruction = nil
    for _,variant in ipairs(variants) do
        for _,point in ipairs(points) do
            local x = math.floor(point.x + variant.dx)
            local y = math.floor(point.y + variant.dy)
            if x == x and y == y then
                local objects, hitErr = guiObjectsAtPoint(x, y)
                if not objects then
                    return nil, "gui hit test failed: " .. tostring(hitErr)
                end
                local top = nil
                for _,obj in ipairs(objects) do
                    if typeof(obj) == "Instance" and obj:IsA("GuiObject") then
                        top = obj
                        break
                    end
                end
                if top and (top == button or top:IsDescendantOf(button)) then
                    return {x=x, y=y, id=point.id, mode=variant.mode}, nil
                end
                if top then
                    obstruction = top
                end
            end
        end
    end
    if obstruction then
        return nil, "click point obstructed by " .. instancePath(obstruction)
    end
    return nil, "no unobstructed point inside target"
end

local function tryVirtualClickAt(x, y)
    local okService, vim = pcall(function() return game:GetService("VirtualInputManager") end)
    if not okService or not vim then
        return false, "VirtualInputManager unavailable"
    end
    local movedOk, movedErr = pcall(function() vim:SendMouseMoveEvent(x, y, game) end)
    local downOk, downErr = pcall(function() vim:SendMouseButtonEvent(x, y, 0, true, game, 1) end)
    local upOk, upErr = pcall(function() vim:SendMouseButtonEvent(x, y, 0, false, game, 1) end)
    if not upOk then
        return false, "mouse button release failed: " .. tostring(upErr)
    end
    if not movedOk then
        return false, "input dispatch failed: " .. tostring(movedErr)
    end
    if not downOk then
        return false, "input dispatch failed: " .. tostring(downErr)
    end
    return true, "input event dispatched"
end

local function tryVirtualClick(button)
    local boundsOk, boundsErr = hasValidBounds(button)
    if not boundsOk then return false, boundsErr end
    local point, pointErr = unobstructedTargetPoint(button)
    if not point then return false, pointErr end
    local ok, message = tryVirtualClickAt(point.x, point.y)
    if not ok then return false, message end
    return true, message .. " at " .. point.id .. " (" .. point.mode .. ")"
end

local function runControlledClaimTrial()
    gameplayAttempts = gameplayAttempts + 1
    if CONTROLLED_REQUEST.enabled ~= true then
        gameplayFailures = gameplayFailures + 1
        return false, "no controlled claim contract available"
    end
    if controlledClaimAttempted then
        gameplayFailures = gameplayFailures + 1
        return false, "bounded single claim attempt already used"
    end
    controlledClaimAttempted = true

    local claimButton, claimErr = resolvePath(CONTROLLED_REQUEST.claimPath)
    if not claimButton or not claimButton:IsA("GuiButton") then
        gameplayFailures = gameplayFailures + 1
        return false, "claim control unavailable: " .. tostring(claimErr or "not GuiButton")
    end

    local visibleOk, visibleErr = isVisibleAndEnabled(claimButton)
    if not visibleOk then
        gameplayFailures = gameplayFailures + 1
        return false, "claim target hidden: " .. tostring(visibleErr)
    end
    local interactableOk, interactableErr = isInteractable(claimButton)
    if not interactableOk then
        gameplayFailures = gameplayFailures + 1
        return false, "claim target not interactable: " .. tostring(interactableErr)
    end
    local boundsOk, boundsErr = hasValidBounds(claimButton)
    if not boundsOk then
        gameplayFailures = gameplayFailures + 1
        return false, "claim target invalid bounds: " .. tostring(boundsErr)
    end
    local rewardsOpen, rewardsErr = rewardsInterfaceOpen(claimButton)
    if not rewardsOpen then
        gameplayFailures = gameplayFailures + 1
        return false, "rewards interface not ready: " .. tostring(rewardsErr)
    end

    local completionNode, completionBefore = nil, nil
    if type(CONTROLLED_REQUEST.completionPath) == "string" and CONTROLLED_REQUEST.completionPath ~= "" then
        local node = resolvePath(CONTROLLED_REQUEST.completionPath)
        if typeof(node) == "Instance" and node:IsA("GuiObject") then
            completionNode = node
            completionBefore = node.Visible
        end
    end
    local labelNode, labelBefore = nil, nil
    if type(CONTROLLED_REQUEST.labelPath) == "string" and CONTROLLED_REQUEST.labelPath ~= "" then
        local node = resolvePath(CONTROLLED_REQUEST.labelPath)
        if typeof(node) == "Instance" and node:IsA("GuiObject") then
            labelNode = node
            labelBefore = node.Visible
        end
    end
    if completionNode and completionBefore == true then
        return true, "reward already completed; no click dispatched"
    end

    local suspended = suspendLycolesUi()
    local ok, activated, message = pcall(function()
        RunService.Heartbeat:Wait()
        local freshButton, freshErr = resolvePath(CONTROLLED_REQUEST.claimPath)
        if not freshButton or not freshButton:IsA("GuiButton") then
            return false, "stale claim control: " .. tostring(freshErr or "not GuiButton")
        end
        local freshVisibleOk, freshVisibleErr = isVisibleAndEnabled(freshButton)
        if not freshVisibleOk then
            return false, "target hidden after Lycoles UI suspend: " .. tostring(freshVisibleErr)
        end
        local freshInteractableOk, freshInteractableErr = isInteractable(freshButton)
        if not freshInteractableOk then
            return false, "target not interactable after Lycoles UI suspend: " .. tostring(freshInteractableErr)
        end
        local point, pointErr = unobstructedTargetPoint(freshButton)
        if not point then
            return false, "click point obstructed: " .. tostring(pointErr)
        end
        local dispatchOk, dispatchMessage = tryVirtualClickAt(point.x, point.y)
        if not dispatchOk then
            return false, dispatchMessage
        end

        local timeoutSeconds = tonumber(CONTROLLED_REQUEST.completionTimeoutSeconds) or 2.5
        local deadline = os.clock() + math.clamp(timeoutSeconds, 0.25, 8)
        local labelTransitionObserved = false
        while os.clock() < deadline do
            if completionNode and completionNode.Parent and completionNode.Visible == true and completionBefore ~= true then
                if labelNode and labelNode.Parent and labelBefore == true and labelNode.Visible == false then
                    return true, "input event dispatched; completion and label transitions observed"
                end
                return true, "input event dispatched; completion transition observed"
            end
            if labelNode and labelNode.Parent and labelBefore == true and labelNode.Visible == false then
                labelTransitionObserved = true
            end
            RunService.Heartbeat:Wait()
        end
        if labelTransitionObserved then
            return false, "input event dispatched; only supporting label transition observed"
        end
        return false, "input event dispatched; completion transition timeout"
    end)
    restoreLycolesUi(suspended)

    if not ok then
        gameplayFailures = gameplayFailures + 1
        return false, "controlled claim trial error: " .. tostring(activated)
    end
    if activated then
        gameplaySuccesses = gameplaySuccesses + 1
        return true, tostring(message)
    end
    gameplayFailures = gameplayFailures + 1
    return false, tostring(message)
end

local function activateGameplayAction(action)
    gameplayAttempts = gameplayAttempts + 1
    if not action or type(action.path) ~= "string" or action.path == "" then
        gameplayFailures = gameplayFailures + 1
        return false, "no actionable path"
    end
    if action.kind == "prompt" then
        local prompt, err = resolvePath(action.path)
        if not prompt or not prompt:IsA("ProximityPrompt") then
            gameplayFailures = gameplayFailures + 1
            return false, "prompt resolve failed: " .. tostring(err)
        end
        if type(fireproximityprompt) ~= "function" then
            gameplayFailures = gameplayFailures + 1
            return false, "fireproximityprompt unavailable"
        end
        local ok, activateError = pcall(function() fireproximityprompt(prompt) end)
        if ok then
            gameplaySuccesses = gameplaySuccesses + 1
            return true, "prompt activated"
        end
        gameplayFailures = gameplayFailures + 1
        return false, "prompt activation failed: " .. tostring(activateError)
    end
    local button, err = resolvePath(action.path)
    if not button or not button:IsA("GuiButton") then
        gameplayFailures = gameplayFailures + 1
        return false, "GUI resolve failed: " .. tostring(err or "not GuiButton")
    end
    local ok, mode = tryVirtualClick(button)
    if ok then
        gameplaySuccesses = gameplaySuccesses + 1
        return true, "activated via " .. mode
    end
    gameplayFailures = gameplayFailures + 1
    return false, "activation unavailable"
end

local function show(title,lines)
    if not alive then return end
    output.Text=title.."\\n\\n"..table.concat(lines,"\\n")
end
local settingsCycle = 0
local function button(name,callback)
    local b=Instance.new("TextButton",tabs)
    b.Size=UDim2.new(0.19,-4,1,0)
    b.Text=name
    b.TextSize=12
    b.BackgroundColor3=Color3.fromRGB(48,78,103)
    b.TextColor3=Color3.new(1,1,1)
    tabButtons[#tabButtons+1]=b
    table.insert(connections,b.MouseButton1Click:Connect(function()
        local ok,err=pcall(callback)
        if not ok then show(name.." failed",{tostring(err)}) end
    end))
end
button("Overview",function()
    local lines={
        "Requested capability supplied: "..tostring(#REQUEST_STATUS_LINES > 0),
        "Loadout evidence available: "..tostring(LOADOUT_SNAPSHOT_COUNT > 0 or #LOADOUT_HINT_PATHS > 0),
        "Movement evidence available: "..tostring(MOVEMENT_HINT_DATA.movementEvidenceAvailable),
        "Action targets: "..tostring(#ACTION_TARGETS),
        "Theme preset: "..activeThemeName,
        "",
    }
    local stats=player:FindFirstChild("leaderstats")
    if stats then
        for _,v in ipairs(stats:GetChildren()) do
            if v:IsA("ValueBase") and (type(v.Value)=="number" or type(v.Value)=="boolean") then
                lines[#lines+1]=v.Name..": "..tostring(v.Value)
            end
            if #lines>=18 then break end
        end
    end
    if #lines<=6 then lines[#lines+1]="No replicated numeric stats found." end
    show("Overview",lines)
end)
button("Loadout",function()
    if LOADOUT_SNAPSHOT_COUNT <= 0 and #LOADOUT_HINT_PATHS == 0 then
        show("Loadout telemetry unavailable",{
            "No loadout runtime evidence was captured in this dataset.",
            "Capture targeted loadout observation and replay this generation run.",
        })
        return
    end
    ensureLoadoutLoop()
    loadoutModule.enabled = not loadoutModule.enabled
    if loadoutModule.enabled then
        rebuildLoadoutSnapshotLines()
    end
    local lines = {
        "Loadout module enabled: " .. tostring(loadoutModule.enabled),
        "Toggle keybind: " .. tostring(loadoutModule.keybind.Name),
        "Refresh seconds: " .. string.format("%.2f", loadoutModule.refreshSeconds),
        "",
    }
    for _,line in ipairs(loadoutModule.lastSnapshotLines) do
        lines[#lines + 1] = line
    end
    show("Loadout telemetry", lines)
end)
button("Movement",function()
    ensureMovementLoop()
    movementModule.enabled = not movementModule.enabled
    if movementModule.enabled then
        rebuildMovementSnapshotLines()
    end
    local lines = {
        "Movement module enabled: " .. tostring(movementModule.enabled),
        "Toggle keybind: " .. tostring(movementModule.keybind.Name),
        "Refresh seconds: " .. string.format("%.2f", movementModule.refreshSeconds),
        "",
    }
    for _,line in ipairs(movementModule.lastSnapshotLines) do
        lines[#lines + 1] = line
    end
    show("Movement telemetry", lines)
end)
button("Settings",function()
    settingsCycle = settingsCycle + 1
    local loadIndex = ((settingsCycle - 1) % #LOADOUT_REFRESH_OPTIONS) + 1
    local moveIndex = ((settingsCycle - 1) % #MOVEMENT_REFRESH_OPTIONS) + 1
    loadoutModule.refreshSeconds = LOADOUT_REFRESH_OPTIONS[loadIndex]
    movementModule.refreshSeconds = MOVEMENT_REFRESH_OPTIONS[moveIndex]
    loadoutModule.includeBackpack = not loadoutModule.includeBackpack
    loadoutModule.keybind = cycleKeybind(LOADOUT_KEYBIND_OPTIONS, loadoutModule.keybind)
    movementModule.keybind = cycleKeybind(MOVEMENT_KEYBIND_OPTIONS, movementModule.keybind)
    local nextTheme = cycleTheme()
    rebuildLoadoutSnapshotLines()
    rebuildMovementSnapshotLines()
    show("Settings", {
        "Theme preset: " .. nextTheme,
        "Loadout refresh seconds: " .. string.format("%.2f", loadoutModule.refreshSeconds),
        "Movement refresh seconds: " .. string.format("%.2f", movementModule.refreshSeconds),
        "Loadout keybind: " .. tostring(loadoutModule.keybind.Name),
        "Movement keybind: " .. tostring(movementModule.keybind.Name),
        "Backpack visibility in loadout panel: " .. tostring(loadoutModule.includeBackpack),
        "Graphite / Slate / Silver / Custom theme compatibility enabled.",
    })
end)
button("Diagnostics",function()
    local candidates=FEATURE_NAMES
    local provenance=SOURCE_PROVENANCE_LINES
    local gameplay=GAMEPLAY_UNDERSTANDING_LINES
    local generation=GENERATION_READINESS_LINES
    local request=REQUEST_STATUS_LINES
    local activationSummary="No actionable gameplay target"
    if CONTROLLED_REQUEST.enabled == true then
        local ok,message=runControlledClaimTrial()
        activationSummary=tostring(ok).." | "..tostring(message)
    else
        local action=selectedGameplayAction()
        if action and action.path ~= "" then
            local ok,message=activateGameplayAction(action)
            activationSummary=tostring(ok).." | "..tostring(message)
            selectedActionIndex=(selectedActionIndex % #ACTION_TARGETS)+1
        end
    end
    local lines={
        "Gameplay action run: "..activationSummary,
        "Actions attempted: "..tostring(gameplayAttempts).." | success: "..tostring(gameplaySuccesses).." | failure: "..tostring(gameplayFailures),
        "Evidence-backed action targets: "..tostring(#ACTION_TARGETS),
        "Controlled mode: "..tostring(CONTROLLED_REQUEST.mode).." | confidence: "..tostring(CONTROLLED_REQUEST.confidence),
        ""}
    for _,line in ipairs(CONTROLLED_STATUS_LINES) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for _,line in ipairs(request) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for _,line in ipairs(generation) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for i=1,math.min(6,#ACTION_TARGETS) do
        local item=ACTION_TARGETS[i]
        lines[#lines+1]="Target "..tostring(i)..": "..item.label.." ["..item.kind.."] confidence="..tostring(item.confidence).." provenance="..tostring(item.provenance)
    end
    lines[#lines+1]=""
    for _,line in ipairs(gameplay) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for _,line in ipairs(provenance) do lines[#lines+1]=line end
    lines[#lines+1]=""
    for i=1,math.min(6,#candidates) do lines[#lines+1]=candidates[i] end
    show("Diagnostics",lines)
end)
applyTheme(activeThemeName)
local dragging,dragInput,dragStart,startPos=false,nil,nil,nil
table.insert(connections,heading.InputBegan:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 then
        dragging=true;dragStart=input.Position;startPos=frame.Position
    end
end))
table.insert(connections,heading.InputEnded:Connect(function(input)
    if input.UserInputType==Enum.UserInputType.MouseButton1 then dragging=false end
end))
table.insert(connections,UserInputService.InputChanged:Connect(function(input)
    if dragging and input.UserInputType==Enum.UserInputType.MouseMovement then
        local d=input.Position-dragStart
        frame.Position=UDim2.new(startPos.X.Scale,startPos.X.Offset+d.X,startPos.Y.Scale,startPos.Y.Offset+d.Y)
    end
end))
table.insert(connections,UserInputService.InputBegan:Connect(function(input, gameProcessed)
    if gameProcessed or not alive then
        return
    end
    if input.KeyCode == loadoutModule.keybind then
        if LOADOUT_SNAPSHOT_COUNT <= 0 and #LOADOUT_HINT_PATHS == 0 then
            show("Loadout telemetry unavailable", {
                "No loadout runtime evidence was captured in this dataset.",
                "Capture targeted loadout observation and replay this generation run.",
            })
            return
        end
        ensureLoadoutLoop()
        loadoutModule.enabled = not loadoutModule.enabled
        if loadoutModule.enabled then
            rebuildLoadoutSnapshotLines()
        end
        local lines = {
            "Loadout module enabled: " .. tostring(loadoutModule.enabled),
            "Refresh seconds: " .. string.format("%.2f", loadoutModule.refreshSeconds),
            "Include backpack tools: " .. tostring(loadoutModule.includeBackpack),
            "",
        }
        for _,line in ipairs(loadoutModule.lastSnapshotLines) do
            lines[#lines + 1] = line
        end
        show("Loadout telemetry", lines)
        return
    end
    if input.KeyCode == movementModule.keybind then
        ensureMovementLoop()
        movementModule.enabled = not movementModule.enabled
        if movementModule.enabled then
            rebuildMovementSnapshotLines()
        end
        local lines = {
            "Movement module enabled: " .. tostring(movementModule.enabled),
            "Refresh seconds: " .. string.format("%.2f", movementModule.refreshSeconds),
            "",
        }
        for _,line in ipairs(movementModule.lastSnapshotLines) do
            lines[#lines + 1] = line
        end
        show("Movement telemetry", lines)
    end
end))
_G.LycolesGeneratedClose=function()
    if not alive then return end
    alive=false
    for _,c in ipairs(connections) do pcall(function() c:Disconnect() end) end
    gui:Destroy()
    _G.LycolesGeneratedClose=nil
end
table.insert(connections,close.MouseButton1Click:Connect(_G.LycolesGeneratedClose))
show("Ready",{
    "Validated scan inventory loaded.",
    "Unified categories: Overview, Loadout, Movement, Settings, Diagnostics.",
    "Loadout keybind: " .. tostring(loadoutModule.keybind.Name) .. ".",
    "Movement keybind: " .. tostring(movementModule.keybind.Name) .. ".",
    "Gameplay automation and outcomes remain unverified.",
})
""".replace("PLACE_ID",str(place)).replace(
        "ACTION_TARGETS_DATA", "{\n"+action_target_list+"\n}").replace(
        "CONTROLLED_REQUEST_DATA", controlled_request_data).replace(
        "CONTROLLED_STATUS_LINES_DATA", "{\n"+status_list+"\n}").replace(
        "LOADOUT_HINT_PATHS_DATA", "{\n"+loadout_hint_list+"\n}").replace(
        "LOADOUT_SNAPSHOT_COUNT_DATA", str(int(loadout_snapshot_count))).replace(
        "MOVEMENT_HINT_DATA_TABLE", movement_hint_data_text).replace(
        "FEATURE_NAMES", "{\n"+feature_list+"\n}").replace(
        "SOURCE_PROVENANCE_LINES", "{\n"+provenance_list+"\n}").replace(
        "GAMEPLAY_UNDERSTANDING_LINES", "{\n"+gameplay_list+"\n}").replace(
        "GENERATION_READINESS_LINES", "{\n"+generation_list+"\n}").replace(
        "REQUEST_STATUS_LINES", "{\n"+request_list+"\n}")

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("--output",default="build/generated")
    args=parser.parse_args()
    try:
        raw=pathlib.Path(args.plan).read_bytes()
        if len(raw)>5_000_000: raise ValueError("Plan too large")
        plan=json.loads(raw)
        understanding=load_local_module("lycoles_gameplay_understanding",
                                        "understand_gameplay.py").analyze(plan)
        discovery_builder=load_local_module("lycoles_action_discovery",
                                             "discover_action_capabilities.py")
        action_discovery=discovery_builder.analyze(plan)
        workflow_planner=load_local_module("lycoles_generated_workflows",
                                           "plan_generated_workflows.py")
        generated_workflows=workflow_planner.plan(plan,action_discovery)
        guided_workflow_builder=load_local_module("lycoles_guided_workflow",
                                                  "generate_guided_workflow.py")
        guided_workflow_lua=guided_workflow_builder.render(generated_workflows)

        guided_workflow_candidates=guided_workflow_builder.validate(generated_workflows)
        guided_workflow_candidate=(guided_workflow_candidates[0]
            if guided_workflow_candidates else None)
        guided_workflow_candidate_id=(guided_workflow_candidate["id"]
            if guided_workflow_candidate else None)

        readiness_builder=load_local_module("lycoles_generation_readiness",
                                             "assess_generation_readiness.py")
        generation_readiness=readiness_builder.assess(
            plan,understanding,action_discovery,generated_workflows)
        utility_lua=render(plan,understanding,generation_readiness)
        prompt_generator=load_local_module("lycoles_prompt_interactions","generate_prompt_interactions.py")
        prompt_interactions_lua=prompt_generator.render(action_discovery)
        prompt_trial_generated=action_discovery["promptInteractions"]["trialReadyTargets"]>0
        tool_trial_generated=action_discovery["toolInteractions"]["generationReadyTargets"]>0
        gui_trial_generated=action_discovery["guiInteractions"]["generationReadyTargets"]>0
        egg_trial_generated=action_discovery["eggHatching"]["automaticSingleTrialReady"] is True

        admin_generator=load_local_module("lycoles_admin_commands",
                                          "generate_admin_commands.py")
        admin_lua=admin_generator.render(
            plan["integrity"]["placeId"],understanding,generation_readiness)
        lua=(utility_lua+"\n"+(prompt_interactions_lua+"\n" if prompt_interactions_lua else "")
            +(guided_workflow_lua+"\n" if guided_workflow_lua else "")+admin_lua)
        result_builder=load_local_module("lycoles_generated_result","generated_result.py")
        generated_result=result_builder.build(plan["integrity"]["placeId"],
            plan["integrity"].get("scanId","standalone"),lua,plan.get("requestedCapability"),
            {"placeGuard":True,"note":"Generator structural contract; not live runtime validation"},
            list(ALLOWED_FEATURES)+["Admin Commands"]+
                (["Prompt Interactions"] if prompt_trial_generated else [])+
                (["Tool Activation Trial"] if tool_trial_generated else [])+
                (["Guided GUI Trial"] if gui_trial_generated else [])+
                (["Linked Workflow Trial"] if guided_workflow_lua else []),
            generation_readiness)

        module_contract=build_generated_module_contract(plan,generation_readiness)
        generation_readiness_bytes=(json.dumps(
            generation_readiness,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
        module_contract_bytes=(json.dumps(
            module_contract,indent=2,sort_keys=True,ensure_ascii=False)+"\n").encode("utf-8")
        out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
        if guided_workflow_lua is None:
            (out/"LycolesGuidedWorkflow.lua").unlink(missing_ok=True)

        script=out/"LycolesGeneratedUtility.lua"
        script.write_text(lua,encoding="utf-8")
        (out/"LycolesAdminCommands.lua").write_text(admin_lua,encoding="utf-8")
        (out/"gameplay-understanding.json").write_text(
            json.dumps(understanding,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        (out/"action-capabilities.json").write_text(json.dumps(
            action_discovery,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        (out/"generated-workflow-plan.json").write_text(json.dumps(
            generated_workflows,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        if guided_workflow_lua is not None:
            (out/"LycolesGuidedWorkflow.lua").write_text(
                guided_workflow_lua,encoding="utf-8")

        (out/"generation-readiness.json").write_bytes(generation_readiness_bytes)
        (out/"generated-module-contract.json").write_bytes(module_contract_bytes)
        if prompt_interactions_lua is not None:
            (out/"LycolesPromptInteractions.lua").write_text(prompt_interactions_lua,encoding="utf-8")

        result_name="Lycoles-"+str(plan["integrity"]["placeId"])+"-generated-result.json"
        (out/result_name).write_text(json.dumps(
            generated_result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")

        manifest={"schemaVersion":"9.0","placeId":plan["integrity"]["placeId"],
          "sourcePlanSHA256":hashlib.sha256(raw).hexdigest(),
          "generatedLuaSHA256":hashlib.sha256(lua.encode()).hexdigest(),
          "implementedFeatures":list(ALLOWED_FEATURES)+["Admin Commands"]+
            (["Prompt Interactions"] if prompt_trial_generated else [])+
            (["Tool Activation Trial"] if tool_trial_generated else [])+
            (["Guided GUI Trial"] if gui_trial_generated else [])+
            (["Linked Workflow Trial"] if guided_workflow_lua else []),
          "adminCommands":list(admin_generator.COMMANDS),
          "generatedResult":{"artifact":result_name,"schemaVersion":generated_result["schemaVersion"],
            "displayOnly":True,"executionAuthorized":False},
          "actionCapabilities":{"artifact":"action-capabilities.json",
            "schemaVersion":action_discovery["schemaVersion"],
            "promptTargets":len(action_discovery["promptInteractions"]["targets"]),
            "trialReadyPromptTargets":action_discovery["promptInteractions"]["trialReadyTargets"],
            "toolTargets":len(action_discovery["toolInteractions"]["targets"]),
            "generationReadyToolTargets":action_discovery["toolInteractions"]["generationReadyTargets"],
            "guiTargets":len(action_discovery["guiInteractions"]["targets"]),
            "generationReadyGuiTargets":action_discovery["guiInteractions"]["generationReadyTargets"],
            "correlatedEggTargets":action_discovery["eggHatching"]["correlatedTargets"]},
          "generatedWorkflowPlan":{"artifact":"generated-workflow-plan.json",
            "schemaVersion":generated_workflows["schemaVersion"],
            "summary":generated_workflows["summary"],
            "temporalAdjacency":{field:generated_workflows["temporalAdjacency"][field]
                for field in ("timedEvents","unlinkedAdjacentPairs","usedForWorkflowLinkage")},
            "guiRevealFollowups":{field:generated_workflows["guiRevealFollowups"][field]
                for field in ("candidateCount","usedForWorkflowLinkage","causalityProven")},
            "automaticallyExecutable":
                generated_workflows["summary"]["automaticallyExecutableWorkflows"]>0,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
          "guidedWorkflowTrial":{"artifact":"LycolesGuidedWorkflow.lua" if guided_workflow_lua else None,
            "integratedInGeneratedUtility":guided_workflow_lua is not None,
            "candidateId":guided_workflow_candidate_id,
            "executionMode":guided_workflow_candidate.get("executionMode")
                if guided_workflow_candidate else None,
            "feedbackSchema":"115.guided-workflow-feedback.1" if guided_workflow_lua else None,
            "feedbackWorkflowPlanSHA256":guided_workflow_builder.digest(generated_workflows)
                if guided_workflow_lua else None,
            "generated":guided_workflow_lua is not None,
            "automaticActivation":guided_workflow_candidate.get("automaticallyExecutable",False)
                if guided_workflow_candidate else False,
            "manualActivationRequired":guided_workflow_candidate.get(
                "manualGuiActivationRequired",False) if guided_workflow_candidate else False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
          "promptInteractionTrial":{"artifact":"LycolesPromptInteractions.lua" if prompt_trial_generated else None,
            "generated":prompt_trial_generated,"automaticMovement":prompt_trial_generated,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
          "toolActivationTrial":{"artifact":"LycolesPromptInteractions.lua" if tool_trial_generated else None,
            "generated":tool_trial_generated,"officialActivation":tool_trial_generated,
            "boundedEquip":tool_trial_generated,"automaticMovement":False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
          "guidedGuiTrial":{"artifact":"LycolesPromptInteractions.lua" if gui_trial_generated else None,
            "generated":gui_trial_generated,"automaticActivation":False,
            "manualActivationRequired":gui_trial_generated,
            "exactControlHighlighting":gui_trial_generated,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False},
          "eggAutofarmTrial":{"artifact":"LycolesPromptInteractions.lua" if egg_trial_generated else None,
            "generated":egg_trial_generated,"runtimeVerified":False,
            "gameplayVerified":False,"multiHatchReady":action_discovery["eggHatching"]["multiHatchTrialReady"],
            "compatibilityAlias":True},
          "gameplayUnderstanding":{"artifact":"gameplay-understanding.json",
            "schemaVersion":understanding["schemaVersion"],"summary":understanding["summary"]},
          "generationReadiness":{"artifact":"generation-readiness.json",
            "schemaVersion":generation_readiness["schemaVersion"],
            "sha256":hashlib.sha256(generation_readiness_bytes).hexdigest(),
            "summary":generation_readiness["summary"],
            "request":generation_readiness["request"],
            "requestFeatureReadiness":generation_readiness["requestFeatureReadiness"]},
          "generatedModuleContract":{"artifact":"generated-module-contract.json",
            "schemaVersion":module_contract["schemaVersion"],
            "sha256":hashlib.sha256(module_contract_bytes).hexdigest(),
            "modules":module_contract["modules"],
            "claims":module_contract["claims"]},
          "gameplayFeaturesImplemented":[],"liveTested":False,
          "sourceFeatureCandidates":len(plan["features"]),
          "releaseStatus":"GENERATED_PROMPT_TRIAL_STATIC_CHECKED_NOT_LIVE_TESTED"
            if prompt_interactions_lua else "CLIENT_DIAGNOSTIC_ONLY_UNTESTED"}
        (out/"release-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
        print("Generated:",script)
        return 0
    except (OSError,ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
        print("GENERATION BLOCKED:",exc,file=sys.stderr);return 2
if __name__=="__main__":sys.exit(main())
