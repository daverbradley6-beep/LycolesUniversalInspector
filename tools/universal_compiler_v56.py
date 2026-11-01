#!/usr/bin/env python3
"""v56 quality-gated compiler of client-visible inspection interfaces."""
import argparse,json,hashlib
from pathlib import Path
from evidence_explorer_v55 import compile_features,render
from balanced_discovery_v54 import analyze

def quality(report):
    return {"samples":report["samples"],"entries":report["recordedEntries"],
            "distinctPaths":report["distinctPathKeys"],"changedPaths":report["changingPaths"],
            "ambiguousDuplicates":report["ambiguousDuplicateOccurrences"],
            "truncatedSamples":report["truncatedSamples"],
            "observationOnly":True,"serverOutcomesVerified":False}
def compile_bundle(report):
    contract=compile_features(report)
    groups={}
    for feature in contract["features"]:
        groups.setdefault(feature["category"],[]).append(feature["id"])
    result={"schemaVersion":"56.0","placeId":contract["placeId"],
            "contract":contract,"groups":groups,"quality":quality(report),
            "verification":{"offlineCompiler":True,"liveGameplay":False}}
    result["fingerprint"]=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
def audit(bundle,script):
    failures=[]
    if bundle["contract"]["capabilities"]["automaticGameplayActions"]:failures.append("Unexpected action capability")
    if len(bundle["contract"]["features"])>120:failures.append("Feature count over limit")
    if "PLACE_ID" in script or "ROWS" in script:failures.append("Unresolved template placeholder")
    if "MouseButton1Click" not in script:failures.append("No working inspection controls")
    if "GetChildren()" not in script:failures.append("Missing object resolver")
    return {"passed":not failures,"failures":failures,
            "featureCount":len(bundle["contract"]["features"]),
            "status":"offline static audit only"}
def build(receipt,place_id,output):
    report=analyze(receipt,place_id)
    bundle=compile_bundle(report)
    script=render(bundle["contract"])
    check=audit(bundle,script)
    if not check["passed"]:raise ValueError("Static audit failed: "+str(check["failures"]))
    output.mkdir(parents=True,exist_ok=True)
    files={"universal-evidence-explorer-v56.luau":script,
           "feature-bundle-v56.json":json.dumps(bundle,indent=2,ensure_ascii=False)+"\n",
           "quality-report-v56.json":json.dumps(bundle["quality"],indent=2)+"\n",
           "static-audit-v56.json":json.dumps(check,indent=2)+"\n"}
    for name,content in files.items():(output/name).write_text(content,encoding="utf-8")
    return check
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v56"))
    a=p.parse_args()
    if a.receipt.stat().st_size>50_000_000:raise ValueError("Receipt too large")
    print(build(a.receipt.read_text(encoding="utf-8-sig"),a.place_id,a.output))
if __name__=="__main__":main()
