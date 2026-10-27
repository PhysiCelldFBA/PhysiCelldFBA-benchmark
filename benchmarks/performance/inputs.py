#!/usr/bin/env python3
"""Materialize one planned case into a fresh input directory; never run it."""
import argparse
import csv
import math
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from common import read_json, write_json, positive, digest

from common import SOURCE as ROOT


def set_text(root, path, value):
    node=root
    for part in path.split('/'):
        found=node.find(part)
        if found is None: found=ET.SubElement(node,part)
        node=found
    node.text=str(value)
    return node


def sbml_metadata(path):
    tree=ET.parse(path)
    reactions={n.get('id') for n in tree.iter() if n.tag.split('}')[-1]=='reaction'}
    species=sum(n.tag.split('}')[-1]=='species' for n in tree.iter())
    objectives=[]
    for node in tree.iter():
        if node.tag.split('}')[-1]=='fluxObjective':
            attrs={k.split('}')[-1]:v for k,v in node.attrib.items()}
            objectives.append((attrs['reaction'],float(attrs['coefficient'])))
    return reactions,species,objectives


def grid_shape(n, two_d):
    if two_d:
        x=max(i for i in range(1,math.isqrt(n)+1) if n%i==0)
        return x,n//x,1
    candidates=[(z//x,x,y) for y in range(1,math.isqrt(n)+1) if n%y==0
                for z in [n//y] for x in range(1,math.isqrt(z)+1) if z%x==0]
    return min(candidates,key=lambda a:max(a)/min(a))


def explicit_geometry(root, case):
    """Validate prescribed coordinates and predict occupancy on an exact cubic grid."""
    spacing=positive(case['voxel_size_um'],'voxel_size_um')
    positions=case['initial_positions']
    if case['layout']!='explicit' or len(positions)!=case['cells_requested']:
        raise ValueError('Explicit layout needs one position per cell')
    if root.findtext('domain/use_2D','false').lower()=='true':
        raise ValueError('Explicit mesh study requires a three-dimensional domain')
    bounds=[(float(root.findtext(f'domain/{a}_min')),float(root.findtext(f'domain/{a}_max'))) for a in 'xyz']
    if any(not math.isclose((hi-lo)/spacing,round((hi-lo)/spacing),abs_tol=1e-10) for lo,hi in bounds):
        raise ValueError('Mesh spacing must divide each domain extent exactly')
    occupied={}
    seen=set()
    for pos in positions:
        if len(pos)!=3 or not all(math.isfinite(float(v)) for v in pos):
            raise ValueError('Positions must contain three finite coordinates')
        if tuple(pos) in seen: raise ValueError('Cell centers must be distinct')
        seen.add(tuple(pos))
        indices=[]
        for value,(lo,hi) in zip(pos,bounds):
            q=(value-lo)/spacing
            if not lo<value<hi or math.isclose(q,round(q),abs_tol=1e-10):
                raise ValueError('Cell centers must lie inside voxels, away from boundaries')
            indices.append(math.floor(q))
        index=tuple(indices); occupied[index]=occupied.get(index,0)+1
    expected=case['expected_max_occupancy']
    if max(occupied.values())!=expected:
        raise ValueError('Predicted occupancy disagrees with the case')
    return spacing,positions,occupied


def materialize(case, study, destination, duration, output_policy=None, nutrient_multiplier=100):
    positive(duration,'duration')
    out=Path(destination)
    if out.exists(): raise ValueError('Input directory must be new')
    source=ROOT/case['template']
    root=ET.parse(source).getroot()
    profile=None
    if case.get('medium_profile'):
        from media import apply_medium
        profile=read_json(Path(__file__).with_name('growth_profiles.json'))[case['medium_profile']]
        if profile['model']!=case['model'] or profile['template']!=case['template']:
            raise ValueError('Medium profile disagrees with model/template')
        if case.get('nutrient_control'):
            raise ValueError('Do not combine a medium profile with a generic nutrient multiplier')
        apply_medium(root,profile)
    if any(c.get('parent_type') for c in root.findall('cell_definitions/cell_definition')):
        raise ValueError('Expand inherited cell definitions before materializing')
    controls=ET.SubElement(root,'benchmark',enabled='true',layout=case['layout'],cells=str(case['cells_requested']),
                           fixed_positions=str(case['fixed_positions']).lower(),fixed_population=str(case['fixed_population']).lower(),
                           fixed_volume=str(case['fixed_volume']).lower(),mixed=str(case.get('mixed',False)).lower(),
                           permute=str(case.get('order_seed') is not None).lower())
    warm_minutes=float(root.findtext('user_parameters/diffusion_steps','0'))*float(root.findtext('overall/dt_diffusion'))
    controls.set('equilibration_minutes',str(warm_minutes))
    if case['layout']=='explicit':
        spacing,positions,occupied=explicit_geometry(root,case)
        for axis in 'xyz': set_text(root,'domain/d'+axis,spacing)
        controls.set('expected_max_occupancy',str(case['expected_max_occupancy']))
        for position in positions:
            ET.SubElement(controls,'cell_position',**{a:str(float(v)) for a,v in zip('xyz',position)})
    if 'initial_position' in case:
        position=case['initial_position']
        if case['layout'] not in ('single','shared') or len(position)!=3 or not all(math.isfinite(float(v)) for v in position):
            raise ValueError('Explicit position requires three finite coordinates in a single/shared layout')
        ET.SubElement(controls,'position',**{a:str(float(v)) for a,v in zip('xyz',position)})
    elif case['model']=='mcf7_core' and case['layout']=='single':
        name=root.findtext('initial_conditions/cell_positions/filename')
        with (source.parent/name).open(newline='') as stream:
            first=next(csv.DictReader(stream))
        ET.SubElement(controls,'position',**{a:str(float(first[a])) for a in 'xyz'})
    if case.get('order_seed') is not None: controls.set('order_seed',str(case['order_seed']))
    policy=output_policy or case['output_policy']
    if policy != case['output_policy']:
        raise ValueError('Use a separate case ID and change its output_policy before generating a timing counterpart')
    controls.set('diagnostics',str(policy!='minimal').lower())
    for path,value in [('overall/max_time',duration),('overall/dt_diffusion',case['diffusion_dt_minutes']),
                       ('parallel/omp_num_threads',case['threads']),('save/folder','output'),
                       ('options/random_seed',case['simulation_seed']),('user_parameters/random_seed',case['simulation_seed']),
                       ('save/full_data/enable',str(policy!='minimal').lower()),('save/full_data/interval',duration if policy=='diagnostic_endpoints' else case['intracellular_dt_minutes']),
                       ('save/SVG/enable','false'),('save/legacy_data/enable','false')]: set_text(root,path,value)
    copied={}
    model_info={}
    for cell in root.findall('cell_definitions/cell_definition'):
        model=cell.find('phenotype/intracellular')
        if model is None: raise ValueError('Every explicit definition must supply model/density for matched controls')
        density=positive(model.findtext('growth_model/cell_density'),'cell_density')
        ET.SubElement(controls,'cell_type',name=cell.get('name'),density_g_ml=str(density))
        sbml=ROOT/(profile['sbml'] if profile else study['models'][case['model']]['path'])
        reactions,species,objectives=sbml_metadata(sbml)
        if case['model']=='iml1515':
            if len(objectives)!=1 or objectives[0][1]!=1: raise ValueError('Explicit reviewed objective mapping required')
            set_text(model,'growth_model/objective_reaction',objectives[0][0])
        used=[model.findtext('growth_model/objective_reaction')]+[n.text for n in model.findall('transport_model/exchange/fba_flux')]
        if any(r not in reactions for r in used): raise ValueError(f'Unknown reaction mapping in {cell.get("name")}: {set(used)-reactions}')
        asset='config/'+sbml.name; copied[asset]=sbml
        set_text(model,'settings/sbml_filename',asset)
        set_text(model,'settings/intracellular_dt',case['intracellular_dt_minutes'])
        old=model.find('settings/time_step')
        if old is not None: model.find('settings').remove(old)
        secondary=model.find('secondary_objective')
        if secondary is not None: model.remove(secondary)
        ET.SubElement(model,'secondary_objective',enabled=str(case['variant']=='pfba').lower(),type='parsimonious',fraction_of_optimum='1.0')
        model_info[asset]=dict(reactions=len(reactions),species=species,sha256=digest(sbml),mapped_reactions=used)
        if case['variant'] in ('dfba_disabled','upstream_physicell'): cell.find('phenotype').remove(model)
        if case['fixed_population']:
            for element in cell.findall('.//cell_interactions/*/*')+cell.findall('.//cell_transformations/*/*'):
                element.text='0'
    positions=root.find('initial_conditions/cell_positions')
    if positions is not None:
        positions.set('enabled',str(case['layout']=='application').lower())
        if case['layout']=='application':
            name=positions.findtext('filename'); asset='config/'+Path(name).name
            copied[asset]=source.parent/name
            set_text(positions,'folder','config'); set_text(positions,'filename',Path(name).name)
    for rules in root.findall('cell_rules/rulesets/ruleset'):
        if rules.get('enabled','false').lower()=='true': raise ValueError('Bundle and review active rules before using this template')
    variables=root.findall('microenvironment_setup/variable')
    for f,v in enumerate(variables): v.set('ID',str(f))
    if case['fields']<len(variables): raise ValueError('Cannot remove required coupled fields')
    for f in range(len(variables),case['fields']):
        v=ET.SubElement(root.find('microenvironment_setup'),'variable',name=f'benchmark_extra_{f}',units='dimensionless',ID=str(f))
        set_text(v,'physical_parameter_set/diffusion_coefficient',1000)
        set_text(v,'physical_parameter_set/decay_rate',0)
        set_text(v,'initial_condition',1)
        ET.SubElement(v,'Dirichlet_boundary_condition',enabled='false').text='0'
    if case.get('nutrient_control'):
        positive(nutrient_multiplier,'nutrient_multiplier')
        uptake={e.get('substrate') for e in root.findall('.//transport_model/exchange') if float(e.findtext('Vmax','0'))>0}
        for v in variables:
            if v.get('name') in uptake: v.find('initial_condition').text=str(float(v.findtext('initial_condition'))*nutrient_multiplier)
    if case['layout']=='lattice':
        shape=grid_shape(case['cells_requested'],root.findtext('domain/use_2D','false').lower()=='true')
        for axis,n in zip('xyz',shape):
            spacing=positive(root.findtext('domain/d'+axis),'voxel size')
            set_text(root,f'domain/{axis}_min',-spacing*n/2)
            set_text(root,f'domain/{axis}_max',spacing*n/2)
    for path in copied.values():
        if not path.is_file(): raise ValueError(f'Missing asset: {path}')
    out.mkdir(parents=True)
    for name,path in copied.items():
        dest=out/name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(path,dest)
    ET.ElementTree(root).write(out/'settings.xml',encoding='utf-8',xml_declaration=True)
    write_json(out/'input-record.json',dict(case=case,duration_minutes=duration,output_policy=policy,models=model_info,medium_profile=profile,nutrient_multiplier=nutrient_multiplier if case.get('nutrient_control') else None))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',required=True,type=Path)
    parser.add_argument('--study',default=Path(__file__).with_name('study.json'),type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--duration',required=True,type=float,help='Pilot-selected physical minutes')
    parser.add_argument('--output-policy',choices=('minimal','intracellular','diagnostic_endpoints'))
    parser.add_argument('--nutrient-multiplier',type=float,default=100)
    args=parser.parse_args()
    materialize(read_json(args.case),read_json(args.study),args.output,args.duration,args.output_policy,args.nutrient_multiplier)

if __name__=='__main__': main()
