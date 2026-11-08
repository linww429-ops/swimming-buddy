"""Deterministic entertainment estimates. No physiology or distribution quota."""
from decimal import Decimal, ROUND_HALF_UP
from statistics import median, pstdev, mean
import math
from legacy_records import comparable, pace

DIMENSIONS=['续航输出','强度投入','节奏稳定','技术经济性','恢复从容度']
CONTEXT_KEYS={'subjective_effort','subjective_feedback','pre_session_intent','post_session_feeling','post_session_final_phase_feeling','post_session_final_effort','discomfort_feedback','discomfort_flag_semantics','device_model','swolf_basis'}

def half(value):
    return float((Decimal(str(value))*2).quantize(Decimal('1'),rounding=ROUND_HALF_UP)/2)

def band(stars):return max(1,min(5,int(stars+.5)))

def metric(record,key,qualifier='average'):
    values=[m['value'] for m in record.get('metrics',[]) if m['key']==key and m['qualifier']==qualifier and m['status']=='confirmed' and (key in CONTEXT_KEYS or m.get('scope','session') in ('session','single_session','全程'))]
    if not values:return None
    if key in CONTEXT_KEYS:return values[-1]
    return values[0] if len(set(values))==1 else None

def context(record):
    whole=' '.join(str(m['value']) for m in record.get('metrics',[]) if m['key'] in {'post_session_feeling','subjective_feedback'} and m['status']=='confirmed' and m['value'] is not None)
    final=' '.join(str(m['value']) for m in record.get('metrics',[]) if m['key'] in {'post_session_final_phase_feeling','post_session_final_effort'} and m['status']=='confirmed' and m['value'] is not None)
    tags=[]
    if any(t in whole for t in ['轻松','放松','easy','relaxed']) and not any(t in whole for t in ['不轻松','不放松','not easy','not relaxed']):tags.append('easy')
    if any(t in whole for t in ['疲劳','很累','fatigued','tired']):tags.append('fatigued')
    if any(t in final for t in ['冲刺','sprint']):tags.append('final_sprint')
    if record.get('discomfort') is True:tags.append('discomfort')
    return tags

def richness(record):
    keys={m['key'] for m in record.get('metrics',[]) if m['status']=='confirmed' and m['value'] is not None and m['key'] not in CONTEXT_KEYS and m.get('scope','session') in ('session','single_session','全程')}
    technical=len(keys & {'swolf','stroke_count','stroke_rate'})
    measured=len(keys & {'distance','time','pace','calories','heart_rate','swolf','stroke_count','stroke_rate','lengths'})
    core=all(record.get(k) is not None for k in ['distance_m','durations','time_basis']) and record.get('stroke') not in (None,'unknown','mixed') and record.get('pool_length_m') is not None
    return bool(core and technical>=2 and measured>=6)

def cohort(record,history):
    # Volume/time effort can differ in distance; pace/economy still use close-distance comparable().
    r=record
    rows=[old for old in history if old.get('person_id','self')==r.get('person_id','self') and old.get('mode')==r.get('mode') and old['record_id']!=r.get('record_id') and old['session_date']<r.get('session_date','') and old['stroke']==r.get('stroke') and r.get('stroke') not in ('unknown','mixed',None) and old['pool_length_m']==r.get('pool_length_m') and r.get('pool_length_m') is not None and old['time_basis']==r.get('time_basis') and old['source']['scope']=='single_session' and old.get('discomfort') is not True and old.get('intent')!='recovery']
    return sorted(rows,key=lambda x:(x['session_date'],x.get('start_time_local') or x.get('start_time') or ''),reverse=True)[:5]

def clamp_score(value):return half(max(1,min(5,value)))

def interpolate(value, anchors):
    if value<=anchors[0][0]:return anchors[0][1]
    for (x0,y0),(x1,y1) in zip(anchors,anchors[1:]):
        if value<=x1:return y0+(y1-y0)*(value-x0)/(x1-x0)
    return anchors[-1][1]

def positive(value):return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0

