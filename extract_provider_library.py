"""Local, read-only discovery of high-voltage electricity generation providers.

Run with the SAME restored .zolca database that students use and the openLCA
IPC server started. This script does NOT export ecoinvent inventories.
Review licensing before uploading even the resulting limited metadata to a
public cloud application. All discovered entries start unapproved.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

from provider_library import TECHNOLOGIES


def guess_technology(name: str) -> str:
    n = name.lower()
    if any(x in n for x in ("hydroelectric", "hydropower", "hydro power", "hydro,", "hydro ", "run-of-river", "reservoir hydro")):
        return "hydro"
    if "wind" in n:
        return "wind"
    if any(x in n for x in ("photovoltaic", "solar", "pv electricity", "concentrating solar")):
        return "solar"
    if "nuclear" in n:
        return "nuclear"
    if any(x in n for x in ("natural gas", "gas turbine", "combined cycle")):
        return "natural_gas"
    if any(x in n for x in ("biogas", "biomass", "wood", "biofuel", "biogenic", "bagasse")):
        return "biomass"
    if any(x in n for x in ("hard coal", "lignite", "coal")):
        return "coal"
    return "other"


def is_candidate_name(name: str) -> bool:
    n = name.lower().strip()
    if "market for electricity" in n or "market group for electricity" in n:
        return False
    if any(x in n for x in ("electricity production", "electricity generation", "electricity, high voltage production")):
        return True
    return "power plant" in n and any(x in n for x in ("hydro", "wind", "solar", "coal", "nuclear", "gas", "biomass"))


def _ref(o):
    return {"id": str(o.id), "name": str(o.name or "")}


def extract_library(descriptors, fetch, database_label: str, reviewer: str,
                    limit: int = 0) -> dict:
    """Create a *review draft*. Candidates must have one high-voltage kWh output.

    A shared product-flow group is required by the existing JSON-LD exporter.
    The dominant group is retained; other groups are reported for manual review.
    """
    if "3.12" not in database_label or "cut" not in database_label.lower():
        raise ValueError("Target database label must identify ecoinvent 3.12 cut-off.")
    if limit < 0:
        raise ValueError("limit must be non-negative")
    candidates = [d for d in descriptors if is_candidate_name(str(getattr(d, "name", "") or ""))]
    truncated = bool(limit and len(candidates) > limit)
    if limit:
        candidates = candidates[:limit]
    entries = []
    refs_by_key = {}
    for d in candidates:
        proc = fetch(d.id)
        if not proc:
            continue
        outputs = [e for e in (proc.exchanges or [])
                   if e.is_input is False and e.is_quantitative_reference is True]
        if len(outputs) != 1:
            continue
        o = outputs[0]
        if not (o.flow and o.unit and o.flow_property):
            continue
        fn = str(o.flow.name or "").lower()
        un = str(o.unit.name or "").lower().replace(" ", "")
        if "electricity" not in fn or "high voltage" not in fn or un not in (
                "kwh", "kilowatthour", "kilowatt-hour"):
            continue
        group = (str(o.flow.id), str(o.flow_property.id), str(o.unit.id))
        refs_by_key[group] = {"flow": _ref(o.flow), "flow_property": _ref(o.flow_property),
                              "unit": _ref(o.unit)}
        loc = getattr(proc, "location", None)
        location = str(getattr(loc, "name", "") or "Not specified")
        entries.append({
            "id": str(proc.id), "name": str(proc.name or ""),
            "location": location, "technology": guess_technology(str(proc.name or "")),
            "flow_id": group[0], "flow_property_id": group[1], "unit_id": group[2],
            "approved": False,
        })
    groups = Counter((e["flow_id"], e["flow_property_id"], e["unit_id"]) for e in entries)
    dominant = sorted(groups, key=lambda k: (-groups[k], k))[0] if groups else None
    selected = [e for e in entries
                if (e["flow_id"], e["flow_property_id"], e["unit_id"]) == dominant]
    excluded = len(entries) - len(selected)
    return {
        "catalog_version": 2, "approved": False, "approved_by": reviewer,
        "reviewed_date": date.today().isoformat(),
        "database_label": database_label,
        "system_model": "cut-off", "voltage": "high",
        "reference_output": refs_by_key.get(dominant),
        "entries": sorted(selected, key=lambda x: (x["technology"], x["location"], x["name"])),
        "extraction_truncated": truncated,
        "discovery": {
            "name_candidates_checked": len(candidates),
            "matching_high_voltage_outputs": len(entries),
            "excluded_incompatible_reference_flows": excluded,
            "selected_reference_flow_group_count": len(selected),
        },
        "review_note": (
            "UNAPPROVED: verify each process, technology, geography, product flow and "
            "license. Exclude markets and incorrect processes. Mark only selected entries "
            "approved=true, then mark library approved=true and set approved_by/reviewed_date."
        ),
    }


def electricity_voltage(flow_name: str) -> str | None:
    """Select only distinct electricity high/medium/low voltage reference products."""
    import re
    match = re.match(r"^electricity,\\s*(high|medium|low) voltage(?:$|[, ].*)",
                     (flow_name or "").strip().lower())
    return match.group(1) if match else None


def provider_kind(activity_name: str) -> str:
    """Classify after checking the process reference output, not by keyword alone."""
    name = (activity_name or "").strip().lower()
    if name.startswith(("market for electricity", "market group for electricity")):
        return "market"
    if "production mix" in name or name.startswith("electricity, high voltage,"):
        return "aggregate"
    return "generation"


def extract_flow_based_library(flow_descriptors, providers_of, fetch, database_label: str,
                               reviewer: str, limit: int = 0) -> dict:
    """Query providers of actual electricity product flows through openLCA IPC.

    This finds generation and cogeneration even when their activity names do not
    contain 'electricity production'. Only QUANTITATIVE REFERENCE outputs qualify.
    Low-/medium-voltage MARKET processes are indexed for the baseline chooser;
    custom mix generation export remains high-voltage only.
    """
    if "3.12" not in database_label or "cut" not in database_label.lower():
        raise ValueError("Target database label must identify ecoinvent 3.12 cut-off.")
    if limit < 0:
        raise ValueError("limit must be non-negative")
    flows = [(f, electricity_voltage(str(getattr(f, "name", "") or "")))
             for f in flow_descriptors]
    flows = [(f, v) for (f, v) in flows if v]
    if not flows:
        raise ValueError("No electricity high/medium/low voltage product flow found in database.")
    seen, candidates = set(), []
    truncated = False
    examined = 0
    excluded_non_reference = 0
    for flow, voltage in flows:
        for pair in providers_of(flow):
            # olca-ipc >=2 Client.get_providers returns TechFlow(provider=Ref, flow=Ref).
            pdesc = getattr(pair, "provider", None)
            if not pdesc or not getattr(pdesc, "id", None) or pdesc.id in seen:
                continue
            if limit and examined >= limit:
                truncated = True
                break
            seen.add(pdesc.id)
            examined += 1
            proc = fetch(pdesc.id)
            if proc is None:
                continue
            outputs = [
                e for e in (getattr(proc, "exchanges", None) or [])
                if getattr(e, "is_input", None) is False
                and getattr(e, "is_quantitative_reference", None) is True
            ]
            if len(outputs) != 1:
                excluded_non_reference += 1
                continue
            o = outputs[0]
            if not (o.flow and o.unit and o.flow_property):
                continue
            product_voltage = electricity_voltage(str(o.flow.name or ""))
            unit_name = str(o.unit.name or "").lower().replace(" ", "")
            if not product_voltage or unit_name not in ("kwh", "kilowatthour", "kilowatt-hour"):
                continue
            kind = provider_kind(str(proc.name or ""))
            if kind == "aggregate":
                continue
            location = getattr(proc, "location", None)
            key = (str(o.flow.id), str(o.flow_property.id), str(o.unit.id))
            candidates.append({
                "id": str(proc.id), "name": str(proc.name or ""),
                "location": str(getattr(location, "name", "") or "Not specified"),
                "technology": guess_technology(str(proc.name or "")) if kind == "generation" else "other",
                "voltage": product_voltage,
                "kind": kind,
                "flow_id": key[0], "flow_property_id": key[1], "unit_id": key[2],
                "reference_output": {
                    "flow": _ref(o.flow), "flow_property": _ref(o.flow_property),
                    "unit": _ref(o.unit),
                },
                "approved": False,
            })
        if truncated:
            break
    high_generators = [x for x in candidates
                       if x["kind"] == "generation" and x["voltage"] == "high"]
    groups = Counter((x["flow_id"], x["flow_property_id"], x["unit_id"])
                     for x in high_generators)
    dominant = sorted(groups, key=lambda g: (-groups[g], g))[0] if groups else None
    generators = [
        {k: v for k, v in x.items() if k != "reference_output"}
        for x in high_generators
        if (x["flow_id"], x["flow_property_id"], x["unit_id"]) == dominant
    ]
    markets = [
        {k: v for k, v in x.items() if k != "reference_output"}
        for x in candidates if x["kind"] == "market"
    ]
    ref = next((x["reference_output"] for x in high_generators
                if (x["flow_id"], x["flow_property_id"], x["unit_id"]) == dominant), None)
    if ref is None:
        raise ValueError(
            "No high-voltage generation processes with a quantitative reference "
            "output in kWh were found. Check openLCA's active database.")
    return {
        "catalog_version": 2,
        "approved": False, "approved_by": reviewer,
        "reviewed_date": date.today().isoformat(),
        "database_label": database_label,
        "system_model": "cut-off", "voltage": "high",
        "reference_output": ref,
        "entries": sorted(generators, key=lambda x: (x["technology"], x["location"], x["name"])),
        "markets": sorted(markets, key=lambda x: (x["voltage"], x["location"], x["name"])),
        "extraction_truncated": truncated,
        "discovery": {
            "electricity_product_flows": len(flows),
            "distinct_processes_examined": examined,
            "rejected_non_reference_output": excluded_non_reference,
            "high_voltage_generation_candidates": len(generators),
            "electricity_market_candidates": len(markets),
            "excluded_incompatible_high_voltage_flow_groups": len(high_generators) - len(generators),
            "market_counts_by_voltage": dict(Counter(x["voltage"] for x in markets)),
        },
        "review_note": (
            "UNAPPROVED. Review technology, reference product, location and "
            "market/generation classification. For custom grid supply select only "
            "true high-voltage generator reference outputs; do not confuse an "
            "electricity coproduct with the quantitative reference. Mark individual "
            "entries and markets approved, then approve the whole library."
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-label", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--out", default="provider_library_REVIEW.json")
    parser.add_argument("--limit", type=int, default=0,
                        help="Optional discovery cap for testing only; truncated result cannot be approved")
    args = parser.parse_args()
    import olca_ipc as ipc
    import olca_schema as o
    client = ipc.Client(args.port)
    library = extract_flow_based_library(
        client.get_descriptors(o.Flow),
        client.get_providers,
        lambda uid: client.get(o.Process, uid),
        args.database_label, args.reviewer, args.limit)
    Path(args.out).write_text(json.dumps(library, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"Wrote {args.out}: {len(library['entries'])} high-voltage generator candidates, "
          f"{len(library['markets'])} electricity market candidates, ALL unapproved.")
    print("Check providers manually and confirm permission before using metadata on public Streamlit.")


if __name__ == "__main__":
    main()
