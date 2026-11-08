"""Optional, explicit copy preferences; never part of measured training data."""
import json,os
from pathlib import Path
THEMES={'general','study','creative','technical','service','other'}
def empty(person):return {'version':0,'person_id':person,'status':'unasked','reference':None,'theme':'general','humor':'playful'}
def validate_context(value):
    if not isinstance(value,dict) or set(value)-{'confirmed','reference','theme','humor'} or value.get('confirmed') is not True:raise ValueError('persona仅接受用户明确提供或确认的精简背景')
    ref=value.get('reference','')
    if not isinstance(ref,str) or len(ref)>80 or '\n' in ref:raise ValueError('背景参考需简短单行')
    if value.get('theme','general') not in THEMES or value.get('humor','playful') not in ('gentle','playful'):raise ValueError('文案主题/幽默偏好无效')
    return dict(reference=ref or None,theme=value.get('theme','general'),humor=value.get('humor','playful'))
def read(directory,person):
    root=Path(directory);owner=root/'.owner.json'
    if owner.exists() and json.loads(owner.read_text(encoding='utf-8'))['person_id']!=person:raise ValueError('文案偏好属于另一人')
    paths=sorted((root/'.quip-profiles').glob('v??????.json'))
    if not paths:return empty(person)
    obj=json.loads(paths[-1].read_text(encoding='utf-8'))
    if obj['person_id']!=person:raise ValueError('文案偏好身份冲突')
    return obj
def resolve(saved,command=None):
    if command is None:return dict(saved)
    if not isinstance(command,dict) or set(command)-{'action','reference','theme','humor'}:raise ValueError('文案偏好操作无效')
    action=command.get('action')
    if action=='set':fields=validate_context({'confirmed':True,**{k:v for k,v in command.items() if k!='action'}});status='selected'
    elif action in ('skip','clear','offered'):fields=dict(reference=None,theme='general',humor='playful');status='offered' if action=='offered' else 'skipped'
    else:raise ValueError('文案偏好操作需set/skip/clear/offered')
    return {**saved,**fields,'status':status}
def append(directory,person,value,expected_version):
    root=Path(directory)/'.quip-profiles';root.mkdir(parents=True,exist_ok=True);lock=root/'.write.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
    try:
        current=read(directory,person)
        if current['version']!=expected_version:raise ValueError('文案偏好版本冲突，未覆盖')
        content={k:v for k,v in value.items() if k!='version'}
        if content=={k:v for k,v in current.items() if k!='version'}:return current
        new={**content,'version':expected_version+1}
        with (root/f'v{new["version"]:06d}.json').open('x',encoding='utf-8') as f:
            json.dump(new,f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        return read(directory,person)
    finally:lock.unlink()

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--ledger',required=True);p.add_argument('--action',required=True,choices=['set','skip','clear','offered']);p.add_argument('--persona-json');p.add_argument('--expected-version',type=int,required=True)
    a=p.parse_args();root=Path(a.ledger)
    owner=root/'.owner.json'
    if not owner.exists() or json.loads(owner.read_text(encoding='utf-8')).get('person_id')!='self':raise ValueError('需使用已有本人私有台账，不另建台账')
    saved=read(root,'self');command={'action':a.action}
    if a.action=='set':command.update(validate_context(json.loads(a.persona_json)))
    updated=append(root,'self',resolve(saved,command),a.expected_version)
    print(json.dumps({'status':updated['status'],'version':updated['version']},ensure_ascii=False))
