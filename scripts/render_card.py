from PIL import Image, ImageDraw, ImageFont
import math, hashlib, re, json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from legacy_records import STROKES, clock
from swim_metrics import raw_text
from rating import CONTEXT_KEYS,band
from energy import display as energy_display,normalized as normalized_energy
from sc_font import find_sc_font

def mean_text(value):
    return format(Decimal(str(value)).quantize(Decimal('0.1'),rounding=ROUND_HALF_UP),'.1f')

TEMPLATE={
    'version':'approved-phone-2026-10-13',
    'canvas':(1280,1840),
    'brand':'Swimming Buddy',
    'brand_xy':(65,51),
    'brand_size':39,
    'brand_cn':'泳搭子',
    'brand_cn_xy':(65,107),
    'brand_cn_size':28,
    'hero_value_size':100,
    'hero_unit_gap':12,
    'time_dividers':(454,845),
    'pace_unit_gap':12,
    'parameter_slots':tuple((657+(i%2)*278,858+(i//2)*167) for i in range(6)),
    'parameter_size':(259,148),
    'parameter_label_size':22,
    'parameter_value_size':28,
    'energy_value_size':28,
    'energy_unit_size':22,
    'parameter_value_offset':(22,83),
    'energy_wrapped_y':(73,111),
    'scale_line_y':1605,
    'scale_label_x':65,
    'scale_label_size':19,
    'scale_star_offset':16,
    'scale_name_offset':46,
}

def render(record, rating, quip, scale=1, font_path=None, font_index=0, decoration=None):
    if scale not in (1,2): raise ValueError('scale must be 1 or 2')
    font_path,font_index=find_sc_font(font_path,font_index)
    if decoration is None:
        from presentation import choose
        decoration=choose(record,rating)['decoration_path']
    rows=[m for m in record.get('metrics',[]) if m.get('status')=='confirmed' and m.get('value') is not None]
    def session_metric(m):return m.get('scope','session') in ('session','single_session','全程')
    def find(key,qualifier=None):return next((m for m in rows if m['key']==key and (qualifier is None or m['qualifier']==qualifier) and session_metric(m)),None)
    def display(m):
        if m['key']=='swolf' and m.get('status')=='confirmed' and isinstance(m.get('value'),(int,float)):return f"{m['value']:g}"
        text=energy_display(m) or raw_text({**m,'display_status':m.get('display_status',m['status'])})
        if m['key'] in ('distance','pool_length') and m.get('unit')=='m':text=text.replace('m','米')
        return text
    def raw(key,qualifier=None):
        m=find(key,qualifier);return display(m) if m else ''
    date_text=(record.get('start_time_local') or record.get('session_date','')).replace('T','  ').replace('-','.')[:17]
    swim_kind=raw('activity_type') or ('泳池游泳' if record.get('pool_length_m') else '')
    stroke=STROKES.get(record.get('stroke'),'') if record.get('stroke') not in (None,'unknown') else ''
    stroke_text=' · '.join(x for x in [swim_kind,stroke] if x)
    hero=find('distance','total')
    if hero is not None:hero_label=hero['label'];distance_text=hero['raw_value'];hero_unit=hero['raw_unit']
    elif record.get('distance_m') is not None:hero_label='距离';distance_text=f"{record['distance_m']:g}";hero_unit='米'
    else:
        hero=next((m for m in rows if m['status']=='confirmed' and session_metric(m) and m['key'] not in {'subjective_effort','subjective_feedback','stroke'}),None)
        hero_label=hero['label'] if hero else '泳训';distance_text=hero['raw_value'] if hero else '';hero_unit=hero['raw_unit'] if hero else ''
    if hero is not None and hero.get('unit')=='m' and hero_unit=='m':hero_unit='米'
    hero_label='运动强度评级' if hero is not None and (hero.get('key')=='effort' or hero.get('label','').lower()=='effort') else hero_label.replace('（计算）','')
    pool_text='泳池长度  '+raw('pool_length') if find('pool_length') else (f"泳池长度  {record['pool_length_m']:g}米" if record.get('pool_length_m') else '')
    lengths_text='趟数  '+raw('lengths') if find('lengths') else ''
    tm=find('time','active');time_label='运动时间'
    time_text=tm['raw_value'] if tm else clock(record['durations']['active_s']) if record.get('durations') and record['durations'].get('active_s') else ''
    pm=find('pace','average'); pace_label=pm['label'].replace('（计算）','') if pm else '';pace_text=pm['raw_value'] if pm else '';pace_unit=pm['raw_unit'] if pm else ''
    used=[find(k,q) for k,q in [('distance','total'),('pool_length',None),('lengths',None),('stroke',None),('time','active'),('start_time',None),('session_date',None),('pace','average')]]
    if hero is not None:used.append(hero)
    consumed={m['id'] for m in used if m is not None}
    selectable=[m for m in rows if session_metric(m) and m['status']=='confirmed' and m['value'] is not None and m['id'] not in consumed and m['key'] not in CONTEXT_KEYS|{'activity_type','fastest_100m'}]
    def priority(m):
        key,qualifier=m['key'],m['qualifier']
        if key in ('calories','energy_kj') and qualifier=='total':return 0
        if key in ('calories','energy_kj') and qualifier=='active':return 1
        if key=='heart_rate' and qualifier=='average':return 2
        if key=='stroke_count' and qualifier=='total':return 3
        if key=='stroke_rate' and qualifier=='average':return 4
        if key=='swolf' and qualifier=='average':return 5
        return 6
    selectable=sorted(selectable,key=priority)
    distinct=[]
    for m in selectable:
        if any(all(m.get(k)==prior.get(k) for k in ('key','qualifier','scope','value','unit','time_basis')) for prior in distinct):continue
        equivalent=any(m['key'] in ('calories','energy_kj') and prior['key'] in ('calories','energy_kj') and m['qualifier']==prior['qualifier'] and m.get('scope','session')==prior.get('scope','session') and normalized_energy(m) is not None and normalized_energy(prior) is not None and abs(normalized_energy(m)-normalized_energy(prior))<=Decimal('1.5') for prior in distinct)
        if not equivalent:distinct.append(m)
    selectable=distinct
    # Select by established priority, then keep average SWOLF last on the card.
    selected=selectable[:6]
    selected.sort(key=lambda m: m['key']=='swolf' and m['qualifier']=='average')
    selectable=selected+selectable[6:]
    def kind(m):return {'calories':'flame','heart_rate':'heart','stroke_count':'waves','stroke_rate':'bars'}.get(m['key'],'diamond')
    metrics=[(('运动强度评级' if m['key']=='effort' else m['label'])+(' · '+m['scope'] if m.get('scope','session') not in ('session','single_session','全程') else ''),display(m),kind(m)) for m in selectable]
    primary=metrics[:6];chosen=selectable[:6]
    level_name=['泡澡','老年蛙','养生游','认真做牛马','拉爆'][band(rating.get('mean',rating['stars']))-1]

    S=scale; W,H=TEMPLATE['canvas'][0],TEMPLATE['canvas'][1]
    im=Image.new('RGBA',(W*S,H*S),'#f8f8f0'); d=ImageDraw.Draw(im)
    navy='#103440';teal='#007c7e';muted='#627b7d';mint='#e7f2ea';grid='#b7ceca'
    def font(n,b=False):
     f=ImageFont.truetype(font_path,round(n*S*1.10),index=font_index)
     if hasattr(f,'get_variation_axes'):
      try:f.set_variation_by_axes([700 if b else 400])
      except OSError:pass
     return f
    overflow_fields=[]
    def shown(value,width,size,field,mode='label'):
     value=str(value);f=font(size,True)
     if f.getlength(value)<=width*S:return value
     overflow_fields.append(field)
     if mode=='value':return '详见报告'
     while value and f.getlength(value+'…')>width*S:value=value[:-1]
     return value+'…'
    def txt(x,y,t,n=26,c=navy,b=False,a='left'):
     f=font(n,b or (n>=22 and any('\u4e00'<=ch<='\u9fff' for ch in t)));bb=d.textbbox((0,0),t,font=f);tw=bb[2]-bb[0]
     if a=='center':x-=tw/S/2
     if a=='right':x-=tw/S
     d.text((round(x*S),round(y*S)),t,font=f,fill=c,anchor='lt')
    def line(p,c=grid,w=1):d.line([(round(x*S),round(y*S)) for x,y in p],fill=c,width=round(w*S))
    def rect(box,fill,r=28):d.rounded_rectangle(tuple(round(v*S) for v in box),radius=round(r*S),fill=fill)
    def poly(points,fill=None,outline=None,w=1):
     pts=[(round(x*S),round(y*S)) for x,y in points];d.polygon(pts,fill=fill)
     if outline: d.line(pts+[pts[0]],fill=outline,width=round(w*S),joint='curve')
    if decoration is None:
        from presentation import choose
        decoration=choose(record,rating)['decoration_path']
    decoration=Path(decoration)
    with Image.open(decoration) as source_asset:asset=source_asset.convert('RGBA')
    display_map=Path(__file__).resolve().parents[1]/'assets/animal-display-sizes.json'
    sizes=json.loads(display_map.read_text(encoding='utf-8'))[decoration.name]['display_sizes']
    asset=asset.resize(tuple(sizes[str(S)]),Image.Resampling.LANCZOS)
    im.alpha_composite(asset,(615*S,30*S))
    txt(*TEMPLATE['brand_xy'],TEMPLATE['brand'],TEMPLATE['brand_size'],b=True)
    txt(*TEMPLATE['brand_cn_xy'],TEMPLATE['brand_cn'],TEMPLATE['brand_cn_size'],c=muted)
    if record['mode']=='demo':txt(290,113,'演示数据',22,c=teal)
    txt(65,173,'今日战报',80,b=True);txt(69,279,date_text,32,c=muted)
    txt(69,329,shown(stroke_text,1140,29,'泳姿'),29,c=teal);line([(65,382),(1215,382)])
    txt(69,415,shown(hero_label,360,29,'主指标名称'),29,c=teal)
    hero_value_display=shown(distance_text,375,TEMPLATE['hero_value_size'],'主指标数值','value')
    hero_unit_display=shown(hero_unit,265,45,'主指标单位')
    txt(60,465,hero_value_display,TEMPLATE['hero_value_size'],b=True)
    value_bbox=d.textbbox((60*S,465*S),hero_value_display,font=font(TEMPLATE['hero_value_size'],True),anchor='lt')
    unit_bbox=d.textbbox((0,0),hero_unit_display,font=font(45,True),anchor='lt')
    hero_unit_x=(value_bbox[2]-unit_bbox[0])/S+TEMPLATE['hero_unit_gap']
    txt(hero_unit_x,528,hero_unit_display,45,c=teal,b=True)
    line([(770,458),(770,569)]);txt(808,470,pool_text,30,c=muted);txt(808,525,lengths_text,28,c=muted)
    rect((65,605,1215,735),mint)
    for divider in TEMPLATE['time_dividers']:line([(divider,630),(divider,711)],'#c6dcd2')
    txt(95,629,time_label if time_text else '',28,c=muted);txt(95,672,shown(time_text,330,42,'运动时间','value'),42,b=True)
    txt(487,629,(pace_label or '平均配速') if pace_text else '',28,c=muted);pace_render_text=shown(pace_text,225,42,'平均配速','value');txt(487,672,pace_render_text,42,b=True)
    pace_unit_display='/100米' if pace_unit in ('/100米','/100m') else pace_unit
    pace_unit_x=487+font(42,True).getlength(pace_render_text)/S+TEMPLATE['pace_unit_gap']
    if pace_unit_display:txt(pace_unit_x,693,shown(pace_unit_display,835-pace_unit_x,19,'配速单位'),19,c=muted)
    badge=rating.get('dolphin') or {'level':'待评','color':'neutral','score_text':'待提供','seconds':None,'reference_only':True}
    # Approved native vector dolphin: four cubic curves, fins, beak and tail.
    def bezier(a,b,c,e):
     return [((1-t)**3*a[0]+3*(1-t)**2*t*b[0]+3*(1-t)*t*t*c[0]+t**3*e[0],
              (1-t)**3*a[1]+3*(1-t)**2*t*b[1]+3*(1-t)*t*t*c[1]+t**3*e[1]) for t in [i/20 for i in range(21)]]
    shape=bezier((0,21),(21,-10),(50,-10),(70,9))
    shape+=bezier((70,9),(73,11),(79,10),(85,14))
    shape+=bezier((85,14),(76,19),(70,16),(66,21))
    shape+=bezier((66,21),(42,31),(20,23),(10,25))
    shape+=[(1,38),(0,26),(-12,25)]
    dolphin_color={'金海豚':'#b79835','银海豚':'#8a9ca0','粉海豚':'#d798a9','绿海豚':'#70a693','蓝海豚':'#6ea9be'}.get(badge['level'],'#6d9997')
    def dolphin_poly(ps):poly([(895+x*.78,641+y*.78) for x,y in ps],fill=dolphin_color)
    dolphin_poly(shape);dolphin_poly([(30,1),(29,-14),(46,1)])
    dolphin_poly([(41,22),(36,38),(54,24)])
    d.ellipse((round(947*S),round(648*S),round(950*S),round(651*S)),fill='#f8f8f0')
    txt(980,637,badge['level'],30,c=teal,b=True)
    best100_text=clock(badge['seconds']) if badge.get('seconds') is not None and badge['seconds']==int(badge['seconds']) else badge['score_text']
    best100_caption='最快100米配速 '+badge.get('score_text',best100_text)
    txt(876,698,best100_caption,18,c=muted)
    # Keep the approved geometry; omit only unavailable field content.
    badge_visible=badge.get('seconds') is not None and badge.get('level') not in (None,'待评')
    for available,box in [(bool(time_text),(85,620,444,726)),(bool(pace_text),(477,620,835,726)),(badge_visible,(856,620,1205,726))]:
        if not available:d.rectangle(tuple(round(v*S) for v in box),fill=mint)
    if badge.get('seconds') is not None and badge.get('level')=='待评':
        d.rectangle((975*S,628*S,1205*S,680*S),fill=mint)
    if not badge_visible:best100_caption=''
    # Five-axis FUN score radar, fixed 0–5; actual measurements in right column.
    rect((65,765,617,1395),mint)
    rect((637,765,1215,1395),'#e3eee7');txt(665,795,'本次参数',30,c=teal,b=True)
    txt(93,795,'维度评分',30,c=teal,b=True)
    scores=list(rating['dimensions'].values());mean=rating['mean'];display_rating=rating['stars']
    cx,cy,R=340,1080,112;angles=[math.radians(-90+72*i) for i in range(5)]
    def point(i,value):return(cx+R*value/5*math.cos(angles[i]),cy+R*value/5*math.sin(angles[i]))
    for level in [1,2,3,4,5]:poly([point(i,level) for i in range(5)],outline=grid,w=1)
    for i in range(5):line([(cx,cy),point(i,5)])
    pts=[point(i,v) for i,v in enumerate(scores)]
    ov=Image.new('RGBA',im.size,(0,0,0,0));od=ImageDraw.Draw(ov);od.polygon([(round(x*S),round(y*S)) for x,y in pts],fill=(11,184,179,100));im.alpha_composite(ov);d=ImageDraw.Draw(im)
    poly(pts,outline='#008b8d',w=3)
    for x,y in pts:
     d.ellipse(((x-6)*S,(y-6)*S,(x+6)*S,(y+6)*S),fill='#13bfc0',outline='#008b8d',width=2*S)
     d.ellipse(((x-2.7)*S,(y-2.7)*S,(x+2.7)*S,(y+2.7)*S),fill='#f8ffff')
    # Hide numeric radial tick labels; internal 0–5 scale unchanged.
    txt(340,872,'续航输出',26,c=muted,b=True,a='center');txt(340,909,f'{scores[0]:g}星',28,b=True,a='center')
    txt(530,1008,'强度投入',25,c=muted,b=True,a='center');txt(530,1046,f'{scores[1]:g}星',29,b=True,a='center')
    txt(451,1235,'节奏稳定',25,c=muted,b=True,a='center');txt(451,1273,f'{scores[2]:g}星',29,b=True,a='center')
    txt(225,1235,'技术经济性',25,c=muted,b=True,a='center');txt(225,1273,f'{scores[3]:g}星',29,b=True,a='center')
    txt(150,1008,'恢复从容度',25,c=muted,b=True,a='center');txt(150,1046,f'{scores[4]:g}星',29,b=True,a='center')
    # Six distinct icon/name/value cards. All source metrics retained.
    def icon(kind,x,y):
     d.ellipse(((x-18)*S,(y-18)*S,(x+18)*S,(y+18)*S),fill='#d4e9df')
     if kind=='heart':
      ps=[]
      for i in range(80):
       t=2*math.pi*i/80;xx=16*math.sin(t)**3;yy=13*math.cos(t)-5*math.cos(2*t)-2*math.cos(3*t)-math.cos(4*t)
       ps.append((x+xx*.65,y-yy*.65))
      poly(ps,outline=teal,w=2)
     elif kind=='flame':
      poly([(x,y-13),(x+9,y-1),(x+8,y+8),(x,y+12),(x-8,y+7),(x-9,y),(x-2,y-7),(x-3,y)],fill=teal)
     elif kind=='waves':
      for yy in [-6,1,8]:
       line([(x-12+j*.6,y+yy+2.5*math.sin(j*.25)) for j in range(41)],teal,2)
     elif kind=='bars':
      for i,h in enumerate([9,15,22]):rect((x-11+i*8,y+11-h,x-7+i*8,y+11),teal,2)
     else:
      poly([(x,y-12),(x+12,y),(x,y+12),(x-12,y)],outline=teal,w=2)
      line([(x-5,y),(x+5,y)],teal,2)
    energy_typography=[]
    def draw_energy(value,x,y,tile_w):
     match=re.fullmatch(r'(\d+) 千卡 / (\d+) kJ',str(value))
     if not match:return False
     a,b=match.groups();number_font=font(TEMPLATE['energy_value_size'],True);unit_font=font(TEMPLATE['energy_unit_size'],True)
     runs=[(a,number_font),(' 千卡 / ',unit_font),(b,number_font),(' kJ',unit_font)]
     width=sum(f.getlength(t) for t,f in runs)/S;available=tile_w-44
     # Fixed number/unit hierarchy. Wide dual-unit values wrap instead of shrinking.
     baseline_shift=-number_font.getbbox('0123456789',anchor='ls')[1]/S
     def draw_runs(runs,top):
      xx=(x+TEMPLATE['parameter_value_offset'][0])*S;yy=(y+top+baseline_shift)*S
      for text,face in runs:
       d.text((round(xx),round(yy)),text,font=face,fill=navy,anchor='ls');xx+=face.getlength(text)
     if width<=available:
      draw_runs(runs,TEMPLATE['parameter_value_offset'][1]);lines=1
     else:
      draw_runs([(a,number_font),(' 千卡 / ',unit_font)],TEMPLATE['energy_wrapped_y'][0])
      draw_runs([(b,number_font),(' kJ',unit_font)],TEMPLATE['energy_wrapped_y'][1]);lines=2
     energy_typography.append({'number_size':TEMPLATE['energy_value_size'],'unit_size':TEMPLATE['energy_unit_size'],'rendered_number_px':round(TEMPLATE['energy_value_size']*S*1.10),'rendered_unit_px':round(TEMPLATE['energy_unit_size']*S*1.10),'single_line_width':width,'available_width':available,'lines':lines,'auto_shrink':False})
     return True
    for i,(label,value,kind) in enumerate(primary):
     x,y=TEMPLATE['parameter_slots'][i]
     tile_w,tile_h=TEMPLATE['parameter_size']
     rect((x,y,x+tile_w,y+tile_h),'#f1f7ef',18)
     icon(kind,x+31,y+36)
     split_calc='（计算）' in label
     if split_calc:
      head=label.replace('（计算）','');txt(x+59,y+24,shown(head,tile_w-69,TEMPLATE['parameter_label_size'],'参数名称'),TEMPLATE['parameter_label_size'],c=muted,b=True)
     else:txt(x+59,y+24,shown(label,tile_w-69,TEMPLATE['parameter_label_size'],'参数名称'),TEMPLATE['parameter_label_size'],c=muted,b=True)
     is_energy=chosen[i]['key'] in ('calories','energy_kj')
     if not (is_energy and draw_energy(value,x,y,tile_w)):
      value_size=TEMPLATE['parameter_value_size']
      txt(x+22,y+(92 if split_calc else 83),shown(value,tile_w-44,value_size,'参数数值','value'),value_size,b=True)
    def star_points(x,y,r):return [(x+(r if i%2==0 else r*.44)*math.cos(math.radians(-90+36*i)),y+(r if i%2==0 else r*.44)*math.sin(math.radians(-90+36*i))) for i in range(10)]
    def stars(x,y,value,r=15,gap=38):
     for i in range(5):
      ps=star_points(x+i*gap,y,r);poly(ps,fill='#c1d2ca')
      fraction=max(0,min(1,value-i))
      if fraction==1:poly(ps,fill='#f58659')
      elif fraction>0:
       mask=Image.new('L',im.size);md=ImageDraw.Draw(mask);md.polygon([(round(a*S),round(b*S)) for a,b in ps],fill=255)
       md.rectangle(((x+i*gap-r+2*r*fraction)*S,(y-r-1)*S,(x+i*gap+r+1)*S,(y+r+1)*S),fill=0)
       im.paste('#f58659',(0,0,im.width,im.height),mask)
    
    rect((65,1420,1215,1550),'#dcede5');txt(93,1438,'牛马指数',44,c=teal,b=True);txt(93,1501,'五项均分 · '+level_name,23,c=muted)
    stars(642,1480,display_rating,31,66);txt(1188,1467,f'均分 {mean_text(mean)}星',26,c=teal,a='right')
    # Ordered named star scale; no fabricated performance thresholds.
    scale_y=TEMPLATE['scale_line_y']
    scale_label_height=font(TEMPLATE['scale_label_size']).getbbox('等级尺',anchor='lt')[3]/S
    scale_label_y=scale_y-scale_label_height/2
    txt(TEMPLATE['scale_label_x'],scale_label_y,'等级尺',TEMPLATE['scale_label_size'],c='#94aaa3')
    names=['泡澡','老年蛙','养生游','认真做牛马','拉爆'];centers=[178,408,638,868,1098]
    line([(178,scale_y),(1098,scale_y)],'#c9d7d0',1)
    for i,(x,name) in enumerate(zip(centers,names)):
     d.ellipse(((x-3)*S,(scale_y-3)*S,(x+3)*S,(scale_y+3)*S),fill='#9fb5ac')
     txt(x,scale_y+TEMPLATE['scale_star_offset'],f'{i+1}星',19,c='#8fa69d',a='center');txt(x,scale_y+TEMPLATE['scale_name_offset'],name,19,c='#8fa69d',a='center')
    txt(65,1718,shown(quip,1150,38,'当次锐评'),38,b=True)
    footer_text='泳后别忘了来根香蕉'
    bx=1185;by=1809
    # Fixed gently curved banana, after the reminder text.
    banana=bezier((0,2),(7,15),(22,16),(29,3))
    banana+=bezier((29,3),(21,9),(11,10),(3,0))
    poly([(bx+x,by+y) for x,y in banana],fill='#f2cf4a',outline='#d9b83b',w=1)
    line([(bx+2,by+1),(bx+1,by-1)],'#93835a',2)
    line([(bx+29,by+3),(bx+30,by+1)],'#93835a',2)
    txt(1178,1808,footer_text,16,c='#8b9290',a='right')
    return im.convert('RGB'), {'layout_mode':'rich','template_version':TEMPLATE['version'],'template_brand':TEMPLATE['brand'],'time_strip_dividers':list(TEMPLATE['time_dividers']),'pace_unit_x':pace_unit_x,'pace_unit_gap':TEMPLATE['pace_unit_gap'],'parameter_slots':[list(slot) for slot in TEMPLATE['parameter_slots']],'overflow_fields':overflow_fields,'dolphin_caption':best100_caption,'radar_drawn':True,'vertices':pts,'center':[cx,cy],'radius':R,'radial_min':0,'radial_max':5,'radial_tick_labels':False,'dimensions':rating['dimensions'],'dimension_mean':mean,'display_stars':display_rating,'scale_label_y':scale_label_y,'scale_label_height':scale_label_height,'scale_line_y':scale_y,'energy_typography':energy_typography,'parameter_label_size':TEMPLATE['parameter_label_size'],'parameter_value_size':TEMPLATE['parameter_value_size'],'displayed_metric_count':len(primary),'displayed_metric_ids':[m['id'] for m in chosen],'font_family':font(24).getname()[0],'decoration_kind':'rendered_animal','decoration_sha256':hashlib.sha256(decoration.read_bytes()).hexdigest(),'decoration_is_personal_tracking':False,'dolphin':badge,'banana_footer':True,'banana_position':'after_text','banana_shape_version':'gentle-curve-v1','display_units':'米','calculation_suffix_visible':False,'demo_label_visible':record['mode']=='demo','hero_unit_x':hero_unit_x,'hero_unit_gap':TEMPLATE['hero_unit_gap']}
