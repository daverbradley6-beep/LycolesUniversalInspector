#!/usr/bin/env python3
"""Plan reviewable multi-control workflows from explicit linked observations."""
import copy
import hashlib
import json
import math
import re
import unicodedata

SCHEMA="114.generated-workflow-plan.1"
MAX_EVENTS=2000
MAX_WORKFLOW_STEPS=64
FALSE_CLAIMS=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified")

def _text(value,limit):
    return (isinstance(value,str) and 1<=len(value.encode("utf-8"))<=limit
        and all(unicodedata.category(character)!="Cc" for character in value))

def _scalar(value):
    return type(value) in (int,float,str,bool) and len(str(value))<=200

_STOP_WORDS={"a","an","and","complete","do","for","from","in","of","observed","please",
    "the","to","with","workflow","flow"}

def _tokens(value):
    if not isinstance(value,str):return set()
    result=set()
    for token in re.findall(r"[a-z0-9]+",value.lower())[:128]:
        if len(token)>4 and token.endswith("s") and not token.endswith("ss"):token=token[:-1]
        if len(token)>=2 and token not in _STOP_WORDS:result.add(token)
    return result

def _selection(steps,request):
    requested=_tokens(request);weighted={}
    for step in steps:
        for value,weight in ((step.get("targetFeature"),5),(step.get("actionCandidate"),4),
                (step.get("targetLabel"),3),(step.get("targetPath"),1),
                (step.get("selectedOutcome",{}).get("key"),1)):
            for token in _tokens(value):weighted[token]=max(weighted.get(token,0),weight)
    matched=sorted(requested&set(weighted))
    return {"requestAligned":bool(matched),"requestScore":sum(weighted[token] for token in matched),
        "matchedTerms":matched,"requestedTerms":sorted(requested)}


def _identity(value):
    if not isinstance(value,list) or not 1<=len(value)<=21:return None
    result=[]
    for item in value:
        if not isinstance(item,dict):return None
        name=item.get("name");class_name=item.get("className");ordinal=item.get("ordinal")
        if (not _text(name,100) or not _text(class_name,100)
                or type(ordinal) is not int or not 1<=ordinal<=10_000):return None
        result.append({"name":name,"className":class_name,"ordinal":ordinal})
    return result

def _targets(actions):
    values={}
    groups=(("promptInteractions","proximity-prompt-trial","promptMetadata"),
        ("toolInteractions","official-tool-activation-trial","toolMetadata"),
        ("guiInteractions","guided-gui-activation-trial","guiMetadata"))
    for group,kind,metadata_key in groups:
        contract=actions.get(group,{})
        targets=contract.get("targets",[]) if isinstance(contract,dict) else None
        if not isinstance(targets,list) or len(targets)>2000:
            raise ValueError("Malformed action capability targets")
        for target in targets:
            if not isinstance(target,dict) or target.get("trialGenerationReady") is not True:
                continue
            path=target.get("path");control_type=target.get("controlType")
            outcome=target.get("selectedOutcome")
            if (target.get("identityMode")!="component" or _identity(target.get("pathIdentity")) is None
                    or not isinstance(outcome,dict) or _identity(outcome.get("stateIdentity")) is None):
                continue
            if kind=="proximity-prompt-trial":
                metadata=target.get(metadata_key)
                if (not isinstance(metadata,dict) or metadata.get("enabled") is not True
                        or not isinstance(metadata.get("anchorPath"),str)
                        or not isinstance(metadata.get("anchorPosition"),dict)
                        or type(metadata.get("maxActivationDistance")) not in (int,float)):
                    continue
            if (not _text(path,400) or not _text(control_type,80) or not _text(target.get("label"),120)
                    or not isinstance(target.get(metadata_key),dict)
                    or not _text(outcome.get("key"),200)
                    or outcome.get("change") not in ("increased","decreased","changed")
                    or outcome.get("generationResolvable") is not True):
                raise ValueError("Malformed generation-ready action target")
            key=(path,control_type)
            if key in values:raise ValueError("Ambiguous generation-ready action target")
            values[key]=(kind,metadata_key,target)
    return values

def _event_delta(event,key):
    changes=event.get("stateChanges",[])
    if not isinstance(changes,list) or len(changes)>256:return None
    matches=[item for item in changes if isinstance(item,dict) and item.get("key")==key
        and _scalar(item.get("before")) and _scalar(item.get("after"))]
    if len(matches)!=1:return None
    identity=_identity(matches[0].get("stateIdentity"))
    if matches[0].get("stateIdentityStatus")!="component-resolved" or identity is None:return None
    return {"key":key,"before":matches[0]["before"],"after":matches[0]["after"],
        "stateIdentity":identity}


_BASELINE_SOURCES={"GuiButton.InputBegan","ProximityPrompt.PromptButtonHoldBegan",
    "Tool.Equipped","activation-callback-fallback"}

