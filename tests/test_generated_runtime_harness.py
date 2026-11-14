import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

GEN_SOURCE = ROOT / "tools" / "generate_script.py"
GEN_SPEC = importlib.util.spec_from_file_location("generator_for_harness", GEN_SOURCE)
GEN = importlib.util.module_from_spec(GEN_SPEC)
sys.modules[GEN_SPEC.name] = GEN
GEN_SPEC.loader.exec_module(GEN)

HARNESS_SOURCE = ROOT / "tools" / "generated_runtime_harness.py"
HARNESS_SPEC = importlib.util.spec_from_file_location("runtime_harness", HARNESS_SOURCE)
HARNESS = importlib.util.module_from_spec(HARNESS_SPEC)
sys.modules[HARNESS_SPEC.name] = HARNESS
HARNESS_SPEC.loader.exec_module(HARNESS)


class RuntimeHarnessTests(unittest.TestCase):
    def _plan(self):
        return {
            "integrity": {"placeId": 3623096087, "scanId": "harness", "scanComplete": True},
            "features": [{"feature": "combat"}],
            "requestedCapability": "Provide loadout and movement telemetry",
            "interactionDiagnostics": {
                "targetedCaptureSessionSummary": {
                    "samples": {
                        "loadoutSnapshots": [{"hudWeaponIndicatorPaths": ["LocalPlayer.PlayerGui.HUD.WeaponLabel"]}],
                        "weaponSnapshots": [{"equippedTools": ["Rifle"]}],
                        "cameraSamples": [{"fieldOfView": 70}],
                        "inputSamples": [{"inputGesturesObserved": 1}],
                    }
                }
            },
        }

    def test_gui_structure_and_module_contract(self):
        plan = self._plan()
        script = GEN.render(plan)
        contract = GEN.build_generated_module_contract(plan, {"request": {"status": "evidence-only-no-replay-contract"}})
        harness = HARNESS.RuntimeContractHarness(contract)
        gui = harness.validate_gui_structure(script)
        self.assertTrue(all(gui.values()))

    def test_toggle_settings_keybind_respawn_cleanup_cycle(self):
        plan = self._plan()
        contract = GEN.build_generated_module_contract(plan, {"request": {"status": "evidence-only-no-replay-contract"}})
        harness = HARNESS.RuntimeContractHarness(contract)

        player = HARNESS.MockPlayer(
            character=HARNESS.MockCharacter(
                tools=[HARNESS.MockTool("Rifle")],
                humanoid=HARNESS.MockHumanoid(walk_speed=16.0, floor_material="Concrete", state_name="Running"),
                root_part=HARNESS.MockRootPart(velocity_magnitude=9.5),
            ),
            backpack=HARNESS.MockContainer(tools=[HARNESS.MockTool("Knife")]),
            hud_indicators={"WeaponLabel": "Rifle"},
        )

        loadout = harness.toggle_loadout(player)
        movement = harness.toggle_movement(player)
        self.assertTrue(loadout["enabled"])
        self.assertTrue(movement["enabled"])
        self.assertTrue(movement["telemetryEnabled"])
        self.assertTrue(movement["focusAssistEnabled"])
        self.assertEqual(movement["currentFov"], float(harness.movement.focus_target_fov))
        self.assertGreaterEqual(harness.connection_count, 2)

        settings = harness.apply_settings_cycle()
        self.assertIn(settings["loadoutRefresh"], HARNESS.LOADOUT_REFRESH_OPTIONS)
        self.assertIn(settings["movementRefresh"], HARNESS.MOVEMENT_REFRESH_OPTIONS)
        self.assertIn(settings["movementFocusTargetFov"], HARNESS.FOCUS_FOV_OPTIONS)

        key_target = harness.handle_keybind(player, harness.loadout.keybind)
        self.assertEqual(key_target, "loadout")

        respawn = harness.handle_respawn(
            player,
            HARNESS.MockCharacter(
                tools=[HARNESS.MockTool("Pistol")],
                humanoid=HARNESS.MockHumanoid(walk_speed=16.0, floor_material="Air", state_name="Freefall"),
                root_part=HARNESS.MockRootPart(velocity_magnitude=2.5),
            ),
        )
        self.assertTrue(respawn["characterPresent"])

        cleaned = harness.cleanup()
        self.assertFalse(cleaned["loadoutEnabled"])
        self.assertFalse(cleaned["movementEnabled"])
        self.assertFalse(cleaned["movementTelemetryEnabled"])
        self.assertFalse(cleaned["movementFocusAssistEnabled"])
        self.assertEqual(cleaned["movementCurrentFov"], harness.movement.baseline_fov)
        self.assertEqual(cleaned["connectionCount"], 0)

    def test_missing_data_handling(self):
        contract = GEN.build_generated_module_contract(self._plan(), {"request": {"status": "unsupported-by-current-evidence"}})
        harness = HARNESS.RuntimeContractHarness(contract)
        player = HARNESS.MockPlayer(character=None)
        movement = harness.toggle_movement(player)
        self.assertTrue(isinstance(movement["enabled"], bool))
        self.assertEqual(movement["enabled"], movement["telemetryEnabled"])
        movement_off = harness.toggle_movement(player)
        self.assertEqual(movement_off["enabled"], movement_off["telemetryEnabled"])
        self.assertEqual(harness.handle_keybind(player, "Unknown"), "none")


if __name__ == "__main__":
    unittest.main()
