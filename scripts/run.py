"""Host vision JSON -> owner-isolated record -> cached animal/native card."""
import argparse,copy,hashlib,json,os,sys
from pathlib import Path
from legacy_records import validate,duplicates,read_ledger,ingest,merge
from swim_metrics import validate_metrics
from rating import grade
from presentation import choose,load_library,ASSETS,verify_pose
from render_card import render
from dolphin import assess,PROMPT
import profile
from derived import complete_metrics
import display_history
import quip_profile
from personal_quip import select as select_quip, validate_authored_quip
from image_review import review

SKILL_ROOT=Path(__file__).resolve().parents[1]

def add_feedback(record,key,label,value,scope):
    if value is None:return
    if not isinstance(value,(str,int,float)) or isinstance(value,bool):raise ValueError('主观反馈需原文或明确数字')
    text=f'{value:g}星' if key=='subjective_effort' else str(value)
    if len(text)>1500:raise ValueError('主观反馈过长')
    fingerprint=hashlib.sha256((str(record.get('record_id','unassigned'))+'|'+key+'|'+text).encode()).hexdigest()[:20]
    item={'id':'feedback-'+fingerprint,'key':key,'qualifier':'unspecified','label':label,'raw_value':text,'raw_unit':'星' if key=='subjective_effort' else '',
          'value':value,'unit':'stars' if key=='subjective_effort' else '', 'time_basis':None,'status':'confirmed','scope':scope,
          'source':{'image_id':'user-confirmed-feedback','region':scope+'；主观反馈，非截图测量','image_sha256':None}}
    existing=next((m for m in record['metrics'] if m['id']==item['id']),None)
    if existing is not None and existing!=item:raise ValueError('已有主观反馈冲突，未覆盖')
    if existing is None:record['metrics'].append(item)

def prepare(envelope,history=()):
    review(envelope)
    person=envelope.get('person_id')
    if not isinstance(person,str) or not 1<=len(person)<=100:raise ValueError('必须确认泳者身份')
    candidate=copy.deepcopy(envelope['record'])
    if candidate.get('person_id') not in (None,person):raise ValueError('记录身份与本次泳者不一致')
    candidate['person_id']=person
    partial=any(candidate.get(k) is None for k in ['session_date','distance_m','durations','time_basis'])
    if partial:
        if candidate.get('mode') not in ('real','demo'):raise ValueError('需区分演示与真实记录')
        candidate['metrics']=validate_metrics(candidate.get('metrics',[]))
        # Partial records keep raw segments, but do not derive session totals.
        for s in candidate.get('segments') or []:
            if not isinstance(s,dict) or not {'distance_m','duration_s','time_basis'}<=set(s) or s['distance_m']<=0 or s['duration_s']<=0 or s['time_basis'] not in ('active','elapsed'):raise ValueError('分段字段不正确')
        r=candidate
    else:r=validate(candidate)
    feedback=envelope.get('feedback',{})
    if not isinstance(feedback,dict):raise ValueError('feedback需为分开保存的主观字段')
    for key,label,scope in [('pre_session_intent','游前目标','before_session'),('post_session_feeling','游后体感','after_session'),('post_session_final_phase_feeling','末段主观体感','final_phase'),('post_session_breathing','游后呼吸感受','after_session'),('post_session_rhythm','游后节奏感受','after_session')]:
        add_feedback(r,key,label,feedback.get(key),scope)
    feeling=envelope.get('subjective_effort',feedback.get('subjective_effort'))
    if feeling is not None:
        if isinstance(feeling,bool) or not isinstance(feeling,(int,float)) or not 1<=feeling<=5:raise ValueError('主观投入需1–5星')
        add_feedback(r,'subjective_effort','主观投入',feeling,'after_session')
    if 'discomfort' in feedback:
        flag=feedback['discomfort']
        if flag is not None and not isinstance(flag,bool):raise ValueError('不适状态需true/false/null，疲劳不等于不适')
        r['discomfort']=flag
        if flag is not None:add_feedback(r,'discomfort_feedback','本人不适反馈','明确报告不适' if flag else '明确否认不适','after_session')
    best=envelope.get('fastest_100m')
    if best is not None:
        if not isinstance(best,dict) or set(best)!={'seconds','stroke','source'} or best['source'] not in ('user_confirmed','screenshot') or best['stroke']!=r.get('stroke') or isinstance(best['seconds'],bool) or not isinstance(best['seconds'],(int,float)) or not 20<=best['seconds']<=900:
            raise ValueError('最快100米需完整距离、同泳姿、用时秒数及截图/本人确认来源')
        seconds=best['seconds'];label='最快完整100米';source=best['source']
        add={'id':'best100-'+hashlib.sha256((str(r.get('record_id'))+'|'+str(seconds)+'|'+source).encode()).hexdigest()[:20],
             'key':'fastest_100m','qualifier':'best','label':label,'raw_value':f'{int(seconds//60)}分{int(seconds%60):02d}秒','raw_unit':'','value':seconds,'unit':'s','time_basis':None,'status':'confirmed','scope':'complete_100m',
             'source':{'image_id':'user-confirmed-best100' if source=='user_confirmed' else 'screenshot-best100','region':'完整100米；'+source,'image_sha256':None}}
        if not any(m['id']==add['id'] for m in r['metrics']):r['metrics'].append(add)
    if not partial:r=validate(r)
    h=[validate(old) for old in history if old.get('person_id','self')==person and old['mode']==r['mode']]
    d={'status':'partial','message':'关键字段缺失；原文已保留并可出简卡，未正式入账'} if partial else duplicates(r,h)
    if d['status'] not in ('new','duplicate','partial'):raise ValueError(d['message'])
    if d['status']=='duplicate':r=merge(next(old for old in h if old['record_id']==d['record_id']),r)
    derived_warnings=[] if partial else complete_metrics(r)
    rating=grade(r,h,envelope.get('dimensions'),feeling)
    rating['derived_warnings']=derived_warnings
    # Final text/pose chosen together in execute; explicit quip remains possible.
    quip=envelope.get('quip')
    if quip is not None and (not isinstance(quip,str) or not quip.strip() or '\n' in quip or len(quip)>45):raise ValueError('当次锐评需为简短单行')
    return r,rating,quip,d

