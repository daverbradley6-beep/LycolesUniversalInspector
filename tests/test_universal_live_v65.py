import pathlib
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from universal_live_v65 import generate

class V65Tests(unittest.TestCase):
    def test_place_lock_and_categories(self):
        source=generate(85896571713843)
        self.assertIn("game.PlaceId~=85896571713843",source)
        for name in ('"Stats"','"Tools"','"Prompts"','"GUI"','"Changes"'):
            self.assertIn(name,source)
        self.assertNotIn("__PLACE__",source)
    def test_prompt_context_and_paths(self):
        source=generate(123)
        for name in ("GetFullName()", "ActionText", "ObjectText", "MaxActivationDistance"):
            self.assertIn(name,source)
    def test_change_history_bounded(self):
        source=generate(123,240,150,3000)
        self.assertIn("MAX_CHANGES=150",source)
        self.assertIn("MAX_SCAN=3000",source)
        self.assertIn("table.remove(changes,1)",source)
    def test_no_unsafe_calls(self):
        source=generate(123)
        for name in ("FireServer(", "InvokeServer(", "firetouchinterest(", "getgc("):
            self.assertNotIn(name,source)
    def test_invalid_arguments(self):
        for args in ((0,),(-1,),(True,),(123,20),(123,501),(123,240,19),(123,240,501),(123,240,150,99)):
            with self.assertRaises(ValueError): generate(*args)
    def test_cli_output(self):
        with tempfile.TemporaryDirectory() as d:
            script=pathlib.Path(__file__).resolve().parents[1]/"tools"/"universal_live_v65.py"
            subprocess.run([sys.executable,str(script),"--place-id","123","--output",d],
                           check=True,capture_output=True)
            self.assertTrue((pathlib.Path(d)/"live-inspector-v65.luau").exists())
            self.assertTrue((pathlib.Path(d)/"release-manifest-v65.json").exists())

if __name__=="__main__":unittest.main()
