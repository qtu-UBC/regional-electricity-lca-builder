"""Extract an UNAPPROVED regional HV/MV adapter from a licensed local openLCA.

Requires olca-ipc 2 and olca-schema 2 on the instructor workstation with the
correct .zolca restored and IPC enabled. This reads process exchange amounts
and provider UUIDs, so its output contains license-sensitive LCI information:
keep it local; DO NOT commit or distribute it through a public app by default.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

ACTIVITIES = {
    "hv_market": "market for electricity, high voltage",
    "transformation": "electricity voltage transformation from high to medium voltage",
    "mv_market": "market for electricity, medium voltage",
}


def _ref(value):
    if value is None:
        return None
    return {"id": str(value.id), "name": str(value.name or "")}


def _exchange(value):
    return {
        "flow": _ref(value.flow),
        "flow_property": _ref(value.flow_property),
        "unit": _ref(value.unit),
        "amount": float(value.amount),
        "is_input": value.is_input is True,
        "is_quantitative_reference": value.is_quantitative_reference is True,
        "is_avoided_product": value.is_avoided_product is True,
        "provider": _ref(getattr(value, "default_provider", None)),
        "description": str(getattr(value, "description", "") or "")[:400],
    }


def extract_adapter(descriptors, fetch, region: str, database_label: str,
                    reviewer: str) -> dict:
    """Select one process for each exact activity name and geography."""
    if not region.strip() or "3.12" not in database_label or "cut" not in database_label.casefold():
        raise ValueError("Specify a region and an ecoinvent 3.12 cut-off database label.")
    processes = {}
    for key, name in ACTIVITIES.items():
        possible = [d for d in descriptors
                    if str(getattr(d, "name", "") or "").casefold().strip() == name.casefold()]
        matches = []
        for desc in possible:
            p = fetch(desc.id)
            loc = str(getattr(getattr(p, "location", None), "name", "") or "")
            if loc.casefold().strip() == region.casefold().strip():
                matches.append(p)
        if len(matches) != 1:
            raise ValueError(
                f"Expected exactly one '{name}' in '{region}', found {len(matches)}. "
                "Inspect openLCA geography/activity names; do not guess a proxy."
            )
        p = matches[0]
        processes[key] = {
            "id": str(p.id), "name": str(p.name),
            "location": region,
            "exchanges": [_exchange(e) for e in (p.exchanges or [])],
        }
    return {
        "adapter_version": 1,
        "approved": False,
        "approved_by": reviewer,
        "reviewed_date": date.today().isoformat(),
        "database_label": database_label,
        "system_model": "cut-off",
        "region": region,
        "extraction_truncated": False,
        "processes": processes,
        "review_note": (
            "UNAPPROVED. Contains licensed ecoinvent exchange amounts: keep private. "
            "Review exact processes, supplier links, reference flows, losses, "
            "direct MV generation and infrastructure; run baseline replication. "
            "Mark approved=true ONLY after instructor review. "
            "This adapter supports one HV market -> HV/MV transformer -> MV market topology."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", required=True, help="Exact openLCA geography, e.g. Canada, Ontario")
    p.add_argument("--database-label", required=True, help="Must equal the approved provider-library label")
    p.add_argument("--reviewer", required=True)
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--out", default="mv_adapter_REVIEW_LOCAL.json")
    args = p.parse_args()
    import olca_ipc as ipc
    import olca_schema as o
    client = ipc.Client(args.port)
    result = extract_adapter(
        list(client.get_descriptors(o.Process)),
        lambda uid: client.get(o.Process, uid),
        args.region, args.database_label, args.reviewer)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"Wrote UNAPPROVED local-only MV adapter: {args.out}")
    for key, proc in result["processes"].items():
        print(f"{key}: {proc['name']} [{proc['location']}] "
              f"{len(proc['exchanges'])} exchanges; UUID {proc['id']}")
    print("Review inputs and default providers, then approve locally. DO NOT add this file to public Git.")


if __name__ == "__main__":
    main()
