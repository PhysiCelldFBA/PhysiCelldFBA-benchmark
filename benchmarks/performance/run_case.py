#!/usr/bin/env python3
"""Run one staged benchmark inside a Slurm step and retain raw resource metrics."""

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

from common import config_metadata, digest, fingerprint, input_files, read_json, write_json


def capture(command):
    try:
        result = subprocess.run(command, text=True, capture_output=True, check=False,
                                env={**os.environ, "LC_ALL": "C"})
    except OSError as error:
        return {"command": command, "returncode": None, "stdout": "", "stderr": str(error)}
    return {"command": command, "returncode": result.returncode,
            "stdout": result.stdout, "stderr": result.stderr}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()
    if not os.environ.get("SLURM_JOB_ID") or not os.environ.get("SLURM_STEP_ID"):
        parser.error("Run this collector inside an srun step; it does not launch local simulations")
    bundle = args.bundle.resolve()
    manifest = read_json(bundle / "manifest.json")
    case = manifest["case"]
    if case["status"] != "ready" or case["open_decisions"]:
        parser.error("Case still has unresolved benchmark decisions")
    for relative, expected in manifest["files"].items():
        path = (bundle / relative).resolve()
        if not path.is_relative_to(bundle) or digest(path) != expected:
            parser.error(f"Bundle changed after staging: {relative}")
    expected_inputs = {name.removeprefix("inputs/"): value
                       for name, value in manifest["files"].items() if name.startswith("inputs/")}
    if input_files(bundle / "inputs") != expected_inputs:
        parser.error("Input files were added or removed after staging")
    config = config_metadata(bundle / "inputs/settings.xml")
    if config != manifest["configuration"] or config["threads"] != case["threads"]:
        parser.error("XML and recorded configuration disagree")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if allocated < case["threads"]:
        parser.error("Slurm allocation has fewer CPUs than the requested OpenMP threads")
    run_id = f"{case['case_id']}_job{os.environ['SLURM_JOB_ID']}_{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}"
    run = args.output_root.resolve() / run_id
    run.mkdir(parents=True, exist_ok=False)
    shutil.copytree(bundle / "inputs", run / "inputs")
    shutil.copy2(bundle / "simulation", run / "simulation")
    write_json(run / "manifest.json", manifest)
    env = dict(os.environ)
    env.update(LC_ALL="C", OMP_NUM_THREADS=str(case["threads"]), OMP_DYNAMIC="FALSE",
               OMP_PLACES="cores", OMP_PROC_BIND="spread", OMP_DISPLAY_ENV="TRUE",
               MKL_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", BLIS_NUM_THREADS="1",
               DFBA_PFBA_DUAL="0")
    lscpu = capture(["lscpu", "--json"])
    # Hostname and frequency fluctuations should not split repetitions of the
    # same hardware class; full topology and placement remain in hardware.json.
    cpu_fields = json.loads(lscpu["stdout"])["lscpu"] if lscpu["returncode"] == 0 else []
    cpu_class = {x["field"]: x["data"] for x in cpu_fields
                 if x["field"] in ("Architecture:", "Model name:", "Socket(s):", "Core(s) per socket:", "Thread(s) per core:", "NUMA node(s):")}
    hardware = {"lscpu": lscpu, "hostname": capture(["hostname"]),
                "uname": capture(["uname", "-a"]), "memory": Path("/proc/meminfo").read_text(),
                "affinity": sorted(os.sched_getaffinity(0)),
                "modules": os.environ.get("LOADEDMODULES", ""),
                "solver_environment": {"DFBA_PFBA_DUAL": env["DFBA_PFBA_DUAL"]},
                "slurm": {k: v for k, v in os.environ.items() if k.startswith("SLURM_")},
                "thread_environment": {k: env[k] for k in ("OMP_NUM_THREADS", "OMP_DYNAMIC", "OMP_PLACES", "OMP_PROC_BIND", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "BLIS_NUM_THREADS")},
                "node": capture(["scontrol", "show", "node", os.environ.get("SLURMD_NODENAME", os.uname().nodename)])}
    write_json(run / "hardware.json", hardware)
    resource = run / "resource.tsv"
    fmt = "elapsed_seconds=%e\nuser_seconds=%U\nsystem_seconds=%S\npeak_rss_kib=%M\ntime_exit_status=%x"
    command = ["/usr/bin/time", "-o", str(resource), "-f", fmt,
               str(run / "simulation"), "settings.xml"]
    write_json(run / "command.json", {"argv": command, "cwd": str(run / "inputs")})
    metrics = {"schema_version": 1, "case_id": case["case_id"], "returncode": None,
               "final_snapshot_present": False, "status": "incomplete_or_terminated",
               "resource": {}, "hardware_class": fingerprint(cpu_class) if cpu_class else None,
               "telemetry": None}
    # Leave an attempt record even if Slurm terminates the job before Python
    # regains control. Incomplete attempts remain visible in the raw CSV.
    write_json(run / "metrics.json", metrics)
    with (run / "stdout.log").open("w") as stdout, (run / "stderr.log").open("w") as stderr:
        result = subprocess.run(command, cwd=run / "inputs", env=env, stdout=stdout, stderr=stderr, check=False)
    values = {}
    for line in resource.read_text().splitlines() if resource.is_file() else []:
        key, separator, value = line.partition("=")
        if separator:
            try:
                parsed = float(value)
                if math.isfinite(parsed):
                    values[key] = parsed
            except ValueError:
                pass
    final_xml = run / "inputs/output/final.xml"
    final_time = None
    try:
        final_time = float(ET.parse(final_xml).findtext(".//current_time"))
        if not math.isfinite(final_time):
            final_time = None
    except (OSError, ET.ParseError, TypeError, ValueError):
        pass
    complete = final_time is not None and final_time >= config["max_time_minutes"] - 1e-8
    metrics.update(returncode=result.returncode, final_snapshot_present=final_xml.is_file(),
                   final_time_minutes=final_time,
                   status="completed" if result.returncode == 0 and complete else "failed", resource=values)
    # Optional measured counters from future instrumentation. Never infer them
    # from cell count / dt: custom objectives and missed updates invalidate that.
    telemetry = run / "inputs/benchmark_metrics.json"
    if telemetry.is_file():
        metrics["telemetry"] = read_json(telemetry)
        order = run / "inputs/benchmark_order.csv"
        if order.is_file(): metrics["telemetry"]["update_order_digest"] = digest(order)
        flags = metrics["telemetry"].get("diagnostic_flags", [])
        if metrics["telemetry"].get("initial_cells") != case["cells_requested"]:
            flags.append("initial_cell_count_mismatch")
        if metrics["telemetry"].get("actual_threads") != case["threads"]:
            flags.append("actual_thread_count_mismatch")
        metrics["telemetry"]["diagnostic_flags"] = flags
        if metrics["status"] == "completed" and flags:
            metrics["status"] = "completed_flagged"
    elif metrics["status"] == "completed":
        metrics["status"] = "missing_telemetry"
    write_json(run / "metrics.json", metrics)
    print(run)
    return 0 if metrics["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
