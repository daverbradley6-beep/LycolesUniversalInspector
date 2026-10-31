import importlib.util
import pathlib
import unittest
p=pathlib.Path(__file__).resolve().parents[1]/"tools"/"compile_implementation_backlog.py"
spec=importlib.util.spec_from_file_location("backlog",p)
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
class BacklogTests(unittest.TestCase):
    def setUp(self):
        self.plan={"integrity":{"scanComplete":True,"placeId":3623096087,"scanId":"scan1"}}
        self.sequences={"placeId":3623096087,"scanId":"scan1","workflows":[
          {"feature":"rebirth","transaction":"tx1","steps":[{"path":"PlayerGui.Rebirth",
           "stateChanges":[{"key":"leaderstats.Rebirths","before":18,"after":19}]}]}]}
    def test_candidates_are_not_executable(self):
        result=m.compile_backlog(self.plan,self.sequences)
        self.assertEqual(result["candidateCount"],1)
        self.assertFalse(result["candidates"][0]["supportedExecutableContract"])
        self.assertEqual(result["automaticallyGeneratedGameplayFunctions"],0)
    def test_feedback_does_not_promote_automation(self):
        feedback={"placeId":3623096087,"results":[{"feature":"rebirth",
          "transaction":"tx1","status":"client-change-observed"}]}
        result=m.compile_backlog(self.plan,self.sequences,feedback)
        self.assertEqual(result["candidates"][0]["clientFeedbackStatus"],"client-change-observed")
        self.assertFalse(result["candidates"][0]["runtimeGameplayVerified"])
    def test_wrong_scan(self):
        self.sequences["scanId"]="wrong"
        with self.assertRaises(ValueError):m.compile_backlog(self.plan,self.sequences)
    def test_wrong_place(self):
        self.sequences["placeId"]=123
        with self.assertRaises(ValueError):m.compile_backlog(self.plan,self.sequences)
if __name__=="__main__":unittest.main()
