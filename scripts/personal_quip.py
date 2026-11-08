"""Validate a freshly host-authored line; never generate or select canned copy."""
import hashlib
import json
import re


def grams(text):
    s = re.sub(r'[\W\d_]+', '', text)
    return {s[i:i+3] for i in range(max(0, len(s)-2))}


def similar(a, b):
    x, y = grams(a), grams(b)
    return a == b or bool(x and y and len(x & y)/min(len(x), len(y)) > .45)


def validate_authored_quip(text):
    if text is None:
        raise ValueError('missing_authored_quip: 请结合本次数据和本人实际体感现场创作quip；不再自动选模板')
    if (not isinstance(text, str) or not text.strip() or len(text) > 45
            or any(ord(c) < 32 or ord(c) == 127 for c in text)):
        raise ValueError('invalid_authored_quip: 现场锐评需为不超过45字的简短单行')
    return text.strip()


def select(record, recent, person, preference, context=None, override=None, tone=None):
    text = validate_authored_quip(override)
    if tone not in (None, 'playful', 'gentle', 'care'):
        raise ValueError('quip_tone仅接受playful/gentle/care或省略')
    if record.get('discomfort') is True and tone != 'care':
        raise ValueError('care_authored_quip_required: 本人明确不适时，请现场写关怀语并设置quip_tone=care，不鼓励硬撑')
    rid = record.get('record_id', 'unknown')
    relevant = [x for x in recent if x.get('person_id') == person
                and x.get('record_id') != rid][-6:]
    if any(similar(text, x.get('quip', '')) for x in relevant):
        raise ValueError('repeated_authored_quip: 与本人近期点评相似，请换一个基于本次事实的笑点重写')
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:12]
    payload = json.dumps({'record': record, 'preference': preference,
                          'context': context}, ensure_ascii=False, sort_keys=True)
    return {
        'quip': text, 'quip_id': 'authored-' + digest,
        'quip_family': 'host_authored', 'quip_joke': digest,
        'quip_context_token': hashlib.sha256(payload.encode('utf-8')).hexdigest()[:12],
        'quip_generation_mode': 'host_authored', 'template_fallback': False,
        'quip_tone': tone or (context or preference).get('humor', 'playful'),
    }
