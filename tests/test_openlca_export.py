import io
import json
import sys
import unittest
import uuid
import zipfile
from pathlib import Path
from types import SimpleNamespace as Obj
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from openlca_jsonld import validate_catalog, make_process, package
from instructor_catalog import make_catalog


def uid(n): return str(uuid.UUID(int=n))


def sample():
    f=uid(11); u=uid(12); p=uid(13)
    catalog={
        'catalog_version':1,'approved':True,'approved_by':'Instructor Review (TEST ONLY)',
        'reviewed_date':'2026-11-16','database_label':'ecoinvent 3.12 cut-off UPR (FAKE TEST DB)',
        'system_model':'cut-off','voltage':'high',
        'reference_output':{
            'flow':{'id':f,'name':'electricity, high voltage'},
            'unit':{'id':u,'name':'kWh'},
            'flow_property':{'id':p,'name':'Energy'}
        },
        'providers':{
            'hydro':{'id':uid(21),'name':'TEST hydro - not real','flow_id':f,'unit_id':u,'flow_property_id':p},
            'natural_gas':{'id':uid(22),'name':'TEST gas - not real','flow_id':f,'unit_id':u,'flow_property_id':p},
        }
    }
    scenario={
        'region':'TEST fictional system','year':2025,'boundary':'hypothetical','evidence_status':'illustrative',
        'voltage':'high','loss_fraction':0.05,'source_url':'https://example.org/fiction',
        'ecoinvent_version':'ecoinvent 3.12, allocation cut-off',
        'mix':[{'technology':'hydro','share':.8,'source_url':'https://example.org/fiction'},
               {'technology':'natural_gas','share':.2,'source_url':'https://example.org/fiction'}],
    }
    return scenario,catalog


class CatalogChecks(unittest.TestCase):
    def test_two_providers_and_loss(self):
        sc,cat=sample(); e,w=validate_catalog(cat,sc); self.assertFalse(e,e)
        p=make_process(sc,cat)
        self.assertEqual(p['processType'],'UNIT_PROCESS')
        self.assertEqual(p['lastInternalId'],3)
        self.assertAlmostEqual(p['exchanges'][1]['amount'],.8/.95)
        self.assertAlmostEqual(p['exchanges'][2]['amount'],.2/.95)
        self.assertEqual(p['exchanges'][1]['defaultProvider']['@id'],uid(21))
        self.assertFalse(p['exchanges'][0]['isInput'])
        self.assertTrue(p['exchanges'][0]['isQuantitativeReference'])
        self.assertEqual(p['exchanges'][0]['flow']['@id'],p['exchanges'][2]['flow']['@id'])

    def test_zip_native_schema_layout(self):
        sc,cat=sample(); b=package(sc,cat)
        with zipfile.ZipFile(io.BytesIO(b)) as z:
            names=z.namelist();self.assertEqual(len(names),2)
            self.assertEqual(json.loads(z.read('olca-schema.json')),{'version':2})
            proc_name=next(n for n in names if n.startswith('processes/'))
            self.assertEqual(json.loads(z.read(proc_name))['@type'],'Process')
            self.assertTrue(z.testzip() is None)

    def test_deterministic_ids(self):
        sc,cat=sample()
        self.assertEqual(make_process(sc,cat)['@id'],make_process(sc,cat)['@id'])
        sc['mix'][0]['share']=.7;sc['mix'][1]['share']=.3
        self.assertNotEqual(make_process(sc,cat)['@id'],make_process(sample()[0],cat)['@id'])

    def test_no_catalog(self):
        sc,cat=sample(); e,_=validate_catalog(None,sc);self.assertTrue(e)

    def test_unapproved_catalog(self):
        sc,cat=sample();cat['approved']=False;e,_=validate_catalog(cat,sc)
        self.assertTrue(any('approved' in x for x in e))
        with self.assertRaises(ValueError):package(sc,cat)

    def test_missing_provider(self):
        sc,cat=sample();del cat['providers']['hydro']
        e,_=validate_catalog(cat,sc);self.assertTrue(any('hydro' in x for x in e))

    def test_mismatched_flow(self):
        sc,cat=sample();cat['providers']['hydro']['flow_id']=uid(998)
        e,_=validate_catalog(cat,sc);self.assertTrue(any('flow UUID' in x for x in e))

    def test_medium_voltage_block(self):
        sc,cat=sample();sc['voltage']='medium'
        e,_=validate_catalog(cat,sc);self.assertTrue(any('HIGH voltage' in x for x in e))

    def test_technology_zero_share_not_required(self):
        sc,cat=sample();sc['mix'].append({'technology':'wind','share':0})
        e,_=validate_catalog(cat,sc);self.assertFalse(e,e)

    def test_make_catalog_instructor(self):
        f=Obj(id=uid(11),name='electricity, high voltage')
        unit=Obj(id=uid(12),name='kWh')
        fp=Obj(id=uid(13),name='Energy')
        def fetch(pid):
            exchange=Obj(is_input=False,is_quantitative_reference=True,flow=f,unit=unit,flow_property=fp)
            return Obj(id=pid,name='TEST provider',exchanges=[exchange])
        cat=make_catalog({'hydro':uid(21)},fetch,'ecoinvent 3.12 cut-off UPR','Test reviewer')
        self.assertFalse(cat['approved'])
        self.assertEqual(cat['providers']['hydro']['flow_id'],uid(11))

    def test_make_catalog_mismatched_provider_outputs(self):
        def fetch(pid):
            f=Obj(id=uid(11 if pid==uid(21) else 99),name='electricity, high voltage')
            unit=Obj(id=uid(12),name='kWh');fp=Obj(id=uid(13),name='Energy')
            return Obj(id=pid,name='TEST provider',exchanges=[Obj(is_input=False,is_quantitative_reference=True,flow=f,unit=unit,flow_property=fp)])
        with self.assertRaises(ValueError):make_catalog({'hydro':uid(21),'natural_gas':uid(22)},fetch,'ecoinvent 3.12 cut-off UPR','Reviewer')

if __name__=='__main__':unittest.main()
