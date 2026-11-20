"""Offline regression checks; no licensed database or IPC server required."""
import copy
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_provider_library import extract_library, guess_technology, is_candidate_name
from provider_library import library_errors, approved_candidates, catalog_for_selection
from openlca_jsonld import make_process


def uid(number):
    return str(uuid.UUID(int=number))


def sample_process(number, name, location="CA", flow_number=10):
    flow = NS(id=uid(flow_number), name="electricity, high voltage")
    unit = NS(id=uid(11), name="kWh")
    prop = NS(id=uid(12), name="Energy")
    reference = NS(input=False, quantitative_reference=True, flow=flow, unit=unit,
                   flow_property=prop)
    return NS(id=uid(number), name=name, location=NS(id=uid(900), name=location),
              exchanges=[reference])


def sample_library():
    processes = [
        sample_process(101, "electricity production, hydro, reservoir"),
        sample_process(102, "electricity production, wind, onshore", "CA-BC"),
        sample_process(103, "market for electricity, high voltage"),
        sample_process(104, "electricity production, natural gas", flow_number=99),
    ]
    desc = [NS(id=p.id, name=p.name) for p in processes]
    fetched = {p.id: p for p in processes}
    return extract_library(desc, fetched.get, "ecoinvent 3.12 cut-off .zolca", "Instructor")


class ProviderLibraryTests(unittest.TestCase):
    def test_hydro_technology_and_market_filter(self):
        self.assertEqual(guess_technology("electricity production, hydro, reservoir"), "hydro")
        self.assertTrue(is_candidate_name("electricity production, wind, onshore"))
        self.assertFalse(is_candidate_name("market for electricity, high voltage"))

    def test_unapproved_until_review(self):
        library = sample_library()
        self.assertFalse(library["approved"])
        self.assertTrue(all(not p["approved"] for p in library["entries"]))
        self.assertEqual(len(library["entries"]), 2)
        self.assertEqual(library["discovery"]["excluded_incompatible_reference_flows"], 1)
        self.assertTrue(library_errors(library))

    def test_catalog_from_approved_selections(self):
        library = sample_library()
        library["approved"] = True
        for e in library["entries"]:
            e["approved"] = True
        self.assertFalse(library_errors(library), library_errors(library))
        hydro = approved_candidates(library, "hydro")
        wind = approved_candidates(library, "wind")
        self.assertEqual(len(hydro), 1)
        self.assertEqual(len(wind), 1)
        catalog = catalog_for_selection(library, {
            "hydro": hydro[0]["id"], "wind": wind[0]["id"]
        })
        scenario = {
            "region": "CLASS EXAMPLE", "year": 2025, "boundary": "hypothetical",
            "evidence_status": "illustrative", "voltage": "high",
            "loss_fraction": 0.0, "source_url": "",
            "ecoinvent_version": "ecoinvent 3.12 cut-off",
            "mix": [{"technology": "hydro", "share": .8},
                    {"technology": "wind", "share": .2}],
        }
        process = make_process(scenario, catalog)
        self.assertEqual(len(process["exchanges"]), 3)
        self.assertEqual(process["exchanges"][1]["defaultProvider"]["@id"], hydro[0]["id"])

    def test_unapproved_entry_rejected(self):
        library = sample_library()
        library["approved"] = True
        library["entries"][0]["approved"] = True
        self.assertFalse(library_errors(library))
        not_approved = next(e for e in library["entries"] if not e["approved"])
        with self.assertRaises(ValueError):
            catalog_for_selection(library, {"wind": not_approved["id"]})

    def test_mixed_reference_flow_rejected_if_approved(self):
        library = sample_library()
        library["approved"] = True
        library["entries"][0]["approved"] = True
        bad = copy.deepcopy(library["entries"][0])
        bad["id"] = uid(999)
        bad["flow_id"] = uid(1000)
        bad["approved"] = True
        library["entries"].append(bad)
        self.assertTrue(any("mismatched" in e for e in library_errors(library)))

    def test_truncation_not_approvable(self):
        library = sample_library()
        library["extraction_truncated"] = True
        library["approved"] = True
        for e in library["entries"]:
            e["approved"] = True
        self.assertTrue(any("truncated" in e for e in library_errors(library)))


if __name__ == "__main__":
    unittest.main()
