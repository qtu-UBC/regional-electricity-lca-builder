"""Safeguarded local openLCA bridge for vetted supply mixes.

Uses olca-ipc + olca-schema v2 and a running IPC server in openLCA 2.x.
Writes a new *foreground* process only when --write is explicitly specified.
No ecoinvent data is redistributed. NOT tested against a live openLCA database.
"""
import argparse
import csv
import json
import math
import uuid
from pathlib import Path
from grid_core import validate_scenario


def provider_rows(filename):
    with open(filename, encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        if not r.fieldnames or not {"technology", "process_uuid"}.issubset(r.fieldnames):
            raise ValueError("Provider mapping CSV requires technology,process_uuid")
        d = {}
        for line in r:
            tech = (line.get("technology") or "").strip().lower()
            pid = (line.get("process_uuid") or "").strip()
            if pid:
                if tech in d:
                    raise ValueError(f"Duplicate provider mapping for {tech}")
                d[tech] = pid
        return d


def plan(scenario, mappings):
    errors, warnings = validate_scenario(scenario)
    if errors:
        raise ValueError("Invalid scenario:\n" + "\n".join(errors))
    if scenario["boundary"] != "consumption":
        warnings.append("Only illustrative/generation boundary provided: output MUST be labeled hypothetical, not actual regional consumption.")
    active = [r for r in scenario["mix"] if float(r["share"])>0]
    missing = [r['technology'] for r in active if r['technology'] not in mappings]
    if missing:
        raise ValueError("Missing process_uuid for: " + ", ".join(missing))
    loss = float(scenario.get("loss_fraction", 0))
    return [(r["technology"], mappings[r["technology"]], float(r["share"])/(1-loss)) for r in active], warnings


def connection(port):
    try:
        import olca_ipc as ipc
        import olca_schema as o
    except ImportError as e:
        raise RuntimeError("Install: pip install olca-ipc olca-schema") from e
    return ipc.Client(port=port), o


def discover(client, o, query, limit):
    refs = client.get_descriptors(o.Process)
    matches = [r for r in refs if query.lower() in (r.name or '').lower()]
    for r in matches[:limit]:
        print(f"{r.id}\t{r.name}")
    print(f"Found {len(matches)} matching process descriptors. Check each reference output before use.")


def output_exchange(process):
    outs = [x for x in (process.exchanges or []) if x.input is False and x.quantitative_reference is True]
    if len(outs) != 1:
        raise ValueError(f"Provider '{process.name}' needs exactly one quantitative-reference OUTPUT; found {len(outs)}")
    return outs[0]


def create(client, o, scenario, entries, warnings, write, create_system):
    if scenario['voltage'] != 'high':
        raise ValueError("Bridge v0.1 supports HIGH-voltage generation mix only. Do not present an HV market as MV/LV delivered electricity.")
    providers = []
    canonical_flow, canonical_unit, canonical_fp = None, None, None
    for tech, pid, amount in entries:
        proc = client.get(o.Process, pid)
        if proc is None:
            raise ValueError(f"Provider {tech} UUID {pid} not found in openLCA")
        out = output_exchange(proc)
        if not out.flow or not out.unit or not out.flow_property:
            raise ValueError(f"Provider {tech} has an incomplete quantitative reference exchange")
        if not (out.unit.name or '').lower() in ('kwh', 'kilowatt hour', 'kilowatt-hour'):
            raise ValueError(f"Provider {tech} has reference unit '{out.unit.name}', not kWh. Convert or select another process explicitly.")
        if "electricity" not in (out.flow.name or '').lower() or "high voltage" not in (out.flow.name or '').lower():
            raise ValueError(f"Provider {tech} does not have an electricity, HIGH VOLTAGE reference output.")
        if canonical_flow is None:
            canonical_flow, canonical_unit, canonical_fp = out.flow, out.unit, out.flow_property
        if out.flow.id != canonical_flow.id or out.unit.id != canonical_unit.id or out.flow_property.id != canonical_fp.id:
            raise ValueError(f"Provider {tech} output flow, unit or flow property differs from first supplier. Reconcile explicitly; not auto-converted.")
        providers.append((tech, proc, amount))
    desc = f"LCA Clinic regional electricity mix; reference year {scenario['year']}; boundary={scenario['boundary']}; evidence={scenario['evidence_status']}; source={scenario.get('source_url','')}; background={scenario.get('ecoinvent_version','')}; loss scaling={scenario['loss_fraction']}; no added grid infrastructure."
    print("=== PROCESS PREVIEW (not a calculated LCIA result) ===")
    print(desc)
    print(f"Output: 1 kWh {canonical_flow.name}; flow ID={canonical_flow.id}")
    for tech, proc, amt in providers:
        print(f"  {tech:15s} {amt:.6f} kWh <-- {proc.name} [{proc.id}]")
    for item in warnings:
        print("WARNING:", item)
    if not write:
        print("DRY RUN ONLY: no database changes. To create, add --write")
        return None
    # Deliberate opt-in: each run creates a NEW process; it never updates the licensed providers.
    process = o.Process()
    process.id = str(uuid.uuid4())
    process.name = f"STUDENT CUSTOM electricity market | {scenario['region']} | {scenario['year']} | {str(process.id)[:8]}"
    process.description = desc
    process.process_type = o.ProcessType.UNIT_PROCESS
    process.exchanges = []
    out = o.Exchange()
    out.internal_id = 1
    out.input = False
    out.quantitative_reference = True
    out.amount = 1.0
    out.flow, out.unit, out.flow_property = canonical_flow, canonical_unit, canonical_fp
    process.exchanges.append(out)
    for i, (tech, provider, amount) in enumerate(providers, start=2):
        e = o.Exchange()
        e.internal_id = i
        e.input = True
        e.quantitative_reference = False
        e.amount = amount
        e.flow, e.unit, e.flow_property = canonical_flow, canonical_unit, canonical_fp
        e.default_provider = o.Ref(id=provider.id, name=provider.name, olca_type='Process')
        e.description = f"Electricity share: {tech}. Source: {scenario.get('source_url', '')}"
        process.exchanges.append(e)
    process.last_internal_id = len(process.exchanges)
    new_ref = client.put(process)
    if not new_ref:
        raise RuntimeError("openLCA did not confirm process creation")
    print(f"CREATED foreground process: {new_ref.name}, UUID: {new_ref.id}")
    if create_system:
        config = o.LinkingConfig(prefer_unit_processes=True, provider_linking=o.ProviderLinking.PREFER_DEFAULTS)
        product_system = client.create_product_system(new_ref, config)
        if not product_system:
            print("WARNING: process saved but automatic product-system creation was unsuccessful")
        else:
            print(f"CREATED product system: {product_system.name}, UUID: {product_system.id}")
    print("CHECK openLCA process links and calculate LCIA manually; the tool does not assert full regional representativeness.")
    return new_ref


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sp = parser.add_subparsers(dest='action', required=True)
    d = sp.add_parser('discover', help='Find candidate provider process UUIDs in YOUR running local openLCA DB')
    d.add_argument('--query', default='electricity production')
    d.add_argument('--limit', type=int, default=30)
    d.add_argument('--port', type=int, default=8080)
    c = sp.add_parser('create', help='Validate and optionally create a NEW custom foreground high-voltage market')
    c.add_argument('--scenario', required=True)
    c.add_argument('--mapping', required=True)
    c.add_argument('--port', type=int, default=8080)
    c.add_argument('--write', action='store_true', help='Actually WRITE to local openLCA DB (default: dry run)')
    c.add_argument('--create-system', action='store_true', help='Create linked product system after writing new process')
    args = parser.parse_args(argv)
    if args.action == 'discover':
        client, o = connection(args.port)
        discover(client, o, args.query, args.limit)
    else:
        scenario = json.loads(Path(args.scenario).read_text(encoding='utf-8'))
        entries, warnings = plan(scenario, provider_rows(args.mapping))
        client, o = connection(args.port)
        create(client, o, scenario, entries, warnings, args.write, args.create_system)


if __name__ == '__main__':
    main()
