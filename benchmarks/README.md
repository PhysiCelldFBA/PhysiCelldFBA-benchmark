# PhysiCelldFBA manuscript benchmarks

This directory contains reproducible experiments intended for the supplementary
material. Scripts, protocols and documentation are versioned here. Generated
campaigns and large simulation outputs belong in ignored `workspaces/` folders;
reviewed compact evidence, tables and figures can be committed under `results/`.

**Final results: [results/final-20261102](results/final-20261102/README.md)** (all studies, including the two completed on 2026-11-04). Every study below was
rerun on PhysiCelldFBA PR commit `c59daa81` (development `7f2b1d0a` + exchange fix), without
patches. The reports from 2026-10-26/27 linked in the table are earlier stages: they document how
the benchmark found the race conditions (fixed in PR #19) and the exchange-scaling defect. The
final report supersedes them.

| Study | Purpose | Protocol/code | Final (2026-11-02) | Earlier stages |
|---|---|---|---|---|
| Shared voxel | Eight cells in one voxel, serial/parallel execution and per-run update-order seeds | [voxel_sharing/README.md](voxel_sharing/README.md) | [60 runs](results/voxel_sharing/voxel-final-20261102/README.md): parallel identical to serial | [Pre-fix](results/voxel_sharing/voxel-20261026/README.md); [after PR #19](results/voxel_sharing/voxel-20261027/README.md) ([comparison](results/voxel_sharing/before-after-20261027/README.md)) |
| Mesh occupancy | Eight distinct fixed centers; 8/4/2/1 cells per occupied voxel | [voxel_sharing/MESH_STUDY.md](voxel_sharing/MESH_STUDY.md) | [240 runs](results/voxel_sharing/mesh-final-20261102/README.md): parallel identical to serial; [same as 2026-10-27](results/voxel_sharing/final-vs-20261027/README.md) | [Pre-fix](results/voxel_sharing/mesh-20261026/README.md); [after PR #19](results/voxel_sharing/mesh-20261027/README.md) |
| Intracellular timestep trade-off | Accuracy (A1–A4) and cost (3 models, 1/56 threads) for k = 1–100, diffusion dt 0.01 and 0.001 min | [performance/TIMESTEP_TRADEOFF.md](performance/TIMESTEP_TRADEOFF.md) | Accuracy [dt 0.01](results/timestep/tradeoff-accuracy-d0_01-final-20261102/README.md), [dt 0.001](results/timestep/tradeoff-accuracy-d0_001-final-20261102/README.md); cost [dt 0.01](results/timestep/tradeoff-cost-d0_01-final-20261102/README.md), [dt 0.001](results/timestep/tradeoff-cost-d0_001-final-20261102/README.md) | [Pilots](results/timestep/pilot-20261026/README.md); [exchange fix](results/timestep/exchange-fix-20261027/README.md); [checks](results/timestep/tradeoff-checks-20261027/README.md); [Part A](results/timestep/tradeoff-accuracy-20261027/README.md); [Part B pilot](results/timestep/tradeoff-cost-pilot-20261027/README.md) |
| Model-specific growth conditions | Native and supplied media, single cells and fixed-volume populations | [performance/model_conditions/README.md](performance/model_conditions/README.md) | [23 controls](results/growth_conditions/growth-final-20261102/README.md): 22 pass | [Pre-fix](results/growth_conditions/growth-20261026/README.md): 10 pass |
| Cancer FBA/pFBA | Single cell and the 240-cell application at intracellular dt 0.01 and 0.1 min | [performance/FINAL_STUDIES.md](performance/FINAL_STUDIES.md) | [8 runs](results/pfba/pfba-final-20261104/README.md): same growth, 192× less internal flux, 1.3–2× cost | — |
| Performance/scaling | Cells, fields, networks and threads; upstream/disabled baselines | [performance/FINAL_STUDIES.md](performance/FINAL_STUDIES.md) | [405 runs](results/performance/scaling-final-20261104/README.md): no add-on overhead; LPs scale to 38–41× on 56 threads | — |

`performance/` supplies shared build, input, telemetry and collection utilities.
The shared-voxel protocol uses the existing sample project's eight-cell test,
with disclosed benchmark controls and observations; it does not change production
solver algorithms or repair races. It also does not establish an architectural
guarantee of one cell per voxel. A smaller voxel reduces sharing risk for a given
cell distribution; measured occupancy and concurrency controls still matter.

Preparing the shared-voxel campaign creates all four study folders, each with
`inputs/`, `bundles/`, `runs/`, `tables/`, `plots/` and `logs/`. Only the shared-voxel
part is populated/submitted by that workflow. Git preserves the publication
table/plot directories through `.gitkeep` files in `results/<study>/`.

## Reproduction and publication

1. Check out the published source commit and read the study-specific README.
2. Build in an isolated directory using `performance/build.sh`; retain compiler,
   dependency, solver, source and executable provenance. Native compiler flags
   require a compatible execution CPU; record the resolved architecture.
3. Prepare a **new** campaign directory. Finalized input bundles carry checksums;
   do not edit them after staging. Regenerate bundles when moving to another host.
4. Submit only the selected study. Attempts are separate, including failed and
   diagnostically flagged runs. No preparation script submits jobs.
5. Run analysis manually in the documented Python environment. Verify coverage,
   order identity, actual thread counts, update counts and failed attempts before
   interpreting plots. Do not silently remove inconvenient outcomes.
6. Publish a report under `results/<study>/<campaign>/`, including the protocol,
   build/source identities, compact raw evidence, tables and figures. Keep bulky
   binaries, duplicated SBML bundles and MultiCellDS snapshots out of Git; provide
   an archival data link if full snapshots accompany the paper.

The report exporter is the study's analysis script. It copies compact per-run
telemetry, settings, manifests, hardware/resource metadata and logs alongside
its tables/plots, with checksums in `analysis.json`. These are collected results,
not fabricated examples. Before jobs finish, result and plot folders are empty.

Python preparation/collection uses the standard library. Plotting requires
Matplotlib. Additional snapshot analysis should prefer `pctk`; `pcdl` is not
required. On MN5 use the project's HDF5/Python 3.12.1 environment; analysis must
run in the allocation/environment described in the study README.
