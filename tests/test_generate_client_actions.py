import importlib.util
import pathlib
import unittest

p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_client_actions.py"
spec=importlib.util.spec_from_file_location("actions",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class GeneratedClientActionTests(unittest.TestCase):
    def contract(self,action="read_leaderstats"):
        return {"schemaVersion":"15.0","placeId":123,"contracts":[
          {"feature":"stats","action":action,"scope":"client-read-only","reviewed":True}]}
    def test_real_read_only_functions(self):
        for action in m.ACTIONS:
            lua=m.render(self.contract(action))
            self.assertIn("assert(game.PlaceId == 123",lua)
            self.assertIn("local function "+action+"()",lua)
            self.assertIn(action+" = "+action,lua)
            self.assertNotIn("FireServer(",lua)
            self.assertNotIn("InvokeServer(",lua)
    def test_reject_unreviewed(self):
        c=self.contract();c["contracts"][0]["reviewed"]=False
        with self.assertRaises(ValueError):m.render(c)
    def test_reject_unknown_action(self):
        with self.assertRaises(ValueError):m.render(self.contract("unknown"))
    def test_reject_wrong_scope(self):
        c=self.contract();c["contracts"][0]["scope"]="server"
        with self.assertRaises(ValueError):m.render(c)
    def test_no_contracts(self):
        c=self.contract();c["contracts"]=[]
        self.assertIn("return {",m.render(c))
if __name__=="__main__":unittest.main()
