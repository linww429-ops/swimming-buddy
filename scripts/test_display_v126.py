"""Synthetic records test real/demo rendering; never saved as real sessions."""
import json,unittest,copy
from pathlib import Path
from unittest.mock import patch
from PIL import ImageDraw
from run import prepare
from render_card import render
class Display126Tests(unittest.TestCase):
 def test_real_demo_labels(self):
  e=json.loads((Path(__file__).resolve().parents[1]/'references/synthetic.json').read_text(encoding='utf-8'));r,rating,_,_=prepare(e)
  for mode in ('real','demo'):
   r['mode']=mode;calls=[];actual=ImageDraw.ImageDraw.text
   def spy(self,xy,text,*a,**kw):calls.append(text);return actual(self,xy,text,*a,**kw)
   with patch.object(ImageDraw.ImageDraw,'text',spy):_,layout=render(r,rating,'内部合成分支测试')
   self.assertEqual('演示数据' in calls,mode=='demo');self.assertEqual(layout['demo_label_visible'],mode=='demo')
 def test_distance_glyph_gap(self):
  e=json.loads((Path(__file__).resolve().parents[1]/'references/synthetic.json').read_text(encoding='utf-8'));r,rating,_,_=prepare(e)
  for distance in ('50','500','1,500','10,000'):
   for scale in (1,2):
    for m in r['metrics']:
     if m['key']=='distance':m['raw_value']=distance
    calls=[];actual=ImageDraw.ImageDraw.text
    def spy(self,xy,text,*a,**kw):
     if text in (distance,'米'):
      calls.append((text,self.textbbox(xy,text,font=kw['font'],anchor=kw.get('anchor'))))
     return actual(self,xy,text,*a,**kw)
    with patch.object(ImageDraw.ImageDraw,'text',spy):_,layout=render(r,rating,'模拟训练',scale)
    val=next(bb for t,bb in calls if t==distance);unit=next(bb for t,bb in calls if t=='米')
    self.assertAlmostEqual((unit[0]-val[2])/scale,12,delta=.5);self.assertEqual(layout['overflow_fields'],[])
if __name__=='__main__':unittest.main()
