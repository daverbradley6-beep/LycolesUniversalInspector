#!/usr/bin/env python3
"""Build a display-only generated result for the in-game inspector."""
import copy
import hashlib
import unicodedata

SCHEMA="113.generated-result.1"
_FALSE_CLAIMS=("sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
               "runtimeVerified","gameplayVerified","actionOutcomesVerified")


def _bounded_text(value,limit):
    return (isinstance(value,str) and 1<=len(value.encode("utf-8"))<=limit
            and all(unicodedata.category(character)!="Cc" for character in value))



def _validate_feedback_correlation(correlation):
    if correlation is None:return
    if not isinstance(correlation,dict) or type(correlation.get("available")) is not bool:
        raise ValueError("Invalid guided feedback correlation")
    claims=correlation.get("claims")
    if (not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in _FALSE_CLAIMS)):
        raise ValueError("Invalid guided feedback correlation claims")
    if correlation["available"] is False:
        if (correlation.get("readinessImpact")!="none"
                or not _bounded_text(correlation.get("reason"),160)):
            raise ValueError("Invalid unavailable guided feedback correlation")
        return
    if (correlation.get("schemaVersion")!="116.guided-workflow-feedback-aggregate.1"
            or correlation.get("readinessImpact")!="informational-only"
            or not isinstance(correlation.get("workflowPlanSHA256"),str)
            or len(correlation["workflowPlanSHA256"])!=64
            or any(character not in "0123456789abcdef"
                for character in correlation["workflowPlanSHA256"])
            or not _bounded_text(correlation.get("candidateId"),160)
            or type(correlation.get("completeSequenceRecurrenceObserved")) is not bool):
        raise ValueError("Invalid available guided feedback correlation")
    summary=correlation.get("summary");steps=correlation.get("steps")
    summary_fields=("sessions","runs","submittedEntries","activationEventsObserved",
        "expectedChangesObserved","completeClientObservationSequences",
        "sessionsWithCompleteClientObservationSequence","stepsWithStatusConflict")
    if (not isinstance(summary,dict) or any(type(summary.get(field)) is not int
            or not 0<=summary[field]<=1_000_000 for field in summary_fields)
            or not isinstance(steps,list) or not 1<=len(steps)<=40
            or correlation["completeSequenceRecurrenceObserved"]
                is not (summary["sessionsWithCompleteClientObservationSequence"]>=2)):
        raise ValueError("Invalid guided feedback correlation summary")
    allowed_statuses={"expected-change-observed","outcome-not-observed","activation-timeout",
        "control-or-state-unavailable","metadata-drift","state-unreadable"}
    step_attempts=step_activations=step_changes=step_conflicts=0
    for index,step in enumerate(steps,1):
        statuses=step.get("statuses") if isinstance(step,dict) else None
        counts=("attempts","sessionsObserved","activationEventsObserved",
            "expectedChangesObserved","sessionsWithExpectedChange")
        if (not isinstance(step,dict) or step.get("stepSequence")!=index
                or not _bounded_text(step.get("targetPath"),512)
                or not _bounded_text(step.get("outcomeKey"),256)
                or step.get("expected") not in ("increased","decreased","changed")
                or not isinstance(statuses,dict)
                or any(status not in allowed_statuses or type(count) is not int or count<1
                    for status,count in statuses.items())
                or any(type(step.get(field)) is not int or not 0<=step[field]<=1_000_000
                    for field in counts)
                or sum(statuses.values())!=step["attempts"]
                or not step["expectedChangesObserved"]<=step["activationEventsObserved"]<=step["attempts"]
                or step["sessionsWithExpectedChange"]>step["sessionsObserved"]
                or not isinstance(step.get("observedScalarTypes"),list)
                or any(kind not in ("boolean","number","string")
                    for kind in step["observedScalarTypes"])
                or step["observedScalarTypes"]!=sorted(set(step["observedScalarTypes"]))
                or any(type(step.get(field)) is not bool for field in
                    ("statusConflictObserved","statusConflictAcrossSessions",
                     "scalarTypeConflictObserved","expectedDirectionAcrossMultipleSessions"))
                or step["statusConflictObserved"] is not (len(statuses)>1)
                or step["scalarTypeConflictObserved"] is not (len(step["observedScalarTypes"])>1)
                or step["expectedDirectionAcrossMultipleSessions"]
                    is not (step["sessionsWithExpectedChange"]>=2)):
            raise ValueError("Invalid guided feedback correlation step")
        step_attempts+=step["attempts"];step_activations+=step["activationEventsObserved"]
        step_changes+=step["expectedChangesObserved"]
        step_conflicts+=step["statusConflictObserved"]
    if (summary["sessions"]<1
            or summary["sessionsWithCompleteClientObservationSequence"]>summary["sessions"]
            or summary["completeClientObservationSequences"]>summary["runs"]
            or summary["expectedChangesObserved"]>summary["activationEventsObserved"]
            or summary["activationEventsObserved"]>summary["submittedEntries"]
            or (step_attempts,step_activations,step_changes,step_conflicts)!=(
                summary["submittedEntries"],summary["activationEventsObserved"],
                summary["expectedChangesObserved"],summary["stepsWithStatusConflict"])):
        raise ValueError("Inconsistent guided feedback correlation summary")


