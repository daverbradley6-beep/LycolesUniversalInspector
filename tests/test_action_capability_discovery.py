import importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


discovery=load("action_discovery","discover_action_capabilities.py")
generator=load("egg_generator","generate_egg_autofarm.py")
FIXTURE=json.loads((ROOT/"tests"/"fixtures"/"bubble_gum_infinity_manifest_v30_sanitized.json").read_text())


class ActionCapabilityDiscoveryTests(unittest.TestCase):
    def real_plan(self):
        return {"integrity":{"scanComplete":True,"placeId":FIXTURE["placeId"],
                    "scanId":"bubble-gum-infinity-real-manifest"},
                "observedInteractionHistory":json.loads(json.dumps(
                    FIXTURE["interactionDiagnostics"]["recentInteractions"])),
                "actionableObjects":[],"actionableObjectsTruncated":True}

    def test_real_rainbow_egg_prompt_becomes_correlated_trial_target(self):
        result=discovery.analyze(self.real_plan())
        egg=result["eggHatching"]
        self.assertTrue(egg["automaticSingleTrialReady"])
        self.assertFalse(egg["multiHatchTrialReady"])
        self.assertEqual(egg["correlatedTargets"],1)
        target=next(item for item in egg["targets"] if item["label"]=="Rainbow Egg")
        self.assertEqual(target["path"],"Workspace.Rendered.Chunker.Rainbow Egg.Prompt.ProximityPrompt")
        self.assertEqual(target["outcomeKeys"],["leaderstats.🥚 Hatches"])
        self.assertEqual(target["evidenceTier"],"temporal-state-increment-observed")
        self.assertFalse(target["causalityProven"])

    def test_generated_trial_has_toggle_teleport_outcome_and_shared_commands(self):
        source=generator.render(discovery.analyze(self.real_plan()))
        for token in ("Egg Autofarm | evidence-bounded trial","fireproximityprompt(prompt)",
                      "root.CFrame=anchor.CFrame","before=readOutcome", "after=readOutcome",
                      "Stopped after 3 uncorroborated attempts","_G.LycolesGameCommands",
                      "eggstart=","eggstop=","eggmode="):
            self.assertIn(token,source)
        self.assertNotIn("FireServer(",source)
        self.assertNotIn("InvokeServer(",source)

    def test_generator_rejects_forged_target_evidence(self):
        result=discovery.analyze(self.real_plan())
        result["eggHatching"]["targets"][0]["controlType"]="RemoteEvent.FireServer"
        with self.assertRaisesRegex(ValueError,"Malformed correlated egg target"):
            generator.render(result)

    def test_name_only_prompt_does_not_generate_execution(self):
        plan=self.real_plan();plan["observedInteractionHistory"]=[]
        plan["actionableObjects"]=[{"path":"Workspace.Eggs.Basic Egg.Prompt",
            "class":"ProximityPrompt","interaction":{"objectText":"Basic Egg"}}]
        result=discovery.analyze(plan)
        self.assertFalse(result["eggHatching"]["automaticSingleTrialReady"])
        self.assertIsNone(generator.render(result))

    def test_generic_tool_actions_support_fps_discovery_without_replay_claims(self):
        plan=self.real_plan()
        plan["actionableObjects"]=[{"path":"LocalPlayer.Backpack.Assault Rifle","class":"Tool",
            "tool":{"requiresHandle":True,"tooltip":"Primary weapon"}}]
        plan["observedInteractionHistory"].append({"path":"LocalPlayer.Backpack.Assault Rifle",
            "controlType":"Tool.Activated","featureCandidate":"combat","outcomeVerified":False})
        result=discovery.analyze(plan)["genericCapabilities"]
        self.assertEqual(result["families"]["tool-action"]["observed"],1)
        self.assertEqual(result["combatCandidates"][0]["evidenceTier"],"interaction-observed")
        self.assertFalse(result["combatCandidates"][0]["replayContractAvailable"])
