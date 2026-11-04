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


def _validate_generation_readiness(place_id,scan_id,requested_capability,readiness):
    if (not isinstance(readiness,dict)
            or readiness.get("schemaVersion")!="113.generation-readiness.1"
            or readiness.get("placeId")!=place_id or readiness.get("scanId")!=scan_id):
        raise ValueError("Invalid generation-readiness identity")
    claims=readiness.get("claims")
    if (not isinstance(claims,dict)
            or any(claims.get(field) is not False for field in _FALSE_CLAIMS)):
        raise ValueError("Invalid generation-readiness claims")
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
                or item.get("kind") not in ("proximity-prompt-trial","official-tool-activation-trial",
                    "guided-gui-activation-trial")
                or not _bounded_text(item.get("targetLabel"),120)
                or not _bounded_text(item.get("selectedOutcomeKey"),200)
                or item.get("expectedChange") not in ("increased","decreased","changed")
                or any(item.get(field) is not False for field in
                       ("runtimeVerified","gameplayVerified","causalityProven","actionOutcomeVerified"))):
            raise ValueError("Invalid generation-readiness capability")
        if (item.get("kind")=="guided-gui-activation-trial"
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
