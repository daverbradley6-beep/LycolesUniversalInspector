#!/usr/bin/env python3
"""v96 evidence-to-Studio compiler bridge.

Links reviewed observations to explicitly developer-authored action mappings.
No observed input is ever treated as an executable implementation by itself.
"""
import argparse
import hashlib
import json
from pathlib import Path
from secure_action_compiler_v95 import generate as generate_v95, validate as validate_v95, audit as audit_v95

def require_dict(value,label):
    if not isinstance(value,dict):
        raise ValueError(label+" must be an object")
    return value

def bridge(review,mapping):
    require_dict(review,"review")
    require_dict(mapping,"mapping")
    if review.get("schemaVersion") not in ("90.review","91.review","92.review"):
        raise ValueError("unsupported evidence review")
    if mapping.get("schemaVersion")!="96.mapping":
        raise ValueError("unsupported mapping schema")
    place=review.get("placeId")
    if type(place)!=int or place<=0 or mapping.get("placeId")!=place:
        raise ValueError("place mismatch")
    if review.get("verifiedInGame") is not False:
        raise ValueError("unexpected evidence verification claim")
    if mapping.get("developerApproved") is not True:
        raise ValueError("explicit developer approval required")
    candidates=review.get("candidates")
    if not isinstance(candidates,list):
        raise ValueError("invalid candidate collection")
    eligible={}
    for candidate in candidates:
        require_dict(candidate,"candidate")
        cid=candidate.get("id")
        if not isinstance(cid,str) or not cid or cid in eligible:
            raise ValueError("invalid or duplicate candidate id")
        if candidate.get("status")=="review_candidate":
            eligible[cid]=candidate
    bindings=mapping.get("bindings")
    if not isinstance(bindings,list) or not bindings or len(bindings)>50:
        raise ValueError("1-50 mappings required")
    actions=[]
    provenance=[]
    used=set()
    for binding in bindings:
        require_dict(binding,"binding")
        cid=binding.get("candidateId")
        if not isinstance(cid,str) or cid in used:
            raise ValueError("invalid or duplicate candidate binding")
        used.add(cid)
        candidate=eligible.get(cid)
        if candidate is None:
            raise ValueError("candidate not eligible: "+str(cid))
        if binding.get("observedInput")!=candidate.get("input") or binding.get("expectedOutcome")!=candidate.get("outcome"):
            raise ValueError("candidate evidence mismatch")
        if binding.get("reviewedByDeveloper") is not True:
            raise ValueError("candidate requires developer review")
        action=binding.get("action")
        require_dict(action,"action")
        actions.append(action)
        provenance.append({"candidateId":cid,"observedInput":candidate["input"],
                           "expectedOutcome":candidate["outcome"],
                           "actionId":action.get("id"),
                           "evidenceStatus":"review_candidate",
                           "verifiedInGame":False})
    spec={"schemaVersion":"95.actions","placeId":place,"enabled":True,
          "authorizedUserIds":mapping.get("authorizedUserIds"),
          "actions":actions}
    validate_v95(spec)
    return spec,provenance

def generate(review,mapping,output):
    spec,provenance=bridge(review,mapping)
    root=Path(output)
    manifest=generate_v95(spec,root)
    audit=audit_v95(root)
    if not audit["ok"]:
        raise RuntimeError("v95 compiler audit failed: "+repr(audit["issues"]))
    evidence_hash=hashlib.sha256(json.dumps(review,sort_keys=True,ensure_ascii=False,
        separators=(",",":")).encode("utf-8")).hexdigest()
    document={"schemaVersion":"96.provenance","placeId":spec["placeId"],
              "reviewSha256":evidence_hash,"bindings":provenance,
              "developerApproved":True,"requiresStudioInstallation":True,
              "verifiedInGame":False}
    payload=json.dumps(document,indent=2,sort_keys=True,ensure_ascii=False)+"\n"
    (root/"provenance-v96.json").write_text(payload,encoding="utf-8")
    return {"schemaVersion":"96.release","placeId":spec["placeId"],
            "bindings":len(provenance),"compiledActions":len(spec["actions"]),
            "v95AuditPassed":True,"verifiedInGame":False,
            "files":list(manifest["files"])+["provenance-v96.json"]}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--review",type=Path,required=True)
    p.add_argument("--mapping",type=Path,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v96"))
    a=p.parse_args()
    review=json.loads(a.review.read_text(encoding="utf-8-sig"))
    mapping=json.loads(a.mapping.read_text(encoding="utf-8-sig"))
    print(json.dumps(generate(review,mapping,a.output)))
if __name__=="__main__":
    main()
