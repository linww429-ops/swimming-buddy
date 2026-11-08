import copy,json,unittest
from pathlib import Path
from rating import band,half
from presentation import choose
from render_card import render
ROOT=Path(__file__).resolve().parents[1]
class Bands(unittest.TestCase):
 def test_existing_thresholds_receive_raw_mean(self):
  for mean,level in [(1.49,1),(1.5,2),(2.49,2),(2.5,3),(3.3,3),(3.49,3),(3.5,4),(4.49,4),(4.5,5)]:
   self.assertEqual(band(mean),level)
  self.assertEqual(half(3.3),3.5)
 def test_display_and_asset_use_same_original_mean(self):
  e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'));r=e['record']
  score={'stars':3.5,'mean':3.3,'state_tags':['normal'],'dimensions':{'续航输出':3,'强度投入':3.5,'节奏稳定':4,'技术经济性':3.5,'恢复从容度':2.5}}
  prior=copy.deepcopy(score);visual=choose(r,score)
  self.assertEqual(visual['level'],3);self.assertEqual(visual['animal'],'企鹅');self.assertEqual(visual['level_name'],'养生游')
  im,layout=render(r,score,'合成档位测试',decoration=visual['decoration_path'])
  self.assertEqual(layout['display_stars'],3.5);self.assertEqual(layout['dimension_mean'],3.3);self.assertEqual(score,prior)
if __name__=='__main__':unittest.main()
