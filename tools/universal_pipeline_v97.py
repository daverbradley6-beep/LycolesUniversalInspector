#!/usr/bin/env python3
"""v97 end-to-end evidence release coordinator for authorized Studio projects.

Stages a review package, proposes non-executable mappings, and optionally
compiles explicitly approved mappings. Never promotes evidence to authority.
"""
import argparse
import hashlib
import json
from pathlib import Path
from evidence_release_v90 import read_events
from temporal_attribution_v91 import release
from evidence_to_actions_v96 import generate as compile_approved
from secure_action_compiler_v95 import audit as audit_compiled

def encode(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def proposal(review):
    if not isinstance(review,dict) or not isinstance(review.get("candidates"),list):
        raise ValueError("invalid review")
    bindings=[]
    for c in sorted(review["candidates"],key=lambda c:str(c.get("id",""))):
        if c.get("status")!="review_candidate":
            continue
        outcome=c.get("outcome",{})
        # Suggestions are deliberately descriptive, never fabricated actions.
        bindings.append({"candidateId":c["id"],"observedInput":c["input"],
            "expectedOutcome":outcome,"reviewedByDeveloper":False,
            "action":None,"suggestedActionType":None,
            "requiresManualImplementation":True})
    return {"schemaVersion":"97.proposal","placeId":review["placeId"],
        "developerApproved":False,"authorizedUserIds":[],
        "bindings":bindings,"executionEnabled":False,
        "verifiedInGame":False}

def plan(review):
    p=proposal(review)
    d=review.get("temporalAttribution",{})
    return {"schemaVersion":"97.plan","placeId":review["placeId"],
        "observations":d.get("total"),"retained":d.get("retained"),
        "quarantined":d.get("quarantined"),"candidateCount":len(review["candidates"]),
        "eligibleCandidateCount":len(p["bindings"]),
        "nextSteps":[
            "Review temporal conflicts and insufficient evidence candidates",
            "Record additional independent controlled sessions when necessary",
            "For an owned game, implement a supported server action for each candidate",
            "Review the exact candidate input/outcome against the implementation",
            "Fill the v96 mapping with explicit approvals and real authorized user IDs",
            "Compile and audit in an authorized Studio project",
            "Test resulting behavior in Roblox Studio and record independent results"
        ],"automaticGameplayExecution":False,"verifiedInGame":False}

def write_stage(review,output):
    root=Path(output)
    root.mkdir(parents=True,exist_ok=True)
    files={"review-v97.json":encode(review),
           "proposal-v97.json":encode(proposal(review)),
           "plan-v97.json":encode(plan(review))}
    hashes={}
    for name,data in files.items():
        (root/name).write_bytes(data)
        hashes[name]=hashlib.sha256(data).hexdigest()
    manifest={"schemaVersion":"97.manifest","placeId":review["placeId"],
        "files":hashes,"automaticGameplayExecution":False,
        "verifiedInGame":False}
    (root/"manifest-v97.json").write_bytes(encode(manifest))
    return manifest

def audit_stage(output):
    root=Path(output)
    issues=[]
    try:
        manifest=json.loads((root/"manifest-v97.json").read_text(encoding="utf-8"))
        if manifest.get("schemaVersion")!="97.manifest" or manifest.get("verifiedInGame") is not False:
            issues.append("invalid_manifest")
        hashes=manifest.get("files")
        expected={"review-v97.json","proposal-v97.json","plan-v97.json"}
        if not isinstance(hashes,dict) or set(hashes)!=expected:
            issues.append("invalid_file_set")
        else:
            for name in sorted(expected):
                path=root/name
                if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=hashes[name]:
                    issues.append("artifact_hash_mismatch:"+name)
            if not issues:
                review=json.loads((root/"review-v97.json").read_text(encoding="utf-8"))
                if (root/"proposal-v97.json").read_bytes()!=encode(proposal(review)):
                    issues.append("proposal_not_reproducible")
                if (root/"plan-v97.json").read_bytes()!=encode(plan(review)):
                    issues.append("plan_not_reproducible")
                if manifest.get("placeId")!=review.get("placeId"):
                    issues.append("place_mismatch")
    except (OSError,ValueError,TypeError,KeyError) as exc:
        issues.append("audit_error:"+type(exc).__name__)
    return {"schemaVersion":"97.audit","ok":not issues,"issues":issues,"verifiedInGame":False}

def run(events,place_id,output,mapping=None):
    review=release(events,place_id)
    write_stage(review,output)
    result=audit_stage(output)
    if not result["ok"]:
        raise RuntimeError("staging audit failed: "+repr(result["issues"]))
    compiled=False
    if mapping is not None:
        compiled_dir=Path(output)/"approved-studio"
        compile_approved(review,mapping,compiled_dir)
        verified=audit_compiled(compiled_dir)
        if not verified["ok"]:
            raise RuntimeError("compiled release audit failed: "+repr(verified["issues"]))
        compiled=True
    return {"schemaVersion":"97.result","events":len(events),
        "candidates":len(review["candidates"]),
        "eligible":len(proposal(review)["bindings"]),
        "quarantined":review["temporalAttribution"]["quarantined"],
        "stagingAuditPassed":True,"approvedStudioCompilation":compiled,
        "verifiedInGame":False,"output":str(output)}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--event-log",type=Path,action="append",required=True)
    p.add_argument("--mapping",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/release-v97"))
    a=p.parse_args()
    events,_,warnings=read_events(a.event_log,a.place_id)
    mapping=json.loads(a.mapping.read_text(encoding="utf-8-sig")) if a.mapping else None
    result=run(events,a.place_id,a.output,mapping)
    result["warnings"]=len(warnings)
    print(json.dumps(result,ensure_ascii=False))
if __name__=="__main__":
    main()
