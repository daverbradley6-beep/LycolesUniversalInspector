"""Manual-only guided GUI workflow generator tests."""
import copy
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("guided_workflow",
    ROOT/"tools"/"generate_guided_workflow.py")
generator=importlib.util.module_from_spec(spec);spec.loader.exec_module(generator)

def identity(button):
    return [{"name":"PlayerGui","className":"PlayerGui","ordinal":1},
        {"name":"HUD","className":"ScreenGui","ordinal":1},
        {"name":button,"className":"TextButton","ordinal":1}]

def step(button,sequence):
    return {"sequence":sequence,"transactionOrder":sequence,"observedSequence":sequence,
        "targetPath":"PlayerGui.HUD."+button,"targetLabel":button,
        "controlType":"GuiButton.Activated","kind":"guided-gui-activation-trial",
        "pathIdentity":identity(button),"prerequisiteMetadata":{
            "controlClass":"TextButton","text":button,"visible":True,"active":True,
            "selectable":True,"autoButtonColor":True,"interactable":True,
            "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
            "effectiveVisible":True},"selectedOutcome":{"key":"Data.Stage","change":"increased",
                "stateIdentity":[{"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Stage","className":"IntValue","ordinal":1}],
                "observedBefore":sequence-1,"observedAfter":sequence},
        "manualActivationRequired":True,"runtimeVerified":False,
        "gameplayVerified":False,"causalityProven":False}

def document():
    steps=[step("Select",1),step("Confirm",2)]
    claims={key:False for key in generator.FALSE_CLAIMS}
    return {"schemaVersion":"114.generated-workflow-plan.1","placeId":789,
        "scanId":"guided-workflow-scan","claims":claims,"workflowCandidates":[{
            "id":"guided-flow","transactionId":"flow","steps":steps,"stepCount":2,
            "unmappedLinkedEvents":0,"exactOrderObserved":True,
            "allStepsGenerationReady":True,"operatorStartRequired":True,
            "manualGuiActivationRequired":True,"guidedTrialGenerationReady":True,
            "automaticallyExecutable":False,"executionReady":False,
            "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False}]}

class GuidedWorkflowGeneratorTests(unittest.TestCase):
    def test_generates_user_mediated_multi_step_trial(self):
        source=generator.render(document())
        self.assertIn("assert(game.PlaceId == 789",source)
        self.assertIn('title.Text="Guided workflow (guided-flow)"',source)
        self.assertIn('button.Activated:Connect(function() activated=true end)',source)
        self.assertIn('for index,step in ipairs(steps) do',source)
        self.assertIn('click highlighted',source)
        self.assertIn('causality and gameplay remain unverified',source)
        self.assertNotIn("firesignal",source.lower())
        self.assertNotIn("virtualinput",source.lower())
        self.assertNotIn("button:Activate",source)
        self.assertNotIn("FireServer(",source)

    def test_automatic_or_incomplete_candidate_fails_closed(self):
        value=document();value["workflowCandidates"][0]["automaticallyExecutable"]=True
        with self.assertRaisesRegex(ValueError,"candidate"):
            generator.render(value)
        value=document();value["workflowCandidates"][0]["unmappedLinkedEvents"]=1
        with self.assertRaisesRegex(ValueError,"candidate"):
            generator.render(value)

    def test_metadata_drift_and_positive_claim_fail_closed(self):
        value=document();value["workflowCandidates"][0]["steps"][0]["prerequisiteMetadata"]["visible"]=False
        with self.assertRaisesRegex(ValueError,"step contract"):
            generator.render(value)
        value=document();value["claims"]["causalityProven"]=True
        with self.assertRaisesRegex(ValueError,"claims"):
            generator.render(value)

    def test_source_validator_rejects_missing_safeguard_and_synthetic_activation(self):
        source=generator.render(document())
        with self.assertRaisesRegex(ValueError,"Missing guided workflow safeguard"):
            generator.validate_source(source.replace("No GUI event is synthesized","removed"),789)
        for unsafe in ("firesignal(button.Activated)","setclipboard(payload)",
                "HttpService:PostAsync(url,payload)"):
            with self.subTest(unsafe=unsafe),self.assertRaisesRegex(
                    ValueError,"Forbidden guided workflow operation"):
                generator.validate_source(source+"\n"+unsafe+"\n",789)

    def test_candidate_id_is_luau_escaped(self):
        value=document();value["workflowCandidates"][0]["id"]='guided"\\flow'
        source=generator.render(value)
        self.assertIn('title.Text="Guided workflow (guided\\"\\\\flow)"',source)

    def test_forged_transition_identity_and_order_fail_closed(self):
        value=document();value["workflowCandidates"][0]["steps"][0]["selectedOutcome"]["observedAfter"]=0
        with self.assertRaisesRegex(ValueError,"step contract"):
            generator.render(value)
        value=document();value["workflowCandidates"][0]["steps"][0]["selectedOutcome"]["stateIdentity"][0]["name"]="Other"
        with self.assertRaisesRegex(ValueError,"step contract"):
            generator.render(value)
        value=document();value["workflowCandidates"][0]["steps"][1]["transactionOrder"]=1
        with self.assertRaisesRegex(ValueError,"step order"):
            generator.render(value)
        value=document();value["workflowCandidates"][0].pop("transactionId")
        with self.assertRaisesRegex(ValueError,"candidate"):
            generator.render(value)

    def test_image_buttons_allow_empty_text_and_optional_interactable(self):
        value=document()
        for item in value["workflowCandidates"][0]["steps"]:
            item["pathIdentity"][-1]["className"]="ImageButton"
            metadata=item["prerequisiteMetadata"]
            metadata["controlClass"]="ImageButton";metadata["text"]=""
            metadata["selectable"]=False;metadata["autoButtonColor"]=False
            metadata.pop("interactable")
        source=generator.render(value)
        self.assertIn('controlClass="ImageButton",text=""',source)

    def test_no_eligible_candidate_returns_none_and_input_is_not_mutated(self):
        value=document();value["workflowCandidates"][0]["guidedTrialGenerationReady"]=False
        before=copy.deepcopy(value)
        self.assertIsNone(generator.render(value))
        self.assertEqual(value,before)

if __name__=="__main__":unittest.main()
