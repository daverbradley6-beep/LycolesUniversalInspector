#!/usr/bin/env python3
"""Compile bounded, inspectable interaction workflows from a validated capability plan.

This stage describes evidence; it never invents executable remote calls.
"""
import json
import pathlib
import sys

MAX_FEATURES=5000
MAX_LABEL=160

def compile_workflows(plan):
    integrity=plan.get("integrity",{})
    if integrity.get("scanComplete") is not True or type(integrity.get("placeId")) is not int:
        raise ValueError("Complete validated plan with place ID required")
    features=plan.get("features")
    if not isinstance(features,list) or len(features)>MAX_FEATURES:
        raise ValueError("Invalid feature inventory")
    workflows=[]
    for item in features:
        if not isinstance(item,dict) or not isinstance(item.get("feature"),str):
            raise ValueError("Malformed feature record")
        name=item["feature"][:MAX_LABEL]
        observed=item.get("interactionEvents",0)
        corroborated=item.get("clientCorroboratedEvents",0)
        transitions=item.get("temporalTransitionEvents",0)
        verified=item.get("verifiedClientOutcomes",0)
        if any(type(x) is not int or x<0 for x in (observed,corroborated,transitions,verified)):
            raise ValueError("Invalid evidence counters")
        if corroborated>observed or transitions>observed or verified>observed:
            raise ValueError("Inconsistent evidence counters")
        evidence_level=("client-outcome-observed" if verified else
                        "client-state-corroborated" if corroborated else
                        "temporal-transition-observed" if transitions else
                        "interaction-observed" if observed else "discovered-only")
        workflows.append({
            "feature":name,
            "evidenceLevel":evidence_level,
            "observedInteractions":observed,
            "corroboratedInteractions":corroborated,
            "temporalTransitions":transitions,
            "clientOutcomes":verified,
            "reproducibleActionContract":False,
            "automaticallyExecutable":False,
            "requiredValidation":[
                "Identify permitted and supported action interface",
                "Validate input constraints and failure behaviour",
                "Verify outcome in a real game session"
            ]
        })
    return {
        "schemaVersion":"13.0",
        "scanId":integrity.get("scanId"),
        "placeId":integrity["placeId"],
        "workflows":workflows,
        "summary":{"discovered":len(workflows),
                   "observed":sum(w["observedInteractions"]>0 for w in workflows),
                   "clientCorroborated":sum(w["corroboratedInteractions"]>0 for w in workflows),
                   "automaticallyExecutable":0},
        "notice":"Passive client observations are not executable server action contracts."
    }

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("plan");p.add_argument("--output",default="build/workflow-specs.json")
    a=p.parse_args()
    try:
        data=json.loads(pathlib.Path(a.plan).read_text(encoding="utf-8"))
        result=compile_workflows(data)
        dest=pathlib.Path(a.output);dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n",encoding="utf-8")
        print("Workflow specifications:",dest)
        return 0
    except (OSError,ValueError,TypeError,KeyError) as exc:
        print("WORKFLOW BUILD BLOCKED:",exc,file=sys.stderr)
        return 2
if __name__=="__main__":sys.exit(main())
