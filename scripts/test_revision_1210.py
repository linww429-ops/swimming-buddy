"""Synthetic no-save regression for sourced metrics and fixed-template evaluation."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import ImageDraw
from run import execute
from rating import grade,DIMENSIONS
from dolphin import assess

ROOT=Path(__file__).resolve().parents[1]

class Revision1210(unittest.TestCase):
    def sample(self):
        e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))
        e.pop('dimensions',None)
        e['person_id']='isolated-regression';e['owner_confirmed']=False
        return e

    def run_case(self,e):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);ledger=base/'ledger'
            result=execute(e,ledger,base/'out',no_save=True)
            self.assertFalse(ledger.exists());self.assertFalse(result['saved'])
            self.assertEqual(result['warnings'],[])
            self.assertTrue(result['layout']['radar_drawn'])
            self.assertEqual(len(result['rating']['dimensions']),5)
            self.assertAlmostEqual(result['rating']['mean'],sum(result['rating']['dimensions'].values())/5)
            return result

    def test_complete_preserves_observations(self):
        e=self.sample();r=self.run_case(e)
        original={m['id']:m for m in e['record']['metrics']}
        self.assertTrue(all(m==original[m['id']] for m in r['raw_record']['metrics'] if m['id'] in original))

    def test_partial_preserves_radar_and_no_fabricated_metrics(self):
        e=self.sample();metric=copy.deepcopy(next(m for m in e['record']['metrics'] if m['key']=='calories'))
        e['record']={'mode':'demo','metrics':[metric]}
        r=self.run_case(e)
        self.assertEqual(r['raw_record']['metrics'],[metric])
        self.assertEqual(r['layout']['displayed_metric_count'],0)
        self.assertEqual(r['layout']['dolphin_caption'],'')
        self.assertTrue(all(v['kind']=='inferred' for v in r['rating']['dimension_provenance'].values()))

    def test_empty_and_uncertain_do_not_generate(self):
        for metrics in [[],[{**self.sample()['record']['metrics'][0],'status':'missing','value':None,'raw_value':''}]]:
            e=self.sample();e['record']={'mode':'demo','metrics':metrics}
            with tempfile.TemporaryDirectory() as td:
                with self.assertRaisesRegex(ValueError,'no_valid_activity_data'):
                    execute(e,Path(td)/'ledger',Path(td)/'out',no_save=True)
                self.assertFalse((Path(td)/'out').exists())

    def test_user_two_stars_only_this_session(self):
        e=self.sample();e['dimensions']=dict(zip(DIMENSIONS,[3,2,3,3,4]));e['subjective_effort']=2
        r=self.run_case(e)
        self.assertEqual(list(r['rating']['dimensions'].values()),[3,2,3,3,4])
        self.assertEqual(r['rating']['mean'],3)
        self.assertEqual(r['rating']['dimension_provenance']['强度投入']['kind'],'user_rating')
        self.assertNotEqual(grade(self.sample()['record'],[])['dimensions']['强度投入'],2)

    def test_dolphin_complete_100m_and_unknown_group(self):
        e=self.sample();r=e['record'];r['segments']=[{'distance_m':100,'duration_s':x,'time_basis':'active'} for x in [125,110,119]]
        self.assertEqual(assess(r,'male')['seconds'],110)
        self.assertEqual(assess(r,'male')['level'],'银海豚')
        self.assertEqual(assess(r,None)['level'],'待评')
        self.assertEqual(self.run_case(e)['layout']['dolphin_caption'],'')
        e['adult_group']='male'
        self.assertTrue(self.run_case(e)['layout']['dolphin_caption'])

    def test_effort_label(self):
        e=self.sample();m=copy.deepcopy(e['record']['metrics'][0]);m.update(id='effort-source',key='effort',qualifier='unspecified',label='Effort',raw_value='4',value=4,unit='')
        e['record']['metrics']=[e['record']['metrics'][0],m]
        texts=[];original=ImageDraw.ImageDraw.text
        def capture(draw,xy,text,*args,**kwargs):
            texts.append(text);return original(draw,xy,text,*args,**kwargs)
        with patch.object(ImageDraw.ImageDraw,'text',capture):self.run_case(e)
        self.assertIn('运动强度评级',texts);self.assertNotIn('Effort',texts)

    def test_effort_hero_label(self):
        e=self.sample();m=copy.deepcopy(e['record']['metrics'][0]);m.update(id='effort-only',key='effort',qualifier='unspecified',label='Effort',raw_value='2',value=2,unit='')
        e['record']={'mode':'demo','metrics':[m]}
        texts=[];original=ImageDraw.ImageDraw.text
        def capture(draw,xy,text,*args,**kwargs):
            texts.append(text);return original(draw,xy,text,*args,**kwargs)
        with patch.object(ImageDraw.ImageDraw,'text',capture):self.run_case(e)
        self.assertIn('运动强度评级',texts);self.assertNotIn('Effort',texts)

    def test_pool_length_alone_is_not_activity(self):
        e=self.sample();e['record']={'mode':'demo','metrics':[next(m for m in e['record']['metrics'] if m['key']=='pool_length')]}
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError,'no_valid_activity_data'):
                execute(e,Path(td)/'ledger',Path(td)/'out',no_save=True)

if __name__=='__main__':unittest.main()
