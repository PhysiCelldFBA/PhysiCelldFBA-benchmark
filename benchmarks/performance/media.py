"""Explicit benchmark medium profiles; no simulation or submission side effects."""
import math
import xml.etree.ElementTree as ET


def apply_medium(root, profile):
    fields = {v.get('name'): v for v in root.findall('microenvironment_setup/variable')}
    concentrations = profile['concentrations_mM']
    if set(concentrations) - set(fields):
        raise ValueError('Medium override names an absent field')
    if any(not math.isfinite(v) or v < 0 for v in concentrations.values()):
        raise ValueError('Medium concentrations must be finite and nonnegative')
    mode = profile['supply']
    if mode not in ('template', 'boundary', 'positive_boundary_override', 'uniform_initial_and_boundary'):
        raise ValueError('Unknown nutrient supply mode')
    if mode == 'template' and concentrations:
        raise ValueError('Template medium cannot contain ignored overrides')
    for name, variable in fields.items():
        initial = variable.find('initial_condition')
        boundary = variable.find('Dirichlet_boundary_condition')
        faces = variable.findall('Dirichlet_options/boundary_value')
        if mode == 'template':
            continue
        if mode == 'positive_boundary_override':
            if name not in concentrations:
                continue
            changed = False
            for node in [boundary, *faces]:
                if node is not None and node.get('enabled', 'false').lower() == 'true' and float(node.text) > 0:
                    node.text = str(concentrations[name]); changed = True
            if not changed:
                raise ValueError('Positive-boundary override found no active positive supply')
            continue
        if mode == 'boundary' and name not in concentrations:
            continue
        supplied = [float(initial.text)]
        supplied += [float(n.text) for n in [boundary, *faces]
                     if n is not None and n.get('enabled', 'false').lower() == 'true']
        value = concentrations.get(name, max(supplied))
        if mode == 'uniform_initial_and_boundary':
            initial.text = str(value)
        if boundary is None:
            boundary = ET.SubElement(variable, 'Dirichlet_boundary_condition')
        boundary.set('enabled', 'true'); boundary.text = str(value)
        options = variable.find('Dirichlet_options')
        if options is None:
            options = ET.SubElement(variable, 'Dirichlet_options')
        for node in list(options):
            options.remove(node)
        for face in ('xmin', 'xmax', 'ymin', 'ymax', 'zmin', 'zmax'):
            ET.SubElement(options, 'boundary_value', ID=face, enabled='true').text = str(value)
    # These profiles use the dFBA concentration convention, without numerical
    # conversion. Correct inconsistent metadata only in generated inputs.
    if mode != 'template':
        for variable in fields.values():
            variable.set('units', 'mM')
            for path in ('initial_condition', 'Dirichlet_boundary_condition'):
                node = variable.find(path)
                if node is not None:
                    node.set('units', 'mM')
