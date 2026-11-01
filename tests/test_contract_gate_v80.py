import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from contract_gate_v80 import flat,changes,identity,load,evaluate,draft
P=85896571713843
def e(i,s='a',key='E',a=1,b=2):
 return {'placeId':P,'captureId':s,'index':i,'kind':'keyboard','details':{'key':key,'gameProcessed':False},'before':{'🥚 Hatches':a},'after':{'🥚 Hatches':b}}
class Tests(unittest.TestCase):
 def test_unicode(self):self.assertIn('🥚 Hatches',changes(e(1)))
 def test_flat(self):self.assertEqual(flat({'a':{'b':1}}),{'a.b':1})
 def test_increase(self):self.assertEqual(changes(e(1))['🥚 Hatches'],'increase')
 def test_decrease(self):self.assertEqual(changes(e(1,a=2,b=1))['🥚 Hatches'],'decrease')
 def test_noop(self):self.assertEqual(changes(e(1,a=1,b=1)),{})
 def test_boolean(self):self.assertEqual(changes({'before':{'a':True},'after':{'a':False}}),{'a':'toggle'})
 def test_string(self):self.assertEqual(changes({'before':{'a':'a'},'after':{'a':'b'}}),{'a':'change'})
 def test_types(self):self.assertEqual(changes({'before':{'a':True},'after':{'a':1}}),{})
 def test_identity(self):self.assertEqual(identity(e(1))[1],'E')
 def test_empty(self):self.assertEqual(evaluate([])['events'],0)
 def test_one_session(self):self.assertEqual(evaluate([e(1),e(2)])['groups'][0]['status'],'needs_more_evidence')
 def test_no_controls(self):self.assertEqual(evaluate([e(1),e(2),e(3,'b'),e(4,'b')])['groups'][0]['status'],'needs_more_evidence')
 def test_candidate(self):
  rows=evaluate([e(1),e(2),e(3,'b'),e(4,'b'),e(5,'c','F',1,1)])['groups']
  self.assertEqual(next(x for x in rows if x['input'][1]=='E')['status'],'review_candidate')
 def test_confounded(self):
  rows=evaluate([e(1),e(2),e(3,'b'),e(4,'b'),e(5,'c','F')])['groups']
  self.assertEqual(next(x for x in rows if x['input'][1]=='E')['status'],'needs_more_evidence')
 def test_conflict(self):
  rows=evaluate([e(1),e(2),e(3,'b',a=2,b=1),e(4,'b',a=2,b=1),e(5,'c','F',1,1)])['groups']
  self.assertEqual(next(x for x in rows if x['input'][1]=='E')['status'],'needs_more_evidence')
 def test_disabled(self):self.assertFalse(draft(evaluate([]),P)['executionEnabled'])
 def test_unverified(self):self.assertFalse(evaluate([])['verified'])
 def test_bad_threshold(self):
  with self.assertRaises(ValueError):evaluate([],min_sessions=1)
 def test_parser(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'log';p.write_text('LYCOLES_V78_EVENT '+json.dumps(e(1),ensure_ascii=False),encoding='utf-8')
   self.assertEqual(len(load([p],P)[0]),1)
 def test_dedup(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'log';line='LYCOLES_V78_EVENT '+json.dumps(e(1));p.write_text(line+'\n'+line)
   self.assertEqual(len(load([p],P)[0]),1)
 def test_collision(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'log';p.write_text('\n'.join('LYCOLES_V78_EVENT '+json.dumps(x) for x in [e(1),e(1,b=9)]))
   with self.assertRaises(ValueError):load([p],P)
if __name__=='__main__':unittest.main()
