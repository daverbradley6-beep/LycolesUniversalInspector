import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

FIXTURES=load("aggregate_guided_fixture","../tests/test_guided_workflow_feedback.py")
AGGREGATOR=load("guided_feedback_aggregator","aggregate_guided_workflow_feedback.py")


class AggregateGuidedWorkflowFeedbackTests(unittest.TestCase):
    def documents(self):
        document=FIXTURES.plan();first=FIXTURES.feedback(document)
        first["sessionId"]="session-a"
        second=FIXTURES.feedback(document);second["sessionId"]="session-b"
        second["entries"].append({"sequence":3,"runId":2,"stepSequence":1,
            "targetPath":document["workflowCandidates"][0]["steps"][0]["targetPath"],
            "outcomeKey":"Data.Stage","expected":"increased","before":2,"after":2,
            "activationObserved":False,"observedExpectedChange":False,
            "status":"activation-timeout","message":"Normal user activation not observed",
            "observedAtUnix":1793635300})
        return document,first,second

    def test_aggregates_recurrence_and_status_conflicts_without_verification(self):
        document,first,second=self.documents()
        result=AGGREGATOR.aggregate(document,[first,second])
        self.assertEqual(result["summary"],{"sessions":2,"runs":3,
            "submittedEntries":5,"activationEventsObserved":4,
            "expectedChangesObserved":4,"completeClientObservationSequences":2,
            "sessionsWithCompleteClientObservationSequence":2,
            "stepsWithStatusConflict":1})
        self.assertTrue(result["completeSequenceRecurrenceObserved"])
        self.assertEqual(result["steps"][0]["statuses"],{
            "activation-timeout":1,"expected-change-observed":2})
        self.assertTrue(result["steps"][0]["statusConflictObserved"])
        self.assertTrue(result["steps"][0]["expectedDirectionAcrossMultipleSessions"])
        self.assertFalse(result["steps"][1]["statusConflictObserved"])
        for claim in AGGREGATOR.FALSE_CLAIMS:
            self.assertFalse(result[claim])

    def test_output_is_deterministic_across_input_order(self):
        document,first,second=self.documents()
        one=AGGREGATOR.aggregate(document,[first,second])
        two=AGGREGATOR.aggregate(document,[second,first])
        self.assertEqual(json.dumps(one,sort_keys=True),json.dumps(two,sort_keys=True))
        self.assertEqual([item["sessionId"] for item in one["sessions"]],
            ["session-a","session-b"])

    def test_duplicate_session_and_forged_feedback_fail_closed(self):
        document,first,second=self.documents();second["sessionId"]="session-a"
        with self.assertRaisesRegex(ValueError,"Duplicate guided feedback session"):
            AGGREGATOR.aggregate(document,[first,second])
        second=copy.deepcopy(first);second["sessionId"]="session-b"
        second["workflowPlanSHA256"]="0"*64
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            AGGREGATOR.aggregate(document,[first,second])

    def test_cli_writes_deterministic_aggregate(self):
        document,first,second=self.documents()
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);plan_path=base/"plan.json";one=base/"one.json";two=base/"two.json"
            output=base/"aggregate.json";plan_path.write_text(json.dumps(document))
            one.write_text(json.dumps(first));two.write_text(json.dumps(second))
            result=subprocess.run([sys.executable,
                str(ROOT/"tools"/"aggregate_guided_workflow_feedback.py"),str(plan_path),
                str(two),str(one),"--output",str(output)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            aggregate=json.loads(output.read_text())
            self.assertEqual(aggregate["summary"]["sessions"],2)
            self.assertFalse(aggregate["runtimeVerified"])

    def test_inventory_bounds_and_positive_claims_fail_closed(self):
        document,first,_=self.documents()
        with self.assertRaisesRegex(ValueError,"one to 100"):
            AGGREGATOR.aggregate(document,[])
        with self.assertRaisesRegex(ValueError,"one to 100"):
            AGGREGATOR.aggregate(document,[first]*101)
        first["claims"]["runtimeVerified"]=True
        with self.assertRaisesRegex(ValueError,"claims"):
            AGGREGATOR.aggregate(document,[first])


if __name__=="__main__":unittest.main()