def _baseline(event):
    fields=("baselineSource","baselineTiming","baselineAgeSeconds",
        "preActivationBaselineAvailable")
    if not any(field in event for field in fields):
        return {"timing":"unknown","preActivationBaselineAvailable":False,
            "possibleSynchronousLoss":True}
    source=event.get("baselineSource");timing=event.get("baselineTiming")
    available=event.get("preActivationBaselineAvailable");age=event.get("baselineAgeSeconds")
    expected="activation-callback" if source=="activation-callback-fallback" else "pre-activation"
    if (source not in _BASELINE_SOURCES or timing!=expected or type(available) is not bool
            or available!=(timing=="pre-activation") or (age is not None and
            (type(age) not in (int,float) or type(age) is bool or not math.isfinite(age)
                or not 0<=age<=3600))):
        raise ValueError("Malformed workflow baseline timing")
    return {"timing":timing,"preActivationBaselineAvailable":available,
        "possibleSynchronousLoss":not available}

def _step(event,sequence,transaction_order,kind,metadata_key,target):
    outcome=target["selectedOutcome"]
    observed=_event_delta(event,outcome["key"])
    if (_identity(event.get("pathIdentity"))!=_identity(target["pathIdentity"])
            or event.get("controlMetadata")!=target[metadata_key]
            or observed is None
            or observed["stateIdentity"]!=_identity(outcome["stateIdentity"])):
        raise ValueError("Workflow step evidence drift")
    expected=outcome["change"]
    before,after=observed["before"],observed["after"]
    direction=((expected=="increased" and type(before) in (int,float)
            and type(after) in (int,float) and after>before)
        or (expected=="decreased" and type(before) in (int,float)
            and type(after) in (int,float) and after<before)
        or (expected=="changed" and after!=before))
    if not direction:raise ValueError("Workflow step outcome drift")
    activation_mode={"guided-gui-activation-trial":"normal-user-gui-activation",
        "official-tool-activation-trial":"official-tool-activate",
        "proximity-prompt-trial":"executor-fireproximityprompt"}[kind]
    return {"sequence":sequence,"transactionOrder":transaction_order,
        "observedSequence":event["sequence"],"targetPath":target["path"],
        "targetLabel":target["label"],"targetFeature":target.get("featureCandidate"),
        "actionCandidate":target.get("actionCandidate"),
        "controlType":target["controlType"],"kind":kind,"activationMode":activation_mode,
        "observationBaseline":_baseline(event),
        "pathIdentity":copy.deepcopy(target["pathIdentity"]),
        "prerequisiteMetadata":copy.deepcopy(target[metadata_key]),
        "entryStatePrerequisite":{"key":outcome["key"],"value":observed["before"],
            "stateIdentity":copy.deepcopy(outcome["stateIdentity"]),
            "classification":"exact-observed-entry-state","causalityProven":False},
        "selectedOutcome":{"key":outcome["key"],"change":outcome["change"],
            "stateIdentity":copy.deepcopy(outcome["stateIdentity"]),
            "observedBefore":observed["before"],"observedAfter":observed["after"]},
        "manualActivationRequired":kind=="guided-gui-activation-trial",
        "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False}

def _continuity(steps):
    links=[]
    for index in range(1,len(steps)):
        previous=steps[index-1]["selectedOutcome"]
        current=steps[index]["selectedOutcome"]
        if (steps[index-1]["transactionOrder"]+1==steps[index]["transactionOrder"]
                and previous["key"]==current["key"] and previous["observedAfter"] is not None
                and previous["observedAfter"]==current["observedBefore"]):
            links.append({"fromStep":index,"toStep":index+1,"stateKey":previous["key"],
                "value":previous["observedAfter"],"classification":"observed-state-continuity",
                "causalityProven":False})
    return links

def plan(plan_document,actions):
    integrity=plan_document.get("integrity") if isinstance(plan_document,dict) else None
    if (not isinstance(integrity,dict) or integrity.get("scanComplete") is not True
            or type(integrity.get("placeId")) is not int or not _text(integrity.get("scanId"),128)):
        raise ValueError("Complete identified scan required")
    request=plan_document.get("requestedCapability")
    if request is not None and not _text(request,1000):
        raise ValueError("Malformed requested capability")
    request=request or ""
    claims=actions.get("claims") if isinstance(actions,dict) else None
    if (not isinstance(actions,dict) or actions.get("schemaVersion")!="111.action-capabilities.1"
            or actions.get("placeId")!=integrity["placeId"]
            or actions.get("scanId")!=integrity["scanId"] or not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in FALSE_CLAIMS)):
        raise ValueError("Action capability identity or claims mismatch")
    history=plan_document.get("observedInteractionHistory",[])
    if not isinstance(history,list) or len(history)>MAX_EVENTS:
        raise ValueError("Invalid interaction history")
    targets=_targets(actions);groups={};unlinked=0
    for event in history:
        if not isinstance(event,dict):raise ValueError("Malformed interaction event")
        transaction=event.get("transactionId");sequence=event.get("sequence")
        if ((type(transaction) not in (int,str) or not _text(str(transaction),80))
                or type(sequence) is not int or not 1<=sequence<=10_000_000):
            unlinked+=1;continue
        groups.setdefault(str(transaction),[]).append(event)
    candidates=[];insufficient_contracts=0;partially_mapped=0;over_step_bound=0
    singleton_transactions=sum(len(events)==1 for events in groups.values())
    multi_event_transactions=sum(len(events)>1 for events in groups.values())
    for transaction,events in sorted(groups.items()):
        sequences=[event["sequence"] for event in events]
        if len(set(sequences))!=len(sequences):
            raise ValueError("Duplicate sequence in linked transaction")
        events.sort(key=lambda item:item["sequence"])
        mapped=[]
        for transaction_order,event in enumerate(events,1):
            key=(event.get("path"),event.get("controlType"))
            if key in targets:mapped.append((transaction_order,event,targets[key]))
        if len(events)>1 and len(mapped)<2:insufficient_contracts+=1
        if len(mapped)<2:continue
        if len(mapped)!=len(events):partially_mapped+=1
        steps=[_step(event,index+1,transaction_order,*target_data)
            for index,(transaction_order,event,target_data) in enumerate(mapped)]
        blockers=["Cross-step gameplay semantics are unverified",
            "Observed order and state continuity do not prove causality"]
        if len(mapped)!=len(events):
            blockers.append("One or more linked events lack exact generation-ready contracts")

        manual_gui=any(step["manualActivationRequired"] for step in steps)
        prompt_runtime=any(step["kind"]=="proximity-prompt-trial" for step in steps)
        if manual_gui:
            blockers.append("At least one GUI step requires normal user activation")
        if prompt_runtime:
            blockers.append("Prompt steps require fireproximityprompt availability at runtime")
        within_step_bound=len(mapped)<=MAX_WORKFLOW_STEPS
        if not within_step_bound:
            over_step_bound+=1
            blockers.append("Workflow exceeds the bounded 64-step generation limit")
        guided_ready=len(mapped)==len(events) and within_step_bound
        automatic=guided_ready and not manual_gui
        execution_mode=("bounded-automatic" if automatic else "mixed-guided" if guided_ready
            else "review-only")
        candidates.append({"id":hashlib.sha256((transaction+"\0"+"\0".join(
                step["targetPath"] for step in steps)).encode()).hexdigest()[:20],
            "transactionId":transaction,"steps":steps,"stepCount":len(steps),
            "unmappedLinkedEvents":len(events)-len(mapped),"exactOrderObserved":True,
            "allStepsGenerationReady":len(mapped)==len(events),
            "stateContinuityLinks":_continuity(steps),"operatorStartRequired":True,
            "manualGuiActivationRequired":manual_gui,"selection":_selection(steps,request),
            "guidedTrialGenerationReady":guided_ready,"executionMode":execution_mode,
            "automaticallyExecutable":automatic,"executionReady":guided_ready,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
            "blockers":blockers})
    candidates.sort(key=lambda item:(-item["selection"]["requestScore"],
        not item["executionReady"],not item["automaticallyExecutable"],
        item["transactionId"],item["id"]))
    selected=next((item for item in candidates if item["executionReady"]),None)
    if selected:planning_status="execution-ready-candidates"
    elif candidates:planning_status="review-only-candidates"
    elif multi_event_transactions:planning_status="no-multi-step-generation-ready-contract"
    elif singleton_transactions:planning_status="singleton-transactions-only"
    elif history:planning_status="no-explicit-linkage"
    else:planning_status="no-interaction-events"
    false_claims={field:False for field in FALSE_CLAIMS}
    return {"schemaVersion":SCHEMA,"placeId":integrity["placeId"],
        "scanId":integrity["scanId"],"workflowCandidates":candidates,
        "summary":{"planningStatus":planning_status,"transactionGroups":len(groups),
            "linkedTransactions":multi_event_transactions,
            "singletonTransactions":singleton_transactions,
            "multiEventTransactions":multi_event_transactions,
            "transactionsWithInsufficientGenerationReadySteps":insufficient_contracts,
            "partiallyMappedTransactions":partially_mapped,
            "transactionsOverStepBound":over_step_bound,
            "workflowCandidates":len(candidates),"guidedTrialGenerationReadyWorkflows":sum(
                item["guidedTrialGenerationReady"] for item in candidates),
            "generationReadySteps":sum(item["stepCount"] for item in candidates),
            "unlinkedEvents":unlinked,"executionReadyWorkflows":sum(
                item["executionReady"] for item in candidates),
            "automaticallyExecutableWorkflows":sum(
                item["automaticallyExecutable"] for item in candidates),
            "requestAlignedWorkflows":sum(item["selection"]["requestAligned"] for item in candidates),
            "selectedExecutionCandidateId":selected["id"] if selected else None},
        "claims":false_claims,"limitations":[
            "Only explicit shared transaction IDs and recorded sequence values establish ordering",
            "A transaction ID present on only one event does not establish cross-event linkage",
            "State continuity is descriptive client-visible evidence, not causal proof",
            "GUI steps require normal user activation because GuiButton has no public activation method",
            "Tool and prompt steps are bounded runtime attempts; successful gameplay remains unverified"]}

def main():
    import argparse,pathlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("actions");parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=plan(json.loads(pathlib.Path(args.plan).read_text()),
        json.loads(pathlib.Path(args.actions).read_text()))
    pathlib.Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":main()
