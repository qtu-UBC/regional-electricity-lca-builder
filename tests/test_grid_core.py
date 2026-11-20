import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from grid_core import validate_scenario, regional_lifecycle_ci, project_sensitivity, direct_factor_correction, parse_mix_csv
from openlca_bridge import plan

BASE = {"region":"classroom test", "year":2025,"boundary":"hypothetical", "evidence_status":"illustrative", "voltage":"high", "loss_fraction":0.05,
        "source_url":"", "mix":[{"technology":"hydro", "share":0.8, "ci_lifecycle_g_per_kwh":10}, {"technology":"natural_gas", "share":0.2,"ci_lifecycle_g_per_kwh":400}]}

class GridCoreTest(unittest.TestCase):
    def test_mix_passes(self):
        errors, warnings = validate_scenario(BASE)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)
    def test_weighted_ci_and_losses(self):
        self.assertAlmostEqual(regional_lifecycle_ci(BASE), (0.8*10+0.2*400)/0.95)
    def test_zero_share_missing_ci_allowed(self):
        mix = BASE["mix"] + [{"technology":"coal", "share":0, "ci_lifecycle_g_per_kwh":None}]
        self.assertAlmostEqual(regional_lifecycle_ci(dict(BASE,mix=mix)),(0.8*10+0.2*400)/0.95)
    def test_share_check(self):
        bad = dict(BASE, mix=[dict(BASE['mix'][0], share=0.7)])
        errors,_ = validate_scenario(bad)
        self.assertTrue(any('sum' in x for x in errors))
    def test_gwp_replacement(self):
        result = project_sensitivity(1000, 1000, 100, 20)
        self.assertAlmostEqual(result['updated_total_kg_co2e'], 920)
        self.assertAlmostEqual(result['percent_change'], -8)
    def test_reject_bad_project_data(self):
        with self.assertRaises(ValueError):
            project_sensitivity(10, 1000, 100, 20)
    def test_direct_correction(self):
        self.assertAlmostEqual(direct_factor_correction(90, 40, 10),60)
        with self.assertRaises(ValueError):
            direct_factor_correction(20,40,10)
    def test_mix_parse(self):
        rows = parse_mix_csv('technology,share\nhydro,0.8\nnatural_gas,0.2')
        self.assertEqual(rows[0]['technology'],'hydro')
    def test_plan_guard_missing_provider(self):
        with self.assertRaises(ValueError):
            plan(BASE, {'hydro':'aaa'})
    def test_plan_loss(self):
        entries, _ = plan(BASE, {'hydro':'aaa','natural_gas':'bbb'})
        self.assertAlmostEqual(entries[0][2],0.8/0.95)

if __name__ == '__main__':
    unittest.main()
