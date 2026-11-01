#!/usr/bin/env python3
"""v104 deterministic read-only client observation release builder."""
import argparse,hashlib,json,re
from pathlib import Path
ROOTS={'Workspace','PlayerGui','ReplicatedStorage','Players'}
PROPS={'TextLabel':'Text','TextButton':'Text','ImageButton':'Visible','TextBox':'Text','IntValue':'Value','NumberValue':'Value','BoolValue':'Value','StringValue':'Value','ProximityPrompt':'Enabled','ClickDetector':'Name','Tool':'Name','ScreenGui':'Enabled'}
SEG=re.compile(r'^[A-Za-z0-9_ .:-]{1,80}$')
def parts(value):
    if isinstance(value,str):
        value=value.split('.')
        if value[0]=='game':value=value[1:]
    if not isinstance(value,list) or not 2<=len(value)<=12 or value[0] not in ROOTS or any(not isinstance(x,str) or not SEG.fullmatch(x) for x in value):return None
    return value
def build(source,place_id):
    if type(place_id)!=int or place_id<=0:raise ValueError('invalid place')
    if isinstance(source,dict):
        if source.get('placeId') is not None and source['placeId']!=place_id:raise ValueError('place mismatch')
        source=next((source[k] for k in ('observations','objects','instances','entries') if isinstance(source.get(k),list)),None)
    if not isinstance(source,list) or len(source)>50000:raise ValueError('invalid inspection')
    accepted={};rejected={}
    def reject(reason):rejected[reason]=rejected.get(reason,0)+1
    for row in source:
        if not isinstance(row,dict):reject('invalid_record');continue
        path=parts(row.get('path',row.get('fullName',row.get('fullPath'))))
        if path is None:reject('invalid_path');continue
        cls=row.get('className',row.get('class'))
        if not isinstance(cls,str) or cls not in PROPS:reject('unsupported_class');continue
        key=tuple(path)
        if key in accepted:
            reject('duplicate_path' if accepted[key]['className']==cls else 'conflicting_class')
            continue
        accepted[key]={'path':path,'className':cls,'property':PROPS[cls],'canAutomate':False}
    objects=sorted(accepted.values(),key=lambda x:(x['path'],x['className']))
    if len(objects)>150:
        rejected['output_limit']=len(objects)-150
        objects=objects[:150]
    result={'schemaVersion':'104.release','placeId':place_id,'inputCount':len(source),
            'acceptedCount':len(objects),'rejectedCount':sum(rejected.values()),
            'rejections':dict(sorted(rejected.items())),'objects':objects,
            'verifiedInGame':False,'gameplayFunctionsGenerated':0,'readOnly':True}
    assert result['acceptedCount']+result['rejectedCount']==result['inputCount']
    return result
def luau(report):
    if report.get('schemaVersion')!='104.release':raise ValueError('invalid report')
    lines=['-- Lycoles v104: read-only client observations',
           'local Players = game:GetService("Players")',
           'local player = Players.LocalPlayer',
           'if not player or game.PlaceId ~= '+str(report['placeId'])+' then return end',
           'local gui = Instance.new("ScreenGui")',
           'gui.Name = "LycolesObserverV104"',
           'gui.ResetOnSpawn = false',
           'gui.Parent = player:WaitForChild("PlayerGui")',
           'local frame = Instance.new("ScrollingFrame")',
           'frame.Size = UDim2.fromOffset(420,330)',
           'frame.Position = UDim2.fromScale(0.05,0.15)',
           'frame.Parent = gui',
           'local layout = Instance.new("UIListLayout")',
           'layout.Parent = frame',
           'local close = Instance.new("TextButton")',
           'close.Size = UDim2.new(1,-8,0,34)',
           'close.Text = "Close"',
           'close.Parent = frame',
           'close.Activated:Connect(function() gui:Destroy() end)',
           'local roots = {Workspace=workspace, PlayerGui=player.PlayerGui, ReplicatedStorage=game:GetService("ReplicatedStorage"), Players=Players}',
           'local items = {']
    for item in report['objects']:
        path='{'+','.join(json.dumps(p,ensure_ascii=True) for p in item['path'])+'}'
        label=json.dumps(item['className']+': '+item['path'][-1],ensure_ascii=True)
        lines.append(' {path='+path+', property='+json.dumps(item['property'])+', label='+label+'},')
    lines+=['}',
            'local labels = {}',
            'for i,item in ipairs(items) do',
            ' local row = Instance.new("TextLabel")',
            ' row.Size = UDim2.new(1,-8,0,34)',
            ' row.TextScaled = true',
            ' row.Parent = frame',
            ' labels[i] = row',
            'end',
            'local active = true',
            'gui.Destroying:Connect(function() active = false end)',
            'task.spawn(function()',
            ' while active and gui.Parent do',
            '  for i,item in ipairs(items) do',
            '   local node = roots[item.path[1]]',
            '   for j=2,#item.path do',
            '    if not node then break end',
            '    node = node:FindFirstChild(item.path[j])',
            '   end',
            '   local value = "not found"',
            '   if node then',
            '    local ok,result = pcall(function() return node[item.property] end)',
            '    value = ok and tostring(result) or "unavailable"',
            '   end',
            '   labels[i].Text = item.label .. " : " .. value',
            '  end',
            '  frame.CanvasSize = UDim2.fromOffset(0,layout.AbsoluteContentSize.Y+12)',
            '  task.wait(1)',
            ' end',
            'end)']
    return '\n'.join(lines)+'\n'
