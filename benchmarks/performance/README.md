# Supplementary performance and numerical-sensitivity benchmarks

This workflow implements the agreed study (developed on PhysiCelldFBA's private
`integration/manuscript-benchmarks` branch; see [`../../PROVENANCE.md`](../../PROVENANCE.md)).
The active shared-voxel experiment is the focused 60-run protocol in
[`../voxel_sharing/README.md`](../voxel_sharing/README.md), using the existing
eight-cell test's settings and duration. It supersedes the earlier incremental
1/2/4/8-cell matrix. The other scientific phases still require their pilot decisions.
It does not submit jobs. Final MN5 runs wait for approved PRs, passing CI, a clean
source revision, validated inputs, pilot-selected durations/criteria, and the
agreed submission authorization. Do not merge this integration branch wholesale
instead of reviewing the individual code PRs.

Before preparing further growth or performance runs, use the
[model-specific medium and nutrient-supply review](model_conditions/README.md).
It inventories the sample conditions and reports 36 static LP checks. Its
dynamic follow-up is the serial growth-validation workflow described below;
existing conservation and shared-voxel settings remain deliberate stress controls.

### Model-specific growth validation

`growth_profiles.json` specifies the source template, exact SBML and nutrient
supply mode for each candidate. `prepare_growth.py` stages 23 serial controls
(10 simulated minutes): single cells at intracellular intervals 0.01/0.1/1 min,
16-cell fixed-volume controls at 0.01/1 min, a closed-medium iML1515 reference,
and a native-medium cancer pFBA control. Diffusion dt is 0.01 min throughout.
This is input validation, not the final timestep or performance study.

`diagnostic_endpoints` output keeps telemetry at every diffusion/intracellular
update while limiting full spatial snapshots to the beginning/end of the run.
The existing `intracellular` output policy is unchanged for the unit tests.
The sample loop can save another snapshot at time zero and advances to 10.01
minutes for a requested 10-minute duration; analyses retain the actual times.

From a clean committed checkout with the isolated unit/cancer builds available:

```bash
sbatch --output=/absolute/growth-validation-%j.log \
  benchmarks/performance/run_growth.sbatch \
  /absolute/new-campaign /absolute/build-root
```

The explicit submission reserves one node with 32 CPUs for at most an hour.
Simulations each use one thread and run sequentially. The script activates the
Python environment, requires workflow tests to pass, verifies staged checksums,
and continues after flagged diagnostics. A nonzero Slurm exit can therefore
mean completed simulations with scientific flags; inspect all `metrics.json`.
After completion, in the documented analysis allocation/environment:

```bash
python benchmarks/performance/analyze_growth.py /absolute/campaign/runs \
  --output /absolute/new-analysis
```

This produces the summary table, growth plots, cell-local endpoint concentrations
read through `pctk`, and compressed telemetry for sharing. The analyzer can also
read its archived `data/` folder without the original large spatial snapshots.
It does not certify long-run feeding, numerical accuracy or parallel safety.

The [completed 23-control analysis](../results/growth_conditions/growth-20261026/README.md)
supports the current performance-only medium profiles at the tested 0.01-minute
timesteps. Ten controls pass all checks. Some runs marked `completed` by the
collector fail the subsequent exchange ledger check: use `short_control_pass`
from the analysis table, not process exit or solver feasibility alone. The
full target-size/extra-field/parallel workloads remain pending validation.

## Agreed experiments

| Experiment | Design |
|---|---|
| Timestep | Standard FBA; E. coli mass conversion and single-cell cancer; intracellular/diffusion ratios 1, 2, 10, 100; diffusion dt fixed |
| Cancer reference | Serial single cell; both timesteps equal and refined together by factors 1, 1/2, 1/4; inspect convergence, do not assume ground truth |
| Cancer application | Selected timestep settings from the single-cell pilot, normal multicellular behavior |
| FBA versus pFBA | Cancer only, after timestep selection; single cell then application; fraction of optimum 1; expand to pFBA timestep sensitivity only if justified |
| Shared voxel | Standard FBA; 8 cells, 1/2/4/8 threads, 5 initialization-order seeds, 3 same-seed repetitions = 60 cases; use the dedicated voxel_sharing workflow |
| Voxel controls | Optional mixed-uptake example and nutrient-rich control; outside the focused 60-run submission |
| Controlled performance | 100/1,000/10,000 cells; domain grows at fixed voxel size and density; fixed positions, population and volumes |
| Baselines | Upstream PhysiCell, PhysiCelldFBA without metabolism, PhysiCelldFBA with metabolism; identical physical workload and output |
| Fields | Retain all required coupled fields; target 4/8/16/32 total, adding uncoupled transport fields where possible |
| Networks | E. coli core, trimmed MCF7 core, iML1515; report actual SBML and LP sizes, not reaction count alone |
| Threads | 1/2/4/8/16/28/56/112, one exclusive GPP node; 3 timing repetitions initially |

