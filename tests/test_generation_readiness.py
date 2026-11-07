"""Request-to-generation readiness synthesis tests."""
import copy
import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/filename)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


understanding=load("readiness_gameplay","understand_gameplay.py")
discovery=load("readiness_actions","discover_action_capabilities.py")
readiness=load("generation_readiness","assess_generation_readiness.py")
workflow_fixtures=load("readiness_workflow_fixtures","../tests/test_generated_workflow_planning.py")
feedback_evaluator=load("readiness_guided_feedback","evaluate_guided_workflow_feedback.py")

def feature(name,interactions=0,candidates=0):
    return {"feature":name,"interactionEvents":interactions,"observedEvents":interactions,
        "verifiedClientOutcomes":0,"clientCorroboratedEvents":0,
        "temporalTransitionEvents":interactions,"observableOutcomeCandidates":candidates,
        "featureStateCorrelations":candidates,"featureGuiCorrelations":0,
        "status":"observable-outcome-candidate-unverified" if candidates else "discovered",
        "implementationReady":False,"reason":"passive evidence"}

def egg_plan(request="Automatically hatch the selected egg in multi mode"):
    return {"integrity":{"scanComplete":True,"placeId":85896571713843,
            "scanId":"generation-egg-scan"},"requestedCapability":request,
        "features":[feature("pets",1,1)],"actionableObjects":[],
        "observedInteractionHistory":[{
            "path":"Workspace.Eggs.Rainbow.Prompt","controlType":"ProximityPrompt.Triggered",
            "featureCandidate":"pets","controlMetadata":{"actionText":"Hatch",
                "objectText":"Rainbow Egg","enabled":True,"holdDuration":0,
                "maxActivationDistance":10},
            "stateChanges":[{"key":"leaderstats.Hatches","before":4,"after":5}],
            "outcomeVerified":False,"workflow":{"phase":"initiated","action":"hatch",
                "confidence":"bounded-name-context-heuristic","verified":False}}]}

def assess(plan):
    gameplay=understanding.analyze(plan);actions=discovery.analyze(plan)
    return readiness.assess(plan,gameplay,actions)


def guided_feedback(workflow,session_id):
    candidate=workflow["workflowCandidates"][0];entries=[]
    for sequence,step in enumerate(candidate["steps"],1):
        outcome=step["selectedOutcome"]
        entries.append({"sequence":sequence,"runId":1,"stepSequence":sequence,
            "targetPath":step["targetPath"],"outcomeKey":outcome["key"],
            "expected":outcome["change"],"before":outcome["observedBefore"],
            "after":outcome["observedAfter"],"activationObserved":True,
            "observedExpectedChange":True,"status":"expected-change-observed",
            "message":"Selected client-visible direction observed",
            "observedAtUnix":1793635200+sequence})
    return {"schemaVersion":feedback_evaluator.SCHEMA,"placeId":workflow["placeId"],
        "scanId":workflow["scanId"],"workflowPlanSHA256":feedback_evaluator.digest(workflow),
        "candidateId":candidate["id"],"sessionId":session_id,"entries":entries,
        "claims":{key:False for key in feedback_evaluator.FALSE_CLAIMS}}


