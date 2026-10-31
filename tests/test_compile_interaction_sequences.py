import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_interaction_sequences.py"
spec=importlib.util.spec_from_file_location("sequences",p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class SequenceTests(unittest.TestCase):
    def plan(self):
        return {"integrity":{"scanComplete":True,"placeId":3623096087,"scanId":"scan"},
          "observedInteractionHistory":[
            {"featureCandidate":"rebirth","transactionId":1,"sequence":1,"path":"PlayerGui.Rebirth",
             "clientStateCorroborated":True,"stateChanges":[{"key":"leaderstats.Rebirths","before":18,"after":19}]},
            {"featureCandidate":"rebirth","transactionId":1,"sequence":2,"path":"PlayerGui.Confirm",
             "outcomeVerified":False}]}
    def test_linked_sequence(self):
        result=m.compile_sequences(self.plan())
        self.assertEqual(result["workflowCount"],1)
        self.assertEqual(len(result["workflows"][0]["steps"]),2)
        self.assertEqual(result["workflows"][0]["observedStateChanges"],1)
        self.assertFalse(result["workflows"][0]["automaticallyExecutable"])
        self.assertFalse(result["workflows"][0]["serverVerified"])
    def test_unlinked_events_separate(self):
        p=self.plan()
        for event in p["observedInteractionHistory"]:event.pop("transactionId")
        self.assertEqual(m.compile_sequences(p)["workflowCount"],2)
    def test_invalid_scan(self):
        p=self.plan();p["integrity"]["scanComplete"]=False
        with self.assertRaises(ValueError):m.compile_sequences(p)
    def test_reject_unbounded_history(self):
        p=self.plan();p["observedInteractionHistory"]=[{}]*2001
        with self.assertRaises(ValueError):m.compile_sequences(p)
if __name__=="__main__":unittest.main()
