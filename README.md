# PhysiCelldFBA benchmarks

Reproducible benchmarks and diagnostics for
[PhysiCelldFBA](https://github.com/PhysiCelldFBA/PhysiCelldFBA), prepared for the
manuscript's supplementary material: protocols, the benchmark harness, analysis
scripts, and compact published results.

The simulator itself is not modified here. It is included as a git submodule pinned
to a public commit, and the benchmark instrumentation is applied at build time from
a patch. Every hook sits inside `#ifdef PHYSICELL_BENCHMARK`.

## Layout

| Path | Contents |
|---|---|
| [`supplementary/`](supplementary/SUPPLEMENTARY.md) | The manuscript's benchmark supplement ([PDF](supplementary/PhysiCelldFBA_benchmark_supplement.pdf)); `make_figures.py` draws Figures S1–S7 from the result tables, `build_pdf.sh` builds the PDF |
| [`PhysiCelldFBA/`](PhysiCelldFBA) | Submodule: the PhysiCelldFBA source under test (configs, SBML models, simulator) |
| [`benchmarks/README.md`](benchmarks/README.md) | Overview of the studies and their status |
| [`benchmarks/voxel_sharing/`](benchmarks/voxel_sharing) | Shared-voxel and mesh-occupancy concurrency diagnostics |
| [`benchmarks/performance/`](benchmarks/performance) | Shared build/telemetry harness, timestep, growth-condition and performance workflows |
| [`benchmarks/results/`](benchmarks/results) | Published reports: tables, figures and compact per-run evidence |
| [`PROVENANCE.md`](PROVENANCE.md) | Which public PhysiCelldFBA commit each result corresponds to, and how that was verified |

Generated campaigns, binaries and raw snapshots go in `benchmarks/workspaces/`, which
is not versioned.

## Main result so far

Before PhysiCelldFBA PR #19, parallel runs skipped intracellular updates and lost
concurrent substrate updates, driving glucose down to −0.6 mM. After it, all 225
parallel runs match their serial run exactly
([before/after report](benchmarks/results/voxel_sharing/before-after-20261027/README.md)).

## Getting started

```bash
git clone --recurse-submodules https://github.com/PhysiCelldFBA/PhysiCelldFBA-benchmark.git
cd PhysiCelldFBA-benchmark
```

The submodule is shallow and fetches only the pinned commit. Commands in the study
READMEs run from this repository's root.

- **Simulator dependencies:** libSBML and Clp are expected in
  `PhysiCelldFBA/addons/dFBA/ext`, installed with PhysiCelldFBA's own setup
  (`beta/setup_fba.py`). To reuse an existing installation, set
  `DFBA_EXT=/path/to/addons/dFBA/ext` when calling `benchmarks/performance/build.sh`.
- **Python:** preparation and collection use the standard library; analysis needs
  Matplotlib and NumPy, and snapshot analysis prefers `pctk`. Study READMEs write
  `source venv/bin/activate` for an environment in the repository root. On MN5 the
  environment is created with `module load hdf5 python/3.12.1`.
- **Another source checkout:** set `PHYSICELLDFBA_SOURCE=/path/to/PhysiCelldFBA` to
  read configs and models from somewhere other than the submodule. Pass the same
  path to `build.sh`.

Builds are made in isolated directories by
[`benchmarks/performance/build.sh`](benchmarks/performance/build.sh). Campaign
preparation refuses to run unless this repository, including the submodule pointer,
is committed and clean. No script submits jobs; Slurm launchers are run by hand. See
[`benchmarks/README.md`](benchmarks/README.md) for the reproduction and publication
procedure.

## Updating the simulator version

1. Check out the new commit in the submodule and commit the new pointer here.
2. Check that `benchmarks/performance/physicelldfba-hooks.patch` still applies; if
   not, regenerate it for the new source and record the change.
3. Rebuild, prepare **new** campaigns and compare them with the earlier reports
   (`benchmarks/voxel_sharing/compare_builds.py`). Never overwrite published results.

## License and citation

The code in this repository (benchmark harness, scripts and patches) is distributed under the BSD 3-Clause
license, the license of PhysiCell: see [LICENSE](LICENSE). The results, tables, figures and documentation are
distributed under CC-BY-4.0.

Release v1.0.0 is archived on Zenodo: [doi:10.5281/zenodo.24283791](https://doi.org/10.5281/zenodo.24283791).