class GenerationReadinessTests(unittest.TestCase):
    def test_egg_request_reports_generated_single_trial_and_unavailable_multi(self):
        result=assess(egg_plan())
        self.assertEqual(result["schemaVersion"],"113.generation-readiness.1")
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertTrue(result["request"]["generatedSubsetAvailable"])
        self.assertFalse(result["request"]["fullRequestImplemented"])
        generated=result["generatedCapabilities"][0]
        self.assertEqual(generated["kind"],"proximity-prompt-trial")
        self.assertEqual(generated["targetLabel"],"Rainbow Egg")
        self.assertTrue(generated["automaticMovement"])
        self.assertTrue(generated["boundedRepeat"])
        self.assertTrue(generated["operatorStartRequired"])
        unavailable={item["id"]:item for item in result["unavailableRequestedBehavior"]}
        self.assertIn("multi-game-mode",unavailable)
        self.assertIn("auto-game-mode",unavailable)
        request_feature=result["requestFeatureReadiness"]
        self.assertEqual(request_feature["schemaVersion"],"113.request-feature-readiness.1")
        self.assertEqual(request_feature["status"],"bounded-generated-subset")
        self.assertIn("request-assessment:mode_selection_observation",
                      request_feature["explicitBlockers"])
        self.assertIn("unavailable:auto-game-mode",request_feature["explicitBlockers"])
        self.assertFalse(request_feature["nameMatchingSufficientForImplementation"])
        self.assertFalse(request_feature["temporalCorrelationSufficientForImplementation"])
        self.assertFalse(result["claims"]["runtimeVerified"])
        self.assertFalse(result["claims"]["gameplayVerified"])

    def test_generic_reward_prompt_supports_request_aligned_bounded_subset(self):
        value=egg_plan("Automatically claim the daily reward")
        value["integrity"]["placeId"]=123
        value["integrity"]["scanId"]="daily-reward-scan"
        value["features"]=[feature("rewards",1,1)]
        event=value["observedInteractionHistory"][0]
        event.update({"path":"Workspace.Rewards.Daily.ClaimPrompt",
            "featureCandidate":"rewards","controlMetadata":{"actionText":"Claim",
                "objectText":"Daily Reward","enabled":True,"holdDuration":0.5,
                "maxActivationDistance":12},
            "stateChanges":[{"key":"Data.DailyClaims","before":2,"after":3}]})
        event["workflow"]["action"]="claim"
        result=assess(value)
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        generated=result["generatedCapabilities"][0]
        self.assertEqual(generated["targetLabel"],"Daily Reward")
        self.assertEqual(generated["commands"],
            ["interaction","interactionstart","interactionstop","interactions"])
        self.assertEqual(generated["observationBaseline"]["classification"],"timing-unknown")
        self.assertEqual(generated["observationBaseline"]["readinessImpact"],"limitations-only")
        self.assertEqual(result["unavailableRequestedBehavior"],[])
        self.assertFalse(result["request"]["fullRequestImplemented"])

    def test_fps_tool_evidence_stays_discovery_only_without_replay(self):
        value={"integrity":{"scanComplete":True,"placeId":456,"scanId":"fps-scan"},
            "requestedCapability":"Automatically attack visible enemies",
            "features":[feature("combat",1,0)],
            "actionableObjects":[{"path":"LocalPlayer.Backpack.Assault Rifle","class":"Tool",
                "tool":{"requiresHandle":True,"tooltip":"Primary weapon"}}],
            "observedInteractionHistory":[{"path":"LocalPlayer.Backpack.Assault Rifle",
                "controlType":"Tool.Activated","featureCandidate":"combat",
                "outcomeVerified":False,"workflow":{"phase":"initiated","action":"attack",
                    "confidence":"bounded-name-context-heuristic","verified":False}}]}
        result=assess(value)
        self.assertEqual(result["generatedCapabilities"],[])
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")
        self.assertEqual(result["requestFeatureReadiness"]["status"],
            "evidence-aligned-no-generated-contract")
        self.assertIn("bounded_generated_contract_unavailable",
                      result["requestFeatureReadiness"]["explicitBlockers"])
        self.assertIn("request_aligned_state_transition_not_observed",
                      result["requestFeatureReadiness"]["explicitBlockers"])
        self.assertEqual(result["discoveryOnlyCapabilities"][0]["family"],"combat-tool-action")
        self.assertFalse(result["discoveryOnlyCapabilities"][0]["replayContractAvailable"])


    def test_gui_only_combat_request_reports_missing_input_and_state_gaps(self):
        value={"integrity":{"scanComplete":True,"placeId":286090429,"scanId":"arsenal-gui-only"},
            "requestedCapability":"Automatically shoot, reload, and switch weapons in Arsenal",
            "features":[feature("combat",1,0)],"actionableObjects":[],
            "observedInteractionHistory":[{"path":"LocalPlayer.PlayerGui.Menew_Main.Container.Play",
                "controlType":"GuiButton.Activated","featureCandidate":None,
                "outcomeVerified":False}]}
        result=assess(value)
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")
        blockers=result["requestFeatureReadiness"]["explicitBlockers"]
        self.assertIn("request_aligned_input_observation_not_captured",blockers)
        self.assertIn("request_aligned_state_transition_not_observed",blockers)



    def test_combat_request_uses_observed_input_actions_for_evidence_alignment(self):
        value={"integrity":{"scanComplete":True,"placeId":286090429,"scanId":"arsenal-input-actions"},
            "requestedCapability":"Automatically shoot and reload in Arsenal",
            "features":[feature("combat",2,0)],"actionableObjects":[],
            "observedInteractionHistory":[{
                "path":"UserInputService","controlType":"InputBegan.MouseButton1",
                "actionKind":"shooting","featureCandidate":"combat",
                "stateChanges":[{"key":"HUD.CrosshairHit","before":0,"after":1}],
                "workflow":{"phase":"initiated","action":"fire",
                    "confidence":"bounded-name-context-heuristic","verified":False}},
                {"path":"UserInputService","controlType":"InputBegan.R",
                "actionKind":"reload","featureCandidate":"combat",
                "stateChanges":[{"key":"HUD.ReloadPulse","before":0,"after":1}],
                "workflow":{"phase":"initiated","action":"reload",
                    "confidence":"bounded-name-context-heuristic","verified":False}}]}
        result=assess(value)
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")
        request_feature=result["requestFeatureReadiness"]
        self.assertIn("fire",request_feature["requestedTerms"])
        self.assertGreaterEqual(request_feature["summary"]["matchedObservedActions"],1)
        self.assertNotIn("no_request_feature_token_overlap",request_feature["explicitBlockers"])


    def test_exact_tool_evidence_produces_bounded_official_activation_trial(self):
        value={"integrity":{"scanComplete":True,"placeId":456,"scanId":"tool-ready-scan"},
            "requestedCapability":"Attack using the training sword",
            "features":[feature("combat",1,1)],"actionableObjects":[],
            "observedInteractionHistory":[{"path":"LocalPlayer.Backpack.Training Sword",
                "pathIdentity":[{"name":"LocalPlayer","className":"Player","ordinal":1},
                    {"name":"Backpack","className":"Backpack","ordinal":1},
                    {"name":"Training Sword","className":"Tool","ordinal":1}],
                "controlType":"Tool.Activated","featureCandidate":"combat",
                "controlMetadata":{"tooltip":"Training weapon","requiresHandle":False,
                    "canBeDropped":False,"enabled":True,"manualActivationOnly":False},
                "stateChanges":[{"key":"leaderstats.Hits","before":4,"after":5,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"leaderstats","className":"Folder","ordinal":1},
                        {"name":"Hits","className":"IntValue","ordinal":1}]}],
                "outcomeVerified":False,"workflow":{"phase":"initiated","action":"attack",
                    "confidence":"bounded-name-context-heuristic","verified":False}}]}
        result=assess(value)
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertEqual(result["request"]["matchedGeneratedCapabilityIds"],["tool-activation-trial"])
        generated=result["generatedCapabilities"][0]
        self.assertEqual(generated["kind"],"official-tool-activation-trial")
        self.assertTrue(generated["officialActivation"])
        self.assertTrue(generated["boundedEquip"])
        self.assertEqual(generated["attemptLimit"],25)
        self.assertFalse(generated["automaticMovement"])
        self.assertEqual(generated["observationBaseline"]["classification"],"timing-unknown")
        self.assertTrue(generated["observationBaseline"]["possibleSynchronousLoss"])
        self.assertEqual(result["discoveryOnlyCapabilities"],[])
        self.assertFalse(result["claims"]["runtimeVerified"])


    def test_exact_gui_evidence_produces_manual_guided_trial(self):
        value={"integrity":{"scanComplete":True,"placeId":789,"scanId":"gui-ready-scan"},
            "requestedCapability":"Buy the shop upgrade","features":[feature("shops",1,1)],
            "actionableObjects":[],"observedInteractionHistory":[{
                "path":"PlayerGui.HUD.Shop.List.Buy","controlType":"GuiButton.Activated",
                "featureCandidate":"shops","pathIdentity":[
                    {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
                    {"name":"HUD","className":"ScreenGui","ordinal":1},
                    {"name":"Shop","className":"Frame","ordinal":1},
                    {"name":"List","className":"ScrollingFrame","ordinal":1},
                    {"name":"Buy","className":"TextButton","ordinal":1}],
                "controlMetadata":{"controlClass":"TextButton","text":"Buy Upgrade",
                    "visible":True,"active":True,"selectable":True,"autoButtonColor":True,
                    "interactable":True,"ancestorVisible":True,"screenEnabled":True,
                    "withinScrollingBounds":True,"effectiveVisible":True},
                "stateChanges":[{"key":"Data.Upgrades","before":2,"after":3,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"Data","className":"Folder","ordinal":1},
                        {"name":"Upgrades","className":"IntValue","ordinal":1}]}]}]}
        result=assess(value)
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertEqual(result["request"]["matchedGeneratedCapabilityIds"],
            ["guided-gui-interaction-trial"])
        generated=result["generatedCapabilities"][0]
        self.assertEqual(generated["kind"],"guided-gui-activation-trial")
        self.assertFalse(generated["automaticActivation"])
        self.assertTrue(generated["manualActivationRequired"])
        self.assertTrue(generated["exactControlHighlighting"])
        self.assertEqual(generated["observationBaseline"]["classification"],"timing-unknown")
        self.assertTrue(generated["observationBaseline"]["possibleSynchronousLoss"])
        self.assertIn("require the user to activate",result["request"]["supportedSubset"][1])
        self.assertEqual(result["discoveryOnlyCapabilities"],[])

    def test_ui_only_request_is_blocked_as_not_meaningful_gameplay(self):
        value={"integrity":{"scanComplete":True,"placeId":791,"scanId":"ui-only-scan"},
            "requestedCapability":"Open inventory menu tab",
            "features":[feature("inventory",1,0)],
            "actionableObjects":[],
            "observedInteractionHistory":[{"path":"PlayerGui.HUD.Inventory.TabButton",
                "controlType":"GuiButton.Activated","featureCandidate":"inventory",
                "outcomeVerified":False,"stateChanges":[],
                "workflow":{"phase":"initiated","action":"open",
                    "confidence":"bounded-name-context-heuristic","verified":False}}]}
        result=assess(value)
        readiness_block=result["requestFeatureReadiness"]
        self.assertIn("no_meaningful_gameplay_feature_matches",
                      readiness_block["explicitBlockers"])
        self.assertEqual(readiness_block["summary"]["meaningfulGameplayFeatureMatches"],0)

    def test_request_aligned_review_only_gui_transitions_surface_specific_blocker(self):
        value={"integrity":{"scanComplete":True,"placeId":790,"scanId":"gui-review-only"},
            "requestedCapability":"Open training panel","features":[feature("training",1,1)],
            "actionableObjects":[],"observedInteractionHistory":[{
                "path":"PlayerGui.HUD.Training.OpenButton","controlType":"GuiButton.Activated",
                "featureCandidate":"training","pathIdentity":[
                    {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
                    {"name":"HUD","className":"ScreenGui","ordinal":1},
                    {"name":"Training","className":"Frame","ordinal":1},
                    {"name":"OpenButton","className":"TextButton","ordinal":1}],
                "controlMetadata":{"controlClass":"TextButton","text":"Open Training",
                    "visible":True,"active":True,"selectable":True,"autoButtonColor":True,
                    "interactable":True,"ancestorVisible":True,"screenEnabled":True,
                    "withinScrollingBounds":True,"effectiveVisible":True},
                "guiStateChanges":[{"path":"PlayerGui.HUD.Training.Panel",
                    "beforeVisible":False,"afterVisible":True}],
                "stateChanges":[]}]}
        result=assess(value);request_feature=result["requestFeatureReadiness"]
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")
        self.assertEqual(request_feature["workflowEvidence"]["reviewOnlyGuiTransitionCandidates"],1)
        self.assertEqual(request_feature["workflowEvidence"][
            "requestAlignedReviewOnlyGuiTransitionCandidates"],1)
        self.assertEqual(request_feature["workflowEvidence"][
            "requestAlignedReviewOnlyGuiTransitionPaths"],["PlayerGui.HUD.Training.OpenButton"])
        self.assertIn("request_aligned_gui_transition_outcomes_without_scalar_contract",
            request_feature["explicitBlockers"])
        self.assertEqual(request_feature["summary"]["requestAlignedReviewOnlyGuiTransitions"],1)

    def test_name_only_prompt_does_not_become_generated_subset(self):
        value=egg_plan();value["observedInteractionHistory"]=[]
        value["actionableObjects"]=[{"path":"Workspace.Eggs.Basic.Prompt",
            "class":"ProximityPrompt","interaction":{"objectText":"Basic Egg"}}]
        result=assess(value)
        self.assertEqual(result["generatedCapabilities"],[])
        self.assertFalse(result["request"]["generatedSubsetAvailable"])
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")


    def test_no_request_produces_empty_request_feature_readiness(self):
        value=egg_plan();value["requestedCapability"]=None
        result=assess(value)
        request_feature=result["requestFeatureReadiness"]
        self.assertEqual(result["request"]["status"],"no-capability-requested")
        self.assertEqual(request_feature["status"],"no-capability-requested")
        self.assertEqual(request_feature["requestedTerms"],[])
        self.assertEqual(request_feature["explicitBlockers"],[])
        self.assertEqual(request_feature["summary"]["blockers"],0)

    def test_source_artifact_drift_is_rejected(self):
        value=egg_plan();gameplay=understanding.analyze(value);actions=discovery.analyze(value)
        forged=copy.deepcopy(actions);forged["promptInteractions"]["trialReadyTargets"]=99
        with self.assertRaisesRegex(ValueError,"action capabilities"):
            readiness.assess(value,gameplay,forged)
        forged_gameplay=copy.deepcopy(gameplay);forged_gameplay["claims"]["runtimeVerified"]=True
        with self.assertRaisesRegex(ValueError,"gameplay understanding"):
            readiness.assess(value,forged_gameplay,actions)

    def test_exact_determinism(self):
        value=egg_plan()
        self.assertEqual(assess(value),assess(copy.deepcopy(value)))


    def test_pre_activation_coverage_is_visible_but_not_causal_proof(self):
        value=egg_plan();event=value["observedInteractionHistory"][0]
        event.update({"baselineSource":"ProximityPrompt.PromptButtonHoldBegan",
            "baselineTiming":"pre-activation","baselineAgeSeconds":0.03,
            "preActivationBaselineAvailable":True})
        value["interactionObservationSummary"]={"available":True,"callbacksFired":1,
            "preActivationBaselinesUsed":1,"callbackBaselinesUsed":0,
            "pendingObservationEvents":0,"observationWindowsExpected":3,
            "observationWindowsCompleted":3,"observationWindowsFailed":0,
            "observationWindowAccountingValid":True,"evidenceLossPossible":False,
            "limitations":[]}
        result=assess(value);coverage=result["interactionObservationCoverage"]
        self.assertEqual(coverage["classification"],"accounted-pre-activation-observation")
        self.assertEqual(coverage["readinessImpact"],"limitations-only")
        baseline=result["generatedCapabilities"][0]["observationBaseline"]
        self.assertEqual(baseline["classification"],
                         "pre-activation-baseline-available-for-all-observations")
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertFalse(result["claims"]["causalityProven"])

    def test_callback_fallback_surfaces_possible_loss_without_hiding_bounded_trial(self):
        value=egg_plan();event=value["observedInteractionHistory"][0]
        event.update({"baselineSource":"activation-callback-fallback",
            "baselineTiming":"activation-callback","baselineAgeSeconds":None,
            "preActivationBaselineAvailable":False})
        value["interactionObservationSummary"]={"available":True,"callbacksFired":1,
            "preActivationBaselinesUsed":0,"callbackBaselinesUsed":1,
            "pendingObservationEvents":0,"observationWindowsExpected":3,
            "observationWindowsCompleted":3,"observationWindowsFailed":0,
            "observationWindowAccountingValid":True,"evidenceLossPossible":True,
            "limitations":["callback-time baselines may miss synchronous activation changes"]}
        result=assess(value)
        self.assertTrue(result["interactionObservationCoverage"]["evidenceLossPossible"])
        self.assertEqual(result["generatedCapabilities"][0]["observationBaseline"][
            "classification"],"callback-fallback-present")
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertIn("may have lost client-visible changes",result["limitations"][0])


    def test_workflow_alignment_uses_normalized_request_terms(self):
        value=workflow_fixtures.plan();value["requestedCapability"]="Automate training"
        value["observedInteractionHistory"]= [
            workflow_fixtures.tool_event(1,0,1,"train-flow"),
            workflow_fixtures.tool_event(2,1,2,"train-flow")]
        for item in value["observedInteractionHistory"]:
            item["workflow"]={"phase":"initiated","action":"train",
                "confidence":"bounded-name-context-heuristic","verified":False}
        gameplay=understanding.analyze(value)
        actions=discovery.analyze(value)
        workflow=workflow_fixtures.planner.plan(value,actions)
        result=readiness.assess(value,gameplay,actions,workflow)
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        self.assertIn("linked-gameplay-workflow-trial",
            result["request"]["matchedGeneratedCapabilityIds"])
        selected=result["workflowSelection"]["candidates"][0]
        self.assertIn("train",selected["matchedTerms"])
        self.assertGreaterEqual(selected["requestScore"],4)


    def test_workflow_gerund_label_alignment_remains_assessable(self):
        value=workflow_fixtures.plan();value["requestedCapability"]="Automate training"
        value["observedInteractionHistory"]= [
            workflow_fixtures.event("Training",1,0,1,"train-label-flow"),
            workflow_fixtures.event("Continue",2,1,2,"train-label-flow")]
        for item in value["observedInteractionHistory"]:
            item["featureCandidate"]=None
        gameplay=understanding.analyze(value)
        actions=discovery.analyze(value)
        workflow=workflow_fixtures.planner.plan(value,actions)
        result=readiness.assess(value,gameplay,actions,workflow)
        self.assertEqual(result["request"]["status"],"generated-bounded-subset")
        selected=result["workflowSelection"]["candidates"][0]
        self.assertEqual(selected["matchedTerms"],["train"])
        self.assertEqual(result["requestFeatureReadiness"]["requestedTerms"],["train"])
        self.assertNotIn("traine",result["requestFeatureReadiness"]["requestedTerms"])

    def test_workflow_selection_reports_review_only_linked_gui_candidates(self):
        value=workflow_fixtures.plan();value["requestedCapability"]="Open training panel"
        value["observedInteractionHistory"]= [
            workflow_fixtures.gui_transition_event("Open Training",1),
            workflow_fixtures.gui_transition_event("Confirm Training",2)]
        gameplay=understanding.analyze(value)
        actions=discovery.analyze(value)
        workflow=workflow_fixtures.planner.plan(value,actions)
        result=readiness.assess(value,gameplay,actions,workflow)
        self.assertEqual(result["request"]["status"],"unsupported-by-current-evidence")
        planning=result["workflowSelection"]["planningDiagnostics"]
        self.assertEqual(planning["status"],"review-only-candidates")
        self.assertEqual(planning["reviewOnlyLinkedCandidates"],1)
        self.assertEqual(planning["requestAlignedReviewOnlyLinkedCandidates"],1)
        self.assertIsNotNone(planning["selectedReviewOnlyCandidateId"])
        selection=result["workflowSelection"]["candidates"][0]
        self.assertFalse(selection["executionReady"])
        self.assertEqual(selection["selectionReason"],"not-execution-ready")


    def test_inconsistent_observation_coverage_fails_closed(self):
        value=egg_plan();value["interactionObservationSummary"]={"available":True,
            "callbacksFired":1,"preActivationBaselinesUsed":1,"callbackBaselinesUsed":0,
            "preActivationCaptureFailures":0,
            "pendingObservationEvents":0,"observationWindowsExpected":3,
            "observationWindowsCompleted":3,"observationWindowsFailed":0,
            "observationWindowAccountingValid":True,"evidenceLossPossible":True,
            "limitations":[]}
        gameplay=understanding.analyze(value);actions=discovery.analyze(value)
        with self.assertRaisesRegex(ValueError,"evidence-loss"):
            readiness.assess(value,gameplay,actions)

    def test_guided_feedback_recurrence_is_informational_only(self):
        value=workflow_fixtures.plan();gameplay=understanding.analyze(value)
        actions=discovery.analyze(value);workflow=workflow_fixtures.planner.plan(value,actions)
        result=readiness.assess(value,gameplay,actions,workflow,[
            guided_feedback(workflow,"session-a"),guided_feedback(workflow,"session-b")])
        correlation=result["guidedWorkflowFeedbackCorrelation"]
        self.assertTrue(correlation["available"])
        self.assertEqual(correlation["summary"]["sessions"],2)
        self.assertTrue(correlation["completeSequenceRecurrenceObserved"])
        self.assertTrue(all(step["expectedDirectionAcrossMultipleSessions"]
            for step in correlation["steps"]))
        self.assertEqual(correlation["readinessImpact"],"informational-only")
        workflow_capability=next(item for item in result["generatedCapabilities"]
            if item["kind"]=="mixed-action-workflow-trial")
        baseline=workflow_capability["observationBaseline"]
        self.assertEqual(baseline["steps"],2)
        self.assertEqual(baseline["unknownTimingSteps"],2)
        self.assertEqual(baseline["classification"],"timing-unknown")
        self.assertEqual(baseline["readinessImpact"],"limitations-only")
        planning=result["workflowSelection"]["planningDiagnostics"]
        self.assertEqual(planning["status"],"execution-ready-candidates")
        self.assertEqual(planning["linkedTransactions"],planning["multiEventTransactions"])
        self.assertEqual(planning["readinessImpact"],"limitations-only")
        self.assertFalse(planning["causalityProven"])


        self.assertFalse(result["request"]["implementationReady"])
        self.assertFalse(result["claims"]["runtimeVerified"])
        self.assertFalse(result["claims"]["actionOutcomesVerified"])

    def test_guided_feedback_and_workflow_drift_fail_closed(self):
        value=workflow_fixtures.plan();gameplay=understanding.analyze(value)
        actions=discovery.analyze(value);workflow=workflow_fixtures.planner.plan(value,actions)
        feedback=guided_feedback(workflow,"session-a")
        feedback["workflowPlanSHA256"]="0"*64
        with self.assertRaisesRegex(ValueError,"identity mismatch"):
            readiness.assess(value,gameplay,actions,workflow,[feedback])
        forged=copy.deepcopy(workflow);forged["workflowCandidates"][0]["steps"][0][
            "targetPath"]="PlayerGui.Forged"
        with self.assertRaisesRegex(ValueError,"workflow plan"):
            readiness.assess(value,gameplay,actions,forged,[])

    def test_workflow_selection_explains_non_selected_candidates(self):
        selected={"id":"selected","selection":{"requestScore":10,"matchedTerms":["shop"]},
            "executionReady":True,"automaticallyExecutable":True,"executionMode":"bounded-automatic"}
        lower={"id":"lower","selection":{"requestScore":5,"matchedTerms":["shop"]},
            "executionReady":True,"automaticallyExecutable":True,"executionMode":"bounded-automatic"}
        blocked={"id":"blocked","selection":{"requestScore":12,"matchedTerms":["shop"]},
            "executionReady":False,"automaticallyExecutable":False,"executionMode":"review-only"}
        manual={"id":"manual","selection":{"requestScore":10,"matchedTerms":["shop"]},
            "executionReady":True,"automaticallyExecutable":False,"executionMode":"mixed-guided"}
        summary={"planningStatus":"execution-ready-candidates","transactionGroups":4,
            "linkedTransactions":4,"singletonTransactions":0,"multiEventTransactions":4,
            "transactionsWithInsufficientGenerationReadySteps":0,
            "partiallyMappedTransactions":0,"transactionsOverStepBound":0,
            "workflowCandidates":4,"unlinkedEvents":0,"executionReadyWorkflows":3}
        result=readiness._workflow_selection(
            {"workflowCandidates":[selected,blocked,manual,lower],"summary":summary},selected)
        reasons={item["candidateId"]:item["selectionReason"] for item in result["candidates"]}
        self.assertEqual(reasons["selected"],"selected-highest-ranked-execution-ready-candidate")
        self.assertEqual(reasons["blocked"],"not-execution-ready")
        self.assertEqual(reasons["manual"],"more-user-involvement-tiebreak")
        self.assertEqual(reasons["lower"],"lower-request-evidence-score")


if __name__=="__main__":unittest.main()