def canonical(x):return (json.dumps(x,sort_keys=True,indent=2,ensure_ascii=False)+'\n').encode()
def audit(directory):
    root=Path(directory)
    try:
        m=root/'manifest-v104.json'
        if m.is_symlink():raise ValueError('symlink manifest')
        manifest=json.loads(m.read_text())
        names={'report-v104.json','LycolesObserverV104.client.lua'}
        if manifest.get('schemaVersion')!='104.manifest' or manifest.get('readOnly') is not True or manifest.get('verifiedInGame') is not False or set(manifest.get('files',{}))!=names:raise ValueError('invalid manifest')
        for name in names:
            p=root/name
            if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest()!=manifest['files'][name]:raise ValueError('file mismatch: '+name)
        report=json.loads((root/'report-v104.json').read_text())
        if report['placeId']!=manifest['placeId'] or report['readOnly'] is not True or report['verifiedInGame'] is not False or report['gameplayFunctionsGenerated']!=0:raise ValueError('invalid report')
        if (root/'report-v104.json').read_bytes()!=canonical(report) or (root/'LycolesObserverV104.client.lua').read_bytes()!=luau(report).encode():raise ValueError('not reproducible')
        return {'ok':True,'issues':[],'verifiedInGame':False,'observations':report['acceptedCount']}
    except (OSError,ValueError,KeyError,TypeError,AttributeError) as e:return {'ok':False,'issues':[str(e)],'verifiedInGame':False}
def generate(source,place_id,directory):
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    report=build(source,place_id)
    files={'report-v104.json':canonical(report),'LycolesObserverV104.client.lua':luau(report).encode()}
    for name,data in files.items():
        p=root/name
        if p.is_symlink():raise ValueError('output symlink')
        p.write_bytes(data)
    manifest={'schemaVersion':'104.manifest','placeId':place_id,'readOnly':True,'verifiedInGame':False,'files':{n:hashlib.sha256(data).hexdigest() for n,data in sorted(files.items())}}
    p=root/'manifest-v104.json'
    if p.is_symlink():raise ValueError('output symlink')
    p.write_bytes(canonical(manifest))
    return audit(root)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inspection',type=Path)
    p.add_argument('--place-id',type=int)
    p.add_argument('--output',type=Path,default=Path('build/release-v104'))
    p.add_argument('--audit-only',action='store_true')
    a=p.parse_args()
    if a.audit_only:result=audit(a.output)
    else:
        if a.inspection is None or a.place_id is None:p.error('inspection and place ID required')
        result=generate(json.loads(a.inspection.read_text(encoding='utf-8-sig')),a.place_id,a.output)
    print(json.dumps(result,sort_keys=True))
    if not result['ok']:raise SystemExit(1)
if __name__=='__main__':main()
