import copy,json,tempfile,unittest
from pathlib import Path
from dolphin import fastest,assess,TABLE
from image_review import review
from run import execute,prepare
ROOT=Path(__file__).resolve().parents[1]

def example():
    e=json.loads((ROOT/'references/synthetic.json').read_text(encoding='utf-8'))
    r=e['record'];r['source']['library_file_ids']=['libfile_syntheticA','libfile_syntheticB','libfile_syntheticC']
    r['segments']=[dict(segment_index=i,distance_m=50,duration_s=57 if i==1 else 60 if i==2 else 64,
                        time_basis='active',stroke='freestyle',pool_length_m=50,includes_rest=False)
                   for i in range(1,31) if i not in (6,7)]
    e['adult_group']='male'
    e['image_review']=[dict(image_id=x,reviewed=True,regions=['synthetic region'],unreadable_regions=[])
                       for x in r['source']['library_file_ids']]
    e['image_review'][1]['unreadable_regions']=['synthetic obscured laps 6 and 7']
    return e

class Revision1211(unittest.TestCase):
    def test_partial_pairs_keep_known_best_and_coverage(self):
        e=example();r=fastest(e['record'])
        self.assertEqual(r['seconds'],117);self.assertEqual(r['lap_indices'],[1,2])
        self.assertEqual(r['unverified_lap_indices'],[5,6,7,8])
        self.assertEqual(r['fastest_scope'],'verified_pairs_only')
        self.assertEqual(r['coverage'],26/30)
        self.assertEqual(assess(e['record'],'male')['level'],'银海豚')

    def test_gap_never_reindexed_or_crossed(self):
        r=example()['record'];r['segments']=[s for s in r['segments'] if s['segment_index'] in (2,3)]
        self.assertIsNone(fastest(r))

    def test_rest_mismatch_or_conflict_affects_only_local_pair(self):
        r=example()['record'];r['segments'][0]['includes_rest']=True
        self.assertNotEqual(fastest(r)['lap_indices'],[1,2])
        r=example()['record'];duplicate=copy.deepcopy(r['segments'][0]);duplicate['duration_s']=49
        r['segments'].append(duplicate)
        self.assertNotEqual(fastest(r)['lap_indices'],[1,2])

    def test_identical_duplicate_lap_is_one_observation(self):
        r=example()['record'];original=fastest(r);r['segments'].append(copy.deepcopy(r['segments'][0]))
        self.assertEqual(fastest(r),original)

    def test_mixed_session_pairs_must_have_same_real_stroke(self):
        r=example()['record'];r['stroke']='mixed'
        self.assertEqual(fastest(r)['seconds'],117)
        r['segments'][0]['stroke']='breaststroke'
        self.assertNotEqual(fastest(r)['lap_indices'],[1,2])

    def test_unknown_group_and_existing_female_threshold(self):
        r=example()['record'];self.assertEqual(assess(r,None)['level'],'待评')
        limits=TABLE['thresholds']['freestyle']['female'];expected=next(k+'海豚' for k,v in limits.items() if 117<=v)
        self.assertEqual(assess(r,'female')['level'],expected)

    def test_all_complete_100m_sources_are_compared(self):
        r=example()['record'];r['segments'].append(dict(distance_m=100,duration_s=120,time_basis='active',includes_rest=False,stroke='freestyle'))
        self.assertEqual(fastest(r)['source'],'paired_50m_segments')
        self.assertEqual(fastest(r)['seconds'],117)
        self.assertTrue(any(c['source']=='complete_100m_segment' and c['seconds']==120 for c in fastest(r)['evidence_candidates']))

    def test_image_review_requires_all_images(self):
        e=example();self.assertEqual(len(review(e)['images']),3)
        e['image_review'].pop()
        with self.assertRaisesRegex(ValueError,'遗漏'):review(e)

    def test_cross_image_conflict_preserves_input_and_stops(self):
        e=example();m=next(x for x in e['record']['metrics'] if x['key']=='heart_rate')
        m['source']['image_id']='libfile_syntheticA';other=copy.deepcopy(m)
        other['id']='synthetic-conflict';other['source']['image_id']='libfile_syntheticB';other['value']+=10
        e['record']['metrics'].append(other);prior=copy.deepcopy(e)
        with self.assertRaisesRegex(ValueError,'跨图'):prepare(e)
        self.assertEqual(e,prior)

    def test_duplicate_sources_preserved_and_displayed_once_both_sizes(self):
        e=example();m=next(x for x in e['record']['metrics'] if x['key']=='heart_rate' and x['qualifier']=='average')
        m['source']['image_id']='libfile_syntheticA';other=copy.deepcopy(m)
        other['id']='synthetic-second-observation';other['source']['image_id']='libfile_syntheticB'
        e['record']['metrics'].append(other)
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);report=execute(e,path/'ledger',path/'out',no_save=True)
            self.assertFalse((path/'ledger').exists());self.assertEqual(report['version'],'1.2.15-rc.1+fresh-quips.20261108')
            self.assertEqual(report['image_review']['status'],'host_attested')
            self.assertEqual(len(report['raw_record']['metrics']),len(e['record']['metrics']))
            selected=[x for x in report['raw_record']['metrics'] if x['id'] in report['layout']['displayed_metric_ids']]
            self.assertEqual(sum(x['key']=='heart_rate' and x['qualifier']=='average' for x in selected),1)
            self.assertTrue(any(x['key']=='swolf' for x in selected))
            from PIL import Image
            with Image.open(path/'out/today-phone.png') as im:self.assertEqual(im.size,(1280,1840))
            with Image.open(path/'out/today-full.png') as im:self.assertEqual(im.size,(2560,3680))

if __name__=='__main__':unittest.main()
