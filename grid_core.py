"""Dependency-free validation and documentation for electricity LCA scenarios.

No licensed data, official region factors or upstream LCIs are bundled.
"""
from __future__ import annotations
from typing import Mapping, Any
import csv
import io
import math

TECHNOLOGIES = ("hydro", "nuclear", "natural_gas", "wind", "solar", "biomass", "coal", "import", "other")
BOUNDARIES = ("consumption", "generation", "hypothetical")
EVIDENCE = ("illustrative", "user_supplied_unverified", "verified")


def parse_mix_csv(text: str) -> list[dict]:
    """Read documented generation shares; emissions factors are not accepted."""
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or not {"technology", "share"}.issubset(reader.fieldnames):
        raise ValueError(
            "Mix CSV requires headers: technology,share "
            "(optionally source_url,notes)."
        )
    if any("ci_lifecycle" in str(h).lower() or "gwp" in str(h).lower()
           for h in reader.fieldnames):
        raise ValueError(
            "This file uses an obsolete carbon-intensity/GWP column. "
            "Remove the column and provide only technology, share, source_url, notes."
        )
    rows = []
    for n, r in enumerate(reader, start=2):
        tech = str(r.get("technology", "")).strip().lower()
        try:
            share = float(r.get("share", ""))
        except (ValueError, TypeError):
            raise ValueError(f"Row {n}: share must be numeric") from None
        rows.append({
            "technology": tech,
            "share": share,
            "source_url": str(r.get("source_url") or "").strip(),
            "notes": str(r.get("notes") or "").strip(),
        })
    return rows