def owner_check(directory,person):
    path=Path(directory)/'.owner.json'
    if path.exists():
        obj=json.loads(path.read_text(encoding='utf-8'))
        if obj['person_id']!=person:raise ValueError('此私有台账属于另一人，不读取、不比较、不保存')
    elif person!='self' and any(Path(directory).glob('v*.json')):raise ValueError('已有未标身份台账，不能归给新用户')

def bind_owner(directory,person):
    p=Path(directory);p.mkdir(parents=True,exist_ok=True);f=p/'.owner.json'
    if not f.exists():
        try:
            with f.open('x',encoding='utf-8') as stream:json.dump({'person_id':person},stream)
        except FileExistsError:pass
    owner_check(directory,person)

def execute(envelope,ledger,out,no_save=False,decoration=None,font=None,font_index=0,phone_only=False):
    review_result=review(envelope)
    validate_authored_quip(envelope.get('quip'))
    person=envelope.get('person_id');mode=envelope.get('record',{}).get('mode')
    if not no_save and envelope.get('owner_confirmed') is not True:raise ValueError('无本人长期保存授权；使用--no-save')
    if mode=='demo' and not no_save:raise ValueError('演示数据禁止入账')
    for path in [ledger,out]:
        if mode=='real' and Path(path).resolve().is_relative_to(SKILL_ROOT):raise ValueError('真实台账/输出必须在技能包之外')
    authorized=envelope.get('owner_confirmed') is True
    # Synthetic demos never read a real ledger, even if its path is accidentally supplied.
    if mode=='real' and authorized:
        owner_check(ledger,person);state=read_ledger(ledger);display=display_history.read(ledger);saved_profile=profile.read(ledger,person)
        history=state['records'];recent=display['items']
    else:
        state={'ledger_version':0,'records':[]};display={'version':0,'items':[]};saved_profile={'version':0,'person_id':person,'adult_group':None}
        history=envelope.get('history',[]) if mode=='demo' else [];recent=envelope.get('recent_presentations',[])
    r,rating,override_quip,d=prepare(envelope,history)
    saved_copy=quip_profile.read(ledger,person) if mode=='real' and authorized and person=='self' else quip_profile.empty(person)
    action=envelope.get('persona_action')
    context=quip_profile.validate_context(envelope['persona']) if envelope.get('persona') is not None else None
    command=None
    if action is not None:
        command={'action':action}
        if action=='set':
            if context is None:raise ValueError('set需用户确认的persona')
            command.update(context)
        elif action in ('skip','clear','offered'):context=None
    copy_pref=quip_profile.resolve(saved_copy,command)
    recent_copy=list(recent)
    host_recent=envelope.get('recent_quips',[])
    if not isinstance(host_recent,list) or len(host_recent)>20 or any(not isinstance(x,str) or len(x)>100 for x in host_recent):raise ValueError('recent_quips需最多20条简短原句')
    recent_copy += [{'person_id':person,'record_id':'host-recent-'+str(i),'quip':x} for i,x in enumerate(host_recent)]
    group=profile.resolve(saved_profile,envelope.get('adult_group'),envelope.get('adult_group_correction') is True)
    mixed_reference=envelope.get('dolphin_mixed_reference')
    if mixed_reference not in (None,'freestyle'):raise ValueError('dolphin_mixed_reference仅接受freestyle或省略')
    rating['dolphin']=assess(r,group,envelope.get('hundred_m_context'),mixed_as_freestyle=mixed_reference=='freestyle')
    copy_result=select_quip(r,recent_copy,person,copy_pref,context,override_quip,envelope.get('quip_tone'))
    visual=choose(r,rating,recent,person,include_quip=False)
    if decoration is not None:
        allowed={(ASSETS/x['path']).resolve():x for x in load_library()['poses'] if x.get('qa_approved') and x.get('goggles') is False and x['level']==visual['level']}
        if Path(decoration).resolve() not in allowed:raise ValueError('只能使用本级已验收动物素材，禁止真人和线条替代')
        visual['decoration_path']=str(Path(decoration).resolve())
        actual=allowed[Path(decoration).resolve()];verify_pose(actual);visual['pose_id']=actual['id'];visual['pose_exact_state_match']=visual['state'] in actual['tags']
    visual.update(copy_result);quip=visual['quip']
    output=Path(out);output.mkdir(parents=True,exist_ok=True);artifacts={};layout=None
    for scale,name in ([(1,'today-phone.png')] if phone_only else [(1,'today-phone.png'),(2,'today-full.png')]):
        image,layout=render(r,rating,quip,scale,font,font_index,visual['decoration_path'])
        image.save(output/name,optimize=True);artifacts[name]={'path':str((output/name).resolve()),'bytes':(output/name).stat().st_size}
    saved=False;version=state['ledger_version'];presentation_version=display['version']
    if not no_save and d['status']!='partial':
        bind_owner(ledger,person);result=ingest(r,ledger,state['ledger_version'])
        if result['status']!='ready':raise ValueError(result.get('message','保存未确认'))
        saved=result['saved'];version=result['ledger_version'];readback=read_ledger(ledger)
        assert any(x['record_id']==result['record']['record_id'] for x in readback['records'])
        item={k:visual[k] for k in ['person_id','record_id','level','state','pose_id','quip_id','quip']}
        item.update({k:visual[k] for k in ['quip_family','quip_joke','quip_context_token']})
        presentation_version=display_history.append(ledger,item,display['version'])
        if group is not None:profile.append(ledger,person,group,saved_profile['version'])
    if not no_save and mode=='real' and authorized and person=='self' and command is not None:
        bind_owner(ledger,person)
        try:copy_pref=quip_profile.append(ledger,person,copy_pref,saved_copy['version'])
        except (OSError,ValueError):
            (output/'report.json').write_text(json.dumps({'status':'preference_save_failed','saved':saved,'ledger_version':version,'persona_state':{'persisted':False,'status':'save_failed'},'no_save':no_save},ensure_ascii=False,indent=2),encoding='utf-8')
            raise
    diagnostics=([d['message']] if d['status']=='partial' else [])+rating.get('derived_warnings',[])
    metric_provenance={m['id']:{'kind':'calculated' if m['source']['image_id']=='calculated-from-confirmed-fields' else 'user_reported' if m['source']['image_id'].startswith('user-confirmed') else 'observed','source':m['source']} for m in r['metrics'] if m['status']=='confirmed'}
    report={'version':'1.2.15-rc.1+fresh-quips.20261108','rating':rating,'quip':quip,'presentation':visual,'layout':layout,'artifacts':artifacts,'dedup':d,'saved':saved,'ledger_version':version,'presentation_version':presentation_version,'person_id':person,'adult_group':group,'profile_version':profile.read(ledger,person)['version'] if not no_save and mode=='real' and authorized and d['status']!='partial' else saved_profile['version'],'image_review':review_result,'raw_record':r,'warnings':[],'internal_diagnostics':diagnostics,'no_save':no_save}
    report['metric_provenance']=metric_provenance
    report['persona_state']={'status':copy_pref['status'],'version':copy_pref['version'],'optional_prompt':copy_pref['status']=='unasked' and context is None,'persisted':mode=='real' and authorized and not no_save and person=='self' and command is not None}
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--ledger',required=True);p.add_argument('--output',required=True)
    p.add_argument('--no-save',action='store_true');p.add_argument('--phone-only',action='store_true',help='先出手机卡，不等待高清版本');p.add_argument('--decoration');p.add_argument('--font');p.add_argument('--font-index',type=int,default=0);a=p.parse_args()
    try:
        result=execute(json.loads(Path(a.input).read_text(encoding='utf-8-sig')),a.ledger,a.output,a.no_save,a.decoration,a.font,a.font_index,phone_only=a.phone_only)
        print(json.dumps({k:result[k] for k in ['version','rating','quip','saved','ledger_version','artifacts','warnings']},ensure_ascii=False));return 0
    except (ValueError,OSError,KeyError,AssertionError,TypeError) as error:
        print(json.dumps({'status':'failed','message':str(error),'save_not_confirmed':True},ensure_ascii=False));return 1

if __name__=='__main__':sys.exit(main())
