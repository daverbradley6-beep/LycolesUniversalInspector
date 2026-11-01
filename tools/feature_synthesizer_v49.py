#!/usr/bin/env python3
"""v49: deterministic feature candidates from passive observation, with strict evidence gates."""
import argparse,hashlib,json
from pathlib import Path
from adaptive_probe_v44 import paths

def synthesize(manifest, report):
    inventory=set(paths(manifest))
    if not isinstance(report,dict) or report.get("schemaVersion")!="48.0":
        raise ValueError("Expected v48 state-change report")
    for key in ("placeId","scanId","sourceFingerprint"):
        if type(report.get(key))!=type(manifest.get(key)) or report[key]!=manifest[key]:
            raise ValueError("Evidence identity mismatch: "+key)
    if report.get("gameplayAutomationApproved") is not False or report.get("mechanicVerified") is not False or report.get("serverOutcomeVerified") is not False:
        raise ValueError("Unverified claims in input")
    samples=report.get("samples")
    if type(samples) is not int or not 2<=samples<=121:
        raise ValueError("Invalid sample count")
    observations=report.get("paths")
    if not isinstance(observations,dict) or set(observations)!=inventory:
        raise ValueError("Incomplete evidence inventory")
    for path,item in observations.items():
        if not isinstance(item,dict):raise ValueError("Invalid path record")
        visible=item.get("visibleSamples")
        transitions=item.get("stateTransitions")
        if type(visible) is not int or not 0<=visible<=samples:
            raise ValueError("Invalid visibility")
        if type(transitions) is not int or not 0<=transitions<samples:
            raise ValueError("Invalid transitions")
        changed=item.get("valueChanged")
        if type(changed) is not bool:raise ValueError("Invalid valueChanged")
        classification="changing" if transitions else "stable-visible" if visible else "not-observed"
        if item.get("classification")!=classification:raise ValueError("Invalid classification")
        if changed and transitions==0:raise ValueError("Contradictory value change")
        if visible==0 and transitions==0 and changed:raise ValueError("Contradictory visibility")
    features=[]
    seen=set()
    for f in sorted(manifest["features"],key=lambda f:f["id"]):
        fid=f.get("id")
        if not isinstance(fid,str) or fid in seen or f.get("kind")!="read-only-inspection" or f.get("gameplayVerified") is not False:
            raise ValueError("Invalid feature")
        seen.add(fid)
        pp=f.get("evidencePaths")
        if not isinstance(pp,list) or not pp or len(pp)!=len(set(pp)) or any(p not in inventory for p in pp):
            raise ValueError("Invalid feature paths")
        active=sorted(p for p in pp if observations[p]["stateTransitions"]>0)
        stable=sorted(p for p in pp if observations[p]["classification"]=="stable-visible")
        missing=sorted(p for p in pp if observations[p]["classification"]=="not-observed")
        features.append({"id":fid,"family":f.get("family",fid),"candidateKind":"observed-client-state",
            "readOnly":True,"observedChangingPaths":active,"stablePaths":stable,"unobservedPaths":missing,
            "candidateState":"change-observed" if active else "presence-only" if stable else "no-evidence",
            "nextValidation":"controlled authorized action/outcome comparison required",
            "mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False})
    digest=hashlib.sha256(json.dumps(report,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    return {"schemaVersion":"49.0","placeId":manifest["placeId"],"scanId":manifest["scanId"],
        "sourceFingerprint":manifest["sourceFingerprint"],"inputEvidenceFingerprint":digest,
        "featureCount":len(features),"features":features,"readOnly":True,
        "mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,
        "limitations":["State correlation is not proof of causation","Client receipt is untrusted",
                       "No gameplay automation has been generated or validated"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("report",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/feature-candidates-v49.json"))
    args=p.parse_args()
    for file in (args.manifest,args.report):
        if file.stat().st_size>8_000_000:raise ValueError("Input too large")
    result=synthesize(json.loads(args.manifest.read_text(encoding="utf-8-sig")),
                      json.loads(args.report.read_text(encoding="utf-8-sig")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("Compiled",result["featureCount"],"evidence-ranked candidate families into",args.output)
if __name__=="__main__":main()
