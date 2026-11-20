"""One-time instructor catalog builder; run locally while openLCA 2 IPC server is on.

Requires: pip install olca-ipc olca-schema
Only copies limited process identifiers and output-reference descriptors, not LCIs.
"""
import argparse
import csv
import json
from datetime import date
from pathlib import Path


def load_mapping(path):
    with open(path,encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        if not reader.fieldnames or not {'technology','process_uuid'}.issubset(reader.fieldnames):
            raise ValueError('CSV must include technology,process_uuid')
        mapping={}
        for row in reader:
            tech=(row.get('technology') or '').strip().lower()
            uid=(row.get('process_uuid') or '').strip()
            if tech and uid:
                if tech in mapping:raise ValueError(f'Duplicate mapping: {tech}')
                mapping[tech]=uid
    if not mapping:raise ValueError('At least one mapped provider is required')
    return mapping


def make_catalog(mapping, fetch, database_label, reviewer, reviewed_date=None):
    """Injected fetch makes it testable without an openLCA server."""
    providers={}; output_refs=None
    for tech,pid in mapping.items():
        proc=fetch(pid)
        if proc is None:raise ValueError(f'{tech} provider UUID not in target database: {pid}')
        outputs=[e for e in proc.exchanges or [] if e.input is False and e.quantitative_reference is True]
        if len(outputs)!=1:raise ValueError(f'{tech}: need exactly one quantitative reference OUTPUT')
        o=outputs[0]
        if not o.flow or not o.unit or not o.flow_property:
            raise ValueError(f'{tech}: reference output missing flow/unit/flow-property')
        def r(obj):return {'id':obj.id,'name':obj.name}
        refs={'flow':r(o.flow),'unit':r(o.unit),'flow_property':r(o.flow_property)}
        if 'electricity' not in refs['flow']['name'].lower() or 'high voltage' not in refs['flow']['name'].lower():
            raise ValueError(f'{tech} reference output is not high-voltage electricity')
        if refs['unit']['name'].lower().replace(' ','') not in ('kwh','kilowatthour','kilowatt-hour'):
            raise ValueError(f'{tech} output unit is not kWh')
        if output_refs and refs!=output_refs:
            raise ValueError(f'{tech} electricity flow/property/unit differs from other providers — review mapping')
        output_refs=refs
        providers[tech]={'id':proc.id,'name':proc.name,'flow_id':o.flow.id,
                         'flow_property_id':o.flow_property.id,'unit_id':o.unit.id}
    return {'catalog_version':1,'approved':False,'approved_by':reviewer,
            'reviewed_date':reviewed_date or date.today().isoformat(),
            'database_label':database_label,'system_model':'cut-off','voltage':'high',
            'reference_output':output_refs,'providers':providers,
            'approval_note':'INSTRUCTOR MUST REVIEW PROVIDERS, GEOGRAPHIES AND SYSTEM MODEL AND SET approved=true.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mapping',required=True,help='CSV with technology,process_uuid')
    p.add_argument('--database-label',required=True,help='Exact database name, must include ecoinvent 3.12 cut-off')
    p.add_argument('--reviewer',required=True)
    p.add_argument('--port',type=int,default=8080)
    p.add_argument('--out',default='provider_catalog_REVIEW.json')
    args=p.parse_args()
    if '3.12' not in args.database_label or 'cut' not in args.database_label.lower():
        p.error('database label must identify ecoinvent 3.12 cut-off')
    import olca_ipc as ipc
    import olca_schema as o
    client=ipc.Client(port=args.port)
    catalog=make_catalog(load_mapping(args.mapping),lambda uid:client.get(o.Process,uid),
                         args.database_label,args.reviewer)
    Path(args.out).write_text(json.dumps(catalog,indent=2,ensure_ascii=False),encoding='utf-8')
    print(f'Created {args.out}. Review each provider and its database, then explicitly change approved to true.')

if __name__=='__main__':main()
