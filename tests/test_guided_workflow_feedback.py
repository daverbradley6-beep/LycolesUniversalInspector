import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

GENERATOR=load("guided_feedback_generator","generate_guided_workflow.py")
EVALUATOR=load("guided_feedback_evaluator","evaluate_guided_workflow_feedback.py")
CONTROLLED=load("guided_feedback_controlled","controlled_guided_workflow.py")


def identity(name):
    return [{"name":"PlayerGui","className":"PlayerGui","ordinal":1},
        {"name":"HUD","className":"ScreenGui","ordinal":1},
        {"name":name,"className":"TextButton","ordinal":1}]


def step(name,sequence,before,after):
    return {"sequence":sequence,"transactionOrder":sequence,"observedSequence":sequence,
        "targetPath":"PlayerGui.HUD."+name,"targetLabel":name,
        "controlType":"GuiButton.Activated","kind":"guided-gui-activation-trial",
        "pathIdentity":identity(name),"prerequisiteMetadata":{
            "controlClass":"TextButton","text":name,"visible":True,"active":True,
            "selectable":True,"autoButtonColor":True,"interactable":True,
            "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
            "effectiveVisible":True},"selectedOutcome":{"key":"Data.Stage","change":"increased",
                "stateIdentity":[{"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Stage","className":"IntValue","ordinal":1}],
                "observedBefore":before,"observedAfter":after},
        "manualActivationRequired":True,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False}


def plan():
    steps=[step("Select",1,0,1),step("Confirm",2,1,2)]
    claims={key:False for key in GENERATOR.FALSE_CLAIMS}
    return {"schemaVersion":"114.generated-workflow-plan.1","placeId":789,
        "scanId":"guided-feedback-scan","claims":claims,"workflowCandidates":[{
            "id":"guided-flow","transactionId":"transaction-1","steps":steps,"stepCount":2,
            "unmappedLinkedEvents":0,"exactOrderObserved":True,"allStepsGenerationReady":True,
            "operatorStartRequired":True,"manualGuiActivationRequired":True,
            "guidedTrialGenerationReady":True,"automaticallyExecutable":False,
            "executionReady":False,"runtimeVerified":False,"gameplayVerified":False,
            "causalityProven":False}]}


def feedback(document):
    entries=[]
    for sequence,item in enumerate(document["workflowCandidates"][0]["steps"],1):
        entries.append({"sequence":sequence,"runId":1,"stepSequence":sequence,
            "targetPath":item["targetPath"],"outcomeKey":item["selectedOutcome"]["key"],
            "expected":item["selectedOutcome"]["change"],"before":sequence-1,
            "after":sequence,"activationObserved":True,"observedExpectedChange":True,
            "status":"expected-change-observed","message":"Client-visible direction observed",
            "observedAtUnix":1793635200+sequence})
    return {"schemaVersion":EVALUATOR.SCHEMA,"placeId":document["placeId"],
        "scanId":document["scanId"],"workflowPlanSHA256":EVALUATOR.digest(document),
        "candidateId":document["workflowCandidates"][0]["id"],
        "sessionId":"guided-session-1","entries":entries,
        "claims":{key:False for key in EVALUATOR.FALSE_CLAIMS}}


class GuidedWorkflowFeedbackTests(unittest.TestCase):
    def test_generated_trial_exports_plan_bound_feedback(self):
        source=GENERATOR.render(plan())
        for token in (EVALUATOR.SCHEMA,"workflowPlanSHA256=",EVALUATOR.digest(plan()),
                "_G.LycolesGuidedWorkflowFeedback","recordFeedback(",
                "HttpService:JSONEncode(feedback)"):
            self.assertIn(token,source)

    def test_complete_ordered_sequence_is_client_observation_only(self):
        document=plan();result=EVALUATOR.evaluate(document,feedback(document))
        self.assertEqual(result["summary"],{"submittedEntries":2,"runs":1,
            "activationEventsObserved":2,"completeClientObservationSequences":1,
            "expectedChangesObserved":2})
        self.assertEqual(result["runs"][0]["statuses"],{"expected-change-observed":2})
        self.assertTrue(result["runs"][0]["completeClientObservationSequence"])
        self.assertFalse(result["runs"][0]["runtimeVerified"])
        self.assertFalse(result["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])
        self.assertFalse(result["causalityProven"])
    def test_gui_tool_prompt_feedback_remains_client_observation_only(self):
        document=CONTROLLED.three_kind_workflow(789)
        result=EVALUATOR.evaluate(document,feedback(document))
        self.assertEqual(result["summary"]["submittedEntries"],3)
        self.assertEqual(result["summary"]["activationEventsObserved"],3)
        self.assertEqual(result["summary"]["completeClientObservationSequences"],1)
        self.assertFalse(result["runtimeVerified"])
        self.assertFalse(result["gameplayVerified"])
        self.assertFalse(result["causalityProven"])



    def test_digest_candidate_and_step_contract_fail_closed(self):
        document=plan();value=feedback(document);value["workflowPlanSHA256"]="0"*64
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            EVALUATOR.evaluate(document,value)
        value=feedback(document);value["candidateId"]="forged"
        with self.assertRaisesRegex(ValueError,"candidate"):
            EVALUATOR.evaluate(document,value)
        value=feedback(document);value["entries"][1]["targetPath"]="PlayerGui.Forged"
        with self.assertRaisesRegex(ValueError,"entry"):
            EVALUATOR.evaluate(document,value)
        document=plan();other=copy.deepcopy(document["workflowCandidates"][0]);other["id"]="z-flow"
        document["workflowCandidates"].append(other);value=feedback(document);value["candidateId"]="z-flow"
        with self.assertRaisesRegex(ValueError,"candidate"):
            EVALUATOR.evaluate(document,value)

    def test_forged_direction_and_run_order_fail_closed(self):
        document=plan();value=feedback(document);value["entries"][1]["after"]=1
        with self.assertRaisesRegex(ValueError,"outcome claim mismatch"):
            EVALUATOR.evaluate(document,value)
        value=feedback(document);value["entries"][1]["stepSequence"]=1
        with self.assertRaisesRegex(ValueError,"run order"):
            EVALUATOR.evaluate(document,value)

    def test_failure_entry_remains_incomplete_and_unverified(self):
        document=plan();value=feedback(document);value["entries"]=value["entries"][:1]
        value["entries"][0].update({"before":0,"after":0,"activationObserved":False,
            "observedExpectedChange":False,"status":"activation-timeout",
            "message":"Normal user activation was not observed"})
        result=EVALUATOR.evaluate(document,value)
        self.assertEqual(result["summary"]["completeClientObservationSequences"],0)
        self.assertFalse(result["runs"][0]["completeClientObservationSequence"])
        self.assertFalse(result["actionOutcomesVerified"])
        value=feedback(document);value["entries"]=value["entries"][:1]
        value["entries"][0].update({"activationObserved":False,
            "observedExpectedChange":False,"status":"activation-timeout"})
        value["entries"][0].pop("before");value["entries"][0].pop("after")
        with self.assertRaisesRegex(ValueError,"status contract"):
            EVALUATOR.evaluate(document,value)
        with self.assertRaisesRegex(ValueError,"workflow plan"):
            EVALUATOR.evaluate([],value)


if __name__=="__main__":unittest.main()
