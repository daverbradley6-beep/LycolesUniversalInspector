#!/usr/bin/env python3
"""Synthesize evidence-bounded generation readiness from validated artifacts."""
import argparse
import importlib.util
import json
import pathlib
import re
import sys

SCHEMA_VERSION="113.generation-readiness.1"
_FALSE_CLAIMS={
    "sourceAuthenticityVerified":False,"causalityProven":False,
    "serverAuthorityVerified":False,"runtimeVerified":False,
    "gameplayVerified":False,"actionOutcomesVerified":False,
}

def _load(filename,name):
    source=pathlib.Path(__file__).with_name(filename)
    spec=importlib.util.spec_from_file_location(name,source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def _tokens(value):
    if not isinstance(value,str):return set()
    return {token for token in re.findall(r"[a-z0-9]+",value.casefold()) if len(token)>2}

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

def _generated_capability(target,is_egg):
    commands=["interaction","interactionstart","interactionstop","interactions"]
    if is_egg:commands.extend(["egg","eggmode","eggstart","eggstop","eggs"])
    outcome=target["selectedOutcome"]
    return {"id":"prompt-interaction-trial","kind":"proximity-prompt-trial",
        "targetPath":target["path"],"targetLabel":target["label"],
        "targetFeature":target.get("featureCandidate"),
        "selectedOutcomeKey":outcome["key"],"expectedChange":outcome["change"],
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
        "commands":["interaction","interactionstart","interactionstop","interactions"],
        "automaticActivation":False,"manualActivationRequired":True,
        "exactControlHighlighting":True,"automaticMovement":False,
        "boundedRepeat":True,"operatorStartRequired":True,"failureLimit":3,"attemptLimit":25,
        "classification":"generated-evidence-bounded-guided-trial",
        "fullGameplayMechanicImplemented":False,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}



def _unavailable_requested(request_words,actions,is_egg):
    if not is_egg:return []
    egg=actions["eggHatching"];values=[]
    automatic=bool(request_words&{"auto","automatic","automatically"})
    multi=bool(request_words&{"multi","multiple","triple"})
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
    guided_correlation=_guided_feedback_correlation(
        plan,actions,workflow_plan,guided_feedback_documents)
    target=_selected_prompt(actions);tool_target=_selected_tool(actions);gui_target=_selected_gui(actions)
    is_egg=_is_egg_target(actions,target)
    generated=[];generated_sources=[]
    if target:
        generated.append(_generated_capability(target,is_egg));generated_sources.append(target)
    if tool_target:
        generated.append(_generated_tool_capability(tool_target));generated_sources.append(tool_target)
    if gui_target:
        generated.append(_generated_gui_capability(gui_target));generated_sources.append(gui_target)
    request_words=_tokens(request)
    matched_generated=[capability["id"] for capability,source in zip(generated,generated_sources)
        if source.get("objective",{}).get("requestAligned") is True]
    prompt_aligned=bool(target and target.get("objective",{}).get("requestAligned") is True)
    unavailable=_unavailable_requested(request_words,actions,is_egg and prompt_aligned)
    gameplay_request=gameplay.get("requestedCapabilityAssessment")
    evidence_matched=bool(gameplay_request and (gameplay_request.get("matchedSystems")
        or gameplay_request.get("matchedObservedActions") or gameplay_request.get("matchedResources")))
    if request is None:
        status="no-capability-requested"
    elif matched_generated:
        status="generated-bounded-subset"
    elif evidence_matched or target or tool_target or gui_target:
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
    result={"schemaVersion":SCHEMA_VERSION,"placeId":integrity["placeId"],
        "scanId":integrity.get("scanId"),"request":request_result,
        "generatedCapabilities":generated,
        "unavailableRequestedBehavior":unavailable,
        "discoveryOnlyCapabilities":discovery_only,
        "guidedWorkflowFeedbackCorrelation":guided_correlation,
        "summary":{"generatedCapabilities":len(generated),
            "requestMatchedGeneratedCapabilities":len(matched_generated),
            "unavailableRequestedBehavior":len(unavailable),
            "discoveryOnlyCapabilityFamilies":len(discovery_only),
            "guidedFeedbackSessions":guided_correlation.get("summary",{}).get("sessions",0),
            "guidedFeedbackStatusConflicts":guided_correlation.get("summary",{}).get(
                "stepsWithStatusConflict",0)},
        "claims":dict(_FALSE_CLAIMS),
        "limitations":["Generation readiness describes emitted code, not successful gameplay",
            "Prompt and Tool outcomes remain temporal correlations without causal proof",
            "Executor-provided prompt activation is checked only at runtime",
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
