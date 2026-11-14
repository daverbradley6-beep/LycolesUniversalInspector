import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
SOURCE=ROOT/"tools"/"universal_gameplay_intelligence.py"
spec=importlib.util.spec_from_file_location("universal_gameplay_intelligence",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def plan():
    return {
        "schemaVersion":"20.0",
        "integrity":{"scanId":"scan-abc","placeId":123456,"parts":2,
            "objects":4,"interactionEvents":2,"scanComplete":True},
        "universalDiscovery":{
            "regions":[{"id":"region_overworld","path":"Workspace.Worlds.Overworld",
                "positionedObjectCount":10,"totalObjectCount":20,
                "centroid":{"x":10,"y":5,"z":2},
                "bounds":{"x":[0,20],"y":[0,10],"z":[-5,5]}}],
            "interactables":[{"id":"interactable_1","path":"Workspace.Egg.Prompt",
                "class":"ProximityPrompt","scope":"workspace",
                "mechanism":"proximity_prompt",
                "position":{"x":1,"y":2,"z":3},"positionSource":"interaction-anchor",
                "actionText":"Hatch","objectText":"Rainbow Egg","observedInteractions":1,
                "relatedFeatures":["pets"],"confidence":"structural-with-observation"}],
            "economySignals":[{"id":"econ_cost","path":"Workspace.Shop.Item",
                "key":"Cost","value":500,"source":"object-attribute",
                "scope":"workspace","classification":"requirement_or_cost_signal"}],
            "stateChangeSignals":[{"id":"state_coins","key":"leaderstats.Coins",
                "classification":"currency_signal","increaseEvents":0,
                "decreaseEvents":1,"changedEvents":1,"lastBefore":1000,
                "lastAfter":900,"sourceFeatures":["shops"]}],
            "interactionPatterns":[{"id":"pattern_1","key":"proximity_prompt:workspace",
                "mechanism":"proximity_prompt","scope":"workspace",
                "memberCount":1,"observedInteractions":1,
                "samplePaths":["Workspace.Egg.Prompt"]}],
            "summary":{},
        },
        "observedInteractionHistory":[
            {"sequence":1,"sessionId":"s1","sessionElapsedSeconds":1.0,
             "transactionId":"flow-1","path":"Workspace.Egg.Prompt",
             "controlType":"ProximityPrompt.Triggered",
             "featureCandidate":"pets","outcomeVerified":False,
             "baselineSource":"ProximityPrompt.PromptButtonHoldBegan",
             "baselineTiming":"pre-activation",
             "preActivationBaselineAvailable":True,
             "stateChanges":[{"key":"leaderstats.Coins","before":1000,"after":900}]},
            {"sequence":2,"sessionId":"s1","sessionElapsedSeconds":2.5,
             "transactionId":"flow-1","path":"Workspace.Egg.Prompt",
             "controlType":"ProximityPrompt.Triggered",
             "featureCandidate":"pets","outcomeVerified":False,
             "workflow":{"action":"hatch","phase":"initiated","confidence":"heuristic"},
             "stateChanges":[{"key":"Data.Pets.Count","before":2,"after":3}]},
            {"sequence":3,"sessionId":"s1","sessionElapsedSeconds":3.1,
             "transactionId":"input-1","path":"LocalPlayer.Input.MouseButton1",
             "controlType":"InputBegan.MouseButton1","featureCandidate":"combat",
             "outcomeVerified":False,
             "workflow":{"action":"fire","phase":"input-observed","confidence":"bounded-input-observation"},
             "controlMetadata":{"source":"UserInputService.InputBegan","inputType":"MouseButton1",
                 "keyCode":"Unknown","combatToolContext":True,"equippedToolCount":1},
             "stateChanges":[{"key":"HUD.Signal.playergui.weapon.ammo","before":"30","after":"29"}]},
        ],
    }


class UniversalGameplayIntelligenceTests(unittest.TestCase):
    def test_analyze_builds_world_economy_action_and_workflow_views(self):
        result=module.analyze(plan())
        self.assertEqual(result["schemaVersion"],"111.universal-gameplay-intelligence.1")
        self.assertEqual(result["world"]["summary"]["regions"],1)
        self.assertEqual(result["world"]["summary"]["interactables"],1)
        self.assertEqual(result["economy"]["summary"]["signals"],1)
        self.assertGreaterEqual(result["summary"]["actionRecords"],3)
        self.assertEqual(result["summary"]["inputActionRecords"],1)
        self.assertEqual(result["summary"]["actionSourceBreakdown"].get("user-input"),1)
        self.assertGreaterEqual(result["summary"]["workflowCandidates"],1)
        input_records=[record for record in result["actions"] if record["during"].get("actionSource")=="user-input"]
        self.assertTrue(input_records)
        self.assertEqual(input_records[0]["during"]["controlMetadata"].get("inputType"),"MouseButton1")
        self.assertFalse(result["claims"]["runtimeVerified"])
        self.assertFalse(result["claims"]["gameplayVerified"])

    def test_validate_roundtrip(self):
        source=plan()
        compiled=module.analyze(source)
        self.assertEqual(module.validate(compiled,source),compiled)


if __name__=="__main__":
    unittest.main()
