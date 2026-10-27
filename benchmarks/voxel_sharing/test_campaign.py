"""Preparation/analysis helper tests; no simulations, jobs or real-data analysis."""
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'performance'))
from common import read_json
from inputs import materialize

def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,HERE/filename)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module

campaign=load('voxel_prepare','prepare.py')
analysis=load('voxel_analysis','analyze.py')

class CampaignTests(unittest.TestCase):
    def test_launcher_keeps_all_cases_after_flagged_step_and_stdin_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); part=root/'voxel_sharing'; (part/'logs').mkdir(parents=True)
            fake=root/'bin'; fake.mkdir()
            for name,body in [('module','exit 0'),('srun','cat >/dev/null\nexit 1')]:
                executable=fake/name; executable.write_text('#!/bin/bash\n'+body+'\n'); executable.chmod(0o755)
            launch=part/'launch-order.txt'; launch.write_text(''.join(str(root/f'case{i}')+'\n' for i in range(3)))
            (root/'campaign.sha256').write_text(hashlib.sha256(launch.read_bytes()).hexdigest()+'  '+str(launch)+'\n')
            env={**os.environ,'PATH':str(fake)+os.pathsep+os.environ['PATH'],'SLURM_CPUS_PER_TASK':'112'}
            for start,expected in [(1,3),(2,2)]:
                env['SLURM_JOB_ID']=f'fixture-{start}'
                result=subprocess.run(['bash',str(HERE/'run_mn5.sbatch'),str(root),str(start)],env=env,capture_output=True,text=True)
                self.assertEqual(result.returncode,1,result.stderr)
                self.assertEqual(len((part/'logs'/f'collection-fixture-{start}.tsv').read_text().splitlines()),expected+1)

    def test_original_n8_matrix_and_inputs(self):
        protocol=read_json(HERE/'protocol.json'); study=read_json(HERE.parent/'performance/study.json')
        cases,duration=campaign.cases_for_protocol(protocol,study)
        self.assertEqual(len(cases),60)
        self.assertEqual(len({c['case_id'] for c in cases}),60)
        self.assertEqual({c['cells_requested'] for c in cases},{8})
        self.assertEqual({c['threads'] for c in cases},{1,2,4,8})
        original=ET.parse(campaign.ROOT/protocol['template']).getroot()
        self.assertEqual(duration,float(original.findtext('overall/max_time')))
        with tempfile.TemporaryDirectory() as directory:
            output=Path(directory)/'inputs'; materialize(cases[0],study,output,duration)
            root=ET.parse(output/'settings.xml').getroot()
            self.assertEqual(root.find('benchmark/position').attrib,dict(x='0.0',y='0.0',z='0.0'))
            for path in ('domain','microenvironment_setup'):
                self.assertEqual(ET.tostring(root.find(path)),ET.tostring(original.find(path)))
            self.assertEqual(root.findtext('overall/dt_diffusion'),original.findtext('overall/dt_diffusion'))
            self.assertEqual(root.find('benchmark').get('fixed_volume'),'false')
            self.assertEqual(root.find('benchmark').get('order_seed'),'11')

    def test_flagged_pairing_retained_but_wrong_order_rejected(self):
        serial=dict(attempt='s',case_id='s',threads=1,actual_threads=1,order_seed=11,repeat=1,
                    status='completed_flagged',flags='negative_concentration',comparison_key='same',
                    order_sha256='order',actual_updates=80,final_biomass_pg=2.7,min_concentration=-.001)
        parallel={**serial,'attempt':'p','case_id':'p','threads':4,'actual_threads':4,'actual_updates':79}
        paired=analysis.paired_comparisons([serial,parallel])[0]
        self.assertEqual(paired['actual_updates_parallel_minus_serial'],-1)
        self.assertEqual(paired['comparison'],'paired_including_diagnostic_flags')
        parallel.update(actual_updates=58,due_updates=60)
        self.assertEqual(analysis.serial_update_deficits([serial,parallel]),{'s':0,'p':22})
        # Excess updates must remain negative, not be silently clipped.
        parallel['actual_updates']=82
        self.assertEqual(analysis.serial_update_deficits([serial,parallel])['p'],-2)
        parallel['order_sha256']='different'
        self.assertEqual(analysis.paired_comparisons([serial,parallel])[0]['comparison'],'incompatible_workload_or_order')
        self.assertNotIn('p',analysis.serial_update_deficits([serial,parallel]))
        self.assertEqual(analysis.paired_comparisons([serial,copy.deepcopy(serial),parallel])[0]['comparison'],'missing_or_ambiguous_attempts')

    def test_mesh_geometry_and_pairing(self):
        study=read_json(HERE.parent/'performance/study.json')
        cases,duration=campaign.cases_for_protocol(read_json(HERE/'mesh_protocol.json'),study)
        self.assertEqual(len(cases),240)
        self.assertEqual(len({c['case_id'] for c in cases}),240)
        positions=cases[0]['initial_positions']
        self.assertEqual(len(set(map(tuple,positions))),8)
        from inputs import explicit_geometry
        with tempfile.TemporaryDirectory() as directory:
            for mesh in ('mesh16','mesh8','mesh4','mesh2'):
                c=next(c for c in cases if c['mesh_id']==mesh)
                self.assertEqual(c['initial_positions'],positions)
                out=Path(directory)/mesh; materialize(c,study,out,duration)
                root=ET.parse(out/'settings.xml').getroot()
                _,_,occupied=explicit_geometry(root,c)
                self.assertEqual(set(occupied.values()),{c['expected_max_occupancy']})
                self.assertEqual(len(root.findall('benchmark/cell_position')),8)
                invalid=copy.deepcopy(c); invalid['initial_positions'][0]=invalid['initial_positions'][1]
                with self.assertRaises(ValueError): explicit_geometry(root,invalid)
        base=dict(threads=1,actual_threads=1,order_seed=11,repeat=1,status='completed',flags='',order_sha256='order',
                  actual_updates=80,final_biomass_pg=1,min_concentration=0)
        records=[]
        for mesh in ('mesh16','mesh2'):
            records.extend([{**base,'mesh_id':mesh,'comparison_key':mesh,'attempt':mesh+'s','case_id':mesh+'s'},
                            {**base,'mesh_id':mesh,'comparison_key':mesh,'attempt':mesh+'p','case_id':mesh+'p',
                             'threads':8,'actual_threads':8,'actual_updates':60}])
        pairs=analysis.paired_comparisons(records)
        self.assertEqual([p['comparison'] for p in pairs],['paired_including_diagnostic_flags']*2)
        self.assertEqual([p['actual_updates_parallel_minus_serial'] for p in pairs],[-20,-20])

if __name__=='__main__': unittest.main()
