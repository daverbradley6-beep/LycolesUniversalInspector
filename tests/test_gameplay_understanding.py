"""Composable, evidence-bounded gameplay understanding tests."""
import copy
import importlib.util
import pathlib
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools"/"understand_gameplay.py"
spec=importlib.util.spec_from_file_location("gameplay_understanding",SOURCE)
understanding=importlib.util.module_from_spec(spec)
spec.loader.exec_module(understanding)


def feature(name,interactions=0,candidates=0,state=0,gui=0):
    return {"feature":name,"interactionEvents":interactions,"observedEvents":interactions,
            "verifiedClientOutcomes":0,"clientCorroboratedEvents":0,
            "temporalTransitionEvents":interactions,"observableOutcomeCandidates":candidates,
            "featureStateCorrelations":state,"featureGuiCorrelations":gui,
            "status":"observable-outcome-candidate-unverified" if candidates else
                     "interaction-observed" if interactions else "discovered",
            "implementationReady":False,"reason":"passive evidence"}


def event(path,feature_name,action,changes,candidate=False,sequence=1):
    value={"path":path,"controlType":"GuiButton.Activated","sequence":sequence,
           "transactionId":sequence,"featureCandidate":feature_name,
           "evidenceLevel":"temporal-state-change-observed","stateChanges":changes,
           "outcomeVerified":False,"workflow":{"phase":"initiated","action":action,
             "confidence":"bounded-name-context-heuristic","verified":False}}
    if candidate:
        value["observableOutcomeCandidate"]={
            "feature":feature_name,"classification":"feature-consistent-observable-change",
            "evidenceKinds":["state-change"],"overlappingInteractionsPossible":False,
            "sourceAuthenticityVerified":False,"causalityProven":False,
            "serverAuthorityVerified":False,"gameplayVerified":False}
    return value


def plan():
    return {"schemaVersion":"20.0",
      "integrity":{"scanId":"bubble-scan","placeId":85896571713843,"parts":2,
                   "objects":20,"interactionEvents":3,"scanComplete":True},
      "requestedCapability":"Automatically hatch a selected egg in multi mode",
      "features":[feature("pets",1,1,1),feature("shops",1),feature("travel"),
                  feature("quests"),feature("rewards")],
      "observedInteractionHistory":[
        event("PlayerGui.Bubble.Button",None,"blow",[
            {"key":"leaderstats.Bubbles","before":0,"after":10}],sequence=1),
        event("PlayerGui.Shop.Sell", "shops","sell",[
            {"key":"leaderstats.Bubbles","before":10,"after":0},
            {"key":"leaderstats.Coins","before":100,"after":110}],sequence=2),
        event("PlayerGui.Eggs.Hatch", "pets","hatch",[
            {"key":"leaderstats.Coins","before":110,"after":100},
            {"key":"Data.PetInventory.Count","before":2,"after":3}],True,3),
      ],
      "releaseGate":{"gameplayAutomationApproved":False}}


