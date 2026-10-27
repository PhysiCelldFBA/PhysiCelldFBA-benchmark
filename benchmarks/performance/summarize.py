#!/usr/bin/env python3
"""Collect benchmark JSON into CSV and optional supplementary figures.

Run manually in the documented Python analysis environment. This reads only
benchmark metadata, not PhysiCell snapshots (use pctk for biological validation).
"""

import argparse
from collections import defaultdict
import csv
import json
import math
from pathlib import Path
import statistics

from common import read_json


def number(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def ratio(a, b):
    return a / b if a is not None and b is not None and b > 0 else None


def load_run(path):
    metrics = read_json(path)
    manifest = read_json(path.parent / "manifest.json")
    case = manifest["case"]
    configuration = manifest["configuration"]
    resource = metrics.get("resource", {})
    telemetry = metrics.get("telemetry") or {}
    wall = number(resource.get("elapsed_seconds"))
    calls = number(telemetry.get("optimization_calls"))
    loop = number(telemetry.get("simulation_loop_seconds"))
    actual_threads = number(telemetry.get("actual_threads"))
    status = metrics["status"]
    if actual_threads is not None and actual_threads != case["threads"]:
        status = "thread_count_mismatch"
    if status == "completed" and (not wall or not metrics.get("hardware_class")):
        status = "incomplete_metrics"
    return {
        "run_directory": str(path.parent), "case_id": case["case_id"],
        "phase": case["phase"], "model": case["model"], "variant": case["variant"],
        "interpretation": case.get("interpretation", "performance_candidate"),
        "simulation_seed": case.get("simulation_seed", configuration.get("seed_user_parameter")),
        "order_seed": case.get("order_seed"),
        "diffusion_dt_minutes": configuration["diffusion_dt_minutes"],
        "intracellular_configuration": json.dumps(configuration["intracellular"], sort_keys=True),
        "cells_requested": case["cells_requested"], "fields": case["fields"],
        "threads_requested": case["threads"], "threads_observed": actual_threads,
        "repeat": case["repeat"], "status": status, "run_status": metrics["status"],
        "comparison_key": manifest["comparison_key"], "hardware_class": metrics.get("hardware_class"),
        "source_commit": manifest["build"]["source_commit"],
        "elapsed_seconds": wall, "peak_rss_mib": ratio(number(resource.get("peak_rss_kib")), 1024),
        "user_seconds": number(resource.get("user_seconds")),
        "system_seconds": number(resource.get("system_seconds")),
        "optimization_calls": calls, "initial_solve_calls": number(telemetry.get("initial_solve_calls")),
        "model_optimization_calls": number(telemetry.get("model_optimization_calls")),
        "stage_one_solve_calls": number(telemetry.get("stage_one_solve_calls")),
        "stage_two_solve_calls": number(telemetry.get("stage_two_solve_calls")),
        "stage_two_retries": number(telemetry.get("stage_two_retries")),
        "stage_two_failures": number(telemetry.get("stage_two_failures")),
        "stage_one_thread_seconds": number(telemetry.get("stage_one_thread_seconds")),
        "stage_two_thread_seconds": number(telemetry.get("stage_two_thread_seconds")),
        "intracellular_updates": number(telemetry.get("intracellular_updates")),
        "update_order_digest": telemetry.get("update_order_digest"),
        "max_cells_per_voxel": number(telemetry.get("max_cells_per_voxel")),
        "calls_per_end_to_end_second": ratio(calls, wall),
        "calls_per_loop_second": ratio(calls, loop),
        "simulation_loop_seconds": loop,
        "initialization_seconds": number(telemetry.get("initialization_seconds")),
        "solver_thread_seconds": number(telemetry.get("solver_thread_seconds")),
        "diffusion_seconds": number(telemetry.get("diffusion_seconds")),
        "mechanics_seconds": number(telemetry.get("mechanics_seconds")),
        "intracellular_seconds": number(telemetry.get("intracellular_seconds")),
        "output_seconds": number(telemetry.get("output_seconds")),
        "solver_failures": number(telemetry.get("solver_failures")),
        "initial_cells_observed": number(telemetry.get("initial_cells")),
        "final_cells_observed": number(telemetry.get("final_cells")),
        "telemetry_present": bool(telemetry),
        "diagnostic_flags": json.dumps(telemetry.get("diagnostic_flags", [])),
        "sampling": telemetry.get("sampling"),
        "voxel_count": number(telemetry.get("voxel_count")),
        "validation_seconds": number(telemetry.get("validation_seconds")),
        "exchange_seconds": number(telemetry.get("exchange_seconds")),
        "phenotype_seconds": number(telemetry.get("phenotype_seconds")),
    }


def summarize(rows):
    groups = defaultdict(list)
    for row in rows:
        if row["status"] == "completed":
            groups[(row["phase"], row["comparison_key"], row["hardware_class"], row["threads_requested"])].append(row)
    result = []
    for (phase, key, hardware, threads), members in sorted(groups.items()):
        first = members[0]
        summary = {name: first[name] for name in ("model", "variant", "cells_requested", "fields", "phase", "source_commit",
                                                 "interpretation", "simulation_seed", "order_seed", "diffusion_dt_minutes", "intracellular_configuration")}
        summary.update(comparison_key=key, hardware_class=hardware, threads=threads,
                       repetitions=len(members), repetitions_with_telemetry=sum(x["telemetry_present"] for x in members))
        for metric in ("elapsed_seconds", "peak_rss_mib", "calls_per_end_to_end_second", "calls_per_loop_second"):
            values = [x[metric] for x in members if x[metric] is not None]
            summary[metric + "_median"] = statistics.median(values) if values else None
            summary[metric + "_min"] = min(values) if values else None
            summary[metric + "_max"] = max(values) if values else None
        result.append(summary)
    serial = {(x["phase"], x["comparison_key"], x["hardware_class"]): x["elapsed_seconds_median"] for x in result
              if x["threads"] == 1 and x["phase"] in ("pilot", "main")}
    for row in result:
        # Never substitute a serial run from another model, timestep, mesh,
        # executable, seed, output policy, or hardware class.
        row["end_to_end_speedup"] = ratio(serial.get((row["phase"], row["comparison_key"], row["hardware_class"])), row["elapsed_seconds_median"])
        row["end_to_end_efficiency"] = ratio(row["end_to_end_speedup"], row["threads"])
    return result


def write_csv(path, rows):
    if not rows:
        return
    with path.open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plots(output, summaries):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # Known-race and timestep diagnostics have separate scientific questions;
    # never display them as evidence of validated computational scaling.
    summaries = [row for row in summaries if row["phase"] in ("pilot", "main")]
    for metric, ylabel in (("elapsed_seconds", "End-to-end wall time (s)"), ("peak_rss_mib", "Peak process RSS (MiB)"),
                           ("calls_per_end_to_end_second", "Measured optimization calls / wall second")):
        figure, ax = plt.subplots(figsize=(7, 4.5))
        groups = defaultdict(list)
        for row in summaries:
            if row[metric + "_median"] is not None:
                groups[(row["phase"], row["model"], row["variant"], row["fields"], row["threads"])].append(row)
        for (phase, model, variant, fields, threads), members in sorted(groups.items()):
            x = [r["cells_requested"] for r in members]
            y = [r[metric + "_median"] for r in members]
            lower = [r[metric + "_median"] - r[metric + "_min"] for r in members]
            upper = [r[metric + "_max"] - r[metric + "_median"] for r in members]
            ax.errorbar(x, y, yerr=[lower, upper], fmt="o", label=f"{phase}, {model}, {variant}, F={fields}, P={threads}")
        if not groups:
            ax.text(0.5, 0.5, "No measured values available", ha="center", transform=ax.transAxes)
        else:
            ax.set_xscale("log")
            ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1.02, 1))
        ax.set(xlabel="Configured initial cell count", ylabel=ylabel)
        figure.tight_layout()
        for extension in ("pdf", "png"):
            figure.savefig(output / f"{metric}.{extension}", bbox_inches="tight", dpi=200)
        plt.close(figure)
    figure, ax = plt.subplots(figsize=(7, 4.5))
    groups = defaultdict(list)
    for row in summaries:
        if row["end_to_end_speedup"] is not None:
            groups[(row["phase"], row["comparison_key"], row["hardware_class"])].append(row)
    for (phase, key, _), members in sorted(groups.items()):
        members.sort(key=lambda r: r["threads"])
        first = members[0]
        ax.plot([r["threads"] for r in members], [r["end_to_end_speedup"] for r in members], "o-",
                label=f"{phase}, {first['model']}, {first['variant']}, N={first['cells_requested']}, F={first['fields']} ({key[:6]})")
    if groups:
        max_threads = max(r["threads"] for r in summaries)
        ax.plot([1, max_threads], [1, max_threads], "k--", label="Ideal")
        ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1.02, 1))
    else:
        ax.text(0.5, 0.5, "No matching serial references", ha="center", transform=ax.transAxes)
    ax.set(xlabel="Requested OpenMP threads", ylabel="End-to-end speedup over matching serial run")
    figure.tight_layout()
    for extension in ("pdf", "png"):
        figure.savefig(output / f"speedup.{extension}", bbox_inches="tight", dpi=200)
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roots", nargs="+", type=Path, help="Benchmark results under runs/ or output/")
    parser.add_argument("--output", required=True, type=Path, help="New directory; existing reports are never replaced")
    parser.add_argument("--plots", action="store_true", help="Requires matplotlib")
    args = parser.parse_args()
    paths = sorted({p.resolve() for root in args.roots for p in root.rglob("metrics.json")})
    if not paths:
        parser.error("No benchmark metrics.json files found")
    rows = [load_run(path) for path in paths]
    summaries = summarize(rows)
    args.output.mkdir(parents=True, exist_ok=False)
    write_csv(args.output / "runs.csv", rows)
    write_csv(args.output / "summary.csv", summaries)
    if args.plots:
        plots(args.output, summaries)
    print(f"Collected {len(rows)} attempts; {sum(r['status'] == 'completed' for r in rows)} completed. Missing telemetry stays blank.")


if __name__ == "__main__":
    main()
