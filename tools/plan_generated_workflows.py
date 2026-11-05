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
MAX_ADJACENCY_CANDIDATES=100
ADJACENCY_WINDOW_SECONDS=15
FALSE_CLAIMS=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified")

def _text(value,limit):
    return (isinstance(value,str) and 1<=len(value.encode("utf-8"))<=limit
        and all(unicodedata.category(character)!="Cc" for character in value))

def _scalar(value):
    return type(value) in (int,float,str,bool) and len(str(value))<=200

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
    "travelled":"travel","upgrading":"upgrade","upgraded":"upgrade",
}


def _token_forms(token):
    forms={token}
    if len(token)>4 and token.endswith("ies"):
        forms.add(token[:-3]+"y")
    if len(token)>4 and token.endswith("es"):
        forms.add(token[:-2])
    if len(token)>4 and token.endswith("s") and not token.endswith("ss"):
        forms.add(token[:-1])
    if len(token)>5 and token.endswith("ing"):
        stem=token[:-3];forms.update((stem,stem+"e"))
    if len(token)>4 and token.endswith("ed"):
        stem=token[:-2];forms.update((stem,stem+"e"))
    return forms


def _tokens(value):
    if not isinstance(value,str):return set()
    result=set()
    for token in re.findall(r"[a-z0-9]+",value.lower())[:128]:
        for form in _token_forms(token):
            canonical=_TOKEN_ALIASES.get(form,form)
            if len(canonical)>=2 and canonical not in _STOP_WORDS:
                result.add(canonical)
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



