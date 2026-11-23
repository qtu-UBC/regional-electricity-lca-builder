"""Tests for the local, reusable instructor-review gate (synthetic metadata)."""
import copy
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from instructor.review_providers import approve_provider_library
from provider_library import library_errors


def uid(n):
    return str(uuid.UUID(int=n))


def library():
    flow = {"id": uid(1), "name": "electricity, high voltage"}
    unit = {"id": uid(2), "name": "kWh"}
    prop = {"id": uid(3), "name": "Energy"}
    entries = []
    for number, name, tech in [
        (10, "electricity production, hydro, run-of-river", "hydro"),
        (11, "electricity production, wind, onshore", "wind"),
        (12, "heat and power co-generation, wood chips", "biomass"),
        (13, "electricity production, hydro, pumped storage", "hydro"),
    ]:
        entries.append({
            "id": uid(number), "name": name, "location": "Canada, Ontario",
            "technology": tech, "provider_class": "storage" if number == 13 else
            ("cogeneration" if number == 12 else "generation"),
            "flow_id": flow["id"], "unit_id": unit["id"],
            "flow_property_id": prop["id"], "approved": False,
        })
    return {
        "catalog_version": 2, "approved": False, "approved_by": "test",
        "reviewed_date": "2026-11-22",
        "database_label": "ecoinvent 3.12 cut-off UPR test database",
        "system_model": "cut-off", "voltage": "high",
        "reference_output": {"flow": flow, "unit": unit, "flow_property": prop},
        "entries": entries,
        "markets": [
            {"id": uid(20), "name": "market for electricity, medium voltage",
             "location": "Canada, Ontario", "kind": "market", "voltage": "medium",
             "approved": False}
        ],
        "extraction_truncated": False,
    }


class InstructorReviewTests(unittest.TestCase):
    def test_selected_only_and_validates(self):
        src = library()
        original = copy.deepcopy(src)
        approved = approve_provider_library(
            src, {uid(10): "Ontario run-of-river hydro is a classroom proxy.",
                  uid(12): "Wood-chip CHP is an explicit sensitivity case."},
            [uid(20)], "Instructor",
            "Models technology alternatives, not verified local consumption.")
        self.assertEqual(src, original)
        self.assertFalse(library_errors(approved), library_errors(approved))
        self.assertEqual(approved["approved_provider_count"], 2)
        self.assertEqual(approved["approved_market_count"], 1)
        ids = {x["id"] for x in approved["entries"] if x["approved"]}
        self.assertEqual(ids, {uid(10), uid(12)})
        self.assertTrue(approved["markets"][0]["approved"])
        self.assertIn("review_reason", approved["entries"][0])

    def test_empty_and_implicit_approval_blocked(self):
        src = library()
        src["approved"] = True
        src["entries"][1]["approved"] = True
        with self.assertRaisesRegex(ValueError, "Select at least one"):
            approve_provider_library(src, {}, [], "Instructor", "Reviewed Ontario candidates.")
        result = approve_provider_library(
            src, {uid(10): "Verified generation dataset."}, [], "Instructor",
            "Reviewed Ontario candidates.")
        self.assertFalse(next(e for e in result["entries"] if e["id"] == uid(11))["approved"])

    def test_missing_reason_unknown_and_truncated_blocked(self):
        src = library()
        for ids, message in [
            ({uid(10): "short"}, "reason"),
            ({uid(999): "Valid lengthy review rationale."}, "Unknown"),
        ]:
            with self.assertRaisesRegex(ValueError, message):
                approve_provider_library(src, ids, [], "Instructor",
                                         "Documented modeling candidate scope.")
        src["extraction_truncated"] = True
        with self.assertRaisesRegex(ValueError, "truncated"):
            approve_provider_library(src, {uid(10): "Verified generation dataset."},
                                     [], "Instructor", "Documented modeling candidate scope.")

    def test_storage_requires_advanced_opt_in(self):
        src = library()
        with self.assertRaisesRegex(ValueError, "classified as storage"):
            approve_provider_library(src, {uid(13): "Pumped storage sensitivity, not primary hydro."},
                                     [], "Instructor", "Explicit pumped-storage test.")
        result = approve_provider_library(
            src, {uid(13): "Pumped storage sensitivity, not primary hydro."},
            [], "Instructor", "Explicit pumped-storage test.", allow_advanced=True)
        self.assertFalse(library_errors(result), library_errors(result))

    def test_mismatched_reference_flow_blocked(self):
        src = library()
        src["entries"][0]["flow_id"] = uid(999)
        with self.assertRaisesRegex(ValueError, "mismatched"):
            approve_provider_library(src, {uid(10): "Hydro candidate under review."},
                                     [], "Instructor", "Ontario supply sensitivity only.")


if __name__ == "__main__":
    unittest.main()
