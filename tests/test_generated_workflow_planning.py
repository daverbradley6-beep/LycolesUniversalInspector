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
generator=load("generated_workflow_generator","generate_guided_workflow.py")

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


def state_change(before,after):
    return [{"key":"Data.ShopStage","before":before,"after":after,
        "stateIdentityStatus":"component-resolved","stateIdentity":[
            {"name":"Data","className":"Folder","ordinal":1},
            {"name":"ShopStage","className":"IntValue","ordinal":1}]}]


def tool_event(sequence,before,after,transaction="mixed-flow"):
    return {"path":"LocalPlayer.Backpack.Sword","pathIdentity":[
            {"name":"LocalPlayer","className":"Player","ordinal":1},
            {"name":"Backpack","className":"Backpack","ordinal":1},
            {"name":"Sword","className":"Tool","ordinal":1}],
        "controlType":"Tool.Activated","featureCandidate":"combat",
        "transactionId":transaction,"sequence":sequence,
        "controlMetadata":{"tooltip":"Train","requiresHandle":True,"canBeDropped":False,
            "enabled":True,"manualActivationOnly":False},
        "stateChanges":state_change(before,after)}


def prompt_event(sequence,before,after,transaction="mixed-flow"):
    return {"path":"Workspace.Shop.Door.Prompt","pathIdentity":[
            {"name":"Workspace","className":"Workspace","ordinal":1},
            {"name":"Shop","className":"Model","ordinal":1},
            {"name":"Door","className":"Part","ordinal":1},
            {"name":"Prompt","className":"ProximityPrompt","ordinal":1}],
        "controlType":"ProximityPrompt.Triggered","featureCandidate":"shops",
        "transactionId":transaction,"sequence":sequence,
        "controlMetadata":{"actionText":"Open","objectText":"Shop Door","enabled":True,
            "holdDuration":0,"maxActivationDistance":10,"keyboardKeyCode":"E",
            "gamepadKeyCode":"ButtonX","anchorPath":"Workspace.Shop.Door",
            "anchorPosition":{"x":1,"y":2,"z":3}},
        "stateChanges":state_change(before,after)}


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
        self.assertEqual(candidate["steps"][1]["entryStatePrerequisite"],{
            "key":"Data.ShopStage","value":3,"stateIdentity":[
                {"name":"Data","className":"Folder","ordinal":1},
                {"name":"ShopStage","className":"IntValue","ordinal":1}],
            "classification":"exact-observed-entry-state","causalityProven":False})
        self.assertFalse(candidate["automaticallyExecutable"])
        self.assertTrue(candidate["executionReady"])
        self.assertEqual(candidate["executionMode"],"mixed-guided")
        self.assertFalse(result["claims"]["causalityProven"])
        self.assertEqual(result["summary"]["executionReadyWorkflows"],1)
        self.assertTrue(all(step["observationBaseline"]=={
            "timing":"unknown","preActivationBaselineAvailable":False,
            "possibleSynchronousLoss":True} for step in candidate["steps"]))
        forged=copy.deepcopy(result)
        forged["workflowCandidates"][0]["steps"][0]["observationBaseline"][
            "possibleSynchronousLoss"]=False
        with self.assertRaisesRegex(ValueError,"step contract"):
            generator.validate(forged)



    def test_request_alignment_ranks_executable_workflows_before_lexical_order(self):
        value=plan();value["requestedCapability"]="Train with the sword in combat"
        value["observedInteractionHistory"]=[
            event("Select",1,0,1,"a-shop"),event("Confirm",2,1,2,"a-shop"),
            tool_event(3,2,3,"z-combat"),tool_event(4,3,4,"z-combat")]
        result=self.analyze(value);candidates=result["workflowCandidates"]
        self.assertEqual(len(candidates),2)
        self.assertEqual(candidates[0]["transactionId"],"z-combat")
        self.assertEqual(candidates[0]["selection"]["matchedTerms"],["combat","sword"])
        self.assertGreater(candidates[0]["selection"]["requestScore"],
            candidates[1]["selection"]["requestScore"])
        self.assertEqual(result["summary"]["requestAlignedWorkflows"],1)
        self.assertEqual(result["summary"]["selectedExecutionCandidateId"],candidates[0]["id"])

    def test_malformed_requested_capability_fails_closed(self):
        value=plan();value["requestedCapability"]="x"*1001
        with self.assertRaisesRegex(ValueError,"requested capability"):
            self.analyze(value)

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


    def test_mixed_gui_tool_prompt_workflow_is_generation_ready(self):
        value=plan();value["observedInteractionHistory"]=[
            event("Select",1,0,1,"mixed-flow"),tool_event(2,1,2),prompt_event(3,2,3)]
        result=self.analyze(value);candidate=result["workflowCandidates"][0]
        self.assertEqual([step["kind"] for step in candidate["steps"]],[
            "guided-gui-activation-trial","official-tool-activation-trial",
            "proximity-prompt-trial"])
        self.assertTrue(candidate["guidedTrialGenerationReady"])
        self.assertEqual(candidate["executionMode"],"mixed-guided")
        self.assertTrue(candidate["executionReady"])
        self.assertFalse(candidate["automaticallyExecutable"])
        self.assertEqual(result["summary"]["executionReadyWorkflows"],1)

    def test_tool_prompt_workflow_is_bounded_automatic_candidate(self):
        value=plan();value["observedInteractionHistory"]=[
            tool_event(1,0,1,"automatic-flow"),prompt_event(2,1,2,"automatic-flow")]
        candidate=self.analyze(value)["workflowCandidates"][0]
        self.assertTrue(candidate["guidedTrialGenerationReady"])
        self.assertEqual(candidate["executionMode"],"bounded-automatic")
        self.assertTrue(candidate["executionReady"])
        self.assertTrue(candidate["automaticallyExecutable"])
        self.assertFalse(candidate["runtimeVerified"])
        self.assertFalse(candidate["gameplayVerified"])

    def test_long_repeated_action_sequence_is_generation_ready(self):
        value=plan();value["observedInteractionHistory"]=[
            (tool_event if sequence%2 else prompt_event)(sequence,sequence-1,sequence,"long-flow")
            for sequence in range(1,25)]
        result=self.analyze(value);candidate=result["workflowCandidates"][0]
        self.assertEqual(candidate["stepCount"],24)
        self.assertEqual([step["kind"] for step in candidate["steps"][:4]],[
            "official-tool-activation-trial","proximity-prompt-trial",
            "official-tool-activation-trial","proximity-prompt-trial"])
        self.assertTrue(candidate["executionReady"])
        self.assertEqual(len(generator.validate(result)[0]["steps"]),24)

    def test_sequence_over_sixty_four_steps_stays_review_only(self):
        value=plan();value["observedInteractionHistory"]=[
            tool_event(sequence,sequence-1,sequence,"over-bound") for sequence in range(1,66)]
        result=self.analyze(value);candidate=result["workflowCandidates"][0]
        self.assertEqual(candidate["stepCount"],65)
        self.assertFalse(candidate["executionReady"])
        self.assertEqual(candidate["executionMode"],"review-only")
        self.assertIn("Workflow exceeds the bounded 64-step generation limit",candidate["blockers"])
        self.assertEqual(generator.validate(result),[])


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