def validate_scenario(payload: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    rows = payload.get("mix", [])
    if not isinstance(rows, list) or not rows:
        errors.append("At least one generation/supply row is required.")
        return errors, warnings
    if payload.get("boundary") not in BOUNDARIES:
        errors.append("Boundary must be consumption, generation, or hypothetical.")
    if payload.get("evidence_status") not in EVIDENCE:
        errors.append("Evidence status must be illustrative, user_supplied_unverified, or verified.")
    if not str(payload.get("region", "")).strip():
        errors.append("Region is required.")
    try:
        y = int(payload.get("year", 0))
        if not 1990 <= y <= 2100:
            errors.append("Year must be 1990–2100.")
    except (ValueError, TypeError):
        errors.append("Year must be an integer.")
    try:
        loss = float(payload.get("loss_fraction", 0))
        if not 0 <= loss < 0.35:
            errors.append("Loss fraction must be in [0,0.35).")
    except (TypeError, ValueError):
        errors.append("Loss fraction must be numeric.")
    seen = set()
    for r in rows:
        t = str(r.get("technology", "")).strip().lower()
        if t not in TECHNOLOGIES:
            errors.append(f"Unknown technology: {t}. Valid values: {', '.join(TECHNOLOGIES)}")
        if t in seen:
            errors.append(f"Duplicate technology row: {t}; consolidate contributions.")
        seen.add(t)
        try:
            share = float(r.get("share", 0))
            if not math.isfinite(share) or not 0 <= share <= 1:
                errors.append(f"Share for {t} must be between 0 and 1.")
        except (ValueError, TypeError):
            errors.append(f"Share for {t} must be numeric.")
    try:
        total = sum(float(x["share"]) for x in rows)
        if not math.isclose(total, 1.0, abs_tol=0.0001):
            errors.append(f"Supply shares sum to {total:.4f}, not 1.0000.")
    except (ValueError, KeyError, TypeError):
        pass
    if payload.get("boundary") == "generation":
        warnings.append("Generation mix ≠ consumption mix: regional imports, exports, and interzonal transfers may be missing.")
    if payload.get("boundary") == "hypothetical":
        warnings.append("Hypothetical scenario: do not call this the measured grid mix for the named region.")
    if payload.get("evidence_status") != "verified":
        warnings.append("Scenario not verified against a documented official supply mix; label as sensitivity analysis.")
    if any(r.get("technology") == "import" for r in rows):
        warnings.append("Import share requires an explicit supplier mix; do not use an arbitrary local technology proxy.")
    if float(payload.get("loss_fraction", 0) or 0) > 0:
        warnings.append("Losses are approximated by scaling upstream kWh. Grid infrastructure is NOT included by this adjustment.")
    if not str(payload.get("source_url", "")).strip():
        warnings.append("Scenario-level source URL missing.")
    if not str(payload.get("year", "")).strip():
        warnings.append("Reference year missing.")
    if any(not r.get("source_url") for r in rows if float(r.get("share", 0)) > 0):
        warnings.append("At least one technology share lacks a row-level data source.")
    return errors, warnings


def dump_supply_mix_csv(rows: list[dict]) -> str:
    """CSV of the inputs needed to model electricity providers in openLCA."""
    stream = io.StringIO()
    fields = ["technology", "share", "source_url", "notes"]
    writer = csv.DictWriter(
        stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({
            key: "" if row.get(key) is None else row.get(key)
            for key in fields
        })
    return stream.getvalue()


def scenario_documentation_report(payload: Mapping[str, Any], errors: list[str],
                                  warnings: list[str],
                                  selected_providers: Mapping[str, Any] | None = None) -> str:
    """Document modeling assumptions without estimating life-cycle carbon intensity."""
    from datetime import date
    lines = [
        f"# Custom electricity supply scenario: {payload.get('region', 'Unknown')}",
        "",
        f"- Generated: {date.today().isoformat()}",
        f"- Reference year: {payload.get('year')}",
        f"- Mix boundary: {payload.get('boundary')}",
        f"- Evidence status: {payload.get('evidence_status')}",
        f"- Electricity delivery level: {payload.get('voltage')}",
        f"- Simplified loss fraction: {payload.get('loss_fraction')}",
        f"- Primary source: {payload.get('source_url') or 'Not documented'}",
        f"- Background database: {payload.get('ecoinvent_version') or 'Not specified'}",
        "",
        "## Generation / supply shares",
        "",
        "| Technology | Share | Source URL | Notes |",
        "|---|---:|---|---|",
    ]
    for row in payload.get("mix", []):
        tech = str(row.get("technology", ""))
        share = float(row.get("share", 0) or 0)
        source = str(row.get("source_url") or "Not documented").replace("|", r"\|")
        notes = str(row.get("notes") or "").replace("|", r"\|")
        lines.append(f"| {tech} | {share:.4%} | {source} | {notes} |")
    lines += [
        "",
        "## Selected openLCA providers",
        "",
    ]
    if selected_providers:
        for tech, entry in selected_providers.items():
            lines += [
                f"### {tech}",
                f"- Process: {entry.get('process_name', 'Not specified')}",
                f"- Process UUID: {entry.get('process_id', 'Not specified')}",
                f"- Geography: {entry.get('location', 'Not specified')}",
                f"- Selection rationale: {entry.get('selection_reason') or 'Not documented'}",
                "",
            ]
    else:
        lines += [
            "No validated provider choices accompanied this export.",
            "Choose providers in Tab 2 before exporting the linked openLCA process.",
            "",
        ]
    lines += [
        "## Validation and representativeness",
        "",
        f"- Arithmetic errors: {len(errors)}",
    ]
    lines += [f"  - {error}" for error in errors] or ["  - None"]
    lines += [f"- Scientific/data advisories: {len(warnings)}"]
    lines += [f"  - {warning}" for warning in warnings] or ["  - None"]
    lines += [
        "",
        "## Methodological cautions",
        "",
        "- Regional generation shares may differ from electricity consumed due to transfers and imports.",
        "- This document does not establish an independently verified or certified electricity mix.",
        "- Imported provider references require testing against the matching licensed openLCA database.",
        "- This scenario does not calculate an electricity carbon intensity or life-cycle impacts.",
        "- Simple loss scaling does not represent electricity transmission or distribution infrastructure.",
        "",
    ]
    return "\n".join(lines)
