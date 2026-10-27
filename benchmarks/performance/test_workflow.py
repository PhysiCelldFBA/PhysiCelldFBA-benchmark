"""Manual standard-library workflow tests; no simulations or submissions.

Run in the documented Python environment:
python -m unittest discover -s benchmarks/performance -p test_workflow.py
"""
import argparse
import copy
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
from common import read_json, write_json, digest, config_metadata
from design import plan_cases
from inputs import materialize
from prepare import stage
from summarize import summarize

HERE=Path(__file__).resolve().parent

class WorkflowTests(unittest.TestCase):
    def setUp(self): self.study=read_json(HERE/'study.json')

    def test_agreed_matrices(self):
        voxel=plan_cases(self.study,'voxel')
        self.assertEqual(len(voxel),60)
        self.assertEqual(len({c['case_id'] for c in voxel}),60)
        self.assertEqual({c['variant'] for c in voxel},{'dfba'})
        sweep=plan_cases(self.study,'timestep')
        self.assertEqual(len(sweep),8)
        self.assertEqual({round(c['intracellular_dt_minutes']/c['diffusion_dt_minutes']) for c in sweep},{1,2,10,100})
        self.assertEqual({c['model'] for c in sweep},{'ecoli_core','mcf7_core'})
        with self.assertRaises(ValueError): plan_cases(self.study,'pfba')

    def test_serial_pilot_inputs(self):
        from prepare_pilots import pilot_cases
        cases=pilot_cases(self.study)
        self.assertEqual(len(cases),11)
        self.assertEqual(len({c['case_id'] for c in cases}),11)
        self.assertEqual({c['threads'] for c in cases},{1})
        with tempfile.TemporaryDirectory() as directory:
            for case in cases:
                out=Path(directory)/case['case_id']; materialize(case,self.study,out,10)
                meta=config_metadata(out/'settings.xml')
                self.assertEqual(meta['max_time_minutes'],10)
                self.assertEqual(meta['diffusion_dt_minutes'],case['diffusion_dt_minutes'])
                self.assertTrue(all(m['effective_minutes']==case['intracellular_dt_minutes'] for m in meta['intracellular'].values()))

    def test_materialize_all_models_and_disabled_mode(self):
        cases=plan_cases(self.study,'pilot')
        with tempfile.TemporaryDirectory() as directory:
            for model in self.study['models']:
                for variant in ('dfba','dfba_disabled'):
                    c=next(c for c in cases if c['model']==model and c['variant']==variant)
                    out=Path(directory)/(model+'-'+variant)
                    materialize(c,self.study,out,0.04)
                    meta=config_metadata(out/'settings.xml')
                    self.assertEqual(meta['fields'],c['fields'])
                    self.assertEqual(bool(meta['intracellular']),variant=='dfba')
                    self.assertEqual(meta['benchmark']['fixed_volume'],'true')
                    with self.assertRaises(ValueError): materialize(c,self.study,out,0.04)

    def test_staging_identity_ignores_repeat_and_thread_labels(self):
        c=plan_cases(self.study,'timestep')[0]
        c.update(status='ready',open_decisions=[],validation_record='synthetic fixture')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); binary=root/'binary'; binary.write_bytes(b'fixture only; never executed')
            build={k:'fixture' for k in ('source_commit','upstream_commit','compiler','compiler_flags','build_command','libraries','solver_settings','benchmark_harness')}
            build['binary_sha256']=digest(binary); write_json(root/'build.json',build)
            keys=[]
            for p in (1,2):
                case=copy.deepcopy(c); case.update(threads=p,repeat=p,case_id=f'fixture-{p}')
                source=root/f'inputs-{p}'; materialize(case,self.study,source,0.04)
                path=root/f'case-{p}.json'; write_json(path,case)
                args=argparse.Namespace(case=path,inputs=source,binary=binary,build=root/'build.json',output=root/f'bundle-{p}')
                stage(args)
                keys.append(read_json(args.output/'manifest.json')['comparison_key'])
            self.assertEqual(keys[0],keys[1])
            case['status']='planned'; write_json(path,case)
            with self.assertRaises(ValueError): stage(args)

    def test_flagged_runs_excluded_from_successful_summaries(self):
        row=dict(status='completed_flagged',phase='voxel')
        self.assertEqual(summarize([row]),[])

    def test_growth_media_preserve_controls_and_feed_zero_initial_cancer(self):
        from prepare_growth import growth_cases
        from inputs import ROOT
        cases=growth_cases(self.study)
        self.assertEqual(len(cases),23)
        with tempfile.TemporaryDirectory() as directory:
            for name in ('ecoli_colony_fed','iml_fed','mcf7_native','mcf7_oxygen2_gradient','mcf7_uniform_fed'):
                c=next(c for c in cases if c['medium_profile']==name)
                out=Path(directory)/name; materialize(c,self.study,out,10)
                root=ET.parse(out/'settings.xml').getroot()
                record=read_json(out/'input-record.json')
                self.assertEqual(root.findtext('save/full_data/interval'),'10')
                self.assertEqual(root.find('benchmark').get('diagnostics'),'true')
                for asset,meta in record['models'].items():
                    self.assertEqual(meta['sha256'],digest(ROOT/record['medium_profile']['sbml']))
                fields={v.get('name'):v for v in root.findall('microenvironment_setup/variable')}
                if name=='mcf7_uniform_fed':
                    self.assertEqual(len(fields),23)
                    self.assertEqual(float(fields['O2'].findtext('initial_condition')),2)
                    self.assertEqual(float(fields['L-Glutamine'].findtext('initial_condition')),1)
                    self.assertTrue(all(f.get('enabled')=='true' and float(f.text)==2 for f in fields['O2'].findall('Dirichlet_options/boundary_value')))
                if name=='mcf7_oxygen2_gradient':
                    self.assertEqual(float(fields['O2'].findtext('initial_condition')),0)
                    faces={f.get('ID'):float(f.text) for f in fields['O2'].findall('Dirichlet_options/boundary_value')}
                    self.assertEqual((faces['xmin'],faces['xmax']),(2,0))
                if name=='mcf7_native':
                    original=ET.parse(ROOT/c['template']).getroot()
                    for i,v in enumerate(original.findall('microenvironment_setup/variable')):
                        v.set('ID',str(i))
                    self.assertEqual(ET.tostring(root.find('microenvironment_setup')),ET.tostring(original.find('microenvironment_setup')))
                if name=='iml_fed':
                    self.assertTrue(all(f.get('enabled')=='true' for f in fields['oxygen'].findall('Dirichlet_options/boundary_value')))
            c=copy.deepcopy(cases[0]); c['nutrient_control']=True
            with self.assertRaises(ValueError): materialize(c,self.study,Path(directory)/'invalid',10)

    def test_conservation_and_competition_media_remain_unchanged(self):
        from inputs import ROOT
        with tempfile.TemporaryDirectory() as directory:
            for phase in ('timestep','voxel'):
                c=next(c for c in plan_cases(self.study,phase) if c['model']=='ecoli_core')
                out=Path(directory)/phase; materialize(c,self.study,out,10)
                root=ET.parse(out/'settings.xml').getroot()
                original=ET.parse(ROOT/c['template']).getroot()
                for i,v in enumerate(original.findall('microenvironment_setup/variable')): v.set('ID',str(i))
                self.assertEqual(ET.tostring(root.find('microenvironment_setup')),ET.tostring(original.find('microenvironment_setup')))
                self.assertEqual(digest(out/'config/Ecoli_core.xml'),digest(ROOT/self.study['models']['ecoli_core']['path']))

    def test_performance_profiles_match_disabled_baseline(self):
        cases=plan_cases(self.study,'pilot')
        with tempfile.TemporaryDirectory() as directory:
            for model,name in self.study['performance_medium_profiles'].items():
                environments=[]
                for variant in ('dfba','dfba_disabled'):
                    c=next(c for c in cases if c['model']==model and c['variant']==variant)
                    self.assertEqual(c['medium_profile'],name)
                    self.assertIn('-medium-'+name,c['case_id'])
                    out=Path(directory)/(model+'-'+variant); materialize(c,self.study,out,10)
                    root=ET.parse(out/'settings.xml').getroot()
                    environments.append(ET.tostring(root.find('microenvironment_setup')))
                self.assertEqual(*environments)
        self.assertTrue(all('medium_profile' not in c for c in plan_cases(self.study,'timestep')))

    def test_exchange_check_rejects_excess_removal_without_negative_concentration(self):
        from analyze_growth import exchange_ledger_pass
        correct=dict(net_export_only='1',before_amount='100',after_amount='99',
                     observed_delta='-1',expected_net_export_delta='-1',residual='1e-12')
        self.assertTrue(exchange_ledger_pass([correct]))
        overdraw=dict(correct,after_amount='90',observed_delta='-10',residual='-9')
        self.assertFalse(exchange_ledger_pass([overdraw]))
        self.assertFalse(exchange_ledger_pass([]))
        self.assertFalse(exchange_ledger_pass([dict(correct,net_export_only='0')]))

if __name__=='__main__': unittest.main()
