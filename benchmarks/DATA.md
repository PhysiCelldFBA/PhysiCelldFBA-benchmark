# Raw benchmark data: what is where and how to read it

The repository contains the **compact results** (tables, figures, per-run metrics and logs) under
[`results/`](results/). The **raw campaign outputs** (every input bundle, MultiCellDS snapshot and per-step
telemetry table) are too large for Git (about 140 GB for the final campaigns) and are kept on MareNostrum 5:

| Location | Contents |
|---|---|
| `/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA-benchmark/benchmarks/workspaces/` | Final campaigns (PhysiCelldFBA `c59daa81`) and the 2026-10-27 timestep stages |
| `/gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA/benchmarks/workspaces/` | Earliest campaigns of 2026-10-26/27: pre-fix voxel and mesh, after PR #19, pilots, growth conditions |

`/gpfs/scratch` is a scratch file system. Copy the data to project storage or an archive before relying
on it long-term. Every campaign carries `campaign.sha256`, so its pinned files can be checked after a copy
(`sha256sum --check campaign.sha256`, which needs the original absolute paths, or an adapted copy of the list).

## Final campaigns

| Campaign folder | Study | Runs | Size | Report |
|---|---|---:|---:|---|
| `voxel-final-20261102` | Eight cells in one voxel, 1/2/4/8 threads, order seeds | 60 | 2.2 GB | [voxel-final-20261102](results/voxel_sharing/voxel-final-20261102/README.md) |
| `mesh-final-20261102` | 16/8/4/2 µm meshes (8/4/2/1 cells per voxel) | 240 | 8.6 GB | [mesh-final-20261102](results/voxel_sharing/mesh-final-20261102/README.md) |
| `tradeoff-accuracy-{fix,dev}-d0_01-final-20261102` | Timestep accuracy, diffusion dt 0.01, PR commit / unfixed | 29 + 29 | 4.7 + 4.7 GB | [tradeoff-accuracy-d0_01](results/timestep/tradeoff-accuracy-d0_01-final-20261102/README.md) |
| `tradeoff-accuracy-{fix,dev}-d0_001-final-20261102` | Timestep accuracy, diffusion dt 0.001 | 29 + 29 | 38 + 38 GB | [tradeoff-accuracy-d0_001](results/timestep/tradeoff-accuracy-d0_001-final-20261102/README.md) |
| `tradeoff-cost-fix-d0_01-final-20261102` | Timestep cost, 1000 cells, 1/56 threads | 126 | 6.3 GB | [tradeoff-cost-d0_01](results/timestep/tradeoff-cost-d0_01-final-20261102/README.md) |
| `tradeoff-cost-fix-d0_001-final-20261102` | Timestep cost at diffusion dt 0.001 | 126 | 6.3 GB | [tradeoff-cost-d0_001](results/timestep/tradeoff-cost-d0_001-final-20261102/README.md) |
| `growth-final-20261102` | Growth-condition controls | 23 | 1.9 GB | [growth-final-20261102](results/growth_conditions/growth-final-20261102/README.md) |
| `pfba-final-20261104` | Cancer FBA vs pFBA (single cell, application) | 8 | 1.2 GB | [pfba-final-20261104](results/pfba/pfba-final-20261104/README.md) |
| `scaling-final-20261104` | Performance and scaling, 3 variants | 405 | 19 GB | [scaling-final-20261104](results/performance/scaling-final-20261104/README.md) |
| `apps-20261109` | The manuscript's own simulations as shipped (timing) | 12 | 7.4 GB | [apps-20261109](results/applications/apps-20261109/README.md) |
| `unit-tests-c59daa81` | PhysiCelldFBA's `dfba_unit_test` suite on `c59daa81` | — | 0.1 GB | [unit_tests/c59daa81](results/unit_tests/c59daa81/README.md) |

Build folders (`final-20261102/{fix,dev}`, `studies-20261104/upstream`, `apps-20261109/build`), preflight runs,
pilots (`pfba-pilot-20261104`, `dtfix-20261027`, `dt-pilot-*`, `tradeoff-*-20261027`) and the job lists
(`*/submitted-jobs.tsv`) are kept alongside. Their compact results are in the earlier-stage reports linked
from [README.md](README.md).

`apps-20261109` is not a campaign: it holds `build/<project>/` (stock builds), `runs/<name>/` (the executable,
the `config/` folder as run, `run-info.txt`, GNU time `time.txt`, `stdout.log`, `stderr.log` and the project's own
output folder with snapshots and SVGs), `submitted-jobs.tsv` and `diagnostics/`.

## Layout of a campaign

