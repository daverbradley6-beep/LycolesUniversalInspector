#!/usr/bin/env python3
"""v59 gameplay planner: combine evidence and explicit, authorized action contracts.

Discovery supplies candidates, never executable authority. Only validated v58
contracts become runnable workflows. Unmatched candidates stay disabled.
"""
import argparse,json,hashlib
from pathlib import Path
from gameplay_workflows_v58 import validate as validate_v58,generate as generate_v58
from action_proposals_v57 import propose
from balanced_discovery_v54 import analyze

def plan(receipt,contract=None):
    report=analyze(receipt)
    candidates=propose(report)
    result={"schemaVersion":"59.0","placeId":report["placeId"],
            "observedToolCandidates":candidates["candidateActions"],
            "authorizedActions":[],"unsupported":[],
            "evidence":{"samples":report["samples"],"truncatedSamples":report["truncatedSamples"],
                        "changingPaths":report["changingPaths"]},
            "liveGameplayVerified":False}
    if contract is not None:
        validate_v58(contract)
        if contract["placeId"]!=report["placeId"]:raise ValueError("Place ID mismatch")
        candidate_names={x["toolName"] for x in candidates["candidateActions"]}
        for a in contract["actions"]:
            if a["toolName"] in candidate_names:
                result["authorizedActions"].append({"id":a["id"],"toolName":a["toolName"],
                    "operation":a["operation"],"status":"ready_for_live_verification"})
            else:
                result["unsupported"].append({"id":a["id"],"reason":"Tool not found in discovery evidence"})
    result["summary"]={"candidates":len(result["observedToolCandidates"]),
                       "readyForLiveVerification":len(result["authorizedActions"]),
                       "unsupported":len(result["unsupported"])}
    result["sha256"]=hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()
    return result
def build(receipt,contract,out):
    result=plan(receipt,contract)
    out.mkdir(parents=True,exist_ok=True)
    (out/"gameplay-plan-v59.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    if contract is not None and result["authorizedActions"]:
        allowed={a["id"] for a in result["authorizedActions"]}
        subset={**contract,"actions":[a for a in contract["actions"] if a["id"] in allowed]}
        script=generate_v58(subset)
        (out/"gameplay-runner-v59.luau").write_text(script,encoding="utf-8")
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--contract",type=Path)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v59"))
    a=p.parse_args()
    if a.receipt.stat().st_size>50_000_000:raise ValueError("Receipt too large")
    receipt=a.receipt.read_text(encoding="utf-8-sig")
    if analyze(receipt,a.place_id)["placeId"]!=a.place_id:raise ValueError("Wrong place")
    contract=json.loads(a.contract.read_text(encoding="utf-8-sig")) if a.contract else None
    print(json.dumps(build(receipt,contract,a.output)["summary"],indent=2))
if __name__=="__main__":main()
