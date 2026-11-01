import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from gui_discovery_v72 import script,import_log,candidates
PLACE=85896571713843
def item(path=None):
    path=path or ["ScreenGui","HUD","Button"]
    return {"className":"ImageButton","path":path,
            "uniquePath":[{"name":x,"className":"ImageButton" if j==len(path)-1 else "Frame","ordinal":1} for j,x in enumerate(path)],
            "text":"","visible":True,"active":True,"effectiveVisible":True}
def log(items,count=None,finished=True,pages=True):
    count=len(items) if count is None else count
    lines=["LYCOLES_V72_BEGIN "+json.dumps({"schemaVersion":"72.gui","placeId":PLACE,"count":count,"pageSize":100,"pages":(count+99)//100})]
    for i,r in items.items():lines.append("LYCOLES_V72_ITEM "+str(i)+" "+json.dumps(r))
    if pages:
        for i in range(1,(count+99)//100+1):lines.append("LYCOLES_V72_PAGE_END "+str(i))
    if finished:lines.append("LYCOLES_V72_END "+str(count))
    return "\n".join(lines)
class TestV72(unittest.TestCase):
    def test_luau_controls(self):
        s=script(PLACE)
        for token in ("GetDescendants()","effectiveVisible","uniquePath","LYCOLES_V72_PAGE_END","Export all","Scan"):
            self.assertIn(token,s)
    def test_no_remote_invocation(self):
        s=script(PLACE)
        self.assertNotIn(":FireServer(",s)
        self.assertNotIn(":InvokeServer(",s)
    def test_complete(self):
        result=import_log(log({1:item()}),PLACE)
        self.assertTrue(result["complete"])
        self.assertEqual(result["recovered"],1)
    def test_partial_recovery(self):
        result=import_log(log({2:item()},count=3,finished=False,pages=False),PLACE)
        self.assertFalse(result["complete"])
        self.assertEqual(result["missingIndices"],[1,3])
    def test_strict(self):
        with self.assertRaisesRegex(ValueError,"incomplete"):
            import_log(log({2:item()},count=3),PLACE,True)
    def test_duplicate_paths(self):
        result=import_log(log({1:item(),2:item()}),PLACE)
        self.assertEqual(result["duplicatePathCount"],1)
        self.assertTrue(result["controls"][0]["ambiguousPath"])
    def test_candidates_unverified(self):
        result=candidates(import_log(log({1:item()}),PLACE))
        self.assertEqual(result["verifiedActions"],0)
        self.assertIsNone(result["candidates"][0]["outcome"])
    def test_multiple_sessions(self):
        partial=log({1:item()},count=2,finished=False)
        self.assertTrue(import_log(partial+"\n"+log({1:item()}),PLACE)["complete"])
    def test_wrong_place(self):
        with self.assertRaisesRegex(ValueError,"no valid"):
            import_log(log({1:item()}),123)
    def test_bad_path(self):
        with self.assertRaisesRegex(ValueError,"invalid path"):
            import_log(log({1:item(["bad\npath"])}),PLACE)
    def test_zero(self):
        self.assertTrue(import_log(log({}),PLACE)["complete"])
    def test_limit(self):
        with self.assertRaises(ValueError):script(PLACE,limit=20001)
if __name__=="__main__":unittest.main()
