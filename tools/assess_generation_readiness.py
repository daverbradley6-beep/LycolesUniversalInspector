#!/usr/bin/env python3
"""Synthesize evidence-bounded generation readiness from validated artifacts."""
import argparse
import importlib.util
import json
import pathlib
import re
import sys

SCHEMA_VERSION="113.generation-readiness.1"
_REQUEST_FEATURE_SCHEMA="113.request-feature-readiness.1"
_FALSE_CLAIMS={
    "sourceAuthenticityVerified":False,"causalityProven":False,
    "serverAuthorityVerified":False,"runtimeVerified":False,
    "gameplayVerified":False,"actionOutcomesVerified":False,
}
_FEATURE_EVIDENCE_CLASSIFICATION={
    "client-outcome-observed":"temporal-client-outcome-correlation",
    "observable-outcome-candidate-unverified":"observable-outcome-candidate-unverified",
    "interaction-observed":"interaction-observed-no-outcome-contract",
    "discovered":"discovered-no-interaction-evidence",
}

def _load(filename,name):
    source=pathlib.Path(__file__).with_name(filename)
    spec=importlib.util.spec_from_file_location(name,source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

_STOP_WORDS={"a","an","and","auto","automate","automated","automatic",
    "automatically","complete","do","for","from","in","of","observed","please",
    "the","to","with","workflow","flow"}
_TOKEN_ALIASES={
    "attacking":"attack","attacked":"attack","buying":"buy",
    "claiming":"claim","claimed":"claim","collecting":"collect",
    "collected":"collect","fighting":"fight","hatching":"hatch",
    "hatched":"hatch","purchasing":"purchase","purchased":"purchase",
    "rebirthing":"rebirth","selling":"sell","sold":"sell",
    "training":"train","trained":"train","traveling":"travel",
    "travelled":"travel","travelling":"travel","upgrading":"upgrade",
    "upgraded":"upgrade",
}
_COMBAT_REQUEST_TOKENS={"combat","attack","fight","fire","reload","weapon",
    "gun","rifle","pistol","shotgun","sniper","ammo","arsenal","switch","enemy"}
_COMBAT_INPUT_ACTION_TOKENS={"fire","reload","switch","equip","unequip",
    "aim-adjust","combat-animation"}


def _token_forms(token):
    forms={token}
    if len(token)>4 and token.endswith("ies"):
        forms.add(token[:-3]+"y")
    if len(token)>4 and token.endswith("es"):
        forms.add(token[:-2])
    if len(token)>4 and token.endswith("s") and not token.endswith("ss"):
        forms.add(token[:-1])
    if len(token)>5 and token.endswith("ing"):
        forms.add(token[:-3])
    if len(token)>4 and token.endswith("ed"):
        forms.add(token[:-2])
    return forms


def _tokens(value):
    if not isinstance(value,str):return set()
    result=set()
    for token in re.findall(r"[a-z0-9]+",value.casefold())[:128]:
        for form in _token_forms(token):
            canonical=_TOKEN_ALIASES.get(form,form)
            if len(canonical)>=2 and canonical not in _STOP_WORDS:
                result.add(canonical)
    return result

def _validate_sources(plan,gameplay,actions):
    if not isinstance(plan,dict):raise ValueError("compiled plan must be an object")
    expected_gameplay=_load("understand_gameplay.py","readiness_gameplay").analyze(plan)
    if gameplay!=expected_gameplay:raise ValueError("gameplay understanding does not match compiled plan")
    expected_actions=_load("discover_action_capabilities.py","readiness_actions").analyze(plan)
    if actions!=expected_actions:raise ValueError("action capabilities do not match compiled plan")
    if any(actions.get("claims",{}).get(key) is not value for key,value in _FALSE_CLAIMS.items()):
        raise ValueError("action capabilities contain unsupported claims")
    return plan["integrity"],plan.get("requestedCapability")

def _selected_prompt(actions):
    prompts=actions["promptInteractions"]
    selected=prompts.get("selectedTargetPath")
    if prompts.get("trialReadyTargets",0)<=0 or not isinstance(selected,str):return None
    matches=[item for item in prompts.get("targets",[])
             if item.get("path")==selected and item.get("trialGenerationReady") is True]
    if len(matches)!=1:raise ValueError("selected prompt target is inconsistent")
    target=matches[0]
    outcome=target.get("selectedOutcome")
    if (not isinstance(outcome,dict)
            or outcome.get("selection",{}).get("selectedForTrial") is not True):
        raise ValueError("selected prompt outcome is inconsistent")
    return target

def _selected_tool(actions):
    tools=actions.get("toolInteractions",{})
    selected=tools.get("selectedTargetPath")
    if tools.get("generationReadyTargets",0)<=0 or not isinstance(selected,str):return None
    matches=[item for item in tools.get("targets",[])
             if item.get("path")==selected and item.get("trialGenerationReady") is True]
    if len(matches)!=1:raise ValueError("selected Tool target is inconsistent")
    target=matches[0];outcome=target.get("selectedOutcome")
    if (target.get("activationContractReady") is not True
            or target.get("replayContractAvailable") is not True
            or not isinstance(outcome,dict)
            or outcome.get("selection",{}).get("selectedForTrial") is not True):
        raise ValueError("selected Tool outcome is inconsistent")
    return target


def _selected_gui(actions):
    gui=actions.get("guiInteractions",{})
    selected=gui.get("selectedTargetPath")
    if gui.get("generationReadyTargets",0)<=0 or not isinstance(selected,str):return None
    matches=[item for item in gui.get("targets",[])
             if item.get("path")==selected and item.get("trialGenerationReady") is True]
    if len(matches)!=1:raise ValueError("selected GUI target is inconsistent")
    target=matches[0];outcome=target.get("selectedOutcome")
    if (target.get("guidedActivationContractReady") is not True
            or target.get("automaticActivationAvailable") is not False
            or target.get("replayContractAvailable") is not False
            or not isinstance(outcome,dict)
            or outcome.get("selection",{}).get("selectedForTrial") is not True):
        raise ValueError("selected GUI outcome is inconsistent")
    return target



def _is_egg_target(actions,target):
    if target is None:return False
    return any(item.get("path")==target["path"]
               for item in actions["eggHatching"].get("targets",[]))



def _capability_baseline(target):
    value=target.get("baselineEvidence")
    if not isinstance(value,dict):
        raise ValueError("selected action target lacks baseline evidence")
    fields=("events","preActivationEvents","activationCallbackEvents","unknownTimingEvents")
    if (any(type(value.get(field)) is not int or not 0<=value[field]<=2_000 for field in fields)
            or value["events"]<1 or value["events"]!=sum(value[field] for field in fields[1:])
            or type(value.get("possibleSynchronousLoss")) is not bool
            or value["possibleSynchronousLoss"] is not bool(
                value["activationCallbackEvents"] or value["unknownTimingEvents"])):
        raise ValueError("selected action target has malformed baseline evidence")
    if value["unknownTimingEvents"]:
        classification="timing-unknown"
    elif value["activationCallbackEvents"]:
        classification="callback-fallback-present"
    else:
        classification="pre-activation-baseline-available-for-all-observations"
    return {field:value[field] for field in fields}|{
        "possibleSynchronousLoss":value["possibleSynchronousLoss"],
        "classification":classification,"readinessImpact":"limitations-only",
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False}


def _workflow_baseline(candidate):
    steps=candidate.get("steps",[]);timings=[]
    for step in steps:
        baseline=step.get("observationBaseline") if isinstance(step,dict) else None
        if (not isinstance(baseline,dict)
                or baseline.get("timing") not in ("pre-activation","activation-callback","unknown")
                or type(baseline.get("preActivationBaselineAvailable")) is not bool
                or baseline["preActivationBaselineAvailable"] is not (
                    baseline["timing"]=="pre-activation")
                or type(baseline.get("possibleSynchronousLoss")) is not bool
                or baseline["possibleSynchronousLoss"] is not (
                    baseline["timing"]!="pre-activation")):
            raise ValueError("generated workflow has malformed baseline evidence")
        timings.append(baseline["timing"])
    pre=timings.count("pre-activation");callback=timings.count("activation-callback")
    unknown=timings.count("unknown")
    return {"steps":len(steps),"preActivationSteps":pre,
        "activationCallbackSteps":callback,"unknownTimingSteps":unknown,
        "possibleSynchronousLoss":bool(callback or unknown),
        "classification":("timing-unknown" if unknown else
            ("callback-fallback-present" if callback else
             "pre-activation-baseline-available-for-all-steps")),
        "readinessImpact":"limitations-only","causalityProven":False,
        "runtimeVerified":False,"gameplayVerified":False}


def _generated_capability(target,is_egg):
    commands=["interaction","interactionstart","interactionstop","interactions"]
    if is_egg:commands.extend(["egg","eggmode","eggstart","eggstop","eggs"])
    outcome=target["selectedOutcome"]
    return {"id":"prompt-interaction-trial","kind":"proximity-prompt-trial",
        "targetPath":target["path"],"targetLabel":target["label"],
        "targetFeature":target.get("featureCandidate"),
        "selectedOutcomeKey":outcome["key"],"expectedChange":outcome["change"],
        "observationBaseline":_capability_baseline(target),
        "commands":commands,"automaticMovement":True,"boundedRepeat":True,
        "operatorStartRequired":True,"failureLimit":3,"attemptLimit":25,
        "classification":"generated-evidence-bounded-trial",
        "fullGameplayMechanicImplemented":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}

def _generated_tool_capability(target):
    outcome=target["selectedOutcome"]
    return {"id":"tool-activation-trial","kind":"official-tool-activation-trial",
        "targetPath":target["path"],"targetLabel":target["label"],
        "targetFeature":target.get("featureCandidate"),
        "selectedOutcomeKey":outcome["key"],"expectedChange":outcome["change"],
        "observationBaseline":_capability_baseline(target),
        "commands":["interaction","interactionstart","interactionstop","interactions"],
        "officialActivation":True,"boundedEquip":True,"automaticMovement":False,
        "boundedRepeat":True,"operatorStartRequired":True,"failureLimit":3,"attemptLimit":25,
        "classification":"generated-evidence-bounded-trial",
        "fullGameplayMechanicImplemented":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}


def _generated_gui_capability(target):
    outcome=target["selectedOutcome"]
    return {"id":"guided-gui-interaction-trial","kind":"guided-gui-activation-trial",
        "targetPath":target["path"],"targetLabel":target["label"],
        "targetFeature":target.get("featureCandidate"),
        "selectedOutcomeKey":outcome["key"],"expectedChange":outcome["change"],
        "observationBaseline":_capability_baseline(target),
        "commands":["interaction","interactionstart","interactionstop","interactions"],
        "automaticActivation":False,"manualActivationRequired":True,
        "exactControlHighlighting":True,"automaticMovement":False,
        "boundedRepeat":True,"operatorStartRequired":True,"failureLimit":3,"attemptLimit":25,
        "classification":"generated-evidence-bounded-guided-trial",
        "fullGameplayMechanicImplemented":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}


def _selected_workflow(workflow_plan,plan,actions):
    if workflow_plan is None:return None
    expected=_load("plan_generated_workflows.py","readiness_workflow_planner").plan(plan,actions)
    if workflow_plan!=expected:
        raise ValueError("generated workflow plan does not match compiled evidence")
    candidates=_load("generate_guided_workflow.py","readiness_workflow_generator").validate(
        workflow_plan)
    return candidates[0] if candidates else None


def _generated_workflow_capability(candidate):
    steps=candidate["steps"]
    return {"id":"linked-gameplay-workflow-trial","kind":"mixed-action-workflow-trial",
        "candidateId":candidate["id"],"transactionId":candidate["transactionId"],
        "executionMode":candidate.get("executionMode","mixed-guided"),
        "stepCount":len(steps),"stepKinds":[step["kind"] for step in steps],
        "observationBaseline":_workflow_baseline(candidate),
        "targetPaths":[step["targetPath"] for step in steps],
        "targetFeatures":sorted({step.get("targetFeature") for step in steps
            if isinstance(step.get("targetFeature"),str)}),
        "requestMatchedTerms":candidate.get("selection",{}).get("matchedTerms",[]),
        "requestMatchScore":candidate.get("selection",{}).get("requestScore",0),
        "manualGuiActivationRequired":candidate["manualGuiActivationRequired"],
        "automaticallyExecutable":candidate["automaticallyExecutable"],
        "operatorStartRequired":True,"stopOnFirstUnobservedOutcome":True,
        "classification":"generated-evidence-bounded-workflow-trial",
        "fullGameplayMechanicImplemented":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}


def _workflow_request_aligned(candidate,request):
    selection=candidate.get("selection")
    if isinstance(selection,dict):return selection.get("requestAligned") is True
    requested=_tokens(request)
    if not requested:return False
    evidence=set()
    for step in candidate["steps"]:
        for value in (step.get("targetLabel"),step.get("targetPath"),
                step.get("targetFeature"),step.get("actionCandidate")):
            evidence.update(_tokens(value))
    return bool(requested&evidence)


def _workflow_selection(workflow_plan,selected):
    if workflow_plan is None:
        return {"available":False,"totalCandidates":0,"shownCandidates":0,
            "omittedCandidates":0,"selectedCandidateId":None,"candidates":[]}
    candidates=workflow_plan.get("workflowCandidates",[])
    selected_id=selected.get("id") if selected else None
    selected_score=selected.get("selection",{}).get("requestScore",0) if selected else 0
    selected_automatic=selected.get("automaticallyExecutable",False) if selected else False
    shown=candidates[:20]
    if selected and all(item.get("id")!=selected_id for item in shown):
        shown=(shown[:19]+[selected]) if shown else [selected]
    values=[]
    for item in shown:
        score=item.get("selection",{}).get("requestScore",0)
        if item.get("id")==selected_id:reason="selected-highest-ranked-execution-ready-candidate"
        elif item.get("executionReady") is not True:reason="not-execution-ready"
        elif score<selected_score:reason="lower-request-evidence-score"
        elif selected_automatic and item.get("automaticallyExecutable") is not True:
            reason="more-user-involvement-tiebreak"
        else:reason="stable-identity-tiebreak"
        values.append({"candidateId":item["id"],"requestScore":score,
            "matchedTerms":item.get("selection",{}).get("matchedTerms",[]),
            "executionMode":item.get("executionMode","review-only"),
            "executionReady":item.get("executionReady") is True,
            "selected":item.get("id")==selected_id,"selectionReason":reason})
    summary=workflow_plan["summary"]
    diagnostic_fields=("transactionGroups","linkedTransactions","singletonTransactions",
        "multiEventTransactions","transactionsWithInsufficientGenerationReadySteps",
        "partiallyMappedTransactions","transactionsOverStepBound","workflowCandidates",
        "unlinkedEvents","executionReadyWorkflows")
    explicit_recordings=summary.get("explicitRecordingTransactions",0)
    review_only_linked=summary.get("reviewOnlyLinkedCandidates",0)
    request_aligned_review_only=summary.get("requestAlignedReviewOnlyLinkedCandidates",0)
    selected_review_only=summary.get("selectedReviewOnlyCandidateId")
    planning_status=summary.get("planningStatus")
    review_only_ids=[item.get("id") for item in candidates
        if item.get("reviewEvidenceType")=="linked-gui-transition-only"]
    review_only_ids=[item for item in review_only_ids if isinstance(item,str)]
    expected_request_aligned_review_only=sum(item.get("reviewEvidenceType")==
        "linked-gui-transition-only" and bool(item.get("selection",{}).get("requestAligned"))
        for item in candidates)
    if (planning_status not in ("execution-ready-candidates","review-only-candidates",
            "no-multi-step-generation-ready-contract","singleton-transactions-only",
            "no-explicit-linkage","no-interaction-events")
            or any(type(summary.get(field)) is not int or not 0<=summary[field]<=10_000_000
                for field in diagnostic_fields)
            or type(explicit_recordings) is not int
            or type(review_only_linked) is not int
            or type(request_aligned_review_only) is not int
            or not 0<=explicit_recordings<=summary.get("transactionGroups",-1)
            or not 0<=review_only_linked<=summary.get("workflowCandidates",-1)
            or not 0<=request_aligned_review_only<=review_only_linked
            or review_only_linked!=len(review_only_ids)
            or request_aligned_review_only!=expected_request_aligned_review_only
            or selected_review_only is not None and (not isinstance(selected_review_only,str)
                or not 1<=len(selected_review_only)<=80)
            or review_only_linked==0 and selected_review_only is not None
            or review_only_linked>0 and selected_review_only not in review_only_ids
            or summary["transactionGroups"]!=summary["singletonTransactions"]+summary[
                "multiEventTransactions"]
            or summary["linkedTransactions"]!=summary["multiEventTransactions"]
            or summary["workflowCandidates"]!=len(candidates)
            or summary["transactionsWithInsufficientGenerationReadySteps"]>summary[
                "multiEventTransactions"]
            or summary["partiallyMappedTransactions"]>summary["workflowCandidates"]
            or summary["transactionsOverStepBound"]>summary["workflowCandidates"]
            or summary["executionReadyWorkflows"]>summary["workflowCandidates"]):
        raise ValueError("generated workflow plan has malformed planning diagnostics")
    expected_status=("execution-ready-candidates" if summary["executionReadyWorkflows"] else
        "review-only-candidates" if summary["workflowCandidates"] else
        "no-multi-step-generation-ready-contract" if summary["multiEventTransactions"] else
        "singleton-transactions-only" if summary["singletonTransactions"] else
        "no-explicit-linkage" if summary["unlinkedEvents"] else "no-interaction-events")
    if planning_status!=expected_status:
        raise ValueError("generated workflow plan has inconsistent planning diagnostics")
    diagnostics={"status":planning_status,**{field:summary[field] for field in diagnostic_fields},
        "explicitRecordingTransactions":explicit_recordings,
        "reviewOnlyLinkedCandidates":review_only_linked,
        "requestAlignedReviewOnlyLinkedCandidates":request_aligned_review_only,
        "selectedReviewOnlyCandidateId":selected_review_only,
        "readinessImpact":"limitations-only","causalityProven":False,
        "runtimeVerified":False,"gameplayVerified":False}
    return {"available":True,"totalCandidates":len(candidates),"shownCandidates":len(values),
        "omittedCandidates":max(0,len(candidates)-len(values)),
        "selectedCandidateId":selected_id,"candidates":values,"planningDiagnostics":diagnostics}




def _unavailable_requested(request_words,actions,is_egg,request_text=None):
    if not is_egg:return []
    egg=actions["eggHatching"];values=[]
    mode_words=set(request_words)
    if isinstance(request_text,str):mode_words.update(re.findall(r"[a-z0-9]+",request_text.lower()))
    automatic=bool(mode_words&{"auto","automatic","automatically"})
    multi=bool(mode_words&{"multi","multiple","triple"})
    if automatic:
        values.append({"id":"auto-game-mode","status":"unavailable",
            "blockers":list(egg["modeExecutionBlockers"]["auto"]),
            "minimumLiveObservations":list(egg["minimumLiveObservations"]["auto"]),
            "reason":"Generated repeat trials do not reproduce the game's Auto control or prove unattended hatching."})
    if multi:
        values.append({"id":"multi-game-mode","status":"unavailable",
            "blockers":list(egg["modeExecutionBlockers"]["multi"]),
            "minimumLiveObservations":list(egg["minimumLiveObservations"]["multi"]),
            "reason":"No distinct replayable multi-hatch contract with a greater-than-one observed outcome exists."})
    return values

def _discovery_only(actions):
    generic=actions["genericCapabilities"];values=[]
    generated_tool_paths={item.get("path") for item in actions.get("toolInteractions",{}).get("targets",[])
                          if item.get("trialGenerationReady") is True}
    generated_gui_paths={item.get("path") for item in actions.get("guiInteractions",{}).get("targets",[])
                         if item.get("trialGenerationReady") is True}
    combat=[item for item in generic.get("combatCandidates",[])
            if item.get("path") not in generated_tool_paths]
    if combat:
        values.append({"family":"combat-tool-action","candidateCount":len(combat),
            "observedCount":sum(item.get("evidenceTier")=="interaction-observed" for item in combat),
            "replayContractAvailable":False,
            "reason":"Remaining weapon and Tool evidence lacks an exact generated activation contract."})
    for family in ("world-interaction","gui-control","tool-action"):
        summary=generic.get("families",{}).get(family,{})
        discovered=summary.get("discovered",0);observed=summary.get("observed",0)
        if family=="tool-action":
            discovered=max(0,discovered-len(generated_tool_paths))
            observed=max(0,observed-len(generated_tool_paths))
        elif family=="gui-control":
            discovered=max(0,discovered-len(generated_gui_paths))
            observed=max(0,observed-len(generated_gui_paths))
        if discovered>0:
            values.append({"family":family,"candidateCount":discovered,
                "observedCount":min(discovered,observed),"replayContractAvailable":False,
                "reason":"Names and observed activation do not establish a generic replay operation."})
    return values


def _request_feature_matches(plan,request_words):
    features=plan.get("features")
    if not isinstance(features,list) or len(features)>5000:
        raise ValueError("compiled plan has malformed feature inventory")
    if not request_words:return []
    values=[]
    for feature in features:
        if not isinstance(feature,dict):
            raise ValueError("compiled plan has malformed feature evidence")
        name=feature.get("feature")
        if not isinstance(name,str) or not 1<=len(name)<=120:
            raise ValueError("compiled plan has malformed feature evidence")
        matched_terms=sorted(request_words&_tokens(name))
        if not matched_terms:continue
        counts={field:feature.get(field,0) for field in ("interactionEvents",
            "observableOutcomeCandidates","featureStateCorrelations","featureGuiCorrelations")}
        if any(type(value) is not int or not 0<=value<=10_000_000 for value in counts.values()):
            raise ValueError("compiled plan has malformed feature evidence")
        status=feature.get("status")
        if not isinstance(status,str) or not 1<=len(status)<=120:
            raise ValueError("compiled plan has malformed feature evidence")
        gameplay_tokens={"hatch","egg","sell","shop","reward","claim","rebirth",
            "upgrade","travel","teleport","quest","battle","combat","pet",
            "farm","bubble","craft","enchant","currency"}
        ui_tokens={"menu","inventory","ui","screen","tab","button","frame"}
        feature_tokens=_tokens(name)
        gameplay_score=0
        if feature_tokens&gameplay_tokens:
            gameplay_score+=20
        if feature_tokens&ui_tokens and not feature_tokens&gameplay_tokens:
            gameplay_score-=8
        gameplay_score+=4*counts["observableOutcomeCandidates"]
        gameplay_score+=3*counts["featureStateCorrelations"]
        gameplay_score+=2*counts["interactionEvents"]
        values.append({"feature":name,"status":status,
            "evidenceClassification":_FEATURE_EVIDENCE_CLASSIFICATION.get(
                status,"unrecognized-feature-status"),
            "matchedTerms":matched_terms,**counts,
            "gameplayPriorityScore":gameplay_score,
            "tokenEvidenceOnly":True,"implementationReady":False})
    values.sort(key=lambda item:(-item["gameplayPriorityScore"],
        -item["observableOutcomeCandidates"],-item["featureStateCorrelations"],
        -item["interactionEvents"],item["feature"]))
    return values



def _review_only_gui_request_evidence(actions,request_words):
    gui=actions.get("guiInteractions") if isinstance(actions,dict) else None
    if not isinstance(gui,dict):
        raise ValueError("action capabilities are malformed")
    targets=gui.get("targets",[])
    if not isinstance(targets,list) or len(targets)>2000:
        raise ValueError("action capabilities are malformed")
    review_targets=[]
    request_set=set(request_words)
    for target in targets:
        if not isinstance(target,dict):
            raise ValueError("action capabilities are malformed")
        if target.get("reviewOnlyTemporalOutcomeCandidate") is not True:
            continue
        path=target.get("path")
        if not isinstance(path,str) or not 1<=len(path)<=400:
            raise ValueError("action capabilities are malformed")
        evidence=set()
        for value in (path,target.get("label"),target.get("featureCandidate"),
                target.get("actionCandidate")):
            if value is None:
                continue
            if not isinstance(value,str):
                raise ValueError("action capabilities are malformed")
            evidence.update(_tokens(value))
        review_targets.append({"path":path,"requestAligned":bool(request_set&evidence)})
    expected_paths=[item["path"] for item in review_targets][:20]
    count=gui.get("reviewOnlyTemporalOutcomeCandidates",len(review_targets))
    paths=gui.get("reviewOnlyTargetPaths",expected_paths)
    if (type(count) is not int or not 0<=count<=10_000_000
            or count!=len(review_targets)
            or not isinstance(paths,list) or len(paths)>20
            or any(not isinstance(path,str) or not 1<=len(path)<=400 for path in paths)
            or paths!=expected_paths):
        raise ValueError("action capabilities are malformed")
    aligned=[item["path"] for item in review_targets if item["requestAligned"]]
    return {"totalCandidates":count,
        "requestAlignedCandidates":len(aligned),
        "requestAlignedPaths":aligned[:20]}


def _request_observation_gap_blockers(plan,request_token_set):
    if not request_token_set or not (request_token_set&_COMBAT_REQUEST_TOKENS):
        return []
    history=plan.get("observedInteractionHistory",[])
    if not isinstance(history,list) or len(history)>20_000:
        raise ValueError("compiled plan has malformed interaction history")
    input_observed=False
    state_transition_observed=False
    for event in history:
        if not isinstance(event,dict):
            raise ValueError("compiled plan has malformed interaction history")
        control=event.get("controlType")
        control_lower=control.casefold() if isinstance(control,str) else ""
        action=event.get("actionKind")
        action_lower=action.casefold() if isinstance(action,str) else ""
        path=event.get("path")
        path_lower=path.casefold() if isinstance(path,str) else ""
        if (control_lower.startswith("inputbegan.")
                or control_lower.startswith("inputchanged.")
                or control_lower.startswith("tool.")
                or control_lower.startswith("humanoid.")
                or control_lower.startswith("inputevent.")
                or action_lower in _COMBAT_INPUT_ACTION_TOKENS
                or ".input." in path_lower):
            input_observed=True
        state_changes=event.get("stateChanges")
        if isinstance(state_changes,list) and state_changes:
            state_transition_observed=True
        windows=event.get("observationWindows")
        if isinstance(windows,list):
            for window in windows:
                if not isinstance(window,dict):
                    continue
                state_count=window.get("stateChangeCount")
                if type(state_count) is int and state_count>0:
                    state_transition_observed=True
                    break
                if isinstance(window.get("stateChanges"),list) and window["stateChanges"]:
                    state_transition_observed=True
                    break
        if input_observed and state_transition_observed:
            break
    blockers=[]
    if not input_observed:
        blockers.append("request_aligned_input_observation_not_captured")
    if not state_transition_observed:
        blockers.append("request_aligned_state_transition_not_observed")
    return blockers



def _request_feature_readiness(plan,request,status,generated,matched_generated,gameplay_request,
        unavailable,discovery_only,workflow_selection,workflow_target,actions):
    request_token_set=_tokens(request)
    request_words=sorted(request_token_set)
    feature_matches=_request_feature_matches(plan,request_token_set)
    review_only_gui=_review_only_gui_request_evidence(actions,request_words)
    observation_gap_blockers=_request_observation_gap_blockers(plan,request_token_set)
    feature_values=feature_matches[:32]
    meaningful_feature_matches=sum(item.get("gameplayPriorityScore",0)>0 for item in feature_matches)
    gameplay_systems=gameplay_request.get("matchedSystems",[]) if isinstance(gameplay_request,dict) else []
    gameplay_actions=(gameplay_request.get("matchedObservedActions",[])
        if isinstance(gameplay_request,dict) else [])
    gameplay_resources=(gameplay_request.get("matchedResources",[])
        if isinstance(gameplay_request,dict) else [])
    request_blockers=gameplay_request.get("blockers",[]) if isinstance(gameplay_request,dict) else []
    if any(not isinstance(values,list) for values in
           (gameplay_systems,gameplay_actions,gameplay_resources,request_blockers)):
        raise ValueError("gameplay requested capability assessment is malformed")
    if any(not isinstance(value,str) or not 1<=len(value)<=160 for values in
           (gameplay_systems,gameplay_actions,gameplay_resources,request_blockers)
           for value in values):
        raise ValueError("gameplay requested capability assessment is malformed")
    workflow_candidates=(workflow_selection.get("candidates",[])
        if isinstance(workflow_selection,dict) and workflow_selection.get("available") is True else [])
    execution_ready_workflows=sum(item.get("executionReady") is True for item in workflow_candidates)
    request_aligned_workflows=sum(item.get("executionReady") is True and bool(
        item.get("matchedTerms")) for item in workflow_candidates)
    request_aligned_review_only_gui=review_only_gui["requestAlignedCandidates"]
    if request is None:
        request_status="no-capability-requested"
    elif status=="generated-bounded-subset":
        request_status="bounded-generated-subset"
    elif status=="evidence-only-no-replay-contract":
        request_status="evidence-aligned-no-generated-contract"
    else:
        request_status="unsupported-by-current-evidence"

    blockers=[]
    if request is not None:
        blockers.extend("request-assessment:"+value for value in request_blockers)
        blockers.extend("unavailable:"+item["id"] for item in unavailable)
        blockers.extend("discovery-only:"+item["family"] for item in discovery_only)
        blockers.extend(observation_gap_blockers)
        if not matched_generated:blockers.append("bounded_generated_contract_unavailable")
        if not feature_values:blockers.append("no_request_feature_token_overlap")
        if meaningful_feature_matches==0:blockers.append("no_meaningful_gameplay_feature_matches")
        if execution_ready_workflows==0:blockers.append("no_execution_ready_workflow_candidates")
        if (not matched_generated and request_aligned_review_only_gui>0):
            blockers.append("request_aligned_gui_transition_outcomes_without_scalar_contract")
        if request_status=="unsupported-by-current-evidence":
            blockers.append("request_evidence_alignment_unresolved")
    blockers=sorted(set(blockers))
    generated_ids=[item["id"] for item in generated]
    return {"schemaVersion":_REQUEST_FEATURE_SCHEMA,"request":request,
        "status":request_status,"requestedTerms":request_words,
        "featureEvidence":{"matchedFeatures":feature_values,
            "omittedMatches":max(0,len(feature_matches)-len(feature_values)),
            "matchSignalsBounded":True},
        "workflowEvidence":{"available":workflow_selection["available"],
            "planningStatus":workflow_selection.get("planningDiagnostics",{}).get("status"),
            "executionReadyCandidates":execution_ready_workflows,
            "requestAlignedExecutionReadyCandidates":request_aligned_workflows,
            "reviewOnlyGuiTransitionCandidates":review_only_gui["totalCandidates"],
            "requestAlignedReviewOnlyGuiTransitionCandidates":request_aligned_review_only_gui,
            "requestAlignedReviewOnlyGuiTransitionPaths":review_only_gui["requestAlignedPaths"],
            "selectedCandidateId":workflow_selection.get("selectedCandidateId"),
            "selectedCandidateRequestAligned":bool(workflow_target and _workflow_request_aligned(
                workflow_target,request)) if request is not None else False,
            "temporalCorrelationOnly":True},
        "generatedEvidence":{"generatedCapabilityIds":generated_ids,
            "matchedGeneratedCapabilityIds":list(matched_generated),
            "generatedCapabilityCount":len(generated_ids)},
        "explicitBlockers":blockers,
        "summary":{"matchedFeatures":len(feature_values),
            "meaningfulGameplayFeatureMatches":meaningful_feature_matches,
            "matchedSystems":len(gameplay_systems),
            "matchedObservedActions":len(gameplay_actions),
            "matchedResources":len(gameplay_resources),
            "requestAlignedExecutionReadyWorkflows":request_aligned_workflows,
            "requestAlignedReviewOnlyGuiTransitions":request_aligned_review_only_gui,
            "blockers":len(blockers)},
        "nameMatchingSufficientForImplementation":False,
        "temporalCorrelationSufficientForImplementation":False,
        "implementationReady":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,
        "actionOutcomesVerified":False}


def _interaction_observation_coverage(plan):
    value=plan.get("interactionObservationSummary")
    if value is None or isinstance(value,dict) and value.get("available") is False:
        return {"available":False,"classification":"unavailable-legacy",
            "evidenceLossPossible":None,"readinessImpact":"limitations-only",
            "limitations":["interaction baseline and delayed-window accounting are unavailable"],
            "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False}
    counts=("callbacksFired","preActivationBaselinesUsed","callbackBaselinesUsed",
        "pendingObservationEvents","observationWindowsExpected",
        "observationWindowsCompleted","observationWindowsFailed")
    capture_failures=value.get("preActivationCaptureFailures") if isinstance(value,dict) else None
    if (not isinstance(value,dict) or value.get("available") is not True
            or any(type(value.get(field)) is not int or not 0<=value[field]<=10_000_000
                for field in counts)
            or capture_failures is not None and
                (type(capture_failures) is not int or not 0<=capture_failures<=10_000_000)
            or value.get("observationWindowAccountingValid") is not True
            or type(value.get("evidenceLossPossible")) is not bool
            or value["preActivationBaselinesUsed"]+value["callbackBaselinesUsed"]!=value[
                "callbacksFired"]
            or value["observationWindowsCompleted"]+value["observationWindowsFailed"]+value[
                "pendingObservationEvents"]!=value["observationWindowsExpected"]):
        raise ValueError("compiled plan has malformed interaction observation coverage")
    known_possible=bool(value["callbackBaselinesUsed"] or value["pendingObservationEvents"]
        or value["observationWindowsFailed"])
    possible=(bool(known_possible or capture_failures) if capture_failures is not None
        else value["evidenceLossPossible"])
    if known_possible and value["evidenceLossPossible"] is not True or (
            capture_failures is not None and possible is not value["evidenceLossPossible"]):
        raise ValueError("compiled plan has inconsistent interaction evidence-loss status")
    limitations=[]
    if value["callbackBaselinesUsed"]:limitations.append(
        "callback-time baselines may miss synchronous activation changes")
    if capture_failures:limitations.append("one or more pre-activation captures failed")
    if value["observationWindowsFailed"]:limitations.append(
        "one or more delayed observation windows failed")
    if value["pendingObservationEvents"]:limitations.append(
        "one or more delayed observation windows were pending at export")
    classification=("possible-evidence-loss" if possible else
        ("accounted-no-interactions" if value["callbacksFired"]==0 else
         "accounted-pre-activation-observation"))
    result={"available":True,"classification":classification,
        **{field:value[field] for field in counts},
        "observationWindowAccountingValid":True,"evidenceLossPossible":possible,
        "readinessImpact":"limitations-only","limitations":limitations,
        "causalityProven":False,"runtimeVerified":False,"gameplayVerified":False}
    if capture_failures is not None:result["preActivationCaptureFailures"]=capture_failures
    return result



def _guided_feedback_correlation(plan,actions,workflow_plan,feedback_documents):
    if workflow_plan is None:
        if feedback_documents not in (None,[]):
            raise ValueError("guided feedback requires the exact generated workflow plan")
        return {"available":False,"reason":"No guided workflow plan was supplied",
            "readinessImpact":"none","claims":dict(_FALSE_CLAIMS)}
    expected=_load("plan_generated_workflows.py","readiness_workflow_planner").plan(plan,actions)
    if workflow_plan!=expected:
        raise ValueError("generated workflow plan does not match validated evidence")
    if feedback_documents in (None,[]):
        return {"available":False,"reason":"No digest-bound guided feedback was supplied",
            "workflowCandidates":expected["summary"]["workflowCandidates"],
            "readinessImpact":"none","claims":dict(_FALSE_CLAIMS)}
    aggregate=_load("aggregate_guided_workflow_feedback.py",
        "readiness_guided_feedback_aggregate").aggregate(workflow_plan,feedback_documents)
    steps=[{"stepSequence":step["stepSequence"],"targetPath":step["targetPath"],
        "outcomeKey":step["outcomeKey"],"expected":step["expected"],
        "attempts":step["attempts"],"sessionsObserved":step["sessionsObserved"],
        "activationEventsObserved":step["activationEventsObserved"],
        "expectedChangesObserved":step["expectedChangesObserved"],
        "sessionsWithExpectedChange":step["sessionsWithExpectedChange"],
        "statuses":dict(step["statuses"]),
        "statusConflictObserved":step["statusConflictObserved"],
        "statusConflictAcrossSessions":step["statusConflictAcrossSessions"],
        "observedScalarTypes":list(step["observedScalarTypes"]),
        "scalarTypeConflictObserved":step["scalarTypeConflictObserved"],
        "expectedDirectionAcrossMultipleSessions":step[
            "expectedDirectionAcrossMultipleSessions"]} for step in aggregate["steps"]]
    return {"available":True,"schemaVersion":aggregate["schemaVersion"],
        "workflowPlanSHA256":aggregate["workflowPlanSHA256"],
        "candidateId":aggregate["candidateId"],"summary":dict(aggregate["summary"]),
        "steps":steps,"completeSequenceRecurrenceObserved":aggregate[
            "completeSequenceRecurrenceObserved"],"readinessImpact":"informational-only",
        "claims":dict(_FALSE_CLAIMS),
        "note":"Repeated digest-bound client observations remain non-causal and do not make implementation ready."}


def assess(plan,gameplay,actions,workflow_plan=None,guided_feedback_documents=None):
    integrity,request=_validate_sources(plan,gameplay,actions)
    observation_coverage=_interaction_observation_coverage(plan)
    guided_correlation=_guided_feedback_correlation(
        plan,actions,workflow_plan,guided_feedback_documents)
    target=_selected_prompt(actions);tool_target=_selected_tool(actions);gui_target=_selected_gui(actions)
    workflow_target=_selected_workflow(workflow_plan,plan,actions)
    is_egg=_is_egg_target(actions,target)
    generated=[];matched_generated=[]
    for target_value,builder in ((target,lambda value:_generated_capability(value,is_egg)),
            (tool_target,_generated_tool_capability),(gui_target,_generated_gui_capability)):
        if target_value:
            capability=builder(target_value);generated.append(capability)
            if target_value.get("objective",{}).get("requestAligned") is True:
                matched_generated.append(capability["id"])
    if workflow_target:
        generated.append(_generated_workflow_capability(workflow_target))
        if _workflow_request_aligned(workflow_target,request):
            matched_generated.append("linked-gameplay-workflow-trial")
    request_words=_tokens(request)
    prompt_aligned=bool(target and target.get("objective",{}).get("requestAligned") is True)
    unavailable=_unavailable_requested(request_words,actions,is_egg and prompt_aligned,request)
    gameplay_request=gameplay.get("requestedCapabilityAssessment")
    evidence_matched=bool(gameplay_request and (gameplay_request.get("matchedSystems")
        or gameplay_request.get("matchedObservedActions") or gameplay_request.get("matchedResources")))
    if request is None:
        status="no-capability-requested"
    elif matched_generated:
        status="generated-bounded-subset"
    elif evidence_matched or target or tool_target or gui_target or workflow_target:
        status="evidence-only-no-replay-contract"
    else:
        status="unsupported-by-current-evidence"
    supported_subset=[]
    if "prompt-interaction-trial" in matched_generated:
        supported_subset.extend(["select one exact observed prompt target",
            "move the local character to its observed anchor"])
    if "tool-activation-trial" in matched_generated:
        supported_subset.extend(["select one exact observed Tool target",
            "equip it through the local Humanoid and call official Tool:Activate()"])
    if "guided-gui-interaction-trial" in matched_generated:
        supported_subset.extend(["resolve and highlight one exact observed GUI control",
            "require the user to activate that game control through Roblox's normal input path"])
    if "linked-gameplay-workflow-trial" in matched_generated:
        supported_subset.extend(["run the exact observed linked action order as one bounded trial",
            "check each exact target and prerequisite snapshot before activation",
            "stop on the first unavailable target, prerequisite drift, activation failure, or unobserved outcome"])


    if matched_generated:
        supported_subset.extend(["run an operator-started bounded repeat trial",
            "observe one selected client-visible scalar direction",
            "stop cleanly after request, close, three uncorroborated attempts, or 25 total attempts"])
    request_result={"request":request,"status":status,
        "matchedGeneratedCapabilityIds":matched_generated,
        "generatedSubsetAvailable":bool(matched_generated),
        "supportedSubset":supported_subset,
        "fullRequestImplemented":False,"implementationReady":False,
        "runtimeVerified":False,"gameplayVerified":False,
        "causalityProven":False,"actionOutcomesVerified":False}
    discovery_only=_discovery_only(actions)
    workflow_selection=_workflow_selection(workflow_plan,workflow_target)
    request_feature_readiness=_request_feature_readiness(
        plan,request,status,generated,matched_generated,gameplay_request,
        unavailable,discovery_only,workflow_selection,workflow_target,actions)
    if observation_coverage["available"] is False:
        observation_limit="Interaction baseline/window coverage is unavailable for this legacy evidence"
    elif observation_coverage["evidenceLossPossible"]:
        observation_limit="Interaction timing or delayed-window coverage may have lost client-visible changes"
    elif observation_coverage["callbacksFired"]==0:
        observation_limit="Observation accounting is complete but no interaction callback evidence was captured"
    else:
        observation_limit="Accounted pre-activation and delayed-window coverage still does not prove causality or complete game state"

    result={"schemaVersion":SCHEMA_VERSION,"placeId":integrity["placeId"],
        "scanId":integrity.get("scanId"),"request":request_result,
        "requestFeatureReadiness":request_feature_readiness,
        "generatedCapabilities":generated,
        "unavailableRequestedBehavior":unavailable,
        "discoveryOnlyCapabilities":discovery_only,
        "workflowSelection":workflow_selection,
        "interactionObservationCoverage":observation_coverage,
        "guidedWorkflowFeedbackCorrelation":guided_correlation,
        "summary":{"generatedCapabilities":len(generated),
            "requestMatchedGeneratedCapabilities":len(matched_generated),
            "requestFeatureMatches":request_feature_readiness["summary"]["matchedFeatures"],
            "requestFeatureBlockers":request_feature_readiness["summary"]["blockers"],
            "unavailableRequestedBehavior":len(unavailable),
            "discoveryOnlyCapabilityFamilies":len(discovery_only),
            "guidedFeedbackSessions":guided_correlation.get("summary",{}).get("sessions",0),
            "guidedFeedbackStatusConflicts":guided_correlation.get("summary",{}).get(
                "stepsWithStatusConflict",0)},
        "claims":dict(_FALSE_CLAIMS),
        "limitations":[observation_limit,
            "Generation readiness describes emitted code, not successful gameplay",
            "Prompt and Tool outcomes remain temporal correlations without causal proof",
            "Executor-provided prompt activation is checked only at runtime",
            "Linked workflow order and state continuity do not prove cross-step gameplay causality",
            "Generated mixed workflows stop when a selected client-visible outcome is not observed",
            "Generated Tool trials use official local equip/Activate methods but remain unverified in Roblox",
            "Guided GUI trials highlight exact controls but require normal user activation because GuiButton has no public automatic Activate method",
            "Repeated guided feedback reports client-observed correlation only and cannot establish causality or implementation readiness",
            "Remaining generic candidates stay unavailable without exact action contracts"]}
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("--output",default="build/generation-readiness.json")
    args=parser.parse_args()
    try:
        plan=json.loads(pathlib.Path(args.plan).read_text(encoding="utf-8"))
        gameplay=_load("understand_gameplay.py","readiness_cli_gameplay").analyze(plan)
        actions=_load("discover_action_capabilities.py","readiness_cli_actions").analyze(plan)
        result=assess(plan,gameplay,actions)
        target=pathlib.Path(args.output);target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",
            encoding="utf-8")
        print("Generation readiness:",target);return 0
    except (OSError,ValueError,TypeError,KeyError,json.JSONDecodeError) as exc:
        print("GENERATION READINESS BLOCKED:",exc,file=sys.stderr);return 2


if __name__=="__main__":sys.exit(main())
