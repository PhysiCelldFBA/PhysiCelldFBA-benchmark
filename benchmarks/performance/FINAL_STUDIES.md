# Cancer FBA/pFBA comparison and performance/scaling (final studies)

Both studies run on the benchmark version, PhysiCelldFBA `c59daa81` (see [PROVENANCE.md](../../PROVENANCE.md)).
They are prepared with [`prepare_final_studies.py`](prepare_final_studies.py) and implement the
corresponding rows of the agreed experiment table in [README.md](README.md). Decisions recorded on 2026-11-04:

## Cancer FBA vs pFBA (`--stage pfba`, 8 runs)

- MCF7 core; standard FBA against pFBA (parsimonious second stage, fraction of optimum 1). The two
  differ only in the secondary objective.
- Intracellular dt **0.01 and 0.1 min** with diffusion dt 0.01 (k = 1 and 10). Part A of the
  [trade-off study](TIMESTEP_TRADEOFF.md) found both accurate for cancer cells in 15 µm voxels.
- **Single cell:** fixed position and population, 240 min, per-step telemetry: trajectories,
  exchange fluxes, second-stage status. 1 thread.
- **Application:** the `cancer_core_metabolism` sample (240 cells from its CSV, normal multicellular
  behaviour: growth, division, death) for its 4320 min. Snapshots are saved hourly and per-step
  telemetry is off (`snapshots_hourly`), so wall times are not inflated by diagnostics. It runs on
  56 threads to stay within the 48 h job limit; FBA and pFBA use identical resources.
- Compare trajectories, cell numbers, substrates, exchange fluxes, second-stage failures and wall
  time, not only final biomass.

## Performance/scaling (`--stage scaling`)

- The `main` design in `study.json`: 100/1000/10000 cells at 1 and 56 threads; 1, 2, 4, 8, 16, 28,
  56 and 112 threads at 1000 cells; field counts at 1000 cells and 56 threads. Fields are raised to
  each model's minimum (23 for MCF7 core).
- E. coli core, MCF7 core and iML1515 ([asset](../assets/iml1515/README.md)), on the fed
  performance profiles: lattice, one cell per voxel, fixed volume and population.
- Variants: PhysiCelldFBA with metabolism, PhysiCelldFBA without metabolism (intracellular model
  removed from the input), and upstream PhysiCell `49d7cc54` with the core-only benchmark hooks.
  The physical workload and output are the same in all three.
- k = 1 at diffusion dt 0.01 min, 10 simulated minutes, minimal output, 3 repeats. One Slurm job
  per model, variant, cell count, thread count and field count; repeats share one exclusive GPP node.
- Memory: iML1515 needs about 2.5 GB per 1000 cells (measured), so about 25 GB at 10000 cells.
