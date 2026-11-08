import copy,hashlib,json,unittest
from pathlib import Path
from unittest.mock import patch
from presentation import choose,load_library,ASSETS
ROOT=Path(__file__).resolve().parents[1]
class NoGoggles(unittest.TestCase):
 def test_all_current_library_assets_have_manual_qa_and_matching_hash(self):
  lib=load_library();qa=json.loads((ASSETS/'NO_GOGGLES_QA.json').read_text(encoding='utf-8'))
  self.assertEqual(len(lib['poses']),10);self.assertEqual(len(qa['assets']),10)
  for pose in lib['poses']:
   self.assertIs(pose['goggles'],False);self.assertTrue(pose['qa_approved'])
   self.assertEqual(hashlib.sha256((ASSETS/pose['path']).read_bytes()).hexdigest(),pose['sha256'])
 def test_selection_rejects_unverified_or_goggled_assets(self):
  record={'record_id':'synthetic-asset-check','metrics':[]};rating={'mean':3.3,'stars':3.5,'state_tags':['normal']}
  lib=load_library()
  for value in (None,True):
   modified=copy.deepcopy(lib)
   for p in modified['poses']:p['goggles']=value
   with patch('presentation.load_library',return_value=modified):
    with self.assertRaises(ValueError):choose(record,rating)
if __name__=='__main__':unittest.main()
