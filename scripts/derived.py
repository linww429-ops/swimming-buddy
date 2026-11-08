"""Conservative session derivations; original observations always win."""
import math
from energy import normalized as normalized_energy

def complete_metrics(record):
    warnings=[];rows=record.get('metrics',[])
    for energy in [m for m in rows if m['key']=='calories' and m['status']=='confirmed' and m['unit']=='cal']:
        warnings.append(f"{energy['label']}的cal口径未确认，不能擅自当千卡换算")
    energy_rows=[m for m in rows if m['key'] in ('calories','energy_kj') and normalized_energy(m) is not None]
    for i,one in enumerate(energy_rows):
        for two in energy_rows[i+1:]:
            if one['qualifier']==two['qualifier'] and one.get('scope','session')==two.get('scope','session') and abs(normalized_energy(one)-normalized_energy(two))>1.5:
                warnings.append('同一口径能量原值与换算值不一致，请核对；未覆盖任何原值')
    def add(key,qualifier,label,value,unit,raw_value,raw_unit,rule):
        existing=[m for m in rows if m['key']==key and m['qualifier']==qualifier and m['status']=='confirmed' and m.get('scope','session') in ('session','single_session','全程')]
        if existing:
            if any(m['unit']==unit and isinstance(m['value'],(int,float)) and not math.isclose(m['value'],value,rel_tol=.015,abs_tol=1) for m in existing):
                warnings.append(f'{label}：原读数与分段计算值不同，请核对；原读数未覆盖')
            return
        if len(rows)>=200:return
        rows.append({'id':'calculated-'+key+'-'+qualifier,'key':key,'qualifier':qualifier,'label':label,'raw_value':raw_value,'raw_unit':raw_unit,'value':value,'unit':unit,'time_basis':record.get('time_basis') if key=='pace' else None,'status':'confirmed','scope':'session','source':{'image_id':'calculated-from-confirmed-fields','region':rule,'image_sha256':None}})
    distance=record.get('distance_m');duration=(record.get('durations') or {}).get((record.get('time_basis') or '')+'_s')
    if distance and duration and not any(m['key']=='pace' and m['qualifier']=='average' and m['status']=='confirmed' for m in rows):
        seconds=duration*100/distance
        add('pace','average','平均配速（计算）',round(seconds,2),'s/100m',f"{int(seconds//60)}′{int(seconds%60):02d}″",'/100m','全程距离与同口径用时')
    segments=record.get('segments') or []
    if not segments:return warnings
    ids=[s.get('segment_index') for s in segments]
    if any(i is None for i in ids) or len(set(ids))!=len(ids) or sorted(ids)!=list(range(1,len(ids)+1)):
        warnings.append('分段序号不完整或重复，未合计划水/SWOLF');return warnings
    if not distance or not math.isclose(sum(s['distance_m'] for s in segments),distance,abs_tol=.01):
        warnings.append('分段距离未覆盖全程，未合计划水/SWOLF');return warnings
    known_strokes={'freestyle','breaststroke','backstroke','butterfly'}
    if record.get('stroke') not in known_strokes|{'mixed'}:
        warnings.append('泳姿未确认，保留原指标，暂不合计划水/SWOLF');return warnings
    if any(s.get('stroke',record.get('stroke')) not in known_strokes for s in segments):
        warnings.append('分段泳姿未明确，保留原指标，暂不合计划水/SWOLF');return warnings
    if any(s.get('includes_rest',False) or s['time_basis']!='active' or (record.get('stroke')!='mixed' and s.get('stroke',record.get('stroke'))!=record.get('stroke')) for s in segments):
        warnings.append('分段含休息或泳姿/用时口径不一致，未合计划水/SWOLF');return warnings
    if any(s.get('stroke_count_basis')!='arm_strokes' or 'stroke_count' not in s for s in segments):
        warnings.append('分段划水计数定义不统一，未合计划水/SWOLF');return warnings
    active=sum(s['duration_s'] for s in segments)
    known_active=(record.get('durations') or {}).get('active_s')
    if known_active is not None and not math.isclose(active,known_active,abs_tol=1):
        warnings.append('分段活动用时与全程运动时间冲突，未合计划水/SWOLF');return warnings
    count=sum(s['stroke_count'] for s in segments)
    add('stroke_count','total','总划水次数（计算）',count,'count',str(count),'次','完整互不重叠活动分段划水次数求和')
    if active>0:
        rate=round(count*60/active,1)
        add('stroke_rate','average','平均划频（计算）',rate,'spm',f'{rate:g}','次/分钟','完整活动分段划水总数/活动分钟')
    pool=record.get('pool_length_m')
    if pool and all(s['distance_m']/pool==int(s['distance_m']/pool) and s.get('pool_length_m',pool)==pool for s in segments):
        lengths=sum(s['distance_m']/pool for s in segments)
        swolf=round((active+count)/lengths,1)
        add('swolf','average','平均SWOLF（计算）',swolf,'score',f'{swolf:g}','分','Σ(活动秒数+同口径划水次数)/Σ完整趟数；混合泳为全程汇总，不作单一泳姿效率对照' if record.get('stroke')=='mixed' else 'Σ(活动秒数+同口径划水次数)/Σ完整趟数；不能反推逐趟SWOLF')
    else:warnings.append('分段不是同池长完整趟，未计算平均SWOLF')
    return warnings
