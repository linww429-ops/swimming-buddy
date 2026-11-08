import copy,json,tempfile,unittest
from pathlib import Path
from rating import grade,DIMENSIONS
from run import prepare,execute
BASE=Path(__file__).resolve().parents[1]
class Scoring128(unittest.TestCase):
 def row(self,d=1000,hr=144,rate=19,pace=125):
  e=json.loads((BASE/'references/synthetic.json').read_text(encoding='utf-8'));e.pop('dimensions',None);e.pop('quip',None)
  r=e['record'];r['distance_m']=d;r['durations']={'active_s':d*pace/100};r['metrics']=[];r['segments']=None;r['discomfort']=None
  for k,v in [('heart_rate',hr),('stroke_rate',rate),('pace',pace)]:
   if v is not None:r['metrics'].append({'id':'test-'+k,'key':k,'qualifier':'average','value':v,'status':'confirmed','scope':'session'})
  return r
 def feedback(self,r,text,key='post_session_feeling'):
  r['metrics'].append({'id':'test-'+key,'key':key,'qualifier':'unspecified','value':text,'status':'confirmed','scope':'after_session'})
 def test_distance_anchors(self):
  for d,v in [(1000,3),(1200,3.5),(1500,4)]:self.assertEqual(grade(self.row(d),[])['dimensions']['续航输出'],v)
 def test_distance_monotonic(self):
  values=[grade(self.row(d),[])['dimensions']['续航输出'] for d in range(50,4001,50)];self.assertEqual(values,sorted(values))
 def test_today_easy(self):
  r=self.row();self.feedback(r,'今天刻意放慢，相对轻松');g=grade(r,[]);self.assertEqual(g['dimensions']['强度投入'],2.5);self.assertEqual(g['dimensions']['恢复从容度'],3.5)
 def test_easy_without_hr(self):
  r=self.row(hr=None);self.feedback(r,'轻松');self.assertEqual(grade(r,[])['dimensions']['强度投入'],2)
 def test_easy_limits_high_hr(self):
  r=self.row(hr=190);self.feedback(r,'轻松');self.assertEqual(grade(r,[])['dimensions']['强度投入'],2.5)
 def test_hard_sprint(self):
  r=self.row(hr=175);self.feedback(r,'高强度，很吃力');self.feedback(r,'末段冲刺','post_session_final_phase_feeling');g=grade(r,[]);self.assertGreaterEqual(g['dimensions']['强度投入'],4.5)
 def test_missing_metrics_neutral(self):
  r=self.row(hr=None,rate=None);r['metrics']=[];g=grade(r,[]);self.assertEqual(g['dimensions'],dict.fromkeys(DIMENSIONS,3))
 def test_numeric_authority(self):
  r=self.row(hr=190);self.feedback(r,'轻松');g=grade(r,[],feeling=4);self.assertEqual(g['dimensions']['强度投入'],4);self.assertEqual(g['dimensions']['恢复从容度'],2)
 def test_inverse_mapping(self):
  for f in [1,1.5,2,2.5,3,3.5,4,4.5,5]:
   g=grade(self.row(),[],feeling=f);self.assertEqual(g['dimensions']['恢复从容度'],6-f)
 def test_economy_requires_rate_and_pace(self):
  a=self.row(rate=19,pace=125);b=self.row(rate=19,pace=200)
  self.assertGreater(grade(a,[])['dimensions']['技术经济性'],grade(b,[])['dimensions']['技术经济性'])
 def test_low_rate_not_always_good(self):
  a=self.row(rate=15,pace=240);b=self.row(rate=22,pace=100)
  self.assertLess(grade(a,[])['dimensions']['技术经济性'],grade(b,[])['dimensions']['技术经济性'])
 def test_unknown_stroke_economy_neutral(self):
  r=self.row();r['stroke']='unknown';self.assertEqual(grade(r,[])['dimensions']['技术经济性'],3)
 def test_unknown_cadence_economy_neutral(self):self.assertEqual(grade(self.row(rate=None),[])['dimensions']['技术经济性'],3)
 def segments(self,r,start=1,end=20,t=62.5):
  r['segments']=[{'segment_index':i,'distance_m':50,'duration_s':t,'time_basis':'active','stroke':'freestyle'} for i in range(start,end+1)]
 def test_full_stability(self):
  r=self.row();self.segments(r);self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],4.5)
 def test_partial_majority_capped(self):
  r=self.row();self.segments(r,4,20);g=grade(r,[]);self.assertEqual(g['dimensions']['节奏稳定'],4);self.assertIn('85%',g['evidence']['节奏稳定'])
 def test_partial_small_neutral(self):
  r=self.row();self.segments(r,1,3);self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],3)
 def test_gaps_not_stability(self):
  r=self.row();self.segments(r);r['segments'].pop(5);self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],3)
 def test_rest_not_stability(self):
  r=self.row();self.segments(r);r['segments'][0]['includes_rest']=True;self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],3)
 def test_breathing_feedback(self):
  r=self.row();self.feedback(r,'呼吸顺畅','post_session_breathing');self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],3.5)
 def test_disrupted_breathing(self):
  r=self.row();self.feedback(r,'呼吸乱','post_session_breathing');self.assertEqual(grade(r,[])['dimensions']['节奏稳定'],2.5)
 def test_not_easy_negation(self):
  r=self.row();self.feedback(r,'今天不轻松');self.assertNotIn('easy',grade(r,[])['state_tags'])
 def test_no_randomness_or_mutation(self):
  r=self.row();original=copy.deepcopy(r);a=grade(r,[]);self.assertEqual(a,grade(r,[]));self.assertEqual(r,original);self.assertFalse(a['distribution_quota'])
 def test_invalid_hr_ignored(self):self.assertEqual(grade(self.row(hr=999),[])['dimensions']['强度投入'],3)
 def test_discomfort_neutral(self):
  r=self.row(hr=190);r['discomfort']=True;self.assertEqual(grade(r,[],feeling=5)['dimensions'],{d:3.0 for d in DIMENSIONS})
 def test_phone_only_no_fastest_no_block(self):
  e=json.loads((BASE/'references/synthetic.json').read_text(encoding='utf-8'));e.pop('dimensions',None);e['adult_group']='male'
  with tempfile.TemporaryDirectory() as td:
   r=execute(e,Path(td)/'ledger',Path(td)/'out',no_save=True,phone_only=True)
   self.assertTrue((Path(td)/'out/today-phone.png').exists());self.assertFalse((Path(td)/'out/today-full.png').exists());self.assertIsNone(r['rating']['dolphin']['seconds']);self.assertFalse(r['saved'])
