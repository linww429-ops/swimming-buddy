"""Lossless screenshot observations: preserve labels, values, units and sources."""
import copy
import math
import re

QUALIFIERS = {
    'calories': {'active', 'total', 'unspecified'},
    'swolf': {'average', 'best', 'unspecified'},
    'heart_rate': {'average', 'max', 'min', 'unspecified'},
    'pace': {'average', 'best', 'unspecified'},
    'time': {'active', 'elapsed', 'rest', 'unspecified'},
    'stroke_count': {'total', 'per_length', 'unspecified'},
    'stroke_rate': {'average', 'max', 'unspecified'},
    'distance': {'total', 'unspecified'},
    'pool_length': {'unspecified'},
    'lengths': {'total', 'unspecified'},
    'laps': {'total', 'unspecified'},
    'stroke': {'unspecified'},
    'session_date': {'unspecified'},
    'start_time': {'unspecified'},
    'fastest_100m': {'best'},
}
UNITS = {'calories': 'kcal', 'swolf': 'score', 'heart_rate': 'bpm', 'pace': 's/100m', 'time': 's', 'stroke_count': 'count', 'stroke_rate': 'spm', 'distance': 'm', 'pool_length': 'm', 'lengths': 'count', 'laps': 'count', 'fastest_100m':'s'}
ALLOWED_UNITS={k:{v} for k,v in UNITS.items()}
ALLOWED_UNITS['pace']={'s/100m','s/100yd','s/unknown'}
ALLOWED_UNITS['calories']={'kcal','kJ','cal'}

