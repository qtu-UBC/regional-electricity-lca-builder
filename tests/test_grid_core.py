import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from grid_core import (
    validate_scenario, parse_mix_csv, dump_supply_mix_csv,
    scenario_documentation_report,
)
from archive.legacy.openlca_bridge import plan


BASE = {
    "region": "classroom test",
    "year": 2025,
    "boundary": "hypothetical",
    "evidence_status": "illustrative",
    "voltage": "high",
    "loss_fraction": 0.05,
    "source_url": "",
    "mix": [
        {"technology": "hydro", "share": 0.8, "source_url": "", "notes": "Example"},
        {"technology": "natural_gas", "share": 0.2, "source_url": "", "notes": "Example"},
    ],
}


class GridCoreTest(unittest.TestCase):
    def test_foreground_documentation_has_no_emission_factor_columns(self):
        rows = [
            {"technology": "hydro", "share": 0.8,
             "source_url": "https://example.org/hydro", "notes": "Example"},
            {"technology": "wind", "share": 0.2,
             "source_url": "", "notes": "Example"},
        ]
        csv_text = dump_supply_mix_csv(rows)
        self.assertEqual(csv_text.splitlines()[0],
                         "technology,share,source_url,notes")
        self.assertNotIn("ci_lifecycle", csv_text.lower())
        report = scenario_documentation_report(
            dict(BASE, mix=rows), [],
            ["Generator shares are unverified."],
            {"hydro": {
                "process_id": "test-id", "process_name": "TEST hydro",
                "location": "Canada, Ontario",
                "selection_reason": "Matching technology and geography",
            }},
        )
        self.assertIn("Matching technology and geography", report)
        self.assertIn("Generator shares are unverified.", report)
        self.assertNotIn("Calculated scenario CI:", report)
        self.assertIn("\n## Generation / supply shares\n", report)

    def test_arithmetic_and_provenance_warnings(self):
        errors, warnings = validate_scenario(BASE)
        self.assertEqual(errors, [])
        self.assertTrue(any("Hypothetical" in w for w in warnings))
        self.assertTrue(any("source URL missing" in w for w in warnings))

    def test_share_sum_check(self):
        invalid = dict(BASE, mix=[dict(BASE["mix"][0], share=0.7)])
        errors, _ = validate_scenario(invalid)
        self.assertTrue(any("sum" in e for e in errors))

    def test_duplicate_and_out_of_range_shares(self):
        invalid = dict(BASE, mix=[
            {"technology": "hydro", "share": 1.2},
            {"technology": "hydro", "share": -0.2},
        ])
        errors, _ = validate_scenario(invalid)
        self.assertTrue(any("Duplicate" in e for e in errors))
        self.assertTrue(any("between 0 and 1" in e for e in errors))

    def test_generation_mix_warning(self):
        _, warnings = validate_scenario(dict(BASE, boundary="generation"))
        self.assertTrue(any("consumption mix" in w for w in warnings))

    def test_parse_share_csv(self):
        rows = parse_mix_csv(
            "technology,share,source_url,notes\n"
            "hydro,0.8,https://example.org/hydro,run of river\n"
            "natural_gas,0.2,,assumed\n"
        )
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["technology"], "hydro")
        self.assertEqual(rows[0]["source_url"], "https://example.org/hydro")
        self.assertNotIn("ci_lifecycle_g_per_kwh", rows[0])

    def test_reject_obsolete_gwp_csv(self):
        with self.assertRaisesRegex(ValueError, "obsolete carbon-intensity/GWP"):
            parse_mix_csv(
                "technology,share,ci_lifecycle_g_per_kwh\n"
                "hydro,1.0,20\n"
            )

    def test_parse_non_numeric_share(self):
        with self.assertRaisesRegex(ValueError, "share must be numeric"):
            parse_mix_csv("technology,share\nhydro,not-a-number\n")

    def test_legacy_plan_guards_missing_provider(self):
        with self.assertRaises(ValueError):
            plan(BASE, {"hydro": "aaa"})

    def test_legacy_plan_respects_loss_scaling(self):
        entries, _ = plan(BASE, {"hydro": "aaa", "natural_gas": "bbb"})
        self.assertAlmostEqual(entries[0][2], 0.8 / 0.95)


if __name__ == "__main__":
    unittest.main()
