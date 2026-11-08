"""1.2.4 energy spacing and unitless SWOLF display regression."""
import copy,json,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import ImageDraw
from run import prepare
from render_card import render
from energy import display
class Display124Tests(unittest.TestCase):
 def test_energy_spaces_swolf_unitless_preserve_source(self):
  e=json.loads((Path(__file__).resolve().parents[1]/'references/synthetic.json').read_text(encoding='utf-8'))
  for m in e['record']['metrics']:
   if m['key']=='swolf':m.update(raw_value='88.6',raw_unit='分',value=88.6)
  r,rating,q,_=prepare(e);before=copy.deepcopy(r);calls=[];actual=ImageDraw.ImageDraw.text
  def spy(self,xy,text,*a,**k):calls.append(text);return actual(self,xy,text,*a,**k)
  with patch.object(ImageDraw.ImageDraw,'text',spy):_,layout=render(r,rating,'模拟训练')
  self.assertIn('88.6',calls);self.assertNotIn('88.6 分',calls)
  self.assertIn('310 千卡 / 1297 kJ',''.join(calls));self.assertIn('260 千卡 / 1088 kJ',''.join(calls))
  self.assertEqual(display({'key':'calories','status':'confirmed','value':330,'unit':'kcal'}),'330 千卡 / 1381 kJ')
  self.assertEqual(r,before);self.assertEqual(layout['overflow_fields'],[])
if __name__=='__main__':unittest.main()
