#!/usr/bin/env python3
"""Validate guided workflow feedback against its exact generated workflow plan."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path

SCHEMA="115.guided-workflow-feedback.1"
OUTPUT_SCHEMA="115.guided-workflow-evaluation.1"
FALSE_CLAIMS={"sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified"}
STATUSES={"control-or-state-unavailable","metadata-drift","state-unreadable",
    "activation-timeout","outcome-not-observed","expected-change-observed"}
ENTRY_FIELDS={"sequence","runId","stepSequence","targetPath","outcomeKey","expected",
    "before","after","activationObserved","observedExpectedChange","status","message",
    "observedAtUnix"}


def digest(document):
    raw=json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _validator():
    path=Path(__file__).with_name("generate_guided_workflow.py")
    spec=importlib.util.spec_from_file_location("lycoles_guided_feedback_plan_validator",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def _scalar(value):
    if value is None:return None
    if type(value) in (int,float):
        if not math.isfinite(value):raise ValueError("Invalid guided feedback scalar")
        return value
    if type(value) is bool or isinstance(value,str) and len(value)<=128:return value
    raise ValueError("Invalid guided feedback scalar")


def _observed(expected,before,after):
    if expected=="increased":
        return type(before) in (int,float) and type(after) in (int,float) and after>before
    if expected=="decreased":
        return type(before) in (int,float) and type(after) in (int,float) and after<before
    return before is not None and after is not None and before!=after


def _candidate(plan,candidate_id):
    candidates=_validator().validate(plan)
    if not candidates or candidate_id!=candidates[0]["id"]:
        raise ValueError("Guided feedback candidate mismatch")
    return candidates[0]


def evaluate(plan,feedback):
    if not isinstance(plan,dict):raise ValueError("Invalid generated workflow plan")
    if not isinstance(feedback,dict) or set(feedback)!={"schemaVersion","placeId","scanId",
            "workflowPlanSHA256","candidateId","sessionId","entries","claims"}:
        raise ValueError("Invalid guided feedback schema")
    if (feedback.get("schemaVersion")!=SCHEMA or feedback.get("placeId")!=plan.get("placeId")
            or feedback.get("scanId")!=plan.get("scanId")
            or feedback.get("workflowPlanSHA256")!=digest(plan)):
        raise ValueError("Guided feedback identity mismatch")
    candidate_id=feedback.get("candidateId")
    session=feedback.get("sessionId");entries=feedback.get("entries");claims=feedback.get("claims")
    if (not isinstance(candidate_id,str) or not 1<=len(candidate_id)<=80
            or not isinstance(session,str) or not 1<=len(session)<=128
            or not isinstance(entries,list) or len(entries)>400
            or not isinstance(claims,dict) or set(claims)!=FALSE_CLAIMS or any(claims.values())):
        raise ValueError("Invalid guided feedback claims or inventory")
    candidate=_candidate(plan,candidate_id);steps=candidate["steps"]
    previous_sequence=0;previous_run=0;current_run=None;expected_step=1;terminated=False
    evaluated=[];runs=[];run_rows=[]
    def complete_run():
        if not run_rows:return
        complete=(len(run_rows)==len(steps) and all(
            row["status"]=="expected-change-observed" for row in run_rows))
        runs.append({"runId":run_rows[0]["runId"],"entries":len(run_rows),
            "lastStepSequence":run_rows[-1]["stepSequence"],
            "activationEventsObserved":sum(row["activationObserved"] for row in run_rows),
            "expectedChangesObserved":sum(row["observedExpectedChange"] for row in run_rows),
            "statuses":{status:sum(row["status"]==status for row in run_rows)
                for status in sorted({row["status"] for row in run_rows})},
            "completeClientObservationSequence":complete,"runtimeVerified":False,
            "gameplayVerified":False,"causalityProven":False})
    for entry in entries:
        if (not isinstance(entry,dict) or not set(entry)<=ENTRY_FIELDS or not {
                "sequence","runId","stepSequence","targetPath","outcomeKey","expected",
                "activationObserved","observedExpectedChange","status","message","observedAtUnix"}<=set(entry)):
            raise ValueError("Invalid guided feedback entry")
        sequence=entry["sequence"];run_id=entry["runId"];step_sequence=entry["stepSequence"]
        if (type(sequence) is not int or sequence!=previous_sequence+1
                or type(run_id) is not int or not 1<=run_id<=1_000_000_000
                or type(step_sequence) is not int or not 1<=step_sequence<=len(steps)):
            raise ValueError("Invalid guided feedback entry")
        if current_run!=run_id:
            complete_run();run_rows=[]
            if run_id<=previous_run:raise ValueError("Invalid guided feedback run order")
            previous_run=run_id;current_run=run_id;expected_step=1;terminated=False
        if terminated or step_sequence!=expected_step:
            raise ValueError("Invalid guided feedback run order")
        contract=steps[step_sequence-1];outcome=contract["selectedOutcome"]
        before=_scalar(entry.get("before"));after=_scalar(entry.get("after"))
        observed=_observed(outcome["change"],before,after)
        status=entry["status"];activation=entry["activationObserved"]
        if (entry["targetPath"]!=contract["targetPath"] or entry["outcomeKey"]!=outcome["key"]
                or entry["expected"]!=outcome["change"] or status not in STATUSES
                or type(activation) is not bool or type(entry["observedExpectedChange"]) is not bool
                or not isinstance(entry["message"],str) or len(entry["message"])>240
                or type(entry["observedAtUnix"]) is not int or entry["observedAtUnix"]<1):
            raise ValueError("Invalid guided feedback entry")
        if (entry["observedExpectedChange"] is not observed
                or (status=="expected-change-observed") is not observed):
            raise ValueError("Guided feedback outcome claim mismatch")
        sampled=status in {"expected-change-observed","outcome-not-observed","activation-timeout"}
        if ((status in {"expected-change-observed","outcome-not-observed"}) is not activation
                or sampled and (before is None or after is None)
                or sampled and outcome["change"] in {"increased","decreased"}
                    and (type(before) not in (int,float) or type(after) not in (int,float))
                or status=="activation-timeout" and (activation or after!=before)
                or status in {"control-or-state-unavailable","metadata-drift","state-unreadable"}
                    and (activation or before is not None or after is not None)):
            raise ValueError("Invalid guided feedback status contract")
        row={"sequence":sequence,"runId":run_id,"stepSequence":step_sequence,
            "targetPath":contract["targetPath"],"outcomeKey":outcome["key"],
            "expected":outcome["change"],"before":before,"after":after,
            "activationObserved":activation,"observedExpectedChange":observed,"status":status,
            "message":entry["message"],"observedAtUnix":entry["observedAtUnix"]}
        evaluated.append(row);run_rows.append(row);previous_sequence=sequence
        expected_step+=1
        if status!="expected-change-observed":terminated=True
    complete_run()
    completed=sum(run["completeClientObservationSequence"] for run in runs)
    return {"schemaVersion":OUTPUT_SCHEMA,"placeId":plan["placeId"],"scanId":plan["scanId"],
        "workflowPlanSHA256":digest(plan),"candidateId":candidate_id,"sessionId":session,
        "entries":evaluated,"runs":runs,"summary":{"submittedEntries":len(evaluated),
            "runs":len(runs),"activationEventsObserved":sum(
                row["activationObserved"] for row in evaluated),
            "completeClientObservationSequences":completed,
            "expectedChangesObserved":sum(row["observedExpectedChange"] for row in evaluated)},
        "sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"runtimeVerified":False,"gameplayVerified":False,
        "actionOutcomesVerified":False,
        "note":"Feedback is digest-bound client observation; it does not prove source authenticity, causality, server authority, runtime correctness, or gameplay semantics."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_plan",type=Path);parser.add_argument("feedback",type=Path)
    parser.add_argument("--output",type=Path,default=Path("build/guided-workflow-evaluation.json"))
    args=parser.parse_args();result=evaluate(
        json.loads(args.workflow_plan.read_text(encoding="utf-8-sig")),
        json.loads(args.feedback.read_text(encoding="utf-8-sig")))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps({"output":str(args.output),**result["summary"],"runtimeVerified":False,
        "gameplayVerified":False},sort_keys=True))


if __name__=="__main__":main()
