#!/usr/bin/env python3
"""Build a display-only generated result for the in-game inspector."""
import hashlib

SCHEMA="110.generated-result.1"


def build(place_id,scan_id,code,requested_capability,validation,capabilities):
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
    return {
        "schemaVersion":SCHEMA,"placeId":place_id,"scanId":scan_id,
        "requestedCapability":requested_capability,"generatedCode":code,
        "generatedCodeSHA256":hashlib.sha256(code.encode("utf-8")).hexdigest(),
        "capabilities":capabilities,"staticValidationPassed":True,
        "staticValidation":validation,
        "unsupportedBehavior":["server administrator authority","unreviewed remote invocation",
            "verified gameplay automation","verified action outcomes"],
        "packageAuthenticityVerified":False,"runtimeVerified":False,
        "gameplayVerified":False,"executionAuthorized":False,
        "note":"Display-only offline result; digest is not authenticated by the in-game loader",
    }
