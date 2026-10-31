"""Offline v31 regression tests. Run: python -m unittest discover -s tests -p 'test_v31*.py'"""
import importlib.util
import pathlib
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]

def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/"tools"/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

corpus=load("analyze_script_corpus")
workflow=load("synthesize_workflow_specs")

class CorpusTests(unittest.TestCase):
    def test_loader_not_verified(self):
        a=corpus.analyze("loader.lua",'loadstring(game:HttpGet("https://example.org/a.lua"))()')
        self.assertEqual(a["classification"],"loader")
        self.assertFalse(a["verification"]["gameplayConfirmed"])
    def test_protected_not_claimed(self):
        a=corpus.analyze("protected.lua","-- Luraph Obfuscator v14.8\nreturn({a=1})")
        self.assertEqual(a["classification"],"protected-opaque")
    def test_telemetry_flag(self):
        a=corpus.analyze("test.lua",'loadstring(game:HttpGet("https://rscripts.net/api/telemetry/v2/client.lua"))()')
        self.assertTrue(any("telemetry" in x.lower() for x in a["warnings"]))
    def test_duplicate_and_shared_dependency(self):
        with tempfile.TemporaryDirectory() as d:
            p=pathlib.Path(d)
            s='loadstring(game:HttpGet("https://example.org/loader.lua"))()'
            (p/"a.lua").write_text(s)
            (p/"b.lua").write_text(s)
            result=corpus.build(sorted(p.iterdir()))
            self.assertEqual(result["summary"]["duplicateFiles"],1)
            self.assertEqual(result["summary"]["sharedDependencies"],1)
    def test_workflow_evidence(self):
        source='local x = thing:FindFirstChild("A")\nbutton.Activated:Connect(function() end)\n'
        item=corpus.analyze("gui.lua",source)
        output=workflow.compile_specs({"schemaVersion":"31.0","source":"offline-static-corpus","files":[item]})
        self.assertGreaterEqual(output["specCount"],1)
        self.assertTrue(all(not x["runtimeVerified"] for x in output["specs"]))
    def test_loader_no_workflow(self):
        item=corpus.analyze("loader.lua",'loadstring(game:HttpGet("https://example.org/a"))()')
        output=workflow.compile_specs({"schemaVersion":"31.0","source":"offline-static-corpus","files":[item]})
        self.assertEqual(output["specCount"],0)
    def test_reject_bad_schema(self):
        with self.assertRaises(ValueError):
            workflow.compile_specs({"schemaVersion":"30.0","files":[]})
    def test_deterministic_id(self):
        self.assertEqual(workflow.stable_id("a","b"),workflow.stable_id("a","b"))

if __name__=="__main__":
    unittest.main()
