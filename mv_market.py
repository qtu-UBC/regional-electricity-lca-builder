"""Validated, region-adapted high-to-medium voltage foreground JSON-LD packages.

The adapter is extracted locally from the SAME licensed openLCA database as the
approved generator library. No ecoinvent coefficients are embedded in this code.
A replication export is provided before the custom all-HV supply substitution.
This is an attributional modeling sensitivity tool, not a grid verifier.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import uuid
import zipfile
from typing import Any, Mapping

from openlca_jsonld import NAMESPACE, _ref, _uuid, make_process, validate_catalog


def _electricity_voltage(flow: Mapping[str, Any]) -> str | None:
    name = str(flow.get("name", "")).casefold().strip()
    for v in ("high", "medium", "low"):
        if name == f"electricity, {v} voltage" or name.startswith(f"electricity, {v} voltage,"):
            return v
    return None


def _output(process: Mapping[str, Any]) -> Mapping[str, Any]:
    results = [x for x in process.get("exchanges", [])
               if not x.get("is_input") and x.get("is_quantitative_reference")]
    if len(results) != 1:
        raise ValueError("Expected exactly one quantitative reference output.")
    return results[0]


def _electric_inputs(process: Mapping[str, Any], voltage: str) -> list[dict]:
    return [x for x in process["exchanges"]
            if x.get("is_input") and _electricity_voltage(x["flow"]) == voltage]


def _p_id(x: Mapping[str, Any]) -> str | None:
    p = x.get("provider")
    return str(p.get("id")) if isinstance(p, dict) and p.get("id") else None


def _is_finite_nonnegative(n: Any) -> bool:
    try:
        v = float(n)
        return math.isfinite(v) and v >= 0
    except (TypeError, ValueError, OverflowError):
        return False


REVIEW_STAGES = ("extracted", "reviewed_for_testing", "replication_validated")


def adapter_review_status(adapter: Mapping[str, Any] | None) -> str:
    """Legacy approved=true is NOT proof of replication validation."""
    if not isinstance(adapter, dict):
        return "extracted"
    return str(adapter.get("review_status") or "extracted")


def source_fingerprint(adapter: Mapping[str, Any]) -> str:
    """Stable digest of the source exchange graph; ignores workflow state."""
    source = {k: adapter.get(k) for k in
              ("adapter_version", "database_label", "system_model", "region", "processes")}
    return hashlib.sha256(json.dumps(
        source, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8")).hexdigest()


def validate_mv_structure(adapter: Any) -> tuple[list[str], list[str]]:
    """Check source-region market topology; no catalog, approval or scenario needed."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(adapter, dict):
        return ["An extracted regional MV adapter JSON object is required."], warnings
    if adapter.get("adapter_version") != 1:
        errors.append("MV adapter_version must be 1.")
    if adapter_review_status(adapter) not in REVIEW_STAGES:
        errors.append("Unknown review_status; must be extracted, reviewed_for_testing or replication_validated.")
    if not str(adapter.get("region", "")).strip():
        errors.append("MV adapter must identify its source geography.")
    label = str(adapter.get("database_label") or "")
    if adapter.get("system_model") != "cut-off" or "3.12" not in label or "cut" not in label.casefold():
        errors.append("MV adapter must identify ecoinvent 3.12 cut-off.")
    if adapter.get("extraction_truncated"):
        errors.append("Truncated MV adapter discovery is not suitable for replication.")
    templates = adapter.get("processes")
    if not isinstance(templates, dict):
        return errors + ["MV adapter processes must be an object."], warnings
    keys = ("hv_market", "transformation", "mv_market")
    expected = {"hv_market": "high", "transformation": "medium", "mv_market": "medium"}
    try:
        for key in keys:
            p = templates[key]
            _uuid(p["id"], f"{key} process")
            if not str(p.get("name", "")).strip():
                errors.append(f"{key} process has no name.")
            exchanges = p["exchanges"]
            if not isinstance(exchanges, list) or not exchanges:
                errors.append(f"{key} has no exchanges.")
                continue
            out = _output(p)
            if _electricity_voltage(out["flow"]) != expected[key]:
                errors.append(f"{key} reference output must be {expected[key]} voltage electricity.")
            if not math.isclose(float(out["amount"]), 1.0, rel_tol=0, abs_tol=1e-10):
                errors.append(f"{key} reference output must be 1 kWh for this adapter.")
            if str(out["unit"].get("name", "")).lower().replace(" ", "") not in (
                    "kwh", "kilowatthour", "kilowatt-hour"):
                errors.append(f"{key} reference output must be in kWh.")
            for index, x in enumerate(exchanges):
                if not _is_finite_nonnegative(x.get("amount")):
                    errors.append(f"{key} exchange {index} has invalid amount.")
                for field in ("flow", "unit", "flow_property"):
                    if not isinstance(x.get(field), dict):
                        errors.append(f"{key} exchange {index} lacks {field}.")
                        continue
                    _uuid(x[field].get("id"), f"{key} {field}")
                if x.get("is_input") and not _p_id(x):
                    errors.append(f"{key} input {index} has no explicit provider; resolve locally first.")
        hv, trans, mv = (templates[k] for k in keys)
        if len({hv["id"], trans["id"], mv["id"]}) != 3:
            errors.append("HV market, transformation and MV market must be distinct processes.")
        hv_ref, trans_ref, mv_ref = (_output(p) for p in (hv, trans, mv))
        for field in ("flow", "unit", "flow_property"):
            if trans_ref[field]["id"] != mv_ref[field]["id"]:
                errors.append(f"MV transformation and MV market {field} do not match.")
        hvin = _electric_inputs(hv, "high")
        if not any(_p_id(x) != hv["id"] and float(x["amount"]) > 0 for x in hvin):
            errors.append("HV market must contain external high-voltage electricity inputs.")
        for x in hv["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("medium", "low"):
                errors.append("HV market has non-HV electricity inputs; unsupported topology.")
        for x in hvin:
            for field in ("flow", "unit", "flow_property"):
                if x[field]["id"] != hv_ref[field]["id"]:
                    errors.append(f"HV market electricity input has mismatched {field}.")
        transform_hv = _electric_inputs(trans, "high")
        if len(transform_hv) != 1 or _p_id(transform_hv[0]) != hv["id"]:
            errors.append("Transformer must have exactly one HV input from the selected HV market.")
        for x in transform_hv:
            for field in ("flow", "unit", "flow_property"):
                if x[field]["id"] != hv_ref[field]["id"]:
                    errors.append(f"Transformer HV input has mismatched {field}.")
        for x in trans["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("medium", "low"):
                errors.append("Transformer has additional electricity inputs; unsupported topology.")
        mvin = _electric_inputs(mv, "medium")
        if len([x for x in mvin if _p_id(x) == trans["id"]]) != 1:
            errors.append("MV market must have exactly one medium-voltage input from transformer.")
        for x in mvin:
            for field in ("flow", "unit", "flow_property"):
                if x[field]["id"] != mv_ref[field]["id"]:
                    errors.append(f"MV market electricity input has mismatched {field}.")
        if not any(_p_id(x) == mv["id"] for x in mvin):
            warnings.append("No MV self-consumption exchange; may be correct for source region.")
        for x in mv["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("high", "low"):
                errors.append("MV market has other-voltage electricity inputs; unsupported topology.")
        if not any(_p_id(x) != mv["id"] and float(x["amount"]) > 0 for x in mvin):
            errors.append("MV market has no upstream non-self electricity supply.")
        if any(_p_id(x) == mv["id"] for x in hvin + transform_hv):
            errors.append("An upstream HV exchange incorrectly references the MV market.")
        if sum(float(x["amount"]) for x in mvin if _p_id(x) == mv["id"]) >= 1:
            errors.append("MV self-input fraction must be below 1 for a solvable market.")
        if sum(float(x["amount"]) for x in hvin if _p_id(x) == hv["id"]) >= 1:
            errors.append("HV self-input fraction must be below 1 for a solvable market.")
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        errors.append(f"MV adapter structure is incomplete or invalid: {exc}")
    warnings += [
        "Source topology checks cannot establish equality of LCIA results in openLCA.",
        "The replicated processes retain exchange amounts and providers but omit some process metadata and uncertainties.",
    ]
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def mark_reviewed_for_testing(adapter: Mapping[str, Any], reviewer: str,
                              notes: str, reviewed_date: str | None = None) -> dict:
    """Explicit, local instructor attestation; no scientific approval implied."""
    from datetime import date
    errors, _ = validate_mv_structure(adapter)
    if errors:
        raise ValueError("Source topology invalid: " + "; ".join(errors))
    if not str(reviewer).strip() or len(str(notes).strip()) < 12:
        raise ValueError("Record a reviewer and meaningful source-link review notes (12+ characters).")
    result = json.loads(json.dumps(adapter))
    result["review_status"] = "reviewed_for_testing"
    result["reviewed_by"] = str(reviewer).strip()
    result["reviewed_date"] = reviewed_date or date.today().isoformat()
    result["review_notes"] = str(notes).strip()
    result.pop("replication_validation", None)
    result.pop("approved", None)  # Old single flag is obsolete for MV.
    return result


def replication_comparisons_errors(comparisons: Any,
                                   tolerance_percent: float = 0.1) -> list[str]:
    errors = []
    if not isinstance(comparisons, list) or len(comparisons) < 2:
        return ["Provide at least two LCIA categories: climate change and one other."]
    if not _is_finite_nonnegative(tolerance_percent) or tolerance_percent <= 0 or tolerance_percent > 5:
        errors.append("Tolerance must be >0 and <=5 percent.")
        return errors
    categories = set()
    climate = False
    for index, row in enumerate(comparisons):
        if not isinstance(row, dict):
            errors.append(f"Impact row {index+1} must be an object.")
            continue
        category = str(row.get("category") or "").strip()
        unit = str(row.get("unit") or "").strip()
        if not category or not unit:
            errors.append(f"Impact row {index+1} needs category and unit.")
        if category.casefold() in categories:
            errors.append("Impact categories must be distinct.")
        categories.add(category.casefold())
        if any(x in category.casefold() for x in ("climate", "gwp", "global warming")):
            climate = True
        try:
            original = float(row.get("original"))
            replicated = float(row.get("replicated"))
            if not math.isfinite(original) or not math.isfinite(replicated):
                raise ValueError("nonfinite")
            delta = abs(original - replicated)
            limit = max(1e-12, abs(original) * float(tolerance_percent)/100)
            if delta > limit:
                errors.append(
                    f"{category or 'Impact row '+str(index+1)} exceeds tolerance: "
                    f"absolute difference {delta:.7g} > {limit:.7g} {unit}."
                )
        except (TypeError, ValueError, OverflowError):
            errors.append(f"Impact row {index+1} has non-numeric or non-finite results.")
    if not climate:
        errors.append("Include a climate change / GWP category in the replication evidence.")
    return errors


def record_replication_validation(
    adapter: Mapping[str, Any], *, checked_by: str, method: str,
    comparisons: list[dict], notes: str, links_checked: bool,
    tolerance_percent: float = 0.1, checked_date: str | None = None
) -> dict:
    """Store *instructor-entered* openLCA evidence, not an independent model calculation."""
    from datetime import date
    errors, _ = validate_mv_structure(adapter)
    if errors:
        raise ValueError("Invalid source topology: " + "; ".join(errors))
    if adapter_review_status(adapter) not in ("reviewed_for_testing", "replication_validated"):
        raise ValueError("First mark the adapter reviewed_for_testing.")
    if not str(checked_by).strip() or not str(method).strip() or len(str(notes).strip()) < 12:
        raise ValueError("Record reviewer, LCIA method and a meaningful comparison note.")
    if links_checked is not True:
        raise ValueError("Explicitly confirm you inspected all copied process/provider links in openLCA.")
    comparison_errors = replication_comparisons_errors(comparisons, tolerance_percent)
    if comparison_errors:
        raise ValueError("LCIA replication not validated: " + "; ".join(comparison_errors))
    result = json.loads(json.dumps(adapter))
    result["review_status"] = "replication_validated"
    result["replication_validation"] = {
        "source_fingerprint": source_fingerprint(adapter),
        "original_mv_process_id": adapter["processes"]["mv_market"]["id"],
        "replicated_mv_process_id": make_mv_replication_processes(adapter)[-1]["@id"],
        "functional_unit": "1 kWh of medium-voltage electricity",
        "lcia_method": str(method).strip(),
        "comparisons": comparisons,
        "tolerance_percent": float(tolerance_percent),
        "links_checked": True,
        "checked_by": str(checked_by).strip(),
        "checked_date": checked_date or date.today().isoformat(),
        "notes": str(notes).strip(),
        "evidence_origin": "instructor-entered openLCA comparison; not independently retrieved",
    }
    return result


def replication_evidence_errors(adapter: Mapping[str, Any]) -> list[str]:
    """Recompute numeric checks and bind evidence to this exact source topology."""
    if adapter_review_status(adapter) != "replication_validated":
        return ["Customized MV export requires a recorded replication_validated stage."]
    evidence = adapter.get("replication_validation")
    if not isinstance(evidence, dict):
        return ["Replication validation record is missing."]
    errors = []
    if evidence.get("source_fingerprint") != source_fingerprint(adapter):
        errors.append("Source process data changed since LCIA replication; rerun the test.")
    if evidence.get("original_mv_process_id") != adapter["processes"]["mv_market"]["id"]:
        errors.append("Recorded source MV process does not match this adapter.")
    if evidence.get("replicated_mv_process_id") != make_mv_replication_processes(adapter)[-1]["@id"]:
        errors.append("Recorded replicated MV process ID is stale.")
    if evidence.get("functional_unit") != "1 kWh of medium-voltage electricity":
        errors.append("Replication must use a 1 kWh MV functional unit.")
    if not evidence.get("links_checked") or not str(evidence.get("lcia_method") or "").strip():
        errors.append("Replication evidence must include inspected links and LCIA method.")
    if not str(evidence.get("checked_by") or "").strip() or not str(evidence.get("checked_date") or "").strip():
        errors.append("Replication evidence lacks reviewer or date.")
    if len(str(evidence.get("notes") or "").strip()) < 12:
        errors.append("Replication evidence needs a meaningful comparison note.")
    errors += replication_comparisons_errors(
        evidence.get("comparisons"), evidence.get("tolerance_percent", 0.1)
    )
    return errors


def validate_mv_adapter(adapter: Any, catalog: Mapping[str, Any],
                        scenario: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Custom MV export gate: source topology + reviewed LCIA + generator catalog."""
    errors, warnings = validate_mv_structure(adapter)
    if errors:
        return errors, warnings
    errors += replication_evidence_errors(adapter)
    if scenario.get("voltage") != "medium":
        errors.append("Medium-voltage export requires delivery level medium.")
    if float(scenario.get("loss_fraction", 0) or 0) != 0:
        errors.append("Set simplified loss scaling to 0 for MV: adapter already models network losses.")
    if not isinstance(catalog, dict):
        errors.append("Custom MV export requires an instructor-approved generator catalog.")
    else:
        if adapter["database_label"] != catalog.get("database_label"):
            errors.append("MV adapter and generator catalog must identify the same restored .zolca.")
        high = dict(scenario, voltage="high", loss_fraction=0.0)
        cat_errors, cat_warnings = validate_catalog(catalog, high)
        errors += cat_errors
        warnings += cat_warnings
        for field, refkey in (("flow", "flow"), ("unit", "unit"), ("flow_property", "flow_property")):
            try:
                if _output(adapter["processes"]["hv_market"])[field]["id"] != catalog["reference_output"][refkey]["id"]:
                    errors.append(f"HV market {field} does not match generator catalog reference output.")
            except (KeyError, ValueError, TypeError):
                errors.append(f"Missing generator catalog reference {field}.")
    warnings += [
        "Replication is recorded from instructor-entered openLCA LCIA results, not independently verified by Streamlit.",
        "Adapter's network data are a regional proxy, not a verified Northwest-specific supply.",
        "Custom mode routes all scenario generation through HV, replacing original direct MV generation.",
        "Copied inventories omit uncertainties and other process metadata; do not claim Monte Carlo equivalence.",
    ]
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def _as_exchange(raw: Mapping[str, Any], internal_id: int, provider: Mapping[str, Any] | None = None) -> dict:
    result = {
        "@type": "Exchange", "internalId": internal_id,
        "isInput": bool(raw.get("is_input")),
        "isQuantitativeReference": bool(raw.get("is_quantitative_reference")),
        "isAvoidedProduct": bool(raw.get("is_avoided_product")),
        "amount": float(raw["amount"]),
        "flow": _ref("Flow", raw["flow"]),
        "unit": _ref("Unit", raw["unit"]),
        "flowProperty": _ref("FlowProperty", raw["flow_property"]),
    }
    source = provider if provider is not None else raw.get("provider")
    if result["isInput"] and source:
        result["defaultProvider"] = _ref("Process", source)
    if raw.get("description"):
        result["description"] = str(raw["description"])[:400]
    return result


def _new_id(prefix: str, payload: Mapping[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(
        {"role": prefix, "payload": payload}, sort_keys=True,
        default=str, ensure_ascii=False,
    ).encode("utf-8")).hexdigest()
    return str(uuid.uuid5(NAMESPACE, digest))


def _as_process(template: Mapping[str, Any], pid: str, name: str,
                raw_exchanges: list[tuple[dict, dict | None]], description: str) -> dict:
    exchanges = [_as_exchange(x, i, provider)
                 for i, (x, provider) in enumerate(raw_exchanges, start=1)]
    return {
        "@type": "Process", "@id": pid, "name": name[:240], "description": description,
        "processType": "UNIT_PROCESS", "version": "01.00.000",
        "lastInternalId": len(exchanges), "exchanges": exchanges,
    }


def make_mv_replication_processes(adapter: Mapping[str, Any]) -> list[dict]:
    """Baseline copy requires ONLY structurally valid extracted data, not approval.

    Process UUIDs depend only on source content, not workflow state, generator
    selection or scenario. This makes replication evidence stable and auditable.
    """
    errors, _ = validate_mv_structure(adapter)
    if errors:
        raise ValueError("Cannot export baseline MV replication:\n" + "\n".join(errors))
    hv, tr, mv = (adapter["processes"][k] for k in
                  ("hv_market", "transformation", "mv_market"))
    identity = {"source_fingerprint": source_fingerprint(adapter), "mode": "replication"}
    ids = {k: _new_id(f"mv-v09-{k}", identity) for k in
           ("hv_market", "transformation", "mv_market")}
    label = f"v0.9 replication of {adapter['region']} (NOT YET LCIA validated)"
    refs = {
        "hv_market": {"id": ids["hv_market"], "name": f"{label} | HV market"},
        "transformation": {"id": ids["transformation"], "name": f"{label} | HV-to-MV"},
        "mv_market": {"id": ids["mv_market"], "name": f"{label} | MV market"},
    }
    chain = []
    for key, template in (("hv_market", hv), ("transformation", tr), ("mv_market", mv)):
        substitutions = {
            "hv_market": {hv["id"]: refs["hv_market"]},
            "transformation": {hv["id"]: refs["hv_market"]},
            "mv_market": {mv["id"]: refs["mv_market"],
                          tr["id"]: refs["transformation"]},
        }[key]
        pairs = [
            (x, substitutions.get(_p_id(x)) if x.get("is_input") else None)
            for x in template["exchanges"]
        ]
        chain.append(_as_process(
            template, ids[key], refs[key]["name"], pairs,
            f"Local baseline replication of {template['name']}; "
            f"source UUID {template['id']}; source {adapter['database_label']}; "
            f"source fingerprint {source_fingerprint(adapter)}. "
            "Check openLCA provider links and compare LCIA before custom modeling."
        ))
    return chain


def mv_replication_package(adapter: Mapping[str, Any]) -> bytes:
    processes = make_mv_replication_processes(adapter)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("olca-schema.json", json.dumps({"version": 2}))
        for p in processes:
            z.writestr(f"processes/{p['@id']}.json",
                       json.dumps(p, indent=2, ensure_ascii=False))
    return buf.getvalue()


def make_mv_processes(scenario: Mapping[str, Any], catalog: Mapping[str, Any],
                      adapter: Mapping[str, Any], replicate: bool = False) -> list[dict]:
    """Three market-chain clones for baseline test, four for custom HV substitution.

    All original non-electric inputs and elementary outputs are retained. In
    custom mode, HV market external generation inputs are replaced by ONE custom
    HV generation-mix link, and MV direct generation shifts to HV pathway.
    """
    if replicate:
        return make_mv_replication_processes(adapter)
    errors, _ = validate_mv_adapter(adapter, catalog, scenario)
    if errors:
        raise ValueError("Cannot export custom MV processes:\n" + "\n".join(errors))
    src = adapter["processes"]
    hv, tr, mv = src["hv_market"], src["transformation"], src["mv_market"]
    mode = "replication" if replicate else "custom"
    identity = {
        "mode": mode, "scenario": scenario, "catalog_providers": catalog["providers"],
        "source_fingerprint": source_fingerprint(adapter),
    }
    hv_id = _new_id("mv-v09-hv-market", identity)
    tr_id = _new_id("mv-v09-transformation", identity)
    mv_id = _new_id("mv-v09-mv-market", identity)
    hv_new = {"id": hv_id, "name": f"v0.9 {mode} HV market | {adapter['region']}"}
    tr_new = {"id": tr_id, "name": f"v0.9 {mode} HV-to-MV | {adapter['region']}"}
    mv_new = {"id": mv_id, "name": f"v0.9 {mode} MV market | {scenario['region']}"}
    label = (f"Regional Electricity LCA Builder v0.9 {mode}; "
             f"source={adapter['database_label']}; "
             f"LCIA replication recorded by={adapter['replication_validation']['checked_by']}")
    built: list[dict] = []
    mix_proc = None
    if not replicate:
        high_scenario = dict(scenario, voltage="high", loss_fraction=0.0)
        mix_proc = make_process(high_scenario, catalog)
        built.append(mix_proc)

    # Retain HV market infrastructure, SF6 and any self-loop, but replace ALL
    # external high-voltage supply links in custom mode.
    hv_pairs: list[tuple[dict, dict | None]] = []
    external_kwh = 0.0
    for x in hv["exchanges"]:
        if x.get("is_input") and _electricity_voltage(x["flow"]) == "high":
            if _p_id(x) == hv["id"]:
                hv_pairs.append((x, hv_new))
            elif replicate:
                hv_pairs.append((x, None))
            else:
                external_kwh += float(x["amount"])
        else:
            hv_pairs.append((x, None))
    if not replicate:
        if external_kwh <= 0:
            raise ValueError("HV market has no external electricity to replace.")
        ref = _output(hv)
        hv_pairs.append(({
            "is_input": True, "is_quantitative_reference": False,
            "is_avoided_product": False, "amount": external_kwh,
            "flow": ref["flow"], "unit": ref["unit"],
            "flow_property": ref["flow_property"],
            "description": "All external HV suppliers replaced with custom HV generation mix; original HV network burdens retained.",
        }, {"id": mix_proc["@id"], "name": mix_proc["name"]}))
    built.append(_as_process(
        hv, hv_id, hv_new["name"], hv_pairs,
        label + "; original HV market network structure copied; self-references redirected."
    ))

    trans_pairs = [
        (x, hv_new if x.get("is_input") and _electricity_voltage(x["flow"]) == "high"
         and _p_id(x) == hv["id"] else None)
        for x in tr["exchanges"]
    ]
    built.append(_as_process(
        tr, tr_id, tr_new["name"], trans_pairs,
        label + "; original HV-to-MV coefficient and non-electric exchanges preserved."
    ))

    # In custom mode, exclude direct-MV generation from the original geography
    # and route the same non-self electricity total through the transformer.
    mv_pairs: list[tuple[dict, dict | None]] = []
    direct_mv = 0.0
    for x in mv["exchanges"]:
        if x.get("is_input") and _electricity_voltage(x["flow"]) == "medium":
            pid = _p_id(x)
            if pid == mv["id"]:
                mv_pairs.append((x, mv_new))
            elif pid == tr["id"]:
                mv_pairs.append((dict(
                    x, amount=float(x["amount"]) + (
                        0.0 if replicate else sum(
                            float(y["amount"]) for y in _electric_inputs(mv, "medium")
                            if _p_id(y) not in (mv["id"], tr["id"])
                        )
                    )), tr_new))
            elif replicate:
                mv_pairs.append((x, None))
            else:
                direct_mv += float(x["amount"])
        else:
            mv_pairs.append((x, None))
    built.append(_as_process(
        mv, mv_id, mv_new["name"], mv_pairs,
        label + (f"; original MV direct generation ({direct_mv:.9g} kWh) reallocated to HV path; "
                 "MV market self-consumption and non-electric burdens retained."
                 if not replicate else "; exact supplier topology retained with internal links redirected.")
    ))
    return built


def mv_package(scenario: Mapping[str, Any], catalog: Mapping[str, Any],
               adapter: Mapping[str, Any], replicate: bool = False) -> bytes:
    processes = (make_mv_replication_processes(adapter) if replicate else
                 make_mv_processes(scenario, catalog, adapter))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("olca-schema.json", json.dumps({"version": 2}))
        for p in processes:
            z.writestr(f"processes/{p['@id']}.json",
                       json.dumps(p, indent=2, ensure_ascii=False))
    return buf.getvalue()


def mv_preview(scenario: Mapping[str, Any], catalog: Mapping[str, Any],
               adapter: Mapping[str, Any]) -> dict:
    processes = make_mv_processes(scenario, catalog, adapter)
    tr = adapter["processes"]["transformation"]
    mv = adapter["processes"]["mv_market"]
    hv_in = _electric_inputs(tr, "high")[0]
    direct = sum(float(x["amount"]) for x in _electric_inputs(mv, "medium")
                 if _p_id(x) not in (tr["id"], mv["id"]))
    self_kwh = sum(float(x["amount"]) for x in _electric_inputs(mv, "medium")
                   if _p_id(x) == mv["id"])
    return {
        "processes": [{"name": p["name"], "id": p["@id"]} for p in processes],
        "mv_output_name": processes[-1]["name"],
        "transformation_hv_per_mv_kwh": float(hv_in["amount"]),
        "mv_self_input_kwh_per_kwh": self_kwh,
        "original_direct_mv_kwh_replaced": direct,
        "adapter_region": adapter["region"],
    }
