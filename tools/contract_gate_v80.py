#!/usr/bin/env python3
"""v80 independent-session evidence gate and review-only action drafts."""
import argparse,json,hashlib,math
from collections import defaultdict
from pathlib import Path
def flat(d,p=''):
 o={}
 for k,v in d.items():
  key=p+'.'+str(k) if p else str(k)
  if isinstance(v,dict):o.update(flat(v,key))
  elif type(v) in (str,bool,int,float) and (type(v) is not float or math.isfinite(v)):o[key]=v
 return o
def changes(e):
 a,b=flat(e['before']),flat(e['after']);o={}
 for k in a.keys()&b.keys():
  x,y=a[k],b[k]
  if type(x)!=type(y) or x==y:continue
  o[k]=('increase' if y>x else 'decrease') if type(x) in (int,float) else ('toggle' if type(x) is bool else 'change')
 return o
def identity(e):
 d=e['details']
 return ('keyboard',d['key'],d['gameProcessed']) if e['kind']=='keyboard' else ('gui',json.dumps(d['uniquePath'],ensure_ascii=False,sort_keys=True))
def load(paths,place):
 out={};warnings=[]
 for p in paths:
  p=Path(p)
  if not p.is_file() or p.stat().st_size>30000000:raise ValueError('invalid log '+str(p))
  for n,line in enumerate(p.read_text(encoding='utf-8-sig',errors='replace').splitlines(),1):
   marker=next((m for m in ('LYCOLES_V76_EVENT ','LYCOLES_V78_EVENT ','LYCOLES_V79_EVENT ') if m in line),None)
   if not marker:continue
   try:e=json.loads(line.split(marker,1)[1])
   except json.JSONDecodeError:warnings.append(str(p)+':'+str(n));continue
   if not isinstance(e,dict) or e.get('placeId')!=place or e.get('kind') not in ('keyboard','gui'):continue
   if type(e.get('index')) is not int or e['index']<1 or not isinstance(e.get('captureId'),str):continue
   if any(not isinstance(e.get(k),dict) for k in ('before','after','details')):continue
   d=e['details']
   if e['kind']=='keyboard' and (not isinstance(d.get('key'),str) or type(d.get('gameProcessed')) is not bool):continue
   if e['kind']=='gui' and not isinstance(d.get('uniquePath'),list):continue
   k=(e['captureId'],e['index'])
   if k in out and out[k]!=e:raise ValueError('conflicting event '+str(k))
   out[k]=e
 return list(out.values()),warnings
def evaluate(events,min_sessions=2,min_per_session=2,control_threshold=.25):
 if type(min_sessions) is not int or min_sessions<2 or type(min_per_session) is not int or min_per_session<1:raise ValueError('invalid thresholds')
 if type(control_threshold) not in (int,float) or not 0<=control_threshold<=1:raise ValueError('invalid control threshold')
 groups=defaultdict(list)
 for e in events:groups[identity(e)].append(e)
 rows=[]
 for key,items in sorted(groups.items(),key=lambda kv:str(kv[0])):
  sessions=defaultdict(int)
  for e in items:sessions[e['captureId']]+=1
  common=set.intersection(*(set(changes(e).items()) for e in items)) if items else set()
  signals=[]
  for signal,direction in sorted(common):
   controls=[changes(e).get(signal)==direction for other,group in groups.items() if other!=key for e in group]
   rate=sum(controls)/len(controls) if controls else None
   signals.append({'signal':signal,'direction':direction,'otherInputRate':rate,'otherInputSamples':len(controls)})
  enough=len(sessions)>=min_sessions and all(n>=min_per_session for n in sessions.values())
  qualified=enough and len(signals)==1 and signals[0]['otherInputRate'] is not None and signals[0]['otherInputRate']<=control_threshold
  rows.append({'input':list(key),'observations':len(items),'sessions':len(sessions),'sessionCounts':dict(sessions),'signals':signals,'status':'review_candidate' if qualified else 'needs_more_evidence','executionEnabled':False})
 return {'schemaVersion':'80.gate','events':len(events),'groups':rows,'verified':False,'executionEnabled':False}
def draft(report,place):
 contracts=[]
 for g in report['groups']:
  if g['status']!='review_candidate':continue
  token=json.dumps([place,g['input']],ensure_ascii=False,sort_keys=True)
  contracts.append({'id':hashlib.sha256(token.encode()).hexdigest()[:16],'input':g['input'],'expected':g['signals'][0],'status':'manual_review_required','executionEnabled':False})
 return {'schemaVersion':'80.contracts','placeId':place,'contracts':contracts,'executionEnabled':False}
def main():
 p=argparse.ArgumentParser();p.add_argument('--place-id',type=int,required=True);p.add_argument('--event-log',type=Path,action='append',required=True);p.add_argument('--output',type=Path,default=Path('build/release-v80'))
 a=p.parse_args()
 if a.place_id<=0:p.error('invalid place')
 events,warnings=load(a.event_log,a.place_id);report=evaluate(events);contracts=draft(report,a.place_id)
 a.output.mkdir(parents=True,exist_ok=True)
 for name,data in [('evidence-gate-v80.json',report),('action-drafts-v80.json',contracts),('warnings-v80.json',warnings)]:
  (a.output/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'events':len(events),'groups':len(report['groups']),'drafts':len(contracts['contracts']),'verified':False}))
if __name__=='__main__':main()
