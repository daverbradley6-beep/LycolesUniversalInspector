"""Bounded mixed-action workflow generator tests."""
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
            "effectiveVisible":True},"entryStatePrerequisite":{"key":"Data.Stage",
                "value":sequence-1,"stateIdentity":[
                    {"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Stage","className":"IntValue","ordinal":1}],
                "classification":"exact-observed-entry-state","causalityProven":False},
            "selectedOutcome":{"key":"Data.Stage","change":"increased",
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


def tool_step(sequence):
    value=step("Sword",sequence)
    value.update(targetPath="LocalPlayer.Backpack.Sword",targetLabel="Sword",
        controlType="Tool.Activated",kind="official-tool-activation-trial",
        activationMode="official-tool-activate",pathIdentity=[
            {"name":"LocalPlayer","className":"Player","ordinal":1},
            {"name":"Backpack","className":"Backpack","ordinal":1},
            {"name":"Sword","className":"Tool","ordinal":1}],
        prerequisiteMetadata={"tooltip":"Train","requiresHandle":True,
            "canBeDropped":False,"enabled":True,"manualActivationOnly":False},
        manualActivationRequired=False)
    return value


def prompt_step(sequence):
    value=step("Prompt",sequence)
    value.update(targetPath="Workspace.Shop.Door.Prompt",targetLabel="Shop Door",
        controlType="ProximityPrompt.Triggered",kind="proximity-prompt-trial",
        activationMode="executor-fireproximityprompt",pathIdentity=[
            {"name":"Workspace","className":"Workspace","ordinal":1},
            {"name":"Shop","className":"Model","ordinal":1},
            {"name":"Door","className":"Part","ordinal":1},
            {"name":"Prompt","className":"ProximityPrompt","ordinal":1}],
        prerequisiteMetadata={"actionText":"Open","objectText":"Shop Door","enabled":True,
            "holdDuration":0,"maxActivationDistance":10,"keyboardKeyCode":"E",
            "gamepadKeyCode":"ButtonX","anchorPath":"Workspace.Shop.Door",
            "anchorPosition":{"x":1,"y":2,"z":3}},manualActivationRequired=False)
    return value


def mixed_document(automatic=False):
    value=document();steps=[tool_step(1),prompt_step(2)] if automatic else [
        step("Select",1),tool_step(2),prompt_step(3)]
    if not automatic:steps[0]["activationMode"]="normal-user-gui-activation"
    candidate=value["workflowCandidates"][0];candidate.update(steps=steps,stepCount=len(steps),
        manualGuiActivationRequired=not automatic,executionMode=(
            "bounded-automatic" if automatic else "mixed-guided"),
        automaticallyExecutable=automatic,executionReady=True)
    return value


class GuidedWorkflowGeneratorTests(unittest.TestCase):
    def test_generates_user_mediated_multi_step_trial(self):
        source=generator.render(document())
        self.assertIn("assert(game.PlaceId == 789",source)
        self.assertIn('title.Text="Guided workflow (guided-flow)"',source)
        self.assertIn('button.Activated:Connect(function() activated=true end)',source)
        self.assertIn('for index,step in ipairs(steps) do',source)
        self.assertIn('requiredBefore=0',source)
        self.assertIn('before~=requiredBefore',source)
        self.assertIn('local maxRunAttempts=5',source)
        self.assertIn('runAttempts>=maxRunAttempts',source)
        self.assertIn('activate highlighted',source)
        self.assertIn('causality and gameplay remain unverified',source)
        self.assertNotIn("firesignal",source.lower())
        self.assertNotIn("virtualinput",source.lower())
        self.assertNotIn("button:Activate",source)
        self.assertNotIn("FireServer(",source)

    def test_generates_operator_armed_bounded_repeat_with_continuity_guard(self):
        source=generator.render(document())
        self.assertIn('makeButton("RepeatGuidedWorkflow","REPEAT: OFF"',source)
        self.assertIn('local maxRunAttempts=5',source)
        self.assertIn('while running do',source)
        self.assertIn('local requiredBefore=firstSequence and step.outcome.requiredBefore',source)
        self.assertIn('or continuity[state]',source)
        self.assertIn('continuity[state]=after',source)
        self.assertIn('Stopped at the bounded five-sequence limit',source)
        self.assertIn('repeatRequested=not repeatRequested',source)
        self.assertIn('STOP cancels immediately',source)


    def test_generates_mixed_gui_tool_prompt_execution(self):
        source=generator.render(mixed_document())
        self.assertIn('kind="guided-gui-activation-trial"',source)
        self.assertIn('kind="official-tool-activation-trial"',source)
        self.assertIn('kind="proximity-prompt-trial"',source)
        self.assertIn('local activated=pcall(function() tool:Activate() end)',source)
        self.assertIn('type(fireproximityprompt)~="function"',source)
        self.assertIn('pcall(function() fireproximityprompt(prompt) end)',source)
        self.assertIn('local function teleportToPrompt(prompt)',source)
        self.assertIn('local function promptMetadataMatches(prompt,expected)',source)
        self.assertNotIn('FireServer(',source)

    def test_generates_operator_started_bounded_automatic_sequence(self):
        source=generator.render(mixed_document(automatic=True))
        self.assertIn('activationMode="official-tool-activate"',source)
        self.assertIn('activationMode="executor-fireproximityprompt"',source)
        self.assertNotIn('kind="guided-gui-activation-trial"',source)
        self.assertIn('for index,step in ipairs(steps) do',source)
    def test_prompt_anchor_metadata_and_activation_mode_fail_closed(self):
        value=mixed_document();value["workflowCandidates"][0]["steps"][2][
            "prerequisiteMetadata"].pop("anchorPosition")
        with self.assertRaisesRegex(ValueError,"step contract"):
            generator.render(value)
        value=mixed_document();value["workflowCandidates"][0]["steps"][1][
            "activationMode"]="synthetic-tool-event"
        with self.assertRaisesRegex(ValueError,"step"):
            generator.render(value)




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

    def test_request_selection_chooses_highest_scored_eligible_candidate(self):
        value=document();first=value["workflowCandidates"][0]
        first["selection"]={"requestAligned":False,"requestScore":0,
            "matchedTerms":[],"requestedTerms":["combat"]}
        second=copy.deepcopy(first);second["id"]="request-aligned";second["transactionId"]="z"
        for step in second["steps"]:step["targetFeature"]="combat"
        second["selection"]={"requestAligned":True,"requestScore":5,
            "matchedTerms":["combat"],"requestedTerms":["combat"]}
        value["workflowCandidates"].append(second)
        source=generator.render(value)
        self.assertIn("Guided workflow (request-aligned)",source)
        second["selection"]["requestScore"]=0
        with self.assertRaisesRegex(ValueError,"selection"):
            generator.render(value)


    def test_source_validator_rejects_missing_safeguard_and_synthetic_activation(self):
        source=generator.render(document())
        with self.assertRaisesRegex(ValueError,"Missing guided workflow safeguard"):
            generator.validate_source(source.replace("No GUI event is synthesized","removed"),789)
        for unsafe in ("firesignal(button.Activated)","setclipboard(payload)",
                "HttpService:PostAsync(url,payload)","untrusted:Activate()"):
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
        value=document();value["workflowCandidates"][0]["steps"][0][
            "entryStatePrerequisite"]["value"]=99
        with self.assertRaisesRegex(ValueError,"step contract"):
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
        self.assertIn('controlClass="ImageButton"',source)
        self.assertIn('text=""',source)

    def test_no_eligible_candidate_returns_none_and_input_is_not_mutated(self):
        value=document();value["workflowCandidates"][0]["guidedTrialGenerationReady"]=False
        before=copy.deepcopy(value)
        self.assertIsNone(generator.render(value))
        self.assertEqual(value,before)

if __name__=="__main__":unittest.main()
