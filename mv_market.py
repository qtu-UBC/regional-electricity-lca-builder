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


def validate_mv_adapter(adapter: Any, catalog: Mapping[str, Any],
                        scenario: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Fail closed for unfamiliar market structures and mismatched flow UUIDs.

    The supported pattern is an HV market with external HV electricity sources
    (optionally a self-loop), a transformation receiving HV from that market,
    and an MV market supplied by transformation/direct MV/self-consumption.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if scenario.get("voltage") != "medium":
        errors.append("Medium-voltage export requires delivery level medium.")
    if float(scenario.get("loss_fraction", 0) or 0) != 0:
        errors.append("Set simplified loss scaling to 0 for MV: network losses come from the adapter.")
    high = dict(scenario, voltage="high", loss_fraction=0.0)
    cat_errors, cat_warnings = validate_catalog(catalog, high)
    errors += cat_errors
    warnings += cat_warnings
    if not isinstance(adapter, dict):
        return errors + ["Instructor-reviewed regional MV adapter JSON is required."], warnings
    if adapter.get("adapter_version") != 1:
        errors.append("MV adapter_version must be 1.")
    if adapter.get("approved") is not True or not str(adapter.get("approved_by", "")).strip():
        errors.append("MV adapter requires explicit instructor approval and approved_by.")
    if not str(adapter.get("reviewed_date", "")).strip():
        errors.append("MV adapter reviewed_date is required.")
    if not str(adapter.get("region", "")).strip():
        errors.append("MV adapter must identify its source geography.")
    if adapter.get("database_label") != catalog.get("database_label"):
        errors.append("MV adapter and generator catalog must name the same restored .zolca.")
    if adapter.get("system_model") != "cut-off" or adapter.get("database_label", "").find("3.12") < 0:
        errors.append("MV adapter must identify ecoinvent 3.12 cut-off.")
    if adapter.get("extraction_truncated"):
        errors.append("Truncated MV adapter discovery cannot be approved.")
    templates = adapter.get("processes", {})
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
            if float(out["amount"]) != 1.0:
                errors.append(f"{key} reference output must be 1 kWh for this adapter.")
            if str(out["unit"].get("name", "")).lower().replace(" ", "") not in ("kwh", "kilowatthour", "kilowatt-hour"):
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
            errors.append("HV market, transformation and MV market must be three distinct processes.")
        hv_ref = _output(hv)
        trans_ref = _output(trans)
        mv_ref = _output(mv)
        cat_ref = catalog["reference_output"]
        for field, key in (("flow", "flow"), ("unit", "unit"), ("flow_property", "flow_property")):
            if hv_ref[field]["id"] != cat_ref[key]["id"]:
                errors.append(f"HV market {field} does not match generator-library reference output.")
            if trans_ref[field]["id"] != mv_ref[field]["id"]:
                errors.append(f"MV transformation and MV market {field} do not match.")
        if hv_ref["amount"] != 1.0 or trans_ref["amount"] != 1.0 or mv_ref["amount"] != 1.0:
            errors.append("All three processes must use a 1 kWh reference output.")

        hvin = _electric_inputs(hv, "high")
        hv_external = [x for x in hvin if _p_id(x) != hv["id"]]
        if not hv_external or sum(float(x["amount"]) for x in hv_external) <= 0:
            errors.append("HV market must have external high-voltage supply inputs.")
        for x in hv["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("medium", "low"):
                errors.append("HV market has non-HV electricity inputs; this topology requires manual review.")
        transform_hv = _electric_inputs(trans, "high")
        if len(transform_hv) != 1 or _p_id(transform_hv[0]) != hv["id"]:
            errors.append("Transformer must have exactly one HV input from the selected HV market.")
        for x in trans["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("medium", "low"):
                errors.append("Transformer has additional electricity inputs; unsupported topology.")
        mvin = _electric_inputs(mv, "medium")
        from_transform = [x for x in mvin if _p_id(x) == trans["id"]]
        if len(from_transform) != 1:
            errors.append("MV market must have exactly one medium-voltage input from transformer.")
        if not any(_p_id(x) == mv["id"] for x in mvin):
            warnings.append("No MV self-consumption exchange; this may be correct for the source market.")
        for x in mv["exchanges"]:
            if x.get("is_input") and _electricity_voltage(x["flow"]) in ("high", "low"):
                errors.append("MV market has other-voltage electricity inputs; unsupported topology.")
        # All MV electric inputs must share the same reference flow/unit/property.
        for x in mvin:
            for field in ("flow", "unit", "flow_property"):
                if x[field]["id"] != mv_ref[field]["id"]:
                    errors.append(f"MV market electricity input has mismatched {field}.")
        for x in hvin + transform_hv:
            for field in ("flow", "unit", "flow_property"):
                if x[field]["id"] != hv_ref[field]["id"]:
                    errors.append(f"HV electricity input has mismatched {field}.")
        if sum(float(x["amount"]) for x in mvin if _p_id(x) != mv["id"]) <= 0:
            errors.append("MV market has no upstream non-self electricity supply.")
    except (KeyError, ValueError, TypeError, AttributeError, IndexError) as exc:
        errors.append(f"MV adapter structure is incomplete or invalid: {exc}")

    warnings += [
        "Region adapter is a proxy; region-specific network representativeness must be checked.",
        "Custom mode routes ALL declared generation through HV and removes direct MV generation.",
        "Process copies preserve exchange amounts/providers, not necessarily all original metadata, costs or uncertainty distributions.",
        "Import and baseline LCIA replication must be verified locally before interpreting custom MV results.",
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


def make_mv_processes(scenario: Mapping[str, Any], catalog: Mapping[str, Any],
                      adapter: Mapping[str, Any], replicate: bool = False) -> list[dict]:
    """Three market-chain clones for baseline test, four for custom HV substitution.

    All original non-electric inputs and elementary outputs are retained. In
    custom mode, HV market external generation inputs are replaced by ONE custom
    HV generation-mix link, and MV direct generation shifts to HV pathway.
    """
    errors, _ = validate_mv_adapter(adapter, catalog, scenario)
    if errors:
        raise ValueError("Cannot export MV processes:\n" + "\n".join(errors))
    src = adapter["processes"]
    hv, tr, mv = src["hv_market"], src["transformation"], src["mv_market"]
    mode = "replication" if replicate else "custom"
    identity = {
        "mode": mode,
        "scenario": scenario,
        "catalog_providers": catalog["providers"],
        "adapter": adapter,
    }
    hv_id = _new_id("mv-v09-hv-market", identity)
    tr_id = _new_id("mv-v09-transformation", identity)
    mv_id = _new_id("mv-v09-mv-market", identity)
    hv_new = {"id": hv_id, "name": f"v0.9 {mode} HV market | {adapter['region']}"}
    tr_new = {"id": tr_id, "name": f"v0.9 {mode} HV-to-MV | {adapter['region']}"}
    mv_new = {"id": mv_id, "name": f"v0.9 {mode} MV market | {scenario['region']}"}
    label = f"Regional Electricity LCA Builder v0.9 {mode}; source={adapter['database_label']}; reviewed_by={adapter['approved_by']}"
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
    processes = make_mv_processes(scenario, catalog, adapter, replicate)
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
