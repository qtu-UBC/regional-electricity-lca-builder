"""Offline regression checks; no licensed database or IPC server required."""
import copy
import sys
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from extract_provider_library import extract_library, extract_flow_based_library, electricity_voltage, guess_technology, is_candidate_name
from provider_library import (
    library_errors, approved_candidates, catalog_for_selection, ranked_candidates,
    classify_provider_name, provider_class, region_preference,
)
from openlca_jsonld import make_process


def uid(number):
    return str(uuid.UUID(int=number))


def sample_process(number, name, location="CA", flow_number=10):
    flow = NS(id=uid(flow_number), name="electricity, high voltage")
    unit = NS(id=uid(11), name="kWh")
    prop = NS(id=uid(12), name="Energy")
    reference = NS(is_input=False, is_quantitative_reference=True, flow=flow, unit=unit,
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


    def test_market_baseline_separate_from_generation(self):
        from provider_library import approved_markets
        library = sample_library()
        library["approved"] = True
        library["entries"][0]["approved"] = True
        library["markets"] = [
            {
                "id": uid(500), "name": "market for electricity, high voltage",
                "location": "Canada, Ontario", "kind": "market", "voltage": "high",
                "approved": True,
            },
            {
                "id": uid(501), "name": "market for electricity, medium voltage",
                "location": "Canada, Ontario", "kind": "market", "voltage": "medium",
                "approved": True,
            },
        ]
        self.assertFalse(library_errors(library), library_errors(library))
        self.assertEqual(len(approved_markets(library, "high")), 1)
        with self.assertRaises(ValueError):
            catalog_for_selection(library, {"hydro": uid(500)})

    def test_market_rejected_as_generation_provider(self):
        library = sample_library()
        library["approved"] = True
        library["entries"][0]["approved"] = True
        rejected = copy.deepcopy(library["entries"][0])
        rejected["id"] = uid(999)
        rejected["name"] = "market for electricity, high voltage"
        rejected["approved"] = True
        library["entries"].append(rejected)
        self.assertTrue(any("downstream electricity market" in e
                            for e in library_errors(library)))


    def test_v05_electricity_product_flow_discovery(self):
        self.assertEqual(electricity_voltage("electricity, high voltage"), "high")
        self.assertEqual(electricity_voltage("electricity, medium voltage"), "medium")
        self.assertIsNone(electricity_voltage("heat, district or industrial"))
        flows = [
            NS(id=uid(10), name="electricity, high voltage"),
            NS(id=uid(30), name="electricity, medium voltage"),
        ]
        hydro = sample_process(101, "electricity production, hydro, run-of-river")
        cogeneration = sample_process(102, "heat and power co-generation, biogas, engine")
        market = sample_process(103, "market for electricity, high voltage")
        mvmarket = sample_process(104, "market for electricity, medium voltage")
        mvmarket.exchanges[0].flow = NS(id=uid(30), name="electricity, medium voltage")
        processes = {p.id: p for p in [hydro, cogeneration, market, mvmarket]}
        by_flow = {
            flows[0].id: [hydro, cogeneration, market],
            flows[1].id: [mvmarket],
        }
        def providers(flow):
            return [NS(provider=NS(id=p.id, name=p.name), flow=flow)
                    for p in by_flow[flow.id]]
        library = extract_flow_based_library(
            flows, providers, processes.get,
            "ecoinvent 3.12 cut-off shared .zolca", "Instructor")
        self.assertEqual(len(library["entries"]), 2)
        self.assertEqual(len(library["markets"]), 2)
        self.assertIn("biomass", [e["technology"] for e in library["entries"]])
        self.assertEqual({e["voltage"] for e in library["markets"]},
                         {"high", "medium"})
        self.assertFalse(library["approved"])
        self.assertTrue(all(not e["approved"] for e in library["entries"]))




    def test_provider_classes_and_legacy_fallback(self):
        self.assertEqual(classify_provider_name("electricity production, hydro, run-of-river"), "generation")
        self.assertEqual(classify_provider_name(
            "heat and power co-generation, wood chips, 6667 kW"), "cogeneration")
        self.assertEqual(classify_provider_name(
            "sulfate pulp production, from softwood, unbleached"), "industrial_coproduct")
        self.assertEqual(classify_provider_name(
            "electricity production, hydro, pumped storage"), "storage")
        self.assertEqual(provider_class({"name": "ethanol production from wood"}),
                         "industrial_coproduct")

    def test_geo_ranking_and_advanced_visibility(self):
        library = sample_library()
        library["approved"] = True
        hydro = library["entries"][0]
        hydro["approved"] = True
        hydro["location"] = "Canada, Ontario"
        def extra(i, name, location):
            e = copy.deepcopy(hydro)
            e["id"] = uid(i)
            e["name"] = name
            e["location"] = location
            return e
        library["entries"].extend([
            extra(250, "electricity production, hydro, reservoir", "Canada, Quebec"),
            extra(251, "electricity production, hydro, run-of-river", "Rest of World"),
            extra(252, "electricity production, hydro, pumped storage", "Canada, Ontario"),
        ])
        ranked = ranked_candidates(library, "hydro", "IESO Northwest — 2025")
        self.assertEqual(ranked[0]["location"], "Canada, Ontario")
        self.assertEqual(len(ranked), 3)
        self.assertEqual(len(ranked_candidates(
            library, "hydro", "IESO Northwest — 2025", include_advanced=True)), 4)
        self.assertLess(region_preference("Canada, Ontario", "IESO Northwest")[0],
                        region_preference("Canada, Quebec", "IESO Northwest")[0])
        self.assertFalse(library_errors(library), library_errors(library))

    def test_student_rationale_preserved_and_cross_technology_rejected(self):
        library = sample_library()
        library["approved"] = True
        for e in library["entries"]:
            e["approved"] = True
        hydro = approved_candidates(library, "hydro")[0]
        wind = approved_candidates(library, "wind")[0]
        with self.assertRaises(ValueError):
            catalog_for_selection(library, {"hydro": wind["id"]})
        catalog = catalog_for_selection(
            library,
            {"hydro": hydro["id"], "wind": wind["id"]},
            {"hydro": "Ontario geography and matching hydro technology", "wind": "Onshore turbine"},
        )
        self.assertEqual(catalog["providers"]["hydro"]["selection_reason"],
                         "Ontario geography and matching hydro technology")
        self.assertEqual(catalog["providers"]["hydro"]["provider_class"], "generation")


if __name__ == "__main__":
    unittest.main()
