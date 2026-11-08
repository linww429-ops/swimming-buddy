"""Swimming Buddy: private local records, comparison and deduplication."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
import os
import re
import statistics
import uuid
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from swim_metrics import demo_metrics, merge_metrics, metric_view, validate_metrics

VERSION = '1.0.0'
ROOT = Path(__file__).resolve().parent
STROKES = {'freestyle': '自由泳', 'breaststroke': '蛙泳', 'backstroke': '仰泳', 'butterfly': '蝶泳', 'mixed': '混合泳姿', 'unknown': '泳姿未确认'}
UNCERTAIN_ALIASES = {'active_s': 'durations.active_s', 'elapsed_s': 'durations.elapsed_s'}
UNCERTAIN_FIELDS = {'session_date', 'distance_m', 'durations', 'durations.active_s', 'durations.elapsed_s', 'time_basis', 'stroke', 'pool_length_m', 'start_time', 'start_time_local', 'source', 'source.app', 'source.scope', 'source.session_key', 'segments'}

class InputError(ValueError):
    pass

def number(value, label, minimum=1, maximum=10**7):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise InputError(f'{label}需要是 {minimum}–{maximum} 之间的数值')

def enum(value, choices, label):
    if not isinstance(value, str) or value not in choices:
        raise InputError(f'{label}不正确')

def normalize_uncertain(fields, metric_ids=()):
    if not isinstance(fields, list) or any(not isinstance(f, str) for f in fields):
        raise InputError('模糊字段列表不正确')
    fields = [UNCERTAIN_ALIASES.get(f, f) for f in fields]
    unknown = set(fields) - UNCERTAIN_FIELDS - {'metrics.' + i for i in metric_ids}
    if unknown:
        raise InputError('未知模糊字段：' + ', '.join(sorted(unknown)))
    return sorted(set(fields))

def comparison_uncertain(r):
    return bool(set(normalize_uncertain(r['uncertain_fields'], [m['id'] for m in r.get('metrics', [])])) & {'stroke', 'pool_length_m', 'session_date', 'distance_m', 'durations', 'time_basis', 'source', 'source.scope', 'durations.' + r['time_basis'] + '_s'})

def validate(record):
    """Validate the trust boundary; unknown comparison metadata is allowed."""
    if not isinstance(record, dict):
        raise InputError('记录必须是对象')
    required = {'schema_version', 'record_id', 'mode', 'session_date', 'date_source', 'distance_m', 'durations', 'time_basis', 'stroke', 'pool_length_m', 'intent', 'discomfort', 'source', 'uncertain_fields', 'segments'}
    if required - record.keys():
        raise InputError('缺少字段：' + ', '.join(sorted(required - record.keys())))
    if record.keys() - (required | {'start_time', 'start_time_local', 'metrics','person_id'}):
        raise InputError('未知字段：' + ', '.join(sorted(record.keys() - required - {'start_time', 'start_time_local', 'metrics'})))
    r = copy.deepcopy(record)
    if 'person_id' in r and (not isinstance(r['person_id'],str) or not 1<=len(r['person_id'])<=100):
        raise InputError('person_id需为不超过100字符的身份标识')
    try:
        r['metrics'] = validate_metrics(r.get('metrics', []))
    except ValueError as error:
        raise InputError(str(error)) from error
    if r['schema_version'] != VERSION:
        raise InputError('记录版本或数据模式不正确')
    enum(r['mode'], {'real', 'demo'}, '数据模式')
    if not isinstance(r['record_id'], str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', r['record_id']):
        raise InputError('record_id 不正确')
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', r['session_date']):
            raise ValueError()
        date.fromisoformat(r['session_date'])
    except (ValueError, TypeError):
        raise InputError('泳训日期需要明确到 YYYY-MM-DD，不能用上传日期代替')
    enum(r['date_source'], {'screenshot', 'user_confirmed'}, '日期来源（需截图或用户确认）')
    if r.get('start_time_local') is not None:
        try:
            local = datetime.fromisoformat(r['start_time_local'])
            if local.tzinfo is not None or local.date().isoformat() != r['session_date']:
                raise ValueError()
        except (ValueError, TypeError):
            raise InputError('截图本地开始时间需无时区且与泳训日期一致；不猜时区')
    if r.get('start_time') is not None:
        try:
            start = datetime.fromisoformat(r['start_time'])
            if start.tzinfo is None or start.date().isoformat() != r['session_date']:
                raise ValueError()
        except (ValueError, TypeError):
            raise InputError('开始时间需含时区且与泳训日期一致')
    number(r['distance_m'], '距离', maximum=100000)
    if not isinstance(r['durations'], dict) or not r['durations'] or r['durations'].keys() - {'active_s', 'elapsed_s'}:
        raise InputError('用时需要明确运动用时或总用时')
    for key, value in r['durations'].items():
        number(value, key, maximum=86400)
    if set(r['durations']) == {'active_s', 'elapsed_s'} and r['durations']['active_s'] > r['durations']['elapsed_s']:
        raise InputError('运动用时不能超过总用时，请核对截图')
    enum(r['time_basis'], {'active', 'elapsed'}, '用时口径')
    if r['time_basis'] + '_s' not in r['durations']:
        raise InputError('配速使用的用时口径缺失')
    enum(r['stroke'], STROKES, '泳姿')
    if r['pool_length_m'] is not None:
        number(r['pool_length_m'],'池长',minimum=1,maximum=500)
    enum(r['intent'], {'normal', 'hard', 'recovery', 'unspecified'}, '训练意图')
    if r['discomfort'] is not None and not isinstance(r['discomfort'], bool):
        raise InputError('训练意图或不适反馈不正确')
    s = r['source']
    if not isinstance(s, dict) or not {'app', 'scope', 'session_key', 'image_sha256'} <= set(s) or set(s) - {'app', 'scope', 'session_key', 'image_sha256', 'library_file_ids'}:
        raise InputError('截图来源结构不正确')
    if 'library_file_ids' in s and (not isinstance(s['library_file_ids'], list) or len(s['library_file_ids']) > 20 or any(not isinstance(x, str) or not re.fullmatch(r'libfile_[A-Za-z0-9_-]+', x) for x in s['library_file_ids'])):
        raise InputError('来源Library身份不正确')
    if not isinstance(s['app'], str) or len(s['app']) > 80:
        raise InputError('截图来源或汇总范围不正确')
    enum(s['scope'], {'single_session', 'daily_summary', 'unknown'}, '汇总范围')
    if s['session_key'] is not None and (not isinstance(s['session_key'], str) or not 1 <= len(s['session_key']) <= 100):
        raise InputError('来源训练编号不正确')
    hashes = s['image_sha256']
    if not isinstance(hashes, list) or len(hashes) > 20 or any(not isinstance(h, str) or not re.fullmatch('[a-f0-9]{64}', h) for h in hashes):
        raise InputError('截图指纹不正确')
    s['image_sha256'] = list(dict.fromkeys(hashes))
    r['uncertain_fields'] = normalize_uncertain(r['uncertain_fields'], [m['id'] for m in r['metrics']])
    uncertain = set(r['uncertain_fields'])
    for metric in r['metrics']:
        if 'metrics.' + metric['id'] in uncertain:
            metric['status'] = 'uncertain'
            metric['value'] = None
        if metric.get('scope','session') not in ('session','single_session','全程'):
            continue
        core = None
        if metric['key'] == 'distance' and metric['qualifier'] in ('total', 'unspecified'):
            core = ('distance_m', r['distance_m'])
        elif metric['key'] == 'time' and metric['qualifier'] in ('active', 'elapsed'):
            field = metric['qualifier'] + '_s'
            if field in r['durations']:
                core = ('durations.' + field, r['durations'][field])
        elif metric['key'] in ('stroke', 'pool_length'):
            field = 'stroke' if metric['key'] == 'stroke' else 'pool_length_m'
            core = (field, r[field])
        elif metric['key'] == 'session_date':
            core = ('session_date', r['session_date'])
        if core:
            field, value = core
            if metric['status'] == 'uncertain':
                uncertain.add(field)
            elif metric['status'] == 'confirmed' and value not in (None, 'unknown') and metric['value'] != value:
                raise InputError(f'截图原始指标与结构化{field}不一致，请确认；原始值未丢弃')
    r['uncertain_fields'] = sorted(uncertain)
    if uncertain & {'session_date', 'distance_m', 'durations', 'time_basis', 'source', 'source.scope', 'durations.' + r['time_basis'] + '_s'}:
        raise InputError('关键值模糊，请只确认日期、距离、用时或是否单次训练中对应的一项')
    if 'stroke' in uncertain:
        r['stroke'] = 'unknown'
    if 'pool_length_m' in uncertain:
        r['pool_length_m'] = None
    if 'start_time' in uncertain:
        r['start_time'] = None
    if 'start_time_local' in uncertain:
        r['start_time_local'] = None
    if uncertain & {'source.app', 'source.session_key'}:
        s['session_key'] = None
    if r['segments'] is not None:
        if not isinstance(r['segments'], list) or len(r['segments']) > 2000:
            raise InputError('分段数据不正确')
        for seg in r['segments']:
            required_seg={'distance_m','duration_s','time_basis'}
            optional_seg={'segment_index','stroke_count','stroke_count_basis','stroke','pool_length_m','includes_rest'}
            if not isinstance(seg, dict) or not required_seg<=set(seg) or set(seg)-required_seg-optional_seg:
                raise InputError('分段需明确距离、用时与口径')
            number(seg['distance_m'], '分段距离', maximum=100000)
            number(seg['duration_s'], '分段用时', maximum=86400)
            enum(seg['time_basis'], {'active', 'elapsed'}, '分段用时口径')
            if 'segment_index' in seg and (isinstance(seg['segment_index'],bool) or not isinstance(seg['segment_index'],int) or seg['segment_index']<1):raise InputError('分段序号需为正整数')
            if 'stroke_count' in seg:
                if isinstance(seg['stroke_count'],bool) or not isinstance(seg['stroke_count'],int) or seg['stroke_count']<0 or seg.get('stroke_count_basis') not in ('arm_strokes','cycles','unknown'):raise InputError('划水次数及计数定义需同时明确')
            elif 'stroke_count_basis' in seg:raise InputError('没有分段划水次数时不能指定计数定义')
            if 'stroke' in seg:
                enum(seg['stroke'],STROKES,'分段泳姿')
                if r['stroke'] not in ('mixed','unknown') and seg['stroke']!=r['stroke']:raise InputError('分段泳姿与本次泳姿不一致')
            if 'pool_length_m' in seg and seg['pool_length_m']!=r['pool_length_m']:raise InputError('分段泳池长度与本次不一致')
            if 'includes_rest' in seg and not isinstance(seg['includes_rest'],bool):raise InputError('分段是否含休息需布尔值')
    if 'segments' in uncertain:
        r['segments'] = None
    return r

def seconds(r):
    return r['durations'][r['time_basis'] + '_s']

def pace(r):
    return seconds(r) * 100 / r['distance_m']

def clock(value):
    value = round(value)
    return f'{value // 60}:{value % 60:02d}'

def duplicates(r, records):
    if r['source']['scope'] != 'single_session':
        return {'status': 'needs_scope', 'message': '这是每日汇总还是一次泳训？请确认范围后再入账，避免与单次记录重叠。'}
    for old in records:
        if old['mode'] != r['mode']:
            continue
        same_hash = bool(set(old['source']['image_sha256']) & set(r['source']['image_sha256']))
        same_id = old['record_id'] == r['record_id']
        same_library = bool(set(old['source'].get('library_file_ids', [])) & set(r['source'].get('library_file_ids', [])))
        same_key = (r['source']['session_key'] is not None and old['source']['app'] == r['source']['app'] and old['source']['session_key'] == r['source']['session_key'] and old['session_date'] == r['session_date'])
        same_start = old.get('start_time') is not None and r.get('start_time') is not None and datetime.fromisoformat(old['start_time']) == datetime.fromisoformat(r['start_time'])
        if same_hash or same_id or same_library or same_key or same_start:
            incompatible = old['session_date'] != r['session_date'] or old['distance_m'] != r['distance_m'] or any(old['durations'][k] != r['durations'][k] for k in old['durations'].keys() & r['durations'].keys())
            incompatible |= old['stroke'] != 'unknown' and r['stroke'] != 'unknown' and old['stroke'] != r['stroke']
            incompatible |= old['pool_length_m'] is not None and r['pool_length_m'] is not None and old['pool_length_m'] != r['pool_length_m']
            if incompatible:
                return {'status': 'conflict', 'record_id': old['record_id'], 'message': '同一次训练的关键数值不一致，请确认；已有记录未覆盖。'}
            return {'status': 'duplicate', 'record_id': old['record_id'], 'message': '同一次泳训已记录；新截图可补充来源，不重复累计。'}
        near_start = old.get('start_time') and r.get('start_time') and abs((datetime.fromisoformat(old['start_time']) - datetime.fromisoformat(r['start_time'])).total_seconds()) <= 120
        timings_overlap = any(old['durations'][k] == r['durations'][k] for k in old['durations'].keys() & r['durations'].keys())
        different_basis = old['time_basis'] != r['time_basis']
        if old['session_date'] == r['session_date'] and old['distance_m'] == r['distance_m'] and (timings_overlap or different_basis) and (near_start or not (old.get('start_time') and r.get('start_time'))):
            return {'status': 'possible_duplicate', 'record_id': old['record_id'], 'message': '同日已有同距离且可能重叠的记录：这是同一次，还是两次不同泳训？请确认开始时间或训练编号。'}
    return {'status': 'new', 'message': '新记录'}

def merge(old, new):
    result = copy.deepcopy(old)
    try:
        result['metrics'] = merge_metrics(old.get('metrics', []), new.get('metrics', []))
    except ValueError as error:
        raise InputError(str(error)) from error
    uncertain = set(old['uncertain_fields']) | set(new['uncertain_fields'])
    for field in ('stroke', 'pool_length_m'):
        if field not in new['uncertain_fields'] and new.get(field) not in (None, 'unknown'):
            uncertain.discard(field)
    result['uncertain_fields'] = sorted(uncertain)
    result['durations'].update(new['durations'])
    result['source']['image_sha256'] = sorted(set(old['source']['image_sha256'] + new['source']['image_sha256']))
    if old['source'].get('library_file_ids') or new['source'].get('library_file_ids'):
        result['source']['library_file_ids'] = sorted(set(old['source'].get('library_file_ids', []) + new['source'].get('library_file_ids', [])))
    observations=[]
    for segment in (old.get('segments') or [])+(new.get('segments') or []):
        if segment not in observations:observations.append(copy.deepcopy(segment))
    result['segments']=observations if observations else (old.get('segments') if old.get('segments') is not None else new.get('segments'))
    for k in ('stroke', 'pool_length_m', 'start_time', 'start_time_local'):
        if result.get(k) in (None, 'unknown') and new.get(k) not in (None, 'unknown'):
            result[k] = new[k]
    flags=[old['discomfort'],new['discomfort']]
    result['discomfort'] = True if True in flags else False if False in flags else None
    if new['intent'] == 'recovery':
        result['intent'] = 'recovery'
    return validate(result)

def comparable(r, records):
    if comparison_uncertain(r) or r['stroke'] in {'unknown', 'mixed'} or r['pool_length_m'] is None:
        return []
    current = date.fromisoformat(r['session_date'])
    usable = [old for old in records if not comparison_uncertain(old) and old['record_id'] != r['record_id'] and old['mode'] == r['mode'] and old.get('person_id','self') == r.get('person_id','self') and old['source']['scope'] == 'single_session' and (old['session_date'] < r['session_date'] or (old['session_date'] == r['session_date'] and (old.get('start_time_local') or old.get('start_time') or '') < (r.get('start_time_local') or r.get('start_time') or '') and bool(old.get('start_time_local') or old.get('start_time')))) and old['stroke'] == r['stroke'] and old['pool_length_m'] == r['pool_length_m'] and old['time_basis'] == r['time_basis'] and 0.8 <= old['distance_m'] / r['distance_m'] <= 1.25 and not old['discomfort'] and old['intent'] != 'recovery']
    return sorted(usable, key=lambda item: (item['session_date'], item.get('start_time') or item.get('start_time_local') or ''), reverse=True)[:8]

def report(record, records=()):
    r = validate(record)
    history = []
    for old in records:
        try:
            history.append(validate(old))
        except InputError as error:
            raise InputError(f'历史记录 {old.get("record_id", "未编号") if isinstance(old, dict) else "未编号"}：{error}') from error
    d = duplicates(r, history)
    if d['status'] not in {'new', 'duplicate'}:
        return {'version': VERSION, 'status': d['status'], 'message': d['message'], 'dedup': d}
    if d['status'] == 'duplicate':
        r = merge(next(old for old in history if old['record_id'] == d['record_id']), r)
    baseline = comparable(r, history)
    n = len(baseline)
    stars = None
    delta = None
    base = None
    basis_label = '运动用时' if r['time_basis'] == 'active' else '总用时'
    if n >= 3:
        base = statistics.median(pace(old) for old in baseline)
        effort = 0.6 * seconds(r) / statistics.median(seconds(old) for old in baseline) + 0.4 * r['distance_m'] / statistics.median(old['distance_m'] for old in baseline)
        stars = 1 + sum(effort >= t for t in (0.65, 0.85, 1.15, 1.40))
        quips = {1: '轻装出勤，也算数。', 2: '悠着点，水照样划。', 3: '稳定上班，水里打卡。', 4: '今天给泳池加班了。', 5: '水里加班，记得下班。'}
        quip = quips[stars]
    else:
        quip = '先留一笔，慢慢熟悉你。'
    previous = baseline[0] if baseline else None
    earlier = sorted([old for old in history if old['mode'] == r['mode'] and old['record_id'] != r['record_id'] and old['session_date'] < r['session_date']], key=lambda old: (old['session_date'], old.get('start_time') or old.get('start_time_local') or ''), reverse=True)
    previous_label = '上次配速' if previous is None or not earlier or earlier[0]['record_id'] == previous['record_id'] else '上次同类配速'
    if previous:
        delta = pace(r) - pace(previous)
        comparison = f'快了 {abs(round(delta))} 秒' if delta < -0.5 else f'慢了 {abs(round(delta))} 秒' if delta > 0.5 else '这次差不多'
        chat = '今天比上次快了点，水里这班没白上。游完感觉怎么样？' if delta < -0.5 else '这次踏踏实实收工了，配速的单次波动先记着。游完感觉怎么样？'
    else:
        comparison = '积累中'
        chat = f'{r["distance_m"]:g} 米、{clock(seconds(r))} 收工，水里这班没白上。游完感觉怎么样？'
    if r['intent'] == 'recovery':
        stars = None
        quip = '恢复日，按计划下班。'
        chat = '恢复日也认真收工了，今天的配速先作记录。游完是松快了，还是仍有疲惫？'
    if r['discomfort']:
        stars = None
        quip = '今天，感受比成绩重要。'
        chat = '收到你说的不适了，今天先把感受放在成绩前面，不加拼劲评分。现在感觉怎么样？'
    raw_time = next((m['label'] for m in r['metrics'] if m['key'] == 'time' and m['qualifier'] == r['time_basis']), None)
    return {'version': VERSION, 'status': 'ready', 'record': r, 'dedup': d, 'title': '今日战报', 'distance': f'{r["distance_m"]:,.0f}', 'duration': clock(seconds(r)), 'pace': clock(pace(r)), 'basis_label': raw_time or basis_label, 'comparison': comparison, 'baseline_count': n, 'baseline_pace_s': base, 'baseline_pace_delta_s': pace(r) - base if base is not None else None, 'pace_delta_s': delta, 'previous_pace': clock(pace(previous)) if previous else None, 'previous_label': previous_label, 'previous_record_id': previous['record_id'] if previous else None, 'stars': stars, 'index_label': '感受优先' if r['discomfort'] else '恢复日 · 不评分' if r['intent'] == 'recovery' else f'{stars} / 5 星' if stars is not None else '积累中', 'quip': quip, 'chat': chat, 'metric_view': metric_view(r)}

def read_ledger(directory):
    path = Path(directory)
    files = sorted(path.glob('v[0-9][0-9][0-9][0-9][0-9][0-9].json')) if path.exists() else []
    if not files:
        return {'ledger_version': 0, 'records': []}
    obj = json.loads(files[-1].read_text(encoding='utf-8'))
    if obj['ledger_version'] != int(files[-1].stem[1:]):
        raise InputError('台账版本与文件名不一致')
    obj['records'] = [validate(r) for r in obj['records']]
    if any(r['mode'] != 'real' for r in obj['records']):
        raise InputError('真实台账含演示数据，停止读取')
    return obj

def ingest(record, directory, expected_version):
    r = validate(record)
    if r['mode'] != 'real':
        raise InputError('演示数据禁止写入真实台账')
    if type(expected_version) is not int or not 0 <= expected_version < 999999:
        raise InputError('预期台账版本需为非负整数且小于999999')
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / '.write.lock'
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise InputError('台账正在写入或存在待检查锁，请稍后重试')
    try:
        os.close(fd)
        ledger = read_ledger(directory)
        if ledger['ledger_version'] != expected_version:
            raise InputError(f'台账版本冲突：当前 {ledger["ledger_version"]}，预期 {expected_version}；未覆盖')
        result = report(r, ledger['records'])
        if result['status'] != 'ready':
            return result
        next_records = copy.deepcopy(ledger['records'])
        if result['dedup']['status'] == 'duplicate':
            index = next(i for i, old in enumerate(next_records) if old['record_id'] == result['record']['record_id'])
            if next_records[index] == result['record']:
                return {**result, 'ledger_version': expected_version, 'saved': False}
            next_records[index] = result['record']
        else:
            next_records.append(result['record'])
        version = expected_version + 1
        snapshot = {'schema_version': VERSION, 'ledger_version': version, 'records': next_records}
        # Immutable snapshots and a lock suit a one-user local ledger.
        with (directory / f'v{version:06d}.json').open('x', encoding='utf-8') as file:
            json.dump(snapshot, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        return {**result, 'ledger_version': version, 'saved': True}
    finally:
        lock.unlink()
