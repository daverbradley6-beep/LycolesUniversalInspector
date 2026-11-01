#!/usr/bin/env python3
"""v57 discovery-to-action proposal generator; proposals are disabled by default."""
import argparse,json
from pathlib import Path
from balanced_discovery_v54 import analyze
from evidence_explorer_v55 import parse_path
def propose(report):
    if report.get("schemaVersion")!="54.analysis":raise ValueError("Expected v54 analysis")
    actions=[]
    seen=set()
    for row in report["paths"]:
        if row.get("className")!="Tool":continue
        segments=parse_path(row.get("path"))
        if not segments or len(segments)<2:continue
        name=segments[-1]["name"]
        if name in seen:continue
        seen.add(name)
        actions.append({"toolName":name,"operation":"activate_equipped_tool",
                        "status":"candidate_only",
                        "blockedBy":["owner authorization","metric selection","live verification"],
                        "reason":"Client-visible Tool exists; activation outcome unknown"})
        if len(actions)>=30:break
    return {"schemaVersion":"57.proposals","placeId":report["placeId"],
            "ownerAuthorized":False,"candidateActions":actions,
            "verifiedActions":0,"automaticExecutionAllowed":False}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--receipt",type=Path,required=True)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--output",type=Path,default=Path("build/release-v57"))
    a=p.parse_args()
    if a.receipt.stat().st_size>50_000_000:raise ValueError("Receipt too large")
    report=analyze(a.receipt.read_text(encoding="utf-8-sig"),a.place_id)
    proposal=propose(report)
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"action-proposals-v57.json").write_text(json.dumps(proposal,indent=2)+"\n",encoding="utf-8")
    print("Proposed",len(proposal["candidateActions"]),"disabled tool-action candidates")
if __name__=="__main__":main()
