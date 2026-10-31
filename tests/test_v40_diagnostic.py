import importlib.util
import pathlib
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("diagnostic_generator_v40",ROOT/"tools"/"diagnostic_generator_v40.py")
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def report(paths):
    return {"schemaVersion":"39.0","families":[{"examplePaths":paths}]}

class TestV40(unittest.TestCase):
    def test_luau_table_not_json_array(self):
        s=mod.generate(report(["Workspace.Training"]))
        self.assertIn('local paths = {"Workspace.Training"}',s)
        self.assertNotIn('local paths = ["Workspace.Training"]',s)
    def test_empty_paths(self):
        self.assertIn("local paths = {}",mod.generate(report([])))
    def test_duplicate_paths(self):
        self.assertEqual(mod.collect(report(["Workspace.A","Workspace.A"])),["Workspace.A"])
    def test_unknown_root(self):
        self.assertEqual(mod.collect(report(["Unknown.A","Workspace.B"])),["Workspace.B"])
    def test_no_gameplay_remotes(self):
        s=mod.generate(report(["Workspace.A"]))
        self.assertNotIn("FireServer",s)
        self.assertNotIn("InvokeServer",s)
        self.assertIn("FindFirstChild",s)
    def test_closable(self):
        s=mod.generate(report(["Workspace.A"]))
        self.assertIn("close.Activated:Connect",s)
    def test_quoted_path(self):
        s=mod.generate(report(['Workspace.A"Name']))
        self.assertIn('A\\"Name',s)
    def test_backslash_path(self):
        s=mod.generate(report(["Workspace.A\\B"]))
        self.assertIn("A\\\\B",s)
    def test_schema_rejection(self):
        with self.assertRaises(ValueError):mod.generate({"schemaVersion":"38.0"})
    def test_bad_path(self):
        with self.assertRaises(ValueError):mod.collect(report([7]))
    def test_cap(self):
        paths=["Workspace.A"+str(i) for i in range(300)]
        self.assertEqual(len(mod.collect(report(paths))),mod.MAX_PATHS)
