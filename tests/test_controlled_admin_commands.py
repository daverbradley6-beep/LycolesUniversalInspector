"""Controlled generated Admin Commands execution against bounded Roblox stubs."""
import os
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))

from controlled_admin_commands import canonical,execute

PLACE=85896571713843
DEFAULTS=(ROOT/"build"/"luau-0.744"/"luau",Path("/tmp/luau-0.744/luau"))
LUAU=Path(os.environ["LUAU_BIN"]) if os.environ.get("LUAU_BIN") else next(
    (path for path in DEFAULTS if path.is_file()),DEFAULTS[0])


@unittest.skipUnless(LUAU.is_file(),"official Luau runtime not installed")
class ControlledAdminCommandsTests(unittest.TestCase):
    def test_commands_share_state_cleanup_and_survive_respawn(self):
        result=execute(PLACE,LUAU)
        self.assertTrue(result["luauExecuted"])
        self.assertTrue(result["commandStateVerified"])
        self.assertTrue(result["cleanupVerified"])
        self.assertTrue(result["respawnVerified"])
        self.assertTrue(result["placeGuardVerified"])
        self.assertFalse(result["robloxRuntimeVerified"])
        self.assertFalse(result["liveGameVerified"])
        self.assertFalse(result["serverAuthorityVerified"])
        self.assertFalse(result["gameplayVerified"])
    def test_place_guard_blocks_initialization(self):
        result=execute(PLACE,LUAU,PLACE+1)
        self.assertTrue(result["placeGuardVerified"])
        self.assertFalse(result["commandStateVerified"])
        self.assertFalse(result["cleanupVerified"])
        self.assertFalse(result["respawnVerified"])
    def test_execution_report_is_deterministic(self):
        self.assertEqual(canonical(execute(PLACE,LUAU)),canonical(execute(PLACE,LUAU)))


if __name__=="__main__":unittest.main()
