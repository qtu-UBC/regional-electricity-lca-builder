import io
import json
import sys
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace as Obj

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mv_market import validate_mv_adapter, make_mv_processes, mv_package, mv_preview
from extract_mv_adapter import extract_adapter


def uid(n):
    return str(uuid.UUID(int=n))


def ref(n, name):
    return {"id": uid(n), "name": name}


HV = ref(11, "electricity, high voltage")
MV = ref(12, "electricity, medium voltage")
UNIT = ref(13, "kWh")
ENERGY = ref(14, "Energy")
SF6 = ref(15, "Sulfur hexafluoride")
KG = ref(16, "kg")
MASS = ref(17, "Mass")
NETWORK = ref(18, "transmission network, electricity, medium voltage")
KM = ref(19, "km")
LENGTH = ref(20, "Length")


def exchange(flow, amount, *, inp, refout=False, provider=None, unit=UNIT, prop=ENERGY):
    return {
        "flow": flow, "amount": amount, "unit": unit, "flow_property": prop,
        "is_input": inp, "is_quantitative_reference": refout,
        "is_avoided_product": False, "provider": provider,
    }


def sample():
    hv_id, tr_id, mv_id = uid(31), uid(32), uid(33)
    hydro, wind = ref(41, "TEST hydro"), ref(42, "TEST wind")
    background = ref(43, "TEST original HV provider")
    direct_mv = ref(44, "TEST municipal incineration")
    supplier = ref(45, "TEST transmission network market")
    catalog = {
        "catalog_version": 1, "approved": True, "approved_by": "TEST reviewer",
        "reviewed_date": "2026-11-22",
        "database_label": "ecoinvent 3.12 cut-off UPR TEST DB",
        "system_model": "cut-off", "voltage": "high",
        "reference_output": {"flow": HV, "unit": UNIT, "flow_property": ENERGY},
        "providers": {
            "hydro": {"id": hydro["id"], "name": hydro["name"],
                      "flow_id": HV["id"], "unit_id": UNIT["id"],
                      "flow_property_id": ENERGY["id"]},
            "wind": {"id": wind["id"], "name": wind["name"],
                     "flow_id": HV["id"], "unit_id": UNIT["id"],
                     "flow_property_id": ENERGY["id"]},
        },
    }
    scenario = {
        "region": "TEST hypothetical Northwest", "year": 2025,
        "boundary": "hypothetical", "evidence_status": "illustrative",
        "voltage": "medium", "loss_fraction": 0.0,
        "source_url": "https://example.org/testing",
        "ecoinvent_version": "ecoinvent 3.12, allocation cut-off",
        "mix": [
            {"technology": "hydro", "share": 0.85, "source_url": "https://example.org/testing"},
            {"technology": "wind", "share": 0.15, "source_url": "https://example.org/testing"},
        ]
    }
    adapter = {
        "adapter_version": 1, "approved": True, "approved_by": "TEST MV reviewer",
        "reviewed_date": "2026-11-22",
        "database_label": catalog["database_label"],
        "system_model": "cut-off", "region": "Canada, Ontario",
        "extraction_truncated": False,
        "processes": {
            "hv_market": {
                "id": hv_id, "name": "market for electricity, high voltage",
                "exchanges": [
                    exchange(HV, 1, inp=False, refout=True),
                    exchange(HV, 0.9985, inp=True, provider=background),
                    exchange(HV, 0.003, inp=True, provider=ref(31, "original HV self")),
                    exchange(SF6, 0.0001, inp=False, unit=KG, prop=MASS),
                ],
            },
            "transformation": {
                "id": tr_id, "name": "electricity voltage transformation from high to medium voltage",
                "exchanges": [
                    exchange(MV, 1, inp=False, refout=True),
                    exchange(HV, 1.00482, inp=True, provider=ref(31, "original HV market")),
                ],
            },
            "mv_market": {
                "id": mv_id, "name": "market for electricity, medium voltage",
                "exchanges": [
                    exchange(MV, 1, inp=False, refout=True),
                    exchange(MV, 0.99862, inp=True, provider=ref(32, "original transformation")),
                    exchange(MV, 0.00138, inp=True, provider=direct_mv),
                    exchange(MV, 0.00239, inp=True, provider=ref(33, "original MV self")),
                    exchange(NETWORK, 1.86278e-8, inp=True, provider=supplier, unit=KM, prop=LENGTH),
                    exchange(SF6, 1.29e-7, inp=False, unit=KG, prop=MASS),
                ],
            },
        },
    }
    return scenario, catalog, adapter


