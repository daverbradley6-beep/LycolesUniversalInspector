"""Controlled generated Tool trial execution; never live gameplay verification."""
import os
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from controlled_tool_activation import canonical,execute

PLACE=85896571713843
DEFAULTS=(ROOT/"build"/"luau-0.744"/"luau",Path("/tmp/luau-0.744/luau"))
LUAU=Path(os.environ["LUAU_BIN"]) if os.environ.get("LUAU_BIN") else next(
    (path for path in DEFAULTS if path.is_file()),DEFAULTS[0])


@unittest.skipUnless(LUAU.is_file(),"official Luau runtime not installed")
class ControlledToolActivationTests(unittest.TestCase):
    def test_generated_trial_equips_activates_observes_and_stops(self):
        result=execute(PLACE,LUAU)
        self.assertTrue(result["luauExecuted"])
        self.assertTrue(result["toolEquipped"])
        self.assertTrue(result["toolActivationObserved"])
        self.assertTrue(result["counterIncrementObserved"])
        self.assertTrue(result["failureBoundaryObserved"])
        self.assertTrue(result["metadataDriftRejected"])
        self.assertTrue(result["repeatAttemptBoundaryObserved"])
        self.assertFalse(result["robloxRuntimeVerified"])
        self.assertFalse(result["serverAuthorityVerified"])
        self.assertFalse(result["causalityProven"])
        self.assertFalse(result["gameplayVerified"])

    def test_execution_report_is_deterministic(self):
        self.assertEqual(canonical(execute(PLACE,LUAU)),canonical(execute(PLACE,LUAU)))


if __name__=="__main__":unittest.main()
