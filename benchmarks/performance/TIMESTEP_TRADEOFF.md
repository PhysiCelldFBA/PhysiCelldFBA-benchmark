# Intracellular timestep: accuracy–cost trade-off

**Status:** decisions recorded 2026-10-27 (below); [check stage](../results/timestep/tradeoff-checks-20261027/README.md),
[Part A](../results/timestep/tradeoff-accuracy-20261027/README.md) and [Part B pilot](../results/timestep/tradeoff-cost-pilot-20261027/README.md)
done on the proposed-fix patch; **final runs in progress** ([plan](#final-runs-2026-11-02)). Campaigns are
prepared with [`prepare_tradeoff.py`](prepare_tradeoff.py).

## Question

PhysiCelldFBA lets the metabolic model update less often than diffusion
(`intracellular_dt = k × diffusion_dt`) to save computation. How much accuracy does
each ratio k cost, and how much time does it save? The result is an error-versus-
speed-up curve per model, from which users can choose a compromise.

## Prerequisites from the pilots

- Above k = 1, the merged code exchanged k times the FBA flux per window
  ([report](../results/timestep/exchange-fix-20261027/README.md)). The study runs on the
  **proposed-fix build**, so it measures the method rather than the defect. It will be
  re-run on the merged commit once a fix is accepted upstream.
- With the fix, the dominant large-k error in the pilots came from the **uptake cap**,
  which limits uptake over a whole window to the cell's own voxel content, with no
  diffusion credit. Its effect depends on voxel size, which ranges from 0.8–2 µm
  (bacterial projects) to 15–20 µm (cancer projects). The design therefore includes
  application-like voxel sizes, not only the 1.6 µm unit test.
- Biomass alone missed the defect. Substrate accounting is a required metric.

## Part A — accuracy (serial)

| Scenario | Model | Voxel | Cells | Medium |
|---|---|---|---|---|
| A1 | E. coli core | 1.6 µm (unit test) | 1 | 10 mM glucose (existing pilot) |
| A2 | E. coli core | 2 µm (bacterial colony) | 16, fixed positions | `ecoli_colony_fed` |
| A3 | MCF7 core | 15 µm (cancer_core_metabolism) | 1 | existing pilot setup |
| A4 | MCF7 core | 15 µm | 16, fixed positions | `mcf7_uniform_fed` |

- Ratios k = 1, 2, 5, 10, 20, 50, 100 at diffusion dt 0.01 min (intracellular dt
  0.01–1 min). k = 1 is the reference. A ratio-1 run at diffusion dt 0.005 min checks
  that the reference itself is converged.
- One thread; fixed positions and population; biomass growth on; standard FBA.
- Metrics, each relative to k = 1 of the same scenario:
  - final biomass and maximum relative biomass error along the trajectory;
  - substrate consumed (glucose; oxygen for cancer) and yield (biomass per glucose);
  - exchange-ledger pass/fail at every step;
  - minimum concentration;
  - infeasible or failed LP solves;
  - number of FBA updates.

## Part B — cost

- Lattice workloads from the performance profiles (fixed volume, minimal output),
  1000 cells, k = 1, 2, 5, 10, 20, 50, 100.
- Models: E. coli core, MCF7 core and iML1515 (≈2700 reactions, where LP time
  dominates and the saving should be largest).
- 1 and 56 threads, 3 repeats, one exclusive node per run.
- Metrics:
  - wall time;
  - the telemetry split between intracellular, exchange, diffusion and mechanics;
  - LP solves and their total time;
  - speed-up relative to k = 1.

## Outputs

Per model: error (Part A) against speed-up (Part B) for each k, with the
exchange-ledger and feasibility outcome shown on every point. Every attempt is retained.
No acceptance threshold is applied in the analysis; the manuscript states its choice.

## Size

- Part A: about 30 serial runs. At 60 simulated minutes, minutes of compute in total.
- Part B: 3 models × 7 ratios × 2 thread counts × 3 repeats = 126 runs. Sized from a
  pilot (1 repeat, 1 and 56 threads, k = 1, 10, 100) before submission.

## Decisions (2026-10-27)

1. **Duration from a test run.** Stage `checks` runs A1–A4 at k = 1 for 240 simulated
   minutes on the proposed-fix build. The Part A duration is chosen from when the
   substrates start to deplete, and the measured run times size the jobs.
2. **Diffusion dt stays at 0.01 min**, the PhysiCell default. The 0.001-min setting of
   some applications is not part of this study.
3. **iML1515 is included in Part B.** Its fed medium passes every
   [growth-condition check](../results/growth_conditions/growth-20261026/README.md) at
   dt 0.01 min. The failures at 0.1 and 1 min were measured on the pre-fix code. Stage
   `checks` re-runs it as a single cell at k = 1, 10 and 100 (60 min) on the fixed build
   before Part B.
4. **Part A runs on both builds.** Proposed fix and development, at every ratio, so that
   the defect is documented in the same study. Part B runs on the proposed-fix build only:
   development's timings would describe code that exchanges the wrong amounts.

Population is fixed: there is no division and positions are frozen, so biomass keeps
growing inside each cell (about 18× for E. coli over 240 min). This keeps ratio
comparisons deterministic. It is a numerical test of the metabolic coupling, not a
colony simulation.

## Final runs (2026-11-02)

The earlier stages ran PhysiCelldFBA `a2519f06` with the exchange fix as a local patch. The final
runs use the fix as submitted upstream, without patches:

- **Source:** PhysiCelldFBA PR `fix/intracellular-dt-exchange`, commit `c59daa81` (one commit on
  `development` @ `7f2b1d0a`). After the merge, the merged tree is compared with `c59daa81` and the
  result is recorded in [PROVENANCE.md](../../PROVENANCE.md); a difference in the engine or in the
  templates used means re-running the affected parts.
- **Unfixed comparison:** Part A also runs on `7f2b1d0a`, which has the defect, to document it in
  the same study.
- **Diffusion dt 0.01 and 0.001 min**, both for Part A (both builds) and Part B (fixed build).
  Diffusion dt is set explicitly per case (`--diffusion-dt`); voxel sizes come from the final
  sample configurations (A1 is now 2 µm, the unit-test default since `7f2b1d0a`).
- **iML1515** comes from [`benchmarks/assets/iml1515/`](../assets/iml1515/README.md), because it is
  no longer shipped with PhysiCelldFBA.
- **Part B jobs:** one Slurm job per model, thread count and k (`launch-<model>-p<threads>-q<k>.txt`,
  pinned in `campaign.sha256`, passed as the launcher's fourth argument). The 3 repeats of a group
  share one exclusive node, and all groups run on identical GPP nodes.
