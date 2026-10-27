# Eight-cell shared-voxel results

Analysis of the 60-case campaign defined in
[`../../../voxel_sharing/README.md`](../../../voxel_sharing/README.md).
All cases completed and are retained, including diagnostic flags. No cases are
missing or duplicated. All 45 parallel runs passed the analysis checks for pairing
with a serial run of the same order seed and repetition (matching workload,
binary and actual initial permutation).

## Figures and tables

- [Diagnostic overview (PDF)](plots/diagnostics.pdf), [PNG](plots/diagnostics.png).
- [Glucose trajectories by seed (PDF)](plots/glucose_by_seed.pdf), [PNG](plots/glucose_by_seed.png).
- [All runs](tables/runs.csv), [coverage](tables/coverage.csv),
  [paired serial/parallel comparisons](tables/paired_serial_parallel.csv),
  [phase-labelled substrate trajectories](tables/substrate_trajectories.csv).

Each color in the diagnostic overview represents one initialization-order seed.
Small horizontal offsets distinguish repetitions. Curves of the same thread count
share a color in the seed panels; overlapping curves can hide individual runs.
All measurements remain accessible in the tables and compact raw evidence.
The legend title **Threads** denotes the number of OpenMP threads (previously P).
The time axis is in minutes. Glucose trajectories use `after_cell_step` samples:
recorded after diffusion and the cell-container update, before the clock advances,
at the iteration timestamp stored in the CSV. This is a sampling convention, not
part of the time unit. Values are minima across the microenvironment voxels.

## Observations

| Threads | Runs | Runs with negative concentrations | Actual intracellular updates per run | Lowest glucose concentration (mM) |
|---|---:|---:|---:|---:|
| 1 | 15 | 15 | 80 | -0.00000378031914109 |
| 2 | 15 | 14 | 50–80 | -0.330011340957 |
| 4 | 15 | 15 | 42–67 | -0.412513231117 |
| 8 | 15 | 15 | 29–73 | -0.598142483976 |

Glucose concentration is **mM = mmol/L**, verified against the unit-test initial
condition and Km, and the dFBA uptake/export conversions in
`addons/dFBA/src/dfba_intracellular.cpp`: concentration times voxel volume divided
by `1e15` gives mmol. The outer variable tag's `dimensionless` annotation is
misleading metadata; the implemented concentration convention is mM. No numerical
values or time coordinates were changed when clarifying the labels.
The [unit audit](glucose_unit_audit.json) includes both `glucose` and `D-Glucose`
sample fields and records the original XML annotations.
The serial minimum was identical across all 15 serial runs. The parallel runs
showed larger variation and, in some runs, much larger negative values.

The update-count mismatch flag occurred in 0/15, 10/15, 15/15 and 15/15 runs at
1, 2, 4 and 8 threads respectively. The overview's right panel now displays
**missing intracellular updates relative to serial = 80 - actual updates**.
Each parallel run is compared with its serial counterpart using the same order
seed and repetition; all serial runs performed 80 updates. A run with 58 updates
therefore shows 22 missing updates. The observed deficits span 0, 0–30, 13–38 and
7–51 at 1, 2, 4 and 8 threads respectively.

This replaces the previous `due - actual` display, which could understate the
overall reduction: after a missed update, subsequent steps may no longer satisfy
scheduler eligibility. Original due/actual counters remain in `tables/runs.csv`.
The paired comparison table retains `actual_parallel - actual_serial`; the plot
uses the opposite sign to express missing updates. These counts should not be
interpreted as proof that every numerical difference has a single cause.

Negative concentrations in serial runs show that negativity alone cannot establish
a parallel race. The parallel update deficits and repeat-dependent trajectories
are separate findings for developer investigation. No tolerance, clipping,
outlier removal or causal correction was applied. This short stress test does not
establish race freedom or predict voxel sharing in a growing tissue.

## Provenance and reproduction

The simulations used source `8ae6a1d722718b9e6a6ffcbc00f19c270281ecda` with the
common benchmark harness. The first run was collected by Slurm job `48048383`;
the remaining 59 by `48049803` after a launcher stdin-handling correction. The
simulation binary and input settings were unchanged. These were separate node
allocations; per-run hardware records are included. These short diagnostic times
are not performance-scaling measurements.

The analysis ran successfully in allocation `48051632` using the existing project
environment: Python 3.12.1, Matplotlib 3.10.8 and NumPy 2.4.4. See
`analysis_environment.json` and `environment.txt`. The environment was activated
without installing or upgrading packages. Both figures were visually inspected.
All copied evidence checksums in `analysis.json` were verified.
Figure refreshes are recorded separately in `analysis.json`; the original
analysis-script identity is retained. Both PDFs
and PNGs were regenerated and inspected, with table/evidence checksums unchanged.

`data/` contains the compact raw evidence, including failed-condition flags,
per-cell updates, permutations, exchange balances, settings, hardware and logs.
`campaign.json`, `protocol.json`, `build.json` and `analysis.json` record source,
input, binary and analysis identities. Large MultiCellDS snapshots remain in the
original campaign workspace. The original results were not overwritten.

To reproduce with the original campaign available, activate the documented
environment inside a compute allocation and run:

```bash
python benchmarks/voxel_sharing/analyze.py \
  --campaign benchmarks/workspaces/voxel-20261026 \
  --output /path/to/a/new/report --plots
```
