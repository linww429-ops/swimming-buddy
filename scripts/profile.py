"""Minimal owner-bound adult group preference, append-only and outside the skill."""
import json,os
from pathlib import Path

def read(directory,person):
    folder=Path(directory)/'.profiles'
    files=sorted(folder.glob('v*.json')) if folder.exists() else []
    if not files:return {'version':0,'person_id':person,'adult_group':None}
    latest=json.loads(files[-1].read_text(encoding='utf-8'))
    if latest['person_id']!=person:raise ValueError('组别资料属于另一人')
    if latest['adult_group'] not in ('male','female'):raise ValueError('组别资料无效')
    return latest

def resolve(saved,answer,correction=False):
    if answer not in (None,'male','female'):raise ValueError('成人组别仅接收本人明确的男生或女生')
    prior=saved['adult_group']
    if prior and answer and answer!=prior and not correction:raise ValueError('组别与已确认值冲突；请明确是本人更正')
    return answer or prior

def append(directory,person,group,expected_version):
    if group not in ('male','female'):return expected_version
    current=read(directory,person)
    if current['version']!=expected_version:raise ValueError('组别资料版本已变化，请重试')
    if current['adult_group']==group:return expected_version
    folder=Path(directory)/'.profiles';folder.mkdir(parents=True,exist_ok=True)
    next_version=expected_version+1
    with (folder/f'v{next_version:06d}.json').open('x',encoding='utf-8') as stream:
        json.dump({'version':next_version,'person_id':person,'adult_group':group},stream,ensure_ascii=False)
        stream.flush();os.fsync(stream.fileno())
    assert read(directory,person)['adult_group']==group
    return next_version
