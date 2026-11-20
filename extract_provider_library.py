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
                   if e.input is False and e.quantitative_reference is True]
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
    client = ipc.Client(port=args.port)
    library = extract_library(
        client.get_descriptors(o.Process),
        lambda uid: client.get(o.Process, uid),
        args.database_label, args.reviewer, args.limit)
    Path(args.out).write_text(json.dumps(library, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"Wrote {args.out} with {len(library['entries'])} candidates, ALL unapproved.")
    print("Check providers manually and confirm permission before using metadata on public Streamlit.")


if __name__ == "__main__":
    main()
