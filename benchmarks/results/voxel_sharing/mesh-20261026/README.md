# Separated-cell mesh analysis

All **240 simulations** completed and were analyzed. Reducing voxel sharing
eliminated the measured glucose exchange-balance mismatches in the one-cell-per-voxel
cases, but **did not eliminate missing intracellular updates or negative glucose**.
This experiment does not support claiming that small voxels alone make parallel
execution safe.

## Figures and data

- [Mesh comparison (PNG)](plots/mesh_comparison.png), [PDF](plots/mesh_comparison.pdf):
  missing updates and minimum-glucose differences relative to the matched serial run.
- Glucose trajectories by initialization seed:
  [8 cells/voxel](plots/mesh16/glucose_by_seed.png),
  [4 cells/voxel](plots/mesh8/glucose_by_seed.png),
  [2 cells/voxel](plots/mesh4/glucose_by_seed.png),
  [1 cell/voxel](plots/mesh2/glucose_by_seed.png).
- Diagnostics by mesh:
  [16 µm](plots/mesh16/diagnostics.png), [8 µm](plots/mesh8/diagnostics.png),
  [4 µm](plots/mesh4/diagnostics.png), [2 µm](plots/mesh2/diagnostics.png).
  Every figure also has a PDF in the same directory.
- [Mesh/thread summary](tables/mesh_thread_summary.csv),
  [per-run diagnostics](tables/mesh_run_diagnostics.csv),
  [same-seed repeat ranges](tables/same_seed_repeats.csv),
  [paired comparisons](tables/paired_serial_parallel.csv),
  [substrate trajectories](tables/substrate_trajectories.csv),
  [coverage](tables/coverage.csv).
- [Validation](mesh_validation.json), [descriptive checks](descriptive_checks.json),
  [compact raw evidence](data/), [build provenance](build.json).

The legend denotes OpenMP thread counts. Glucose is in **mM**; the unit audit is
in the [original report](../voxel-20261026/README.md). Trajectories show the minimum
over all voxels, sampled after the cell step at the recorded iteration time.
The time unit is minutes. Missing updates means **80 minus actual updates**,
using the serial run on the same mesh, with the same seed and repetition.
Overlapping curves and points can conceal individual runs; the tables retain all
observations. These short, instrumented runs are correctness diagnostics, not
performance-scaling measurements.

## Experimental controls

The [protocol](../../../voxel_sharing/MESH_STUDY.md) uses the existing E. coli
eight-cell unit-test physiology. Eight distinct, fixed centers occupy a fixed
16 × 16 × 16 µm domain. Only the voxel edge, thread count and initial update-order
permutation vary. All runs retain eight cells and allow metabolic biomass growth.
Each mesh has 1/2/4/8 threads × five order seeds (11/23/37/51/71) × three repeats:
15 serial and 45 parallel runs per mesh. The order changes once at initialization,
never deliberately within a run. Recorded positions, occupancy, thread counts and
permutations match the protocol; all 180 serial/parallel pairs are valid.

Diffusion and intracellular timesteps are both 0.01 min. The nominal maximum time
is 0.1 min; the inherited loop also executes at 0.1 min, so the recorded final time
is 0.11 min. Every serial run performs 80 intracellular updates. Initial glucose
is 0.165 mM, with **glucose diffusion disabled** and no glucose boundary supply.
The unit test retains its artificial oxygen supply of 1e8 mM and zero
ATPM maintenance lower bound. This is a numerical stress test, not physiological
medium validation or a tissue-packing model.

## Observations

The table pools the 2/4/8-thread runs within each mesh. Each parallel column has
45 runs; each serial minimum summarizes 15 controls.

| Voxel edge (µm) | Cells per occupied voxel | Parallel runs missing updates | Parallel runs failing glucose exchange balance | Serial minimum glucose (mM) | Parallel minimum glucose (mM) |
|---:|---:|---:|---:|---:|---:|
| 16 | 8 | 36/45 | 33/45 | 0.157946 | 0.157942 |
| 8 | 4 | 38/45 | 32/45 | 0.136979 | 0.136796 |
| 4 | 2 | 37/45 | 34/45 | 0.057888 | 0.051940 |
| 2 | 1 | 36/45 | 0/45 | −0.00000118834 | −0.287238 |

All 60 serial runs pass the glucose exchange-balance check and perform all 80
updates. Across the 180 parallel runs, 147 miss updates and 99 fail the glucose
exchange-balance check. Missing updates remain frequent at every occupancy:
there is no observed monotonic approach to serial update counts as voxels shrink.
The largest deficit is 60 of 80 updates. A shorter runtime from such a run would
not establish a speedup for equivalent computational work.

All 60 runs on the finest mesh have negative glucose, including the serial
controls. The nine parallel runs on that mesh with no missing updates have the
same minimum as serial, −1.1883362427411726e-6 mM. Other parallel runs reach much
larger negative values. This association supports investigating stale exchange
rates after skipped updates, but does not establish causality.

There are **zero recorded solver failures and zero nonoptimal primary statuses
among the recorded per-cell updates**. Optimal LP solutions therefore do not
establish correct simulation scheduling, substrate accounting or nonnegativity.
The collector labels 69 runs completed and 171 completed with diagnostic flags;
all are retained. The additional exchange-balance checks are reported separately
and do not overwrite the collector's original labels.

