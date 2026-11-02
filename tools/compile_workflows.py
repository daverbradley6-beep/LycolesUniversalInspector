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
        candidates=item.get("observableOutcomeCandidates",0)
        state_correlations=item.get("featureStateCorrelations",0)
        gui_correlations=item.get("featureGuiCorrelations",0)
        counters=(observed,corroborated,transitions,verified,candidates,state_correlations,gui_correlations)
        if any(type(x) is not int or x<0 for x in counters):
            raise ValueError("Invalid evidence counters")
        if corroborated>observed or transitions>observed or verified>observed or candidates>observed:
            raise ValueError("Inconsistent evidence counters")
        if state_correlations>candidates or gui_correlations>candidates:
            raise ValueError("Inconsistent correlation counters")
        evidence_level=("client-outcome-observed" if verified else
                        "observable-outcome-candidate-unverified" if candidates else
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
            "observableOutcomeCandidates":candidates,
            "featureStateCorrelations":state_correlations,
            "featureGuiCorrelations":gui_correlations,
            "correlationSemantics":"Feature-consistent client-visible change; correlation, not causal proof",
            "sourceAuthenticityVerified":False,
            "causalityProven":False,
            "serverAuthorityVerified":False,
            "gameplayVerified":False,
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
                   "observableOutcomeCandidates":sum(w["observableOutcomeCandidates"] for w in workflows),
                   "featuresWithObservableOutcomeCandidates":sum(w["observableOutcomeCandidates"]>0 for w in workflows),
                   "automaticallyExecutable":0},
        "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
                  "serverAuthorityVerified":False,"gameplayVerified":False},
        "notice":"Passive client observations are not executable server action contracts."
    }

def render_review(workflows):
    """Produce an actionable per-game engineering backlog from passive evidence."""
    if not isinstance(workflows,dict) or not isinstance(workflows.get("workflows"),list):
        raise ValueError("Invalid workflow specifications")
    place=workflows.get("placeId")
    lines=["# Game-specific implementation review", "",
           "Place ID: "+str(place), "",
           "This report distinguishes observed client evidence from reproducible actions.",
           "No gameplay action is marked executable without a validated implementation contract.",
           "", "## Evidence-ranked features", ""]
    priority={"client-outcome-observed":0,"observable-outcome-candidate-unverified":1,
              "client-state-corroborated":2,"temporal-transition-observed":3,
              "interaction-observed":4,"discovered-only":5}
    ranked=sorted(workflows["workflows"],key=lambda w:(
        priority.get(w["evidenceLevel"],6),-w["observedInteractions"],w["feature"]))
    for i,w in enumerate(ranked,1):
        name=w["feature"].replace("\\n"," ").replace("\\r"," ").replace("#","").strip()
        lines.extend(["### "+str(i)+". "+name, "",
            "- Evidence: "+w["evidenceLevel"],
            "- Observed interactions: "+str(w["observedInteractions"]),
            "- Client corroboration: "+str(w["corroboratedInteractions"]),
            "- Temporal transitions: "+str(w["temporalTransitions"]),
            "- Observable outcome candidates: "+str(w.get("observableOutcomeCandidates",0)),
            "- Feature-state correlations: "+str(w.get("featureStateCorrelations",0)),
            "- Feature-GUI correlations: "+str(w.get("featureGuiCorrelations",0)),
            "- Candidate semantics: "+w.get("correlationSemantics","correlation, not causal proof"),
            "- Executable contract: not established",
            "- Next validation: "+", ".join(w["requiredValidation"]), ""])
    if not ranked: lines.append("No candidate features were identified.")
    lines.extend(["## Release decision", "",
       "Client diagnostic utilities may be generated; gameplay automation is not approved.",
       "A passive scan cannot prove server-authoritative operations or anti-cheat safety.", ""])
    return "\n".join(lines)

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
