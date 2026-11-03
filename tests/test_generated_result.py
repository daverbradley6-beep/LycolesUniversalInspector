import importlib.util,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("generated_result",ROOT/"tools"/"generated_result.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class GeneratedResultTests(unittest.TestCase):
    def build(self,**changes):
        values={"place_id":123,"scan_id":"scan12345",
            "code":"assert(game.PlaceId == 123, \"Incorrect Roblox place\")",
            "requested_capability":"show pet evidence",
            "validation":{"placeGuard":True,"unsafeOperationsFound":False},
            "capabilities":["Stats","Admin Commands"]}
        values.update(changes)
        return module.build(**values)

    def test_display_only_claims_fail_closed(self):
        result=self.build()
        self.assertEqual(result["schemaVersion"],"110.generated-result.1")
        self.assertTrue(result["staticValidationPassed"])
        for claim in ("packageAuthenticityVerified","runtimeVerified","gameplayVerified",
                      "executionAuthorized"):
            self.assertFalse(result[claim])
        self.assertRegex(result["generatedCodeSHA256"],r"^[a-f0-9]{64}$")

    def test_rejects_missing_place_guard_and_bad_validation(self):
        with self.assertRaisesRegex(ValueError,"place guard"):
            self.build(code="print('unsafe identity')")
        with self.assertRaisesRegex(ValueError,"validation"):
            self.build(validation={"placeGuard":False})

    def test_deterministic(self):
        self.assertEqual(self.build(),self.build())
