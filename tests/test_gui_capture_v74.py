import json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from gui_capture_v74 import script,merge,candidates,parse_page
PLACE=85896571713843
def record(name="Button"):
 path=["ScreenGui","HUD",name]
 return {"className":"TextButton","path":path,"uniquePath":[{"name":n,"className":"TextButton" if i==2 else "Frame","ordinal":1} for i,n in enumerate(path)],"text":"Click","visible":True,"active":True,"effectiveVisible":True}
def page(number,records,total=2,capture="capture-a",size=1):
 first=(number-1)*size+1;last=min(number*size,total)
 h={"schemaVersion":"74.page","placeId":PLACE,"captureId":capture,"page":number,"pageSize":size,"total":total,"first":first,"last":last}
 lines=["LYCOLES_V74_PAGE_BEGIN "+json.dumps(h)]
 for i,r in records.items():lines.append("LYCOLES_V74_ITEM "+str(i)+" "+json.dumps(r))
 lines.append("LYCOLES_V74_PAGE_END "+json.dumps({"captureId":capture,"page":number,"first":first,"last":last}))
 return "\n".join(lines)
class TestV74(unittest.TestCase):
 def test_script(self):
  s=script(PLACE)
  self.assertIn("Export page",s)
  self.assertIn("GenerateGUID",s)
 def test_no_remote(self):
  self.assertNotIn(":FireServer(",script(PLACE))
 def test_invalid_limit(self):
  with self.assertRaises(ValueError):script(PLACE,limit=20001)
 def test_merge_two_files(self):
  a=page(1,{1:record("A")});b=page(2,{2:record("B")})
  d=merge([a,b],PLACE)
  self.assertTrue(d["complete"])
  self.assertEqual(d["recovered"],2)
 def test_missing_page(self):
  d=merge([page(2,{2:record()})],PLACE)
  self.assertFalse(d["complete"])
  self.assertEqual(d["missingPages"],[1])
 def test_reject_incomplete_page(self):
  with self.assertRaisesRegex(ValueError,"no complete"):
   merge([page(1,{})],PLACE)
 def test_reject_wrong_place(self):
  with self.assertRaisesRegex(ValueError,"no complete"):
   merge([page(1,{1:record()})],123)
 def test_reject_conflict(self):
  a=page(1,{1:record("A")});b=page(1,{1:record("B")})
  with self.assertRaisesRegex(ValueError,"conflicting page"):merge([a,b],PLACE)
 def test_reject_mixed_sessions(self):
  a=page(1,{1:record("A")});b=page(1,{1:record("B")},capture="capture-b")
  with self.assertRaisesRegex(ValueError,"multiple capture"):merge([a,b],PLACE)
 def test_select_session(self):
  a=page(1,{1:record("A")});b=page(1,{1:record("B")},capture="capture-b")
  self.assertEqual(merge([a,b],PLACE,"capture-b")["captureId"],"capture-b")
 def test_duplicate_paths(self):
  d=merge([page(1,{1:record()},total=2,size=2).replace('"last": 1','"last": 2')],PLACE) if False else merge([page(1,{1:record(),2:record()},total=2,size=2)],PLACE)
  self.assertEqual(d["duplicatePathCount"],1)
 def test_v73_compatible(self):
  d=merge([page(1,{1:record("A")})],PLACE)
  c=candidates(d)
  self.assertEqual(c["schemaVersion"],"72.candidates")
  self.assertFalse(c["sourceComplete"])
  self.assertIsNone(c["candidates"][0]["outcome"])
if __name__=="__main__":unittest.main()