def _gui_metadata_matches(observed, expected, text_dynamic):
    if not isinstance(observed,dict) or not isinstance(expected,dict):
        return False
    if observed.get("controlClass")!=expected.get("controlClass"):
        return False
    if not text_dynamic and observed.get("text")!=expected.get("text"):
        return False
    for key in ("visible","active","selectable","autoButtonColor",
            "ancestorVisible","screenEnabled","withinScrollingBounds",
            "effectiveVisible"):
        if observed.get(key)!=expected.get(key):
            return False
    if "interactable" in expected and observed.get("interactable")!=expected.get("interactable"):
        return False
    return True


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
            if kind=="guided-gui-activation-trial" and type(target.get("guiMetadataTextDynamic",False)) is not bool:
                raise ValueError("Malformed generation-ready action target")
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
    metadata_matches=(
        _gui_metadata_matches(event.get("controlMetadata"),target[metadata_key],
            target.get("guiMetadataTextDynamic",False))
        if kind=="guided-gui-activation-trial"
        else event.get("controlMetadata")==target[metadata_key]
    )
    if (_identity(event.get("pathIdentity"))!=_identity(target["pathIdentity"])
            or not metadata_matches
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

def _temporal_adjacency(history):
    timed=[]
    for index,event in enumerate(history):
        present="sessionId" in event or "sessionElapsedSeconds" in event
        if not present:continue
        session=event.get("sessionId");elapsed=event.get("sessionElapsedSeconds")
        if (not _text(session,80) or type(elapsed) not in (int,float) or type(elapsed) is bool
                or not math.isfinite(elapsed) or not 0<=elapsed<=604_800):
            raise ValueError("Malformed interaction session timing")
        transaction=event.get("transactionId")
        marker=(str(transaction) if type(transaction) in (int,str) and _text(str(transaction),80)
            else "unlinked-"+str(index))
        sequence=event.get("sequence") if type(event.get("sequence")) is int else None
        timed.append({"sessionId":session,"elapsed":elapsed,"transaction":marker,
            "sequence":sequence,"path":event.get("path") if _text(event.get("path"),400) else None,
            "controlType":event.get("controlType") if _text(event.get("controlType"),120) else None})
    timed.sort(key=lambda item:(item["sessionId"],item["elapsed"],item["sequence"] is None,
        item["sequence"] or 0,item["path"] or ""))
    candidates=[];count=0
    for previous,current in zip(timed,timed[1:]):
        gap=current["elapsed"]-previous["elapsed"]
        if (previous["sessionId"]!=current["sessionId"]
                or previous["transaction"]==current["transaction"]
                or not 0<=gap<=ADJACENCY_WINDOW_SECONDS):continue
        count+=1
        if len(candidates)<MAX_ADJACENCY_CANDIDATES:
            candidates.append({"gapSeconds":round(gap,3),
                "first":{"sequence":previous["sequence"],"path":previous["path"],
                    "controlType":previous["controlType"]},
                "second":{"sequence":current["sequence"],"path":current["path"],
                    "controlType":current["controlType"]},
                "classification":"unlinked-temporal-adjacency",
                "usedForWorkflowLinkage":False,"causalityProven":False})
    return {"timedEvents":len(timed),"windowSeconds":ADJACENCY_WINDOW_SECONDS,
        "unlinkedAdjacentPairs":count,"candidates":candidates,
        "candidatesTruncated":count>len(candidates),"usedForWorkflowLinkage":False,
        "causalityProven":False}

def _identity_prefix(prefix,target):
    return (len(prefix)<=len(target) and all(left==right
        for left,right in zip(prefix,target)))


def _gui_reveal_followups(history):
    if not any(event.get("guiRevealFollowup") is not None for event in history):
        return {"candidateCount":0,"candidates":[],"candidatesTruncated":False,
            "evidenceRule":"observed visible transition plus exact descendant component identity",
            "usedForWorkflowLinkage":False,"causalityProven":False}
    by_sequence={}
    for event in history:
        sequence=event.get("sequence")
        if type(sequence) is int:
            if sequence in by_sequence:raise ValueError("Duplicate interaction sequence")
            by_sequence[sequence]=event
    candidates=[];count=0
    for target in history:
        evidence=target.get("guiRevealFollowup")
        if evidence is None:continue
        if not isinstance(evidence,dict):raise ValueError("Malformed GUI reveal followup")
        source_sequence=evidence.get("sourceSequence");target_sequence=target.get("sequence")
        source=by_sequence.get(source_sequence)
        source_identity=_identity(evidence.get("sourcePathIdentity"))
        revealed_identity=_identity(evidence.get("revealedPathIdentity"))
        target_identity=_identity(target.get("pathIdentity"))
        source_event_identity=_identity(source.get("pathIdentity")) if source else None
        elapsed=evidence.get("elapsedSinceSourceSeconds")
        observation_window=evidence.get("sourceObservationWindowSeconds")
        claims=(evidence.get("explicitlyLinked") is False
            and evidence.get("temporalCorrelationOnly") is True
            and evidence.get("causalityProven") is False
            and evidence.get("runtimeVerified") is False
            and evidence.get("gameplayVerified") is False)
        path_names=".".join(item["name"] for item in revealed_identity or [])
        source_path_names=".".join(item["name"] for item in source_identity or [])
        target_path_names=".".join(item["name"] for item in target_identity or [])
        source_changes=source.get("guiStateChanges",[]) if source else None
        if not isinstance(source_changes,list) or len(source_changes)>48:
            raise ValueError("Malformed GUI reveal followup")
        matching_changes=[change for change in source_changes
            if isinstance(change,dict) and _identity(change.get("pathIdentity"))==revealed_identity
            and change.get("path")==evidence.get("revealedPath")
            and change.get("afterVisible") is True and change.get("beforeVisible") is not True]
        valid_timing=(source and source.get("sessionId")==target.get("sessionId")
            and type(source.get("sessionElapsedSeconds")) in (int,float)
            and type(source.get("sessionElapsedSeconds")) is not bool
            and type(target.get("sessionElapsedSeconds")) in (int,float)
            and type(target.get("sessionElapsedSeconds")) is not bool
            and math.isfinite(source["sessionElapsedSeconds"])
            and math.isfinite(target["sessionElapsedSeconds"])
            and round(target["sessionElapsedSeconds"]-source["sessionElapsedSeconds"],3)==elapsed)
        if (type(source_sequence) is not int or type(target_sequence) is not int
                or source_sequence>=target_sequence or not source
                or not _text(source.get("path"),400) or evidence.get("sourcePath")!=source.get("path")
                or source_identity is None or source_identity!=source_event_identity
                or source_path_names!=source.get("path")
                or revealed_identity is None or target_identity is None
                or not _text(target.get("path"),400) or target_path_names!=target.get("path")
                or not _identity_prefix(revealed_identity,target_identity)
                or not _text(evidence.get("revealedPath"),400)
                or path_names!=evidence.get("revealedPath") or len(matching_changes)!=1
                or type(elapsed) not in (int,float) or type(elapsed) is bool
                or not math.isfinite(elapsed) or not 0<=elapsed<=ADJACENCY_WINDOW_SECONDS
                or observation_window not in (0.35,1.25,3.0)
                or not valid_timing or not claims
                or evidence.get("classification")!="observed-gui-reveal-descendant-followup"):
            raise ValueError("Malformed GUI reveal followup")
        count+=1
        if len(candidates)<MAX_ADJACENCY_CANDIDATES:
            candidates.append({"sourceSequence":source_sequence,"targetSequence":target_sequence,
                "sourcePath":source["path"],"targetPath":target.get("path"),
                "revealedPath":evidence["revealedPath"],
                "sourceObservationWindowSeconds":observation_window,
                "elapsedSinceSourceSeconds":elapsed,
                "classification":"observed-gui-reveal-descendant-followup",
                "usedForWorkflowLinkage":False,"causalityProven":False})
    return {"candidateCount":count,"candidates":candidates,
        "candidatesTruncated":count>len(candidates),
        "evidenceRule":"observed visible transition plus exact descendant component identity",
        "usedForWorkflowLinkage":False,"causalityProven":False}


def _explicit_recording(events,transaction):
    marked=any(event.get("transactionLinkSource")=="explicit-user-armed-recording"
        or event.get("explicitWorkflowRecording") is not None
        or transaction.startswith("user-recorded-") for event in events)
    if not marked:return False
    if not transaction.startswith("user-recorded-") or len(events)>8:
        raise ValueError("Malformed explicit workflow recording")
    ordered=sorted(events,key=lambda item:item.get("sequence",0))
    session=ordered[0].get("sessionId");started=None
    for order,event in enumerate(ordered,1):
        record=event.get("explicitWorkflowRecording")
        elapsed=event.get("sessionElapsedSeconds")
        if (event.get("transactionLinkSource")!="explicit-user-armed-recording"
                or event.get("transactionOrder")!=order or not isinstance(record,dict)
                or record.get("recordingId")!=transaction or record.get("order")!=order
                or record.get("linkageSource")!="explicit-user-armed-recording"
                or record.get("explicitUserArmed") is not True
                or record.get("establishesOrdering") is not True
                or record.get("causalityProven") is not False
                or record.get("runtimeVerified") is not False
                or record.get("gameplayVerified") is not False
                or record.get("maxDurationSeconds")!=60 or record.get("maxEvents")!=8
                or event.get("sessionId")!=session or not _text(session,128)
                or type(elapsed) not in (int,float) or type(elapsed) is bool
                or not math.isfinite(elapsed)):
            raise ValueError("Malformed explicit workflow recording")
        item_started=record.get("startedElapsedSeconds")
        if (type(item_started) not in (int,float) or type(item_started) is bool
                or not math.isfinite(item_started) or item_started<0
                or elapsed<item_started or elapsed-item_started>60):
            raise ValueError("Malformed explicit workflow recording")
        if started is None:started=item_started
        elif item_started!=started:raise ValueError("Malformed explicit workflow recording")
    return True


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
    temporal_adjacency=_temporal_adjacency(history)
    gui_reveal_followups=_gui_reveal_followups(history)
    candidates=[];insufficient_contracts=0;partially_mapped=0;over_step_bound=0
    explicit_recording_transactions=0
    singleton_transactions=sum(len(events)==1 for events in groups.values())
    multi_event_transactions=sum(len(events)>1 for events in groups.values())
    for transaction,events in sorted(groups.items()):
        explicit_recording=_explicit_recording(events,transaction)
        if explicit_recording:explicit_recording_transactions+=1
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
            "transactionId":transaction,
            "linkageSource":"explicit-user-armed-recording" if explicit_recording
                else "observed-shared-transaction",
            "steps":steps,"stepCount":len(steps),
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
            "explicitRecordingTransactions":explicit_recording_transactions,
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
            "guiRevealFollowupCandidates":gui_reveal_followups["candidateCount"],
            "selectedExecutionCandidateId":selected["id"] if selected else None},
        "temporalAdjacency":temporal_adjacency,
        "guiRevealFollowups":gui_reveal_followups,
        "claims":false_claims,"limitations":[
            "Only explicit shared transaction IDs and recorded sequence values establish ordering",
            "User-armed recording establishes intended order only, not causality or gameplay success",
            "Session-relative temporal adjacency is review evidence and never creates workflow linkage",
            "Observed GUI reveal and descendant followup evidence remains review-only and unlinked",
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
