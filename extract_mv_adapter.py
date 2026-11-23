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
import re

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


def _activity_name(name: str) -> str:
    """Strip openLCA's formatted 'activity | product | model - geography' suffix.

    In some imported .zolca databases IPC descriptors return the fully
    formatted title, while the source Process.name contains only the activity.
    Never use broad substring matching: 'market group' must not match 'market'.
    """
    return re.sub(r"\s+", " ", str(name or "").split("|", 1)[0]).strip().casefold()


def _location_label(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().casefold()


def _title_geography(name: str) -> str:
    """Recognize an explicit geography only in a formatted title after a pipe."""
    pieces = str(name or "").split("|")
    if len(pieces) < 3:
        return ""
    tail = pieces[-1].strip()
    # Examples: 'Cutoff, U - CA-ON', 'Cutoff, U – CA-ON'.
    match = re.search(r"\s[-–—]\s(.+)$", tail)
    return match.group(1).strip() if match else ""


def _region_aliases(region: str, region_code: str | None) -> set[str]:
    names = {_location_label(region)}
    if region_code:
        names.add(_location_label(region_code))
    # Only add the alias when its full geography is explicitly selected.
    # Other regions can supply --region-code to avoid guessing.
    if _location_label(region) == "canada, ontario":
        names.add("ca-on")
    return names


def _describe_candidate(descriptor, process=None) -> str:
    loc = str(getattr(getattr(process, "location", None), "name", "") or "")
    title = str(getattr(descriptor, "name", "") or "")
    displayed = title[:160]
    return (
        f"name={displayed!r}; process_location={loc or '(not provided)'!r}; "
        f"title_geography={_title_geography(title) or '(not provided)'!r}; "
        f"UUID={getattr(descriptor, 'id', '(missing)')}"
    )


def extract_adapter(descriptors, fetch, region: str, database_label: str,
                    reviewer: str, region_code: str | None = None) -> dict:
    """Match exact activity names and an explicit geography, with diagnostics.

    Accepts openLCA's formatted descriptor titles and an optional explicit
    location code. Fails closed if no unique source process can be identified.
    """
    if not region.strip() or "3.12" not in database_label or "cut" not in database_label.casefold():
        raise ValueError("Specify a region and an ecoinvent 3.12 cut-off database label.")
    descriptors = list(descriptors)
    aliases = _region_aliases(region, region_code)
    processes = {}
    for key, name in ACTIVITIES.items():
        possible = [d for d in descriptors if _activity_name(
            getattr(d, "name", "")) == name.casefold()]
        matches = []
        inspected = []
        for desc in possible:
            p = fetch(desc.id)
            if p is None:
                continue
            loc = _location_label(
                getattr(getattr(p, "location", None), "name", ""))
            code = _location_label(_title_geography(getattr(desc, "name", "")))
            # A meaningful process location is authoritative. Only when it
            # is missing can the title geography serve as the locator.
            if loc in aliases or (not loc and code in aliases):
                matches.append(p)
            inspected.append(_describe_candidate(desc, p))
        if len(matches) != 1:
            nearby = [d for d in descriptors if
                      "electricity" in _activity_name(getattr(d, "name", ""))
                      and (key == "transformation" or "market" in _activity_name(getattr(d, "name", "")))]
            preview = inspected[:10] if inspected else [
                _describe_candidate(d) for d in nearby[:10]]
            sample = "\n  ".join(preview) if preview else "(no electricity market candidates visible over IPC)"
            raise ValueError(
                f"Expected exactly one '{name}' in '{region}' "
                f"(accepted locations: {', '.join(sorted(aliases))}); found {len(matches)} "
                f"from {len(possible)} matching activity titles.\n"
                f"Candidate descriptors:\n  {sample}\n"
                "Confirm the correct .zolca database is active in the openLCA IPC server. "
                "If the dataset uses a location code not recognized above, rerun with "
                "--region-code <exact code shown in openLCA> (e.g., CA-ON). "
                "Never choose a different region merely to satisfy the lookup."
            )
        p = matches[0]
        processes[key] = {
            "id": str(p.id), "name": str(p.name),
            "location": region,
            "exchanges": [_exchange(e) for e in (p.exchanges or [])],
        }
    return {
        "adapter_version": 1,
        "review_status": "extracted",
        "extracted_by": reviewer,
        "extracted_date": date.today().isoformat(),
        "database_label": database_label,
        "system_model": "cut-off",
        "region": region,
        "extraction_truncated": False,
        "processes": processes,
        "review_note": (
            "EXTRACTED ONLY, NOT SCIENTIFICALLY APPROVED. Contains licensed "
            "ecoinvent exchange amounts: keep private. "
            "Review exact processes, supplier links, reference flows, losses, "
            "direct MV generation and infrastructure; run baseline replication. "
            "Use Streamlit's source-link review and LCIA replication steps; "
            "do not mark this model validated without actual openLCA comparison. "
            "This adapter supports one HV market -> HV/MV transformer -> MV market topology."
        ),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--region", required=True, help="Exact openLCA geography, e.g. Canada, Ontario")
    p.add_argument("--database-label", required=True, help="Must equal the approved provider-library label")
    p.add_argument("--reviewer", required=True)
    p.add_argument(
        "--region-code", default=None,
        help="Exact short geography code when Process.location uses codes (e.g. CA-ON).",
    )
    p.add_argument("--port", type=int, default=8080)
    p.add_argument("--out", default="mv_adapter_REVIEW_LOCAL.json")
    args = p.parse_args()
    import olca_ipc as ipc
    import olca_schema as o
    client = ipc.Client(args.port)
    result = extract_adapter(
        list(client.get_descriptors(o.Process)),
        lambda uid: client.get(o.Process, uid),
        args.region, args.database_label, args.reviewer, args.region_code)
    Path(args.out).write_text(json.dumps(result, indent=2, ensure_ascii=False),
                              encoding="utf-8")
    print(f"Wrote EXTRACTED local-only MV adapter: {args.out}")
    for key, proc in result["processes"].items():
        print(f"{key}: {proc['name']} [{proc['location']}] "
              f"{len(proc['exchanges'])} exchanges; UUID {proc['id']}")
    print("Next: run local Streamlit and export the baseline replication. No generator-provider approval needed for that. DO NOT add this file to public Git.")


if __name__ == "__main__":
    main()
