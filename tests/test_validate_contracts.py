import importlib.util
import pathlib
import unittest

p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"validate_contracts.py"
spec=importlib.util.spec_from_file_location("contracts",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ContractTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"scanComplete":True,"placeId":123},
                "features":[{"feature":"rebirth"}]}
    def test_approved_read_only(self):
        result=m.validate_contracts(self.plan(),{"schemaVersion":"15.0","placeId":123,
          "contracts":[{"feature":"rebirth","action":"read_leaderstats","reviewed":True}]})
        self.assertEqual(result["clientActionsApproved"],1)
        self.assertFalse(result["gameplayAutomationApproved"])
    def test_unreviewed_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_contracts(self.plan(),{"schemaVersion":"15.0","placeId":123,
              "contracts":[{"feature":"rebirth","action":"read_leaderstats","reviewed":False}]})
    def test_unknown_action_rejected(self):
        with self.assertRaises(ValueError):
            m.validate_contracts(self.plan(),{"schemaVersion":"15.0","placeId":123,
              "contracts":[{"feature":"rebirth","action":"unknown","reviewed":True}]})
    def test_place_mismatch(self):
        with self.assertRaises(ValueError):
            m.validate_contracts(self.plan(),{"schemaVersion":"15.0","placeId":124,"contracts":[]})
if __name__=="__main__":
    unittest.main()