def _validate_generation_readiness(place_id,scan_id,requested_capability,readiness):
    if (not isinstance(readiness,dict)
            or readiness.get("schemaVersion")!="113.generation-readiness.1"
            or readiness.get("placeId")!=place_id or readiness.get("scanId")!=scan_id):
        raise ValueError("Invalid generation-readiness identity")
    claims=readiness.get("claims")
    if (not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in _FALSE_CLAIMS)):
        raise ValueError("Invalid generation-readiness claims")
    _validate_feedback_correlation(readiness.get("guidedWorkflowFeedbackCorrelation"))
    request=readiness.get("request")
    if (not isinstance(request,dict) or request.get("request")!=requested_capability
            or request.get("status") not in ("no-capability-requested","generated-bounded-subset",
                "evidence-only-no-replay-contract","unsupported-by-current-evidence")
            or request.get("fullRequestImplemented") is not False
            or request.get("implementationReady") is not False
            or any(request.get(field) is not False for field in
                   ("runtimeVerified","gameplayVerified","causalityProven","actionOutcomesVerified"))):
        raise ValueError("Invalid generation-readiness request")
    subset=request.get("supportedSubset")
    matched=request.get("matchedGeneratedCapabilityIds")
    if (not isinstance(subset,list) or len(subset)>16
            or any(not _bounded_text(item,160) for item in subset)
            or not isinstance(matched,list) or len(matched)>64
            or any(not _bounded_text(item,80) for item in matched)
            or type(request.get("generatedSubsetAvailable")) is not bool):
        raise ValueError("Invalid generation-readiness subset")
    generated=readiness.get("generatedCapabilities")
    if not isinstance(generated,list) or len(generated)>64:
        raise ValueError("Invalid generation-readiness capabilities")
    for item in generated:
        if (not isinstance(item,dict) or not _bounded_text(item.get("id"),80)
                or any(item.get(field) is not False for field in
                       ("runtimeVerified","gameplayVerified","causalityProven","actionOutcomeVerified"))):
            raise ValueError("Invalid generation-readiness capability")
        kind=item.get("kind")
        if kind=="mixed-action-workflow-trial":
            paths=item.get("targetPaths");step_kinds=item.get("stepKinds")
            matched_terms=item.get("requestMatchedTerms");match_score=item.get("requestMatchScore")
            if (not _bounded_text(item.get("candidateId"),120)
                    or not _bounded_text(item.get("transactionId"),200)
                    or item.get("executionMode") not in ("mixed-guided","bounded-automatic")
                    or not isinstance(item.get("stepCount"),int)
                    or not 2<=item["stepCount"]<=128
                    or not isinstance(paths,list) or len(paths)!=item["stepCount"]
                    or any(not _bounded_text(path,500) for path in paths)
                    or not isinstance(step_kinds,list) or len(step_kinds)!=item["stepCount"]
                    or any(step_kind not in ("guided-gui-activation-trial",
                        "official-tool-activation-trial","proximity-prompt-trial")
                        for step_kind in step_kinds)
                    or not isinstance(matched_terms,list) or len(matched_terms)>128
                    or any(not _bounded_text(term,80) or not all(
                        "a"<=character<="z" or "0"<=character<="9" for character in term)
                        for term in matched_terms)
                    or matched_terms!=sorted(set(matched_terms))
                    or type(match_score) is not int or not 0<=match_score<=10_000
                    or (match_score>0)!=bool(matched_terms)
                    or type(item.get("manualGuiActivationRequired")) is not bool
                    or item.get("automaticallyExecutable") is not (
                        not item["manualGuiActivationRequired"])
                    or item["executionMode"]!=("mixed-guided"
                        if item["manualGuiActivationRequired"] else "bounded-automatic")
                    or item.get("operatorStartRequired") is not True
                    or item.get("stopOnFirstUnobservedOutcome") is not True):
                raise ValueError("Invalid workflow generation-readiness capability")
            continue
        if (kind not in ("proximity-prompt-trial","official-tool-activation-trial",
                    "guided-gui-activation-trial")
                or not _bounded_text(item.get("targetLabel"),120)
                or not _bounded_text(item.get("selectedOutcomeKey"),200)
                or item.get("expectedChange") not in ("increased","decreased","changed")):
            raise ValueError("Invalid generation-readiness capability")
        if (kind=="guided-gui-activation-trial"
                and (item.get("automaticActivation") is not False
                    or item.get("manualActivationRequired") is not True
                    or item.get("exactControlHighlighting") is not True)):
            raise ValueError("Invalid guided GUI generation-readiness capability")

    generated_ids=[item["id"] for item in generated]
    status=request["status"]
    if (len(set(generated_ids))!=len(generated_ids) or len(set(matched))!=len(matched)
            or any(identifier not in generated_ids for identifier in matched)
            or (requested_capability is None)!=(status=="no-capability-requested")
            or (status=="generated-bounded-subset")!=(request["generatedSubsetAvailable"] is True)
            or (status=="generated-bounded-subset")!=(len(matched)>0)
            or (status=="generated-bounded-subset")!=(len(subset)>0)):
        raise ValueError("Inconsistent generation-readiness subset")

    unavailable=readiness.get("unavailableRequestedBehavior")
    if (not isinstance(unavailable,list) or len(unavailable)>16
            or any(not isinstance(item,dict) or not _bounded_text(item.get("id"),80)
                   or item.get("status")!="unavailable" for item in unavailable)):
        raise ValueError("Invalid unavailable requested behavior")
    discovery=readiness.get("discoveryOnlyCapabilities")
    if not isinstance(discovery,list) or len(discovery)>16:
        raise ValueError("Invalid discovery-only capabilities")
    for item in discovery:
        if (not isinstance(item,dict) or not _bounded_text(item.get("family"),80)
                or type(item.get("candidateCount")) is not int or not 0<=item["candidateCount"]<=1_000_000
                or type(item.get("observedCount")) is not int or not 0<=item["observedCount"]<=item["candidateCount"]
                or item.get("replayContractAvailable") is not False):
            raise ValueError("Invalid discovery-only capability")
    return copy.deepcopy(readiness)


