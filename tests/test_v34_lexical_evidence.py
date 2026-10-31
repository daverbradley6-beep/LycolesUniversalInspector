"""v34 lexical evidence tests: run py -m unittest discover -s tests -p 'test_v34*.py'"""
import importlib.util,pathlib,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("lexical_v34",ROOT/"tools"/"luau_evidence_v34.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class EvidenceTests(unittest.TestCase):
    def test_real_function(self):
        r=m.extract('local function Cashier()\nworkspace.Jobs:FindFirstChild("Cashier")\nend')
        self.assertEqual(r["functions"][0]["name"],"Cashier")
        self.assertEqual(r["lookups"][0]["value"],"Cashier")
    def test_comments_excluded(self):
        self.assertEqual(m.extract('-- workspace.X:FireServer()\n--[[ workspace.X:InvokeServer() ]]')["calls"],[])
    def test_strings_excluded(self):
        self.assertEqual(m.extract('local x="workspace.X:FireServer()"')["calls"],[])
    def test_long_string_excluded(self):
        self.assertEqual(m.extract('local x=[=[workspace.X:FireServer()]=]')["calls"],[])
    def test_service(self):
        self.assertEqual(m.extract('game:GetService("Players")')["services"][0]["value"],"Players")
    def test_line_number(self):
        self.assertEqual(m.extract('-- comment\nfunction F() end')["functions"][0]["line"],2)
    def test_never_verified(self):
        self.assertFalse(m.extract('workspace.X:FireServer()')["verification"]["serverOutcomeVerified"])
    def test_deterministic(self):
        self.assertEqual(m.extract("function F() end"),m.extract("function F() end"))
    def test_directory(self):
        with tempfile.TemporaryDirectory() as d:
            pathlib.Path(d,"example.lua").write_text("function F() end")
            self.assertEqual(m.scan(d)["summary"]["files"],1)
    def test_missing_directory(self):
        with self.assertRaises(ValueError):m.scan("/not/a/real/lycoles-v34-path")
    def test_too_large(self):
        with self.assertRaises(ValueError):m.extract("x"*(m.MAX_BYTES+1))
if __name__=="__main__":unittest.main()
