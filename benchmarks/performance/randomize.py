#!/usr/bin/env python3
"""Write a reproducible launch order from staged bundles. Never submit jobs."""
import argparse
from pathlib import Path
import random
from common import read_json, write_json, digest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('bundles',nargs='+',type=Path)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.output.exists(): p.error('Launch-order record already exists')
    items=[]
    for path in args.bundles:
        path=path.resolve(); manifest=read_json(path/'manifest.json')
        if manifest['case']['status']!='ready' or manifest['case']['open_decisions']: p.error(f'Unready bundle: {path}')
        items.append(dict(bundle=str(path),case_id=manifest['case']['case_id'],manifest_sha256=digest(path/'manifest.json')))
    if len({x['case_id'] for x in items})!=len(items): p.error('Duplicate case IDs')
    items.sort(key=lambda x:x['case_id']); random.Random(args.seed).shuffle(items)
    write_json(args.output,dict(seed=args.seed,launch_order=items,submitted=False))
if __name__=='__main__': main()