def input_exchanges(p, name):
    return [x for x in p["exchanges"] if x["isInput"] and x["flow"]["name"] == name]


class MVAdapterTests(unittest.TestCase):
    def test_ontario_shaped_adapter_passes(self):
        sc, cat, ad = sample()
        errors, warnings = validate_mv_adapter(ad, cat, sc)
        self.assertEqual(errors, [])
        self.assertTrue(warnings)

    def test_custom_four_processes_replace_supply_and_preserve_network(self):
        sc, cat, ad = sample()
        mix, hv, tr, mv = make_mv_processes(sc, cat, ad)
        self.assertEqual(len({p["@id"] for p in (mix, hv, tr, mv)}), 4)
        self.assertEqual(input_exchanges(hv, HV["name"])[0]["amount"], 0.003)
        self.assertAlmostEqual(input_exchanges(hv, HV["name"])[1]["amount"], 0.9985)
        self.assertEqual(
            input_exchanges(hv, HV["name"])[0]["defaultProvider"]["@id"], hv["@id"])
        self.assertEqual(
            input_exchanges(hv, HV["name"])[1]["defaultProvider"]["@id"], mix["@id"])
        self.assertEqual(
            input_exchanges(tr, HV["name"])[0]["defaultProvider"]["@id"], hv["@id"])
        self.assertEqual(input_exchanges(tr, HV["name"])[0]["amount"], 1.00482)
        inputs = input_exchanges(mv, MV["name"])
        self.assertEqual(len(inputs), 2)  # transformed supply + self-loop, no direct MV
        self.assertAlmostEqual(
            next(x["amount"] for x in inputs if x["defaultProvider"]["@id"] == tr["@id"]),
            1.0)
        self.assertAlmostEqual(
            next(x["amount"] for x in inputs if x["defaultProvider"]["@id"] == mv["@id"]),
            0.00239)
        self.assertAlmostEqual(
            input_exchanges(mv, NETWORK["name"])[0]["amount"], 1.86278e-8)
        self.assertTrue(any(x["flow"]["name"] == SF6["name"] and not x["isInput"]
                            for x in mv["exchanges"]))
        self.assertFalse(any(x.get("defaultProvider", {}).get("@id") in
                             (ad["processes"]["hv_market"]["id"],
                              ad["processes"]["mv_market"]["id"])
                             for p in (mix, hv, tr, mv) for x in p["exchanges"]))

    def test_replication_preserves_external_sources_and_direct_mv(self):
        sc, cat, ad = sample()
        hv, tr, mv = make_mv_processes(sc, cat, ad, replicate=True)
        self.assertEqual(len(input_exchanges(hv, HV["name"])), 2)
        self.assertEqual(input_exchanges(hv, HV["name"])[0]["defaultProvider"]["@id"], uid(43))
        self.assertEqual(input_exchanges(hv, HV["name"])[1]["defaultProvider"]["@id"], hv["@id"])
        self.assertEqual(input_exchanges(tr, HV["name"])[0]["defaultProvider"]["@id"], hv["@id"])
        inp = input_exchanges(mv, MV["name"])
        self.assertEqual(len(inp), 3)
        self.assertAlmostEqual(sum(x["amount"] for x in inp), 1.00239)
        self.assertEqual(inp[0]["defaultProvider"]["@id"], tr["@id"])
        self.assertEqual(inp[1]["defaultProvider"]["@id"], uid(44))
        self.assertEqual(inp[2]["defaultProvider"]["@id"], mv["@id"])

    def test_package_schema_and_preview(self):
        sc, cat, ad = sample()
        b = mv_package(sc, cat, ad)
        with zipfile.ZipFile(io.BytesIO(b)) as archive:
            names = archive.namelist()
            self.assertEqual(len(names), 5)
            self.assertIn("olca-schema.json", names)
            self.assertIsNone(archive.testzip())
        pre = mv_preview(sc, cat, ad)
        self.assertEqual(len(pre["processes"]), 4)
        self.assertAlmostEqual(pre["transformation_hv_per_mv_kwh"], 1.00482)
        self.assertAlmostEqual(pre["mv_self_input_kwh_per_kwh"], 0.00239)
        self.assertAlmostEqual(pre["original_direct_mv_kwh_replaced"], 0.00138)

    def test_deterministic_ids_and_mode_difference(self):
        sc, cat, ad = sample()
        a = make_mv_processes(sc, cat, ad)
        b = make_mv_processes(sc, cat, ad)
        c = make_mv_processes(sc, cat, ad, replicate=True)
        self.assertEqual([x["@id"] for x in a], [x["@id"] for x in b])
        self.assertNotIn(c[-1]["@id"], [x["@id"] for x in a])
        sc["mix"][0]["share"], sc["mix"][1]["share"] = .8, .2
        d = make_mv_processes(sc, cat, ad)
        self.assertNotEqual(a[-1]["@id"], d[-1]["@id"])

    def test_unapproved_or_mismatched_adapter_is_blocked(self):
        sc, cat, ad = sample()
        ad["approved"] = False
        self.assertTrue(validate_mv_adapter(ad, cat, sc)[0])
        with self.assertRaises(ValueError):
            mv_package(sc, cat, ad)
        ad["approved"] = True
        ad["database_label"] = "ecoinvent 3.11 cut-off"
        self.assertTrue(any("same restored" in s for s in
                            validate_mv_adapter(ad, cat, sc)[0]))

    def test_double_loss_scaling_is_blocked(self):
        sc, cat, ad = sample()
        sc["loss_fraction"] = 0.02
        self.assertTrue(any("simplified loss" in s for s in
                            validate_mv_adapter(ad, cat, sc)[0]))

    def test_wrong_transform_supplier_and_flow_is_blocked(self):
        sc, cat, ad = sample()
        ad["processes"]["transformation"]["exchanges"][1]["provider"] = ref(500, "wrong")
        self.assertTrue(any("Transformer" in s for s in validate_mv_adapter(ad, cat, sc)[0]))
        sc, cat, ad = sample()
        ad["processes"]["mv_market"]["exchanges"][1]["flow"] = ref(500, MV["name"])
        self.assertTrue(any("mismatched flow" in s for s in validate_mv_adapter(ad, cat, sc)[0]))

    def test_unsupported_hv_market_voltage_mix_is_blocked(self):
        sc, cat, ad = sample()
        ad["processes"]["hv_market"]["exchanges"].append(
            exchange(MV, 0.05, inp=True, provider=ref(600, "MV provider")))
        self.assertTrue(any("non-HV" in s for s in validate_mv_adapter(ad, cat, sc)[0]))

    def test_extractor_makes_unapproved_local_adapter(self):
        def as_obj(d):
            return Obj(**d)
        def e(o):
            return Obj(
                flow=as_obj(o["flow"]), unit=as_obj(o["unit"]),
                flow_property=as_obj(o["flow_property"]), amount=o["amount"],
                is_input=o["is_input"],
                is_quantitative_reference=o["is_quantitative_reference"],
                is_avoided_product=o["is_avoided_product"],
                default_provider=as_obj(o["provider"]) if o["provider"] else None,
                description="")
        sc, cat, ad = sample()
        descriptors = [Obj(id=v["id"], name=v["name"])
                       for v in ad["processes"].values()]
        processes = {
            v["id"]: Obj(id=v["id"], name=v["name"],
                         location=Obj(name="Canada, Ontario"),
                         exchanges=[e(x) for x in v["exchanges"]])
            for v in ad["processes"].values()
        }
        result = extract_adapter(descriptors, lambda i: processes[i],
                                 "Canada, Ontario", cat["database_label"], "Course instructor")
        self.assertFalse(result["approved"])
        self.assertEqual(result["processes"]["transformation"]["exchanges"][1]["amount"], 1.00482)
        with self.assertRaises(ValueError):
            extract_adapter(descriptors, lambda i: processes[i],
                            "Canada, Alberta", cat["database_label"], "Course instructor")


    def test_extractor_accepts_formatted_openlca_titles_and_ca_on_code(self):
        sc, cat, ad = sample()

        def convert_entry(row):
            return Obj(
                flow=Obj(**row["flow"]), unit=Obj(**row["unit"]),
                flow_property=Obj(**row["flow_property"]),
                amount=row["amount"], is_input=row["is_input"],
                is_quantitative_reference=row["is_quantitative_reference"],
                is_avoided_product=row["is_avoided_product"],
                default_provider=Obj(**row["provider"]) if row["provider"] else None,
                description="",
            )

        processes = {
            p["id"]: Obj(
                id=p["id"], name=p["name"], location=Obj(name="CA-ON"),
                exchanges=[convert_entry(x) for x in p["exchanges"]],
            )
            for p in ad["processes"].values()
        }
        formatted = [
            Obj(
                id=p["id"],
                name=f"{p['name']} | electricity, "
                     f"{'high' if role == 'hv_market' else 'medium'} voltage "
                     f"| Cutoff, U - CA-ON"
            )
            for role, p in ad["processes"].items()
        ]
        result = extract_adapter(
            formatted, lambda i: processes[i], "Canada, Ontario",
            cat["database_label"], "Instructor",
        )
        self.assertEqual(
            result["processes"]["transformation"]["exchanges"][1]["amount"], 1.00482
        )
        self.assertEqual(
            result["processes"]["hv_market"]["id"], ad["processes"]["hv_market"]["id"]
        )

    def test_extractor_uses_explicit_code_for_other_regions(self):
        sc, cat, ad = sample()
        processes = {
            p["id"]: Obj(
                id=p["id"], name=p["name"], location=Obj(name="CA-AB"),
                exchanges=[],
            )
            for p in ad["processes"].values()
        }
        descriptors = [
            Obj(id=p["id"], name=p["name"] + " | electricity, medium voltage | Cutoff, U - CA-AB")
            for p in ad["processes"].values()
        ]
        with self.assertRaisesRegex(ValueError, "Candidate descriptors"):
            extract_adapter(descriptors, lambda i: processes[i],
                            "Canada, Alberta", cat["database_label"], "Instructor")
        result = extract_adapter(descriptors, lambda i: processes[i],
                                 "Canada, Alberta", cat["database_label"], "Instructor",
                                 region_code="CA-AB")
        self.assertEqual(result["region"], "Canada, Alberta")

    def test_extractor_fails_closed_on_ambiguous_formatted_titles(self):
        sc, cat, ad = sample()
        original = ad["processes"]["hv_market"]
        descriptors = [
            Obj(id=original["id"], name=original["name"] + " | electricity, high voltage | Cutoff, U - CA-ON"),
            Obj(id=uid(501), name=original["name"] + " | electricity, high voltage | Cutoff, U - CA-ON"),
        ]
        processes = {
            d.id: Obj(id=d.id, name=original["name"],
                      location=Obj(name="Canada, Ontario"), exchanges=[])
            for d in descriptors
        }
        with self.assertRaisesRegex(ValueError, "found 2"):
            extract_adapter(descriptors, lambda i: processes[i], "Canada, Ontario",
                            cat["database_label"], "Instructor")


if __name__ == "__main__":
    unittest.main()