```
<campaign>/
  campaign.json        preparation commit, protocol, builds, duration, case count, launch-order seed
  campaign.sha256      checksums of the pinned files (campaign.json, case lists, every bundle manifest)
  study.json / protocol.json / build.json   (as applicable) the design and the build record used
  tools/run_mn5.sbatch the launcher copied at preparation
  <part>/              voxel_sharing/ or timestep/ (growth campaigns keep these at the top level)
    cases.jsonl        one JSON case per line: model, cells, threads, timesteps, layout, controls, seeds
    launch-order.txt   randomized order of all bundles; launch-<group>.txt: the case list of one Slurm job
    inputs/<case>/     materialized inputs (settings.xml, SBML, positions)
    bundles/<case>/    immutable bundle: inputs/, a copy of the executable (simulation), tools/, manifest.json
    runs/<case>_job<JOBID>_<UTC timestamp>/   one attempt (see below); a case never has more than one
    logs/              slurm-<JOBID>.{out,err}; collection-<JOBID>.tsv (case, collector exit code)
```

The collector exit code is nonzero when a run completed **with diagnostic flags**. A Slurm `FAILED` state
therefore usually means "flagged", not "crashed". Check `metrics.json` (`status`) before drawing conclusions.

## Layout of one run

| File | Contents |
|---|---|
| `manifest.json` | The case, the full build record (`build`), input-file digests, comparison key |
| `metrics.json` | `status` (`completed`, `completed_flagged`, ...), return code, `resource` (wall time, peak RSS), telemetry summary |
| `hardware.json` | Node, `lscpu`, memory, loaded modules, CPU affinity, OpenMP and BLAS environment |
| `resource.tsv`, `command.json`, `stdout.log`, `stderr.log` | GNU time output, exact command, program output |
| `simulation` | The executable that ran (identical to the bundle's; SHA-256 in the manifest) |
| `inputs/settings.xml` | The PhysiCell configuration actually used |
| `inputs/benchmark_metrics.json` | Run telemetry: phase timings, solver calls, iterations, LP sizes, failures, flags |
| `inputs/benchmark_*.csv` | Per-step telemetry (only for output policies with diagnostics; see below) |
| `inputs/output/` | MultiCellDS snapshots: `initial.xml`, `output########.xml`, `final.xml` with `*_cells.mat` and `*_microenvironment0.mat` |

### Telemetry tables (`inputs/benchmark_*.csv`)

| File | Columns | Meaning |
|---|---|---|
| `benchmark_population.csv` | time_minutes, phase, cells, total_dry_mass_pg, max_cells_per_voxel | Population after each step (`phase`: initial, after_cell_step, final) |
| `benchmark_substrates.csv` | time_minutes, phase, field_index, field_name, amount_concentration_um3, min_concentration | Domain amount (mM·µm³) and minimum concentration (mM) of every field |
| `benchmark_exchange_balance.csv` | time_minutes, field_index, before_amount, after_amount, expected_net_export_delta, observed_delta, residual, net_export_only | Exchange ledger of the cell-exchange step; cell uptake = −Σ observed_delta |
| `benchmark_cells.csv` | time_minutes, cell_id, dry_mass_pg, volume_um3, growth_per_hour, primary_status, secondary_status, total_internal_abs_flux | One row per cell and FBA update |
| `benchmark_fluxes.csv` | time_minutes, cell_id, field_index, net_export_BioFVM_per_min | Exchange rate set by each update, per field |
| `benchmark_update_counts.csv` | cell_id, due, actual | Intracellular updates due and performed |
| `benchmark_order.csv` | traversal_index, cell_id | Cell traversal order after the once-per-run permutation |
| `benchmark_positions.csv` | cell_id, x_um, y_um, z_um, voxel_index | Initial positions and voxels |

Output policies: `diagnostic_endpoints` writes all tables and only initial/final snapshots; `minimal` (timing
runs) writes only `benchmark_metrics.json`; `snapshots_hourly` (application runs) writes hourly snapshots and
no per-step tables. Glucose and the other fields are in mM; the ledger amounts are mM·µm³.

### Snapshots

Standard PhysiCell/MultiCellDS output. Read with `pctk` (preferred) or with `scipy.io.loadmat`: cell variables
are rows of `*_cells.mat`, indexed by the `<label>` entries of the matching XML. Fields are rows 4+ of
`*_microenvironment0.mat`, in the order of the XML `<variable>` list. The application runs also carry dFBA
custom data per cell (`growth_rate`, `R_EX_*` exchange fluxes and their applied bounds `R_EX_*_lb`).

## Re-running an analysis

Inside a compute allocation, with `module load hdf5 python/3.12.1` and the environment in
[`environment/`](environment/), run the script named in the study report on its campaign folder. For example:

```bash
python benchmarks/performance/analyze_scaling.py --campaign benchmarks/workspaces/scaling-final-20261104 --output /new/folder --plots
```

Each report's `analysis.json` lists the SHA-256 of the analysis script and of every evidence file it copied,
so a re-analysis can be compared file by file.
