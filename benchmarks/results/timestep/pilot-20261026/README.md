# Serial timestep pilot: results and cancer infeasibility diagnosis

All 11 runs from job **48052925** completed with simulation exit code zero and
final snapshots. Nine had no recorded diagnostic flags; two ratio-100 runs were
flagged. The launcher therefore reported a failed Slurm job, without missing runs.
These are provisional ten-minute pilots, not final accuracy or scaling results.

## Analysis and figures

- [Timestep outcomes: PNG](plots/timestep_outcomes.png), [PDF](plots/timestep_outcomes.pdf).
- [Cancer reference refinement: PNG](plots/cancer_refinement.png), [PDF](plots/cancer_refinement.pdf).
- [Outcomes and resources](tables/outcomes.csv), [plotted trajectories](tables/trajectories.csv),
  [per-update solver statuses](tables/intracellular_updates.csv).
- [Cancer LP diagnosis](diagnosis/README.md), including the exported failed LP and counterfactual checks.

Ratio means `intracellular_dt / diffusion_dt`; diffusion dt is 0.01 minutes for
the ratio sweep. Refinement changes both intervals together. All runs use one
thread and standard FBA. Positions and population are fixed, biomass can grow.
The cancer model retains three minutes of pre-equilibration before the pilot.

| Model | Ratio | Intracellular updates | Biomass change (%) | Recorded issue |
|---|---:|---:|---:|---|
| E. coli | 1 | 1000 | 12.97218 | None |
| E. coli | 2 | 500 | 12.97168 | None |
| E. coli | 10 | 100 | 12.96687 | None |
| E. coli | 100 | 10 | 4.56065 | Negative glucose, minimum -1.11276 mM |
| Cancer | 1 | 1000 | 0.22777 | None |
| Cancer | 2 | 500 | 0.22772 | None |
| Cancer | 10 | 100 | 0.22738 | None |
| Cancer | 100 | 10 | 0 | All 10 primary LPs infeasible |

Cancer refinement produced biomass changes of 0.22777%, 0.22779% and 0.22780%
at equal dt values of 0.01, 0.005 and 0.0025 minutes. This is a short, weak-growth
pilot, so close curves do not establish accuracy for longer cancer applications.
The ratio-one cancer run and the coarsest refinement have identical final biomass.

The E. coli runs with ratios 1, 2 and 10 have similar biomass growth but consume
different amounts of glucose: about 1.17%, 2.33% and 11.56% of initial domain
glucose, respectively. Biomass alone is therefore insufficient to select dt.
Exchange-ledger residuals are also reported and require developer review before
interpreting unequal-timestep differences as ordinary numerical convergence.
No production timestep or exchange code was changed by this analysis.

The cancer global minimum glucose stays zero because it includes glucose-free
parts of the domain; it does not mean the cell has zero local glucose. Mean glucose
is also plotted. The first failed LP's cell-local glucose was 0.5 mM.
Glucose is in mM, including the cancer field named `D-Glucose`.

## Why the cancer ratio-100 run is infeasible

At intracellular dt = 1 minute, the current uptake cap limits oxygen according to
the oxygen initially present in the cell's voxel over that whole update window.
At the first solve, voxel volume is 3375 µm³, oxygen is 0.5 mM, and dry mass is
778.128 pg. The kinetic oxygen uptake limit is 0.5 mmol/gDW/h, but the voxel budget
reduces it to **0.13011998 mmol/gDW/h**.

With those bounds, the maximum attainable ATP-maintenance flux is
**0.83241808 mmol/gDW/h**, below the model's mandatory **1.07 mmol/gDW/h**.
A fresh primal solve is also infeasible. Restoring only the oxygen uptake bound
to its kinetic value makes the exported LP feasible while retaining the ATP
requirement. These counterfactual solves diagnose the failure; they do not modify
or replace any campaign result.

The first failure occurs at minute 1, followed by failures at minutes 2–10. The
implementation sets growth and fluxes to zero on infeasibility. Fixed-population
benchmark controls retain the cell; this is not evidence of a physiological
zero-growth steady state or a parallel race. The cap uses the local substrate
budget; it does not credit future diffusion replenishment over the long window.

## Reproduction and limits

Activate the project Python environment inside a compute allocation and run:

```bash
python benchmarks/performance/analyze_pilots.py \
  --campaign benchmarks/workspaces/timestep-pilot-20261026 \
  --output /path/to/a/new/report
```

The analysis checks all expected case IDs and verifies scientific input/binary
compatibility within each model, allowing the intended timestep differences.
`analysis.json` records source evidence hashes and copied compact evidence hashes.
Per-run manifests include compiler, solver, model, hardware and input identities.
The report includes compact evidence under `data/`; full snapshots and raw
substrate/exchange trajectories remain in the campaign workspace. Derived plotted
trajectories are included in `tables/`. Original data were not edited.

Curves use recorded `after_cell_step` iteration timestamps. The clock advances
after this observation; the unchanged sample loop ends one diffusion interval
beyond nominal duration. Final snapshots therefore occur at 10.01, 10.005 or
10.0025 minutes, depending on diffusion dt. These conventions matter for any later
quantitative convergence analysis. No yield ground truth, accuracy tolerance or
reference-error estimate is imposed here. Diagnostic output frequency differs by
dt, so the recorded wall times are not an unbiased solver-speed comparison.

Figures were visually inspected. The isolated LP diagnostic preserved the original
per-update statuses and biomass values; its source changes and provenance are
archived separately under `diagnosis/`.
