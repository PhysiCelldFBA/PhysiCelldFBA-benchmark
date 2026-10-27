"""Agreed experiment matrix; no simulation or submission side effects."""
import itertools
from pathlib import Path
from common import config_metadata, read_json
from common import SOURCE as ROOT
PHASES = ('pilot', 'main', 'timestep', 'refinement', 'voxel', 'voxel_mixed', 'voxel_rich', 'cancer_application', 'pfba', 'pfba_application')


def plan_cases(study, phase):
    cases = []
    def add(model, n, p, fields=None, repeat=1, variant='dfba', ratio=1, factor=1, seed=None, template=None, layout=None, dt=None):
        performance = phase in ('pilot', 'main')
        profile_id=study.get('performance_medium_profiles',{}).get(model) if performance else None
        if profile_id:
            profile=read_json(Path(__file__).with_name('growth_profiles.json'))[profile_id]
            if profile['model']!=model: raise ValueError('Performance profile/model mismatch')
            template=profile['template']
        template = template or study['models'][model]['template']
        meta = config_metadata(ROOT / template)
        fields = max(fields or meta['fields'], meta['fields'])
        diffusion_dt=study.get('performance_diffusion_dt_minutes',meta['diffusion_dt_minutes']) if performance else meta['diffusion_dt_minutes']
        layout = layout or ('lattice' if performance else 'shared' if phase.startswith('voxel') else 'single')
        case = dict(phase=phase, model=model, cells_requested=n, threads=p, fields=fields,
                    repeat=repeat, variant=variant, template=template, layout=layout,
                    simulation_seed=study['simulation_seed'], order_seed=seed,
                    diffusion_dt_minutes=diffusion_dt*factor,
                    intracellular_dt_minutes=dt if dt is not None else diffusion_dt*factor*ratio,
                    fixed_positions=layout!='application', fixed_population=performance or phase.startswith('voxel') or layout=='single',
                    fixed_volume=performance, output_policy='minimal' if performance else 'intracellular',
                    interpretation='performance_candidate' if performance else 'known_race_diagnostic' if phase.startswith('voxel') and p>1 else 'numerical_diagnostic',
                    status='planned', open_decisions=list(study['open_decisions']), validation_record=None,
                    mixed=phase=='voxel_mixed', nutrient_control=phase=='voxel_rich')
        case['case_id'] = f'{phase}-{model}-{variant}-n{n}-p{p}-f{fields}-q{ratio}-h{factor}-o{seed}-r{repeat}'.replace('.', '_')
        if profile_id:
            case['medium_profile']=profile_id
            case['case_id']+='-medium-'+profile_id
        cases.append(case)
    if phase == 'timestep':
        for model, ratio in itertools.product(study[phase]['models'], study[phase]['ratios']): add(model,1,1,ratio=ratio)
    elif phase == 'refinement':
        for factor in study[phase]['factors']: add('mcf7_core',1,1,factor=factor)
    elif phase.startswith('voxel'):
        v=study['voxel']
        for n,p,seed,r in itertools.product(v['cells'] if phase=='voxel' else [8],v['threads'],v['order_seeds'],range(1,v['repeats']+1)):
            add('ecoli_core',n,p,repeat=r,seed=seed,template=v['mixed_template'] if phase=='voxel_mixed' else v['template'])
    elif phase in ('pfba','pfba_application','cancer_application'):
        dt=study['pfba']['selected_dt_minutes']
        if dt is None: raise ValueError('Record a pilot-selected timestep in pfba.selected_dt_minutes first')
        for variant in (['dfba'] if phase=='cancer_application' else study['pfba']['variants']):
            add('mcf7_core',1,1,variant=variant,layout='application' if phase.endswith('application') else 'single',dt=dt)
        for c in cases:
            if c['layout']=='application': c['open_decisions'].append('Set cells_requested from application CSV')
    else:
        s=study[phase]
        common_fields=max(config_metadata(ROOT/m['template'])['fields'] for m in study['models'].values())
        if phase=='pilot': points=set(itertools.product(s['cells'],s['threads'],[max(common_fields,s['fields'])]))
        else:
            f=max(common_fields,s['reference_fields'])
            points={(n,p,f) for n in s['cells'] for p in (1,s['reference_threads'])}
            points.update((s['reference_cells'],p,f) for p in s['threads'])
            points.update((s['reference_cells'],s['reference_threads'],f) for f in s['fields'])
        for model,(n,p,f),variant,r in itertools.product(study['models'],sorted(points),['dfba',*study['baseline_variants']],range(1,s['repeats']+1)):
            add(model,n,p,f,r,variant)
    return list({c['case_id']:c for c in cases}.values())
