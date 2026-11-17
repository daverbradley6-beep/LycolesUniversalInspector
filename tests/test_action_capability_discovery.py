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

    def gui_plan(self):
        metadata={"controlClass":"TextButton","text":"Buy Upgrade","visible":True,
            "active":True,"selectable":True,"autoButtonColor":True,"interactable":True,
            "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
            "effectiveVisible":True}
        return {"integrity":{"scanComplete":True,"placeId":123,"scanId":"gui-scan"},
            "requestedCapability":"buy upgrade","actionableObjects":[],
            "observedInteractionHistory":[{
                "path":"PlayerGui.HUD.Shop.List.Buy","controlType":"GuiButton.Activated",
                "featureCandidate":"shops","controlMetadata":metadata,"pathIdentity":[
                    {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
                    {"name":"HUD","className":"ScreenGui","ordinal":1},
                    {"name":"Shop","className":"Frame","ordinal":1},
                    {"name":"List","className":"ScrollingFrame","ordinal":1},
                    {"name":"Buy","className":"TextButton","ordinal":1}],
                "stateChanges":[{"key":"Data.Upgrades","before":2,"after":3,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"Data","className":"Folder","ordinal":1},
                        {"name":"Upgrades","className":"IntValue","ordinal":1}]}]}]}

    def test_target_baseline_provenance_is_preserved(self):
        plan=self.gui_plan();event=plan["observedInteractionHistory"][0]
        event.update({"baselineSource":"GuiButton.InputBegan",
            "baselineTiming":"pre-activation","baselineAgeSeconds":0.02,
            "preActivationBaselineAvailable":True})
        result=discovery.analyze(plan);target=result["guiInteractions"]["targets"][0]
        self.assertEqual(target["baselineEvidence"],{"events":1,
            "preActivationEvents":1,"activationCallbackEvents":0,
            "unknownTimingEvents":0,"possibleSynchronousLoss":False})
        self.assertEqual(result["observedActions"][0]["baselineEvidence"]["timing"],
                         "pre-activation")

    def test_callback_fallback_is_marked_as_possible_loss(self):
        plan=self.gui_plan();event=plan["observedInteractionHistory"][0]
        event.update({"baselineSource":"activation-callback-fallback",
            "baselineTiming":"activation-callback","baselineAgeSeconds":None,
            "preActivationBaselineAvailable":False})
        target=discovery.analyze(plan)["guiInteractions"]["targets"][0]
        self.assertEqual(target["baselineEvidence"]["activationCallbackEvents"],1)
        self.assertTrue(target["baselineEvidence"]["possibleSynchronousLoss"])


    def test_legacy_input_event_callback_timing_is_normalized(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"legacy-input-callback"},
            "actionableObjects":[],"observedInteractionHistory":[
                {"path":"LocalPlayer.Input.MouseButton1.None",
                 "controlType":"InputBegan.MouseButton1",
                 "baselineSource":"input-event-callback",
                 "baselineTiming":"input-event-callback",
                 "preActivationBaselineAvailable":False,
                 "baselineAgeSeconds":None},
                {"path":"LocalPlayer.Input.MouseButton2.None",
                 "controlType":"InputBegan.MouseButton2",
                 "baselineSource":"input-event-callback",
                 "baselineTiming":"activation-callback",
                 "preActivationBaselineAvailable":False,
                 "baselineAgeSeconds":None}]}
        result=discovery.analyze(plan)
        self.assertEqual(len(result["observedActions"]),2)
        self.assertTrue(all(item["baselineEvidence"]["timing"]=="activation-callback"
            for item in result["observedActions"]))
        self.assertTrue(all(item["baselineEvidence"]["possibleSynchronousLoss"] is True
            for item in result["observedActions"]))

    def test_malformed_baseline_timing_fails_closed(self):
        plan=self.gui_plan();event=plan["observedInteractionHistory"][0]
        event.update({"baselineSource":"GuiButton.InputBegan",
            "baselineTiming":"activation-callback","baselineAgeSeconds":0.02,
            "preActivationBaselineAvailable":True})
        with self.assertRaisesRegex(ValueError,"baseline timing"):
            discovery.analyze(plan)
    def test_nonfinite_oversized_and_partial_baselines_fail_closed(self):
        for age in (float("nan"),float("inf"),-0.01,3600.01,True):
            plan=self.gui_plan();plan["observedInteractionHistory"][0].update({
                "baselineSource":"GuiButton.InputBegan","baselineTiming":"pre-activation",
                "baselineAgeSeconds":age,"preActivationBaselineAvailable":True})
            with self.subTest(age=age),self.assertRaisesRegex(ValueError,"baseline timing"):
                discovery.analyze(plan)
        plan=self.gui_plan();plan["observedInteractionHistory"][0]["baselineSource"]="x"*500
        with self.assertRaisesRegex(ValueError,"baseline timing"):
            discovery.analyze(plan)



    def test_linked_transaction_outcome_can_enable_initiating_gui_target(self):
        metadata={"controlClass":"TextButton","text":"Buy","visible":True,
            "active":True,"selectable":True,"autoButtonColor":True,"interactable":True,
            "ancestorVisible":True,"screenEnabled":True,"withinScrollingBounds":True,
            "effectiveVisible":True}
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"linked-gui"},
            "requestedCapability":"buy upgrade","actionableObjects":[],
            "observedInteractionHistory":[
                {"path":"PlayerGui.HUD.Shop.Buy.Button","controlType":"GuiButton.Activated",
                 "transactionId":"txn-1","sequence":10,
                 "pathIdentity":[
                    {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
                    {"name":"HUD","className":"ScreenGui","ordinal":1},
                    {"name":"Shop","className":"Frame","ordinal":1},
                    {"name":"Buy","className":"Frame","ordinal":1},
                    {"name":"Button","className":"TextButton","ordinal":1}],
                 "controlMetadata":metadata,
                 "stateChanges":[]},
                {"path":"PlayerGui.HUD.Shop.Confirm.Yes","controlType":"GuiButton.Activated",
                 "transactionId":"txn-1","sequence":11,
                 "pathIdentity":[
                    {"name":"PlayerGui","className":"PlayerGui","ordinal":1},
                    {"name":"HUD","className":"ScreenGui","ordinal":1},
                    {"name":"Shop","className":"Frame","ordinal":1},
                    {"name":"Confirm","className":"Frame","ordinal":1},
                    {"name":"Yes","className":"TextButton","ordinal":1}],
                 "stateChanges":[{"key":"Data.Upgrades","before":2,"after":3,
                    "stateIdentityStatus":"component-resolved","stateIdentity":[
                        {"name":"Data","className":"Folder","ordinal":1},
                        {"name":"Upgrades","className":"IntValue","ordinal":1}]}]}]}
        result=discovery.analyze(plan)
        target=next(item for item in result["guiInteractions"]["targets"]
            if item["path"]=="PlayerGui.HUD.Shop.Buy.Button")
        self.assertTrue(target["trialGenerationReady"])
        self.assertEqual(target["selectedOutcome"]["key"],"Data.Upgrades")
        self.assertTrue(target["selectedOutcome"]["inheritedFromLinkedTransaction"])
        self.assertEqual(target["selectedOutcome"]["sourcePath"],
                         "PlayerGui.HUD.Shop.Confirm.Yes")
        observed=next(item for item in result["observedActions"]
            if item["path"]=="PlayerGui.HUD.Shop.Buy.Button")
        self.assertEqual(observed["outcomeEvidenceSource"],"linked-transaction-followup")



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

    def test_input_cadence_patterns_capture_sustained_and_burst_sequences(self):
        plan=self.real_plan()
        for sequence in range(200,208):
            plan["observedInteractionHistory"].append({
                "path":"UserInput.MouseButton1",
                "controlType":"Input.MouseButton1",
                "sequence":sequence,
                "inferredAction":{"kind":"fire","source":"input-observed"},
            })
        for sequence in (300,301,302):
            plan["observedInteractionHistory"].append({
                "path":"UserInput.KeyCode.R",
                "controlType":"Input.KeyCode",
                "sequence":sequence,
                "workflow":{"action":"reload"},
            })
        result=discovery.analyze(plan)
        generic=result["genericCapabilities"]
        patterns={item["actionKind"]:item for item in generic["inputCadencePatterns"]}
        self.assertIn("fire",patterns)
        self.assertEqual(patterns["fire"]["cadence"],"sustained")
        self.assertGreaterEqual(patterns["fire"]["maxEpisodeLength"],6)
        self.assertIn("reload",patterns)
        self.assertEqual(patterns["reload"]["cadence"],"burst")
        summary=generic["inputCadenceSummary"]
        self.assertGreaterEqual(summary["actionsWithSustainedCadence"],1)
        self.assertGreaterEqual(summary["actionsWithBurstCadence"],1)
        observed=result["observedActions"]
        fire_event=next(item for item in observed if item.get("inferredActionKind")=="fire")
        self.assertFalse(fire_event["causalityProven"])

    def test_automatic_action_inference_detects_sustained_input_state_patterns(self):
        plan=self.real_plan()
        before=10
        for sequence in range(220,228):
            after=before+1
            plan["observedInteractionHistory"].append({
                "path":"UserInput.MouseButton1",
                "controlType":"Input.MouseButton1",
                "sequence":sequence,
                "inferredAction":{"kind":"fire","source":"input-observed"},
                "stateChanges":[{"key":"leaderstats.Hits","before":before,"after":after}],
            })
            before=after
        result=discovery.analyze(plan)
        generic=result["genericCapabilities"]
        inferences=generic["automaticActionInferences"]
        fire=next(item for item in inferences if item["actionKind"]=="fire")
        self.assertTrue(fire["automaticActionCandidate"])
        self.assertEqual(fire["inferredMode"],"automatic-sustained-input-candidate")
        self.assertEqual(fire["cadence"],"sustained")
        self.assertIn("leaderstats.Hits",fire["stateSignalKeys"])
        summary=generic["automaticActionSummary"]
        self.assertGreaterEqual(summary["automaticCandidateCount"],1)
        self.assertGreaterEqual(summary["sustainedAutomaticCandidateCount"],1)
        self.assertFalse(fire["causalityProven"])
        self.assertFalse(fire["runtimeVerified"])

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


    def test_observed_gui_control_produces_guided_not_automatic_contract(self):
        result=discovery.analyze(self.gui_plan());gui=result["guiInteractions"]
        self.assertEqual(gui["guidedTrialReadyTargets"],1)
        self.assertFalse(gui["automaticActivationSupported"])
        target=gui["targets"][0]
        self.assertTrue(target["guidedActivationContractReady"])
        self.assertTrue(target["trialGenerationReady"])
        self.assertFalse(target["automaticActivationAvailable"])
        self.assertFalse(target["replayContractAvailable"])
        self.assertEqual(target["selectedOutcome"]["key"],"Data.Upgrades")
        self.assertTrue(any("no public automatic Activate method" in item
            for item in target["blockers"]))
        self.assertTrue(gui["generatorIntegrated"])
        self.assertEqual(gui["generationReadyTargets"],1)
        source=generator.render(result)
        for token in ('kind="gui"','guiMetadata={','local function currentGuiMetadata(button)',
                      'Instance.new("UIStroke")','button.Activated:Connect',
                      'gui-activation-timeout','automatic GUI activation unsupported',
                      'guiTextDynamic=false'):
            self.assertIn(token,source)
        for forbidden in ('firesignal(','VirtualInputManager','VirtualUser'):
            self.assertNotIn(forbidden,source)


    def test_unavailable_or_non_text_drifted_gui_control_stays_discovery_only(self):
        unavailable=self.gui_plan()
        unavailable["observedInteractionHistory"][0]["controlMetadata"]["withinScrollingBounds"]=False
        target=discovery.analyze(unavailable)["guiInteractions"]["targets"][0]
        self.assertFalse(target["guidedActivationContractReady"])
        self.assertIn("GUI control was not observed visible, enabled, and within scrolling bounds",
            target["blockers"])
        drift=self.gui_plan();second=json.loads(json.dumps(drift["observedInteractionHistory"][0]))
        second["controlMetadata"]["active"]=False
        drift["observedInteractionHistory"].append(second)
        target=discovery.analyze(drift)["guiInteractions"]["targets"][0]
        self.assertFalse(target["guidedActivationContractReady"])
        self.assertTrue(target["prerequisiteEvidence"]["metadataDriftObserved"])
        self.assertIn("GUI activation prerequisite metadata drift was observed",target["blockers"])

    def test_text_only_gui_metadata_drift_can_remain_generation_ready(self):
        drift=self.gui_plan();second=json.loads(json.dumps(drift["observedInteractionHistory"][0]))
        second["controlMetadata"]["text"]="Buy Better Upgrade"
        drift["observedInteractionHistory"].append(second)
        result=discovery.analyze(drift)
        target=result["guiInteractions"]["targets"][0]
        self.assertTrue(target["guidedActivationContractReady"])
        self.assertTrue(target["guiMetadataTextDynamic"])
        self.assertTrue(target["prerequisiteEvidence"]["metadataDriftObserved"])
        source=generator.render(result)
        self.assertIn("guiTextDynamic=true",source)

    def test_gui_transition_only_outcome_is_review_only_not_generation_ready(self):
        plan=self.gui_plan()
        event=plan["observedInteractionHistory"][0]
        event["stateChanges"]=[]
        event["guiStateChanges"]= [{
            "path":"PlayerGui.HUD.Shop.UpgradeResult",
            "transition":"became-visible",
            "beforeVisible":False,
            "afterVisible":True,
        }]
        result=discovery.analyze(plan)
        target=result["guiInteractions"]["targets"][0]
        self.assertFalse(target["guidedActivationContractReady"])
        self.assertEqual(target["observableOutcomeEvidenceKind"],"gui-transition-only")
        self.assertTrue(target["reviewOnlyTemporalOutcomeCandidate"])
        self.assertTrue(any("only GUI transition outcome evidence was observed" in item
            for item in target["blockers"]))
        gui=result["guiInteractions"]
        self.assertEqual(gui["reviewOnlyTemporalOutcomeCandidates"],1)
        self.assertEqual(gui["reviewOnlyTargetPaths"],["PlayerGui.HUD.Shop.List.Buy"])
        self.assertTrue(any("review-only GUI transition outcome candidates were observed" in item
            for item in gui["blockers"]))
        self.assertEqual(gui["generationReadyTargets"],0)

    def test_malformed_gui_prerequisite_metadata_fails_closed(self):
        plan=self.gui_plan();plan["observedInteractionHistory"][0]["controlMetadata"]["unknown"]=True
        with self.assertRaisesRegex(ValueError,"Malformed GUI prerequisite metadata"):
            discovery.analyze(plan)

    def test_generator_rejects_forged_gui_prerequisite_evidence(self):
        result=discovery.analyze(self.gui_plan())
        result["guiInteractions"]["targets"][0]["guiMetadata"]["text"]="Forged"
        with self.assertRaisesRegex(ValueError,"Malformed GUI prerequisite evidence"):
            generator.render(result)
