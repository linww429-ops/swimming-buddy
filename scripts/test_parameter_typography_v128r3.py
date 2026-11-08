import copy,json,unittest
from pathlib import Path
from PIL import Image,ImageChops
from render_card import render,TEMPLATE
from run import prepare
BASE=Path(__file__).resolve().parents[1]
class ParameterTypography(unittest.TestCase):
 def setUp(self):
  self.e=json.loads((BASE/'references/synthetic.json').read_text(encoding='utf-8'));self.e.pop('dimensions',None);self.e.pop('quip',None)
 def draw(self,total=187,active=160,scale=1):
  e=copy.deepcopy(self.e)
  for m in e['record']['metrics']:
   if m['key']=='calories':m['value']=total if m['qualifier']=='total' else active;m['raw_value']=str(m['value'])
  r,g,q,d=prepare(e);return render(r,g,'字体固定测试',scale)
 def test_fixed_sizes_and_positions(self):
  self.assertEqual(TEMPLATE['parameter_label_size'],22);self.assertEqual(TEMPLATE['parameter_value_size'],28);self.assertEqual(TEMPLATE['energy_value_size'],28);self.assertEqual(TEMPLATE['energy_unit_size'],22)
  self.assertEqual(TEMPLATE['parameter_slots'],tuple((657+(i%2)*278,858+(i//2)*167) for i in range(6)));self.assertEqual(TEMPLATE['parameter_size'],(259,148));self.assertEqual(TEMPLATE['parameter_value_offset'],(22,83))
 def test_today_both_numbers_28(self):
  im,l=self.draw();self.assertEqual(len(l['energy_typography']),2)
  for t in l['energy_typography']:
   self.assertEqual(t['number_size'],28);self.assertEqual(t['unit_size'],22);self.assertEqual(t['rendered_number_px'],31);self.assertEqual(t['rendered_unit_px'],24);self.assertLessEqual(t['single_line_width'],t['available_width']);self.assertEqual(t['lines'],1);self.assertFalse(t['auto_shrink'])
 def test_long_energy_wraps_no_shrink(self):
  im,l=self.draw(1234,1000)
  for t in l['energy_typography']:self.assertEqual(t['lines'],2);self.assertEqual(t['number_size'],28);self.assertFalse(t['auto_shrink'])
 def test_hd_exact_double_type_sizes(self):
  im,l=self.draw(scale=2);self.assertEqual(im.size,(2560,3680))
  for t in l['energy_typography']:self.assertEqual(t['rendered_number_px'],62);self.assertEqual(t['rendered_unit_px'],48)
 def test_no_parameter_geometry_change_sparse(self):
  self.e['record']['metrics']=[m for m in self.e['record']['metrics'] if m['key'] in ('distance','time','calories')]
  r,g,q,d=prepare(self.e);im,l=render(r,g,'字体固定测试');self.assertEqual(l['parameter_slots'],[list(x) for x in TEMPLATE['parameter_slots']]);self.assertEqual(l['parameter_value_size'],28)
 def test_energy_spacing_kept(self):
  from energy import display
  m=next(x for x in self.e['record']['metrics'] if x['key']=='calories');m.update(value=187,raw_value='187',unit='kcal');self.assertEqual(display(m),'187 千卡 / 782 kJ')
