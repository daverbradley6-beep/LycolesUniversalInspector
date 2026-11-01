import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from evidence_reconciler_v68 import canonical, telemetry_sessions, reconcile

PLACE=85896571713843
PATH='Players/"geckoflicker"#1@Player/"leaderstats"#1@Folder/"🟣 Bubbles"#1@IntValue'
def discovery():
    entry={"index":3,"entries":[{"root":"Players","path":PATH,"className":"IntValue","value":"321"}]}
    return "LYCOLES_V54_BATCH 3/44/46 "+json.dumps(entry,ensure_ascii=False)
def session(ticks,changes):
    head={"ticks":ticks,"placeId":PLACE,"schemaVersion":"66.telemetry","eventCount":len(changes)}
    lines=["05:51:48LYCOLES_V66_HEADER "+json.dumps(head)]
    for i,(before,after) in enumerate(changes,1):
        e={"before":before,"after":after,"path":"Players.geckoflicker.leaderstats.🟣 Bubbles","tick":i+1,"kind":"stat"}
        lines.append("LYCOLES_V66_EVENT "+str(i)+" "+json.dumps(e,ensure_ascii=False))
    lines.append("LYCOLES_V66_END "+str(len(changes)))
    return "\n".join(lines)
class TestV68(unittest.TestCase):
    def test_canonical(self):
        self.assertEqual(canonical(PATH),"players.geckoflicker.leaderstats.🟣 bubbles")
        self.assertEqual(canonical(PATH),canonical("Players.geckoflicker.leaderstats.🟣 Bubbles"))
    def test_windows_console_mojibake(self):
        self.assertEqual(canonical(PATH.replace("🟣", "ðŸŸ£")),canonical(PATH))
    def test_latest_complete_session(self):
        parsed,info=telemetry_sessions(session(3,[])+"\n"+session(19,[("437","456")]),PLACE)
        self.assertEqual(info["selectedSession"],2)
        self.assertEqual(len(parsed["events"]),1)
    def test_skip_incomplete_session(self):
        parsed,info=telemetry_sessions(session(19,[("1","2")])+"\nLYCOLES_V66_HEADER {}",PLACE)
        self.assertEqual(info["selectedSession"],1)
        self.assertEqual(info["validSessions"],1)
    def test_reconcile_structural_only(self):
        result=reconcile(discovery(),session(19,[("437","456")]),PLACE)
        self.assertEqual(result["manifest"]["correlation"]["matchedEvents"],1)
        self.assertFalse(result["manifest"]["readyForActionGeneration"])
        self.assertFalse(result["matches"][0]["actionVerified"])
    def test_wrong_place_rejected(self):
        with self.assertRaises(ValueError):
            telemetry_sessions(session(19,[]),123)
    def test_empty_discovery_rejected(self):
        with self.assertRaisesRegex(ValueError,"no recoverable"):
            reconcile("",session(19,[]),PLACE)
if __name__=="__main__": unittest.main()
