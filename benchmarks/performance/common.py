"""Standard-library helpers for benchmark provenance; no simulation imports."""

import hashlib
import json
import math
import os
from pathlib import Path
import xml.etree.ElementTree as ET

# This repository (protocols, harness, results) and the PhysiCelldFBA source it
# benchmarks: the pinned submodule, or the checkout named by PHYSICELLDFBA_SOURCE.
REPO = Path(__file__).resolve().parents[2]
SOURCE = Path(os.environ.get("PHYSICELLDFBA_SOURCE") or REPO / "PhysiCelldFBA").resolve()


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def positive(value, name):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return number


def config_metadata(path):
    root = ET.parse(path).getroot()
    diffusion_dt = positive(root.findtext("overall/dt_diffusion"), "dt_diffusion")
    steps = {}
    for cell in root.findall("cell_definitions/cell_definition"):
        model = cell.find("phenotype/intracellular")
        if model is None or model.get("type") != "dfba":
            continue
        step = model.findtext("settings/intracellular_dt")
        if step is None:
            step = model.findtext("settings/time_step")
        secondary = model.find("secondary_objective")
        pfba_enabled = secondary is not None and secondary.get("enabled", "true").lower() in ("true", "1")
        steps[cell.get("name", "unnamed")] = {
            "declared": step,
            "effective_minutes": positive(step, "intracellular_dt") if step is not None else diffusion_dt,
            "sbml": model.findtext("settings/sbml_filename"),
            "pfba_enabled": pfba_enabled,
            "secondary_objective_type": secondary.get("type", "parsimonious") if secondary is not None else None,
            "fraction_of_optimum": secondary.get("fraction_of_optimum", secondary.findtext("fraction_of_optimum", "1.0")) if secondary is not None else None,
        }
    return {
        "diffusion_dt_minutes": diffusion_dt,
        "mechanics_dt_minutes": root.findtext("overall/dt_mechanics"),
        "phenotype_dt_minutes": root.findtext("overall/dt_phenotype"),
        "intracellular": steps,
        "max_time_minutes": positive(root.findtext("overall/max_time"), "max_time"),
        "threads": int(root.findtext("parallel/omp_num_threads")),
        "fields": len(root.findall("microenvironment_setup/variable")),
        "domain": {node.tag: node.text for node in root.findall("domain/*")},
        "seed_options": root.findtext("options/random_seed"),
        "seed_user_parameter": root.findtext("user_parameters/random_seed"),
        "benchmark_order_seed": root.find("benchmark").get("order_seed") if root.find("benchmark") is not None else None,
        "benchmark": dict(root.find("benchmark").attrib) if root.find("benchmark") is not None else {},
    }


def input_files(folder):
    folder = Path(folder)
    result = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Input bundles must contain files, not symlinks: {path}")
        if path.is_file():
            result[path.relative_to(folder).as_posix()] = digest(path)
    return result


def local_asset(folder, name):
    if not name or Path(name).is_absolute():
        raise ValueError(f"Expected a relative bundled input path, got {name!r}")
    folder = Path(folder).resolve()
    path = (folder / name).resolve()
    if not path.is_relative_to(folder) or not path.is_file():
        raise ValueError(f"Missing or external input: {name}")
    return path
