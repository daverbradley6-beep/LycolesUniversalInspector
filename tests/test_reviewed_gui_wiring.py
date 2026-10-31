import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]/"tools"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
gui=load("generate_actions_gui")
validator=load("validate_generated_gui")
class ReviewedGUIWiringTests(unittest.TestCase):
    def document(self):
        return {"schemaVersion":"15.0","placeId":123,"contracts":[
          {"feature":"stats","action":"read_leaderstats","scope":"client-read-only","reviewed":True},
          {"feature":"menus","action":"list_player_gui","scope":"client-read-only","reviewed":True}]}
    def test_real_buttons_and_dispatch(self):
        source=gui.render(self.document())
        report=validator.validate(source,["list_player_gui","read_leaderstats"])
        self.assertTrue(report["guiWiringValidated"])
        self.assertFalse(report["runtimeVerified"])
        self.assertIn('local ACTION_NAMES = {"list_player_gui","read_leaderstats"}',source)
        self.assertIn('pcall(actions[name])',source)
        self.assertIn('HttpService:JSONEncode',source)
        self.assertIn('Export audit JSON',source)
        self.assertIn('local output = Instance.new("TextBox")',source)
        self.assertIn('\\n',source)
    def test_reject_missing_dispatch(self):
        source=gui.render(self.document()).replace("pcall(actions[name])","pcall(function() end)")
        with self.assertRaises(ValueError):validator.validate(source,["list_player_gui","read_leaderstats"])
    def test_reject_unknown_action(self):
        with self.assertRaises(ValueError):
            validator.validate(gui.render(self.document()),["unknown_action"])
if __name__=="__main__":unittest.main()
