"""Adult 100 m timing reference; a personal comparison, never a certificate."""
from pathlib import Path
import json,math,re

TABLE=json.loads((Path(__file__).resolve().parents[1]/'references/dolphin-100m.json').read_text(encoding='utf-8'))
PROMPT='上传完整配速截图，分析更准确；也可以直接告诉我最快100米成绩。'

def _paired(record):
    if record.get('pool_length_m')!=50:return None
    by_index={}
    for lap in record.get('segments') or []:
        index=lap.get('segment_index')
        if isinstance(index,int) and not isinstance(index,bool) and index>0:
            by_index.setdefault(index,[]).append(lap)
    total=record.get('distance_m',0)
    expected=int(total//50) if isinstance(total,(int,float)) and total>0 else 0
    valid={}
    for index,rows in by_index.items():
        if index>expected:continue
        # Identical cross-image observations are one lap; conflicts invalidate this lap only.
        signatures={(s.get('distance_m'),s.get('duration_s'),s.get('time_basis'),s.get('includes_rest'),s.get('stroke'),s.get('pool_length_m',50)) for s in rows}
        s=rows[0];duration=s.get('duration_s')
        if (len(signatures)==1 and s.get('distance_m')==50
            and isinstance(duration,(int,float)) and not isinstance(duration,bool) and math.isfinite(duration) and duration>0
            and s.get('time_basis')=='active' and s.get('includes_rest') is not True
            and s.get('pool_length_m',50)==50
            and (s.get('stroke')==record.get('stroke') or record.get('stroke')=='mixed' and s.get('stroke') in ('freestyle','breaststroke','backstroke','butterfly'))):valid[index]=s
    pairs=[{'lap_indices':[i,i+1],'seconds':valid[i]['duration_s']+valid[i+1]['duration_s'],
                'lap_seconds':[valid[i]['duration_s'],valid[i+1]['duration_s']],
                'rest_status':'explicitly_excluded' if all(valid[j].get('includes_rest') is False for j in (i,i+1)) else 'not_reported',
                'timing_interpretation':'sum_of_reported_contiguous_lap_times'}
           for i in range(1,expected,2) if i in valid and i+1 in valid and valid[i].get('stroke')==valid[i+1].get('stroke')]
    if pairs:
        best=min(pairs,key=lambda p:p['seconds'])
        covered=[i for p in pairs for i in p['lap_indices']]
        return {'seconds':best['seconds'],'source':'paired_50m_segments','pairing':'fixed_nonoverlapping_from_first_lap',
                'lap_indices':best['lap_indices'],'lap_seconds':best['lap_seconds'],
                'rest_status':best['rest_status'],'timing_interpretation':best['timing_interpretation'],
                'pair_seconds':[p['seconds'] for p in pairs],'verified_pairs':pairs,
                'covered_lap_indices':covered,'expected_laps':expected,
                'unverified_lap_indices':[i for i in range(1,expected+1) if i not in covered],
                'coverage':len(covered)/expected,'fastest_scope':'verified_pairs_only' if len(covered)<expected else 'complete_session',
                'metric_ids':[]}
    return None

def fastest(record,evidence_context=None,diagnostics=None):
    """Compare all current-session complete 100m evidence; never accept a history list."""
    if record.get('stroke') in ('unknown',None):return None
    context=evidence_context or {}
    if not isinstance(context,dict):raise ValueError('hundred_m_context需按指标ID映射')
    candidates=[];excluded=[];conflicts=[]
    if diagnostics is not None:diagnostics.update(excluded_evidence=excluded,conflicts=conflicts)
    groups={}
    for segment in record.get('segments') or []:
        index=segment.get('segment_index')
        if isinstance(index,int) and not isinstance(index,bool):groups.setdefault(index,[]).append(segment)
    conflict_indices=set()
    for index,rows in groups.items():
        signatures={(row.get('distance_m'),row.get('duration_s'),row.get('time_basis'),row.get('includes_rest'),row.get('stroke',record.get('stroke')),row.get('pool_length_m',record.get('pool_length_m'))) for row in rows}
        if len(signatures)>1:
            conflict_indices.add(index)
            conflicts.append({'type':'segment_observation_conflict','segment_index':index,'observations':rows})
            excluded.append({'evidence_id':'segment:'+str(index),'reason':'conflicting_segment_observations'})
    def scoped(item,key):
        meta=context.get(key,{})
        if not isinstance(meta,dict) or set(meta)-{'person_id','record_id','session_date','stroke','lap_indices','scope'}:raise ValueError('百米来源上下文字段无效')
        for name in ('person_id','record_id','session_date','stroke'):
            if name in meta and meta[name]!=record.get(name,'self' if name=='person_id' else None):
                excluded.append({'evidence_id':key,'reason':'different_'+name,'context':meta});return False
        if meta.get('scope','current_session')!='current_session':
            excluded.append({'evidence_id':key,'reason':'not_current_session','context':meta});return False
        return True
    for m in record.get('metrics',[]):
        if not (m.get('key')=='fastest_100m' and m.get('qualifier')=='best' and m.get('status')=='confirmed' and m.get('scope')=='complete_100m' and m.get('unit')=='s'):continue
        text=' '.join([m.get('label',''),str(m.get('raw_value','')),m.get('source',{}).get('region','')])
        negative_rest=r'不包含休息(?:时间)?|未包含休息(?:时间)?|不包括休息(?:时间)?|未包括休息(?:时间)?|不含休息(?:时间)?|未含休息(?:时间)?|无休息|not including rest|excluding rest|without rest'
        rest_excluded=bool(re.search(negative_rest,text,re.I))
        rest_text=re.sub(negative_rest,'',text,flags=re.I)
        if m.get('time_basis')=='elapsed' or re.search(r'包括休息|包含休息|含休息|含暂停|including rest|with rest|elapsed',rest_text,re.I):
            excluded.append({'evidence_id':m['id'],'reason':'elapsed_or_explicit_rest','source':m.get('source')});continue
        dates=re.findall(r'\d{4}-\d{2}-\d{2}',text)
        if re.search(r'历史|个人最佳|个人最好|生涯|personal best|all.time|\bPB\b|\bPR\b',text,re.I) or any(d!=record.get('session_date') for d in dates):
            excluded.append({'evidence_id':m['id'],'reason':'historical_or_other_date','source':m.get('source')});continue
        if not scoped(m,m['id']):continue
        value=m.get('value')
        if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0:
            candidates.append({'seconds':value,'source':'screenshot_or_user_confirmed','metric_ids':[m['id']],
                               'origin':m.get('source'),'context':context.get(m['id'],{}),'rest_status':'explicitly_excluded' if rest_excluded else 'not_reported'})
    for i,s in enumerate(record.get('segments') or []):
        duration=s.get('duration_s');key='segment:'+str(s.get('segment_index',i+1))
        if s.get('segment_index') in conflict_indices:continue
        if (s.get('distance_m')==100 and isinstance(duration,(int,float)) and not isinstance(duration,bool) and math.isfinite(duration) and duration>0
            and s.get('time_basis')=='active' and s.get('includes_rest') is not True
            and (s.get('stroke',record['stroke'])==record['stroke'] or record['stroke']=='mixed' and s.get('stroke') in ('freestyle','breaststroke','backstroke','butterfly','mixed'))
            and scoped(s,key)):
            candidates.append({'seconds':duration,'source':'complete_100m_segment','metric_ids':[],
                               'segment_index':s.get('segment_index'),'rest_status':'explicitly_excluded' if s.get('includes_rest') is False else 'not_reported'})
    current_record={**record,'segments':[s for i,s in enumerate(record.get('segments') or []) if s.get('segment_index') not in conflict_indices and scoped(s,'segment:'+str(s.get('segment_index',i+1)))]}
    paired=_paired(current_record)
    if paired:
        for pair in paired['verified_pairs']:
            candidates.append({**paired,**pair})
    if not candidates:return None
    best=min(candidates,key=lambda item:item['seconds'])
    declared=[c for c in candidates if c['source']=='screenshot_or_user_confirmed']
    for c in declared:
        if c['seconds']>best['seconds']:
            conflicts.append({'type':'reported_best_slower_than_verified_complete_100m','metric_ids':c['metric_ids'],
                              'reported_seconds':c['seconds'],'verified_best_seconds':best['seconds'],'source':c.get('origin')})
    if len({c['seconds'] for c in declared})>1:conflicts.append({'type':'reported_best_disagreement','metric_ids':[m for c in declared for m in c['metric_ids']]})
    result=dict(best)
    result.update(evidence_candidates=[{k:v for k,v in c.items() if k in ('seconds','source','metric_ids','origin','context','segment_index','lap_indices','lap_seconds','rest_status')} for c in candidates],
                  conflicts=conflicts,excluded_evidence=excluded,comparison_scope={'person_id':record.get('person_id','self'),'record_id':record.get('record_id'),'session_date':record.get('session_date'),'stroke':record['stroke']},
                  selection_rule='minimum_of_valid_current_session_complete_100m')
    return result

def assess(record,group,evidence_context=None,*,mixed_as_freestyle=False):
    if not isinstance(mixed_as_freestyle,bool):raise ValueError('mixed_as_freestyle需布尔值')
    diagnostics={}
    evidence=fastest(record,evidence_context,diagnostics)
    base={'level':'待评','color':'neutral','seconds':None,'score_text':'待提供','reference_only':True,'source':None,'prompt':PROMPT}
    if evidence is None:
        base.update(diagnostics);return base
    seconds=evidence['seconds'];seconds_text=f'{int(seconds%60):02d}' if seconds==int(seconds) else f'{seconds%60:04.1f}'
    base.update(seconds=seconds,score_text=f"{int(seconds//60)}′{seconds_text}″",source=evidence['source'],prompt=None)
    for field in ('pairing','lap_indices','lap_seconds','rest_status','timing_interpretation','pair_seconds','verified_pairs','covered_lap_indices','expected_laps','unverified_lap_indices','coverage','fastest_scope','evidence_candidates','conflicts','excluded_evidence','comparison_scope','selection_rule'):
        if field in evidence:base[field]=evidence[field]
    if record.get('stroke')=='mixed' and not mixed_as_freestyle:
        base.update(reference_basis='mixed_reference_not_authorized');return base
    reference_stroke='freestyle' if record.get('stroke')=='mixed' else record.get('stroke')
    if record.get('stroke')=='mixed':base.update(reference_stroke='freestyle',reference_basis='user_requested_mixed_as_freestyle',reference_note='按用户指定采用成人自由泳计时阈值作娱乐参考；不是正式混合泳认证')
    if group not in ('male','female') or reference_stroke not in TABLE['thresholds']:return base
    for level,limit in TABLE['thresholds'][reference_stroke][group].items():
        if seconds<=limit:
            base.update(level=level+'海豚',color=TABLE['colors'][level],prompt=None);return base
    base.update(level='未达计时档',color='neutral',prompt=None)
    return base