class GameplayUnderstandingTests(unittest.TestCase):
    def test_bubble_like_evidence_forms_composable_systems_and_loops(self):
        result=understanding.analyze(plan())
        self.assertEqual(result["schemaVersion"],"110.gameplay-understanding.2")
        capability_ids={item["id"] for item in result["systems"]}
        self.assertTrue({"companion_collection","commerce","navigation",
                         "task_progression","reward_collection","resource_progression"}
                        <= capability_ids)
        resources={item["name"]:item for item in result["resources"]}
        self.assertEqual(resources["Bubbles"]["observedDirections"],["decrease","increase"])
        self.assertEqual(resources["Coins"]["classification"],"currency_candidate")
        self.assertEqual(resources["Count"]["classification"],"inventory_quantity_candidate")
        loop_ids={item["id"] for item in result["progressionLoops"]}
        self.assertIn("resource_conversion",loop_ids)
        self.assertIn("companion_acquisition",loop_ids)
        objective_kinds={item["kind"] for item in result["objectiveCandidates"]}
        self.assertIn("resource_accumulation",objective_kinds)
        self.assertIn("collection_progression",objective_kinds)
        self.assertGreaterEqual(len(result["mechanicCandidates"]),2)
        self.assertEqual(result["summary"]["topAutomationMechanic"],
                         result["mechanicCandidates"][0]["id"])
        mechanic_ids={item["id"] for item in result["mechanicCandidates"]}
        self.assertIn("resource_conversion",mechanic_ids)
        self.assertIn("mechanicCandidateIds",result["profileIndex"])
        self.assertFalse(result["claims"]["causalityProven"])
        self.assertFalse(result["claims"]["gameplayVerified"])

    def test_request_readiness_is_evidence_ranked_but_not_implemented(self):
        result=understanding.analyze(plan())
        request=result["requestedCapabilityAssessment"]
        self.assertEqual(request["matchedSystems"],["companion_collection"])
        self.assertIn("hatch",request["matchedObservedActions"])
        self.assertEqual(request["evidenceTier"],"observable_outcome_candidate_unverified")
        self.assertEqual(request["status"],"blocked_pending_action_contract")
        self.assertIn("selected_target_identity",request["blockers"])
        self.assertIn("interaction_mechanism",request["blockers"])
        self.assertIn("egg_selection_observation",request["blockers"])
        self.assertIn("affordability_and_cost_observation",request["blockers"])
        self.assertIn("inventory_capacity_observation",request["blockers"])
        self.assertIn("mode_selection_observation",request["blockers"])
        self.assertIn("rate_limit_contract",request["blockers"])
        self.assertIn("mode_semantics",request["blockers"])
        self.assertIn("failure_outcomes",request["blockers"])
        self.assertFalse(request["implementationReady"])

    def test_hybrid_game_retains_multiple_systems_without_single_genre(self):
        value=plan()
        value["requestedCapability"]=None
        value["features"]=[feature("combat",4,1,1),feature("quests",2),
                           feature("travel",1),feature("inventory",1)]
        value["observedInteractionHistory"]=[
            event("HUD.Weapon.Fire","combat","attack",[
                {"key":"Character.Ammo","before":30,"after":29}],True,1),
            event("HUD.Quest.Claim","quests","claim",[
                {"key":"Data.QuestProgress","before":4,"after":5}],False,2),
        ]
        result=understanding.analyze(value)
        ids={item["id"] for item in result["systems"]}
        self.assertTrue({"combat","task_progression","navigation","item_management"}<=ids)
        self.assertIsNone(result["genre"])
        self.assertEqual(result["model"],"composable_capabilities")

    def test_name_only_candidates_do_not_become_observed_mechanics(self):
        value=plan();value["observedInteractionHistory"]=[]
        value["features"]=[feature("pets"),feature("shops")]
        result=understanding.analyze(value)
        self.assertTrue(all(item["evidenceTier"]=="structural_candidate"
                            for item in result["systems"]))
        self.assertEqual(result["progressionRelationships"],[])
        self.assertEqual(result["progressionLoops"],[])
        self.assertTrue(all(not item["implementationReady"]
                            for item in result["automationOpportunities"]))
    def test_explicit_not_discovered_feature_is_excluded(self):
        value=plan();value["observedInteractionHistory"]=[]
        missing=feature("combat");missing["evidence"]={"status":"not-discovered"}
        present=feature("pets");present["evidence"]={"status":"candidate-needs-verification"}
        value["features"]=[missing,present]
        result=understanding.analyze(value)
        self.assertEqual([item["id"] for item in result["systems"]],["companion_collection"])
    def test_multiple_features_compose_one_resource_system(self):
        value=plan();value["observedInteractionHistory"]=[]
        value["features"]=[feature("training",2),feature("progression",3)]
        result=understanding.analyze(value)
        self.assertEqual(len(result["systems"]),1)
        self.assertEqual(result["systems"][0]["id"],"resource_progression")
        self.assertEqual(result["systems"][0]["sourceFeatures"],["progression","training"])
        self.assertEqual(result["systems"][0]["observedInteractions"],5)

    def test_unknown_feature_remains_a_structural_composable_system(self):
        value=plan();value["requestedCapability"]="Automatically fish in the lake"
        value["features"]=[feature("fishing")];value["observedInteractionHistory"]=[]
        result=understanding.analyze(value)
        self.assertEqual(len(result["systems"]),1)
        system=result["systems"][0]
        self.assertTrue(system["id"].startswith("feature_fishing_"))
        self.assertEqual(system["sourceFeatures"],["fishing"])
        self.assertEqual(system["evidenceTier"],"structural_candidate")
        self.assertEqual(result["requestedCapabilityAssessment"]["matchedSystems"],[system["id"]])
        self.assertEqual(result["requestedCapabilityAssessment"]["status"],
            "insufficient_interaction_evidence")
        self.assertIn("observed_interaction_evidence",
            result["requestedCapabilityAssessment"]["blockers"])
        self.assertFalse(system["systemVerified"])

    def test_generic_system_inventory_is_bounded_and_truncation_disclosed(self):
        value=plan();value["requestedCapability"]=None
        value["features"]=[feature(f"custom_{index:03d}") for index in range(140)]
        value["features"].append(feature("travel"));value["observedInteractionHistory"]=[]
        result=understanding.analyze(value)
        self.assertEqual(len(result["systems"]),understanding.MAX_SYSTEMS)
        self.assertIn("navigation",{item["id"] for item in result["systems"]})
        self.assertEqual(result["summary"]["omittedSystemCandidates"],13)
        self.assertTrue(result["profileIndex"]["systemInventoryTruncated"])
        self.assertEqual(result["profileIndex"]["omittedSystemCandidates"],13)

    def test_duplicate_resource_labels_keep_distinct_provider_independent_ids(self):
        value=plan();value["observedInteractionHistory"]=[
            event("HUD.First","shops","purchase",[
                {"key":"Data.Coins","before":10,"after":9,
                 "stateIdentityStatus":"component-resolved","stateIdentity":[
                    {"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Coins","className":"IntValue","ordinal":1}]},
                {"key":"Data.Coins","before":100,"after":90,
                 "stateIdentityStatus":"component-resolved","stateIdentity":[
                    {"name":"Data","className":"Folder","ordinal":1},
                    {"name":"Coins","className":"IntValue","ordinal":2}]}],False,1)]
        result=understanding.analyze(value)
        coins=[item for item in result["resources"] if item["name"]=="Coins"]
        self.assertEqual(len(coins),2)
        self.assertEqual(len({item["id"] for item in coins}),2)
        self.assertTrue(all(item["identityMode"]=="component-resolved" for item in coins))
        self.assertEqual({item["stateIdentity"][-1]["ordinal"] for item in coins},{1,2})
        effect_ids={item["resourceId"] for item in result["observedActions"][0][
            "resourceEffects"]}
        self.assertEqual(effect_ids,{item["id"] for item in coins})
        self.assertTrue(all(item["targetId"] in effect_ids
            for item in result["progressionRelationships"]))

    def test_profile_index_and_structured_evidence_gaps_are_bounded(self):
        result=understanding.analyze(plan())
        profile=result["profileIndex"]
        self.assertEqual(profile["model"],"provider-independent-composable-profile")
        self.assertFalse(profile["singleGenreAssumed"])
        self.assertEqual(profile["resourceIds"],sorted(
            item["id"] for item in result["resources"]))
        gaps={item["id"]:item for item in result["evidenceGaps"]}
        self.assertFalse(profile["systemInventoryTruncated"])
        self.assertEqual(profile["omittedSystemCandidates"],0)
        self.assertIn("interaction_mechanism",gaps)
        self.assertIn("mode_selection_observation",gaps)
        self.assertTrue(gaps["mode_selection_observation"]["requestRelevant"])
        self.assertTrue(gaps["mode_selection_observation"]["liveObservationRequired"])
        self.assertEqual(gaps["permitted_action_contract"]["category"],"operator-review")
        self.assertTrue(all(item["status"]=="unresolved" for item in gaps.values()))
        self.assertTrue(all(item["causalityProven"] is False for item in gaps.values()))
        resource_ids=set(profile["resourceIds"])
        action_ids=set(profile["observedActionIds"])
        system_ids=set(profile["systemIds"])
        self.assertTrue(all(item["targetId"] in resource_ids
            and item["sourceId"] in action_ids for item in result["progressionRelationships"]))
        for loop in result["progressionLoops"]:
            self.assertTrue(set(loop["stepActionIds"])<=action_ids)
            self.assertTrue(set(loop.get("inputResourceIds",[]))<=resource_ids)
            self.assertTrue(set(loop.get("intermediateResourceIds",[]))<=resource_ids)
            self.assertTrue(set(loop.get("outputResourceIds",[]))<=resource_ids)
        self.assertTrue(all(set(item["targetIds"])<=(resource_ids|system_ids)
            for item in result["objectiveCandidates"]))

    def test_exact_determinism_and_fail_closed_claims(self):
        value=plan()
        self.assertEqual(understanding.analyze(value),
                         understanding.analyze(copy.deepcopy(value)))
        broken=plan();broken["integrity"]["scanComplete"]=False
        with self.assertRaisesRegex(ValueError,"complete"):
            understanding.analyze(broken)
        forged=plan();forged["observedInteractionHistory"][2]["outcomeVerified"]=True
        with self.assertRaisesRegex(ValueError,"verified outcome"):
            understanding.analyze(forged)


if __name__=="__main__":unittest.main()
