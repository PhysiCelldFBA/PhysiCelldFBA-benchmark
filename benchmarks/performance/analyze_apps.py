#!/usr/bin/env python3
"""Timing of the manuscript's own simulations run as shipped (apps workspace); no simulations or submissions.

Per run: wall time, peak memory and exit status (GNU time), simulated time reached, cells at the start, end and
maximum (from the snapshots), cell-steps (cells integrated over time divided by the diffusion dt) and the
resulting cost per cell-step and per simulated hour.
"""
import argparse
import csv
from pathlib import Path
import re
import xml.etree.ElementTree as ET
from common import digest, write_json


def write_table(path, records):
    keys = list(dict.fromkeys(k for r in records for k in r))
    with path.open('x', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys, lineterminator='\n'); writer.writeheader(); writer.writerows(records)


def gnu_time(path):
    text = path.read_text() if path.exists() else ''
    wall = re.search(r'Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): (\S+)', text)
    seconds = None
    if wall:
        parts = [float(x) for x in wall.group(1).split(':')]
        seconds = sum(v*60**i for i, v in enumerate(reversed(parts)))
    rss = re.search(r'Maximum resident set size \(kbytes\): (\d+)', text)
    status = re.search(r'Exit status: (\d+)', text)
    return seconds, int(rss.group(1)) if rss else None, int(status.group(1)) if status else None


def physicell_wall(path):
    """Last 'total wall time' printed by PhysiCell (fallback when the job was killed before GNU time reported)."""
    hits = re.findall(r'total wall time: (\d+) days, (\d+) hours, (\d+) minutes, and ([\d.e+-]+) seconds', path.read_text(errors='replace')) if path.exists() else []
    if not hits: return None
    d, h, m, s = hits[-1]
    return int(d)*86400 + int(h)*3600 + int(m)*60 + float(s)


def slurm_state(job):
    import subprocess
    try:
        out = subprocess.run(['sacct', '-j', job, '-X', '-n', '-P', '--format=State'], capture_output=True, text=True, timeout=60).stdout.split()
        return out[0] if out else None
    except (OSError, subprocess.SubprocessError):
        return None


def snapshot(xml):
    import scipy.io as sio
    root = ET.parse(xml).getroot()
    time = float(root.findtext('.//current_time'))
    name = root.find('.//cell_population//filename')
    if name is None: return time, 0
    cells = sio.loadmat(xml.parent/name.text)['cells']
    return time, cells.shape[1] if cells.ndim == 2 else 0


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workspace', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    jobs = list(csv.DictReader((a.workspace/'submitted-jobs.tsv').open(), delimiter='\t'))
    records, copied = [], {}
    a.output.mkdir(parents=True, exist_ok=False); (a.output/'tables').mkdir(); (a.output/'data').mkdir()
    for job in jobs:
        run = a.workspace/'runs'/job['name']
        info = dict(line.split(' ', 1) for line in (run/'run-info.txt').read_text().splitlines() if ' ' in line) if (run/'run-info.txt').exists() else {}
        config = ET.parse(run/job['config']).getroot()
        dt = float(config.findtext('overall/dt_diffusion')); max_time = float(config.findtext('overall/max_time'))
        intra = sorted({float(x.text) for x in config.iter('intracellular_dt')})
        out = run/config.findtext('save/folder').strip('./')
        snaps = sorted(snapshot(x) for x in list(out.glob('output*.xml')) + [out/'final.xml'] if x.exists()) if out.exists() else []
        cell_steps = sum((t1-t0)*(c0+c1)/2 for (t0, c0), (t1, c1) in zip(snaps, snaps[1:]))/dt if len(snaps) > 1 else None
        wall, rss, status = gnu_time(run/'time.txt')
        wall_source = 'gnu_time'
        if wall is None:   # killed (e.g. Slurm time limit): PhysiCell's own clock up to its last report
            wall, wall_source = physicell_wall(run/'stdout.log'), 'physicell_stdout'
        reached = snaps[-1][0] if snaps else None
        r = dict(name=job['name'], project=job['project'], config=job['config'], threads=int(info.get('threads_setting', 0) or 0),
                 slurm_job=job['job_id'], slurm_state=slurm_state(job['job_id']), exit_status=status,
                 completed=bool(reached is not None and reached >= max_time - 1e-6), simulated_minutes=max_time, reached_minutes=reached,
                 diffusion_dt=dt, intracellular_dt=';'.join(f'{x:g}' for x in intra), snapshots=len(snaps),
                 initial_cells=snaps[0][1] if snaps else None, final_cells=snaps[-1][1] if snaps else None,
                 max_cells=max(c for _, c in snaps) if snaps else None, wall_seconds=wall, wall_hours=round(wall/3600, 3) if wall else None, wall_source=wall_source,
                 peak_rss_gib=round(rss/1048576, 2) if rss else None,
                 wall_seconds_per_simulated_hour=round(wall/(reached/60), 2) if wall and reached else None,
                 microseconds_per_cell_step=round(1e6*wall/cell_steps, 2) if wall and cell_steps else None,
                 binary_sha256=info.get('binary_sha256'), config_sha256=info.get('config_sha256'), shipped_config_sha256=info.get('shipped_config_sha256'))
        records.append(r)
        dest = a.output/'data'/job['name']; dest.mkdir()
        for f in ('run-info.txt', 'time.txt', 'lscpu.txt', 'stderr.log'):
            if (run/f).exists(): (dest/f).write_bytes((run/f).read_bytes()); copied[f"data/{job['name']}/{f}"] = digest(run/f)
        if (run/'stdout.log').exists():
            tail = (run/'stdout.log').read_text(errors='replace').splitlines()[-60:]
            (dest/'stdout-tail.log').write_text('\n'.join(tail)+'\n')
    write_table(a.output/'tables/apps.csv', records)
    write_json(a.output/'analysis.json', dict(script_sha256=digest(__file__), workspace=str(a.workspace.resolve()), runs=len(records), evidence_sha256=copied,
        note='Cell-steps integrate the snapshot cell counts (trapezoid) over time divided by the diffusion dt; wall time includes start-up and output.'))
    for r in records: print({k: r[k] for k in ('name', 'threads', 'exit_status', 'reached_minutes', 'initial_cells', 'final_cells', 'max_cells', 'wall_hours', 'peak_rss_gib', 'microseconds_per_cell_step')})


if __name__ == '__main__': main()
