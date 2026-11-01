#!/usr/bin/env python3
"""v86 workflow orchestrator: preflight, build, inspect, and report without tracebacks.

No automatic Roblox input injection or remote invocation.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

PLACE = 85896571713843
STAGES = (
    ("v82", "tools/interactive_runner_v82.py", "interactive-runner-v82.luau"),
    ("v83", "tools/action_result_analyzer_v83.py", "action-results-v83.json"),
    ("v85", "tools/evidence_to_contracts_v85.py", "contracts-for-review-v85.json"),
    ("v84", "tools/release_pipeline_v84.py", "interactive-runner-v84.luau"),
)

def inspect(root, place, contracts, result_log, output):
    root = Path(root)
    contracts = Path(contracts)
    result_log = Path(result_log)
    output = Path(output)
    issues = []
    actions = []
    if type(place) is not int or place <= 0:
        issues.append("Place ID must be a positive integer")
    if not contracts.is_file():
        issues.append(f"Missing contracts: {contracts}. Provide an approved.json with GUI contracts.")
    else:
        try:
            document = json.loads(contracts.read_text(encoding="utf-8-sig"))
            from release_pipeline_v84 import validate
            approved = validate(document, place)
            actions = [c["id"] for c in approved]
            if not actions:
                issues.append("No approved GUI contracts; review and explicitly approve a contract first")
        except (ValueError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            issues.append(f"Invalid contracts: {exc}")
    if not result_log.is_file():
        issues.append(f"Missing observation log: {result_log}. Run v82 and save real LYCOLES_V82_RESULT console lines.")
    elif not result_log.read_text(encoding="utf-8-sig", errors="replace").strip():
        issues.append(f"Empty observation log: {result_log}")
    for _, script, _ in STAGES:
        if not (root / script).is_file():
            issues.append(f"Missing tool: {root / script}")
    return {"schemaVersion":"86.preflight","placeId":place,"approvedActionIds":actions,
            "ready":not issues,"issues":issues,"contracts":str(contracts),
            "resultLog":str(result_log),"output":str(output)}

def plan(root, place, contracts, result_log, output):
    root = Path(root)
    output = Path(output)
    return [
        [sys.executable, str(root / "tools/interactive_runner_v82.py"), "--place-id", str(place), "--contracts", str(contracts), "--output", str(output / "v82")],
        [sys.executable, str(root / "tools/action_result_analyzer_v83.py"), "--place-id", str(place), "--result-log", str(result_log), "--contracts", str(contracts), "--output", str(output / "v83")],
        [sys.executable, str(root / "tools/evidence_to_contracts_v85.py"), "--place-id", str(place), "--review", str(output / "v83/action-results-v83.json"), "--catalog", str(contracts), "--output", str(output / "v85")],
        [sys.executable, str(root / "tools/release_pipeline_v84.py"), "--place-id", str(place), "--contracts", str(contracts), "--output", str(output / "v84"), "--force"],
    ]

def run(root, place, contracts, result_log, output, dry_run=False):
    preflight = inspect(root, place, contracts, result_log, output)
    if not preflight["ready"]:
        return {"status":"blocked","preflight":preflight,"completed":[]}
    commands = plan(root, place, contracts, result_log, output)
    if dry_run:
        return {"status":"planned","preflight":preflight,"commands":commands,"completed":[]}
    completed = []
    for stage, command in zip(("v82","v83","v85","v84"),commands):
        process = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, check=False)
        record = {"stage":stage,"returnCode":process.returncode,"stdout":process.stdout[-5000:],"stderr":process.stderr[-5000:]}
        completed.append(record)
        if process.returncode != 0:
            return {"status":"failed","preflight":preflight,"completed":completed}
    return {"status":"built_unverified","preflight":preflight,"completed":completed,
            "verifiedInGame":False,"automaticallyExecuted":0}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--place-id",type=int,required=True)
    p.add_argument("--contracts",type=Path,default=Path("approved.json"))
    p.add_argument("--result-log",type=Path,default=Path("results-v82.txt"))
    p.add_argument("--output",type=Path,default=Path("build/release-v86"))
    p.add_argument("--dry-run",action="store_true")
    args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        result = run(root,args.place_id,args.contracts.resolve(),args.result_log.resolve(),args.output.resolve(),args.dry_run)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        result = {"status":"failed","error":str(exc)}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result["status"] in ("blocked","failed"):
        raise SystemExit(2)

if __name__ == "__main__":
    main()