Use separate sweeps, not the full Cartesian product. Cancer requires more fields
than E. coli: impossible field counts are raised to the required minimum and
identical resulting cases are deduplicated. Cell/thread/model sweeps use a common
field count at least as large as every model's requirement. Confirm actual counts
in `input-record.json` and the run manifest. Extra fields use diffusion coefficient
1000 micron²/min, no decay, and initial concentration `1 + 0.1 sin(x)` (x in microns).

Shared-voxel runs fix positions and population but allow metabolic biomass growth.
One Fisher–Yates permutation of cell traversal order is applied at initialization
using its own mt19937 RNG and seed. Cell IDs remain stable, indices are updated,
and no permutation occurs at subsequent timesteps. `benchmark_order.csv` records
the exact order; its SHA-256 is included in collected telemetry. This does not
fix or determine parallel execution order. Repeated identical-seed runs assess
thread scheduling variability. Known shared-voxel and packed-scheduler races are
not repaired by this workflow, and those results are diagnostics, not proof of
safe scaling. Verify matched serial/parallel update counts and occupancy.

Durations are deliberately not fixed in `study.json`. Use the pilot to choose a
common physical duration per comparison: substrate depletion/biomass plateau for
mass conversion, appreciable competition for voxel sharing, meaningful dynamics
for cancer, and enough updates at the largest intracellular interval. Retain
residual substrate in yield calculations. Pilot error/runtime plots inform an
accuracy criterion, which must be frozen before the final campaign.

## Code and controls

Ordinary builds do not define `PHYSICELL_BENCHMARK`: instrumentation and control
hooks compile out. Benchmark builds use `driver.cpp`, `runtime.h`, and
`telemetry.h`; the production sample mains/custom modules and root active project
are not overwritten. Only isolated build snapshots select a project and replace
its main. No production scheduling, timestep equality constraint, exchange
coefficient correction, solver algorithm change or race fix is introduced.

The benchmark driver retains the sample's diffusion -> secretion/uptake ->
intracellular ordering and end condition. Standard sample SVG/console output is
omitted; regular MultiCellDS output is supported. These runs must be described as
benchmark-driver runs, not byte-identical runs of an unmodified application main.
Cancer pre-diffusion initialization is retained and expressed in physical minutes
(the template uses 300 steps at 0.01 min = 3 min), so refinement preserves its
duration. The benchmark initial snapshot follows this preparation. Controlled
single-cell cancer uses the first application CSV position; other controlled
single/shared cases use the central voxel center. All placement is explicit in
the input record/XML. Pre-equilibration time is included in initialization.

The explicit XML `<benchmark enabled="true" ...>` node selects layout and controls.
`single`, `shared`, and `lattice` create controlled cells from the configured cell
definitions. `application` calls the sample's normal tissue setup. The lattice
uses factorized rectangular grid dimensions with exactly one voxel per cell;
record the resulting aspect ratios. For mixed cells, definitions alternate.
Fixed population suppresses division/removal/death hooks; generated controlled
inputs also disable transformation/interaction rates. Fixed volumes disable the
volume callback and dFBA growth-to-volume application; FBA and exchange still run.
The post-update callback is removed for cells without intracellular metabolism.

`upstream-hooks.patch` contains only the common benchmark instrumentation/control
hooks. Apply it to the pinned upstream baseline, without any dFBA implementation.
Archive that patch and benchmark driver/header hashes with baseline provenance.
A baseline is therefore upstream PhysiCell with the disclosed common harness.

`physicelldfba-hooks.patch` adds the same core hooks plus the dFBA-engine hooks
(solver timing/counters, fixed-volume control, update records) to PhysiCelldFBA.
`build.sh` applies it to an unhooked PhysiCelldFBA checkout such as the pinned
submodule. All hooks compile out without `-DPHYSICELL_BENCHMARK`.

## Manual preparation

Python commands below are manual and use the project's required environment:

```bash
salloc -A bsc08 -q gp_debug -t 02:00:00 -n 1 -c 32 -J dfba
module load hdf5
module load python/3.12.1
source /gpfs/scratch/bsc08/bsc219297/PhysiCelldFBA/venv/bin/activate
python benchmarks/performance/prepare.py plan --phase timestep --output /path/to/new-plan.jsonl
```

