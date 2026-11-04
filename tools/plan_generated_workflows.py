#!/usr/bin/env python3
"""Plan reviewable multi-control workflows from explicit linked observations."""
import copy
import hashlib
import json
import unicodedata

SCHEMA="114.generated-workflow-plan.1"
MAX_EVENTS=2000
FALSE_CLAIMS=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified")

def _text(value,limit):
    return (isinstance(value,str) and 1<=len(value.encode("utf-8"))<=limit
        and all(unicodedata.category(character)!="Cc" for character in value))

def _scalar(value):
    return type(value) in (int,float,str,bool) and len(str(value))<=200

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
    return {"sequence":sequence,"transactionOrder":transaction_order,
        "observedSequence":event["sequence"],"targetPath":target["path"],
        "targetLabel":target["label"],"controlType":target["controlType"],"kind":kind,
        "pathIdentity":copy.deepcopy(target["pathIdentity"]),
        "prerequisiteMetadata":copy.deepcopy(target[metadata_key]),
        "selectedOutcome":{"key":outcome["key"],"change":outcome["change"],
            "stateIdentity":copy.deepcopy(outcome["stateIdentity"]),
            "observedBefore":observed["before"] if observed else None,
            "observedAfter":observed["after"] if observed else None},
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
    candidates=[]
    for transaction,events in sorted(groups.items()):
        sequences=[event["sequence"] for event in events]
        if len(set(sequences))!=len(sequences):
            raise ValueError("Duplicate sequence in linked transaction")
        events.sort(key=lambda item:item["sequence"])
        mapped=[]
        for transaction_order,event in enumerate(events,1):
            key=(event.get("path"),event.get("controlType"))
            if key in targets:mapped.append((transaction_order,event,targets[key]))
        if len(mapped)<2:continue
        steps=[_step(event,index+1,transaction_order,*target_data)
            for index,(transaction_order,event,target_data) in enumerate(mapped)]
        blockers=["Cross-step gameplay semantics are unverified",
            "Observed order and state continuity do not prove causality"]
        if len(mapped)!=len(events):
            blockers.append("One or more linked events lack exact generation-ready contracts")

        if any(step["manualActivationRequired"] for step in steps):
            blockers.append("At least one GUI step requires normal user activation")
        guided_ready=(len(mapped)==len(events) and all(
            step["kind"]=="guided-gui-activation-trial" for step in steps))
        candidates.append({"id":hashlib.sha256((transaction+"\0"+"\0".join(
                step["targetPath"] for step in steps)).encode()).hexdigest()[:20],
            "transactionId":transaction,"steps":steps,"stepCount":len(steps),
            "unmappedLinkedEvents":len(events)-len(mapped),"exactOrderObserved":True,
            "allStepsGenerationReady":len(mapped)==len(events),
            "stateContinuityLinks":_continuity(steps),"operatorStartRequired":True,
            "manualGuiActivationRequired":any(step["manualActivationRequired"] for step in steps),
            "guidedTrialGenerationReady":guided_ready,
            "automaticallyExecutable":False,"executionReady":False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
            "blockers":blockers})
    false_claims={field:False for field in FALSE_CLAIMS}
    return {"schemaVersion":SCHEMA,"placeId":integrity["placeId"],
        "scanId":integrity["scanId"],"workflowCandidates":candidates,
        "summary":{"linkedTransactions":len(groups),"workflowCandidates":len(candidates),
            "guidedTrialGenerationReadyWorkflows":sum(
                item["guidedTrialGenerationReady"] for item in candidates),
            "generationReadySteps":sum(item["stepCount"] for item in candidates),
            "unlinkedEvents":unlinked,"executionReadyWorkflows":0},
        "claims":false_claims,"limitations":[
            "Only explicit transaction IDs and recorded sequence values establish ordering",
            "State continuity is descriptive client-visible evidence, not causal proof",
            "No multi-step workflow is emitted as executable gameplay automation"]}

def main():
    import argparse,pathlib
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan");parser.add_argument("actions");parser.add_argument("--output",required=True)
    args=parser.parse_args()
    result=plan(json.loads(pathlib.Path(args.plan).read_text()),
        json.loads(pathlib.Path(args.actions).read_text()))
    pathlib.Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")

if __name__=="__main__":main()
