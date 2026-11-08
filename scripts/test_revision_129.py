import copy
import json
import unittest
from pathlib import Path

from dolphin import assess, fastest
from rating import grade

ROOT = Path(__file__).resolve().parents[1]

class Revision129Tests(unittest.TestCase):
    def sample(self):
        return copy.deepcopy(json.loads((ROOT / "references" / "synthetic.json").read_text(encoding="utf-8"))["record"])

    def test_all_five_axes_contribute_to_main_index(self):
        record = self.sample()
        result = grade(record, [], {"续航输出": 3, "强度投入": 3, "节奏稳定": 4, "技术经济性": 3.5})
        values = result["dimensions"]
        self.assertEqual(len(result["aggregate_axes"]), 5)
        self.assertEqual(result["mean_basis"], "five_dimension_evaluation_mean")
        self.assertEqual(result["mean"], sum(values.values()) / 5)
        self.assertEqual(result["stars"], 3.5)

    def test_fixed_adjacent_laps_make_complete_100m(self):
        record = self.sample()
        record["distance_m"] = 200
        record["segments"] = [
            {"segment_index": i+1, "distance_m": 50, "duration_s": s, "time_basis": "active",
             "stroke": "freestyle", "pool_length_m": 50, "includes_rest": False}
            for i, s in enumerate([53, 61, 63, 63])
        ]
        result = fastest(record)
        self.assertEqual(result["seconds"], 114)
        self.assertEqual(result["lap_indices"], [1, 2])
        self.assertEqual(result["pairing"], "fixed_nonoverlapping_from_first_lap")
        self.assertEqual(assess(record, "male")["level"], "银海豚")

    def test_reported_contiguous_laps_do_not_require_fabricated_rest_flag(self):
        record = self.sample()
        record["distance_m"] = 100
        record["segments"] = [
            {"segment_index": i+1, "distance_m": 50, "duration_s": s, "time_basis": "active",
             "stroke": "freestyle", "pool_length_m": 50}
            for i, s in enumerate([53, 61])
        ]
        result=fastest(record)
        self.assertEqual(result['seconds'],114)
        self.assertEqual(result['rest_status'],'not_reported')
        self.assertEqual(result['timing_interpretation'],'sum_of_reported_contiguous_lap_times')

if __name__ == "__main__":
    unittest.main()

