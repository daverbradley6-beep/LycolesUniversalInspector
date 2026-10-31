#!/usr/bin/env python3
"""v42: deterministic, evidence-gated generation manifest and test oracle."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ALLOWED_ROOTS={"Workspace","ReplicatedStorage","ReplicatedFirst","Players","Lighting",
               "StarterGui","StarterPack","StarterPlayer","SoundService","Teams"}
MAX_BYTES=8_000_000
MAX_FEATURES=100
MAX_PATHS=100

def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=True)

def fingerprint(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()

def compile_manifest(spec, discovery):
    if not isinstance(spec,dict) or spec.get("schemaVersion")!="41.0":
        raise ValueError("Expected v41 feature specifications")
    if not isinstance(discovery,dict) or discovery.get("schemaVersion")!="39.0":
        raise ValueError("Expected v39 discovery report")
    for field in ("placeId","scanId"):
        if spec.get(field)!=discovery.get(field):
            raise ValueError("Cross-report identity mismatch: "+field)
    families=discovery.get("families")
    features=spec.get("features")
    if not isinstance(families,list) or not isinstance(features,list) or len(features)>MAX_FEATURES:
        raise ValueError("Invalid feature or family collection")
    evidence={}
    for family in families:
        if not isinstance(family,dict) or not isinstance(family.get("id"),str):
            raise ValueError("Invalid family")
        if family["id"] in evidence:raise ValueError("Duplicate family")
        paths=family.get("examplePaths",[])
        if not isinstance(paths,list):raise ValueError("Invalid family paths")
        evidence[family["id"]]=set(paths)
    compiled=[]
    ids=set()
    for feature in features:
        if not isinstance(feature,dict):raise ValueError("Invalid feature")
        fid=feature.get("id")
        family=feature.get("family")
        paths=feature.get("evidencePaths")
        if not isinstance(fid,str) or not re.fullmatch(r"inspect-[a-z]+",fid) or fid in ids:
            raise ValueError("Duplicate or invalid feature id")
        ids.add(fid)
        if fid!="inspect-"+str(family) or family not in evidence:
            raise ValueError("Feature has no matching discovery family")
        if feature.get("kind")!="read-only-inspection" or feature.get("gameplayImplementationAvailable") is not False:
            raise ValueError("Unsupported gameplay implementation")
        if not isinstance(paths,list) or not 1<=len(paths)<=MAX_PATHS:
            raise ValueError("Missing or excessive evidence paths")
        seen=set()
        for path in paths:
            if not isinstance(path,str) or not 1<=len(path)<=1024:
                raise ValueError("Invalid path")
            if path in seen:raise ValueError("Duplicate evidence path")
            seen.add(path)
            if path not in evidence[family]:raise ValueError("Unattributed evidence path")
            if path.split(".",1)[0] not in ALLOWED_ROOTS or "." not in path:
                raise ValueError("Unsupported evidence root")
        compiled.append({"id":fid,"family":family,"label":feature.get("label",fid),
                         "kind":"read-only-inspection","evidencePaths":sorted(seen),
                         "evidenceFingerprint":fingerprint(sorted(seen)),
                         "tests":[{"name":"path-presence","expected":"observed-or-not-found",
                                   "requiresClientExecution":True},
                                  {"name":"gameplay-outcome","expected":"not-verified",
                                   "requiresClientExecution":True}],
                         "implementationStatus":"diagnostic-only",
                         "gameplayVerified":False})
    compiled.sort(key=lambda x:x["id"])
    return {"schemaVersion":"42.0","placeId":spec["placeId"],"scanId":spec["scanId"],
            "sourceFingerprint":fingerprint({"spec":spec,"discovery":discovery}),
            "featureCount":len(compiled),"features":compiled,
            "readOnly":True,"gameplayAutomationApproved":False,
            "runtimeVerified":False,"serverOutcomeVerified":False,
            "nextEvidenceRequired":["Live path-existence results","Authorized mechanic contract",
                                    "Independent functional outcome verification"]}

def load(path):
    p=Path(path)
    if p.stat().st_size>MAX_BYTES:raise ValueError("Input too large")
    return json.loads(p.read_text(encoding="utf-8-sig"))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("spec",type=Path)
    p.add_argument("discovery",type=Path)
    p.add_argument("--output",type=Path,default=Path("build/generation-manifest-v42.json"))
    a=p.parse_args()
    result=compile_manifest(load(a.spec),load(a.discovery))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Compiled",result["featureCount"],"evidence-gated features into",a.output)

if __name__=="__main__":main()
