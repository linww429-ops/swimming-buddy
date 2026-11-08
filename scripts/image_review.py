"""Host-vision review evidence, not an OCR or proof of visual completeness."""
def review(envelope):
    record=envelope['record']
    expected=set(record.get('source',{}).get('library_file_ids',[]))
    checklist=envelope.get('image_review')
    if checklist is None:
        return {'status':'legacy_unattested','expected_images':sorted(expected),
                'note':'No host review checklist supplied; this does not claim all images were read.'}
    if not isinstance(checklist,list):raise ValueError('image_review需逐图清单')
    listed={}
    for item in checklist:
        if not isinstance(item,dict) or not isinstance(item.get('image_id'),str):raise ValueError('逐图清单需来源身份')
        if item['image_id'] in listed:raise ValueError('逐图清单来源重复')
        if item.get('reviewed') is not True:raise ValueError('仍有图片未完整查看')
        if not isinstance(item.get('regions'),list) or not item['regions'] or any(not isinstance(s,str) or not s.strip() for s in item['regions']):raise ValueError('需列出每图已查看区域')
        if not isinstance(item.get('unreadable_regions',[]),list):raise ValueError('遮挡区域需单独列出')
        listed[item['image_id']]=item
    if expected-set(listed):raise ValueError('逐图清单遗漏已提供图片')
    if set(listed)-expected:raise ValueError('逐图清单出现未知来源')
    metrics=record.get('metrics',[])
    # Cross-image confirmed readings with the same meaning must agree.
    grouped={}
    for m in metrics:
        source=m.get('source',{}).get('image_id')
        if source not in expected or m.get('status')!='confirmed':continue
        key=(m['key'],m['qualifier'],m.get('scope','session'),m.get('unit'),m.get('time_basis'))
        for prior in grouped.get(key,[]):
            if prior['source']['image_id']!=source and prior['value']!=m['value']:
                raise ValueError('跨图同口径指标冲突：'+m['key']+'；保留原文并确认该项')
        grouped.setdefault(key,[]).append(m)
    return {'status':'host_attested','images':[dict(item,metric_ids=[m['id'] for m in metrics if m.get('source',{}).get('image_id')==image_id]) for image_id,item in listed.items()],
            'note':'Host attestation only; all raw labels, values, units and source regions remain in raw_record.'}
