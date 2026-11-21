"""Dependency-free validation and calculations for student electricity LCA scenarios.

No licensed data, official region factors or upstream LCIs are bundled.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Mapping, Any
import csv
import io
import json
import math

TECHNOLOGIES = ("hydro", "nuclear", "natural_gas", "wind", "solar", "biomass", "coal", "import", "other")
BOUNDARIES = ("consumption", "generation", "hypothetical")
EVIDENCE = ("illustrative", "user_supplied_unverified", "verified")


def parse_mix_csv(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not reader.fieldnames or not {"technology", "share"}.issubset(reader.fieldnames):
        raise ValueError("Mix CSV requires headers: technology,share (and optionally source_url,notes,ci_lifecycle_g_per_kwh).")
    rows = []
    for n, r in enumerate(reader, start=2):
        tech = str(r.get("technology", "")).strip().lower()
        try:
            share = float(r.get("share", ""))
        except (ValueError, TypeError):
            raise ValueError(f"Row {n}: share must be numeric") from None
        ci_text = str(r.get("ci_lifecycle_g_per_kwh") or "").strip()
        ci = None
        if ci_text:
            try:
                ci = float(ci_text)
            except ValueError:
                raise ValueError(f"Row {n}: lifecycle CI must be numeric") from None
        rows.append({"technology": tech, "share": share, "source_url": str(r.get("source_url") or "").strip(),
                     "notes": str(r.get("notes") or "").strip(), "ci_lifecycle_g_per_kwh": ci})
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
        ci = r.get("ci_lifecycle_g_per_kwh")
        if ci is not None:
            try:
                if not math.isfinite(float(ci)) or float(ci) < 0:
                    errors.append(f"Lifecycle CI for {t} must be nonnegative and finite.")
            except (ValueError, TypeError):
                errors.append(f"Lifecycle CI for {t} must be numeric.")
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


def regional_lifecycle_ci(payload: Mapping[str, Any]) -> float | None:
    """Weighted lifecycle CI (g/kWh delivered); None if any technology CI is absent.

    No standalone infrastructure is modeled; provider CI values must already include
    appropriate upstream impacts at their specified electricity output boundary.
    """
    rows = payload["mix"]
    if any(r.get("ci_lifecycle_g_per_kwh") is None for r in rows if float(r["share"]) > 0):
        return None
    return sum(float(r["share"]) * float(r["ci_lifecycle_g_per_kwh"]) for r in rows if float(r["share"]) > 0) / (1 - float(payload.get("loss_fraction", 0)))


def project_sensitivity(baseline_total_kg: float, electricity_kwh: float,
                        original_lifecycle_g: float, alternate_lifecycle_g: float) -> dict:
    if min(electricity_kwh, original_lifecycle_g, alternate_lifecycle_g) < 0:
        raise ValueError("Electricity and CI inputs must be nonnegative.")
    if baseline_total_kg < 0:
        raise ValueError("Baseline total impact must be nonnegative.")
    baseline_electricity = electricity_kwh * original_lifecycle_g / 1000
    if baseline_electricity > baseline_total_kg + 1e-8:
        raise ValueError("Baseline electricity contribution exceeds baseline total: check units or boundaries.")
    adjusted = baseline_total_kg + electricity_kwh * (alternate_lifecycle_g - original_lifecycle_g) / 1000
    return {"original_total_kg_co2e": baseline_total_kg, "updated_total_kg_co2e": adjusted,
            "delta_kg_co2e": adjusted-baseline_total_kg, "baseline_electricity_kg_co2e": baseline_electricity,
            "alternate_electricity_kg_co2e": electricity_kwh * alternate_lifecycle_g/1000,
            "percent_change": 100 * (adjusted-baseline_total_kg) / baseline_total_kg if baseline_total_kg else None}


def direct_factor_correction(baseline_lifecycle_g: float,
                             baseline_direct_g: float, alternate_direct_g: float) -> float:
    """Screening correction only. Assumes unchanged non-direct lifecycle burden."""
    if any((not math.isfinite(x)) or x < 0 for x in (baseline_lifecycle_g, baseline_direct_g, alternate_direct_g)):
        raise ValueError("Factors must be finite and nonnegative.")
    if baseline_direct_g > baseline_lifecycle_g:
        raise ValueError("Baseline direct factor exceeds full lifecycle factor; check boundaries.")
    return baseline_lifecycle_g + (alternate_direct_g - baseline_direct_g)



def dump_supply_mix_csv(rows: list[dict]) -> str:
    """CSV of the inputs needed to model electricity providers in openLCA."""
    stream = io.StringIO()
    fields = ["technology", "share", "source_url", "notes"]
    writer = csv.DictWriter(
        stream, fieldnames=fields, extrasaction="ignore", lineterminator="\\n"
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
        source = str(row.get("source_url") or "Not documented").replace("|", r"\\|")
        notes = str(row.get("notes") or "").replace("|", r"\\|")
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
    return "\\n".join(lines)



def dump_mix_csv(rows: list[dict]) -> str:
    s = io.StringIO()
    fields = ["technology", "share", "ci_lifecycle_g_per_kwh", "source_url", "notes"]
    w = csv.DictWriter(s, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    for row in rows:
        w.writerow({k: ("" if row.get(k) is None else row.get(k)) for k in fields})
    return s.getvalue()


def scenario_report(payload: Mapping[str, Any], errors: list[str], warnings: list[str], lifecycle_ci: float | None) -> str:
    from datetime import date
    title = str(payload.get("region", "unknown"))
    lines = [f"# Electricity scenario: {title}", "", f"Generated: {date.today().isoformat()}", "",
             f"- Reference year: {payload.get('year')}", f"- Spatial boundary: {payload.get('boundary')}",
             f"- Evidence status: {payload.get('evidence_status')}", f"- Voltage: {payload.get('voltage')}",
             f"- Loss fraction (simple scaling only): {payload.get('loss_fraction')}",
             f"- Main source: {payload.get('source_url', '')}",
             f"- Background dataset: {payload.get('ecoinvent_version', 'not specified')}", "",
             "## Methodological cautions", "",
             "- This is a scenario, not a verified measured regional CI unless independently validated.",
             "- All provider CI values, if entered, must be lifecycle CI in g CO2e per kWh at comparable boundaries.",
             "- The method scales input electricity for losses; it does not add new T&D infrastructure LCIs.",
             "- Avoid mixing operational emission factors with life-cycle emission factors.",
             "- A generated local supply mix may not represent electricity delivered to consumers.", "",
             f"Calculated scenario CI: {lifecycle_ci:.3f} g CO2e/kWh delivered (screening estimate)" if lifecycle_ci is not None else "Calculated scenario CI: unavailable (technology-specific lifecycle factors not supplied)", "",
             "## Supply shares", "",
             "| Technology | Share | Lifecycle CI (g/kWh) | Source |", "|---|---:|---:|---|"]
    for r in payload['mix']:
        ci = r.get('ci_lifecycle_g_per_kwh')
        lines.append(f"| {r['technology']} | {float(r['share']):.1%} | {'' if ci is None else ci} | {r.get('source_url', '')} |")
    lines += ["", "## Validation", "", "Errors:"]
    lines += [f"- {x}" for x in errors] or ["- None"]
    lines += ["", "Warnings:"]
    lines += [f"- {x}" for x in warnings] or ["- None"]
    return "\n".join(lines) + "\n"
