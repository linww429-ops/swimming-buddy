"""All business fixtures are synthetic; every render entry uses no_save=True."""
import copy,json,os,tempfile,unittest
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
from PIL import Image,ImageFont
from legacy_records import validate,duplicates,merge
from rating import DIMENSIONS,half,grade,richness
from run import prepare,execute,owner_check
from presentation import choose,load_library
from render_card import render,TEMPLATE
from dolphin import assess,fastest,PROMPT
import profile
from derived import complete_metrics
from energy import display as energy_display,normalized as normalized_energy
from sc_font import find_sc_font

BASE=Path(__file__).resolve().parents[1]

class SkillTests(unittest.TestCase):
    def require_font(self):
        try:find_sc_font()
        except ValueError as exc:self.skipTest(str(exc))
    def setUp(self):
        self.e=json.loads((BASE/'references/synthetic.json').read_text(encoding='utf-8'))
        self.r=copy.deepcopy(self.e['record']);self.e.pop('dimensions');self.r['discomfort']=None;self.e['record']['discomfort']=None
    def history(self,n,person='self'):
        rows=[]
        for i in range(n):
            r=copy.deepcopy(self.r);r['record_id']=f'synthetic-history-{i}';r['person_id']=person
            r['session_date']=(date(2030,1,8)-timedelta(days=i+1)).isoformat();r['start_time']=None;r['start_time_local']=None
            rows.append(r)
        return rows
    def feedback(self,r,key,text):
        m=copy.deepcopy(r['metrics'][-1]);m.update(id='synthetic-'+key,key=key,qualifier='unspecified',label='主观反馈',raw_value=text,raw_unit='',value=text,unit='',scope='after_session');r['metrics'].append(m)
    def render_entry(self,e):
        self.require_font()
        with tempfile.TemporaryDirectory() as t:
            result=execute(e,Path(t)/'ledger',Path(t)/'out',no_save=True)
            self.assertFalse(result['saved']);self.assertFalse((Path(t)/'ledger').exists())
            with Image.open(Path(t)/'out/today-phone.png') as im:self.assertEqual(im.width,1280);im.verify()
            with Image.open(Path(t)/'out/today-full.png') as im:self.assertEqual(im.width,2560);im.verify()
            return result
    def test_half_rounding_ties_up(self):self.assertEqual([half(v) for v in [3.24,3.25,3.74,3.75]],[3,3.5,3.5,4])
    def test_rich_mean_arithmetic(self):
        # 1.2.9: all five displayed axes contribute; recovery remains 6 - effort.
        g=grade(self.r,[],dict(zip(DIMENSIONS,[4,3,3.5,4.5,4])));self.assertEqual(g['mean'],3.6);self.assertEqual(g['stars'],3.5);self.assertEqual(g['dimensions']['恢复从容度'],3)

    def test_half_star_native_pixels(self):
        self.require_font()
        g=grade(self.r,[],{d:3.5 for d in DIMENSIONS});im,_=render(self.r,g,'今天这班不卷，只把自己游顺了。')
        self.assertEqual(im.getpixel((830,1480)),(245,134,89));self.assertEqual(im.getpixel((850,1480)),(193,210,202))
    def test_five_reference_sufficient(self):
        g=grade(self.r,list(reversed(self.history(7))));self.assertEqual(g['basis_record_ids'],[f'synthetic-history-{i}' for i in range(5)]);self.assertFalse(g['provisional'])
    def test_two_reference_provisional(self):g=grade(self.r,self.history(2));self.assertTrue(g['provisional']);self.assertEqual(g['basis_count'],2)
    def test_incompatible_pool_stroke_time(self):
        h=self.history(3);h[0]['pool_length_m']=25;h[1]['stroke']='breaststroke';h[2]['time_basis']='elapsed';h[2]['durations']={'elapsed_s':1890}
        self.assertEqual(grade(self.r,h)['basis_count'],0)
    def test_other_person_excluded(self):self.assertEqual(grade(self.r,self.history(5,'other'))['basis_count'],0)
    def test_new_user_self_contained(self):
        e=copy.deepcopy(self.e);e['person_id']='synthetic-new-owner';e['history']=self.history(5)
        result=self.render_entry(e);self.assertEqual(result['rating']['basis_count'],0);self.assertEqual(result['raw_record']['person_id'],'synthetic-new-owner')
    def test_owner_binding_refuses_cross_person(self):
        with tempfile.TemporaryDirectory() as t:
            (Path(t)/'.owner.json').write_text('{"person_id":"synthetic-owner-a"}',encoding='utf-8')
            with self.assertRaises(ValueError):owner_check(t,'synthetic-owner-b')
    def test_demo_never_reads_real_ledger_or_calls_ingest(self):
        with patch('run.read_ledger',side_effect=AssertionError('must not read')),patch('run.ingest',side_effect=AssertionError('must not save')):self.render_entry(self.e)
    def test_no_save_has_no_presentation_history(self):
        with patch('display_history.append',side_effect=AssertionError('must not persist')):self.render_entry(self.e)
    def test_no_unauthorized_write(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):execute(self.e,Path(t)/'ledger',Path(t)/'out')
            self.assertFalse((Path(t)/'ledger').exists())
    def test_duplicate_fingerprint_no_extra_row(self):
        r=copy.deepcopy(self.r);r['source']['image_sha256']=['a'*64];other=copy.deepcopy(r);other['record_id']='another-upload'
        d=duplicates(other,[r]);self.assertEqual(d['status'],'duplicate');self.assertEqual(merge(r,other)['record_id'],r['record_id'])
    def test_duplicate_identity_preserves_raw_and_feedback(self):
        e=copy.deepcopy(self.e);e['feedback']={'post_session_final_phase_feeling':'最后自己觉得在冲刺'}
        r,_,_,_=prepare(e);again=copy.deepcopy(self.e);replayed,g,_,d=prepare(again,[r])
        self.assertEqual(d['status'],'duplicate');self.assertEqual(replayed['metrics'],r['metrics']);self.assertIn('final_sprint',g['state_tags'])
    def test_unknown_discomfort_is_null(self):self.assertIsNone(validate(self.r)['discomfort'])
    def test_pre_intent_not_post_feeling(self):
        e=copy.deepcopy(self.e);e['feedback']={'pre_session_intent':'轻松放松'}
        r,g,_,_=prepare(e,self.history(5));self.assertNotIn('easy',g['state_tags']);self.assertEqual(g['dimensions']['强度投入'],3)
        self.assertEqual(r['metrics'][-1]['key'],'pre_session_intent')
    def test_easy_post_feedback_only_two_axes(self):
        # 1.2.9: the recovery axis is included in the five-axis mean.
        e=copy.deepcopy(self.e);e['feedback']={'post_session_feeling':'游后觉得轻松'}
        r,g,_,_=prepare(e,self.history(5));self.assertEqual(g['dimensions']['强度投入'],2.5);self.assertEqual(g['dimensions']['恢复从容度'],3.5);self.assertEqual(g['dimensions']['技术经济性'],3);self.assertEqual(g['dimensions']['节奏稳定'],3.5)

    def test_fatigue_not_rewarded_as_extra_effort(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        r=copy.deepcopy(self.r);self.feedback(r,'post_session_feeling','今天觉得疲劳');g=grade(r,self.history(5));self.assertEqual(g['dimensions']['强度投入'],3);self.assertEqual(g['dimensions']['恢复从容度'],3)

    def test_final_sprint_no_fabricated_splits(self):
        e=copy.deepcopy(self.e);e['feedback']={'post_session_final_phase_feeling':'末段自己觉得在冲刺'}
        r,g,_,_=prepare(e,self.history(5));self.assertIsNone(r['segments']);self.assertEqual(g['dimensions']['强度投入'],3.5);self.assertEqual(r['durations'],self.r['durations'])
    def test_subjective_numeric_no_all_axes_translation(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        e=copy.deepcopy(self.e);e['subjective_effort']=4;r,g,_,_=prepare(e,self.history(5))
        self.assertEqual(g['dimensions']['强度投入'],4);self.assertEqual(g['dimensions']['续航输出'],4);self.assertEqual(g['dimensions']['恢复从容度'],2);self.assertEqual(g['mean'],3.2);self.assertEqual(g['stars'],3)

    def test_user_feedback_takes_priority_over_host_estimate(self):
        e=copy.deepcopy(self.e);e['dimensions']={d:5 for d in DIMENSIONS};e['subjective_effort']=2;e['feedback']={'post_session_feeling':'游后轻松'}
        _,g,_,_=prepare(e);self.assertEqual(g['dimensions']['强度投入'],2);self.assertEqual(g['dimensions']['恢复从容度'],4)
    def test_saved_numeric_feedback_reused_on_duplicate(self):
        e=copy.deepcopy(self.e);e['subjective_effort']=4;r,g,_,_=prepare(e)
        _,again,_,d=prepare(self.e,[r]);self.assertEqual(d['status'],'duplicate');self.assertEqual(again['dimensions']['强度投入'],4)
    def test_heart_rate_no_health_or_score_inference(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        low=copy.deepcopy(self.r);high=copy.deepcopy(self.r)
        for r,v in [(low,80),(high,190)]:
            m=next(x for x in r['metrics'] if x['key']=='heart_rate');m.update(value=v,raw_value=str(v))
        a,b=grade(low,self.history(5)),grade(high,self.history(5));self.assertLess(a['dimensions']['强度投入'],b['dimensions']['强度投入'])
        for d in ['续航输出','节奏稳定','技术经济性']:self.assertEqual(a['dimensions'][d],b['dimensions'][d])
        self.assertEqual(a['dimensions']['恢复从容度'],6-a['dimensions']['强度投入'])

    def test_discomfort_not_more_stars(self):
        r=copy.deepcopy(self.r);r['discomfort']=True;self.assertEqual(grade(r,self.history(5),{d:5 for d in DIMENSIONS},5)['dimensions'],{d:3.0 for d in DIMENSIONS})
    def test_recovery_not_volume_penalized(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        r=copy.deepcopy(self.r);r['intent']='recovery';r['distance_m']=300;r['metrics']=[];g=grade(r,self.history(5));self.assertEqual(g['dimensions']['续航输出'],1.5);self.assertEqual(g['dimensions']['强度投入'],3);self.assertEqual(g['dimensions']['恢复从容度'],3)

    def test_economy_does_not_reduce_effort(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        r=copy.deepcopy(self.r);h=self.history(5)
        next(x for x in r['metrics'] if x['key']=='stroke_rate').update(value=15,raw_value='15')
        g=grade(r,h);self.assertGreater(g['dimensions']['技术经济性'],3);self.assertEqual(g['dimensions']['强度投入'],3)

    def test_work_volume_varies_without_quota_or_randomness(self):
        h=self.history(5);normal=grade(self.r,h);short=copy.deepcopy(self.r);heavy=copy.deepcopy(self.r)
        short['distance_m']=150;short['durations']={'active_s':189};heavy['distance_m']=3000;heavy['durations']={'active_s':3780}
        for record in [short,heavy]:
            for m in record['metrics']:
                if m['key']=='distance':m.update(value=record['distance_m'],raw_value=f"{record['distance_m']:g}")
                elif m['key']=='time':m.update(value=record['durations']['active_s'],raw_value=f"{record['durations']['active_s']//60}:{record['durations']['active_s']%60:02d}")
                elif m['key']=='lengths':m.update(value=record['distance_m']/50,raw_value=f"{record['distance_m']/50:g}")
            validate(record)
        self.assertLess(grade(short,h)['dimensions']['续航输出'],normal['dimensions']['续航输出']);self.assertGreater(grade(heavy,h)['dimensions']['续航输出'],normal['dimensions']['续航输出'])
        self.assertEqual(grade(heavy,h),grade(heavy,h));self.assertFalse(normal['distribution_quota'])
    def test_long_stable_evidence_changes_rating_without_randomness(self):
        short=copy.deepcopy(self.r);long=copy.deepcopy(self.r)
        short.update(distance_m=500,durations={'active_s':900},segments=None)
        long.update(distance_m=3000,durations={'active_s':3600},segments=[{'segment_index':i,'distance_m':100,'duration_s':120,'time_basis':'active'} for i in range(1,31)])
        a,b=grade(short,[]),grade(long,[])
        self.assertGreater(b['stars'],a['stars'])
        self.assertGreater(b['dimensions']['续航输出'],a['dimensions']['续航输出'])
        self.assertGreater(b['dimensions']['节奏稳定'],a['dimensions']['节奏稳定'])
        self.assertEqual(b,grade(long,[]))
        self.assertIn('配速离散',b['evidence']['节奏稳定'])
    def test_stability_requires_whole_session_compatible_splits(self):
        base=copy.deepcopy(self.r);base.update(distance_m=1500,durations={'active_s':1800})
        valid=copy.deepcopy(base);valid['segments']=[{'segment_index':i,'distance_m':50,'duration_s':60,'time_basis':'active','includes_rest':False} for i in range(1,31)]
        partial=copy.deepcopy(valid);partial['segments']=partial['segments'][:3]
        resting=copy.deepcopy(valid);resting['segments'][0]['includes_rest']=True
        self.assertGreater(grade(valid,[])['dimensions']['节奏稳定'],grade(base,[])['dimensions']['节奏稳定'])
        for record in (partial,resting):
            self.assertEqual(grade(record,[])['dimensions']['节奏稳定'],3)
    def test_complete_session_workload_and_stroke_consistency_are_evidence(self):
        steady=copy.deepcopy(self.r);steady.update(distance_m=1000,durations={'active_s':1180},metrics=[],segments=[{'segment_index':i,'distance_m':50,'duration_s':59,'time_basis':'active','stroke_count':22 if i<=10 else 24,'stroke_count_basis':'arm_strokes'} for i in range(1,21)])
        uneven=copy.deepcopy(steady)
        for i,segment in enumerate(uneven['segments']):segment['duration_s']=42 if i%2==0 else 76
        a,b=grade(steady,[]),grade(uneven,[])
        self.assertEqual(a['dimensions']['强度投入'],3)
        self.assertEqual(a['dimensions']['节奏稳定'],4.5)
        self.assertEqual(a['dimensions']['技术经济性'],3)
        self.assertEqual(a['stars'],3.5)
        self.assertLess(b['dimensions']['节奏稳定'],a['dimensions']['节奏稳定'])
        self.assertLess(b['stars'],a['stars'])
        self.assertEqual(a['dimension_provenance']['技术经济性']['kind'],'inferred')
    def test_sparse_uses_fixed_radar_with_estimated_axes(self):
        e=copy.deepcopy(self.e);e['record']['metrics']=[m for m in e['record']['metrics'] if m['key'] in ['distance','time','calories']]
        result=self.render_entry(e);self.assertTrue(result['layout']['radar_drawn']);self.assertEqual(len(result['rating']['dimensions']),5);self.assertEqual(result['layout']['layout_mode'],'rich')
    def test_missing_core_still_no_save_card(self):
        e={'person_id':'self','record':{'mode':'demo','metrics':[copy.deepcopy(self.r['metrics'][6])]}}
        e['quip']='今天只看清热量这笔账，泳池还藏着半本明细。'
        result=self.render_entry(e);self.assertEqual(result['dedup']['status'],'partial');self.assertNotIn('distance_m',result['raw_record']);self.assertTrue(result['layout']['radar_drawn']);self.assertTrue(all(isinstance(v,(int,float)) for v in result['rating']['dimensions'].values()))
    def test_dolphin_fastest_not_average(self):
        e=copy.deepcopy(self.e);e['adult_group']='male';e['fastest_100m']={'seconds':100,'stroke':'freestyle','source':'user_confirmed'}
        report=self.render_entry(e);self.assertEqual(report['rating']['dolphin']['level'],'金海豚');self.assertEqual(report['rating']['dolphin']['seconds'],100)
        self.assertEqual(report['layout']['dolphin_caption'],'最快100米配速 1′40″')
        self.assertEqual(next(m for m in report['raw_record']['metrics'] if m['key']=='pace')['qualifier'],'average')
    def test_silver_dolphin_caption_uses_complete_100m(self):
        e=copy.deepcopy(self.e);e['adult_group']='male';e['fastest_100m']={'seconds':110,'stroke':'freestyle','source':'user_confirmed'}
        report=self.render_entry(e)
        self.assertEqual(report['layout']['dolphin']['level'],'银海豚')
        self.assertEqual(report['layout']['dolphin_caption'],'最快100米配速 1′50″')
    def test_dolphin_threshold_boundaries(self):
        for stroke,group,limits in [('freestyle','male',[100,118,140,170]),('freestyle','female',[130,145,175,200]),('breaststroke','male',[110,125,146,178]),('breaststroke','female',[150,170,200,220])]:
            for expected,seconds in zip(['金海豚','银海豚','粉海豚','绿海豚'],limits):
                r=copy.deepcopy(self.r);r['stroke']=stroke;r['segments']=[{'distance_m':100,'duration_s':seconds,'time_basis':'active'}]
                self.assertEqual(assess(r,group)['level'],expected)
            r['segments'][0]['duration_s']=limits[-1]+1
            self.assertEqual(assess(r,group)['level'],'未达计时档')
    def test_no_fastest_no_group_and_unknown_stroke(self):
        r=copy.deepcopy(self.r);self.assertIsNone(fastest(r));self.assertEqual(assess(r,None)['level'],'待评');self.assertEqual(assess(r,None)['prompt'],PROMPT)
        r['stroke']='backstroke';r['segments']=[{'distance_m':100,'duration_s':100,'time_basis':'active'}]
        self.assertEqual(assess(r,'male')['level'],'待评')
    def test_profile_first_followup_correction_isolated(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertIsNone(profile.read(t,'synthetic-a')['adult_group'])
            self.assertEqual(profile.resolve(profile.read(t,'synthetic-a'),'female'), 'female')
            profile.append(t,'synthetic-a','female',0)
            self.assertEqual(profile.resolve(profile.read(t,'synthetic-a'),None),'female')
            with self.assertRaises(ValueError):profile.resolve(profile.read(t,'synthetic-a'),'male')
            self.assertEqual(profile.resolve(profile.read(t,'synthetic-a'),'male',True),'male')
            with self.assertRaises(ValueError):profile.read(t,'synthetic-b')
    def test_no_save_does_not_write_profile(self):
        self.require_font()
        with tempfile.TemporaryDirectory() as t:
            e=copy.deepcopy(self.e);e['adult_group']='female'
            result=execute(e,Path(t)/'ledger',Path(t)/'out',no_save=True)
            self.assertEqual(result['adult_group'],'female');self.assertFalse((Path(t)/'ledger').exists())
    def test_real_no_save_reads_same_person_group_without_changing_it(self):
        self.require_font()
        with tempfile.TemporaryDirectory() as t:
            ledger=Path(t)/'ledger';profile.append(ledger,'self','female',0)
            e=copy.deepcopy(self.e);e['record']['mode']='real';e['owner_confirmed']=True
            first=execute(e,ledger,Path(t)/'first',no_save=True)
            self.assertEqual(first['adult_group'],'female');self.assertFalse(any('首次请确认' in w for w in first['warnings']))
            e['adult_group']='male';e['adult_group_correction']=True
            corrected=execute(e,ledger,Path(t)/'corrected',no_save=True)
            self.assertEqual(corrected['adult_group'],'male');self.assertEqual(profile.read(ledger,'self')['adult_group'],'female')
            self.assertFalse(list(ledger.glob('v*.json')))
    def test_five_axes_change_with_session_inputs(self):
        short=copy.deepcopy(self.r);long=copy.deepcopy(self.r)
        short.update(distance_m=500,durations={'active_s':900});long.update(distance_m=2000,durations={'active_s':3600})
        a=grade(short,[]);b=grade(long,[])
        self.assertEqual(len(a['dimensions']),5);self.assertGreater(b['dimensions']['续航输出'],a['dimensions']['续航输出']);self.assertEqual(b['dimensions']['强度投入'],a['dimensions']['强度投入'])
        self.assertEqual(a['mean_basis'],'five_dimension_evaluation_mean')
    def test_elapsed_only_does_not_claim_active_effort(self):
        r=copy.deepcopy(self.r);r['time_basis']='elapsed';r['durations']={'elapsed_s':6000}
        self.assertEqual(grade(r,[])['dimensions']['强度投入'],3)
    def test_banana_and_dolphin_metadata(self):
        result=self.render_entry(self.e);self.assertTrue(result['layout']['banana_footer']);self.assertEqual(result['layout']['dolphin']['level'],'待评')
    def test_approved_phone_template_golden_geometry(self):
        self.require_font()
        self.assertEqual(TEMPLATE['brand'],'Swimming Buddy')
        self.assertEqual(TEMPLATE['brand_cn'],'泳搭子')
        self.assertEqual(TEMPLATE['brand_xy'],(65,51))
        self.assertEqual(TEMPLATE['brand_size'],39)
        self.assertEqual((TEMPLATE['brand_cn_xy'],TEMPLATE['brand_cn_size']),((65,107),28))
        self.assertEqual(TEMPLATE['time_dividers'],(454,845))
        self.assertEqual(TEMPLATE['parameter_slots'],((657,858),(935,858),(657,1025),(935,1025),(657,1192),(935,1192)))
        self.assertEqual(TEMPLATE['parameter_size'],(259,148))
        self.assertEqual((TEMPLATE['parameter_label_size'],TEMPLATE['parameter_value_size'],TEMPLATE['energy_value_size']),(22,28,28))
        result=self.render_entry(self.e);layout=result['layout']
        self.assertEqual(layout['template_brand'],'Swimming Buddy')
        self.assertEqual(layout['time_strip_dividers'],[454,845])
        self.assertEqual(layout['pace_unit_gap'],12)
        self.assertEqual(layout['parameter_slots'],[list(p) for p in TEMPLATE['parameter_slots']])
        rating=grade(self.r,[]);rating['dolphin']={'level':'银海豚','color':'银','score_text':'1′50″','seconds':110}
        im,_=render(self.r,rating,'岸上忙成一团，水里总算有条泳道。')
        self.assertEqual(im.getpixel((454,650)),(198,220,210));self.assertEqual(im.getpixel((845,650)),(198,220,210))
        self.assertEqual(im.getpixel((920,654)),(138,156,160))
        path,index=find_sc_font();f=ImageFont.truetype(path,round(16*1.1),index=index)
        self.assertEqual(im.getpixel((1200,1820)),(242,207,74))
        self.assertEqual(layout['banana_position'],'after_text')
        sparse=copy.deepcopy(self.e);sparse['record']['metrics']=[m for m in sparse['record']['metrics'] if m['key'] in ('distance','time','calories')]
        self.assertEqual(self.render_entry(sparse)['layout']['parameter_slots'],layout['parameter_slots'])
    def test_dolphin_outline_fixed_across_grade_colors(self):
        self.require_font()
        masks=[]
        for level,color,expected in [('金海豚','金',(183,152,53)),('银海豚','银',(138,156,160)),('粉海豚','粉',(215,152,169)),('绿海豚','绿',(112,166,147)),('蓝海豚','蓝',(110,169,190))]:
            rating=grade(self.r,[]);rating['dolphin']={'level':level,'color':color,'score_text':'1′50″','seconds':110}
            im,_=render(self.r,rating,'岸上忙成一团，水里总算有条泳道。')
            self.assertEqual(im.getpixel((920,654)),expected)
            masks.append({(x,y) for y in range(625,680) for x in range(880,970) if im.getpixel((x,y))==expected})
        self.assertTrue(all(mask==masks[0] for mask in masks[1:]))
    def test_long_fields_use_fixed_overflow_policy(self):
        e=copy.deepcopy(self.e);heart=next(m for m in e['record']['metrics'] if m['key']=='heart_rate')
        heart['label']='特别长的设备平均心率标签'*10
        heart['raw_value']='154'*40
        result=self.render_entry(e)
        self.assertIn('参数名称',result['layout']['overflow_fields'])
        self.assertIn('参数数值',result['layout']['overflow_fields'])
        self.assertEqual(next(m for m in result['raw_record']['metrics'] if m['key']=='heart_rate')['raw_value'],'154'*40)
    def test_sc_font_override_and_missing_font(self):
        self.require_font()
        path,index=find_sc_font()
        with patch.dict(os.environ,{'SWIM_BUDDY_SC_FONT':path}):
            self.assertEqual(find_sc_font(),(path,index))
        with patch('sc_font.STANDARD',[]),patch.dict(os.environ,{'SWIM_BUDDY_SC_FONT':''}):
            with self.assertRaisesRegex(ValueError,'SC字体'):find_sc_font()
    def test_complete_segments_calculate_swolf_25_and_50(self):
        for pool,seconds,strokes,expected in [(25,180,80,65),(50,120,40,80)]:
            r=copy.deepcopy(self.r);r.update(distance_m=100,pool_length_m=pool,durations={'active_s':seconds},segments=[{'segment_index':1,'distance_m':100,'duration_s':seconds,'time_basis':'active','stroke_count':strokes,'stroke_count_basis':'arm_strokes','pool_length_m':pool}]);r['metrics']=[]
            self.assertEqual(complete_metrics(r),[])
            self.assertEqual(next(m['value'] for m in r['metrics'] if m['key']=='swolf'),expected)
            self.assertEqual(next(m['value'] for m in r['metrics'] if m['key']=='stroke_count'),strokes)
            self.assertIn('（计算）',next(m['label'] for m in r['metrics'] if m['key']=='swolf'))
    def test_partial_rest_duplicate_segments_do_not_sum(self):
        base=copy.deepcopy(self.r);base.update(distance_m=200,durations={'active_s':240},metrics=[])
        seg={'distance_m':100,'duration_s':120,'time_basis':'active','stroke_count':40,'stroke_count_basis':'arm_strokes'}
        for segments in [[{**seg,'segment_index':1}],[{**seg,'segment_index':1},{**seg,'segment_index':1}],[{**seg,'segment_index':1,'includes_rest':True},{**seg,'segment_index':2}],[{**seg,'segment_index':1,'time_basis':'elapsed'},{**seg,'segment_index':2}]]:
            r=copy.deepcopy(base);r['segments']=segments;warnings=complete_metrics(r)
            self.assertTrue(warnings);self.assertFalse(any(m['key']=='swolf' for m in r['metrics']))
    def test_different_count_basis_and_conflict_preserve_raw(self):
        r=copy.deepcopy(self.r);r.update(distance_m=100,durations={'active_s':180},pool_length_m=25,metrics=[])
        a={'segment_index':1,'distance_m':50,'duration_s':90,'time_basis':'active','stroke_count':40,'stroke_count_basis':'arm_strokes'}
        r['segments']=[a,{**a,'segment_index':2,'stroke_count_basis':'cycles'}]
        self.assertTrue(complete_metrics(r));self.assertFalse(any(m['key']=='swolf' for m in r['metrics']))
        r['segments']=[{**a,'distance_m':100,'duration_s':180,'stroke_count':80}]
        raw=copy.deepcopy(self.r['metrics'][0]);raw.update(id='synthetic-swolf-original',key='swolf',qualifier='average',label='平均SWOLF',raw_value='50',raw_unit='',value=50,unit='score');r['metrics']=[raw]
        warnings=complete_metrics(r);self.assertTrue(any('SWOLF' in w for w in warnings));self.assertEqual(next(m for m in r['metrics'] if m['key']=='swolf')['value'],50)
    def test_calories_units_stay_original_and_card_caps_six(self):
        e=copy.deepcopy(self.e);r=e['record']
        extra=copy.deepcopy(r['metrics'][0]);extra.update(id='synthetic-energy-kj',key='energy_kj',qualifier='total',label='能量',raw_value='500',raw_unit='kJ',value=500,unit='kJ')
        r['metrics'].extend([extra]+[{**copy.deepcopy(extra),'id':f'synthetic-extra-{i}','key':f'unknown_{i}','label':f'原始字段{i}'} for i in range(8)])
        result=self.render_entry(e);self.assertLessEqual(result['layout']['displayed_metric_count'],6)
        self.assertTrue(any(m['raw_unit']=='kJ' for m in result['raw_record']['metrics']))
        self.assertTrue(any(m['unit']=='kcal' for m in result['raw_record']['metrics'] if m['key']=='calories'))
    def test_session_parameter_order_and_missing_compaction(self):
        result=self.render_entry(self.e)
        indexed={m['id']:m for m in result['raw_record']['metrics']}
        selected=[(indexed[id]['key'],indexed[id]['qualifier']) for id in result['layout']['displayed_metric_ids']]
        self.assertEqual(selected,[('calories','total'),('calories','active'),('heart_rate','average'),('stroke_count','total'),('stroke_rate','average'),('swolf','average')])
        e=copy.deepcopy(self.e);r=e['record']
        r['metrics']=[m for m in r['metrics'] if not(m['key']=='calories' and m['qualifier']=='active') and m['key']!='stroke_rate']
        template=copy.deepcopy(r['metrics'][0]);template.update(id='synthetic-device-extra',key='device_extra',qualifier='unspecified',label='设备额外参数',raw_value='42',raw_unit='次',value=42,unit='count')
        r['metrics'].insert(0,template)
        result=self.render_entry(e);indexed={m['id']:m for m in result['raw_record']['metrics']}
        selected=[(indexed[id]['key'],indexed[id]['qualifier']) for id in result['layout']['displayed_metric_ids']]
        self.assertEqual(selected[:3],[('calories','total'),('heart_rate','average'),('stroke_count','total')]);self.assertEqual(selected[-1],('swolf','average'))
        self.assertIn(('device_extra','unspecified'),selected)
        self.assertLessEqual(len(selected),6)
    def test_twenty_lengths_only_session_metrics_on_card(self):
        e=copy.deepcopy(self.e);r=e['record']
        r.update(distance_m=1000,durations={'active_s':1200},segments=[{'segment_index':i,'distance_m':50,'duration_s':60,'time_basis':'active','stroke_count':20,'stroke_count_basis':'arm_strokes','pool_length_m':50} for i in range(1,21)])
        r['metrics']=[m for m in r['metrics'] if m['key'] not in ('swolf','stroke_count','stroke_rate')]
        for m in r['metrics']:
            if m['key']=='distance':m.update(raw_value='1,000',value=1000)
            elif m['key']=='time' and m['qualifier']=='active':m.update(raw_value='00:20:00',value=1200)
            elif m['key']=='pace':m.update(raw_value='2′00″',value=120)
            elif m['key']=='lengths':m.update(raw_value='20',value=20)
        template=copy.deepcopy(r['metrics'][0])
        for i in range(1,21):
            for key,value in [('swolf',80),('stroke_count',20)]:
                r['metrics'].append({**copy.deepcopy(template),'id':f'synthetic-segment-{i}-{key}','key':key,'qualifier':'average' if key=='swolf' else 'total','label':'分段SWOLF' if key=='swolf' else '分段划水','raw_value':str(value),'raw_unit':'分' if key=='swolf' else '次','value':value,'unit':'score' if key=='swolf' else 'count','scope':f'segment:{i}'})
        result=self.render_entry(e);rows=result['raw_record']['metrics'];ids=set(result['layout']['displayed_metric_ids'])
        self.assertEqual(result['layout']['displayed_metric_count'],6)
        self.assertFalse(any(id.startswith('synthetic-segment-') for id in ids))
        self.assertEqual(len([m for m in rows if m.get('scope','').startswith('segment:')]),40)
        self.assertTrue({'calculated-swolf-average','calculated-stroke_count-total','calculated-stroke_rate-average'}.issubset(ids))
        self.assertTrue(any(m['key']=='heart_rate' and m['id'] in ids for m in rows))
        self.assertEqual(sum(m['key']=='calories' and m['id'] in ids for m in rows),2)
    def test_energy_conversion_exact_values_and_precision(self):
        template={'key':'calories','status':'confirmed','value':976,'unit':'kJ','qualifier':'total'}
        self.assertEqual(energy_display(template),'233 千卡 / 976 kJ')
        self.assertEqual(energy_display({**template,'value':1096}),'262 千卡 / 1096 kJ')
        self.assertEqual(energy_display({**template,'unit':'kcal','value':233.27}),'233 千卡 / 976 kJ')
        self.assertEqual(template['value'],976)
    def test_energy_active_total_and_ambiguous_cal(self):
        r=copy.deepcopy(self.r);base=copy.deepcopy(r['metrics'][0]);base.update(key='calories',qualifier='active',unit='kJ',value=976,raw_value='976',raw_unit='kJ',label='活动热量',id='synthetic-active')
        total={**copy.deepcopy(base),'id':'synthetic-total','qualifier':'total','value':1096,'raw_value':'1096','label':'总热量'}
        r['metrics']=[base,total];complete_metrics(r)
        self.assertEqual([energy_display(m) for m in r['metrics'] if m['key']=='calories'],['233 千卡 / 976 kJ','262 千卡 / 1096 kJ'])
        ambiguous={**copy.deepcopy(base),'id':'synthetic-cal','unit':'cal','raw_unit':'cal'}
        r['metrics']=[ambiguous]
        self.assertIsNone(energy_display(ambiguous));self.assertTrue(any('cal口径' in w for w in complete_metrics(r)))
    def test_rich_native_radar_sc(self):
        result=self.render_entry(self.e);self.assertTrue(result['layout']['radar_drawn']);self.assertIn('SC',result['layout']['font_family']);self.assertFalse(result['layout']['radial_tick_labels'])
    def test_huawei_total_active_preserved(self):
        e=copy.deepcopy(self.e);e['record']['source']['app']='synthetic Huawei';result=self.render_entry(e)
        values={m['qualifier']:m['value'] for m in result['raw_record']['metrics'] if m['key']=='calories'};self.assertEqual(values,{'total':310,'active':260})
    def test_xiaomi_without_hr_not_zero(self):
        e=copy.deepcopy(self.e);e['record']['source']['app']='synthetic Mi Fitness Band7';e['record']['metrics']=[m for m in e['record']['metrics'] if m['key']!='heart_rate']
        result=self.render_entry(e);self.assertFalse(any(m['key']=='heart_rate' for m in result['raw_record']['metrics']));self.assertTrue(result['layout']['radar_drawn'])
    def test_apple_imperial_raw_units(self):
        e=copy.deepcopy(self.e);e['record']['source']['app']='synthetic Apple Fitness';e['record']['distance_m']=1371.6
        e['record']['pool_length_m']=45.72
        pool=next(m for m in e['record']['metrics'] if m['key']=='pool_length');pool.update(raw_value='50',raw_unit='yd',value=45.72)
        m=next(m for m in e['record']['metrics'] if m['key']=='distance');m.update(raw_value='1,500',raw_unit='yd',value=1371.6)
        m=next(m for m in e['record']['metrics'] if m['key']=='pace');m.update(raw_unit='/100yd',unit='s/100yd')
        result=self.render_entry(e);m=next(m for m in result['raw_record']['metrics'] if m['key']=='pace');self.assertEqual(m['raw_unit'],'/100yd');self.assertEqual(m['unit'],'s/100yd')
    def test_unknown_brand_same_data_same_rating(self):
        # 1.2.8: expectation updated for explicitly requested scoring semantics.
        e=copy.deepcopy(self.e);e['record']['source']['app']='未知';result=self.render_entry(e);self.assertEqual(result['rating']['dimensions'],grade(self.e['record'],[])['dimensions'])

    def test_unknown_denominator_preserved(self):
        e=copy.deepcopy(self.e);m=next(m for m in e['record']['metrics'] if m['key']=='pace');m.update(raw_unit='',unit='s/unknown',time_basis='unspecified')
        result=self.render_entry(e);m=next(m for m in result['raw_record']['metrics'] if m['key']=='pace');self.assertEqual(m['raw_unit'],'');self.assertEqual(m['unit'],'s/unknown')
    def test_segment_scope_not_total(self):
        r=copy.deepcopy(self.r);m=copy.deepcopy(r['metrics'][0]);m.update(id='synthetic-segment-distance',raw_value='50',value=50,scope='segment:2');r['metrics'].insert(0,m)
        result=validate(r);self.assertEqual(result['distance_m'],1500);self.assertEqual(result['metrics'][0]['scope'],'segment:2')
    def test_all_unknown_extra_metrics_kept(self):
        e=copy.deepcopy(self.e)
        for i in range(8):
            m=copy.deepcopy(self.r['metrics'][-1]);m.update(id=f'synthetic-extra-{i}',key=f'extra_{i}',qualifier='unspecified',label=f'扩展指标{i}',raw_value=str(i+1),value=i+1,raw_unit='单位',unit='unknown');e['record']['metrics'].append(m)
        result=self.render_entry(e);self.assertEqual(result['layout']['displayed_metric_count'],6);self.assertEqual(len(result['raw_record']['metrics']),20)
    def test_fixed_mapping_multiple_poses_no_humans(self):
        library=load_library();expected=['海豹','青蛙','企鹅','水獭','水牛']
        for level,animal in enumerate(expected,1):
            self.assertEqual(library['levels'][str(level)]['animal'],animal);poses=[x for x in library['poses'] if x['level']==level];self.assertGreaterEqual(len(poses),2)
            for pose in poses:
                with Image.open(BASE/'assets'/pose['path']) as im:self.assertEqual(im.mode,'RGBA');self.assertLess(im.getextrema()[-1][0],255)
        self.assertFalse(any('swimmer_rendered' in x['path'] for x in library['poses']))
    def test_recent_rotation_and_same_record_idempotent(self):
        g=grade(self.r,[]);a=choose(self.r,g);recent=[a];other=copy.deepcopy(self.r);other['record_id']='synthetic-next'
        b=choose(other,g,recent);self.assertNotEqual(a['pose_id'],b['pose_id']);self.assertNotEqual(a['quip_id'],b['quip_id'])
        self.assertEqual(choose(self.r,g,recent)['pose_id'],a['pose_id'])
    def test_final_sprint_otter_pose_copy_match(self):
        r=copy.deepcopy(self.r);self.feedback(r,'post_session_final_phase_feeling','末段冲刺');g=grade(r,[],{d:4 for d in DIMENSIONS});v=choose(r,g)
        self.assertEqual(v['animal'],'水獭');self.assertEqual(v['state'],'final_sprint');self.assertTrue(v['pose_exact_state_match'])
    def test_explicit_human_decoration_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):execute(self.e,Path(t)/'ledger',Path(t)/'out',no_save=True,decoration=BASE/'assets/swimmer_rendered.png')
    def test_case_inputs_leave_original_unchanged(self):
        original=copy.deepcopy(self.e);self.render_entry(self.e);self.assertEqual(self.e,original)

if __name__=='__main__':unittest.main(verbosity=2)