Phases: `timestep`, `refinement`, `voxel`, `voxel_mixed`, `voxel_rich`, `pilot`,
`main`, `cancer_application`, `pfba`, `pfba_application`. The last three require
`pfba.selected_dt_minutes` in the study file, chosen after inspecting timestep
results. Generate distinct plans/case IDs when testing several selected application
timesteps. Standard performance cases exclude pFBA. The separate cancer comparison
can be repeated with `output_policy=minimal` for unbiased runtime measurement.

Select a JSONL record into `case.json`. Set the intended cells_requested for
application cases from the actual CSV. Generate inputs with an explicit duration:

```bash
python benchmarks/performance/inputs.py --case /path/to/case.json \
  --duration 240 --output /path/to/new-inputs
# Duration above is illustrative, not a prescribed duration for every phase.
# For a timing counterpart, use a distinct case ID and set output_policy to minimal.
```

This preserves voxel spacing; enlarges only controlled lattice domains; bundles
SBML and application cell CSV inputs; sets explicit timestep/seed/output choices;
and validates mapped reaction IDs against SBML. iML1515 uses its SBML objective,
not the core-model biomass identifier. Review its bounds and nutrient conditions
in the pilot. Inheritance and active external rules require explicit preparation
rather than silent guessing. No existing directory is overwritten.

Build each required project in a fresh directory:

```bash
bash benchmarks/performance/build.sh PhysiCelldFBA /path/to/new-build dfba_unit_test 4
bash benchmarks/performance/build.sh PhysiCelldFBA /path/to/new-cancer-build cancer_core_metabolism 4
# For the upstream baseline, use a checkout of the pinned upstream commit:
bash benchmarks/performance/build.sh /path/to/upstream /path/to/new-upstream-build template 4
```

The source snapshot includes tracked files and records tracked deviations in
`source.patch`. Add new benchmark sources to Git before using this builder.
Dependencies are reused from the source checkout (or from `DFBA_EXT`, an installed
`addons/dFBA/ext`) via a symlink, so retain that
checkout through compilation. Build logs contain actual compile/link flags.
Archive compiler version, dependency versions, solver settings, binary hash,
source commit, patches, and benchmark harness hashes in `build.json` using
`build.example.json`. Publication runs require a clean source commit; local
validation builds may contain explicitly recorded patches. The baseline template
must be compiled on the same architecture with comparable optimization flags.

After reviewing an input bundle, record `validation_record`, resolve applicable
`open_decisions` and set case status to `ready`. For a known-race diagnostic,
readiness means the experiment is correctly constructed and its limitation is
explicitly recorded, not that the race is fixed.

```bash
python benchmarks/performance/prepare.py stage --case /path/to/case.json \
  --inputs /path/to/new-inputs --binary /path/to/new-build/dfba-unit-test \
  --build /path/to/build.json --output /path/to/new-bundle
```

Use the actual executable name printed by the build for each project. Stage
requires matching case/XML settings and build checksum. It changes only requested
OpenMP threads and output folder, preserving the finalized numerical settings.

## Measurements and output

Diagnostic snapshots follow intracellular dt. Compact per-cell rows are recorded
immediately after actual intracellular outputs, even though regular snapshots
occur before the current step. Times follow the engine's step labels; phase names
identify sampling order. These are distinct observations, not simultaneous states.

- `benchmark_cells.csv`: cell ID, post-update biomass/volume, growth and solver statuses.
- `benchmark_fluxes.csv`: post-update net export rates, in BioFVM concentration·um³/min units.
- `benchmark_population.csv`: initial/final and phase-labelled population biomass/occupancy.
- `benchmark_substrates.csv`: domain-integrated concentration·um³ and minimum concentration.
- `benchmark_exchange_balance.csv`: before/after exchange amounts and expected rate × diffusion dt.
- `benchmark_order.csv`, `benchmark_update_counts.csv`: permutation and actual per-cell work.
- `benchmark_metrics.json`: counters, phase timings, LP sizes, flags and sampling policy.

The exchange ledger brackets secretion/uptake **after diffusion**, isolating its
amount change from transport/boundary effects. Its residual is directly meaningful
when `net_export_only=1`; nonzero implicit secretion/uptake coefficients require
additional accounting. For mM fields, divide concentration·um³ by 1e15 for mmol.
Do not interpret differently labelled substrate units without checking the model.

Measured `model_optimization_calls` differs from `optimization_calls` (post-initialization
LP invocations, including retries). Initialization solves are separate. Stage-two
call counts include retries; `stage_two_retries` is a subset, not an additional
summand. Solver time is summed thread time, not elapsed wall time. Phase timings
are elapsed scopes; `cell_container_seconds` includes intracellular, exchange,
phenotype/mechanics and some diagnostic work. Do not sum nested scopes. LP size
metrics are maxima, iterations and status counts are measured per invocation.

