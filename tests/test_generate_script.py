"""Run with: python3 -m unittest discover -s tests -v"""
import importlib.util, pathlib, unittest
source=pathlib.Path(__file__).resolve().parents[1]/"tools"/"generate_script.py"
spec=importlib.util.spec_from_file_location("generator",source)
generator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
class GeneratorTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"placeId":3623096087,"scanComplete":True},
                "features":[{"feature":"rebirth"},{"feature":"pets"}]}
    def test_generates_client_utility(self):
        result=generator.render(self.plan())
        self.assertIn("3623096087",result)
        self.assertIn('button("Stats"',result)
        self.assertIn('button("Menus"',result)
        self.assertNotIn("FireServer(",result)
        self.assertNotIn("InvokeServer(",result)
    def test_invalid_scan_blocked(self):
        plan=self.plan();plan["integrity"]["scanComplete"]=False
        with self.assertRaises(ValueError):generator.render(plan)
    def test_malformed_feature_blocked(self):
        plan=self.plan();plan["features"]=[{"feature":4}]
        with self.assertRaises(ValueError):generator.render(plan)
    def test_escape_untrusted_feature_name(self):
        plan=self.plan();plan["features"]=[{"feature":'abc"\\\\\nscript'}]
        result=generator.render(plan)
        self.assertIn("abc",result)
        self.assertNotIn("FireServer(",result)
if __name__=="__main__":unittest.main()
