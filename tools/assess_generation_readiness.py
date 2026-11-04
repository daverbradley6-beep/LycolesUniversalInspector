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
        "operatorStartRequired":True,"failureLimit":3,
        "classification":"generated-evidence-bounded-trial",
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
    combat=generic.get("combatCandidates",[])
    if combat:
        values.append({"family":"combat-tool-action","candidateCount":len(combat),
            "observedCount":sum(item.get("evidenceTier")=="interaction-observed" for item in combat),
            "replayContractAvailable":False,
            "reason":"Weapon and Tool evidence is discovery-only; no permitted replay contract is established."})
    for family in ("world-interaction","gui-control","tool-action"):
        summary=generic.get("families",{}).get(family,{})
        if summary.get("discovered",0)>0:
            values.append({"family":family,"candidateCount":summary["discovered"],
                "observedCount":summary.get("observed",0),"replayContractAvailable":False,
                "reason":"Names and observed activation do not establish a generic replay operation."})
    return values


def assess(plan,gameplay,actions):
    integrity,request=_validate_sources(plan,gameplay,actions)
    target=_selected_prompt(actions)
    is_egg=_is_egg_target(actions,target)
    generated=[_generated_capability(target,is_egg)] if target else []
    request_words=_tokens(request)
    aligned=bool(target and target.get("objective",{}).get("requestAligned") is True)
    matched_generated=[generated[0]["id"]] if generated and aligned else []
    unavailable=_unavailable_requested(request_words,actions,is_egg and aligned)
    gameplay_request=gameplay.get("requestedCapabilityAssessment")
    evidence_matched=bool(gameplay_request and (gameplay_request.get("matchedSystems")
        or gameplay_request.get("matchedObservedActions") or gameplay_request.get("matchedResources")))
    if request is None:
        status="no-capability-requested"
    elif matched_generated:
        status="generated-bounded-subset"
    elif evidence_matched or target:
        status="evidence-only-no-replay-contract"
    else:
        status="unsupported-by-current-evidence"
    supported_subset=[]
    if matched_generated:
        supported_subset=["select one exact observed prompt target",
            "move the local character to its observed anchor",
            "run an operator-started bounded repeat trial",
            "observe one selected client-visible scalar direction",
            "stop cleanly after request, close, or three uncorroborated attempts"]
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
        "summary":{"generatedCapabilities":len(generated),
            "requestMatchedGeneratedCapabilities":len(matched_generated),
            "unavailableRequestedBehavior":len(unavailable),
            "discoveryOnlyCapabilityFamilies":len(discovery_only)},
        "claims":dict(_FALSE_CLAIMS),
        "limitations":["Generation readiness describes emitted code, not successful gameplay",
            "Prompt outcomes remain temporal correlations without causal proof",
            "Executor-provided prompt activation is checked only at runtime",
            "GUI and Tool candidates remain unavailable without permitted replay contracts"]}
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