Performance runs save initial/final snapshots and compact end-of-run summaries.
Concentration/occupancy scans are initial/final only in minimal mode; they cannot
exclude transient problems. Validate representative cases with dense diagnostics
before using minimal measurements. Diagnostic scans/timing/logging have overhead;
record `validation_seconds` and assess instrumentation overhead in the pilot.
Do not compare dense-output and minimal-output wall times as if output were equal.

Negative/nonfinite concentrations, primary failures, pFBA fallbacks, overdue or
mismatched updates, and broken control invariants are retained and flagged, never
clipped. Completed flagged runs remain diagnostic findings and are excluded from
successful performance summaries. An exit or kill before telemetry is written is
retained as failed/incomplete by the collector. Inspect raw logs and Slurm accounting.

## MN5 execution and analysis

After prerequisites and submission authorization are satisfied:

```bash
sbatch benchmarks/performance/run_mn5.sbatch /absolute/bundle /absolute/results
```

The template reserves one exclusive GPP node and 112 physical slots for every
case, with fixed core/spread placement and single-thread BLAS.
The collector fixes `DFBA_PFBA_DUAL=0` (the feature's default primal second stage)
and records it, preventing an inherited shell override from changing a comparison.
Confirm account, partition, QoS, memory and wall limit using the pilot. Randomize the final launch
order, recording it. Reserve identical resources for serial/parallel comparisons.
The template is single-node OpenMP, not distributed-memory scaling.

`run_case.py` verifies hashes and records hardware, affinity, modules, Slurm
metadata, command, stdout/stderr and GNU-time process peak RSS/wall time. Each
attempt has a fresh directory. Reconcile timeouts/OOM with `sacct`; process RSS is
not whole-node memory. Initial/final snapshots plus exit zero establish completion,
not numerical validity. Requested and observed thread counts must agree.

Run analysis manually in the environment above:

```bash
python benchmarks/performance/summarize.py runs/performance output/performance \
  --output /path/to/new-performance-report --plots
python benchmarks/performance/analyze_outcomes.py runs/diagnostics \
  --output /path/to/new-outcome-report --plots
```

The outcome tool reads compact telemetry rather than MultiCellDS snapshots. Use
`pctk` for additional snapshot variables; no `pcdl` dependency is introduced.
Optional `--verified-yield Y --yield-record /path/to/evidence` enables the E. coli
biomass prediction from consumed glucose (not assumed complete depletion).
Y must be independently established for the exact SBML/constraints; the old
notebook's 0.5197 is not silently assumed. Optional `--reference-run` explicitly
selects a numerical reference; compatible workload metadata is checked and curves
are interpolated on shared physical times without extrapolation. Review all other
input differences before interpreting error. No accuracy threshold is invented.
Alternatively, `--paired-run /path/to/fba-run` compares cancer FBA/pFBA with only
the secondary objective differing. Binary and scientific input identities are
checked; incompatible runs are labelled rather than pooled. Biomass and domain
substrate trajectory differences and paired wall-time ratios are exported.
Use `randomize.py --seed SEED --output new-launch-order.json BUNDLE...` to record
the final randomized launch order without submitting any jobs.

pFBA comparison must examine trajectories, exchange fluxes and secondary failures,
not only final biomass. Its secondary objective excludes reactions with at most
one metabolite in this implementation. Align that objective with an independent
reference before using the existing COBRApy/Gurobi helper; it currently invokes
the reference solver's default objective, which is not automatically equivalent.

## Validation and release gate

Before production, validate generated plans/inputs/staging with fixtures; compile
ordinary and instrumented builds; test opt-in controls, order reproducibility,
per-cell counts, pFBA counters, the two baselines, incomplete/flagged collection,
and comparison grouping. Python scripts are not automatically executed. Static
syntax checks alone do not establish workflow correctness. Tiny C++ runs are
implementation checks, not the scientific pilot. Freeze pilot-selected durations,
accuracy criteria, final source/binary/input hashes and randomized run order before
launching publication runs. No Slurm submission is performed by preparation tools.

The standard-library workflow tests are manual in the Python environment above:
`python -m unittest discover -s benchmarks/performance -p test_workflow.py`.
The counter-isolation test can be built with
`g++ -std=c++11 -fopenmp benchmarks/performance/test_telemetry.cpp -o /path/to/new-test`
and run directly; it performs no simulation. Tests should cover a feasible cancer
case after pre-equilibration as well as a deliberately infeasible case, so a failed
primary solve cannot be misreported as a successful pFBA timing measurement.