def validate_metrics(metrics):
    if not isinstance(metrics, list) or len(metrics) > 200:
        raise ValueError('metrics 需为不超过200项的截图指标列表')
    result = copy.deepcopy(metrics)
    ids = set()
    for item in result:
        fields = {'id', 'key', 'qualifier', 'label', 'raw_value', 'raw_unit', 'value', 'unit', 'time_basis', 'status', 'source'}
        if not isinstance(item, dict) or not fields<=set(item) or set(item)-fields-{'scope'}:
            raise ValueError('每项指标需完整保留 id/key/qualifier/label/raw_value/raw_unit/value/unit/time_basis/status/source')
        if not isinstance(item['id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', item['id']) or item['id'] in ids:
            raise ValueError('指标id无效或重复')
        ids.add(item['id'])
        if 'scope' in item and (not isinstance(item['scope'],str) or not 1<=len(item['scope'])<=100):
            raise ValueError('指标scope需为保留原范围的非空字符串')
        if not isinstance(item['key'], str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', item['key']):
            raise ValueError('指标key需为小写字段名；未知游泳指标也可用扩展key保留')
        for name, limit in [('qualifier', 80), ('label', 200), ('raw_value', 1500), ('raw_unit', 100), ('unit', 100)]:
            if not isinstance(item[name], str) or len(item[name]) > limit:
                raise ValueError(f'指标{name}无效')
        if not item['label'].strip() or not item['qualifier'] or item['status'] not in ('confirmed', 'uncertain', 'missing') or item['time_basis'] not in (None, 'active', 'elapsed', 'unspecified'):
            raise ValueError('指标标签、口径或确认状态无效')
        if item['key'] in QUALIFIERS and item['qualifier'] not in QUALIFIERS[item['key']]:
            raise ValueError('指标平均/最佳、活动/总量等口径不正确')
        if item['key'] == 'time' and item['qualifier'] in ('active', 'elapsed') and item['time_basis'] != item['qualifier']:
            raise ValueError('指标时间口径不一致')
        if item['key'] == 'pace' and item['time_basis'] is None:
            raise ValueError('配速指标需明确active/elapsed/unspecified口径')
        value = item['value']
        if item['status'] != 'confirmed':
            if value is not None:
                raise ValueError('模糊或缺失的指标value必须为null；原文保留在raw_value中')
        elif item['key'] in UNITS:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 10**7 or item['unit'] not in ALLOWED_UNITS[item['key']] or not item['raw_value'].strip():
                raise ValueError('已确认指标需有数值、原文及正确规范单位')
        elif value is not None and (isinstance(value, bool) or not isinstance(value, (str, int, float)) or isinstance(value, (int, float)) and not math.isfinite(value)):
            raise ValueError('扩展指标value需为数值、文字或null')
        source = item['source']
        if not isinstance(source, dict) or set(source) != {'image_id', 'region', 'image_sha256'} or any(not isinstance(source[k], str) or not 1 <= len(source[k]) <= 200 for k in ('image_id', 'region')):
            raise ValueError('每项指标需保留来源图标识与区域')
        if source['image_sha256'] is not None and (not isinstance(source['image_sha256'], str) or not re.fullmatch('[a-f0-9]{64}', source['image_sha256'])):
            raise ValueError('指标来源图指纹无效')
    return result

def merge_metrics(old, new):
    result = copy.deepcopy(old)
    indexed = {item['id']: item for item in result}
    for item in new:
        if item['id'] in indexed:
            if indexed[item['id']] != item:
                raise ValueError('同一来源指标id的原始数据有冲突，请确认；已有值未覆盖')
        else:
            result.append(copy.deepcopy(item))
            indexed[item['id']] = item
    return validate_metrics(result)

def metric_view(record):
    rows = []
    signatures = {}
    values = {}
    for item in record['metrics']:
        identity = (item['key'], item['qualifier'], item['time_basis'], item['unit'])
        if item['status'] == 'confirmed' and item['value'] is not None:
            values.setdefault(identity, set()).add(item['value'])
        signature = (item['key'], item['qualifier'], item['time_basis'], item['label'], item['raw_value'], item['raw_unit'], item['status'])
        if signature in signatures:
            signatures[signature]['ids'].append(item['id'])
            continue
        row = {**copy.deepcopy(item), 'ids': [item['id']], 'display_status': item['status']}
        signatures[signature] = row
        rows.append(row)
    for row in rows:
        identity = (row['key'], row['qualifier'], row['time_basis'], row['unit'])
        if len(values.get(identity, ())) > 1:
            row['display_status'] = 'conflict'
    focus = {}
    for key, qualifiers in [('calories', ('active', 'total', 'unspecified')), ('swolf', ('average', 'best', 'unspecified'))]:
        found = next((row for qualifier in qualifiers for row in rows if row['key'] == key and row['qualifier'] == qualifier), None)
        if found is None:
            found = {'ids': [], 'label': '消耗热量' if key == 'calories' else 'SWOLF', 'raw_value': '', 'raw_unit': '', 'display_status': 'missing'}
        elif found['display_status'] == 'conflict':
            found = {**found, 'ids': [], 'raw_value': '', 'raw_unit': ''}
        focus[key] = found
    consumed = {i for row in focus.values() for i in row['ids']}
    groups = []
    for title, keys in [('泳池与训练', {'distance', 'time', 'pace', 'pool_length', 'stroke', 'lengths', 'laps', 'session_date', 'start_time'}), ('消耗与效率', {'calories', 'swolf'}), ('心率与划水', {'heart_rate', 'stroke_count', 'stroke_rate'}), ('还有这些', None)]:
        items = [row for row in rows if not consumed.intersection(row['ids']) and (row['key'] in keys if keys is not None else row['key'] not in QUALIFIERS)]
        if items:
            groups.append({'title': title, 'items': items})
    return {'focus': focus, 'groups': groups, 'observation_count': len(record['metrics'])}

def raw_text(row):
    raw = row.get('raw_value', '') + (' ' + row['raw_unit'] if row.get('raw_unit') else '')
    if row['display_status'] == 'missing':
        return '未提供'
    if row['display_status'] in ('uncertain', 'conflict'):
        return '待确认' + (' · ' + raw if raw.strip() else '')
    return raw or '未提供'

def demo_metrics(active_s=2535, elapsed_s=2820):
    def clock(s):
        s = round(s)
        return f'{s // 60}:{s % 60:02d}'
    specs = [
        ('distance', 'total', '距离', '1,500', '米', 1500, 'm', None),
        ('time', 'active', '运动时间', clock(active_s), '', active_s, 's', 'active'),
        ('time', 'elapsed', '总用时', clock(elapsed_s), '', elapsed_s, 's', 'elapsed'),
        ('pace', 'average', '平均配速', clock(active_s / 15), '/100米', round(active_s / 15), 's/100m', 'active'),
        ('pace', 'best', '最快配速', '2:31', '/100米', 151, 's/100m', 'unspecified'),
        ('calories', 'active', '活动热量', '420', '千卡', 420, 'kcal', None),
        ('calories', 'total', '总热量', '486', '千卡', 486, 'kcal', None),
        ('swolf', 'average', '平均 SWOLF', '43', '', 43, 'score', None),
        ('swolf', 'best', '最佳 SWOLF', '36', '', 36, 'score', None),
        ('heart_rate', 'average', '平均心率', '132', '次/分', 132, 'bpm', None),
        ('heart_rate', 'max', '最高心率', '156', '次/分', 156, 'bpm', None),
        ('stroke_count', 'total', '划水次数', '980', '次', 980, 'count', None),
        ('stroke_rate', 'average', '平均划频', '24.8', '次/分', 24.8, 'spm', None),
        ('lengths', 'total', '泳池趟数', '60', '趟', 60, 'count', None),
        ('pool_length', 'unspecified', '泳池长度', '25', '米', 25, 'm', None),
        ('stroke', 'unspecified', '泳姿', '自由泳', '', 'freestyle', '', None),
        ('training_effect', 'aerobic', '有氧训练效果', '2.7', '', 2.7, 'score', None),
    ]
    return [{'id': f'demo-{key}-{qualifier}', 'key': key, 'qualifier': qualifier, 'label': label, 'raw_value': raw, 'raw_unit': raw_unit, 'value': value, 'unit': unit, 'time_basis': basis, 'status': 'confirmed', 'source': {'image_id': 'synthetic-data-page', 'region': '泳训概览', 'image_sha256': None}} for key, qualifier, label, raw, raw_unit, value, unit, basis in specs]
