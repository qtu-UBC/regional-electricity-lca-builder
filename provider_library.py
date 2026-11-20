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
        if entry.get("approved") is True:
            approved_count += 1
            for field, ref_key in (("flow_id", "flow"), ("unit_id", "unit"), ("flow_property_id", "flow_property")):
                if entry.get(field) != ref[ref_key]["id"]:
                    errors.append(f"Approved provider {pid} has mismatched {field}.")
            if "market for electricity" in str(entry.get("name", "")).lower() or str(entry.get("name","")).lower().startswith("market group for electricity"):
                errors.append(f"Approved provider {pid} looks like a downstream electricity market.")
    if approved_count == 0:
        errors.append("No provider entries are marked approved; review the extraction CSV first.")
    return errors


def approved_candidates(library: Mapping[str, Any], technology: str | None = None,
                        geography: str | None = None, include_other: bool = False) -> list[dict]:
    """Return only instructor-approved providers, optionally narrowed by technology/region."""
    entries = [e for e in library.get("entries", []) if isinstance(e, dict) and e.get("approved") is True]
    if technology and not include_other:
        entries = [e for e in entries if e.get("technology") == technology]
    if geography and geography != "All geographies":
        entries = [e for e in entries if e.get("location", "Not specified") == geography]
    return sorted(entries, key=lambda e: (e.get("location", ""), e.get("name", ""), e.get("id", "")))


def catalog_for_selection(library: Mapping[str, Any], selected: Mapping[str, str]) -> dict:
    """Build the v0.2 exporter-compatible catalog from explicit student choices."""
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
        if pid in used_ids:
            raise ValueError("Do not assign the same provider to multiple technology shares; combine them instead.")
        used_ids.add(pid)
        providers[technology] = {
            "id": entry["id"],
            "name": entry["name"],
            "flow_id": entry["flow_id"],
            "unit_id": entry["unit_id"],
            "flow_property_id": entry["flow_property_id"],
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
