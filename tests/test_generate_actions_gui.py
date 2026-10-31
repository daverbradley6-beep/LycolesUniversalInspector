import importlib.util
import pathlib
import unittest

path=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_actions_gui.py"
spec=importlib.util.spec_from_file_location("actions_gui",path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ActionGuiTests(unittest.TestCase):
    def contracts(self):
        return {"schemaVersion":"15.0","placeId":3623096087,"contracts":[
          {"feature":"stats","action":"read_leaderstats","scope":"client-read-only","reviewed":True},
          {"feature":"pets","action":"list_proximity_prompts","scope":"client-read-only","reviewed":True}]}
    def test_controls_are_connected_to_real_functions(self):
        source=module.render(self.contracts())
        self.assertIn("assert(game.PlaceId == 3623096087",source)
        self.assertIn("local function read_leaderstats()",source)
        self.assertIn("local function list_proximity_prompts()",source)
        self.assertIn("pcall(actions[name])",source)
        self.assertIn("MouseButton1Click:Connect",source)
        self.assertIn("LycolesActionsClose",source)
        self.assertNotIn("FireServer(",source)
        self.assertNotIn("InvokeServer(",source)
    def test_unreviewed_rejected(self):
        doc=self.contracts();doc["contracts"][0]["reviewed"]=False
        with self.assertRaises(ValueError):module.render(doc)
    def test_empty_rejected(self):
        doc=self.contracts();doc["contracts"]=[]
        with self.assertRaises(ValueError):module.render(doc)
if __name__=="__main__":unittest.main()
