"""Synthetic display-only regressions for 1.2.3; no ledger writes."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import ImageDraw
from run import prepare
from render_card import render,TEMPLATE
from dolphin import assess

class DisplayTests(unittest.TestCase):
 def test_chinese_units_clean_labels_and_fixed_footer(self):
  e=json.loads((Path(__file__).resolve().parents[1]/'references/synthetic.json').read_text(encoding='utf-8'))
  e['adult_group']='male';e['fastest_100m']={'seconds':98,'stroke':'freestyle','source':'screenshot'}
  for m in e['record']['metrics']:
   if m['key'] in ('distance','pool_length'):m['raw_unit']='m'
   if m['key']=='pace':m['raw_unit']='/100m';m['label']+='（计算）'
   if m['key'] in ('stroke_count','stroke_rate','swolf'):m['label']+='（计算）'
  r,rating,q,_=prepare(e);original=copy.deepcopy(r);rating['dolphin']=assess(r,'male')
  calls=[];actual=ImageDraw.ImageDraw.text
  def spy(self,xy,text,*a,**k):calls.append((xy,text));return actual(self,xy,text,*a,**k)
  with patch.object(ImageDraw.ImageDraw,'text',spy):im,layout=render(r,rating,'模拟训练')
  labels=[s for _,s in calls]
  self.assertTrue(all('（计算）' not in s for s in labels))
  self.assertIn('/100米',labels);self.assertIn('米',labels)
  self.assertTrue(any('泳池长度' in s and '米' in s for s in labels))
  self.assertIn('最快100米配速 1′38″',labels)
  self.assertEqual(r,original)
  self.assertEqual(layout['time_strip_dividers'],[454,845])
  self.assertEqual(layout['banana_position'],'after_text')
  self.assertEqual(layout['banana_shape_version'],'gentle-curve-v1')
  self.assertFalse(layout['calculation_suffix_visible'])
  self.assertEqual(layout['parameter_slots'],[list(x) for x in TEMPLATE['parameter_slots']])
  self.assertIn('泳后别忘了来根香蕉',labels)
if __name__=='__main__':unittest.main()
