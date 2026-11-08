import json,unittest
from pathlib import Path
from run import prepare
from render_card import render,TEMPLATE
class ScaleAlignment(unittest.TestCase):
 def test_fixed_scale_coordinates(self):
  self.assertEqual(TEMPLATE['scale_line_y'],1605);self.assertEqual(TEMPLATE['scale_label_x'],65);self.assertEqual(TEMPLATE['scale_label_size'],19);self.assertEqual(TEMPLATE['scale_star_offset'],16);self.assertEqual(TEMPLATE['scale_name_offset'],46)
 def test_phone_center_aligned(self):self.check(1)
 def test_hd_center_aligned(self):self.check(2)
 def check(self,scale):
  e=json.loads((Path(__file__).resolve().parents[1]/'references/synthetic.json').read_text(encoding='utf-8'));r,g,q,d=prepare(e);im,l=render(r,g,'对齐核验',scale)
  self.assertEqual(l['scale_line_y'],1605);self.assertEqual(l['scale_label_y']+l['scale_label_height']/2,1605);self.assertLessEqual(abs(round(l['scale_label_y']*scale)+l['scale_label_height']*scale/2-1605*scale),.5)
