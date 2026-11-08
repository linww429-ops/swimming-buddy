import json,unittest
from pathlib import Path
from PIL import Image,features
from sc_font import find_sc_font
ROOT=Path(__file__).resolve().parents[1]
class CompactAssets(unittest.TestCase):
 def test_webp_and_all_sizes(self):
  self.assertTrue(features.check('webp'))
  data=json.loads((ROOT/'assets/animal-display-sizes.json').read_text(encoding='utf-8'));self.assertEqual(len(data),10)
  for name,row in data.items():
   with Image.open(ROOT/'assets/animals'/name) as im:self.assertEqual(list(im.size),row['display_sizes']['1']);self.assertEqual(im.mode,'RGBA')
   self.assertEqual(row['display_sizes']['2'][1],670)
 def test_bundled_complete_sc_face(self):
  path,index=find_sc_font();self.assertEqual(Path(path).name,'NotoSansCJKsc-Regular.otf');self.assertEqual(index,0)
