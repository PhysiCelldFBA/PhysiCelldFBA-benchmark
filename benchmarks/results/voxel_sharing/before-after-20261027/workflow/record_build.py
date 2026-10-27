import json
from pathlib import Path
import subprocess
import sys
root=Path.cwd()
sys.path.insert(0,str(root/'benchmarks/performance'))
from common import digest, read_json, write_json
def command(*args): return subprocess.check_output(args,text=True).strip()
build=Path(sys.argv[1]).resolve(); executable=sys.argv[2]; original=Path(sys.argv[3])
record=read_json(original)
if (build/'source.patch').stat().st_size: raise ValueError('Build contains uncommitted changes')
for name,expected in record['libraries']['static_archives'].items():
    if digest(root/'addons/dFBA/ext'/name)!=expected: raise ValueError('Dependency archive changed')
record.update(source_commit=(build/'source_commit.txt').read_text().strip(),
    binary_sha256=digest(build/executable),compiler=command('g++','--version'),
    compiler_flags=next(line for line in (build/'build.log').read_text().splitlines() if line.startswith('g++ ') and ' -c ' in line).split(' -c ')[0],
    build_command=f'bash benchmarks/performance/build.sh {root} {build} '+('dfba_unit_test' if executable=='dfba-unit-test' else 'cancer_core_metabolism')+' 16',
    build_host=command('lscpu'),compiler_target=command('g++','-march=native','-Q','--help=target'),
    build_log_sha256=digest(build/'build.log'),source_patch_sha256=digest(build/'source.patch'),
    benchmark_harness={name:digest(build/'benchmarks/performance'/name) for name in ('driver.cpp','runtime.h','telemetry.h','upstream-hooks.patch')},
    notes='Fresh clean-source build with explicit-position observation/control at the merge of PR #19 (byte-vector intracellular update flags; per-voxel locks in Basic_Agent::simulate_secretion_and_uptake). Dependency identities verified against previous build.')
record['libraries']['dynamic_links']=command('ldd',str(build/executable))
if 'not found' in record['libraries']['dynamic_links']: raise ValueError('Missing dynamic library')
write_json(build/'build.json',record)
print('Recorded',build/'build.json')
