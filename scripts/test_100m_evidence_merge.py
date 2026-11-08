import copy,unittest
from test_revision_1211 import example
from dolphin import fastest,assess

class UnifiedEvidence(unittest.TestCase):
 def record(self):
  r=example()['record'];r['person_id']='self';r['record_id']='synthetic-current';return r
 def add_best(self,r,value,label='最快完整100米',mid='direct-current'):
  r['metrics'].append(dict(id=mid,key='fastest_100m',qualifier='best',status='confirmed',scope='complete_100m',unit='s',value=value,label=label,raw_value=str(value),raw_unit='秒',time_basis='active',source={'image_id':'synthetic-current-detail','region':'本次完整100米计时','image_sha256':None}))
 def test_slower_reported_best_cannot_hide_faster_pair(self):
  r=self.record();self.add_best(r,125);original=copy.deepcopy(r);e=fastest(r)
  self.assertEqual(e['seconds'],117);self.assertEqual(e['source'],'paired_50m_segments')
  self.assertEqual(e['conflicts'][0]['type'],'reported_best_slower_than_verified_complete_100m')
  self.assertTrue(any(c['metric_ids']==['direct-current'] and c['seconds']==125 for c in e['evidence_candidates']))
  self.assertEqual(r,original)
 def test_faster_direct_can_win_and_ties_keep_all_sources(self):
  r=self.record();self.add_best(r,110);e=assess(r,'male')
  self.assertEqual(e['seconds'],110);self.assertEqual(e['source'],'screenshot_or_user_confirmed')
  self.assertEqual(e['conflicts'],[])
  r['metrics'][-1]['value']=117;e=fastest(r)
  self.assertGreaterEqual(sum(c['seconds']==117 for c in e['evidence_candidates']),2)
 def test_real_100m_segment_competes_with_direct_and_pairs(self):
  r=self.record();self.add_best(r,122)
  r['segments'].append(dict(segment_index=31,distance_m=100,duration_s=112,time_basis='active',includes_rest=False,stroke='freestyle'))
  self.assertEqual(fastest(r)['seconds'],112);self.assertEqual(fastest(r)['source'],'complete_100m_segment')
 def test_history_pb_is_not_current(self):
  r=self.record();self.add_best(r,90,'历史最佳100米')
  e=fastest(r);self.assertEqual(e['seconds'],117);self.assertEqual(e['excluded_evidence'][0]['reason'],'historical_or_other_date')
  self.assertEqual(e['comparison_scope']['record_id'],'synthetic-current')
 def test_different_person_session_date_stroke_excluded(self):
  for field,value in [('person_id','another'),('record_id','another-session'),('session_date','2001-01-01'),('stroke','breaststroke'),('scope','history')]:
   r=self.record();self.add_best(r,90);e=fastest(r,{'direct-current':{field:value}})
   self.assertEqual(e['seconds'],117);self.assertTrue(e['excluded_evidence'])
 def test_other_person_laps_do_not_inflate_coverage(self):
  r=self.record();e=fastest(r,{'segment:1':{'person_id':'another'}})
  self.assertNotEqual(e['lap_indices'],[1,2]);self.assertIn(1,e['unverified_lap_indices']);self.assertIn(2,e['unverified_lap_indices'])
 def test_rest_pair_does_not_suppress_other_pairs(self):
  r=self.record();r['segments'][0]['includes_rest']=True;e=fastest(r)
  self.assertIsNotNone(e);self.assertNotEqual(e['lap_indices'],[1,2]);self.assertIn(1,e['unverified_lap_indices'])
 def test_conflicting_direct_best_values_have_provenance(self):
  r=self.record();self.add_best(r,111);self.add_best(r,112,mid='second-direct');e=fastest(r)
  self.assertEqual(e['seconds'],111);self.assertTrue(any(x['type']=='reported_best_disagreement' for x in e['conflicts']))
  self.assertTrue(all('origin' in c for c in e['evidence_candidates'] if c['source']=='screenshot_or_user_confirmed'))
if __name__=='__main__':unittest.main()
