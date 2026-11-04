"""Evidence-bounded generated-control workflow planning tests."""
import copy
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

discovery=load("workflow_action_discovery","discover_action_capabilities.py")
planner=load("generated_workflow_planner","plan_generated_workflows.py")

def identity(button):
    return [{"name":"PlayerGui","className":"PlayerGui","ordinal":1},
        {"name":"HUD","className":"ScreenGui","ordinal":1},
        {"name":"Shop","className":"Frame","ordinal":1},
        {"name":button,"className":"TextButton","ordinal":1}]

def event(button,sequence,before,after,transaction="shop-flow"):
    return {"path":"PlayerGui.HUD.Shop."+button,"pathIdentity":identity(button),
        "controlType":"GuiButton.Activated","featureCandidate":"shops",
        "transactionId":transaction,"sequence":sequence,
        "controlMetadata":{"controlClass":"TextButton","text":button,
            "visible":True,"active":True,"selectable":True,"autoButtonColor":True,
            "interactable":True,"ancestorVisible":True,"screenEnabled":True,
            "withinScrollingBounds":True,"effectiveVisible":True},
        "stateChanges":[{"key":"Data.ShopStage","before":before,"after":after,
            "stateIdentityStatus":"component-resolved","stateIdentity":[
                {"name":"Data","className":"Folder","ordinal":1},
                {"name":"ShopStage","className":"IntValue","ordinal":1}]}]}

def plan():
    return {"integrity":{"scanComplete":True,"placeId":789,"scanId":"workflow-scan"},
        "requestedCapability":"Complete the observed shop flow","features":[],
        "actionableObjects":[],"observedInteractionHistory":[
            event("Select",1,2,3),event("Confirm",2,3,4)]}

class GeneratedWorkflowPlanningTests(unittest.TestCase):
    def analyze(self,value):
        actions=discovery.analyze(value)
        return planner.plan(value,actions)

    def test_explicitly_linked_generated_controls_form_reviewable_candidate(self):
        result=self.analyze(plan())
        self.assertEqual(result["schemaVersion"],"114.generated-workflow-plan.1")
        self.assertEqual(result["summary"]["workflowCandidates"],1)
        candidate=result["workflowCandidates"][0]
        self.assertEqual([step["targetLabel"] for step in candidate["steps"]],
            ["Select","Confirm"])
        self.assertTrue(candidate["exactOrderObserved"])
        self.assertTrue(candidate["allStepsGenerationReady"])
        self.assertTrue(candidate["manualGuiActivationRequired"])
        self.assertTrue(candidate["guidedTrialGenerationReady"])
        self.assertEqual(result["summary"]["guidedTrialGenerationReadyWorkflows"],1)
        self.assertEqual(candidate["stateContinuityLinks"],[{"fromStep":1,"toStep":2,
            "stateKey":"Data.ShopStage","value":3,
            "classification":"observed-state-continuity","causalityProven":False}])
        self.assertFalse(candidate["automaticallyExecutable"])
        self.assertFalse(candidate["executionReady"])
        self.assertFalse(result["claims"]["causalityProven"])
        self.assertEqual(result["summary"]["executionReadyWorkflows"],0)

    def test_unlinked_or_partially_ready_events_do_not_form_workflow(self):
        value=plan()
        for item in value["observedInteractionHistory"]:item.pop("transactionId")
        self.assertEqual(self.analyze(value)["workflowCandidates"],[])
        value=plan();value["observedInteractionHistory"][1]["controlMetadata"]["visible"]=False
        value["observedInteractionHistory"][1]["controlMetadata"]["effectiveVisible"]=False
        self.assertEqual(self.analyze(value)["workflowCandidates"],[])

    def test_duplicate_sequence_and_forged_claim_fail_closed(self):
        value=plan();value["observedInteractionHistory"][1]["sequence"]=1
        actions=discovery.analyze(value)
        with self.assertRaisesRegex(ValueError,"Duplicate sequence"):
            planner.plan(value,actions)
        value=plan();actions=discovery.analyze(value);actions["claims"]["causalityProven"]=True
        with self.assertRaisesRegex(ValueError,"claims mismatch"):
            planner.plan(value,actions)

    def test_exact_determinism(self):
        value=plan();actions=discovery.analyze(value)
        self.assertEqual(planner.plan(value,actions),planner.plan(copy.deepcopy(value),copy.deepcopy(actions)))

    def test_legacy_flat_paths_remain_single_control_compatible_but_not_workflow_ready(self):
        value=plan();actions=discovery.analyze(value)
        for target in actions["guiInteractions"]["targets"]:
            target["identityMode"]="legacy-flat-path";target["pathIdentity"]=None
            target["selectedOutcome"]["stateIdentity"]=None
        result=planner.plan(value,actions)
        self.assertEqual(result["workflowCandidates"],[])
        self.assertEqual(result["summary"]["executionReadyWorkflows"],0)

    def test_unmapped_intermediate_event_is_disclosed_and_breaks_continuity(self):
        value=plan();value["observedInteractionHistory"][1]["sequence"]=3
        value["observedInteractionHistory"].insert(1,{"transactionId":"shop-flow","sequence":2,
            "path":"PlayerGui.HUD.Shop.Unknown","controlType":"GuiButton.Activated"})
        candidate=self.analyze(value)["workflowCandidates"][0]
        self.assertFalse(candidate["allStepsGenerationReady"])
        self.assertFalse(candidate["guidedTrialGenerationReady"])
        self.assertEqual(candidate["unmappedLinkedEvents"],1)
        self.assertEqual([step["transactionOrder"] for step in candidate["steps"]],[1,3])
        self.assertEqual(candidate["stateContinuityLinks"],[])
        self.assertIn("One or more linked events lack exact generation-ready contracts",
            candidate["blockers"])

    def test_forged_step_snapshot_or_identity_fails_closed(self):
        value=plan();actions=discovery.analyze(value)
        actions["guiInteractions"]["targets"][0]["guiMetadata"]["text"]="Forged"
        with self.assertRaisesRegex(ValueError,"step evidence drift"):
            planner.plan(value,actions)
        actions=discovery.analyze(value)
        actions["guiInteractions"]["targets"][0]["pathIdentity"][-1]["ordinal"]=2
        with self.assertRaisesRegex(ValueError,"step evidence drift"):
            planner.plan(value,actions)

if __name__=="__main__":unittest.main()
