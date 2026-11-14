#!/usr/bin/env python3
"""Aggregate exact-plan guided workflow feedback without upgrading verification claims."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

SCHEMA="116.guided-workflow-feedback-aggregate.1"
FALSE_CLAIMS={"sourceAuthenticityVerified","causalityProven","serverAuthorityVerified",
    "runtimeVerified","gameplayVerified","actionOutcomesVerified"}


def _load_evaluator():
    path=Path(__file__).with_name("evaluate_guided_workflow_feedback.py")
    spec=importlib.util.spec_from_file_location("lycoles_guided_aggregate_evaluator",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def _digest(document):
    raw=json.dumps(document,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _scalar_type(value):
    if value is None:return None
    if type(value) is bool:return "boolean"
    if type(value) in (int,float):return "number"
    return "string"


def aggregate(plan,feedback_documents):
    if not isinstance(feedback_documents,list) or not 1<=len(feedback_documents)<=100:
        raise ValueError("Guided feedback aggregation requires one to 100 sessions")
    evaluator=_load_evaluator();evaluations=[]
    for document in feedback_documents:
        result=evaluator.evaluate(plan,document)
        evaluations.append((result,_digest(document)))
    session_ids=[item[0]["sessionId"] for item in evaluations]
    if len(session_ids)!=len(set(session_ids)):
        raise ValueError("Duplicate guided feedback session")
    evaluations.sort(key=lambda item:item[0]["sessionId"])
    candidate=evaluator._candidate(plan,evaluations[0][0]["candidateId"])
    sessions=[]
    for result,feedback_digest in evaluations:
        statuses={}
        for entry in result["entries"]:
            statuses[entry["status"]]=statuses.get(entry["status"],0)+1
        sessions.append({"sessionId":result["sessionId"],"feedbackSHA256":feedback_digest,
            "runs":result["summary"]["runs"],
            "submittedEntries":result["summary"]["submittedEntries"],
            "activationEventsObserved":result["summary"]["activationEventsObserved"],
            "expectedChangesObserved":result["summary"]["expectedChangesObserved"],
            "completeClientObservationSequences":result["summary"][
                "completeClientObservationSequences"],"statuses":dict(sorted(statuses.items())),
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})
    steps=[]
    for step in candidate["steps"]:
        sequence=step["sequence"]
        rows=[]
        session_successes=0
        session_status_sets=[]
        for result,_ in evaluations:
            selected=[entry for entry in result["entries"] if entry["stepSequence"]==sequence]
            rows.extend((result["sessionId"],entry) for entry in selected)
            session_successes+=bool(any(entry["observedExpectedChange"] for entry in selected))
            session_status_sets.append(tuple(sorted({entry["status"] for entry in selected})))
        statuses={status:sum(entry["status"]==status for _,entry in rows)
            for status in sorted({entry["status"] for _,entry in rows})}
        scalar_types=sorted({kind for _,entry in rows for kind in (
            _scalar_type(entry["before"]),_scalar_type(entry["after"])) if kind is not None})
        steps.append({"stepSequence":sequence,"targetPath":step["targetPath"],
            "outcomeKey":step["selectedOutcome"]["key"],
            "expected":step["selectedOutcome"]["change"],"attempts":len(rows),
            "sessionsObserved":sum(bool(statuses_for_session)
                for statuses_for_session in session_status_sets),
            "activationEventsObserved":sum(entry["activationObserved"] for _,entry in rows),
            "expectedChangesObserved":sum(entry["observedExpectedChange"] for _,entry in rows),
            "sessionsWithExpectedChange":session_successes,"statuses":statuses,
            "statusConflictObserved":len(statuses)>1,
            "statusConflictAcrossSessions":len(set(session_status_sets))>1,
            "observedScalarTypes":scalar_types,"scalarTypeConflictObserved":len(scalar_types)>1,
            "expectedDirectionAcrossMultipleSessions":session_successes>=2,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False})
    total_runs=sum(item[0]["summary"]["runs"] for item in evaluations)
    complete=sum(item[0]["summary"]["completeClientObservationSequences"]
        for item in evaluations)
    sessions_complete=sum(item[0]["summary"]["completeClientObservationSequences"]>0
        for item in evaluations)
    summary={"sessions":len(evaluations),"runs":total_runs,
        "submittedEntries":sum(item[0]["summary"]["submittedEntries"] for item in evaluations),
        "activationEventsObserved":sum(item[0]["summary"]["activationEventsObserved"]
            for item in evaluations),
        "expectedChangesObserved":sum(item[0]["summary"]["expectedChangesObserved"]
            for item in evaluations),"completeClientObservationSequences":complete,
        "sessionsWithCompleteClientObservationSequence":sessions_complete,
        "stepsWithStatusConflict":sum(step["statusConflictObserved"] for step in steps)}
    return {"schemaVersion":SCHEMA,"placeId":plan["placeId"],"scanId":plan["scanId"],
        "workflowPlanSHA256":evaluator.digest(plan),"candidateId":candidate["id"],
        "sessions":sessions,"steps":steps,"summary":summary,
        "completeSequenceRecurrenceObserved":sessions_complete>=2,
        "sourceAuthenticityVerified":False,"causalityProven":False,
        "serverAuthorityVerified":False,"runtimeVerified":False,"gameplayVerified":False,
        "actionOutcomesVerified":False,
        "note":"Repeated or conflicting digest-bound client observations remain non-causal, non-authoritative, and runtime/gameplay unverified."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workflow_plan",type=Path)
    parser.add_argument("feedback",type=Path,nargs="+")
    parser.add_argument("--output",type=Path,
        default=Path("build/guided-workflow-feedback-aggregate.json"))
    args=parser.parse_args();plan=json.loads(args.workflow_plan.read_text(encoding="utf-8-sig"))
    feedback=[json.loads(path.read_text(encoding="utf-8-sig")) for path in args.feedback]
    result=aggregate(plan,feedback);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False)+"\n")
    print(json.dumps({"output":str(args.output),**result["summary"],"runtimeVerified":False,
        "gameplayVerified":False},sort_keys=True))


if __name__=="__main__":main()
