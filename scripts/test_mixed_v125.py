"""Synthetic mixed-stroke and provenance regressions; no owner ledger."""
import copy,json,tempfile,unittest
from pathlib import Path
from run import prepare,execute
from dolphin import assess
from legacy_records import validate
BASE=Path(__file__).resolve().parents[1]
class MixedTests(unittest.TestCase):
 def setUp(self):
  self.e=json.loads((BASE/'references/synthetic.json').read_text(encoding='utf-8'));self.e.pop('dimensions');self.e['adult_group']='male'
  r=self.e['record'];r.update(stroke='mixed',distance_m=400,durations={'active_s':490})
  r['metrics']=[m for m in r['metrics'] if m['key'] in ('calories','heart_rate')]
  r['segments']=[{'segment_index':i+1,'distance_m':100,'duration_s':t,'time_basis':'active','stroke':s,'pool_length_m':50,'stroke_count':44,'stroke_count_basis':'arm_strokes','includes_rest':False} for i,(t,s) in enumerate([(110,'freestyle'),(145,'breaststroke'),(120,'backstroke'),(115,'butterfly')])]
 def computed(self,e=None):return prepare(e or self.e)
 def test_true_mixed_accepted_labels_preserved(self):
  r,_,_,_=self.computed();self.assertEqual([s['stroke'] for s in r['segments']],['freestyle','breaststroke','backstroke','butterfly']);self.assertEqual(next(m['value'] for m in r['metrics'] if m['key']=='swolf'),83.2)
 def test_mixed_free_threshold_user_reference(self):
  r,*_=self.computed();b=assess(r,'male',mixed_as_freestyle=True);self.assertEqual(b['level'],'银海豚');self.assertEqual(b['seconds'],110);self.assertEqual(b['reference_basis'],'user_requested_mixed_as_freestyle')
 def test_mixed_no_single_stroke_efficiency(self):
  _,rating,_,_=self.computed();self.assertEqual(rating['dimensions']['技术经济性'],3);self.assertEqual(rating['dimensions']['节奏稳定'],3)
 def test_unknown_not_inferred(self):
  e=copy.deepcopy(self.e);e['record']['stroke']='unknown';r,*_=self.computed(e);self.assertEqual(assess(r,'male')['level'],'待评');self.assertFalse(any(m['key']=='swolf' for m in r['metrics']))
 def test_ambiguous_mixed_segments_skip_derivation(self):
  e=copy.deepcopy(self.e)
  for s in e['record']['segments']:s['stroke']='mixed'
  r,rating,*_=self.computed(e);self.assertFalse(any(m['key']=='swolf' for m in r['metrics']));self.assertTrue(rating['derived_warnings'])
 def test_cycles_conflict_preserves_device_swolf(self):
  e=copy.deepcopy(self.e);e['record']['segments'][1]['stroke_count_basis']='cycles';m=copy.deepcopy(e['record']['metrics'][0]);m.update(id='device-swolf',key='swolf',qualifier='average',label='平均SWOLF',raw_value='87',raw_unit='',value=87,unit='score');e['record']['metrics'].append(m)
  r,rating,*_=self.computed(e);self.assertEqual(next(m['value'] for m in r['metrics'] if m['key']=='swolf'),87);self.assertFalse(any(m['id'].startswith('calculated-stroke') for m in r['metrics']));self.assertTrue(rating['derived_warnings'])
 def test_pool_mismatch_rejected(self):
  e=copy.deepcopy(self.e);e['record']['segments'][1]['pool_length_m']=25
  with self.assertRaises(ValueError):self.computed(e)
 def test_time_conflict_no_derivation(self):
  e=copy.deepcopy(self.e);e['record']['durations']['active_s']=500;r,_,_,_=self.computed(e);self.assertFalse(any(m['key']=='swolf' for m in r['metrics']))
 def test_rest_no_derivation(self):
  e=copy.deepcopy(self.e);e['record']['segments'][1]['includes_rest']=True;r,_,_,_=self.computed(e);self.assertFalse(any(m['key']=='swolf' for m in r['metrics']))
 def test_invalid_segment_stroke_rejected(self):
  e=copy.deepcopy(self.e);e['record']['segments'][0]['stroke']='imagined'
  with self.assertRaises(ValueError):self.computed(e)
 def test_pure_back_butterfly_no_free_threshold(self):
  for stroke in ['backstroke','butterfly']:
   e=copy.deepcopy(self.e);e['record']['stroke']=stroke
   for s in e['record']['segments']:s['stroke']=stroke
   r,*_=self.computed(e);self.assertEqual(assess(r,'male')['level'],'待评')
 def test_render_mixed_no_save(self):
  with tempfile.TemporaryDirectory() as td:
   r=execute(self.e,td+'/ledger',td+'/out',no_save=True);self.assertFalse(r['saved']);self.assertEqual(r['version'],'1.2.15-rc.1+fresh-quips.20261108');self.assertFalse(Path(td+'/ledger').exists());self.assertEqual(r['layout']['displayed_metric_count'],6)
if __name__=='__main__':unittest.main()

