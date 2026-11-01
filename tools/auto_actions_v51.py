#!/usr/bin/env python3
"""v51: automatic evidence-to-runnable local inspector compilation."""
import argparse,hashlib,json,re
from pathlib import Path
from action_contract_v50 import validate,generate
from adaptive_probe_v44 import paths

def compile_auto(manifest, report, limit=64):
    if type(limit) is not int or not 1<=limit<=64:raise ValueError("Invalid limit")
    inventory=set(paths(manifest))
    if not isinstance(report,dict) or report.get("schemaVersion")!="48.0":raise ValueError("Expected v48 report")
    for key in ("placeId","scanId","sourceFingerprint"):
        if type(report.get(key))!=type(manifest.get(key)) or report[key]!=manifest[key]:
            raise ValueError("Identity mismatch: "+key)
    if any(report.get(key) is not False for key in ("mechanicVerified","serverOutcomeVerified","gameplayAutomationApproved")):
        raise ValueError("Unsupported verification claim")
    samples=report.get("samples")
    if type(samples) is not int or not 2<=samples<=121:raise ValueError("Invalid sample count")
    observed=report.get("paths")
    if not isinstance(observed,dict) or set(observed)!=inventory:raise ValueError("Incomplete path inventory")
    eligible=[]
    for path in sorted(inventory):
        record=observed[path]
        if not isinstance(record,dict):raise ValueError("Invalid observation")
        count=record.get("visibleSamples"); transitions=record.get("stateTransitions")
        if type(count) is not int or not 0<=count<=samples or type(transitions) is not int or not 0<=transitions<samples:
            raise ValueError("Invalid observation counts")
        if type(record.get("valueChanged")) is not bool:raise ValueError("Invalid change flag")
        expected="changing" if transitions else "stable-visible" if count else "not-observed"
        if record.get("classification")!=expected:raise ValueError("Inconsistent classification")
        if record["valueChanged"] and transitions==0:raise ValueError("Inconsistent change evidence")
        # v50 runtime supports local-player ValueBase and GUI text, not general workspace mutations.
        if not path.startswith("Players.LocalPlayer.") or len(path)>256 or not all(0<len(part)<=80 for part in path.split(".")):
            continue
        if count==0:continue
        eligible.append((path,count,transitions))
    eligible.sort(key=lambda x:(-x[1],-x[2],x[0]))
    actions=[]
    for path,count,transitions in eligible[:limit]:
        digest=hashlib.sha256(path.encode("utf-8")).hexdigest()[:12]
        actions.append({"id":"read-"+digest,"kind":"read-value","path":path})
    contract={"schemaVersion":"50.0","placeId":manifest["placeId"],"actions":actions}
    if actions:validate(contract)
    audit={"schemaVersion":"51.0","placeId":manifest["placeId"],"scanId":manifest["scanId"],
           "sourceFingerprint":manifest["sourceFingerprint"],"inventoryPaths":len(inventory),
           "eligiblePaths":len(eligible),"generatedActions":len(actions),
           "excludedPaths":len(inventory)-len(eligible),"readOnly":True,
           "mechanicVerified":False,"serverOutcomeVerified":False,"gameplayAutomationApproved":False,
           "limitations":["Only observed local-player paths are eligible",
                          "A visible object may not be a supported readable value",
                          "Client evidence is untrusted; runtime tests are still required"]}
    return contract,audit

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("manifest",type=Path)
    p.add_argument("report",type=Path)
    p.add_argument("--output",type=Path,default=Path("build"))
    p.add_argument("--limit",type=int,default=64)
    args=p.parse_args()
    for f in (args.manifest,args.report):
        if f.stat().st_size>8000000:raise ValueError("Input too large")
    manifest=json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    report=json.loads(args.report.read_text(encoding="utf-8-sig"))
    contract,audit=compile_auto(manifest,report,args.limit)
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"auto-actions-v51.json").write_text(json.dumps(contract,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (args.output/"auto-actions-audit-v51.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    if contract["actions"]:
        (args.output/"auto-actions-v51.luau").write_text(generate(contract),encoding="utf-8")
    else:
        target=args.output/"auto-actions-v51.luau"
        if target.exists():target.unlink()
    print("v51:",audit["generatedActions"],"generated read-only actions;",audit["excludedPaths"],"paths excluded")
if __name__=="__main__":main()
