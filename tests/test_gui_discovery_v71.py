import json
import pathlib
import sys
import unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/"tools"))
from gui_discovery_v71 import script,parse,make_candidates
PLACE=85896571713843
def log(controls):
    lines=["LYCOLES_V71_GUI_BEGIN "+json.dumps({"placeId":PLACE,"count":len(controls)})]
    lines.extend("LYCOLES_V71_GUI_ITEM "+str(i)+" "+json.dumps(x,ensure_ascii=False) for i,x in enumerate(controls,1))
    lines.append("LYCOLES_V71_GUI_END "+str(len(controls)))
    return "\n".join(lines)
def button():
    return {"className":"TextButton","path":["GameUI","EggPanel","HatchButton"],
            "text":"Hatch","visible":True,"active":True}
class TestV71(unittest.TestCase):
    def test_script_generation(self):
        s=script(PLACE)
        self.assertIn("LYCOLES_V71_GUI_ITEM",s)
        self.assertIn("GetDescendants()",s)
        self.assertIn("LYCOLES_V71_GUI_END",s)
    def test_no_remote_invocation(self):
        s=script(PLACE)
        self.assertNotIn(":FireServer(",s)
        self.assertNotIn(":InvokeServer(",s)
    def test_roundtrip(self):
        self.assertEqual(parse(log([button()]),PLACE)[0]["path"][-1],"HatchButton")
    def test_candidate_not_verified(self):
        result=make_candidates(parse(log([button()]),PLACE),PLACE)
        self.assertIsNone(result["candidates"][0]["outcome"])
        self.assertFalse(result["actionContractsVerified"])
    def test_zero_items(self):
        self.assertEqual(parse(log([]),PLACE),[])
    def test_incomplete(self):
        with self.assertRaisesRegex(ValueError,"incomplete"):
            parse(log([button()]).replace("LYCOLES_V71_GUI_END 1",""),PLACE)
    def test_wrong_place(self):
        with self.assertRaisesRegex(ValueError,"place mismatch"):
            parse(log([button()]),123)
    def test_duplicate_conflict(self):
        value=log([button()])
        bad=button()
        bad["text"]="Different"
        value=value.replace("LYCOLES_V71_GUI_END 1","LYCOLES_V71_GUI_ITEM 1 "+json.dumps(bad)+"\nLYCOLES_V71_GUI_END 1")
        with self.assertRaisesRegex(ValueError,"conflicting"):
            parse(value,PLACE)
    def test_bad_path(self):
        bad=button()
        bad["path"]=["x\nbad"]
        with self.assertRaisesRegex(ValueError,"invalid control name"):
            parse(log([bad]),PLACE)
if __name__=="__main__": unittest.main()
