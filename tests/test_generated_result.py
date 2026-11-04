import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("generated_result",ROOT/"tools"/"generated_result.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class GeneratedResultTests(unittest.TestCase):
    def readiness(self):
        return {"schemaVersion":"113.generation-readiness.1","placeId":123,
            "scanId":"scan12345","request":{"request":"show pet evidence",
                "status":"generated-bounded-subset","generatedSubsetAvailable":True,
                "matchedGeneratedCapabilityIds":["prompt-interaction-trial"],
                "supportedSubset":["select one exact observed prompt target"],
                "fullRequestImplemented":False,"implementationReady":False,
                "runtimeVerified":False,"gameplayVerified":False,
                "causalityProven":False,"actionOutcomesVerified":False},
            "generatedCapabilities":[{"id":"prompt-interaction-trial",
                "kind":"proximity-prompt-trial","targetLabel":"Rainbow Egg",
                "selectedOutcomeKey":"leaderstats.Hatches","expectedChange":"increased",
                "runtimeVerified":False,"gameplayVerified":False,"causalityProven":False,
                "actionOutcomeVerified":False}],
            "unavailableRequestedBehavior":[{"id":"multi-game-mode","status":"unavailable"}],
            "discoveryOnlyCapabilities":[{"family":"tool-action","candidateCount":2,
                "observedCount":1,"replayContractAvailable":False}],
            "workflowSelection":{"available":False,"totalCandidates":0,"shownCandidates":0,
                "omittedCandidates":0,"selectedCandidateId":None,"candidates":[]},
            "claims":{"sourceAuthenticityVerified":False,"causalityProven":False,
                "serverAuthorityVerified":False,"runtimeVerified":False,
                "gameplayVerified":False,"actionOutcomesVerified":False}}

    def build(self,**changes):
        values={"place_id":123,"scan_id":"scan12345",
            "code":"assert(game.PlaceId == 123, \"Incorrect Roblox place\")",
            "requested_capability":"show pet evidence",
            "validation":{"placeGuard":True,"unsafeOperationsFound":False},
            "capabilities":["Stats","Admin Commands"],
            "generation_readiness":self.readiness()}
        values.update(changes)
        return module.build(**values)

    def test_display_only_claims_fail_closed(self):
        result=self.build()
        self.assertEqual(result["schemaVersion"],"113.generated-result.1")
        self.assertTrue(result["staticValidationPassed"])
        self.assertEqual(result["generationReadiness"]["request"]["status"],
                         "generated-bounded-subset")
        self.assertEqual(result["generationReadiness"]["generatedCapabilities"][0]["targetLabel"],
                         "Rainbow Egg")
        for claim in ("packageAuthenticityVerified","runtimeVerified","gameplayVerified",
                      "executionAuthorized"):
            self.assertFalse(result[claim])
        self.assertRegex(result["generatedCodeSHA256"],r"^[a-f0-9]{64}$")

    def test_rejects_missing_place_guard_and_bad_validation(self):
        with self.assertRaisesRegex(ValueError,"place guard"):
            self.build(code="print('unsafe identity')")
        with self.assertRaisesRegex(ValueError,"validation"):
            self.build(validation={"placeGuard":False})

    def test_rejects_mismatched_or_positive_readiness_claims(self):
        mismatched=self.readiness();mismatched["placeId"]=999
        with self.assertRaisesRegex(ValueError,"identity"):
            self.build(generation_readiness=mismatched)
        forged=self.readiness();forged["claims"]["runtimeVerified"]=True
        with self.assertRaisesRegex(ValueError,"claims"):
            self.build(generation_readiness=forged)
        deceptive=self.readiness();deceptive["request"]["status"]="live gameplay verified"
        with self.assertRaisesRegex(ValueError,"request"):
            self.build(generation_readiness=deceptive)
        contradictory=self.readiness();contradictory["request"]["generatedSubsetAvailable"]=False
        with self.assertRaisesRegex(ValueError,"subset"):
            self.build(generation_readiness=contradictory)
        malformed=self.readiness();malformed["generatedCapabilities"][0]["targetLabel"]="x"*121
        with self.assertRaisesRegex(ValueError,"capability"):
            self.build(generation_readiness=malformed)
        spoofed=self.readiness();spoofed["generatedCapabilities"][0]["targetLabel"]="Egg\nRuntime verified"
        with self.assertRaisesRegex(ValueError,"capability"):
            self.build(generation_readiness=spoofed)

    def test_official_tool_trial_kind_is_displayable_but_unverified(self):
        readiness=self.readiness();capability=readiness["generatedCapabilities"][0]
        capability.update({"id":"tool-activation-trial","kind":"official-tool-activation-trial",
            "targetLabel":"Training Sword"})
        readiness["request"]["matchedGeneratedCapabilityIds"]=["tool-activation-trial"]
        result=self.build(generation_readiness=readiness)
        self.assertEqual(result["generationReadiness"]["generatedCapabilities"][0]["kind"],
            "official-tool-activation-trial")
        self.assertFalse(result["generationReadiness"]["claims"]["runtimeVerified"])

    def test_guided_gui_trial_requires_manual_activation_safeguards(self):
        readiness=self.readiness();capability=readiness["generatedCapabilities"][0]
        capability.update({"id":"guided-gui-interaction-trial",
            "kind":"guided-gui-activation-trial","targetLabel":"Buy Upgrade",
            "automaticActivation":False,"manualActivationRequired":True,
            "exactControlHighlighting":True})
        readiness["request"]["matchedGeneratedCapabilityIds"]=["guided-gui-interaction-trial"]
        result=self.build(generation_readiness=readiness)
        generated=result["generationReadiness"]["generatedCapabilities"][0]
        self.assertTrue(generated["manualActivationRequired"])
        forged=self.readiness();forged_capability=forged["generatedCapabilities"][0]
        forged_capability.update({"id":"guided-gui-interaction-trial",
            "kind":"guided-gui-activation-trial","automaticActivation":True,
            "manualActivationRequired":False,"exactControlHighlighting":True})
        forged["request"]["matchedGeneratedCapabilityIds"]=["guided-gui-interaction-trial"]
        with self.assertRaisesRegex(ValueError,"guided GUI"):
            self.build(generation_readiness=forged)

    def test_mixed_workflow_mode_and_step_contract_fail_closed(self):
        readiness=self.readiness();readiness["generatedCapabilities"]=[{
            "id":"linked-gameplay-workflow-trial","kind":"mixed-action-workflow-trial",
            "candidateId":"workflow-1","transactionId":"transaction-1",
            "executionMode":"bounded-automatic","stepCount":2,
            "stepKinds":["official-tool-activation-trial","proximity-prompt-trial"],
            "targetPaths":["LocalPlayer.Backpack.Sword","Workspace.Shop.Door.Prompt"],
            "targetFeatures":["shops"],"requestMatchedTerms":["shop"],
            "requestMatchScore":5,"manualGuiActivationRequired":False,
            "automaticallyExecutable":True,"operatorStartRequired":True,
            "stopOnFirstUnobservedOutcome":True,"runtimeVerified":False,
            "gameplayVerified":False,"causalityProven":False,"actionOutcomeVerified":False}]
        readiness["workflowSelection"]={"available":True,"totalCandidates":1,
            "shownCandidates":1,"omittedCandidates":0,"selectedCandidateId":"workflow-1",
            "candidates":[{"candidateId":"workflow-1","requestScore":5,
                "matchedTerms":["shop"],"executionMode":"bounded-automatic",
                "executionReady":True,"selected":True,
                "selectionReason":"selected-highest-ranked-execution-ready-candidate"}]}
        readiness["request"]["matchedGeneratedCapabilityIds"]=["linked-gameplay-workflow-trial"]
        result=self.build(generation_readiness=readiness)
        self.assertEqual(result["generationReadiness"]["generatedCapabilities"][0][
            "executionMode"],"bounded-automatic")
        readiness["workflowSelection"]["selectedCandidateId"]="forged"
        with self.assertRaisesRegex(ValueError,"selected workflow|selection"):
            self.build(generation_readiness=readiness)
        readiness["workflowSelection"]["selectedCandidateId"]="workflow-1"
        readiness["generatedCapabilities"][0]["executionMode"]="mixed-guided"
        with self.assertRaisesRegex(ValueError,"workflow"):
            self.build(generation_readiness=readiness)


    def test_guided_feedback_correlation_claims_fail_closed(self):
        readiness=self.readiness();readiness["guidedWorkflowFeedbackCorrelation"]={
            "available":False,"reason":"No digest-bound guided feedback was supplied",
            "readinessImpact":"none","claims":{"sourceAuthenticityVerified":False,
                "causalityProven":False,"serverAuthorityVerified":False,
                "runtimeVerified":False,"gameplayVerified":False,
                "actionOutcomesVerified":False}}
        result=self.build(generation_readiness=readiness)
        self.assertFalse(result["generationReadiness"][
            "guidedWorkflowFeedbackCorrelation"]["available"])
        readiness["guidedWorkflowFeedbackCorrelation"]["claims"]["runtimeVerified"]=True
        with self.assertRaisesRegex(ValueError,"correlation claims"):
            self.build(generation_readiness=readiness)

    def test_deterministic(self):
        self.assertEqual(self.build(),self.build())
