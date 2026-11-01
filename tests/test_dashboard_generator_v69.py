import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from dashboard_generator_v69 import generate, candidates, validate_release
PLACE=85896571713843
def manifest():
    return {"schemaVersion":"68.release","placeId":PLACE,"readyForActionGeneration":False}
def cat():
    return {"capabilities":[
        {"path":"Players/\"geckoflicker\"#1@Player/\"leaderstats\"#1@Folder/\"🟣 Bubbles\"#1@IntValue",
         "kind":"observable_value","className":"IntValue","actionStatus":"unverified"},
        {"path":"ReplicatedStorage/\"Remotes\"#1@Folder/\"Example\"#1@RemoteEvent",
         "kind":"remote_observed","className":"RemoteEvent","actionStatus":"unverified"}]}
class TestV69(unittest.TestCase):
    def test_generate_real_gui(self):
        src=generate(manifest(),cat(),PLACE)
        for token in ("Instance.new(\"ScreenGui\")","GetPropertyChangedSignal(\"Text\")",
                      "MouseButton1Click:Connect(render)","mini.MouseButton1Click",
                      "UIS.InputChanged:Connect","leaderstats"):
            self.assertIn(token,src)
    def test_no_remote_invocation(self):
        src=generate(manifest(),cat(),PLACE)
        self.assertNotIn(":FireServer(",src)
        self.assertNotIn(":InvokeServer(",src)
    def test_emoji_preserved(self):
        self.assertIn("🟣 Bubbles",generate(manifest(),cat(),PLACE))
    def test_deterministic(self):
        self.assertEqual(generate(manifest(),cat(),PLACE),generate(manifest(),cat(),PLACE))
    def test_wrong_place(self):
        with self.assertRaisesRegex(ValueError,"place ID mismatch"):
            generate(manifest(),cat(),123)
    def test_reject_unexpected_action_claim(self):
        m=manifest()
        m["readyForActionGeneration"]=True
        with self.assertRaisesRegex(ValueError,"unexpected"):
            generate(m,cat(),PLACE)
    def test_filter_invalid_entries(self):
        data=cat()
        data["capabilities"].append({"path":"abc\nx","kind":"observable_value"})
        self.assertEqual(len(candidates(data)),2)
if __name__=="__main__": unittest.main()