def grade(record,history,overrides=None,feeling=None):
    has_core=all(record.get(k) for k in ['session_date','distance_m','durations','time_basis'])
    baseline=cohort(record,history) if has_core else []
    close=comparable(record,history)[:5] if has_core else []
    valid=[m for m in record.get('metrics',[]) if m.get('status')=='confirmed' and positive(m.get('value')) and m.get('key') not in CONTEXT_KEYS|{'pool_length','session_date','start_time'}]
    if not valid and not positive(record.get('distance_m')) and not any(positive(v) for v in (record.get('durations') or {}).values()):
        raise ValueError('no_valid_activity_data')
    scores={d:3.0 for d in DIMENSIONS};evidence={d:'基于本次有效运动记录的中性评价起点' for d in DIMENSIONS};inputs={}
    tags=context(record)
    # Explicit fixed scale requested by the user; independent of recent workload.
    distance=record.get('distance_m')
    if positive(distance):
        scores['续航输出']=clamp_score(interpolate(distance,[(0,1),(300,1.5),(500,2),(750,2.5),(1000,3),(1200,3.5),(1500,4),(2000,4.5),(3000,5)]))
        evidence['续航输出']='固定距离投入尺：1000米3星、1200米3.5星、1500米4星；锚点线性插值取半星，非能力标准'
    # Heart rate is a declared entertainment input, not a physiological zone.
    hr=metric(record,'heart_rate');hr_score=None
    if positive(hr) and 40<=hr<=220:
        old_hr=[metric(x,'heart_rate') for x in baseline if x['source']['app']==record.get('source',{}).get('app')]
        old_hr=[v for v in old_hr if positive(v) and 40<=v<=220]
        if len(old_hr)>=3:
            hr_score=max(1,min(5,3+(hr-median(old_hr))/15))
            evidence['强度投入']='平均心率相对本人同来源近次中位数的娱乐投入代理'
        else:
            hr_score=interpolate(hr,[(40,1),(100,1.5),(120,2),(140,3),(160,4),(180,5),(220,5)])
            evidence['强度投入']='平均心率的固定娱乐刻度；不使用年龄/最大心率推算或心率区间诊断'
        scores['强度投入']=clamp_score(hr_score);inputs['average_heart_rate']=hr;inputs['heart_rate_proxy']=hr_score
    # Explicit after-session language only; avoid treating pre-session intent as feedback.
    whole=' '.join(str(m['value']) for m in record.get('metrics',[]) if m['key'] in {'post_session_feeling','subjective_feedback'} and m['status']=='confirmed')
    breathing=' '.join(str(m['value']) for m in record.get('metrics',[]) if m['key'] in {'post_session_breathing','post_session_rhythm'} and m['status']=='confirmed')
    easy=('easy' in tags);hard=any(t in whole for t in ['高强度','很吃力','非常吃力','high intensity','hard effort'])
    subjective=2.0 if easy else (4.5 if hard else None)
    if subjective is not None:
        scores['强度投入']=clamp_score(subjective if hr_score is None else .75*subjective+.25*hr_score)
        if easy:scores['强度投入']=min(2.5,scores['强度投入'])
        evidence['强度投入']='本人游后体感占75%、平均心率娱乐代理占25%；缺心率仅用体感，明确轻松不超过2.5星'
    if 'final_sprint' in tags:
        scores['强度投入']=clamp_score(scores['强度投入']+.5)
        evidence['强度投入']+='；明确末段冲刺小幅加0.5星，不当成全程冲刺'
    # A contiguous visible majority supports provisional stability, never invent missing laps.
    segments=record.get('segments') or [];ids=[s.get('segment_index') for s in segments]
    coherent=(record.get('stroke') not in ('mixed','unknown',None) and len(segments)>=3 and all(isinstance(i,int) for i in ids)
        and sorted(ids)==list(range(min(ids),max(ids)+1)) and len(set(ids))==len(ids)
        and all(s.get('time_basis')=='active' and not s.get('includes_rest',False) and positive(s.get('distance_m')) and positive(s.get('duration_s'))
        and s.get('stroke',record.get('stroke'))==record.get('stroke') and s.get('pool_length_m',record.get('pool_length_m'))==record.get('pool_length_m') for s in segments))
    coverage=sum(s.get('distance_m',0) for s in segments)/distance if positive(distance) else 0
    active_gap=abs(sum(s['duration_s'] for s in segments)-(record.get('durations') or {}).get('active_s',0))
    rounding_slack=.5*len(segments)+1 if all(type(s.get('duration_s')) is int for s in segments) else 1
    full=coherent and ids==list(range(1,len(ids)+1)) and math.isclose(coverage,1,abs_tol=.0001) and positive((record.get('durations') or {}).get('active_s')) and active_gap<=rounding_slack
    partial=coherent and .5<=coverage<1
    if full or partial:
        values=[s['duration_s']*100/s['distance_m'] for s in segments];cv=pstdev(values)/mean(values)
        score=4.5 if cv<=.04 else 4 if cv<=.08 else 3.5 if cv<=.15 else 3 if cv<=.25 else 2.5
        scores['节奏稳定']=min(4,score) if partial else score
        evidence['节奏稳定']=('完整分段' if full else f'可见连续分段覆盖{coverage:.0%}，保守暂估上限4星')+'的配速离散；不补缺失分段'
        if full and active_gap>1:evidence['节奏稳定']+=f'；逐段整数秒合计与全程差{active_gap:g}秒，在取整容差内，娱乐暂估'
        inputs['pace_cv']=cv;inputs['segment_coverage']=coverage;inputs['segment_active_gap_s']=active_gap
    rhythmic=any(t in breathing for t in ['呼吸稳定','呼吸顺畅','节奏稳定','轻松','平稳','steady','easy'])
    disrupted=any(t in breathing for t in ['呼吸乱','节奏乱','不稳定','吃力','喘不过','unstable'])
    if disrupted:
        scores['节奏稳定']=clamp_score((scores['节奏稳定']+2)/2) if full or partial else 2.5
        evidence['节奏稳定']+='；本人明确报告呼吸/节奏不稳'
    elif rhythmic or easy:
        if not (full or partial):scores['节奏稳定']=3.5
        evidence['节奏稳定']+='；本人呼吸/节奏顺畅或轻松体感作为保守补充'
    # Cadence x pace combines both signals; no arm/cycle conversion or medical inference.
    rate=metric(record,'stroke_rate');p=metric(record,'pace')
    if p is None and positive(distance) and positive((record.get('durations') or {}).get('active_s')):p=record['durations']['active_s']*100/distance
    if record.get('stroke')=='freestyle' and positive(rate) and positive(p) and 10<=rate<=80 and 60<=p<=300:
        product=rate*p/60;inputs['cadence_pace_product']=product
        older=[]
        for old in close:
            rr=metric(old,'stroke_rate');pp=metric(old,'pace')
            if old['source']['app']==record.get('source',{}).get('app') and positive(rr) and positive(pp):older.append(rr*pp/60)
        if len(older)>=3:
            scores['技术经济性']=clamp_score(3+4*(median(older)/product-1))
            evidence['技术经济性']='同泳姿同来源可比训练的划频×配速组合相对本人中位数；不把低划频单独判为技术好'
        else:
            scores['技术经济性']=4 if product<=32 else 3.5 if product<=44 else 3 if product<=58 else 2.5 if product<=75 else 2
            evidence['技术经济性']='自由泳划频×配速组合的宽档娱乐代理（≤32/44/58/75对应4/3.5/3/2.5，否则2）；计数定义不明，不称实际每100米划数或绝对效率'
    for axis,value in (overrides or {}).items():
        if axis not in DIMENSIONS or isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<=value<=5:raise ValueError('五维娱乐评分需0–5且名称正确')
        scores[axis]=clamp_score(value);evidence[axis]='宿主有据的当次娱乐维度评分；原始证据留在报告'
    # Numeric self-report is authoritative; easy language still overrides host-only guesses.
    if subjective is not None:
        scores['强度投入']=clamp_score(subjective if hr_score is None else .75*subjective+.25*hr_score)
        if easy:scores['强度投入']=min(2.5,scores['强度投入'])
        if 'final_sprint' in tags:scores['强度投入']=clamp_score(scores['强度投入']+.5)
        evidence['强度投入']='本人游后体感优先；心率仅作25%娱乐辅助'
    if feeling is None:feeling=metric(record,'subjective_effort','unspecified')
    if feeling is not None:
        if isinstance(feeling,bool) or not isinstance(feeling,(int,float)) or not 1<=feeling<=5:raise ValueError('主观投入需1–5星')
        scores['强度投入']=half(feeling);evidence['强度投入']='本人明确主观投入优先，只确定投入轴及其反向娱乐轴'
    scores['恢复从容度']=half(6-scores['强度投入']);evidence['恢复从容度']='娱乐映射：6－强度投入；非恢复心率、恢复能力或生理验证值'
    aggregate_axes=DIMENSIONS[:]
    average=sum(scores[d] for d in aggregate_axes)/5
    provenance={d:{'kind':'inferred','basis':evidence[d]} for d in DIMENSIONS}
    for axis in (overrides or {}):
        if scores[axis]==clamp_score(overrides[axis]):provenance[axis]={'kind':'inferred','basis':'宿主根据本次记录提交的维度评价','value':scores[axis]}
    if feeling is not None:provenance['强度投入']={'kind':'user_rating','basis':'当次明确运动强度评级','value':scores['强度投入']}
    provenance['恢复从容度']={'kind':'inferred','basis':evidence['恢复从容度'],'depends_on':'强度投入'}
    # Explicit discomfort has final precedence over host estimates and self-ratings.
    # Keep original reports in record.metrics, but do not reward exertion or diagnose.
    if record.get('discomfort') is True:
        safety_basis='明确报告不适，安全优先采用中性娱乐评价；不奖励强度，不作健康诊断；原始主观反馈保留'
        scores={d:3.0 for d in DIMENSIONS}
        evidence={d:safety_basis for d in DIMENSIONS}
        provenance={d:{'kind':'inferred','basis':safety_basis,'value':3.0,'safety_neutral':True} for d in DIMENSIONS}
        average=3.0
        inputs['discomfort_safety_neutral']=True
    return {'dimensions':scores,'mean':average,'stars':max(1,min(5,half(average))),'basis_count':len(baseline),'basis_record_ids':[x['record_id'] for x in baseline],'pace_basis_record_ids':[x['record_id'] for x in close],'provisional':len(baseline)<5,'evidence':evidence,'inputs':inputs,'kind':'entertainment','layout_mode':'rich','mean_basis':'five_dimension_evaluation_mean','aggregate_axes':aggregate_axes,'dimension_provenance':provenance,'state_tags':tags or ['normal'],'strategy_version':'1.2.11','distribution_quota':False}
