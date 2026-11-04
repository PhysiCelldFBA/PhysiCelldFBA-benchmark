#!/usr/bin/env python3
"""Write build.json for a directory made by build.sh; runs no simulation and submits nothing.

Library versions, upstream commit and solver settings come from --template: an earlier
build.json, or a run manifest that embeds one. The linked static archives must still
match the template's digests. Extra source patches (EXTRA_PATCHES) are recorded and
added to benchmark_harness, so prepare scripts verify them like the other harness files.
"""
import argparse
from pathlib import Path
import subprocess
from common import REPO, digest, read_json, write_json

HERE=Path(__file__).resolve().parent
HARNESS=('driver.cpp','runtime.h','telemetry.h','upstream-hooks.patch','physicelldfba-hooks.patch')


def command(*args): return subprocess.check_output(args,text=True).strip()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('build',type=Path,help='Directory created by build.sh')
    p.add_argument('executable',help='dfba-unit-test or cancer-core-metabolism')
    p.add_argument('--template',type=Path,required=True)
    p.add_argument('--notes',required=True,help='What this build is for, including any proposed fix')
    a=p.parse_args()
    build=a.build.resolve()
    record=read_json(a.template)
    record=record.get('build',record) if 'binary_sha256' not in record else record
    if (build/'source.patch').stat().st_size: raise ValueError('Build contains uncommitted source changes')
    for name in ('telemetry.h','runtime.h'):
        if digest(build/'benchmarks/performance'/name)!=digest(HERE/name): raise ValueError(f'Harness changed since build: {name}')
    ext=(build/'addons/dFBA/ext').resolve()
    for name,expected in record['libraries'].get('static_archives',{}).items():   # none for upstream PhysiCell
        if digest(ext/name)!=expected: raise ValueError(f'Dependency archive changed: {name}')
    patches=[]
    for line in (build/'applied-patches.txt').read_text().splitlines():
        checksum,path=line.split(maxsplit=1)
        if digest(path)!=checksum: raise ValueError(f'Patch changed since build: {path}')
        patches.append(dict(path=str(Path(path).resolve().relative_to(HERE)),sha256=checksum))
    harness={name:digest(HERE/name) for name in HARNESS}
    harness.update({x['path']:x['sha256'] for x in patches})
    executable=build/a.executable
    record.update(source_commit=(build/'source_commit.txt').read_text().strip(),
        benchmark_repository_commit=command('git','-C',str(REPO),'rev-parse','HEAD'),
        source_patches=patches,binary_sha256=digest(executable),compiler=command('g++','--version'),
        compiler_flags=next(l for l in (build/'build.log').read_text().splitlines() if l.startswith('g++ ') and ' -c ' in l).split(' -c ')[0],
        build_command=(build/'build-command.txt').read_text().strip(),
        build_host=command('lscpu'),compiler_target=command('g++','-march=native','-Q','--help=target'),
        build_log_sha256=digest(build/'build.log'),source_patch_sha256=digest(build/'source.patch'),
        benchmark_harness=harness,notes=a.notes)
    record['libraries']['dynamic_links']=command('ldd',str(executable))
    if 'not found' in record['libraries']['dynamic_links']: raise ValueError('Missing dynamic library')
    write_json(build/'build.json',record)
    print('Recorded',build/'build.json')


if __name__=='__main__': main()
