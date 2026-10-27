#!/usr/bin/env python3
"""Generate a draft case list or stage one independently reviewed input bundle.

Never builds an executable, changes the source tree, runs a simulation, or submits jobs.
"""

import argparse
from pathlib import Path
import re
import shutil
import xml.etree.ElementTree as ET

from common import config_metadata, digest, fingerprint, input_files, local_asset, read_json, write_json
from design import PHASES


HERE = Path(__file__).resolve().parent


def plan(args):
    import json
    from design import plan_cases
    cases = plan_cases(read_json(args.study), args.phase)
    with Path(args.output).open("x") as stream:
        for case in cases:
            stream.write(json.dumps(case, sort_keys=True) + "\n")
    print(f"Wrote {len(cases)} planned cases; no simulation launched.")


def stage(args):
    case = read_json(args.case)
    if case.get("status") != "ready" or case.get("open_decisions") or not case.get("validation_record"):
        raise ValueError("Case is still a draft: resolve its open decisions and record the numerical validation first")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", case["case_id"]):
        raise ValueError("case_id may contain only letters, digits, underscores, and hyphens")
    for name in ("threads", "cells_requested", "fields", "repeat"):
        if type(case[name]) is not int or case[name] < 1:
            raise ValueError(f"{name} must be a positive integer")
    if case["variant"] not in ("dfba", "pfba", "dfba_disabled", "upstream_physicell"):
        raise ValueError("Unknown benchmark variant")
    provenance = read_json(args.build)
    for name in ("source_commit", "upstream_commit", "compiler", "compiler_flags", "build_command", "libraries", "solver_settings", "binary_sha256", "benchmark_harness"):
        if not provenance.get(name):
            raise ValueError(f"Build provenance requires {name}; use 'not_applicable' for a nonmetabolic baseline")
    if digest(args.binary) != provenance["binary_sha256"]:
        raise ValueError("Executable does not match the checksum in the build record")
    source = Path(args.inputs).resolve()
    out = Path(args.output).resolve()
    if out.is_relative_to(source):
        raise ValueError("Stage the bundle outside the source input directory")
    files_before = input_files(source)
    if "settings.xml" not in files_before:
        raise ValueError("Input directory must contain settings.xml and its config/assets")
    if (source / "output").exists() or (source / "benchmark_metrics.json").exists():
        raise ValueError("Stage fresh inputs only, without previous output or benchmark telemetry")
    original = config_metadata(source / "settings.xml")
    controls = original["benchmark"]
    if controls.get("enabled") != "true":
        raise ValueError("An explicit enabled benchmark configuration is required")
    for name in ("layout", "fixed_positions", "fixed_population", "fixed_volume", "mixed"):
        expected = case.get(name, False)
        expected = str(expected).lower() if isinstance(expected, bool) else str(expected)
        if controls.get(name, "false") != expected:
            raise ValueError(f"Benchmark control {name} disagrees with the case")
    if controls.get("cells") != str(case["cells_requested"]):
        raise ValueError("Configured benchmark population disagrees with the case")
    if 'initial_position' in case:
        position = ET.parse(source / 'settings.xml').find('benchmark/position')
        if position is None or [float(position.get(a, 'nan')) for a in 'xyz'] != case['initial_position']:
            raise ValueError('Initial position disagrees with the case')
    if case['layout']=='explicit':
        from inputs import explicit_geometry
        root=ET.parse(source/'settings.xml').getroot()
        spacing,positions,_=explicit_geometry(root,case)
        actual=[[float(n.get(a,'nan')) for a in 'xyz'] for n in root.findall('benchmark/cell_position')]
        if actual!=positions or any(float(root.findtext('domain/d'+a))!=spacing for a in 'xyz'):
            raise ValueError('Explicit geometry disagrees with the case')
        if controls.get('expected_max_occupancy')!=str(case['expected_max_occupancy']):
            raise ValueError('Occupancy control disagrees with the case')
    if controls.get("permute") != str(case.get("order_seed") is not None).lower():
        raise ValueError("Permutation control disagrees with the case")
    if controls.get("diagnostics") != str(case["output_policy"] != "minimal").lower():
        raise ValueError("Output policy disagrees with case; use a separate timing case for minimal output")
    if original["fields"] != case["fields"]:
        raise ValueError("Case field count disagrees with the finalized XML")
    if case["variant"] in ("dfba", "pfba") and not original["intracellular"]:
        raise ValueError("dFBA case has no explicit dFBA cell definition; resolve XML inheritance before staging")
    if case["variant"] in ("dfba_disabled", "upstream_physicell") and original["intracellular"]:
        raise ValueError("Baseline input still contains an active dFBA definition")
    for model in original["intracellular"].values():
        if model["pfba_enabled"] != (case["variant"] == "pfba"):
            raise ValueError("Secondary-objective configuration disagrees with the case variant")
        if model["pfba_enabled"] and model["secondary_objective_type"] != "parsimonious":
            raise ValueError("pFBA case requires a parsimonious secondary objective")
        if "intracellular_dt_minutes" in case and model["effective_minutes"] != case["intracellular_dt_minutes"]:
            raise ValueError("Intracellular timestep disagrees with the diagnostic case")
    if "diffusion_dt_minutes" in case and original["diffusion_dt_minutes"] != case["diffusion_dt_minutes"]:
        raise ValueError("Diffusion timestep disagrees with the diagnostic case")
    if case.get("order_seed") is not None and original["benchmark_order_seed"] != str(case["order_seed"]):
        raise ValueError("Diagnostic case requires an explicit benchmark_order_seed input and validated order instrumentation")
    if "simulation_seed" in case:
        seeds = (original["seed_options"], original["seed_user_parameter"])
        if not any(seed is not None for seed in seeds) or any(seed is not None and seed != str(case["simulation_seed"]) for seed in seeds):
            raise ValueError("Simulation RNG seeds disagree with the diagnostic case")
    xml = ET.parse(source / "settings.xml")
    for node in xml.findall(".//intracellular/settings/sbml_filename"):
        local_asset(source, node.text)
    positions = xml.find("initial_conditions/cell_positions")
    if positions is not None and positions.get("enabled", "false").lower() == "true":
        local_asset(source, str(Path(positions.findtext("folder", ".")) / positions.findtext("filename", "")))
    for rules in xml.findall("cell_rules/rulesets/ruleset"):
        if rules.get("enabled", "false").lower() == "true":
            local_asset(source, str(Path(rules.findtext("folder", ".")) / rules.findtext("filename", "")))
    for node_path in ("parallel/omp_num_threads", "save/folder"):
        if xml.find(node_path) is None:
            raise ValueError(f"Missing {node_path}")
    out.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, out / "inputs")
    xml.find("parallel/omp_num_threads").text = str(case["threads"])
    xml.find("save/folder").text = "output"
    xml.write(out / "inputs/settings.xml", encoding="utf-8", xml_declaration=True)
    shutil.copy2(args.binary, out / "simulation")
    (out / "simulation").chmod(0o750)
    (out / "tools").mkdir()
    for name in ("run_case.py", "common.py"):
        shutil.copy2(HERE / name, out / "tools" / name)
    metadata = config_metadata(out / "inputs/settings.xml")
    assert original["diffusion_dt_minutes"] == metadata["diffusion_dt_minutes"]
    assert original["intracellular"] == metadata["intracellular"]
    # Normalize only thread count for strong-scaling comparisons. Seeds, output
    # settings, timestep choices, geometry and every asset stay in the identity.
    xml.find("parallel/omp_num_threads").text = "THREAD_COUNT"
    assets = input_files(out / "inputs")
    # The input record contains case labels/repeat/thread metadata, not physics.
    # Its full checksum is retained in files, but must not prevent matching
    # otherwise identical serial/parallel workloads or timing repetitions.
    comparable_assets = {k: v for k, v in assets.items() if k not in ("settings.xml", "input-record.json")}
    workload = {"xml": ET.tostring(xml.getroot(), encoding="unicode"), "assets": comparable_assets,
                "build": provenance, "binary": digest(out / "simulation"), "variant": case["variant"]}
    manifest = {"schema_version": 1, "case": case, "build": provenance,
                "configuration": metadata, "comparison_key": fingerprint(workload),
                "files": input_files(out)}
    write_json(out / "manifest.json", manifest)
    print(f"Staged {case['case_id']} at {out}. Timesteps preserved; no job submitted.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    draft = commands.add_parser("plan")
    draft.add_argument("--study", default=HERE / "study.json", type=Path)
    draft.add_argument("--phase", choices=PHASES, default="pilot")
    draft.add_argument("--output", required=True, type=Path)
    draft.set_defaults(action=plan)
    bundle = commands.add_parser("stage")
    for name in ("case", "inputs", "binary", "build", "output"):
        bundle.add_argument(f"--{name}", required=True, type=Path)
    bundle.set_defaults(action=stage)
    args = parser.parse_args()
    args.action(args)


if __name__ == "__main__":
    main()
