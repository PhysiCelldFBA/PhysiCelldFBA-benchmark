# Eight cells sharing one voxel

This diagnostic is based on the existing
[`Unit_test_voxel_sharing_n8.xml`](../../sample_projects_intracellular/fba/dfba_unit_test/config/Unit_test_voxel_sharing_n8.xml)
and its E. coli core model. It measures how thread count and a single initial
cell-order permutation affect shared-substrate exchange and intracellular updates.
The results may support a recommendation to avoid shared voxels in this version;
the experiment must first establish what actually happens.

## Frozen protocol

[`protocol.json`](protocol.json) specifies **60 runs**:

- Eight cells at `(0,0,0)`, as in the sample's `setup_tissue`, sharing one voxel.
- 1, 2, 4 and 8 OpenMP threads; one thread is the serial control.
- Initialization-order seeds 11, 23, 37, 51 and 71.
- Three independent repetitions of each thread/seed combination.
- The original test's duration: **0.1 min**, with diffusion and intracellular
  timesteps **0.01 min**. These values are inherited from this test, not enforced
  in the general engine. Snapshots follow intracellular dt.
- Original `[-8,8]` domain in each dimension, voxel spacing **1.6 µm**, original
  fields, initial concentrations, diffusion coefficients and metabolic mappings.
- Standard FBA, simulation RNG seed 50. Positions and population are fixed for
  the diagnostic; metabolic biomass/volume growth remains enabled.

The common benchmark driver compiles the unit-test custom code and preserves its
diffusion/exchange/intracellular ordering and loop end condition. It replaces the
normal main with an instrumented main and controlled placement. It suppresses
movement, division/removal/death so all eight cells stay in the shared voxel. These
are disclosed experimental controls, not a claim of byte-identical execution of
the original application. Original input settings and assets are hashed.

A separate mt19937/Fisher–Yates permutation changes the `all_cells` traversal
order **once, at initialization**. Cell IDs stay stable; the simulation RNG stays
fixed. `benchmark_order.csv` records the permutation. There is no per-timestep
shuffle. OpenMP execution/interleaving is not fixed by that permutation. Repeat
runs with the same seed distinguish scheduling variability from initial order.
Run launch order is randomized with its own recorded seed.

## Prepare

From the repository root, build the unit-test benchmark in a new directory:

```bash
mkdir -p benchmarks/workspaces
bash benchmarks/performance/build.sh PhysiCelldFBA "$PWD/benchmarks/workspaces/unit-build" dfba_unit_test 4
```

Fill a `build.json` from [`build.example.json`](../performance/build.example.json)
and the actual build evidence (see the [shared build instructions](../performance/README.md)).
`benchmark_harness` must map `driver.cpp`, `runtime.h`, `telemetry.h`,
`physicelldfba-hooks.patch` (builds after the move to this repository) and
`upstream-hooks.patch` to their SHA-256 digests; `binary_sha256` must match the
executable. Record actual compiler flags, libraries and solver settings. An
existing validated binary may be reused if those identities still match. The
campaign records simulation and preparation source revisions separately.

After committing preparation sources, load the project Python environment and run:

```bash
module load hdf5 python/3.12.1
source venv/bin/activate
python benchmarks/voxel_sharing/prepare.py \
  --binary benchmarks/workspaces/unit-build/dfba-unit-test \
  --build /absolute/path/to/build.json \
  --output benchmarks/workspaces/voxel-campaign
```

The preparation refuses to overwrite a campaign and never runs a simulation.
It creates `timestep/`, `voxel_sharing/`, `pfba/` and `performance/` subfolders.
Each has `inputs/`, `bundles/`, `runs/`, `tables/`, `plots/` and `logs/`; only
`voxel_sharing/` receives cases in this protocol. `campaign.json`, `protocol.json`,
`build.json`, checksums and a randomized launch list document the campaign.

## Submit on MN5

```bash
campaign=$(realpath benchmarks/workspaces/voxel-campaign)
sbatch --output="$campaign/voxel_sharing/logs/slurm-%j.out" \
  --error="$campaign/voxel_sharing/logs/slurm-%j.err" \
  "$campaign/tools/run_mn5.sbatch" "$campaign"
```

One allocation runs the 60 cases sequentially in individual `srun` steps. It
reserves the same exclusive GPP node and 112 physical slots throughout, even
for serial cases, with fixed core/spread affinity and single-thread BLAS. Account,
partition and QoS defaults are `bsc08`, `gpp`, `gp_bscls`; adjust them for your
allocation. The default wall limit is 30 minutes. Hardware and actual thread
counts are recorded per attempt; these short diagnostic runtimes are not scaling
benchmarks. No distributed-memory scaling is claimed.

Every attempt gets a new run directory. A flagged result returns a nonzero
collector status, but the batch script continues through all cases. Therefore a
Slurm `FAILED` state can mean diagnostics were found; consult
`logs/collection-JOBID.tsv` and each attempt's `metrics.json`. Reconcile missing
attempts/timeouts/OOM with Slurm accounting. Do not count absence of output as a
successful test. The runner does not automatically launch analysis or other studies.

The launcher disconnects simulation standard input so `srun` cannot consume the
remaining case list. Its optional second argument is a one-based start index in
the frozen launch order. Use it only after checking that earlier cases have
recorded completed attempts (including flagged diagnostics); preserve the original
campaign and record the resumed job ID and launcher revision. For example, passing
`2` runs the remaining 59 cases after the first case has completed. If only the
launcher is repaired, save the corrected script under a new name and record its
checksum; do not overwrite the script pinned by the original campaign hashes.

