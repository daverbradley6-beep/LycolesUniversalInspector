#!/usr/bin/env python3
"""Merge independently verified dynamic observation plans with a full baseline.

This is an evidence overlay, not object reconstruction or gameplay execution.
"""
import copy


_UNVERIFIED_PROVENANCE=("resumeCheckpointAuthenticated","receiverResponseAuthenticityVerified",
    "localPayloadEquivalent","sourceAuthenticityVerified","causalityProven",
    "serverAuthorityVerified","replayable","gameplayVerified","actionOutcomesVerified")

def _observation_provenance(observation,integrity):
    provenance=observation.get("sourceProvenance")
    mode=provenance.get("inputMode") if isinstance(provenance,dict) else None
    receiver=mode in ("receiver-import","receiver-import-legacy-v11")
    digest_receiver=mode=="receiver-import"
    digest_verified=provenance.get("receiverStoredPayloadDigestsVerified") if provenance else None
    integrity_verified=provenance.get("receiverIntegrityVerified") if provenance else None
    acknowledgement=provenance.get("receiverAcknowledgementDigestEquivalent") if provenance else None
    revalidated=provenance.get("receiverStoredPayloadDigestsRevalidatedThisRun") if provenance else None
    if (not isinstance(provenance,dict)
            or provenance.get("schemaVersion")!="30.2.source-provenance.1"
            or mode not in ("local-multipart","receiver-import","receiver-import-legacy-v11")
            or provenance.get("scanId")!=integrity.get("scanId")
            or provenance.get("placeId")!=integrity.get("placeId")
            or provenance.get("partCount")!=integrity.get("parts")
            or any(provenance.get(field) is not False for field in _UNVERIFIED_PROVENANCE)
            or type(digest_verified) is not bool or digest_verified is not digest_receiver
            or type(integrity_verified) is not bool or integrity_verified is not receiver
            or type(acknowledgement) is not bool or type(revalidated) is not bool
            or (mode!="receiver-import" and revalidated)
            or (not receiver and acknowledgement)):
        raise ValueError("Invalid observation source provenance")
    return copy.deepcopy(provenance)

def merge_evidence(baseline, observations):
    base=baseline.get("integrity") or {}
    if base.get("scanComplete") is not True or type(base.get("placeId")) is not int:
        raise ValueError("Complete baseline required")
    if (baseline.get("sourceDiagnostics") or {}).get("scanMode")=="dynamic-observations":
        raise ValueError("Dynamic observations cannot be a baseline")
    if not isinstance(observations,list) or len(observations)>64:
        raise ValueError("Invalid observation list")
    result=copy.deepcopy(baseline)
    by_name={x["feature"]:x for x in result.get("features",[])}
    seen={base.get("scanId")}
    overlays=[]
    keys=("interactionEvents","observedEvents","verifiedClientOutcomes",
          "clientCorroboratedEvents","temporalTransitionEvents")
    for obs in observations:
        integrity=obs.get("integrity") or {}
        sid=integrity.get("scanId")
        if integrity.get("scanComplete") is not True or integrity.get("placeId")!=base["placeId"]:
            raise ValueError("Observation incomplete or different game")
        if not isinstance(sid,str) or not sid or sid in seen:
            raise ValueError("Duplicate or missing scan ID")
        seen.add(sid)
        if (obs.get("sourceDiagnostics") or {}).get("scanMode")!="dynamic-observations":
            raise ValueError("Only dynamic observations may be overlaid")
        provenance=_observation_provenance(obs,integrity)
        for feature in obs.get("features",[]):
            name=feature.get("feature")
            if not isinstance(name,str) or not name:
                raise ValueError("Invalid feature")
            if name not in by_name:
                by_name[name]={"feature":name,"status":"observation-only",
                               "implementationReady":False,
                               "reason":"Observation evidence is not a reproducible action contract",
                               "evidence":None,"readiness":None,
                               **{key:0 for key in keys}}
            target=by_name[name]
            for key in keys:
                value=feature.get(key,0)
                if type(value) is not int or value<0:
                    raise ValueError("Invalid evidence count")
                old=target.get(key,0)
                if type(old) is not int or old<0: raise ValueError("Invalid baseline count")
                target[key]=old+value
            target["implementationReady"]=False
        overlays.append({"scanId":sid,"parts":integrity.get("parts"),
                         "interactionEvents":integrity.get("interactionEvents",0),
                         "sourceProvenance":provenance})
    result["features"]=sorted(by_name.values(),key=lambda x:x["feature"])
    result["featureCount"]=len(result["features"])
    result["evidenceOverlays"]=overlays
    result["releaseGate"]={"gameplayAutomationApproved":False,
      "reason":"Correlated client observations do not establish executable server action contracts"}
    return result
