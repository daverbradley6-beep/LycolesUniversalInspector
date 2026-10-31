#!/usr/bin/env python3
"""Merge independently verified dynamic observation plans with a full baseline.

This is an evidence overlay, not object reconstruction or gameplay execution.
"""
import copy

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
                         "interactionEvents":integrity.get("interactionEvents",0)})
    result["features"]=sorted(by_name.values(),key=lambda x:x["feature"])
    result["featureCount"]=len(result["features"])
    result["evidenceOverlays"]=overlays
    result["releaseGate"]={"gameplayAutomationApproved":False,
      "reason":"Correlated client observations do not establish executable server action contracts"}
    return result