Within each mesh/thread/seed group, three repeats share the same initialization.
None of the 20 serial groups varies in update count, minimum glucose or final
biomass. At least one of these quantities varies in **57/60 parallel groups**.
Parallel variation is therefore not explained solely by changing the initial
order seed. These are descriptive counts, not independent-sample significance
tests or estimates of a universal race probability.

The glucose exchange balance compares the observed change in total extracellular
glucose during the cell-exchange step with the sum of recorded cell export rates
times the diffusion timestep. Amounts are in mM·µm³. For each recorded step the
allowed residual is:

```text
1e-10 × max(1, |before_amount|, |after_amount|)
  + 1e-8 × max(|observed_delta|, |expected_delta|)
```

This is the floating-point accounting check already used by the
[growth-condition analysis](../../growth_conditions/growth-20261026/README.md),
not a biological accuracy tolerance. All checked records use net export only.
Passing this check means the requested exchange was accounted for; it does not
mean that the requested uptake was feasible or that concentrations stayed positive.

## Hypotheses to discuss with the developers

1. **A scheduler race can lose updates even with separate voxels.**
   `core/PhysiCell_cell_container.cpp`, in `update_all_cells_intracellular`, stores
   readiness in `std::vector<bool>` and writes its entries in parallel. Packed
   bits can share storage between cells. This is a concrete candidate for the
   observed deficits. A separately identified build using independently writable
   readiness entries should be compared with the current build under identical
   settings. This analysis does not include that intervention or a race-detector run.
2. **Shared-voxel exchange has an additional concurrency problem.**
   Exchange-balance mismatches occur with shared voxels and disappear in the
   measured one-cell-per-voxel cases. Concurrent updates to the same BioFVM density
   vector are a candidate. Isolate exchange synchronization from the scheduler
   change so that their effects can be distinguished. A passing balance in these
   runs is not a general proof of race freedom.
3. **Small local nutrient budgets expose uptake-limit/timing errors.**
   The small serial undershoot needs separate investigation. Check the substrate
   budget used to set uptake bounds against the mass, interval and rate actually
   used for exchange, including growth and numerical tolerances. Skipped updates
   may additionally leave uptake rates stale in parallel. Do not infer a specific
   cause, change production timesteps or hide undershoots by clipping based on
   these data alone.

Refining the mesh changes local substrate amount as well as occupancy. Glucose
cannot diffuse from unoccupied voxels in this test. The initial glucose amount in
an occupied voxel divided by its cell count falls from 84.48 to 21.12 to 5.28 to
1.32 mM·µm³ across the four meshes: **64 times less locally available glucose per
cell** on the finest mesh, despite identical whole-domain glucose amount.
Therefore cross-mesh concentration changes are not a pure concurrency experiment
or a numerical convergence proof. Each parallel run must
be assessed against its own mesh's serial control. The eight separated centers
also differ from the original coincident-center study; keep the studies distinct.

Before the full performance campaign, use focused controls to test these
hypotheses, then require complete updates, acceptable accounting and agreed
nonnegativity/accuracy criteria on representative workloads. The validated
model-specific media remain useful for serial pilots, but do not resolve the
parallel findings. No new simulations or full benchmark were launched for this
analysis.

## Provenance, validation and reproduction

Simulation job **48052924** used source
`0e66312f5eea4914d5f7634022b4e6f59e0ae04e`, with the benchmark harness and unchanged
production scheduling/exchange code. The approved development base and PhysiCell
upstream revision are recorded in `build.json`. The build used GCC 11.5.0,
`-O3 -march=native -fomit-frame-pointer -mfpmath=both -fopenmp -m64 -std=c++11`
and `-DPHYSICELL_BENCHMARK`; the native target was Sapphire Rapids. MN5 hardware
records accompany every run. Primary solves use Clp dual simplex after initial
solve, with primal/dual tolerances 1e-7 and one BLAS thread. This campaign uses
standard dFBA, not pFBA. Binary, dependency and input identities are archived.

Analysis allocation **48055063** generated the tables and PNG/PDF figures.
Allocation **48055149** checked all 3,840 archived evidence checksums, the 240-run
coverage, geometry, occupancy, orders, thread counts, timesteps and matched pairs;
all four existing voxel-campaign tests passed
([validation log](analysis_validation.txt)). Allocation **48055204** reproduced
the three supplemental tables from the archived report byte for byte and recorded
the [analysis environment](analysis_environment.json). The overview and finest-mesh
seed plot were visually inspected. No production C++ changes were made or tested.

Within an MN5 compute allocation, load `hdf5` and `python/3.12.1`, then activate
the repository's `venv`. With the original campaign available, regenerate a
complete report in a **new** directory:

```bash
python benchmarks/voxel_sharing/analyze.py \
  --campaign benchmarks/workspaces/mesh-20261026 \
  --output /path/to/new-mesh-report --plots
python benchmarks/voxel_sharing/summarize_mesh.py \
  --report /path/to/new-mesh-report
```

Readers with only the published compact report can verify its evidence and
recompute the three supplemental tables without simulation outputs or binaries:

```bash
python benchmarks/voxel_sharing/summarize_mesh.py \
  --report benchmarks/results/voxel_sharing/mesh-20261026 \
  --output /path/to/new-mesh-summary
```

The output directory must not already exist. The original report is preserved.
Full snapshots and simulation binaries remain in the campaign workspace; the
compact telemetry, settings, logs, hardware and manifests used here are in `data/`.
