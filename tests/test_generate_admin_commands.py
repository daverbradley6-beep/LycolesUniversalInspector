"""Reusable universal admin-command generator tests."""
import importlib.util
import pathlib
import unittest

SOURCE=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_admin_commands.py"
spec=importlib.util.spec_from_file_location("generate_admin_commands",SOURCE)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdminCommandGeneratorTests(unittest.TestCase):
    def test_universal_command_inventory_and_help(self):
        source=module.render(85896571713843)
        for command in ("fly","unfly","noclip","clip","tp","goto","speed","jump",
                        "coords","systems","readiness","reset","rejoin","cmds","help","stopall","hidegui"):
            self.assertIn('register("'+command+'"',source)
        self.assertIn("Admin Commands",source)
        self.assertIn("description",source)
        self.assertIn("arguments",source)
        self.assertIn("availability",source)
        self.assertIn("currentState",source)

    def test_command_bar_chat_autocomplete_and_history(self):
        source=module.render(123)
        self.assertIn("Enum.KeyCode.RightBracket",source)
        self.assertIn("player.Chatted:Connect",source)
        self.assertIn("PREFIX = \";\"",source)
        self.assertIn("updateAutocomplete",source)
        self.assertIn("commandHistory",source)
        self.assertIn("Enum.KeyCode.Up",source)
        self.assertIn("Enum.KeyCode.Down",source)
        self.assertIn("commandBar.Position = UDim2.new(0.5",source)

    def test_gui_and_commands_share_feature_state(self):
        source=module.render(123)
        self.assertIn("local featureState =",source)
        self.assertIn("featureState.fly",source)
        self.assertIn("featureState.noclip",source)
        self.assertIn("setFlyEnabled",source)
        self.assertIn("setNoclipEnabled",source)
        self.assertIn("stopAll",source)
        self.assertIn("refreshCommandRows",source)

    def test_evidence_commands_present_unverified_systems_and_blockers(self):
        understanding={"schemaVersion":"110.gameplay-understanding.1","systems":[
            {"label":'Pets\";error(\"owned\")--',"evidenceTier":"structural_candidate"}],
            "requestedCapabilityAssessment":{"status":"blocked_pending_action_contract",
                "blockers":["permitted_action_contract","hatch_result_observation"]}}
        source=module.render(85896571713843,understanding)
        self.assertIn("System candidates (unverified)",source)
        self.assertIn("structural_candidate",source)
        self.assertIn("blocked_pending_action_contract",source)
        self.assertIn("hatch_result_observation",source)
        self.assertNotIn('error(\"owned\")',source)
        self.assertIn('error(\\\"owned\\\")',source)
        with self.assertRaises(ValueError):
            module.render(123,{"schemaVersion":"110.gameplay-understanding.1","systems":[
                {"label":"__LYCOLES_READINESS_SUMMARY_110__","evidenceTier":"structural_candidate"}]})
        with self.assertRaises(ValueError):
            module.render(123,{"schemaVersion":"110.gameplay-understanding.1","systems":None})
        with self.assertRaises(ValueError):
            module.render(123,{"schemaVersion":"110.gameplay-understanding.1","systems":[
                {"label":"x"*161,"evidenceTier":"structural_candidate"}]})

    def test_cleanup_restores_character_state(self):
        source=module.render(123)
        self.assertIn("originalCollision",source)
        self.assertIn("part.CanCollide = original",source)
        self.assertIn("restoreHumanoid",source)
        self.assertIn("LycolesAdminClose",source)
        self.assertIn("gui:Destroy()",source)

    def test_place_guard_and_no_arbitrary_server_calls(self):
        source=module.render(123)
        self.assertIn('assert(game.PlaceId == 123',source)
        for banned in ("FireServer(","InvokeServer(","loadstring(","hookmetamethod(","getrawmetatable("):
            self.assertNotIn(banned,source)
        with self.assertRaises(ValueError):module.render(0)
        with self.assertRaises(ValueError):module.render(True)


if __name__=="__main__":unittest.main()
