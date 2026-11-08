"""Private versioned presentation metadata. Separate from measured training records."""
import json,os
from pathlib import Path

def read(directory):
    p=Path(directory)/'.presentations';files=sorted(p.glob('v[0-9][0-9][0-9][0-9][0-9][0-9].json')) if p.exists() else []
    if not files:return {'version':0,'items':[]}
    value=json.loads(files[-1].read_text(encoding='utf-8'))
    if value['version']!=int(files[-1].stem[1:]):raise ValueError('展示历史版本不一致')
    return value

def append(directory,item,expected_version):
    p=Path(directory)/'.presentations';p.mkdir(parents=True,exist_ok=True);lock=p/'.write.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd)
    try:
        value=read(directory)
        if value['version']!=expected_version:raise ValueError('展示历史版本冲突；未覆盖')
        if value['items'] and value['items'][-1]==item:return value['version']
        version=value['version']+1
        with (p/f'v{version:06d}.json').open('x',encoding='utf-8') as f:
            json.dump({'version':version,'items':value['items']+[item]},f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        return version
    finally:lock.unlink()
