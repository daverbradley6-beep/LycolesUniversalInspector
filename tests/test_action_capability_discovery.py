import importlib.util,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/file)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


discovery=load("action_discovery","discover_action_capabilities.py")
generator=load("egg_generator","generate_prompt_interactions.py")
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
        self.assertFalse(egg["autoGameModeExecutable"])
        self.assertFalse(egg["multiGameModeExecutable"])
        self.assertIn("no unattended hatch outcome was observed after Auto activation",
            egg["modeExecutionBlockers"]["auto"])
        self.assertIn("observe a hatch-count delta greater than one in the linked observation window",
            egg["minimumLiveObservations"]["multi"])


    def test_generated_trial_has_toggle_teleport_outcome_and_shared_commands(self):
        source=generator.render(discovery.analyze(self.real_plan()))
        for token in ("Prompt Interactions | evidence-bounded trial","fireproximityprompt(prompt)",
                      "root.CFrame=anchor.CFrame","before=readOutcome", "after=readOutcome",
                      "Stopped after 3 uncorroborated attempts","_G.LycolesGameCommands",
                      "interactionstart=","interactionstop=","interaction=",
                      "eggstart=","eggstop=","eggmode=","targetDropdown",
                      "_G.LycolesPromptState","_G.LycolesGameStateChanged",
                      "state=commandState"):
            self.assertIn(token,source)
        self.assertNotIn("FireServer(",source)
        self.assertNotIn("InvokeServer(",source)

    def test_generator_rejects_forged_target_evidence(self):
        result=discovery.analyze(self.real_plan())
        result["promptInteractions"]["targets"][0]["controlType"]="RemoteEvent.FireServer"
        with self.assertRaisesRegex(ValueError,"Malformed correlated prompt target"):
            generator.render(result)

    def test_generator_rejects_forged_outcome_identity(self):
        result=discovery.analyze(self.real_plan())
        target=result["promptInteractions"]["targets"][0]
        target["outcomeSignals"][0]["stateIdentity"]=[
            {"name":"Other","className":"Folder","ordinal":1},
            {"name":"Hatches","className":"IntValue","ordinal":1}]
        with self.assertRaisesRegex(ValueError,"Malformed correlated prompt target"):
            generator.render(result)


    def test_component_identity_reaches_generated_resolver(self):
        plan=self.real_plan()
        event=next(item for item in plan["observedInteractionHistory"]
            if item.get("controlType")=="ProximityPrompt.Triggered")
        event["path"]="Workspace.Rendered.Chunker.Rainbow.Egg.Prompt.ProximityPrompt"
        event["pathIdentity"]=[{"name":"Workspace","className":"Workspace","ordinal":1},
            {"name":"Rendered","className":"Folder","ordinal":1},
            {"name":"Chunker","className":"Folder","ordinal":1},
            {"name":"Rainbow.Egg","className":"Model","ordinal":2},
            {"name":"Prompt","className":"Folder","ordinal":1},
            {"name":"ProximityPrompt","className":"ProximityPrompt","ordinal":1}]
        for change in event["stateChanges"]:
            if change.get("key")=="leaderstats.🥚 Hatches":
                change["stateIdentityStatus"]="component-resolved"
                change["stateIdentity"]=[
                    {"name":"leaderstats","className":"Folder","ordinal":1},
                    {"name":"🥚 Hatches","className":"IntValue","ordinal":1}]
        result=discovery.analyze(plan)
        target=next(item for item in result["eggHatching"]["targets"] if item.get("pathIdentity"))
        self.assertEqual(target["pathIdentity"][3]["name"],"Rainbow.Egg")
        source=generator.render(result)
        self.assertIn('name="Rainbow.Egg",className="Model",ordinal=2',source)
        self.assertIn('name="🥚 Hatches",className="IntValue",ordinal=1',source)
        self.assertIn("for _,child in ipairs(current:GetChildren())",source)

    def test_non_egg_prompt_generates_request_ranked_interaction_trial(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"reward-scan"},
            "requestedCapability":"Automatically claim daily reward",
            "actionableObjects":[],"observedInteractionHistory":[{
                "path":"Workspace.Rewards.Daily.ClaimPrompt","controlType":"ProximityPrompt.Triggered",
                "featureCandidate":"rewards","controlMetadata":{"actionText":"Claim","objectText":"Daily Reward",
                    "enabled":True,"holdDuration":0.5,"maxActivationDistance":12,
                    "keyboardKeyCode":"E","gamepadKeyCode":"ButtonX",
                    "anchorPath":"Workspace.Rewards.Daily","anchorPosition":{"x":1,"y":2,"z":3}},
                "pathIdentity":[
                    {"name":"Workspace","className":"Workspace","ordinal":1},
                    {"name":"Rewards","className":"Folder","ordinal":1},
                    {"name":"Daily","className":"Part","ordinal":1},
                    {"name":"ClaimPrompt","className":"ProximityPrompt","ordinal":1}],
                "stateChanges":[{"key":"Data.DailyClaims","before":2,"after":3,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"Data","className":"Folder","ordinal":1},
                        {"name":"DailyClaims","className":"IntValue","ordinal":1}]},
                    {"key":"Data.Gems","before":100,"after":90,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"Data","className":"Folder","ordinal":1},
                        {"name":"Gems","className":"IntValue","ordinal":1}]}]}]}
        result=discovery.analyze(plan)
        prompt=result["promptInteractions"]
        self.assertEqual(prompt["trialReadyTargets"],1)
        self.assertEqual(prompt["selectedTargetPath"],"Workspace.Rewards.Daily.ClaimPrompt")
        self.assertTrue(prompt["targets"][0]["objective"]["requestAligned"])
        self.assertEqual(prompt["targets"][0]["selectedOutcome"]["key"],"Data.DailyClaims")
        self.assertTrue(prompt["targets"][0]["selectedOutcome"]["selection"]["selectedForTrial"])
        evidence=prompt["targets"][0]["prerequisiteEvidence"]
        self.assertFalse(evidence["metadataDriftObserved"])
        self.assertEqual(evidence["metadataSnapshots"][0]["maxActivationDistance"],12)
        self.assertEqual(evidence["metadataSnapshots"][0]["anchorPosition"],{"x":1,"y":2,"z":3})


        source=generator.render(result)
        self.assertIn('label="Daily Reward"',source)
        self.assertIn('feature="rewards"',source)
        self.assertIn("egg=false",source)
        self.assertIn('outcome="Data.DailyClaims"',source)
        self.assertNotIn('outcome="Data.Gems"',source)

        self.assertIn("interactionstart=",source)
        self.assertNotIn("FireServer(",source)

    def test_generator_rejects_unselected_competing_outcome(self):
        plan={"integrity":{"scanComplete":True,"placeId":123},
            "requestedCapability":"claim reward","actionableObjects":[],
            "observedInteractionHistory":[{"path":"Workspace.Reward.Prompt",
                "controlType":"ProximityPrompt.Triggered","stateChanges":[
                    {"key":"Data.Rewards","before":1,"after":2},
                    {"key":"Data.Currency","before":10,"after":9}]}]}
        result=discovery.analyze(plan);target=result["promptInteractions"]["targets"][0]
        target["selectedOutcome"]=target["outcomeSignals"][1]
        with self.assertRaisesRegex(ValueError,"Malformed correlated prompt outcome"):
            generator.render(result)




    def test_malformed_prompt_prerequisite_metadata_fails_closed(self):
        plan=self.real_plan()
        event=next(item for item in plan["observedInteractionHistory"]
            if item.get("controlType")=="ProximityPrompt.Triggered")
        event["controlMetadata"]={"holdDuration":-1,"enabled":True}
        with self.assertRaisesRegex(ValueError,"Malformed prompt prerequisite metadata"):
            discovery.analyze(plan)

    def test_prompt_prerequisite_metadata_drift_is_preserved_without_overwrite(self):
        events=[]
        for enabled in (True,False):
            events.append({"path":"Workspace.Reward.Prompt","controlType":"ProximityPrompt.Triggered",
                "controlMetadata":{"actionText":"Claim","objectText":"Reward","enabled":enabled,
                    "holdDuration":0,"maxActivationDistance":10},
                "stateChanges":[{"key":"Data.Rewards","before":1,"after":2}]})
        result=discovery.analyze({"integrity":{"scanComplete":True,"placeId":123},
            "actionableObjects":[],"observedInteractionHistory":events})
        evidence=result["promptInteractions"]["targets"][0]["prerequisiteEvidence"]
        self.assertTrue(evidence["metadataDriftObserved"])
        self.assertEqual([item["enabled"] for item in evidence["metadataSnapshots"]],[True,False])

    def test_generator_rejects_forged_prompt_prerequisite_evidence(self):
        plan=self.real_plan();result=discovery.analyze(plan)
        target=result["promptInteractions"]["targets"][0]
        target["prerequisiteEvidence"]["metadataDriftObserved"]=True
        with self.assertRaisesRegex(ValueError,"Malformed prompt prerequisite evidence"):
            generator.render(result)



    def test_unavailable_new_state_identity_blocks_trial_readiness(self):
        plan=self.real_plan()
        event=next(item for item in plan["observedInteractionHistory"]
            if item.get("controlType")=="ProximityPrompt.Triggered")
        collections=[event.get("stateChanges",[])]
        collections.extend(window.get("stateChanges",[]) for window in event.get("observationWindows",[]))
        for changes in collections:
            for change in changes:
                if change.get("key")=="leaderstats.🥚 Hatches":
                    change.pop("stateIdentity",None)
                    change["stateIdentityStatus"]="unavailable"
        result=discovery.analyze(plan)
        self.assertFalse(result["eggHatching"]["automaticSingleTrialReady"])
        self.assertEqual(result["promptInteractions"]["trialReadyTargets"],0)

        self.assertIsNone(generator.render(result))



    def test_name_only_prompt_does_not_generate_execution(self):
        plan=self.real_plan();plan["observedInteractionHistory"]=[]
        plan["actionableObjects"]=[{"path":"Workspace.Eggs.Basic Egg.Prompt",
            "class":"ProximityPrompt","interaction":{"objectText":"Basic Egg"}}]
        result=discovery.analyze(plan)
        self.assertFalse(result["eggHatching"]["automaticSingleTrialReady"])
        self.assertIsNone(generator.render(result))

    def test_generic_temporal_relationships_preserve_evidence_tiers_without_replay(self):
        result=discovery.analyze(self.real_plan())
        generic=result["genericCapabilities"]
        relationships=generic["temporalActionOutcomeCandidates"]
        self.assertEqual(generic["generationReadiness"]["temporalCandidateCount"],8)
        self.assertEqual(generic["generationReadiness"]["generationReadyCount"],0)
        season=next(item for item in relationships if "Season.Frame" in item["path"])
        self.assertEqual(season["evidenceTier"],"interaction-with-temporal-gui-change")
        shop=next(item for item in relationships if "GumShop.Frame.Items" in item["path"])
        self.assertEqual(shop["evidenceTier"],"interaction-with-temporal-state-and-gui-change")
        self.assertTrue(all(item["temporalCorrelationOnly"] for item in relationships))
        self.assertTrue(all(not item["causalityProven"] and not item["replayContractAvailable"]
            for item in relationships))

    def test_malformed_generic_observation_windows_fail_closed(self):
        plan=self.real_plan();plan["observedInteractionHistory"][0]["observationWindows"]="invalid"
        with self.assertRaisesRegex(ValueError,"Malformed observation windows"):
            discovery.analyze(plan)

    def ready_tool_plan(self):
        plan=self.real_plan()
        plan["actionableObjects"]=[{"path":"LocalPlayer.Backpack.Assault Rifle","class":"Tool",
            "tool":{"requiresHandle":True,"tooltip":"Primary weapon","enabled":True,
                "manualActivationOnly":False,"canBeDropped":False}}]
        plan["observedInteractionHistory"].append({"path":"LocalPlayer.Backpack.Assault Rifle",
            "pathIdentity":[{"name":"LocalPlayer","className":"Player","ordinal":1},
                {"name":"Backpack","className":"Backpack","ordinal":1},
                {"name":"Assault Rifle","className":"Tool","ordinal":1}],
            "controlType":"Tool.Activated","featureCandidate":"combat","outcomeVerified":False,
            "controlMetadata":{"tooltip":"Primary weapon","requiresHandle":True,
                "canBeDropped":False,"enabled":True,"manualActivationOnly":False},
            "stateChanges":[{"key":"leaderstats.Hits","before":4,"after":5,
                "stateIdentityStatus":"component-resolved","stateIdentity":[
                    {"name":"leaderstats","className":"Folder","ordinal":1},
                    {"name":"Hits","className":"IntValue","ordinal":1}]}]})
        return plan

    def test_observed_tool_with_identity_prerequisites_and_scalar_outcome_is_trial_ready(self):
        result=discovery.analyze(self.ready_tool_plan())
        generic=result["genericCapabilities"]
        self.assertEqual(generic["families"]["tool-action"]["observed"],1)
        self.assertEqual(generic["combatCandidates"][0]["evidenceTier"],"interaction-observed")
        self.assertFalse(generic["combatCandidates"][0]["replayContractAvailable"])
        tools=result["toolInteractions"]
        self.assertEqual(tools["activationContractReadyTargets"],1)
        self.assertTrue(tools["generatorIntegrated"])
        self.assertEqual(tools["generationReadyTargets"],1)
        self.assertEqual(tools["executionMechanism"],"official Tool:Activate() after bounded equip")
        target=tools["targets"][0]
        self.assertEqual(target["selectedOutcome"]["key"],"leaderstats.Hits")
        self.assertTrue(target["activationContractReady"])
        self.assertTrue(target["trialGenerationReady"])
        self.assertTrue(target["replayContractAvailable"])
        self.assertFalse(target["causalityProven"])
        source=generator.render(result)
        for token in ('kind="tool"','humanoid:EquipTool(tool)','tool:Activate()',
                      'tool.Enabled','tool.ToolTip~=metadata.tooltip','tool-metadata-drift',
                      'Expected one mobile Tool match'):
            self.assertIn(token,source)
        self.assertNotIn("FireServer(",source)

    def test_disabled_or_metadata_drifted_tool_is_not_generation_ready(self):
        disabled=self.ready_tool_plan()
        disabled["observedInteractionHistory"][-1]["controlMetadata"]["enabled"]=False
        result=discovery.analyze(disabled);target=result["toolInteractions"]["targets"][0]
        self.assertFalse(target["trialGenerationReady"])
        self.assertIn("Tool was not observed enabled for activation",target["blockers"])

        drifted=self.ready_tool_plan()
        second=json.loads(json.dumps(drifted["observedInteractionHistory"][-1]))
        second["controlMetadata"]["tooltip"]="Changed tooltip"
        drifted["observedInteractionHistory"].append(second)
        result=discovery.analyze(drifted);target=result["toolInteractions"]["targets"][0]
        self.assertFalse(target["trialGenerationReady"])
        self.assertIn("Tool activation prerequisite metadata drift was observed",target["blockers"])

    def test_tool_without_prerequisites_or_outcome_remains_discovery_only(self):
        plan=self.real_plan();plan["actionableObjects"]=[]
        plan["observedInteractionHistory"].append({"path":"LocalPlayer.Backpack.Sword",
            "controlType":"Tool.Activated","featureCandidate":"combat","outcomeVerified":False})
        result=discovery.analyze(plan)
        self.assertEqual(result["toolInteractions"]["activationContractReadyTargets"],0)
        self.assertFalse(result["observedActions"][-1]["replayContractAvailable"])

    def test_malformed_tool_prerequisite_metadata_fails_closed(self):
        plan=self.real_plan();plan["observedInteractionHistory"].append({
            "path":"LocalPlayer.Backpack.Sword","controlType":"Tool.Activated",
            "controlMetadata":{"enabled":"yes"}})
        with self.assertRaisesRegex(ValueError,"Malformed Tool prerequisite metadata"):
            discovery.analyze(plan)
