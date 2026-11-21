"""Validate an instructor-approved searchable provider library.

Only metadata/UUIDs are stored. No LCI exchanges or LCIA scores are distributed.
A library is bound to the exact ecoinvent .zolca that students restore.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Mapping
from uuid import UUID

TECHNOLOGIES = {"hydro", "nuclear", "natural_gas", "wind", "solar", "biomass", "coal", "import", "other"}


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
        return True
    except (ValueError, TypeError, AttributeError):
        return False


def library_errors(library: Any) -> list[str]:
    """Validate format, instructor approval and the shared high-voltage product flow."""
    errors = []
    if not isinstance(library, dict):
        return ["An instructor provider library (JSON object) is required."]
    if library.get("catalog_version") != 2:
        errors.append("Searchable provider library must have catalog_version 2.")
    if library.get("approved") is not True or not str(library.get("approved_by", "")).strip():
        errors.append("Instructor approval and approved_by are required.")
    if not str(library.get("reviewed_date", "")).strip():
        errors.append("reviewed_date is required.")
    label = str(library.get("database_label", "")).lower()
    if "3.12" not in label or "cut" not in label:
        errors.append("Database label must identify ecoinvent 3.12 cut-off.")
    if library.get("system_model") != "cut-off" or library.get("voltage") != "high":
        errors.append("This exporter currently supports only cut-off HIGH voltage.")
    if library.get("extraction_truncated"):
        errors.append("A truncated discovery run cannot be approved for classroom use.")
    ref = library.get("reference_output")
    if not isinstance(ref, dict):
        errors.append("Missing reference_output flow, unit and flow_property.")
        return errors
    try:
        for field in ("flow", "unit", "flow_property"):
            item = ref[field]
            if not _is_uuid(item.get("id")) or not item.get("name"):
                errors.append(f"Invalid reference_output {field}.")
        if "electricity" not in ref["flow"]["name"].lower() or "high voltage" not in ref["flow"]["name"].lower():
            errors.append("Reference output is not high-voltage electricity.")
        if ref["unit"]["name"].lower().replace(" ", "") not in ("kwh", "kilowatthour", "kilowatt-hour"):
            errors.append("Reference output unit is not kWh.")
    except (KeyError, TypeError, AttributeError):
        errors.append("Incomplete reference_output metadata.")
        return errors
    entries = library.get("entries")
    if not isinstance(entries, list):
        return errors + ["entries must be a list."]
    ids, approved_count = set(), 0
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"Entry {i} is not a JSON object.")
            continue
        pid = entry.get("id")
        if not _is_uuid(pid):
            errors.append(f"Entry {i} has an invalid process UUID.")
        if pid in ids:
            errors.append(f"Duplicate provider UUID: {pid}")
        ids.add(pid)
        if not entry.get("name"):
            errors.append(f"Entry {i} missing process name.")
        if entry.get("technology") not in TECHNOLOGIES:
            errors.append(f"Entry {i} has unknown technology.")
        if entry.get("provider_class") is not None and entry.get("provider_class") not in PROVIDER_CLASSES:
            errors.append(f"Entry {i} has unknown provider_class.")
        if entry.get("approved") is True:
            approved_count += 1
            for field, ref_key in (("flow_id", "flow"), ("unit_id", "unit"), ("flow_property_id", "flow_property")):
                if entry.get(field) != ref[ref_key]["id"]:
                    errors.append(f"Approved provider {pid} has mismatched {field}.")
            if "market for electricity" in str(entry.get("name", "")).lower() or str(entry.get("name","")).lower().startswith("market group for electricity"):
                errors.append(f"Approved provider {pid} looks like a downstream electricity market.")
    if approved_count == 0:
        errors.append("No generation provider entries are marked approved; review the library first.")
    markets = library.get("markets", [])
    if markets is not None and not isinstance(markets, list):
        errors.append("markets must be a list.")
    elif isinstance(markets, list):
        for i, market in enumerate(markets):
            if not isinstance(market, dict):
                errors.append(f"Market entry {i} is not an object.")
                continue
            if market.get("approved") is not True:
                continue
            if not _is_uuid(market.get("id")) or not market.get("name"):
                errors.append(f"Approved market {i} has an invalid UUID/name.")
            if market.get("kind") != "market":
                errors.append(f"Approved market {i} is not classified as a market.")
            if market.get("voltage") not in ("high", "medium", "low"):
                errors.append(f"Approved market {i} lacks a valid voltage.")
            if "market" not in str(market.get("name", "")).lower():
                errors.append(f"Approved market {i} has no market activity name.")
    return errors


# Classification uses activity names only, so every provider still needs instructor review.
# The fallback also supports approved v0.5 catalogs that lack a provider_class field.
PROVIDER_CLASSES = ("generation", "cogeneration", "industrial_coproduct", "storage", "review")


def classify_provider_name(name: str) -> str:
    """Conservative, explainable classification of electricity-reference activities."""
    n = (name or "").lower().strip()
    if any(x in n for x in ("pumped storage", "pumped-storage", "pump storage")):
        return "storage"
    if any(x in n for x in (
        "heat and power co-generation", "heat and power cogeneration",
        "combined heat and power", "co-generation", "cogeneration"
    )):
        return "cogeneration"
    if n.startswith(("electricity production", "electricity generation")):
        return "generation"
    if any(x in n for x in (
        "pulp production", "sulfate pulp", "ethanol production",
        "sawmill", "refinery", "chemical production",
        "treatment of", "recycling"
    )):
        return "industrial_coproduct"
    return "review"


def provider_class(entry: Mapping[str, Any]) -> str:
    value = entry.get("provider_class")
    return value if value in PROVIDER_CLASSES else classify_provider_name(str(entry.get("name", "")))


def region_preference(location: str, region: str) -> tuple[int, str]:
    """Sort by geographic relevance, without treating proximity as scientific validity.

    Handles common Canada/Ontario labels (including IESO Northwest), other
    explicit 'Canada, Province' regions, and fallback exact/country matches.
    """
    loc = (location or "").casefold().strip()
    target = (region or "").casefold().strip()
    if not target or "hypothetical" in target or target.startswith(("demo", "custom")):
        return 4, loc
    if "ieso northwest" in target or "northwest ontario" in target or "ontario" in target:
        return (0 if loc == "canada, ontario" else
                1 if loc.startswith("canada,") else
                2 if loc.startswith("north america") else
                3 if loc in ("rest of world", "global") else 4, loc)
    if target.startswith("canada,"):
        province = target.split("|", 1)[0].split(" — ", 1)[0].strip()
        return (0 if loc == province else
                1 if loc.startswith("canada,") else
                2 if loc.startswith("north america") else
                3 if loc in ("rest of world", "global") else 4, loc)
    # For unfamiliar region names show exact matches first, then avoid assumptions.
    if loc and (loc == target or loc in target):
        return 0, loc
    if loc in ("rest of world", "global"):
        return 3, loc
    return 4, loc


def ranked_candidates(library: Mapping[str, Any], technology: str, region: str,
                      geography: str | None = None, search: str = "",
                      include_advanced: bool = False) -> list[dict]:
    """Instructor-approved providers, ranked geographically and by process role."""
    options = approved_candidates(library, technology, geography)
    query = search.casefold().strip()
    if query:
        options = [e for e in options if query in
                   (str(e.get("name", "")) + " " + str(e.get("location", ""))).casefold()]
    if not include_advanced:
        options = [e for e in options if provider_class(e) in ("generation", "cogeneration")]
    role_rank = {"generation": 0, "cogeneration": 1, "industrial_coproduct": 2, "storage": 3, "review": 4}
    return sorted(options, key=lambda e: (
        region_preference(e.get("location", ""), region)[0],
        role_rank[provider_class(e)],
        e.get("location", ""),
        e.get("name", ""),
        e.get("id", ""),
    ))


def approved_candidates(library: Mapping[str, Any], technology: str | None = None,
                        geography: str | None = None, include_other: bool = False) -> list[dict]:
    """Return only instructor-approved providers, optionally narrowed by technology/region."""
    entries = [e for e in library.get("entries", []) if isinstance(e, dict) and e.get("approved") is True]
    if technology and not include_other:
        entries = [e for e in entries if e.get("technology") == technology]
    if geography and geography != "All geographies":
        entries = [e for e in entries if e.get("location", "Not specified") == geography]
    return sorted(entries, key=lambda e: (e.get("location", ""), e.get("name", ""), e.get("id", "")))


def approved_markets(library: Mapping[str, Any], voltage: str | None = None) -> list[dict]:
    """Electricity markets are for baseline selection only, never generator shares."""
    markets = [m for m in library.get("markets", [])
               if isinstance(m, dict) and m.get("approved") is True]
    if voltage:
        markets = [m for m in markets if m.get("voltage") == voltage]
    return sorted(markets, key=lambda m: (m.get("location", ""), m.get("name", "")))


def catalog_for_selection(library: Mapping[str, Any], selected: Mapping[str, str],
                          rationales: Mapping[str, str] | None = None) -> dict:
    """Create the exporter catalog with chosen provider metadata and explanations."""
    errors = library_errors(library)
    if errors:
        raise ValueError("Invalid provider library: " + "; ".join(errors))
    approved = {e["id"]: e for e in approved_candidates(library)}
    providers = {}
    used_ids = set()
    for technology, pid in selected.items():
        if technology not in TECHNOLOGIES:
            raise ValueError(f"Unknown scenario technology: {technology}")
        entry = approved.get(pid)
        if not entry:
            raise ValueError(f"Provider {pid} for {technology} is absent or not approved.")
        if entry.get("technology") != technology:
            raise ValueError(f"Provider {pid} was reviewed for {entry.get('technology')}, not {technology}.")
        if pid in used_ids:
            raise ValueError("Do not assign the same provider to multiple technology shares; combine them instead.")
        used_ids.add(pid)
        providers[technology] = {
            "id": entry["id"],
            "name": entry["name"],
            "flow_id": entry["flow_id"],
            "unit_id": entry["unit_id"],
            "flow_property_id": entry["flow_property_id"],
            "provider_class": provider_class(entry),
            "location": entry.get("location", "Not specified"),
            "selection_reason": str((rationales or {}).get(technology, "")).strip()[:500],
        }
    return {
        "catalog_version": 1,
        "approved": True,
        "approved_by": library["approved_by"],
        "reviewed_date": library["reviewed_date"],
        "database_label": library["database_label"],
        "system_model": "cut-off",
        "voltage": "high",
        "reference_output": library["reference_output"],
        "providers": providers,
    }
