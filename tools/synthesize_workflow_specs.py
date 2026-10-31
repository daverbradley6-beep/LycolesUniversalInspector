#!/usr/bin/env python3
"""Lycoles v31 offline workflow hypothesis compiler.

Converts source evidence into reviewable workflow specifications, not untested
gameplay scripts. Generated steps are declarative and require game inspection,
authorization, and outcome verification before implementation.
"""
import argparse
import hashlib
import json
import pathlib
import re
from collections import defaultdict

VERSION="31.0"
KINDS={
    "interaction-ui":("ui_event","state_read"),
    "state-observer":("state_read",),
    "lifecycle-monitor":("lifecycle",),
}
CAPABILITY={
    "interaction-ui":"observe visible controls and validate expected UI transitions",
    "state-observer":"read client-visible state and compare before/after snapshots",
    "lifecycle-monitor":"detect character or interface replacement and refresh references",
}

def stable_id(name,kind):
    return hashlib.sha256((name+"\0"+kind).encode()).hexdigest()[:16]

def compile_specs(manifest):
    if not isinstance(manifest,dict) or manifest.get("schemaVersion")!="31.0" or manifest.get("source")!="offline-static-corpus":
        raise ValueError("Expected v31 static corpus manifest")
    files=manifest.get("files")
    if not isinstance(files,list) or len(files)>1000:
        raise ValueError("Invalid corpus file list")
    specs=[]
    for item in files:
        if not isinstance(item,dict):raise ValueError("Invalid file entry")
        if item.get("classification")!="implementation":
            continue
        signals=item.get("workflowSignals") or {}
        if not isinstance(signals,dict):raise ValueError("Invalid signals")
        for kind,requirements in KINDS.items():
            if not all(type(signals.get(k)) is int and signals[k]>0 for k in requirements):
                continue
            name=item.get("file")
            if not isinstance(name,str) or len(name)>300:raise ValueError("Invalid filename")
            specs.append({
                "id":stable_id(name,kind),"sourceFile":name,
                "sourceSha256":item.get("sha256"),
                "kind":kind,"status":"hypothesis-needs-review",
                "evidence":{k:signals[k] for k in requirements},
                "intent":CAPABILITY[kind],
                "preconditions":["matching live game inspection","authorised client-visible interface"],
                "plan":[
                    {"step":"discover","expected":"observable objects and controls recorded"},
                    {"step":"snapshot","expected":"baseline state recorded"},
                    {"step":"review","expected":"specific action contract approved"},
                    {"step":"test","expected":"bounded client-visible observation captured"},
                    {"step":"verify","expected":"explicit outcome evidence or unsupported result"}
                ],
                "failureModes":["missing object","stale reference","changed UI","insufficient permissions",
                                "client-only observation","server outcome unknown"],
                "generatedCode":False,
                "runtimeVerified":False,
                "serverOutcomeVerified":False
            })
    return {"schemaVersion":VERSION,"source":"offline-workflow-hypotheses",
            "specCount":len(specs),"specs":specs,
            "verificationNotice":"Plans are hypotheses. Never treat source patterns as gameplay success."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("corpus",type=pathlib.Path)
    p.add_argument("--output",type=pathlib.Path,default=pathlib.Path("build/workflow-specs.json"))
    a=p.parse_args()
    data=json.loads(a.corpus.read_text(encoding="utf-8"))
    result=compile_specs(data)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("Compiled",result["specCount"],"reviewable workflow hypotheses")

if __name__=="__main__":
    main()
