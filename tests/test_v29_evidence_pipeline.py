import importlib.util
import pathlib
import unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]/"tools"
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+".py"))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
audit=load("evaluate_action_audit")
coverage=load("report_feature_coverage")
class EvidencePipelineTests(unittest.TestCase):
    def contracts(self):
        return {"schemaVersion":"15.0","placeId":123,"contracts":[
          {"feature":"stats","action":"read_leaderstats","scope":"client-read-only","reviewed":True}]}
    def report(self):
        return {"schemaVersion":"28.0","placeId":123,"source":"reviewed-client-actions",
          "results":[{"action":"read_leaderstats","success":True,"durationSeconds":0.01,"error":None}]}
    def test_success_does_not_verify_gameplay(self):
        result=audit.evaluate(self.contracts(),self.report())
        self.assertEqual(result["observedActions"],1)
        self.assertEqual(result["results"][0]["status"],"client-function-returned")
        self.assertFalse(result["runtimeGameplayVerified"])
    def test_missing_action_is_untested(self):
        r=self.report();r["results"]=[]
        self.assertEqual(audit.evaluate(self.contracts(),r)["results"][0]["status"],"not-tested")
    def test_unknown_action_rejected(self):
        r=self.report();r["results"][0]["action"]="fire_remote"
        with self.assertRaises(ValueError):audit.evaluate(self.contracts(),r)
    def test_malformed_duration_rejected(self):
        r=self.report();r["results"][0]["durationSeconds"]=-2
        with self.assertRaises(ValueError):audit.evaluate(self.contracts(),r)
    def test_unreviewed_rejected(self):
        c=self.contracts();c["contracts"][0]["reviewed"]=False
        with self.assertRaises(ValueError):audit.evaluate(c,self.report())
    def test_feature_coverage(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"abc"},
              "features":[{"feature":"stats"},{"feature":"rebirth"}]}
        backlog={"placeId":123,"scanId":"abc","candidates":[
          {"feature":"rebirth","transaction":"t1"}]}
        evaluated=audit.evaluate(self.contracts(),self.report())
        result=coverage.report(plan,backlog,self.contracts(),evaluated)
        self.assertEqual(result["featureCount"],2)
        self.assertEqual(result["gameplayFunctionsVerified"],0)
        self.assertEqual(result["features"][1]["observedWorkflows"],1)
    def test_nan_and_infinity_rejected(self):
        for duration in (float("nan"),float("inf"),float("-inf")):
            r=self.report();r["results"][0]["durationSeconds"]=duration
            with self.assertRaises(ValueError):audit.evaluate(self.contracts(),r)
    def test_scan_provenance(self):
        c=self.contracts();c["scanId"]="scan-a"
        r=self.report();r["scanId"]="scan-b"
        with self.assertRaises(ValueError):audit.evaluate(c,r)
        r["scanId"]="scan-a"
        self.assertEqual(audit.evaluate(c,r)["scanId"],"scan-a")
    def test_feature_specific_action_attribution(self):
        c=self.contracts()
        c["contracts"].append({"feature":"rebirth","action":"list_player_gui",
                               "scope":"client-read-only","reviewed":True})
        r=self.report()
        r["results"].append({"action":"list_player_gui","success":False,
                             "durationSeconds":0.2,"error":"missing"})
        evaluated=audit.evaluate(c,r)
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"abc"},
              "features":[{"feature":"stats"},{"feature":"rebirth"}]}
        backlog={"placeId":123,"scanId":"abc","candidates":[]}
        result=coverage.report(plan,backlog,c,evaluated)
        stats,rebirth=result["features"]
        self.assertEqual(stats["clientExecutionEvidence"],{"read_leaderstats":"client-function-returned"})
        self.assertEqual(rebirth["clientExecutionEvidence"],{"list_player_gui":"client-function-error"})
        self.assertEqual(rebirth["readiness"],"client-action-error")
        self.assertEqual(evaluated["results"][0]["failedCalls"],1)
    def test_duplicate_feature_action_rejected(self):
        c=self.contracts();c["contracts"].append(dict(c["contracts"][0]))
        with self.assertRaises(ValueError):audit.evaluate(c,self.report())
    def test_scan_mismatch_rejected(self):
        plan={"integrity":{"scanComplete":True,"placeId":123,"scanId":"abc"},"features":[]}
        with self.assertRaises(ValueError):
            coverage.report(plan,{"placeId":123,"scanId":"wrong","candidates":[]})
if __name__=="__main__":unittest.main()
