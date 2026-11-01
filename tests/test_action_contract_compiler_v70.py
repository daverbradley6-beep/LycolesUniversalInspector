import copy
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from action_contract_compiler_v70 import generate, validate
PLACE=85896571713843
def fixture():
    return {"schemaVersion":"70.contracts","placeId":PLACE,"contracts":[{
        "id":"hatch_button","label":"Hatch once",
        "action":{"type":"local_gui_activate","className":"TextButton","path":["Main","EggUI","HatchButton"]},
        "outcome":{"type":"leaderstat","stat":"🥚 Hatches","operator":"increased",
                   "target":None,"timeoutSeconds":5}}]}
class TestV70(unittest.TestCase):
    def test_valid_compilation(self):
        result=generate(fixture(),PLACE)
        self.assertIn("🥚 Hatches",result)
        self.assertIn("HatchButton",result)
        self.assertIn("target:Activate()",result)
        self.assertIn("outcome not observed before timeout",result)
    def test_determinism(self):
        self.assertEqual(generate(fixture(),PLACE),generate(fixture(),PLACE))
    def test_no_implicit_remote_calls(self):
        result=generate(fixture(),PLACE)
        self.assertNotIn(":FireServer(",result)
        self.assertNotIn(":InvokeServer(",result)
    def test_wrong_place(self):
        with self.assertRaisesRegex(ValueError,"place ID mismatch"):
            validate(fixture(),123)
    def test_reject_unknown_action(self):
        x=fixture()
        x["contracts"][0]["action"]["type"]="remote_fire"
        with self.assertRaisesRegex(ValueError,"unsupported action"):
            validate(x,PLACE)
    def test_duplicate_id(self):
        x=fixture()
        x["contracts"].append(copy.deepcopy(x["contracts"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate id"):
            validate(x,PLACE)
    def test_timeout_bounds(self):
        x=fixture()
        x["contracts"][0]["outcome"]["timeoutSeconds"]=1000
        with self.assertRaisesRegex(ValueError,"timeout"):
            validate(x,PLACE)
    def test_injection_rejected(self):
        x=fixture()
        x["contracts"][0]["action"]["path"]=["UI\nbad"]
        with self.assertRaisesRegex(ValueError,"path segment"):
            validate(x,PLACE)
    def test_equals_requires_target(self):
        x=fixture()
        x["contracts"][0]["outcome"]["operator"]="equals"
        with self.assertRaisesRegex(ValueError,"target"):
            validate(x,PLACE)
    def test_empty_contracts_rejected(self):
        x=fixture()
        x["contracts"]=[]
        with self.assertRaisesRegex(ValueError,"1 to 60"):
            validate(x,PLACE)
if __name__=="__main__": unittest.main()
