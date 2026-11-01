import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from workflow_v86 import inspect,plan,run

P=85896571713843
class TestWorkflow(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.root=Path(self.temp.name)
  (self.root/"tools").mkdir()
  for name in ("interactive_runner_v82.py","action_result_analyzer_v83.py","evidence_to_contracts_v85.py","release_pipeline_v84.py"):
   (self.root/"tools"/name).write_text("print('ok')\n",encoding="utf-8")
  self.contracts=self.root/"approved.json"
  self.contracts.write_text(json.dumps({"placeId":P,"contracts":[{"id":"hatch","approved":True,"executionEnabled":False,"input":["gui",[{"name":"Button","className":"ImageButton","ordinal":1}]]}]}))
  self.log=self.root/"results-v82.txt"
  self.log.write_text('LYCOLES_V82_RESULT {"schemaVersion":"82.result"}\n')
 def tearDown(self):self.temp.cleanup()
 def check(self):return inspect(self.root,P,self.contracts,self.log,self.root/"build")
 def test_ready(self):self.assertTrue(self.check()["ready"])
 def test_action_id(self):self.assertEqual(self.check()["approvedActionIds"],["hatch"])
 def test_missing_log(self):
  self.log.unlink()
  self.assertIn("Missing observation log"," ".join(self.check()["issues"]))
 def test_empty_log(self):
  self.log.write_text("")
  self.assertFalse(self.check()["ready"])
 def test_missing_contracts(self):
  self.contracts.unlink()
  self.assertFalse(self.check()["ready"])
 def test_invalid_json(self):
  self.contracts.write_text("{")
  self.assertFalse(self.check()["ready"])
 def test_wrong_place(self):self.assertFalse(inspect(self.root,1,self.contracts,self.log,self.root/"build")["ready"])
 def test_missing_tool(self):
  (self.root/"tools/release_pipeline_v84.py").unlink()
  self.assertFalse(self.check()["ready"])
 def test_plan(self):self.assertEqual(len(plan(self.root,P,self.contracts,self.log,self.root/"build")),4)
 def test_plan_order(self):
  commands=plan(self.root,P,self.contracts,self.log,self.root/"build")
  self.assertIn("interactive_runner_v82.py",commands[0][1])
  self.assertIn("release_pipeline_v84.py",commands[-1][1])
 def test_dry_run(self):
  self.assertEqual(run(self.root,P,self.contracts,self.log,self.root/"build",True)["status"],"planned")
 def test_blocked(self):
  self.log.unlink()
  self.assertEqual(run(self.root,P,self.contracts,self.log,self.root/"build")["status"],"blocked")
 def test_failure_is_reported(self):
  (self.root/"tools/interactive_runner_v82.py").write_text("raise RuntimeError('failed')\n")
  result=run(self.root,P,self.contracts,self.log,self.root/"build")
  self.assertEqual(result["status"],"failed")
  self.assertEqual(len(result["completed"]),1)
 def test_all_steps(self):
  result=run(self.root,P,self.contracts,self.log,self.root/"build")
  self.assertEqual(result["status"],"built_unverified")
  self.assertEqual(len(result["completed"]),4)
 def test_no_game_verification(self):
  self.assertFalse(run(self.root,P,self.contracts,self.log,self.root/"build")["verifiedInGame"])
 def test_no_auto_execution(self):
  self.assertEqual(run(self.root,P,self.contracts,self.log,self.root/"build")["automaticallyExecuted"],0)
if __name__=="__main__":unittest.main()