## Read and plot the results

Keep all attempts, including negative concentrations, solver failures, missed
updates and exceptions. The compact CSV files record per-cell biomass and fluxes,
substrate amounts/minima, exchange balance, occupancy, update counts and order.
Glucose concentration is in **mM (mmol/L)**. The original glucose initial condition
and uptake Km are labelled mM; dFBA converts concentration times voxel volume to
mmol by dividing by `1e15` (one litre in cubic micrometres). Some outer XML variable
tags say `dimensionless`; those annotations are inconsistent with this implemented
concentration convention. No rescaling of the recorded glucose values is needed.
Report raw values and any analysis tolerance explicitly; this workflow does not
clip negatives or silently choose a tolerance.

The glucose figure's legend gives the number of OpenMP **threads** (previously
written as P). Its x-axis is simulation time in minutes. Trajectories use the
`after_cell_step` rows: sampled after diffusion and cell-container updates, before
the driver's simulation clock is advanced. The plotted time is the recorded
iteration timestamp; this sampling detail belongs in the methods rather than the
axis unit. These rows are distinct from snapshots saved before the step. The
minimum is taken across the microenvironment voxels.

After completion, run analysis manually in the required environment:

```bash
salloc -A bsc08 -q gp_debug -t 02:00:00 -n 1 -c 32 -J dfba-analysis
module load hdf5 python/3.12.1
source venv/bin/activate
python benchmarks/voxel_sharing/analyze.py \
  --campaign benchmarks/workspaces/voxel-campaign \
  --output benchmarks/results/voxel_sharing/voxel-campaign --plots
```

The output directory must be new. It contains:

- `tables/coverage.csv`: all expected cases and missing/duplicate attempts.
- `tables/runs.csv`: every observed attempt, flags, measured thread/cell/update
  counts, minima, biomass, wall time and peak process RSS.
- `tables/paired_serial_parallel.csv`: comparisons to the serial run with the
  same order seed and repetition; incompatible orders/workloads, wrong thread
  counts, incomplete and ambiguous attempts are explicitly labelled.
- `tables/substrate_trajectories.csv`: phase-labelled raw trajectories.
- `plots/diagnostics.pdf/.png` and `plots/glucose_by_seed.pdf/.png`: signed glucose
  minima and missing intracellular updates relative to the matched serial run;
  flagged attempts remain visible. Each parallel point uses the same seed and
  repetition as its serial reference, with workload/order compatibility verified.
  In this campaign all serial references performed 80 updates, so the deficit is
  `80 - actual_updates`. Zero means the same update count; a negative value would
  indicate extra updates and is not clipped. Original due/actual scheduler
  counters remain in `tables/runs.csv`; they are not the plotted deficit.
- `data/`: compact raw telemetry, settings, manifests, hardware/resources and logs.
- `analysis.json`: analysis-script and evidence hashes and coverage findings.

Compare serial order dependence, same-seed repeat variation and matched
serial/parallel outcomes separately. A negative concentration in serial execution
cannot by itself identify a parallel race. Missed updates and exchange residuals
help distinguish scheduler and exchange problems; inspect code and controls
before assigning causality. A clean result in a short run cannot prove race
freedom. This unit test does not measure how often cells share voxels in growing
tissue, nor establish that PhysiCell guarantees one cell per voxel.

The uptake-budget fix (voxel substrate shared between the cells drawing on it)
and the concurrency fixes merged in PR #19 (byte-sized intracellular update flags
in `Cell_Container::update_all_cells_intracellular`; per-voxel locks in
`Basic_Agent::simulate_secretion_and_uptake`) address different code paths. Pin the
tested source revision in the manuscript; rerun the same campaign at any
subsequently approved fix for a before/after study. Do not mix revisions in a
paired comparison: serial/parallel pairs always come from the same build.

## Before/after comparison

Prepare and run new campaigns with the unchanged protocols from a new build, analyze
each with `analyze.py`, then compare the exported reports:

```bash
python benchmarks/voxel_sharing/compare_builds.py \
  --before benchmarks/results/voxel_sharing/voxel-20261026 benchmarks/results/voxel_sharing/mesh-20261026 \
  --after  benchmarks/results/voxel_sharing/voxel-NEW benchmarks/results/voxel_sharing/mesh-NEW \
  --labels pre-fix post-fix --output benchmarks/results/voxel_sharing/before-after-NEW --plots
```

Within each build, every parallel run is still compared with its matched serial
run (same mesh, seed and repetition). The script reports missing updates, the
glucose exchange-balance check, negative glucose, and the largest differences in
the glucose-minimum trajectory and in final per-cell dry mass. It also compares
the serial runs across builds; with one thread neither fix changes the executed
code path, so differing serial results would point to another source change. No
tolerance is applied; zero means bitwise-equal recorded values.

## Checks

```bash
python -m unittest discover -s benchmarks/performance -p test_workflow.py -v
python -m unittest discover -s benchmarks/voxel_sharing -p test_campaign.py -v
```

These tests check the matrix, original physical settings/placement, and comparison
rules. They submit no jobs and do not analyze real simulation results. Review the
report before committing it to GitHub; keep bulky binary/snapshot bundles in the
ignored workspace or an external data archive.
