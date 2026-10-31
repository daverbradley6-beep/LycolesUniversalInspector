import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_verification_harness.py"
spec=importlib.util.spec_from_file_location("verification",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class VerificationTests(unittest.TestCase):
    def data(self):
        return {"placeId":3623096087,"workflows":[{"feature":"rebirth","transaction":"1","steps":[
          {"stateChanges":[{"key":"leaderstats.Rebirths","before":18,"after":19},
                           {"key":"Workspace.Hidden","before":0,"after":1}]}]}]}
    def test_generates_real_observer(self):
        plan,lua=m.compile_verification(self.data())
        self.assertEqual(plan["checks"][0]["leaderstatsKeys"],["Rebirths"])
        self.assertIn("function api.capture_before()",lua)
        self.assertIn("function api.compare_after()",lua)
        self.assertIn("function api.capture_all_before()",lua)
        self.assertIn("function api.export_report()",lua)
        self.assertIn("HttpService:JSONEncode",lua)
        self.assertIn("schemaVersion = \"22.0\"",lua)
        self.assertIn("assert(game.PlaceId == 3623096087",lua)
        self.assertNotIn("FireServer(",lua)
        self.assertNotIn("InvokeServer(",lua)
    def test_no_supported_keys(self):
        d=self.data();d["workflows"]=[]
        plan,lua=m.compile_verification(d)
        self.assertIsNone(lua)
        self.assertEqual(plan["checks"],[])
    def test_invalid_place(self):
        d=self.data();d["placeId"]=None
        with self.assertRaises(ValueError):m.compile_verification(d)
    def test_invalid_key_ignored(self):
        d=self.data();d["workflows"][0]["steps"][0]["stateChanges"][0]["key"]="leaderstats.bad key"
        self.assertIsNone(m.compile_verification(d)[1])
if __name__=="__main__":unittest.main()
