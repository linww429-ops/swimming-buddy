"""Synthetic integration checks for fresh copy; no real ledger is read or saved."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageChops
from personal_quip import select,validate_authored_quip
from presentation import choose,load_library
from run import execute

ROOT=Path(__file__).resolve().parents[1]

class FreshQuips(unittest.TestCase):
 def sample(self):
  return json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))

 def test_missing_copy_stops_before_private_reads_outputs_or_save(self):
  e=self.sample();e.pop('quip',None)
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)
   with patch('run.read_ledger',side_effect=AssertionError('private read')):
    with self.assertRaisesRegex(ValueError,'missing_authored_quip'):
     execute(e,p/'ledger',p/'out',no_save=True)
   self.assertFalse((p/'out').exists());self.assertFalse((p/'ledger').exists())

 def test_invalid_copy_is_not_replaced_by_template(self):
  for text in ['', ' ', 'x'*46, '一行\n两行', '制表\t文本', 5, False]:
   with self.subTest(text=text):
    with self.assertRaises(ValueError):validate_authored_quip(text)

 def test_pose_selection_does_not_need_any_library_quips(self):
  library=load_library();library['quips']=[]
  with patch('presentation.load_library',return_value=library):
   p=choose({'record_id':'synthetic-no-copy-pool','metrics':[]},
            {'mean':3.3,'stars':3.5,'state_tags':['normal']},include_quip=False)
  self.assertTrue(p['pose_id']);self.assertEqual(p['quip'],'')

 def test_rerender_updates_line_when_feeling_changes(self):
  r=self.sample()['record'];first='1500米绕完，池壁熟得像楼下便利店。'
  old=select(r,[],'self',{},override=first)
  recent=[dict(old,person_id='self',record_id=r['record_id'])]
  second='你说最后腿酸，1500米的账果然要腿来结。'
  r=copy.deepcopy(r);r['metrics'].append({'key':'post_session_feeling','value':'最后腿酸'})
  result=select(r,recent,'self',{},override=second)
  self.assertEqual(result['quip'],second);self.assertNotEqual(result['quip_context_token'],old['quip_context_token'])

 def test_changing_authored_line_does_not_change_scores_pose_or_other_pixels(self):
  e=self.sample();e['feedback']={'post_session_feeling':'前面轻松，最后腿酸'}
  first='1500米绕完，池壁熟得像楼下便利店。'
  second='前面轻松最后腿酸，1500米还会分期收账。'
  with tempfile.TemporaryDirectory() as td:
   p=Path(td);reports=[]
   library=load_library();library['quips']=[]
   with patch('presentation.load_library',return_value=library):
    for i,text in enumerate([first,second]):
     e['quip']=text;reports.append(execute(e,p/'ledger',p/str(i),no_save=True))
   a,b=reports
   self.assertEqual(a['rating'],b['rating'])
   self.assertEqual(a['raw_record'],b['raw_record'])
   self.assertEqual(a['presentation']['pose_id'],b['presentation']['pose_id'])
   for result,text in zip(reports,[first,second]):
    self.assertEqual(result['quip'],text);self.assertFalse(result['presentation']['template_fallback'])
    self.assertEqual(result['presentation']['quip_generation_mode'],'host_authored')
   for name in ['today-phone.png','today-full.png']:
    with Image.open(p/'0'/name) as x,Image.open(p/'1'/name) as y:
     self.assertEqual(x.size,y.size)
     box=ImageChops.difference(x.convert('RGB'),y.convert('RGB')).getbbox()
     self.assertIsNotNone(box)
     # The authored line is at the bottom; the scores and layout above it
     # must remain pixel-identical for both output sizes.
     self.assertGreater(box[1],x.height*.75)
   self.assertFalse((p/'ledger').exists())

if __name__=='__main__':unittest.main()
