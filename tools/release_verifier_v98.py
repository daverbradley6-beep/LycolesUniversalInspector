#!/usr/bin/env python3
"""v98 offline verification harness for Lycoles release artifacts.

Verifies deterministic stage outputs, integrity, cross-file provenance and
review-only boundaries. Does not claim to run a Roblox game.
"""
import argparse
import hashlib
import json
import tempfile
from pathlib import Path

def canonical(obj):
    return (json.dumps(obj,sort_keys=True,ensure_ascii=False,indent=2)+"\n").encode("utf-8")

def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def verify_release(path):
    root=Path(path)
    issues=[]
    manifest_path=root/"manifest-v97.json"
    try:
        manifest=read_json(manifest_path)
    except (OSError,ValueError,UnicodeError):
        return {"ok":False,"issues":["missing_or_invalid_manifest"]}
    required={"review-v97.json","proposal-v97.json","plan-v97.json"}
    hashes=manifest.get("files")
    if manifest.get("schemaVersion")!="97.manifest" or not isinstance(hashes,dict) or set(hashes)!=required:
        issues.append("invalid_manifest")
    if manifest.get("verifiedInGame") is not False or manifest.get("automaticGameplayExecution") is not False:
        issues.append("unsubstantiated_execution")
    if not isinstance(hashes,dict):
        hashes={}
    documents={}
    for name in sorted(required):
        p=root/name
        if not p.is_file() or p.is_symlink():
            issues.append("missing_file:"+name)
            continue
        data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=hashes.get(name):
            issues.append("digest_mismatch:"+name)
        try:
            documents[name]=json.loads(data)
        except (ValueError,UnicodeError):
            issues.append("invalid_json:"+name)
    if len(documents)==3:
        review=documents["review-v97.json"]
        proposal=documents["proposal-v97.json"]
        plan=documents["plan-v97.json"]
        if not all(isinstance(x,dict) for x in (review,proposal,plan)):
            issues.append("invalid_document_shape")
        else:
            place=manifest.get("placeId")
            if any(x.get("placeId")!=place for x in (review,proposal,plan)):
                issues.append("place_mismatch")
            if proposal.get("developerApproved") is not False or proposal.get("executionEnabled") is not False:
                issues.append("proposal_not_review_only")
            if proposal.get("verifiedInGame") is not False or plan.get("verifiedInGame") is not False:
                issues.append("unsubstantiated_verification")
            candidates=review.get("candidates")
            bindings=proposal.get("bindings")
            if not isinstance(candidates,list) or not isinstance(bindings,list):
                issues.append("invalid_candidates_or_bindings")
            else:
                eligible={c.get("id"):c for c in candidates
                          if isinstance(c,dict) and c.get("status")=="review_candidate"}
                if len(bindings)!=len(eligible):
                    issues.append("proposal_count_mismatch")
                seen=set()
                for b in bindings:
                    if not isinstance(b,dict):
                        issues.append("invalid_binding")
                        continue
                    cid=b.get("candidateId")
                    c=eligible.get(cid)
                    if cid in seen or c is None:
                        issues.append("invalid_candidate_reference")
                    seen.add(cid)
                    if c is not None and (b.get("observedInput")!=c.get("input") or
                                          b.get("expectedOutcome")!=c.get("outcome")):
                        issues.append("evidence_mismatch")
                    if b.get("reviewedByDeveloper") is not False or b.get("action") is not None:
                        issues.append("unexpected_automatic_action")
    return {"schemaVersion":"98.verification","ok":not issues,
            "issues":sorted(set(issues)),"checked":sorted(documents),
            "verifiedInGame":False}

def verify_reproducibility(review,stage_writer):
    with tempfile.TemporaryDirectory() as a,tempfile.TemporaryDirectory() as b:
        stage_writer(review,a)
        stage_writer(review,b)
        first=verify_release(a)
        second=verify_release(b)
        if not first["ok"] or not second["ok"]:
            return {"ok":False,"reason":"invalid_staging","first":first,"second":second}
        files=("review-v97.json","proposal-v97.json","plan-v97.json","manifest-v97.json")
        matching=all((Path(a)/name).read_bytes()==(Path(b)/name).read_bytes() for name in files)
        return {"ok":matching,"reason":"reproducible" if matching else "nondeterministic",
                "verifiedInGame":False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--directory",type=Path,required=True)
    p.add_argument("--report",type=Path)
    args=p.parse_args()
    result=verify_release(args.directory)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_bytes(canonical(result))
    print(json.dumps(result))
    raise SystemExit(0 if result["ok"] else 1)
if __name__=="__main__":
    main()
