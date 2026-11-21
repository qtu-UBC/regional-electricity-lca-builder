"""Create openLCA 2 JSON-LD *foreground only* process packages.

An instructor-prepared provider catalog ties names to UUIDs in a specific
locally licensed openLCA database. Nothing from the ecoinvent inventory is
redistributed. Without a verified matching catalog, export is prohibited.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import uuid
import zipfile
from typing import Any, Mapping

from grid_core import validate_scenario

NAMESPACE = uuid.UUID('53a57371-3288-498f-bb0d-8dba94331ccc')


def _uuid(value: Any, label: str) -> str:
    try:
        result = str(uuid.UUID(str(value)))
        return result
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError(f'{label} must contain a valid UUID') from exc


def _ref(kind: str, data: Mapping[str, Any]) -> dict:
    return {'@type': kind, '@id': _uuid(data['id'], kind), 'name': str(data['name'])}


def validate_catalog(catalog: Any, scenario: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    """Apply hard guards before generating links to an external database."""
    errors, warnings = validate_scenario(scenario)
    if not isinstance(catalog, dict):
        return errors + ['An instructor provider catalog is required.'], warnings
    if catalog.get('catalog_version') != 1:
        errors.append('Catalog format must be catalog_version 1.')
    if catalog.get('approved') is not True or not str(catalog.get('approved_by', '')).strip():
        errors.append('Catalog must be reviewed and approved by an instructor.')
    if not str(catalog.get('database_label', '')).strip():
        errors.append('Catalog must name its exact target openLCA database.')
    if catalog.get('system_model') != 'cut-off':
        errors.append('This starter export requires an instructor catalog for the cut-off system model.')
    if catalog.get('voltage') != 'high' or scenario.get('voltage') != 'high':
        errors.append('v0.2 openLCA export supports HIGH voltage only (MV/LV require transformation datasets).')
    label = (catalog.get('database_label') or '').lower()
    requested = (scenario.get('ecoinvent_version') or '').lower()
    if '3.12' not in label or '3.12' not in requested or 'cut' not in requested:
        errors.append('Catalog and scenario must explicitly identify ecoinvent 3.12 cut-off.')
    if str(catalog.get('reviewed_date','')).strip() == '':
        errors.append('Catalog must include reviewed_date.')
    flow = catalog.get('reference_output', {})
    try:
        for key, typ in (('flow','Flow'), ('flow_property','FlowProperty'), ('unit','Unit')):
            if not flow.get(key,{}).get('name'):
                raise ValueError(f'Reference output {key} has no name')
            _uuid(flow[key].get('id'), f'Reference output {key}')
        if 'electricity' not in flow['flow']['name'].lower() or 'high voltage' not in flow['flow']['name'].lower():
            errors.append('Reference output must be electricity, high voltage.')
        if flow['unit']['name'].lower().replace(' ','') not in ('kwh', 'kilowatthour','kilowatt-hour'):
            errors.append('Reference output unit must be kWh.')
    except (KeyError, AttributeError, TypeError, ValueError) as exc:
        errors.append('Incomplete/invalid reference output: '+str(exc))
    providers = catalog.get('providers', {})
    if not isinstance(providers, dict):
        providers = {}
        errors.append('Catalog providers must be a dictionary by technology.')
    seen = set()
    for row in scenario.get('mix',[]) or []:
        try:
            active = float(row.get('share', 0)) > 0
        except (ValueError, TypeError):
            continue
        if not active:
            continue
        tech = row.get('technology')
        entry = providers.get(tech)
        if not isinstance(entry, dict):
            errors.append(f'Missing approved provider for active technology: {tech}')
            continue
        try:
            uid = _uuid(entry.get('id'), f'Provider {tech}')
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if uid in seen:
            errors.append('Different technologies cannot use the same provider UUID; review mapping.')
        seen.add(uid)
        if not entry.get('name'):
            errors.append(f'Provider name missing for {tech}.')
        if entry.get('flow_id') != flow.get('flow',{}).get('id'):
            errors.append(f'Provider {tech} reference output flow UUID does not match catalog flow.')
        if entry.get('unit_id') != flow.get('unit',{}).get('id'):
            errors.append(f'Provider {tech} output unit UUID does not match catalog unit.')
        if entry.get('flow_property_id') != flow.get('flow_property',{}).get('id'):
            errors.append(f'Provider {tech} output flow-property UUID does not match catalog.')
    if scenario.get('boundary') == 'generation':
        warnings.append('Only local generation modeled; not necessarily representative of electricity consumed at site.')
    if scenario.get('evidence_status') != 'verified':
        warnings.append('An approved provider catalog does NOT verify regional generation shares. Scenario is illustrative/unverified.')
    if float(scenario.get('loss_fraction',0) or 0) > 0:
        warnings.append('Loss correction is simple kWh scaling; it does NOT model voltage conversion, networks or grid infrastructure.')
    return errors, list(dict.fromkeys(warnings))


def make_process(scenario: Mapping[str, Any], catalog: Mapping[str, Any]) -> dict:
    errors, _ = validate_catalog(catalog, scenario)
    if errors:
        raise ValueError('Cannot export openLCA process:\n'+'\n'.join(errors))
    relevant = {
        'scenario': {k:scenario.get(k) for k in ('region','year','boundary','evidence_status','voltage','loss_fraction','source_url','ecoinvent_version')},
        'mix': [{'technology':r['technology'],'share':round(float(r['share']),12)} for r in scenario['mix'] if float(r['share'])>0],
        'database': catalog['database_label'],
        'catalog_date': catalog['reviewed_date'],
        'providers': {
            r['technology']: {
                'id': catalog['providers'][r['technology']]['id'],
                'reason': catalog['providers'][r['technology']].get('selection_reason', ''),
            }
            for r in scenario['mix'] if float(r['share'])>0
        },
    }
    digest = hashlib.sha256(json.dumps(relevant, sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()
    uid = str(uuid.uuid5(NAMESPACE, digest))
    ref = catalog['reference_output']
    amount_output = {
        '@type':'Exchange', 'internalId':1, 'isInput':False, 'isQuantitativeReference':True,
        'isAvoidedProduct':False, 'amount':1.0,
        'flow':_ref('Flow',ref['flow']), 'flowProperty':_ref('FlowProperty',ref['flow_property']),
        'unit':_ref('Unit',ref['unit']),
    }
    exchanges = [amount_output]
    loss = float(scenario.get('loss_fraction',0))
    for i,row in enumerate((r for r in scenario['mix'] if float(r['share'])>0), start=2):
        supplier = catalog['providers'][row['technology']]
        amount = float(row['share'])/(1-loss)
        assert math.isfinite(amount) and amount>0
        exchanges.append({
            '@type':'Exchange', 'internalId':i, 'isInput':True, 'isQuantitativeReference':False,
            'isAvoidedProduct':False, 'amount':amount, 'flow':_ref('Flow',ref['flow']),
            'flowProperty':_ref('FlowProperty',ref['flow_property']), 'unit':_ref('Unit',ref['unit']),
            'defaultProvider':_ref('Process', supplier),
            'description':(
                f"{row['technology']} share={float(row['share']):.8f}; "
                f"source={row.get('source_url') or scenario.get('source_url') or 'UNSPECIFIED'}; "
                f"provider_class={supplier.get('provider_class', 'not classified')}; "
                f"provider_location={supplier.get('location', 'not specified')}; "
                f"selection_reason={supplier.get('selection_reason') or 'NOT DOCUMENTED'}"
            )
        })
    desc = (f"LCA Clinic student foreground electricity scenario. Region={scenario['region']}; year={scenario['year']}; "
            f"data boundary={scenario['boundary']}; evidence={scenario['evidence_status']}; "
            f"source={scenario.get('source_url','')}; catalog={catalog['database_label']}; "
            f"approved catalog reviewer={catalog['approved_by']}; simple loss fraction={loss}. "
            "Not an official or certified regional electricity inventory. No T&D infrastructure, "
            "voltage transformation, or imported ecoinvent inventories included in this foreground package.")
    name = (f"LCA Clinic CUSTOM HV electricity | {scenario['region']} | {scenario['year']} | {uid[:8]}")[:240]
    return {'@type':'Process','@id':uid,'name':name,'description':desc,
            'processType':'UNIT_PROCESS','version':'01.00.000',
            'lastInternalId':len(exchanges), 'exchanges':exchanges}


def package(scenario: Mapping[str, Any], catalog: Mapping[str, Any]) -> bytes:
    process = make_process(scenario,catalog)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('olca-schema.json',json.dumps({'version':2}))
        z.writestr(f"processes/{process['@id']}.json",json.dumps(process,indent=2,ensure_ascii=False))
    return buf.getvalue()


def package_preview(scenario: Mapping[str, Any], catalog: Mapping[str, Any]) -> dict:
    p = make_process(scenario,catalog)
    return {'process_id':p['@id'],'name':p['name'], 'database':catalog['database_label'],
            'inputs':[{'technology':r['technology'], 'kwh':r['amount'], 'provider':r['defaultProvider']['name']}
                      for r in p['exchanges'][1:]]}