def build(place_id,scan_id,code,requested_capability,validation,capabilities,
          generation_readiness):
    if type(place_id) is not int or not 1<=place_id<=2**53:
        raise ValueError("Invalid generated-result place ID")
    if not isinstance(scan_id,str) or not 1<=len(scan_id)<=128:
        raise ValueError("Invalid generated-result scan ID")
    if not isinstance(code,str) or not 1<=len(code.encode("utf-8"))<=1_000_000:
        raise ValueError("Invalid generated-result code")
    if f"assert(game.PlaceId == {place_id}" not in code:
        raise ValueError("Generated-result code lacks place guard")
    if requested_capability is not None and (not isinstance(requested_capability,str)
            or not 1<=len(requested_capability.encode("utf-8"))<=240):
        raise ValueError("Invalid generated-result request")
    if not isinstance(validation,dict) or validation.get("placeGuard") is not True:
        raise ValueError("Generated-result static validation missing")
    if (not isinstance(capabilities,list) or len(capabilities)>64
            or any(not isinstance(value,str) or not 1<=len(value)<=120 for value in capabilities)):
        raise ValueError("Invalid generated-result capabilities")
    readiness=_validate_generation_readiness(
        place_id,scan_id,requested_capability,generation_readiness)
    return {
        "schemaVersion":SCHEMA,"placeId":place_id,"scanId":scan_id,
        "requestedCapability":requested_capability,"generatedCode":code,
        "generatedCodeSHA256":hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "capabilities":capabilities,"staticValidationPassed":True,
        "staticValidation":validation,"generationReadiness":readiness,
        "unsupportedBehavior":["server administrator authority","unreviewed remote invocation",
            "verified gameplay automation","verified action outcomes"],
        "packageAuthenticityVerified":False,"runtimeVerified":False,
        "gameplayVerified":False,"executionAuthorized":False,
        "note":"Display-only offline result; digest is not authenticated by the in-game loader",
    }
