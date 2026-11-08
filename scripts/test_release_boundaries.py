import copy,json,unittest,tempfile
from run import execute,prepare
from rating import DIMENSIONS
from unittest.mock import patch
from presentation import choose,load_library,verify_pose
from pathlib import Path
from dolphin import fastest,assess
from legacy_records import merge
ROOT=Path(__file__).resolve().parents[1]
class ReleaseBoundaries(unittest.TestCase):
 def record(self):
  r=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))['record']
  r.update(stroke='freestyle',metrics=[],segments=[])
  return r
 def segment(self,index,seconds):
  return dict(segment_index=index,distance_m=100,duration_s=seconds,time_basis='active',stroke='freestyle')
 def metric(self,basis='active',label='最快完整100米'):
  return dict(id='direct',key='fastest_100m',qualifier='best',status='confirmed',scope='complete_100m',unit='s',value=90,label=label,time_basis=basis,source={'region':'本次完整100米'})
 def test_conflicting_100m_excluded_valid_other_retained(self):
  r=self.record();r['segments']=[self.segment(1,90),self.segment(1,110),self.segment(2,120)]
  e=fastest(r);self.assertEqual(e['seconds'],120);self.assertEqual(e['conflicts'][0]['type'],'segment_observation_conflict')
 def test_only_conflict_has_diagnostics_no_grade(self):
  r=self.record();r['segments']=[self.segment(1,90),self.segment(1,110)]
  a=assess(r,'male');self.assertIsNone(a['seconds']);self.assertTrue(a['excluded_evidence']);self.assertTrue(a['conflicts'])
 def test_identical_100m_observations_remain_valid(self):
  r=self.record();r['segments']=[self.segment(1,110),self.segment(1,110)]
  self.assertEqual(fastest(r)['seconds'],110)
 def test_elapsed_direct_excluded(self):
  r=self.record();r['metrics']=[self.metric('elapsed')]
  a=assess(r,'male');self.assertIsNone(a['seconds']);self.assertEqual(a['excluded_evidence'][0]['reason'],'elapsed_or_explicit_rest')
 def test_rest_text_excluded_in_label_or_source(self):
  for label,region in [('最快100米含休息','本次'),('最快100米','本次含休息'),('最快100米','including rest'),('最快100米','包括休息'),('最快100米','包含休息时间')]:
   r=self.record();m=self.metric(label=label);m['source']['region']=region;r['metrics']=[m]
   self.assertIsNone(assess(r,'male')['seconds'])
 def test_negated_rest_wording_not_rejected(self):
  for text in ['不含休息','不包含休息','未包含休息','不包括休息','not including rest','excluding rest','without rest']:
   r=self.record();r['metrics']=[self.metric(label='最快100米 '+text)]
   e=fastest(r);self.assertEqual(e['seconds'],90);self.assertEqual(e['rest_status'],'explicitly_excluded')
 def test_raw_value_rest_annotation_excluded(self):
  r=self.record();m=self.metric();m['raw_value']='90（含休息）';r['metrics']=[m]
  self.assertIsNone(assess(r,'male')['seconds']);self.assertEqual(r['metrics'][0]['raw_value'],'90（含休息）')
 def test_unknown_rest_not_invented(self):
  r=self.record();r['metrics']=[self.metric()]
  self.assertEqual(fastest(r)['rest_status'],'not_reported')
 def test_excluded_direct_keeps_other_valid(self):
  r=self.record();r['metrics']=[self.metric('elapsed')];r['segments']=[self.segment(1,120)]
  self.assertEqual(fastest(r)['seconds'],120)
 def test_merge_keeps_added_lap(self):
  old=self.record();old['segments']=[self.segment(1,120)];new=copy.deepcopy(old);new['segments'].append(self.segment(2,110))
  result=merge(old,new);self.assertEqual(len(result['segments']),2);self.assertEqual(fastest(result)['seconds'],110)
 def test_merge_keeps_conflicting_observations(self):
  old=self.record();old['segments']=[self.segment(1,120)];new=copy.deepcopy(old);new['segments'][0]['duration_s']=90
  result=merge(old,new);self.assertEqual(len(result['segments']),2);self.assertIsNone(fastest(result))
 def test_merge_identical_observations_deduplicated(self):
  old=self.record();old['segments']=[self.segment(1,120)]
  self.assertEqual(len(merge(old,copy.deepcopy(old))['segments']),1)
 def test_mixed_default_unrated_explicit_opt_in(self):
  r=self.record();r['stroke']='mixed';r['segments']=[self.segment(1,110)]
  self.assertEqual(assess(r,'male')['level'],'待评')
  self.assertEqual(assess(r,'male',mixed_as_freestyle=True)['level'],'银海豚')
 def test_mixed_flag_requires_boolean(self):
  with self.assertRaises(ValueError):assess(self.record(),'male',mixed_as_freestyle='true')
 def test_save_requires_literal_boolean_true(self):
  for consent in [False,'false','true',1,0,{},[],{'yes':True},None]:
   e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))
   e['record']['mode']='real';e['owner_confirmed']=consent
   with tempfile.TemporaryDirectory() as td:
    with self.assertRaises(ValueError):execute(e,td+'/ledger',td+'/out')
    self.assertFalse((Path(td)/'ledger').exists())
 def test_mixed_envelope_rejects_unrecognized_reference(self):
  e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'));e['dolphin_mixed_reference']=True
  with tempfile.TemporaryDirectory() as td:
   with self.assertRaises(ValueError):execute(e,td+'/ledger',td+'/out',no_save=True)
 def test_selected_asset_hash_must_match_review(self):
  lib=load_library()
  for pose in lib['poses']:pose['sha256']='0'*64
  with patch('presentation.load_library',return_value=lib):
   with self.assertRaises(ValueError):choose({'record_id':'synthetic-hash','metrics':[]},{'mean':3.3,'stars':3.5,'state_tags':['normal']})
 def test_replaced_asset_bytes_rejected(self):
  with tempfile.TemporaryDirectory() as td:
   (Path(td)/'animal.webp').write_bytes(b'unreviewed replacement')
   with patch('presentation.ASSETS',Path(td)):
    with self.assertRaises(ValueError):verify_pose({'path':'animal.webp','sha256':'0'*64})
 def discomfort_case(self,partial=False,overrides=False,subjective=False):
  e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))
  e['record']['discomfort']=True;e.pop('dimensions',None)
  if partial:e['record']['session_date']=None
  if overrides:e['dimensions']={d:5 for d in DIMENSIONS}
  if subjective:e['subjective_effort']=5
  record,rating,_,_=prepare(e)
  self.assertEqual(rating['dimensions'],{d:3.0 for d in DIMENSIONS});self.assertEqual(rating['mean'],3);self.assertEqual(rating['stars'],3)
  self.assertIn('discomfort',rating['state_tags'])
  for value in rating['dimension_provenance'].values():
   self.assertEqual(value['kind'],'inferred');self.assertTrue(value['safety_neutral']);self.assertIn('不适',value['basis'])
  if subjective:self.assertTrue(any(m['key']=='subjective_effort' and m['value']==5 for m in record['metrics']))
 def test_discomfort_complete_neutral(self):self.discomfort_case()
 def test_discomfort_partial_neutral(self):self.discomfort_case(partial=True)
 def test_discomfort_overrides_and_subjective_cannot_reward(self):self.discomfort_case(overrides=True,subjective=True)
 def test_discomfort_partial_overrides_and_subjective_cannot_reward(self):self.discomfort_case(partial=True,overrides=True,subjective=True)
if __name__=='__main__':unittest.main()
