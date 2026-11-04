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
        self.assertEqual(result["discoveryOnlyCapabilities"][0]["family"],"combat-tool-action")
        self.assertFalse(result["discoveryOnlyCapabilities"][0]["replayContractAvailable"])

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
        self.assertIn("require the user to activate",result["request"]["supportedSubset"][1])
        self.assertEqual(result["discoveryOnlyCapabilities"],[])

    def test_name_only_prompt_does_not_become_generated_subset(self):
        value=egg_plan();value["observedInteractionHistory"]=[]
        value["actionableObjects"]=[{"path":"Workspace.Eggs.Basic.Prompt",
            "class":"ProximityPrompt","interaction":{"objectText":"Basic Egg"}}]
        result=assess(value)
        self.assertEqual(result["generatedCapabilities"],[])
        self.assertFalse(result["request"]["generatedSubsetAvailable"])
        self.assertEqual(result["request"]["status"],"evidence-only-no-replay-contract")

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


if __name__=="__main__":unittest.main()
