import copy,json,tempfile,unittest
from pathlib import Path
import quip_profile as qp
from personal_quip import select
from run import execute
ROOT=Path(__file__).resolve().parents[1]
class CopyTests(unittest.TestCase):
 def sample(self):
  e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'));return e
 def test_first_skip_change_clear_and_version_conflict(self):
  with tempfile.TemporaryDirectory() as d:
   s=qp.read(d,'self');self.assertEqual(s['status'],'unasked')
   s=qp.append(d,'self',qp.resolve(s,{'action':'skip'}),0);self.assertEqual(qp.read(d,'self')['status'],'skipped')
   s=qp.append(d,'self',qp.resolve(s,{'action':'set','reference':'学生','theme':'study'}),s['version'])
   self.assertEqual(s['reference'],'学生')
   s=qp.append(d,'self',qp.resolve(s,{'action':'set','reference':'爱画画','theme':'creative'}),s['version'])
   self.assertEqual(s['theme'],'creative')
   with self.assertRaises(ValueError):qp.append(d,'self',s,0)
   s=qp.append(d,'self',qp.resolve(s,{'action':'clear'}),s['version']);self.assertIsNone(s['reference']);self.assertEqual(s['status'],'skipped')
 def test_person_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   qp.append(d,'self',qp.resolve(qp.empty('self'),{'action':'skip'}),0)
   with self.assertRaises(ValueError):qp.read(d,'someone')
 def test_theme_does_not_replace_authored_copy(self):
  r=self.sample()['record'];text='1500米绕完，池壁熟得像楼下便利店。'
  for theme in ('general','study','creative','technical','service','other'):
   c=select(r,[],'self',qp.empty('self'),{'theme':theme},override=text)
   self.assertEqual(c['quip'],text);self.assertEqual(c['quip_generation_mode'],'host_authored')
   self.assertFalse(c['template_fallback'])
 def test_recent_duplicate_requests_rewrite_same_session_can_rerender(self):
  r=self.sample()['record'];r['record_id']='one';pref=qp.empty('self')
  text='1500米绕完，池壁熟得像楼下便利店。';c=select(r,[],'self',pref,override=text)
  recent=[dict(c,person_id='self',record_id='one')]
  self.assertEqual(select(r,recent,'self',pref,override=text)['quip'],text)
  r['record_id']='two'
  with self.assertRaisesRegex(ValueError,'repeated_authored_quip'):select(r,recent,'self',pref,override=text)
  other='最后一趟还想提速，胳膊当场申请调休。'
  self.assertEqual(select(r,recent,'self',pref,override=other)['quip'],other)
  self.assertEqual(select(r,recent,'someone',pref,override=text)['quip'],text)
 def test_no_template_without_authored_copy_and_no_background_interpolation(self):
  r={'record_id':'sparse','metrics':[]};p=qp.resolve(qp.empty('self'),{'action':'set','reference':'自选背景不应原样贴卡','theme':'other'})
  with self.assertRaisesRegex(ValueError,'missing_authored_quip'):select(r,[],'self',p)
  text='今天只看得清这一项，泳池把其余剧情打了码。'
  q=select(r,[],'self',p,override=text)['quip'];self.assertEqual(q,text);self.assertNotIn(p['reference'],q)
 def test_demo_never_reads_or_writes_profile_scores_and_pose_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   e=self.sample();p=Path(d);(p/'ledger').mkdir();(p/'ledger/.owner.json').write_text('{"person_id":"stranger"}',encoding='utf-8')
   a=execute(e,p/'ledger',p/'a',no_save=True,phone_only=True)
   e.update(persona={'confirmed':True,'reference':'爱画画','theme':'creative'},persona_action='set')
   b=execute(e,p/'ledger',p/'b',no_save=True,phone_only=True)
   self.assertEqual(a['rating'],b['rating']);self.assertEqual(a['presentation']['pose_id'],b['presentation']['pose_id'])
   self.assertFalse((p/'ledger/.quip-profiles').exists());self.assertFalse(b['persona_state']['optional_prompt'])
   e.pop('persona');e['persona_action']='skip';c=execute(e,p/'ledger',p/'c',no_save=True,phone_only=True)
   self.assertFalse(c['persona_state']['optional_prompt'])
 def test_real_synthetic_save_profile_and_dedup(self):
  with tempfile.TemporaryDirectory() as d:
   e=self.sample();e['record']['mode']='real';e.update(owner_confirmed=True,persona={'confirmed':True,'theme':'study','reference':'学生'},persona_action='set')
   p=Path(d);a=execute(e,p/'ledger',p/'a',phone_only=True);b=execute(e,p/'ledger',p/'b',phone_only=True)
   self.assertTrue(a['saved']);self.assertFalse(b['saved']);self.assertEqual(a['ledger_version'],b['ledger_version'])
   self.assertEqual(qp.read(p/'ledger','self')['version'],1)
   self.assertEqual(a['quip'],b['quip']);self.assertNotIn('persona',a['raw_record'])
 def test_context_requires_explicit_confirmation(self):
  with self.assertRaises(ValueError):qp.validate_context({'reference':'猜测'})
 def test_partial_preference_actions_save_without_training(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);e=self.sample();e['record']['mode']='real';e['record']['distance_m']=None;e['owner_confirmed']=True
   for action in ('offered','skip','clear'):
    e['persona_action']=action;r=execute(e,p/'ledger',p/action,phone_only=True)
    self.assertFalse(r['saved']);self.assertEqual(r['ledger_version'],0)
    self.assertTrue(r['persona_state']['persisted']);self.assertFalse(r['persona_state']['optional_prompt'])
   self.assertFalse(list((p/'ledger').glob('v*.json')))
   self.assertEqual(qp.read(p/'ledger','self')['status'],'skipped')
 def test_failed_preference_write_never_returns_remembered(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);e=self.sample();e['record']['mode']='real';e['record']['distance_m']=None;e.update(owner_confirmed=True,persona_action='skip')
   with patch('quip_profile.append',side_effect=OSError('synthetic write failure')):
    with self.assertRaises(OSError):execute(e,p/'ledger',p/'out',phone_only=True)
   report=json.loads((p/'out/report.json').read_text(encoding='utf-8'))
   self.assertFalse(report['persona_state']['persisted']);self.assertEqual(report['status'],'preference_save_failed')
 def test_demo_does_not_call_private_readers(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as d:
   with patch('run.read_ledger',side_effect=AssertionError('private read')),patch('quip_profile.read',side_effect=AssertionError('private preference read')):
    execute(self.sample(),Path(d)/'ledger',Path(d)/'out',no_save=True,phone_only=True)
 def test_discomfort_requires_fresh_care_review_not_fixed_care_pool(self):
  r={'record_id':'care','discomfort':True,'metrics':[]};text='你说肩膀不舒服，今天这趟先把自己送回岸边。'
  with self.assertRaisesRegex(ValueError,'care_authored_quip_required'):
   select(r,[],'self',qp.empty('self'),override=text)
  c=select(r,[],'self',qp.empty('self'),override=text,tone='care')
  self.assertEqual(c['quip'],text);self.assertEqual(c['quip_tone'],'care');self.assertFalse(c['template_fallback'])
 def test_split_data_never_silently_generates_template_copy(self):
  r={'distance_m':200,'metrics':[],'segments':[dict(segment_index=i+1,distance_m=50,time_basis='active',includes_rest=False,duration_s=t) for i,t in enumerate([70,70,60,60])]}
  with self.assertRaisesRegex(ValueError,'missing_authored_quip'):select(r,[],'self',qp.empty('self'))
  text='后半程省了20秒，胳膊像突然看见了下班铃。'
  self.assertEqual(select(r,[],'self',qp.empty('self'),override=text)['quip'],text)
if __name__=='__main__':unittest.main()
