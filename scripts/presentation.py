"""State-matched, reproducible asset/copy selection; no training-score randomness."""
import hashlib,json
from pathlib import Path
from rating import band,CONTEXT_KEYS

ASSETS=Path(__file__).resolve().parents[1]/'assets'

def load_library():return json.loads((ASSETS/'presentation-library.json').read_text(encoding='utf-8'))

def verify_pose(pose):
    path=(ASSETS/pose['path']).resolve()
    if (not path.is_relative_to(ASSETS.resolve()) or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest()!=pose.get('sha256')):
        raise ValueError('动物素材内容与验收SHA256不符；需要重新验收')
    return path

def choose(record,rating,recent=(),person_id='self',include_quip=True):
    library=load_library();level=band(rating.get('mean',rating['stars']));tags=rating['state_tags']
    state=next((t for t in ['discomfort','final_sprint','fatigued','easy','normal'] if t in tags),'normal')
    owned=[x for x in recent if x.get('person_id')==person_id]
    key=str(record.get('record_id') or hashlib.sha256(json.dumps({'source':record.get('source'),'metrics':record.get('metrics')},ensure_ascii=False,sort_keys=True).encode()).hexdigest()[:20])
    same=next((x for x in reversed(owned) if x.get('record_id')==key and x.get('level')==level and x.get('state')==state),None)
    poses=[x for x in library['poses'] if x['level']==level and x.get('qa_approved') and x.get('goggles') is False and (ASSETS/x['path']).is_file()]
    if not poses:raise ValueError(f'{level}星{library["levels"][str(level)]["animal"]}素材缺失；不会退回真人或线条占位')
    quips=[x for x in library['quips'] if x['level']==level] if include_quip else []
    def pick(rows,kind):
        if same:
            exact=next((x for x in rows if x['id']==same.get(kind+'_id')),None)
            if exact:return exact
        matched=[x for x in rows if state in x['tags']] or [x for x in rows if 'normal' in x['tags']] or rows
        used={x.get(kind+'_id') for x in owned[-6:] if x.get('record_id')!=key}
        fresh=[x for x in matched if x['id'] not in used]
        if fresh:pool=fresh
        else:
            last={row['id']:max((i for i,x in enumerate(owned) if x.get(kind+'_id')==row['id']),default=-1) for row in matched}
            oldest=min(last.values());pool=[row for row in matched if last[row['id']]==oldest]
        digest=hashlib.sha256((person_id+'|'+key+'|'+state+'|'+kind).encode()).digest()
        # Hash rotates an eligible pose/copy only; it never enters scoring.
        return pool[int.from_bytes(digest[:4],'big')%len(pool)]
    pose=pick(poses,'pose');verify_pose(pose)
    quip=pick(quips,'quip') if include_quip else {'id':None,'text':''}
    text=quip['text']
    replacements={m['key']:m['raw_value'] for m in record.get('metrics',[]) if m['status']=='confirmed' and m['key'] not in CONTEXT_KEYS}
    for field,value in replacements.items():text=text.replace('{'+field+'}',value)
    if '{' in text or '}' in text:raise ValueError('锐评需要的真实指标未提供；没有补造数值')
    return {'pose_id':pose['id'],'quip_id':quip['id'],'decoration_path':str(ASSETS/pose['path']),'quip':text,'animal':library['levels'][str(level)]['animal'],'level_name':library['levels'][str(level)]['label'],'level':level,'state':state,'record_id':key,'person_id':person_id,'anti_repeat_window':6,'pose_exact_state_match':state in pose['tags'],'quota_affects_scores':False}
